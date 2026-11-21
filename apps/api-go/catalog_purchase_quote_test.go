package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type paidIndexQuoteClient struct {
	*paidGrantClient
	commerceFixture
}

func (c paidIndexQuoteClient) Do(ctx context.Context, op string, body []byte, signature string) (int, []byte, error) {
	return c.commerceFixture.Do(ctx, op, body, signature)
}

func TestPaidIndexPurchaseQuoteResponse(t *testing.T) {
	fresh := `{"version":"v1","product_key":"workshop-configuration-v1","configuration_id":"` + paidTestConfiguration +
		`","region":"CA","configuration_label":"Approved configuration","amount_minor":2000,"currency":"USD","purchase_terms_version":"workshop-v1","purchasable":true,"private":"must not leak"}`
	for _, tc := range []struct {
		name   string
		status int
		body   string
		err    error
		object bool
	}{
		{"valid", 200, fresh, nil, true},
		{"private 503", 503, `{"error":{"code":"COMMERCE_UNAVAILABLE","message":"must not leak"}}`, nil, false},
		{"other scope", 200, strings.Replace(fresh, `"CA"`, `"US"`, 1), nil, false},
		{"invalid amount", 200, strings.Replace(fresh, "2000", "1600", 1), nil, false},
		{"not purchasable", 200, strings.Replace(fresh, "true", "false", 1), nil, false},
		{"transport", 0, "", errors.New("must not leak"), false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, store, grant := paidHTTPServer()
			quotes := 0
			s.commerceClient = paidIndexQuoteClient{grant, func(ctx context.Context, op string, body []byte, signature string) (int, []byte, error) {
				quotes++
				if grant.calls != 1 || op != "quote" || signature != "" {
					t.Fatalf("unexpected %s after %d grant checks", op, grant.calls)
				}
				var input map[string]string
				if err := json.Unmarshal(body, &input); err != nil || len(input) != 2 ||
					input["configuration_id"] != paidTestConfiguration || input["region"] != "CA" {
					t.Fatalf("quote input %s", body)
				}
				deadline, ok := ctx.Deadline()
				if !ok || time.Until(deadline) > commerceTimeout("quote") {
					t.Fatal("quote call lost its own timeout")
				}
				return tc.status, []byte(tc.body), tc.err
			}}
			req := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles?region=CA", nil)
			req.Header.Set("Prefer", "other, "+purchaseQuotePreference)
			w := httptest.NewRecorder()
			s.Handler().ServeHTTP(w, req)
			var envelope struct {
				Error struct {
					Code      string                     `json:"code"`
					Message   string                     `json:"message"`
					RequestID string                     `json:"request_id"`
					Retryable bool                       `json:"retryable"`
					Details   map[string]json.RawMessage `json:"details"`
				} `json:"error"`
			}
			if err := json.Unmarshal(w.Body.Bytes(), &envelope); err != nil {
				t.Fatal(err)
			}
			got := envelope.Error
			if w.Code != http.StatusForbidden || got.Code != "ENTITLEMENT_REQUIRED" ||
				got.Message != "Purchase access to this vehicle configuration." || got.RequestID == "" || got.Retryable ||
				w.Header().Get("Preference-Applied") != purchaseQuotePreference || w.Header().Get("Cache-Control") != "private, no-store" ||
				quotes != 1 || store.protected != 0 || strings.Contains(w.Body.String(), "must not leak") {
				t.Fatalf("status=%d headers=%v quotes=%d protected=%d body=%s", w.Code, w.Header(), quotes, store.protected, w.Body)
			}
			if len(got.Details) != 1 {
				t.Fatalf("unexpected details %s", w.Body)
			}
			detail := got.Details["purchase_quote"]
			if !tc.object {
				if string(detail) != "null" {
					t.Fatalf("unusable quote details=%s", detail)
				}
				return
			}
			var quote commerceQuote
			if err := json.Unmarshal(detail, &quote); err != nil || !quote.Purchasable ||
				quote.ConfigurationID != paidTestConfiguration || quote.Region != "CA" || quote.AmountMinor != 2000 ||
				quote.ConfigurationLabel != "Approved configuration" {
				t.Fatalf("invalid quote: %s", detail)
			}
		})
	}
}

func TestPaidIndexPurchaseQuoteDoesNotRunOutsideExactDeniedIndex(t *testing.T) {
	index := "/v1/catalog/vehicles/" + paidTestConfiguration + "/articles"
	detail := index + "/55555555-5555-4555-8555-555555555555"
	for _, tc := range []struct {
		name, method, path string
		grantErr           error
		status             int
		grants             int
	}{
		{"no preference", "GET", index + "?region=CA", ErrVehicleGrantRequired, 403, 1},
		{"missing region", "GET", index, ErrVehicleGrantRequired, 403, 1},
		{"wrong region", "GET", index + "?region=US", ErrVehicleGrantRequired, 404, 0},
		{"duplicate region", "GET", index + "?region=CA&region=CA", ErrVehicleGrantRequired, 404, 0},
		{"legacy vehicle", "GET", "/v1/catalog/vehicles/" + paidTestVehicle + "/articles?region=CA", ErrVehicleGrantRequired, 404, 0},
		{"search", "GET", index + "?region=CA&q=pump", ErrVehicleGrantRequired, 403, 1},
		{"empty search", "GET", index + "?region=CA&q=", ErrVehicleGrantRequired, 403, 1},
		{"head", "HEAD", index + "?region=CA", ErrVehicleGrantRequired, 403, 1},
		{"reader", "GET", detail + "?region=CA", ErrVehicleGrantRequired, 403, 1},
		{"source", "GET", detail + "/source?region=CA", ErrVehicleGrantRequired, 403, 1},
		{"revoked", "GET", index + "?region=CA", ErrVehicleGrantRevoked, 403, 1},
		{"grant dependency", "GET", index + "?region=CA", ErrVehicleGrantUnavailable, 503, 1},
		{"owned", "GET", index + "?region=CA", nil, 200, 1},
		{"unauthed", "GET", index + "?region=CA", ErrVehicleGrantRequired, 401, 0},
		{"open demo", "GET", index + "?region=CA&demo=1", ErrVehicleGrantRequired, 200, 0},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, _, grant := paidHTTPServer()
			grant.err = tc.grantErr
			if tc.name == "unauthed" || tc.name == "open demo" {
				s.auth = &fakeAuthenticator{err: ErrUnauthenticated}
			}
			if tc.name == "open demo" {
				s.workshopOpenDemoHost = "localhost:3013"
			}
			req := httptest.NewRequest(tc.method, "http://localhost:3013"+tc.path, nil)
			if tc.name != "no preference" {
				req.Header.Set("Prefer", purchaseQuotePreference)
			}
			w := httptest.NewRecorder()
			s.Handler().ServeHTTP(w, req)
			if w.Code != tc.status || grant.calls != tc.grants ||
				w.Header().Get("Preference-Applied") != "" || strings.Contains(w.Body.String(), "purchase_quote") {
				t.Fatalf("status=%d grants=%d headers=%v body=%s", w.Code, grant.calls, w.Header(), w.Body)
			}
		})
	}
}
