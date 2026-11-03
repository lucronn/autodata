package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCommerceClientPrivateBoundary(t *testing.T) {
	raw := []byte("{\n \"signed\": true\n}")
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.Header.Get("X-Autodata-Internal-Token") != "server-token" {
			t.Error("missing private authentication")
		}
		for _, h := range []string{"Cookie", "Authorization", "X-Autodata-Owner-Id", "X-Autodata-Organization-Id"} {
			if r.Header.Get(h) != "" {
				t.Errorf("forwarded %s", h)
			}
		}
		if r.URL.Path != "/internal/commerce/stripe/webhook" || r.Header.Get("Stripe-Signature") != "t=1,v1=opaque" {
			t.Error("wrong webhook seam")
		}
		b, _ := io.ReadAll(r.Body)
		if string(b) != string(raw) {
			t.Error("changed signed bytes")
		}
		io.WriteString(w, `{"status":"accepted"}`)
	}))
	defer private.Close()
	c, err := NewHTTPCommerceClient(private.URL, "server-token")
	if err != nil {
		t.Fatal(err)
	}
	status, b, err := c.Do(context.Background(), "stripe/webhook", raw, "t=1,v1=opaque")
	if err != nil || status != 200 || string(b) != `{"status":"accepted"}` {
		t.Fatal(status, string(b), err)
	}
	for _, tc := range []struct{ url, token string }{{private.URL, ""}, {private.URL + "/path", "x"}, {"http://user:pass@localhost", "x"}, {"http://localhost?x=y", "x"}, {"ftp://localhost", "x"}} {
		if _, err := NewHTTPCommerceClient(tc.url, tc.token); err == nil {
			t.Error("unsafe config accepted", tc.url)
		}
	}
	if _, _, err := c.Do(context.Background(), "../catalog", nil, ""); err == nil {
		t.Error("arbitrary operation accepted")
	}
}
func TestCommerceClientBoundsAndRedirects(t *testing.T) {
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { t.Error("redirect followed") }))
	defer target.Close()
	for _, tc := range []struct {
		name  string
		serve http.HandlerFunc
	}{{"redirect", func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, target.URL, 307) }}, {"oversize", func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, strings.Repeat("x", maxCommerceResponseBytes+1))
	}}} {
		t.Run(tc.name, func(t *testing.T) {
			s := httptest.NewServer(tc.serve)
			defer s.Close()
			c, _ := NewHTTPCommerceClient(s.URL, "token")
			status, _, err := c.Do(context.Background(), "quote", []byte(`{}`), "")
			if err == nil && status >= 200 && status < 300 {
				t.Fatal("unsafe response accepted")
			}
		})
	}
}
func TestCommerceGrantTypedOutcomes(t *testing.T) {
	for _, tc := range []struct {
		status int
		body   string
		want   error
	}{{200, `{"entitlement_id":"11111111-1111-4111-8111-111111111111","order_id":"22222222-2222-4222-8222-222222222222","configuration_id":"33333333-3333-4333-8333-333333333333","region":"US"}`, nil}, {403, `{"error":{"code":"ENTITLEMENT_REQUIRED"}}`, ErrVehicleGrantRequired}, {403, `{"error":{"code":"ENTITLEMENT_REVOKED"}}`, ErrVehicleGrantRevoked}, {503, `{"error":{"code":"database secret"}}`, ErrVehicleGrantUnavailable}, {200, `{"entitlement_id":"bad","order_id":"bad","configuration_id":"33333333-3333-4333-8333-333333333333","region":"US"}`, ErrVehicleGrantUnavailable}} {
		t.Run(tc.body, func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var b map[string]any
				json.NewDecoder(r.Body).Decode(&b)
				if b["customer_account_id"] != "account" || b["configuration_id"] != "33333333-3333-4333-8333-333333333333" {
					t.Error("wrong scope")
				}
				w.WriteHeader(tc.status)
				io.WriteString(w, tc.body)
			}))
			defer s.Close()
			c, _ := NewHTTPCommerceClient(s.URL, "token")
			_, err := c.CheckVehicleGrant(context.Background(), "account", "33333333-3333-4333-8333-333333333333", "US")
			if err != tc.want {
				t.Fatal(err, tc.want)
			}
		})
	}
}
