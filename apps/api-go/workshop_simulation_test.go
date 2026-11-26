package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"testing"
)

func TestWorkshopSimulationIsAnAuthorizedNoChargeCheckout(t *testing.T) {
	const tester = "11111111-1111-4111-8111-111111111111"
	calls := 0
	s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(_ context.Context, operation string, body []byte, _ string) (int, []byte, error) {
		calls++
		var input map[string]any
		if operation != "checkouts" || json.Unmarshal(body, &input) != nil ||
			input["expected_mode"] != "simulation" || input["customer_account_id"] != tester {
			t.Fatalf("unbound simulation request: %s %s", operation, body)
		}
		return http.StatusOK, []byte(`{"version":"v1","state":"owned","order_id":"` + commerceOrderID +
			`","library_item_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US"}`), nil
	}))
	s.workshopSimulation = true
	handler := s.Handler()
	headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}
	route := "/v1/workshop/checkout-sessions"
	simulated := strings.TrimSuffix(commerceCheckoutBody, "}") + `,"expected_mode":"simulation"}`

	if w := customerHTTP(t, handler, "POST", route, commerceCheckoutBody, headers, cookie); w.Code != 503 || calls != 0 {
		t.Fatalf("unmarked checkout reached simulation: %d", w.Code)
	}
	if w := customerHTTP(t, handler, "POST", route, simulated, headers, nil); w.Code != 401 || calls != 0 {
		t.Fatalf("anonymous checkout reached simulation: %d", w.Code)
	}
	if w := customerHTTP(t, handler, "POST", route, simulated, headers, cookie); w.Code != 200 || calls != 1 ||
		!strings.Contains(w.Body.String(), `"state":"owned"`) || strings.Contains(w.Body.String(), "checkout_url") {
		t.Fatalf("simulated checkout: %d %s", w.Code, w.Body.String())
	}

	s.workshopSimulation = false
	if w := customerHTTP(t, handler, "POST", route, simulated, headers, cookie); w.Code != 503 || calls != 1 {
		t.Fatalf("stale simulated checkout reached Stripe: %d", w.Code)
	}
}

func TestWorkshopSimulationIncludesOnlyAnAuthorizedFirstIndex(t *testing.T) {
	for _, tc := range []struct {
		name, region string
		requestIndex bool
		rows         int
		grantErr     error
		wantGrants   int
		wantIndex    bool
	}{
		{"available", "US", true, 1, nil, 1, true},
		{"first page", "US", true, 101, nil, 1, true},
		{"old client", "US", false, 1, nil, 0, false},
		{"empty", "US", true, 0, nil, 1, false},
		{"different region", "CA", true, 1, nil, 0, false},
		{"revoked grant", "US", true, 1, ErrVehicleGrantRevoked, 1, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			grant := &paidGrantClient{err: tc.grantErr}
			client := paidIndexQuoteClient{paidGrantClient: grant, commerceFixture: func(_ context.Context, op string, _ []byte, _ string) (int, []byte, error) {
				if op != "checkouts" {
					t.Fatal("unexpected commerce request", op)
				}
				return 200, []byte(`{"version":"v1","state":"owned","order_id":"` + commerceOrderID +
					`","library_item_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID +
					`","region":"US","article_index":{"items":["untrusted index"]}}`), nil
			}}
			s, cookie, csrf := commerceTestAPI(t, client)
			s.workshopSimulation = true
			catalog := &paidHTTPStore{memoryCatalogStore: newMemoryCatalogStore(),
				progress: &CatalogArticleProgress{Status: "running"}}
			s.catalog = catalog
			catalog.PutConfiguration(CatalogConfiguration{ID: commerceConfigID, VehicleID: paidTestVehicle, Region: tc.region})
			for i := range tc.rows {
				id := fmt.Sprintf("55555555-5555-4555-8555-%012d", i)
				catalog.PutArticle(CatalogArticle{ID: id, VehicleID: commerceConfigID, CanonicalArticleID: &id,
					Title: "Stored procedure", Body: "private body", Images: []CatalogImage{{ID: "private image"}}})
			}
			headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example",
				"X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}
			if tc.requestIndex {
				headers["Prefer"] = checkoutArticleIndexPreference
			}
			body := strings.TrimSuffix(commerceCheckoutBody, "}") + `,"expected_mode":"simulation"}`
			w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", body, headers, cookie)
			var reply struct {
				commerceCheckout
				Index *CatalogArticlesResponse `json:"article_index"`
			}
			if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &reply) != nil ||
				reply.State != "owned" || reply.OrderID != commerceOrderID ||
				(reply.Index != nil) != tc.wantIndex || grant.calls != tc.wantGrants {
				t.Fatalf("unexpected checkout status=%d response=%+v grant reads=%d", w.Code, reply, grant.calls)
			}
			if strings.Contains(w.Body.String(), "private") || strings.Contains(w.Body.String(), "untrusted") {
				t.Fatal("checkout leaked index content")
			}
			if !tc.wantIndex {
				return
			}
			index := reply.Index
			if !index.Hydrating || index.Complete || index.Configuration.ID != commerceConfigID ||
				index.Configuration.Region != "US" || len(index.Items) != min(tc.rows, 100) ||
				grant.account != "11111111-1111-4111-8111-111111111111" || grant.region != "US" ||
				w.Header().Get("Preference-Applied") != checkoutArticleIndexPreference ||
				w.Header().Get("Cache-Control") != "no-store" {
				t.Fatal("checkout index was not tied to the checked owner and exact vehicle")
			}
			if tc.rows > 100 && (index.Page == nil || index.Page.Offset != 0 || index.Page.Total != tc.rows) {
				t.Fatal("missing first page metadata")
			}
		})
	}
}

func TestSimulationPurchaseConfigurationIsAccountScoped(t *testing.T) {
	const tester = "11111111-1111-4111-8111-111111111111"
	calls := 0
	s, cookie, _ := commerceTestAPI(t, commerceFixture(func(_ context.Context, operation string, body []byte, _ string) (int, []byte, error) {
		calls++
		var input map[string]any
		if operation != "purchase-config" || json.Unmarshal(body, &input) != nil || input["customer_account_id"] != tester {
			t.Fatalf("unbound simulation config: %s %s", operation, body)
		}
		return http.StatusOK, []byte(`{"enabled":true,"checkout_mode":"simulation","terms_version":"workshop-v1",
			"terms_url":"https://cars.example/workshop/test-notices/terms","privacy_url":"https://cars.example/workshop/test-notices/privacy",
			"refund_url":"https://cars.example/workshop/test-notices/refund","contact_url":"https://cars.example/workshop/test-notices/contact","tax_notice":"No charge."}`), nil
	}))
	s.workshopSimulation = true
	for _, test := range []struct {
		session *http.Cookie
		enabled bool
	}{{nil, false}, {cookie, true}} {
		w := customerHTTP(t, s.Handler(), "GET", "/workshop/purchase-config.json", "", nil, test.session)
		var config workshopPurchaseConfig
		if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &config) != nil ||
			config.Enabled != test.enabled || config.CheckoutMode != workshopSimulationMode {
			t.Fatalf("simulation enabled=%v response=%d %s", test.enabled, w.Code, w.Body.String())
		}
	}
	if calls != 1 {
		t.Fatalf("anonymous configuration reached private service: %d calls", calls)
	}
}
