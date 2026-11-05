package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type workshopPurchaseConfig struct {
	Enabled      bool    `json:"enabled"`
	TermsVersion string  `json:"terms_version"`
	TermsURL     *string `json:"terms_url"`
	PrivacyURL   *string `json:"privacy_url"`
	RefundURL    *string `json:"refund_url"`
	ContactURL   *string `json:"contact_url"`
	TaxNotice    *string `json:"tax_notice"`
}

func disabledWorkshopPurchaseConfig() workshopPurchaseConfig {
	return workshopPurchaseConfig{TermsVersion: "workshop-v1"}
}
func purchaseForbidden(c rune) bool {
	return c <= 32 || c >= 127 && c <= 160 || c == 0x1680 || c >= 0x2000 && c <= 0x200a || c == 0x2028 || c == 0x2029 || c == 0x202f || c == 0x205f || c == 0x3000 || c == 0xfeff
}

var purchaseURLPattern = regexp.MustCompile(`^https://([^/?#]+)(/[^?#]*)?$`)
var purchaseLabelPattern = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$`)
var purchaseFinalLabelPattern = regexp.MustCompile(`^[A-Za-z]{2,63}$`)

func purchaseURLValid(value string) bool {
	if len(value) == 0 || len(value) > 2048 || strings.ContainsFunc(value, purchaseForbidden) {
		return false
	}
	parts := purchaseURLPattern.FindStringSubmatch(value)
	if parts == nil {
		return false
	}
	host := strings.TrimSuffix(parts[1], ":443")
	labels := strings.Split(host, ".")
	if len(host) > 253 || len(labels) < 2 || !purchaseFinalLabelPattern.MatchString(labels[len(labels)-1]) {
		return false
	}
	for _, label := range labels {
		if !purchaseLabelPattern.MatchString(label) {
			return false
		}
	}
	for i := 0; i < len(parts[2]); i++ {
		if parts[2][i] == '%' {
			if i+2 >= len(parts[2]) {
				return false
			}
			if _, e := strconv.ParseUint(parts[2][i+1:i+3], 16, 8); e != nil {
				return false
			}
			i += 2
		}
	}
	return true
}

// Validate scalar escapes before encoding/json can silently replace lone surrogates.
// json.Valid supplies grammar validation; this pass tracks string escape boundaries.
func purchaseUnicodeValid(b []byte) bool {
	if !utf8.Valid(b) || !json.Valid(b) {
		return false
	}
	inString := false
	for i := 0; i < len(b); i++ {
		if b[i] == '"' {
			inString = !inString
			continue
		}
		if !inString || b[i] != '\\' {
			continue
		}
		i++
		if b[i] != 'u' {
			continue
		}
		n, e := strconv.ParseUint(string(b[i+1:i+5]), 16, 16)
		if e != nil {
			return false
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return false
		}
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(b) || b[i+1] != '\\' || b[i+2] != 'u' {
				return false
			}
			low, e := strconv.ParseUint(string(b[i+3:i+7]), 16, 16)
			if e != nil || low < 0xdc00 || low > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return true
}

// Scan every object recursively so duplicate occurrences cannot be overwritten.
func purchaseJSONValue(d *json.Decoder) error {
	tok, e := d.Token()
	if e != nil {
		return e
	}
	switch tok {
	case json.Delim('{'):
		seen := map[string]bool{}
		for d.More() {
			key, e := d.Token()
			if e != nil {
				return e
			}
			s, ok := key.(string)
			if !ok || seen[s] {
				return fmt.Errorf("duplicate key")
			}
			seen[s] = true
			if e := purchaseJSONValue(d); e != nil {
				return e
			}
		}
		end, e := d.Token()
		if e != nil || end != json.Delim('}') {
			return fmt.Errorf("object")
		}
	case json.Delim('['):
		for d.More() {
			if e := purchaseJSONValue(d); e != nil {
				return e
			}
		}
		end, e := d.Token()
		if e != nil || end != json.Delim(']') {
			return fmt.Errorf("array")
		}
	}
	return nil
}
func decodeWorkshopPurchaseConfig(b []byte) (workshopPurchaseConfig, error) {
	bad := func() (workshopPurchaseConfig, error) {
		return workshopPurchaseConfig{}, fmt.Errorf("invalid purchase configuration")
	}
	if len(b) > 16384 || !purchaseUnicodeValid(b) {
		return bad()
	}
	d := json.NewDecoder(bytes.NewReader(b))
	if purchaseJSONValue(d) != nil {
		return bad()
	}
	if _, e := d.Token(); e != io.EOF {
		return bad()
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(b, &fields) != nil || len(fields) != 7 {
		return bad()
	}
	for _, key := range []string{"enabled", "terms_version", "terms_url", "privacy_url", "refund_url", "contact_url", "tax_notice"} {
		if _, ok := fields[key]; !ok {
			return bad()
		}
	}
	var enabled any
	if json.Unmarshal(fields["enabled"], &enabled) != nil {
		return bad()
	}
	if _, ok := enabled.(bool); !ok {
		return bad()
	}
	var result workshopPurchaseConfig
	if json.Unmarshal(b, &result) != nil || result.TermsVersion != "workshop-v1" {
		return bad()
	}
	urls := []*string{result.TermsURL, result.PrivacyURL, result.RefundURL, result.ContactURL}
	if !result.Enabled {
		for _, value := range append(urls, result.TaxNotice) {
			if value != nil {
				return bad()
			}
		}
		return disabledWorkshopPurchaseConfig(), nil
	}
	for _, value := range urls {
		if value == nil || !purchaseURLValid(*value) {
			return bad()
		}
	}
	if result.TaxNotice == nil || len(*result.TaxNotice) > 1024 || strings.TrimFunc(*result.TaxNotice, purchaseForbidden) == "" || strings.ContainsFunc(*result.TaxNotice, func(c rune) bool { return c < 32 || c >= 127 && c <= 159 || c == 0x2028 || c == 0x2029 }) {
		return bad()
	}
	return result, nil
}
func (s *Server) workshopPurchaseConfig(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	fail := func(status int, code string) {
		if r.Method == http.MethodHead {
			w.WriteHeader(status)
			return
		}
		writeAPIError(w, r, status, code, "Purchase configuration unavailable.", false)
	}
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		fail(405, "INVALID_REQUEST")
		return
	}
	if r.URL.RawQuery != "" || r.URL.ForceQuery {
		fail(400, "INVALID_REQUEST")
		return
	}
	result := disabledWorkshopPurchaseConfig()
	if s.commerceClient != nil {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		status, b, e := s.commerceClient.Do(ctx, "purchase-config", []byte(`{}`), "")
		if e != nil || status != 200 {
			fail(503, "COMMERCE_UNAVAILABLE")
			return
		}
		result, e = decodeWorkshopPurchaseConfig(b)
		if e != nil {
			fail(503, "COMMERCE_UNAVAILABLE")
			return
		}
	}
	w.WriteHeader(200)
	if r.Method != http.MethodHead {
		json.NewEncoder(w).Encode(result)
	}
}
