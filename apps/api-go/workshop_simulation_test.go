package main

import (
	"context"
	"encoding/json"
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
