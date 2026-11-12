package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// A public presentation signal, never an access grant. Both processes must
// independently agree that the merchant is in test mode before showing it.
func workshopProductionOrigin(origin string) bool {
	u, err := url.Parse(origin)
	if err != nil {
		return false
	}
	host := strings.TrimSuffix(strings.ToLower(u.Hostname()), ".")
	return host == "cars.tk" || host == "autodata.cars.tk"
}

func workshopTestCheckoutMode(mode, environment, authMode, origin string) bool {
	if mode != "stripe_test" || authMode != "firebase" || origin == "" || workshopProductionOrigin(origin) {
		return false
	}
	switch environment {
	case "test", "development", "staging":
		return true
	default:
		return false
	}
}

func workshopPrivateTestModeReady(body []byte) bool {
	if len(body) > 256 {
		return false
	}
	d := json.NewDecoder(bytes.NewReader(body))
	open, err := d.Token()
	if err != nil || open != json.Delim('{') {
		return false
	}
	var mode string
	var purchaseEnabled, hasMode, hasPurchase bool
	for d.More() {
		token, err := d.Token()
		if err != nil {
			return false
		}
		key, ok := token.(string)
		if !ok {
			return false
		}
		switch key {
		case "mode":
			if hasMode || d.Decode(&mode) != nil {
				return false
			}
			hasMode = true
		case "purchase_enabled":
			if hasPurchase || d.Decode(&purchaseEnabled) != nil {
				return false
			}
			hasPurchase = true
		default:
			return false
		}
	}
	close, err := d.Token()
	if err != nil || close != json.Delim('}') {
		return false
	}
	var trailing any
	return d.Decode(&trailing) == io.EOF && hasMode && hasPurchase && mode == "stripe_test" && purchaseEnabled
}

func (s *Server) workshopDemoMode(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if r.URL.RawQuery != "" || r.URL.ForceQuery {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	enabled := false
	if s.workshopTestCheckout && s.commerceClient != nil {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		status, body, err := s.commerceClient.Do(ctx, "demo-mode", []byte(`{}`), "")
		if err == nil && status == http.StatusOK {
			enabled = workshopPrivateTestModeReady(body)
		}
	}
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_ = json.NewEncoder(w).Encode(struct {
			Enabled bool `json:"enabled"`
		}{Enabled: enabled})
	}
}
