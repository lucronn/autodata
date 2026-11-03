package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const commerceConfigID = "33333333-3333-4333-8333-333333333333"
const commerceOrderID = "22222222-2222-4222-8222-222222222222"
const commerceCheckoutBody = `{"configuration_id":"33333333-3333-4333-8333-333333333333","region":"US","terms_version":"workshop-v1"}`

func commerceTestAPI(t *testing.T, client CommerceClient) (*Server, *http.Cookie, string) {
	t.Helper()
	now := time.Now().UTC()
	token, _, _ := newCustomerSessionToken()
	svc := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"}, store: &customerSessionFixture{session: customerSession{AccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "44444444-4444-4444-8444-444444444444", ExpiresAt: now.Add(time.Hour)}}, verifier: &customerVerifierFixture{}, now: func() time.Time { return now }}
	s := NewServer(staticReadiness{})
	s.customerAuth = svc
	s.commerceClient = client
	return s, &http.Cookie{Name: customerSessionName, Value: token}, customerCSRF(token)
}
func TestCommercePublicTrustedOwnerAndStrictShape(t *testing.T) {
	calls := 0
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var b map[string]any
		json.NewDecoder(r.Body).Decode(&b)
		if b["customer_account_id"] != "11111111-1111-4111-8111-111111111111" || b["organization_id"] != "44444444-4444-4444-8444-444444444444" || b["idempotency_key"] != commerceOrderID {
			t.Error("untrusted ownership", b)
		}
		if r.Header.Get("X-Autodata-Owner-Id") != "" || r.Header.Get("Cookie") != "" {
			t.Error("browser authority forwarded")
		}
		w.WriteHeader(201)
		io.WriteString(w, `{"version":"v1","state":"checkout","order_id":"`+commerceOrderID+`","configuration_id":"`+commerceConfigID+`","region":"US","checkout_url":"https://checkout.stripe.com/c/pay/test","provider_expires_at":"2026-11-03T20:00:00Z","private_secret":"hidden"}`)
	}))
	defer private.Close()
	c, _ := NewHTTPCommerceClient(private.URL, "token")
	s, cookie, csrf := commerceTestAPI(t, c)
	good := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID, "X-Autodata-Owner-Id": "attacker"}
	w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", commerceCheckoutBody, good, cookie)
	if w.Code != 201 || strings.Contains(w.Body.String(), "hidden") || calls != 1 {
		t.Fatal(w.Code, w.Body.String(), calls)
	}
	for _, tc := range []struct {
		body    string
		headers map[string]string
		cookie  *http.Cookie
		status  int
	}{{commerceCheckoutBody, good, nil, 401}, {commerceCheckoutBody, map[string]string{"Content-Type": "application/json", "Origin": "https://evil.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}, cookie, 403}, {commerceCheckoutBody, map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "Idempotency-Key": commerceOrderID}, cookie, 403}, {strings.TrimSuffix(commerceCheckoutBody, "}") + `,"amount_minor":1}`, good, cookie, 400}, {commerceCheckoutBody + `{}`, good, cookie, 400}, {`null`, good, cookie, 400}, {strings.Repeat(" ", 16*1024) + commerceCheckoutBody, good, cookie, 413}} {
		w = customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", tc.body, tc.headers, tc.cookie)
		if w.Code != tc.status {
			t.Errorf("want %d got %d: %s", tc.status, w.Code, w.Body.String())
		}
	}
	if calls != 1 {
		t.Fatal("invalid requests reached authority", calls)
	}
}

type commerceFixture func(context.Context, string, []byte, string) (int, []byte, error)

func (f commerceFixture) Do(ctx context.Context, op string, b []byte, s string) (int, []byte, error) {
	return f(ctx, op, b, s)
}
func TestCommerceQuoteLibraryStatusAndSafeErrors(t *testing.T) {
	var operation string
	var payload map[string]any
	c := commerceFixture(func(ctx context.Context, op string, b []byte, sig string) (int, []byte, error) {
		operation = op
		json.Unmarshal(b, &payload)
		if _, ok := ctx.Deadline(); !ok {
			t.Error("missing deadline")
		}
		switch op {
		case "quote":
			return 200, []byte(`{"version":"v1","product_key":"workshop-configuration-v1","configuration_id":"` + commerceConfigID + `","region":"US","configuration_label":"Vehicle","amount_minor":2000,"currency":"USD","purchase_terms_version":"workshop-v1","purchasable":true}`), nil
		case "library":
			return 200, []byte(`{"version":"v1","items":[],"next_cursor":null}`), nil
		case "orders/status":
			return 404, []byte(`{"error":{"code":"NOT_FOUND","secret":"unsafe"}}`), nil
		}
		panic(op)
	})
	s, cookie, _ := commerceTestAPI(t, c)
	w := customerHTTP(t, s.Handler(), "GET", "/v1/workshop/quote?configuration_id="+commerceConfigID+"&region=US", "", nil, nil)
	if w.Code != 200 || operation != "quote" || len(payload) != 2 {
		t.Fatal(w.Code, w.Body.String(), payload)
	}
	w = customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library?limit=50&cursor=opaque", "", nil, cookie)
	if w.Code != 200 || payload["limit"] != float64(50) || payload["cursor"] != "opaque" {
		t.Fatal(w.Code, payload)
	}
	w = customerHTTP(t, s.Handler(), "GET", "/v1/workshop/orders/"+commerceOrderID, "", nil, cookie)
	if w.Code != 404 || strings.Contains(w.Body.String(), "unsafe") {
		t.Fatal(w.Code, w.Body.String())
	}
	for _, path := range []string{"/v1/workshop/quote?configuration_id=bad&region=US", "/v1/workshop/quote?configuration_id=" + commerceConfigID + "&region=us", "/v1/workshop/quote?configuration_id=" + commerceConfigID + "&region=US&amount_minor=1", "/v1/workshop/library?limit=51", "/v1/workshop/library?limit=1&limit=2", "/v1/workshop/orders/bad"} {
		w = customerHTTP(t, s.Handler(), "GET", path, "", nil, cookie)
		if w.Code != 400 {
			t.Error(path, w.Code)
		}
	}
	s.commerceClient = commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
		return 500, []byte(`{"error":{"code":"secret-provider-key"}}`), nil
	})
	w = customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library", "", nil, cookie)
	if w.Code != 503 || strings.Contains(w.Body.String(), "secret-provider-key") {
		t.Fatal("unsafe upstream error", w.Code, w.Body.String())
	}
}
func TestCommerceWebhookRawAndBounds(t *testing.T) {
	calls := 0
	raw := "{\n \"signed\": true\n}"
	s, _, _ := commerceTestAPI(t, commerceFixture(func(ctx context.Context, op string, b []byte, sig string) (int, []byte, error) {
		calls++
		if op != "stripe/webhook" || string(b) != raw || sig != "t=1,v1=opaque" {
			t.Error("changed signed webhook")
		}
		return 200, []byte(`{"status":"accepted","secret":"hidden"}`), nil
	}))
	for _, tc := range []struct {
		body, sig string
		want      int
	}{{raw, "t=1,v1=opaque", 200}, {raw, "", 400}, {raw, strings.Repeat("x", 4097), 400}, {strings.Repeat("x", (1<<20)+1), "t=1,v1=opaque", 413}} {
		w := customerHTTP(t, s.Handler(), "POST", "/v1/payments/stripe/webhook", tc.body, map[string]string{"Stripe-Signature": tc.sig}, nil)
		if w.Code != tc.want || strings.Contains(w.Body.String(), "hidden") {
			t.Fatal(w.Code, w.Body.String())
		}
	}
	if calls != 1 {
		t.Fatal("invalid webhook reached authority")
	}
}

func TestCommerceRejectsUnsafeAuthorityResponses(t *testing.T) {
	for _, tc := range []struct {
		name, body string
		status     int
	}{
		{"foreign checkout", `{"version":"v1","state":"checkout","order_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US","checkout_url":"https://checkout.stripe.com.evil.example/c/pay/cs_test","provider_expires_at":"2026-11-03T20:00:00Z"}`, 201},
		{"wrong scope", `{"version":"v1","state":"processing","order_id":"` + commerceOrderID + `","configuration_id":"11111111-1111-4111-8111-111111111111","region":"US"}`, 202},
		{"status mismatch", `{"version":"v1","state":"processing","order_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US"}`, 201},
		{"secret error", `{"error":{"code":"raw_secret=sk_live_forbidden"}}`, 400},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
				return tc.status, []byte(tc.body), nil
			}))
			w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", commerceCheckoutBody, map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}, cookie)
			if w.Code != 503 || strings.Contains(w.Body.String(), "raw_secret") {
				t.Fatal(w.Code, w.Body.String())
			}
		})
	}
}
func TestCommerceCheckoutDiscriminantsAndProviderFragment(t *testing.T) {
	url := "https://checkout.stripe.com/c/pay/cs_test_fixture#fidkdOpaque"
	for _, tc := range []struct {
		state, extra string
		status       int
	}{{"checkout", `,"checkout_url":"` + url + `","provider_expires_at":"2026-11-03T20:00:00Z"`, 201}, {"checkout", `,"checkout_url":"` + url + `","provider_expires_at":"2026-11-03T20:00:00Z"`, 200}, {"processing", "", 202}, {"owned", `,"library_item_id":"` + commerceOrderID + `"`, 200}} {
		t.Run(tc.state+string(rune(tc.status)), func(t *testing.T) {
			s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
				return tc.status, []byte(`{"version":"v1","state":"` + tc.state + `","order_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US"` + tc.extra + `}`), nil
			}))
			w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", commerceCheckoutBody, map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}, cookie)
			if w.Code != tc.status {
				t.Fatal(w.Code, w.Body.String())
			}
			if tc.status == 202 && w.Header().Get("Retry-After") != "2" {
				t.Error("missing safe retry delay")
			}
			if tc.state == "checkout" && !strings.Contains(w.Body.String(), "#fidkdOpaque") {
				t.Error("lost provider fragment")
			}
		})
	}
}

func TestCommerceRejectsDuplicateCheckoutAuthorityHeaders(t *testing.T) {
	s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
		t.Error("ambiguous authority forwarded")
		return 503, nil, nil
	}))
	for _, header := range []string{"Origin", "X-CSRF-Token"} {
		t.Run(header, func(t *testing.T) {
			r := httptest.NewRequest("POST", "https://cars.example/v1/workshop/checkout-sessions", strings.NewReader(commerceCheckoutBody))
			r.AddCookie(cookie)
			r.Header.Set("Origin", "https://cars.example")
			r.Header.Set("X-CSRF-Token", csrf)
			r.Header.Set("Content-Type", "application/json")
			r.Header.Set("Idempotency-Key", commerceOrderID)
			r.Header.Add(header, r.Header.Get(header))
			w := httptest.NewRecorder()
			s.Handler().ServeHTTP(w, r)
			if w.Code != 403 {
				t.Fatal("ambiguous authority", w.Code)
			}
		})
	}
}
