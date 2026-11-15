package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func configuredReadOnlyCommerce(t *testing.T, endpoint string) CommerceClient {
	t.Helper()
	values := map[string]string{"AUTODATA_COMMERCE_MODE": "read_only", "AUTODATA_ENV": "production", "AUTODATA_AUTH_MODE": "firebase", "AUTODATA_PUBLIC_ORIGIN": "https://autodata.cars.tk", "AUTODATA_INGESTION_URL": endpoint, "AUTODATA_INGESTION_INTERNAL_TOKEN": "read-only-private-token"}
	client, err := configuredCommerceClient(func(key string) string { return values[key] })
	if err != nil || client == nil {
		t.Fatalf("configure read-only commerce: %v", err)
	}
	if _, ok := client.(VehicleGrantChecker); !ok {
		t.Fatal("read-only client lost required grant checker")
	}
	return client
}

func TestReadOnlyCommerceConfiguration(t *testing.T) {
	for _, origin := range []string{"https://cars.tk", "https://autodata.cars.tk"} {
		for _, tc := range []struct {
			endpoint, token string
			valid           bool
		}{{"http://127.0.0.1:3031", "private-token", true}, {"", "private-token", false}, {"http://127.0.0.1:3031", "", false}, {"http://127.0.0.1:3031/path", "private-token", false}} {
			values := map[string]string{"AUTODATA_COMMERCE_MODE": "read_only", "AUTODATA_PUBLIC_ORIGIN": origin, "AUTODATA_INGESTION_URL": tc.endpoint, "AUTODATA_INGESTION_INTERNAL_TOKEN": tc.token}
			c, err := configuredCommerceClient(func(key string) string { return values[key] })
			if (err == nil && c != nil) != tc.valid {
				t.Fatalf("origin=%s endpoint=%s valid=%v err=%v", origin, tc.endpoint, tc.valid, err)
			}
		}
	}
}

func TestReadOnlyCommerceAuthenticatedReads(t *testing.T) {
	calls := map[string]int{}
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		operation := strings.TrimPrefix(r.URL.Path, "/internal/commerce/")
		calls[operation]++
		if r.Method != "POST" || r.Header.Get("X-Autodata-Internal-Token") != "read-only-private-token" {
			t.Error("missing private authentication")
		}
		for _, header := range []string{"Cookie", "Authorization", "X-Autodata-Owner-Id", "Stripe-Signature"} {
			if r.Header.Get(header) != "" {
				t.Errorf("browser authority leaked: %s", header)
			}
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
		}
		if operation != "quote" && (body["customer_account_id"] != "11111111-1111-4111-8111-111111111111" || body["organization_id"] != "44444444-4444-4444-8444-444444444444") {
			t.Error("lost authenticated ownership", body)
		}
		switch operation {
		case "quote":
			if body["configuration_id"] != commerceConfigID || body["region"] != "US" || len(body) != 2 {
				t.Error("changed quote scope", body)
			}
			io.WriteString(w, `{"version":"v1","product_key":"workshop-configuration-v1","configuration_id":"`+commerceConfigID+`","region":"US","configuration_label":"Vehicle","amount_minor":2000,"currency":"USD","purchase_terms_version":"workshop-v1","purchasable":true}`)
		case "library":
			if body["limit"] != float64(20) || body["cursor"] != "" || len(body) != 4 {
				t.Error("changed library request", body)
			}
			io.WriteString(w, `{"version":"v1","items":[],"next_cursor":null}`)
		case "grants/check":
			if body["configuration_id"] != commerceConfigID || body["region"] != "US" || len(body) != 4 {
				t.Error("changed grant scope", body)
			}
			io.WriteString(w, `{"entitlement_id":"11111111-1111-4111-8111-111111111111","order_id":"`+commerceOrderID+`","configuration_id":"`+commerceConfigID+`","region":"US"}`)
		default:
			t.Errorf("unexpected private operation %s", operation)
			w.WriteHeader(500)
		}
	}))
	defer private.Close()
	client := configuredReadOnlyCommerce(t, private.URL)
	s, cookie, _ := commerceTestAPI(t, client)
	for _, path := range []string{"/v1/workshop/quote?configuration_id=" + commerceConfigID + "&region=US", "/v1/workshop/library"} {
		w := customerHTTP(t, s.Handler(), "GET", path, "", nil, cookie)
		if w.Code != 200 {
			t.Fatalf("%s status=%d body=%s", path, w.Code, w.Body.String())
		}
	}
	if w := customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library", "", nil, nil); w.Code != 401 {
		t.Fatal("library authentication bypassed", w.Code)
	}
	grant, err := client.(VehicleGrantChecker).CheckVehicleGrant(context.Background(), "11111111-1111-4111-8111-111111111111", "44444444-4444-4444-8444-444444444444", commerceConfigID, "US")
	if err != nil || grant.ConfigurationID != commerceConfigID {
		t.Fatal(grant, err)
	}
	for _, op := range []string{"quote", "library", "grants/check"} {
		if calls[op] != 1 {
			t.Errorf("%s calls=%d", op, calls[op])
		}
	}
}

func TestReadOnlyCommerceGrantDenials(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		body   string
		want   error
	}{
		{"unpaid or wrong owner", 403, `{"error":{"code":"ENTITLEMENT_REQUIRED"}}`, ErrVehicleGrantRequired},
		{"revoked", 403, `{"error":{"code":"ENTITLEMENT_REVOKED"}}`, ErrVehicleGrantRevoked},
		{"private unavailable", 503, `{"error":{"code":"private secret"}}`, ErrVehicleGrantUnavailable},
		{"wrong scope", 200, `{"entitlement_id":"11111111-1111-4111-8111-111111111111","order_id":"` + commerceOrderID + `","configuration_id":"44444444-4444-4444-8444-444444444444","region":"US"}`, ErrVehicleGrantUnavailable},
		{"wrong region", 200, `{"entitlement_id":"11111111-1111-4111-8111-111111111111","order_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"CA"}`, ErrVehicleGrantUnavailable},
	} {
		t.Run(tc.name, func(t *testing.T) {
			private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(tc.status); io.WriteString(w, tc.body) }))
			defer private.Close()
			client := configuredReadOnlyCommerce(t, private.URL)
			_, err := client.(VehicleGrantChecker).CheckVehicleGrant(context.Background(), "account", "org", commerceConfigID, "US")
			if !errors.Is(err, tc.want) {
				t.Fatalf("got %v want %v", err, tc.want)
			}
		})
	}
}

func TestReadOnlyCommerceCannotEnablePurchasesOrReachPayments(t *testing.T) {
	calls := 0
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; io.WriteString(w, purchaseEnabled) }))
	defer private.Close()
	client := configuredReadOnlyCommerce(t, private.URL)
	s, cookie, csrf := commerceTestAPI(t, client)
	for _, method := range []string{"GET", "HEAD"} {
		w := customerHTTP(t, s.Handler(), method, "/workshop/purchase-config.json", "", nil, nil)
		if w.Code != 200 || w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal(w.Code, w.Header())
		}
		if method == "GET" {
			got, err := decodeWorkshopPurchaseConfig(w.Body.Bytes())
			if err != nil || got.Enabled || strings.TrimSpace(w.Body.String()) != purchaseDisabled {
				t.Fatal(w.Body.String(), err)
			}
		} else if w.Body.Len() != 0 {
			t.Fatal("HEAD returned body")
		}
	}
	for _, testFlag := range []bool{false, true} {
		s.workshopTestCheckout = testFlag
		w := customerHTTP(t, s.Handler(), "GET", "/workshop/demo-mode.json", "", nil, nil)
		if w.Code != 200 || strings.TrimSpace(w.Body.String()) != `{"enabled":false}` {
			t.Fatal(w.Code, w.Body.String())
		}
	}
	s.workshopTestCheckout = false
	headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}
	for _, tc := range []struct {
		method, path, body string
		headers            map[string]string
		cookie             *http.Cookie
	}{
		{"POST", "/v1/workshop/checkout-sessions", commerceCheckoutBody, headers, cookie},
		{"POST", "/v1/workshop/checkout-sessions", strings.TrimSuffix(commerceCheckoutBody, "}") + `,"expected_mode":"stripe_test"}`, headers, cookie},
		{"POST", "/v1/payments/stripe/webhook", `{"signed":true}`, map[string]string{"Stripe-Signature": "t=1,v1=opaque"}, nil},
		{"GET", "/v1/workshop/orders/" + commerceOrderID, "", nil, cookie},
	} {
		w := customerHTTP(t, s.Handler(), tc.method, tc.path, tc.body, tc.headers, tc.cookie)
		if w.Code != 503 || !strings.Contains(w.Body.String(), `"code":"COMMERCE_UNAVAILABLE"`) {
			t.Fatalf("%s %s status=%d body=%s", tc.method, tc.path, w.Code, w.Body.String())
		}
	}
	for _, operation := range []string{"checkouts", "stripe/webhook", "orders/status", "demo-mode", "../catalog", "unknown"} {
		if _, _, err := client.Do(context.Background(), operation, []byte(`{}`), "signature"); err == nil {
			t.Errorf("allowed private operation %s", operation)
		}
	}
	if calls != 0 {
		t.Fatalf("blocked operations reached private authority %d times", calls)
	}
	private.Close()
	w := customerHTTP(t, s.Handler(), "GET", "/workshop/purchase-config.json", "", nil, nil)
	if w.Code != 200 || strings.TrimSpace(w.Body.String()) != purchaseDisabled {
		t.Fatal("private outage changed disabled config", w.Code, w.Body.String())
	}
}
