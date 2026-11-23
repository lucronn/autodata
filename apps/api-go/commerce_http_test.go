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

func TestWorkshopTestCheckoutPinsPrivateExpectedMode(t *testing.T) {
	calls := 0
	s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(_ context.Context, operation string, body []byte, _ string) (int, []byte, error) {
		calls++
		var input map[string]any
		if operation != "checkouts" || json.Unmarshal(body, &input) != nil || input["expected_mode"] != "stripe_test" {
			t.Fatalf("test checkout did not pin the private payment mode: %s %s", operation, body)
		}
		return 503, []byte(`{"error":{"code":"COMMERCE_UNAVAILABLE"}}`), nil
	}))
	s.workshopTestCheckout = true
	headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}
	body := strings.TrimSuffix(commerceCheckoutBody, "}") + `,"expected_mode":"stripe_test"}`
	w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", body, headers, cookie)
	if w.Code != 503 || calls != 1 {
		t.Fatalf("checkout status=%d calls=%d", w.Code, calls)
	}
}

func TestWorkshopStaleTestTabCannotCheckoutAfterGoRestartsLive(t *testing.T) {
	calls := 0
	s, cookie, csrf := commerceTestAPI(t, commerceFixture(func(_ context.Context, _ string, _ []byte, _ string) (int, []byte, error) {
		calls++
		return 201, []byte(`{}`), nil
	}))
	s.workshopTestCheckout = false // a replacement Go process is now configured live
	headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": csrf, "Idempotency-Key": commerceOrderID}
	body := strings.TrimSuffix(commerceCheckoutBody, "}") + `,"expected_mode":"stripe_test"}`
	w := customerHTTP(t, s.Handler(), "POST", "/v1/workshop/checkout-sessions", body, headers, cookie)
	if w.Code != 503 || calls != 0 {
		t.Fatalf("stale no-charge tab reached live checkout: status=%d calls=%d body=%s", w.Code, calls, w.Body.String())
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

func TestCommerceOrderResumeLinkRequiresOwnerAndValidOpenPair(t *testing.T) {
	hosted := "https://checkout.stripe.com/c/pay/fixture#opaque%2Ffragment"
	future := time.Now().UTC().Add(time.Hour).Format(time.RFC3339)
	past := time.Now().UTC().Add(-time.Hour).Format(time.RFC3339)
	pair := map[string]any{"checkout_url": hosted, "provider_expires_at": future}
	for _, tc := range []struct {
		name, state, disposition string
		fields                   map[string]any
		status                   int
		link                     bool
	}{
		{"open owner", "open", "do_not_repay", pair, 200, true},
		{"legacy open", "open", "do_not_repay", nil, 200, false},
		{"legacy paid", "paid", "do_not_repay", nil, 200, false},
		{"expired in transit", "open", "do_not_repay", map[string]any{"checkout_url": hosted, "provider_expires_at": past}, 200, false},
		{"partial url", "open", "do_not_repay", map[string]any{"checkout_url": hosted}, 503, false},
		{"partial expiry", "open", "do_not_repay", map[string]any{"provider_expires_at": future}, 503, false},
		{"null pair", "open", "do_not_repay", map[string]any{"checkout_url": nil, "provider_expires_at": nil}, 503, false},
		{"foreign url", "open", "do_not_repay", map[string]any{"checkout_url": "https://checkout.stripe.com.evil.example/c/pay/fixture", "provider_expires_at": future}, 503, false},
		{"bad expiry", "open", "do_not_repay", map[string]any{"checkout_url": hosted, "provider_expires_at": "tomorrow"}, 503, false},
		{"processing pair", "processing", "do_not_repay", pair, 503, false},
		{"paid pair", "paid", "do_not_repay", pair, 503, false},
		{"expired pair", "expired", "new_key", pair, 503, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			s, cookie, _ := commerceTestAPI(t, commerceFixture(func(_ context.Context, op string, b []byte, _ string) (int, []byte, error) {
				calls++
				var input map[string]string
				if op != "orders/status" || json.Unmarshal(b, &input) != nil || len(input) != 3 ||
					input["order_id"] != commerceOrderID ||
					input["customer_account_id"] != "11111111-1111-4111-8111-111111111111" ||
					input["organization_id"] != "44444444-4444-4444-8444-444444444444" {
					t.Fatal("order lookup lost the authenticated owner and exact order")
				}
				body := map[string]any{
					"version": "v1", "order_id": commerceOrderID, "configuration_id": commerceConfigID,
					"region": "CA", "state": tc.state, "retry_disposition": tc.disposition, "private_secret": "hidden",
				}
				for key, value := range tc.fields {
					body[key] = value
				}
				raw, err := json.Marshal(body)
				return 200, raw, err
			}))
			path := "/v1/workshop/orders/" + commerceOrderID
			guest := customerHTTP(t, s.Handler(), "GET", path, "", nil, nil)
			if guest.Code != 401 || calls != 0 {
				t.Fatal("unauthenticated order lookup reached commerce authority")
			}
			w := customerHTTP(t, s.Handler(), "GET", path, "", nil, cookie)
			if w.Code != tc.status || w.Header().Get("Cache-Control") != "no-store" || calls != 1 {
				t.Fatalf("status=%d cache-policy=%q authority calls=%d", w.Code, w.Header().Get("Cache-Control"), calls)
			}
			var public map[string]any
			if json.Unmarshal(w.Body.Bytes(), &public) != nil {
				t.Fatal("invalid public response")
			}
			_, urlPresent := public["checkout_url"]
			_, expiryPresent := public["provider_expires_at"]
			if _, secret := public["private_secret"]; secret || urlPresent != tc.link || expiryPresent != tc.link {
				t.Fatal("order response projected the wrong fields")
			}
			if tc.status == 200 && (public["order_id"] != commerceOrderID || public["configuration_id"] != commerceConfigID ||
				public["region"] != "CA" || public["state"] != tc.state || public["retry_disposition"] != tc.disposition) {
				t.Fatal("order state or scope changed")
			}
			if tc.link && (public["checkout_url"] != hosted || public["provider_expires_at"] != future) {
				t.Fatal("resume pair lost the exact link or expiry")
			}
		})
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
	url := "https://checkout.stripe.com/g/pay/opaque_Checkout42#fidkdOpaque"
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

func TestCommerceLibraryTruthfulRevocationAndUTCTime(t *testing.T) {
	for _, tc := range []struct {
		name, state, time string
		want              int
	}{{"ungranted revoked", "revoked", "null", 200}, {"paid needs grant", "paid", "null", 503}, {"viewable needs grant", "viewable", "null", 503}, {"preparing needs grant", "preparing", "null", 503}, {"granted UTC offset", "paid", `"2026-11-03T20:00:00+00:00"`, 200}, {"granted UTC Z", "viewable", `"2026-11-03T20:00:00Z"`, 200}, {"non UTC denied", "paid", `"2026-11-03T20:00:00+01:00"`, 503}} {
		t.Run(tc.name, func(t *testing.T) {
			s, cookie, _ := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
				return 200, []byte(`{"version":"v1","items":[{"library_item_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US","label":"Vehicle","access_state":"` + tc.state + `","granted_at":` + tc.time + `}],"next_cursor":null}`), nil
			}))
			w := customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library", "", nil, cookie)
			if w.Code != tc.want {
				t.Fatal(w.Code, w.Body.String())
			}
			if tc.state == "revoked" && w.Code == 200 && !strings.Contains(w.Body.String(), `"granted_at":null`) {
				t.Fatal("invented grant time", w.Body.String())
			}
		})
	}
}

func TestCommerceLibraryRetainsPaidCatalogAvailability(t *testing.T) {
	for _, tc := range []struct {
		name, state, availability, empty string
		wantStatus                       int
	}{
		{"older response", "paid", "", "", 200},
		{"retained unavailable purchase", "paid", "false", "", 200},
		{"completed empty catalog", "paid", "", "true", 200},
		{"null unavailable marker", "paid", "null", "", 503},
		{"true unavailable marker", "paid", "true", "", 503},
		{"preparing with unavailable marker", "preparing", "false", "", 503},
		{"viewable with unavailable marker", "viewable", "false", "", 503},
		{"revoked with unavailable marker", "revoked", "false", "", 503},
		{"null empty marker", "paid", "", "null", 503},
		{"false empty marker", "paid", "", "false", 503},
		{"preparing with empty marker", "preparing", "", "true", 503},
		{"viewable with empty marker", "viewable", "", "true", 503},
		{"revoked with empty marker", "revoked", "", "true", 503},
		{"contradictory catalog markers", "paid", "false", "true", 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, cookie, _ := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) {
				extra := ""
				if tc.availability != "" {
					extra = `,"catalog_available":` + tc.availability
				}
				if tc.empty != "" {
					extra += `,"catalog_empty":` + tc.empty
				}
				return 200, []byte(`{"version":"v1","items":[{"library_item_id":"` + commerceOrderID +
					`","configuration_id":"` + commerceConfigID + `","region":"US","label":"Vehicle","access_state":"` +
					tc.state + `","granted_at":"2026-11-03T20:00:00Z"` + extra + `}],"next_cursor":null}`), nil
			}))
			w := customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library", "", nil, cookie)
			if w.Code != tc.wantStatus || strings.Contains(w.Body.String(), `"catalog_available":false`) != (tc.wantStatus == 200 && tc.availability == "false") ||
				strings.Contains(w.Body.String(), `"catalog_empty":true`) != (tc.wantStatus == 200 && tc.empty == "true") {
				t.Fatalf("status=%d response=%s", w.Code, w.Body)
			}
			if w.Code != 200 {
				return
			}
			var data commerceLibrary
			if err := json.Unmarshal(w.Body.Bytes(), &data); err != nil || len(data.Items) != 1 {
				t.Fatalf("invalid library response: %v %s", err, w.Body)
			}
			item := data.Items[0]
			if item.LibraryItemID != commerceOrderID || item.ConfigurationID != commerceConfigID ||
				item.Region != "US" || item.AccessState != "paid" || item.GrantedAt == nil || *item.GrantedAt != "2026-11-03T20:00:00Z" {
				t.Fatalf("historical purchase changed: %+v", item)
			}
		})
	}
}

func TestCommerceHostedURLRejectsWhitespaceAndControls(t *testing.T) {
	for _, u := range []string{"https://checkout.stripe.com/c/pay/cs test", "https://checkout.stripe.com/c/pay/cs_test#opaque space", "https://checkout.stripe.com:443/c/pay/cs_test", "https://user@checkout.stripe.com/c/pay/cs_test", "https://checkout.stripe.com/c/pay/cs_test\n"} {
		if commerceHostedURL(u) {
			t.Error("unsafe provider URL accepted", u)
		}
	}
}

func TestCommerceLibraryRejectsMissingRequiredNullableFields(t *testing.T) {
	for _, body := range []string{`{"version":"v1","items":[]}`, `{"version":"v1","items":[{"library_item_id":"` + commerceOrderID + `","configuration_id":"` + commerceConfigID + `","region":"US","label":"Vehicle","access_state":"revoked"}],"next_cursor":null}`} {
		s, cookie, _ := commerceTestAPI(t, commerceFixture(func(context.Context, string, []byte, string) (int, []byte, error) { return 200, []byte(body), nil }))
		w := customerHTTP(t, s.Handler(), "GET", "/v1/workshop/library", "", nil, cookie)
		if w.Code != 503 {
			t.Fatal("missing nullable field accepted", w.Code, w.Body.String())
		}
	}
}

func TestCommerceCurrentHostedCheckoutPaths(t *testing.T) {
	for _, prefix := range []string{"c", "g"} {
		hosted := "https://checkout.stripe.com/" + prefix + "/pay/opaque_Checkout42#opaque%2Ffragment"
		if !commerceHostedURL(hosted) {
			t.Errorf("rejected trusted %s path", prefix)
		}
		for _, bad := range []string{strings.Replace(hosted, "https:", "http:", 1), strings.Replace(hosted, "checkout.stripe.com", "checkout.stripe.com.evil", 1), strings.Replace(hosted, "checkout.stripe.com", "user@checkout.stripe.com", 1), strings.Replace(hosted, "checkout.stripe.com", "checkout.stripe.com:443", 1), "https://checkout.stripe.com/" + prefix + "/pay/", hosted + " ", hosted + "\x00"} {
			if commerceHostedURL(bad) {
				t.Errorf("accepted invalid hosted URL %q", bad)
			}
		}
	}
	for _, bad := range []string{"https://checkout.stripe.com/pay/opaque", "https://checkout.stripe.com/x/pay/opaque"} {
		if commerceHostedURL(bad) {
			t.Errorf("accepted unknown hosted path %q", bad)
		}
	}
}
