package main

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
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
				if b["customer_account_id"] != "account" || b["organization_id"] != "org" || len(b) != 4 || b["configuration_id"] != "33333333-3333-4333-8333-333333333333" {
					t.Error("wrong scope")
				}
				w.WriteHeader(tc.status)
				io.WriteString(w, tc.body)
			}))
			defer s.Close()
			c, _ := NewHTTPCommerceClient(s.URL, "token")
			_, err := c.CheckVehicleGrant(context.Background(), "account", "org", "33333333-3333-4333-8333-333333333333", "US")
			if err != tc.want {
				t.Fatal(err, tc.want)
			}
		})
	}
}

func TestCommerceClientSanitizedCorrelationAndDeadlines(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Request-ID") != "commerce-safe-request" {
			t.Error("missing safe correlation")
		}
		io.WriteString(w, `{}`)
	}))
	defer s.Close()
	c, _ := NewHTTPCommerceClient(s.URL, "token")
	c.client.Transport = commerceRoundTrip(func(r *http.Request) (*http.Response, error) {
		deadline, ok := r.Context().Deadline()
		if !ok || time.Until(deadline) <= 0 || time.Until(deadline) > 2*time.Second {
			t.Error("missing read deadline")
		}
		return http.DefaultTransport.RoundTrip(r)
	})
	ctx := context.WithValue(context.Background(), requestIDContextKey, "commerce-safe-request")
	if _, _, err := c.Do(ctx, "quote", []byte(`{}`), ""); err != nil {
		t.Fatal(err)
	}
}
func TestCommerceConfigurationFailsClosed(t *testing.T) {
	for _, tc := range []struct {
		mode, url, token     string
		wantErr, wantEnabled bool
	}{{"disabled", "", "", false, false}, {"", "", "", false, false}, {"stripe_test", "http://localhost:8081", "token", false, true}, {"stripe_live", "http://localhost:8081", "token", false, true}, {"stripe_live", "http://localhost:8081", "", true, false}, {"stripe_test", "", "token", true, false}, {"automatic", "http://localhost:8081", "token", true, false}} {
		t.Run(tc.mode+tc.token+tc.url, func(t *testing.T) {
			values := map[string]string{"AUTODATA_COMMERCE_MODE": tc.mode, "AUTODATA_INGESTION_URL": tc.url, "AUTODATA_INGESTION_INTERNAL_TOKEN": tc.token}
			c, e := configuredCommerceClient(func(k string) string { return values[k] })
			if (e != nil) != tc.wantErr || (c != nil) != tc.wantEnabled {
				t.Fatal(c, e)
			}
		})
	}
}

type commerceRoundTrip func(*http.Request) (*http.Response, error)

func (f commerceRoundTrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

// TestWorkshopCommercePythonIntegration is invoked only by the first required
// real-PostgreSQL commerce case while its actual Python private HTTP server is
// running. It reuses that case's existing order/key; it never creates fixtures.
func TestWorkshopCommercePythonIntegration(t *testing.T) {
	if os.Getenv("AUTODATA_REQUIRE_COMMERCE_INTEGRATION") != "1" {
		t.Skip("requires the isolated Python commerce/PostgreSQL fixture")
	}
	fixture := make(map[string]string)
	for _, name := range []string{"URL", "ACCOUNT_ID", "ORGANIZATION_ID", "CONFIGURATION_ID", "IDEMPOTENCY_KEY", "ORDER_ID", "REGION"} {
		value := os.Getenv("AUTODATA_COMMERCE_FIXTURE_" + name)
		if value == "" {
			t.Fatalf("required fixture input %s is missing", name)
		}
		fixture[name] = value
	}
	target, err := url.Parse(fixture["URL"])
	if err != nil || target == nil || target.Scheme != "http" || target.Hostname() != "127.0.0.1" || target.User != nil || target.Path != "" || target.RawQuery != "" || target.ForceQuery || target.Fragment != "" || target.Opaque != "" {
		t.Fatal("fixture URL must be an explicit loopback HTTP authority")
	}
	host, portText, err := net.SplitHostPort(target.Host)
	port, portErr := strconv.Atoi(portText)
	if err != nil || host != "127.0.0.1" || portErr != nil || port < 1 || port > 65535 || fixture["URL"] != "http://127.0.0.1:"+strconv.Itoa(port) {
		t.Fatal("fixture URL must have a canonical valid explicit port")
	}
	for _, name := range []string{"ACCOUNT_ID", "ORGANIZATION_ID", "CONFIGURATION_ID", "IDEMPOTENCY_KEY", "ORDER_ID"} {
		if !commerceUUID(fixture[name]) {
			t.Fatalf("fixture %s must be a canonical UUID", name)
		}
	}
	if fixture["REGION"] != "US" {
		t.Fatal("fixture region must be US")
	}
	client, err := NewHTTPCommerceClient(fixture["URL"], "fixture-internal")
	if err != nil {
		t.Fatal("fixture client configuration failed")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	invoke := func(operation string, input map[string]any) any {
		t.Helper()
		body, err := json.Marshal(input)
		if err != nil {
			t.Fatal("fixture input serialization failed")
		}
		status, raw, err := client.Do(ctx, operation, body, "")
		if err != nil || status != 200 {
			t.Fatalf("actual Python %s response failed: HTTP %d", operation, status)
		}
		projected, ok := commercePublicResult(operation, status, raw, input)
		if !ok {
			t.Fatalf("actual Python %s response violates the public DTO contract", operation)
		}
		return projected
	}
	scope := map[string]any{"configuration_id": fixture["CONFIGURATION_ID"], "region": fixture["REGION"]}
	invoke("quote", scope)
	owner := func() map[string]any {
		return map[string]any{"customer_account_id": fixture["ACCOUNT_ID"], "organization_id": fixture["ORGANIZATION_ID"]}
	}
	input := owner()
	input["configuration_id"], input["region"], input["terms_version"], input["idempotency_key"] = fixture["CONFIGURATION_ID"], fixture["REGION"], "workshop-v1", fixture["IDEMPOTENCY_KEY"]
	checkout := invoke("checkouts", input).(commerceCheckout)
	if checkout.State != "checkout" || checkout.OrderID != fixture["ORDER_ID"] {
		t.Fatal("fixture checkout did not reuse the existing unpaid order")
	}
	input = owner()
	input["order_id"] = fixture["ORDER_ID"]
	status := invoke("orders/status", input).(commerceOrder)
	if status.ConfigurationID != fixture["CONFIGURATION_ID"] || status.Region != fixture["REGION"] || status.State != "open" {
		t.Fatal("fixture order status changed owner scope or unpaid state")
	}
	input = owner()
	input["cursor"], input["limit"] = "", 20
	library := invoke("library", input).(commerceLibrary)
	if !commerceFixtureLibraryHasNoGrant(library) {
		t.Fatal("unpaid fixture must have no library grant")
	}
	if _, err := client.CheckVehicleGrant(ctx, fixture["ACCOUNT_ID"], fixture["ORGANIZATION_ID"], fixture["CONFIGURATION_ID"], fixture["REGION"]); err != ErrVehicleGrantRequired {
		t.Fatal("unpaid fixture must return the typed required grant outcome")
	}
}

func commerceFixtureLibraryHasNoGrant(library commerceLibrary) bool {
	return len(library.Items) == 0 && (library.NextCursor == nil || *library.NextCursor == "")
}

func TestCommerceFixtureLibraryTerminalCursorProjection(t *testing.T) {
	for _, tc := range []struct {
		name, cursor, items string
		wantNoGrant         bool
	}{
		{"null terminal", "null", "[]", true},
		{"empty terminal", `""`, "[]", true},
		{"nonempty continuation", `"continue"`, "[]", false},
		{"existing grant", "null", `[{"library_item_id":"22222222-2222-4222-8222-222222222222","configuration_id":"33333333-3333-4333-8333-333333333333","region":"US","label":"Vehicle","access_state":"paid","granted_at":"2026-11-03T20:00:00+00:00"}]`, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw := []byte(`{"version":"v1","items":` + tc.items + `,"next_cursor":` + tc.cursor + `}`)
			projected, ok := commercePublicResult("library", 200, raw, map[string]any{"limit": 20})
			if !ok {
				t.Fatal("valid library cursor representation rejected")
			}
			if commerceFixtureLibraryHasNoGrant(projected.(commerceLibrary)) != tc.wantNoGrant {
				t.Fatal("fixture no-grant assertion misclassified projected library")
			}
		})
	}
}

func TestCommercePurchaseConfigPrivateBoundary(t *testing.T) {
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		if r.URL.Path != "/internal/commerce/purchase-config" || r.Method != "POST" || r.Header.Get("X-Autodata-Internal-Token") != "fixture-token" || string(b) != "{}" || r.Header.Get("Stripe-Signature") != "" {
			t.Error("invalid config operation")
		}
		io.WriteString(w, purchaseEnabled)
	}))
	defer private.Close()
	c, _ := NewHTTPCommerceClient(private.URL, "fixture-token")
	c.client.Transport = commerceRoundTrip(func(r *http.Request) (*http.Response, error) {
		deadline, ok := r.Context().Deadline()
		if !ok || time.Until(deadline) > 2*time.Second {
			t.Error("unbounded config deadline")
		}
		return http.DefaultTransport.RoundTrip(r)
	})
	status, b, e := c.Do(context.Background(), "purchase-config", []byte(`{}`), "")
	if e != nil || status != 200 || string(b) != purchaseEnabled {
		t.Fatal(status, string(b), e)
	}
}
