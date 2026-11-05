package main

import (
	"context"
	"encoding/json"
	"github.com/jackc/pgx/v5/pgxpool"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const purchaseDisabled = `{"enabled":false,"terms_version":"workshop-v1","terms_url":null,"privacy_url":null,"refund_url":null,"contact_url":null,"tax_notice":null}`
const purchaseEnabled = `{"enabled":true,"terms_version":"workshop-v1","terms_url":"https://legal.example.test/terms","privacy_url":"https://legal.example.test/privacy","refund_url":"https://legal.example.test/refund","contact_url":"https://legal.example.test/contact","tax_notice":"Synthetic fixture notice"}`

var purchaseURLVectors = []struct {
	ID    string `json:"id"`
	URL   string `json:"url"`
	Valid bool   `json:"valid"`
}{
	{ID: "plain_https", URL: "https://legal.example.test/terms", Valid: true},
	{ID: "explicit_443", URL: "https://legal.example.test:443/terms", Valid: true},
	{ID: "mixed_ascii", URL: "https://Legal.Example.TEST/terms", Valid: true},
	{ID: "punycode", URL: "https://xn--bcher-kva.example/terms", Valid: true},
	{ID: "encoded_space", URL: "https://legal.example.test/terms%20v1", Valid: true},
	{ID: "encoded_octets", URL: "https://legal.example.test/a%2Fb%FF", Valid: true},
	{ID: "wrong_scheme", URL: "http://legal.example.test/terms", Valid: false},
	{ID: "upper_scheme", URL: "HTTPS://legal.example.test/terms", Valid: false},
	{ID: "credentials", URL: "https://user:pass@legal.example.test/terms", Valid: false},
	{ID: "empty_query", URL: "https://legal.example.test/terms?", Valid: false},
	{ID: "query", URL: "https://legal.example.test/terms?v=1", Valid: false},
	{ID: "empty_fragment", URL: "https://legal.example.test/terms#", Valid: false},
	{ID: "fragment", URL: "https://legal.example.test/terms#v1", Valid: false},
	{ID: "wrong_port", URL: "https://legal.example.test:444/terms", Valid: false},
	{ID: "padded_port", URL: "https://legal.example.test:0443/terms", Valid: false},
	{ID: "empty_port", URL: "https://legal.example.test:/terms", Valid: false},
	{ID: "ipv4", URL: "https://127.0.0.1/terms", Valid: false},
	{ID: "ipv6", URL: "https://[::1]/terms", Valid: false},
	{ID: "localhost", URL: "https://localhost/terms", Valid: false},
	{ID: "trailing_dot", URL: "https://legal.example.test./terms", Valid: false},
	{ID: "empty_label", URL: "https://legal..test/terms", Valid: false},
	{ID: "leading_hyphen", URL: "https://-legal.example.test/terms", Valid: false},
	{ID: "trailing_hyphen", URL: "https://legal-.example.test/terms", Valid: false},
	{ID: "underscore", URL: "https://legal_site.example.test/terms", Valid: false},
	{ID: "numeric_tld", URL: "https://legal.example.123/terms", Valid: false},
	{ID: "unicode_host", URL: "https://b\u00fccher.example/terms", Valid: false},
	{ID: "host_escape", URL: "https://legal%2Eexample.test/terms", Valid: false},
	{ID: "incomplete_escape", URL: "https://legal.example.test/a%2", Valid: false},
	{ID: "bad_escape", URL: "https://legal.example.test/a%G0", Valid: false},
	{ID: "bare_percent", URL: "https://legal.example.test/a%", Valid: false},
	{ID: "space", URL: "https://legal.example.test/terms v1", Valid: false},
	{ID: "tab", URL: "https://legal.example.test/terms\tv1", Valid: false},
	{ID: "nbsp", URL: "https://legal.example.test/terms\u00a0v1", Valid: false},
	{ID: "line_separator", URL: "https://legal.example.test/terms\u2028v1", Valid: false},
	{ID: "feff", URL: "https://legal.example.test/terms\ufeffv1", Valid: false},
	{ID: "c0", URL: "https://legal.example.test/terms\u0001v1", Valid: false},
	{ID: "del", URL: "https://legal.example.test/terms\u007fv1", Valid: false},
	{ID: "c1", URL: "https://legal.example.test/terms\u009fv1", Valid: false},
}

func TestPurchaseConfigStrictDecode(t *testing.T) {
	for _, raw := range []string{purchaseDisabled, purchaseEnabled} {
		if _, e := decodeWorkshopPurchaseConfig([]byte(raw)); e != nil {
			t.Fatal(e)
		}
	}
	for _, raw := range []string{`{}`, `null`, `[]`, `{"enabled":false}`, purchaseEnabled + `{}`, strings.Replace(purchaseEnabled, `"enabled":true`, `"enabled":true,"enabled":true`, 1), strings.Replace(purchaseEnabled, `"enabled":true`, `"enabled":1`, 1), strings.Replace(purchaseEnabled, `"tax_notice":"Synthetic fixture notice"`, `"tax_notice":null`, 1), strings.Replace(purchaseDisabled, `"terms_url":null`, `"terms_url":"https://legal.example.test/"`, 1), strings.Replace(purchaseEnabled, `"Synthetic fixture notice"`, `"\ud800"`, 1), string([]byte{255}), strings.Repeat(" ", 16385)} {
		if _, e := decodeWorkshopPurchaseConfig([]byte(raw)); e == nil {
			t.Fatalf("accepted invalid %q", raw)
		}
	}
	for _, notice := range []string{`"literal \\ud800"`, `"paired \ud83d\ude00"`} {
		raw := strings.Replace(purchaseEnabled, `"Synthetic fixture notice"`, notice, 1)
		if _, e := decodeWorkshopPurchaseConfig([]byte(raw)); e != nil {
			t.Fatal(notice, e)
		}
	}
	for _, v := range purchaseURLVectors {
		t.Run(v.ID, func(t *testing.T) {
			var obj map[string]any
			json.Unmarshal([]byte(purchaseEnabled), &obj)
			obj["terms_url"] = v.URL
			b, _ := json.Marshal(obj)
			got, e := decodeWorkshopPurchaseConfig(b)
			if (e == nil) != v.Valid {
				t.Fatalf("valid %v err %v", v.Valid, e)
			}
			if e == nil && *got.TermsURL != v.URL {
				t.Fatal("rewritten")
			}
		})
	}
	codes := []rune{}
	for c := rune(0); c <= 32; c++ {
		codes = append(codes, c)
	}
	for c := rune(127); c <= 160; c++ {
		codes = append(codes, c)
	}
	for c := rune(0x2000); c <= 0x200a; c++ {
		codes = append(codes, c)
	}
	codes = append(codes, 0x1680, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000, 0xfeff)
	for _, c := range codes {
		for _, url := range []string{string(c) + "https://legal.example.test/a", "https://legal.example.test/a" + string(c) + "b", "https://legal.example.test/a" + string(c)} {
			var obj map[string]any
			json.Unmarshal([]byte(purchaseEnabled), &obj)
			obj["terms_url"] = url
			b, _ := json.Marshal(obj)
			if _, e := decodeWorkshopPurchaseConfig(b); e == nil {
				t.Fatalf("accepted U+%04X", c)
			}
		}
	}
}
func TestPurchaseConfigFullServerNetwork(t *testing.T) {
	for _, raw := range []string{purchaseDisabled, purchaseEnabled, `{"enabled":true}`, strings.Replace(purchaseEnabled, `"enabled":true`, `"extra":1,"enabled":true`, 1)} {
		t.Run(raw, func(t *testing.T) {
			calls := 0
			private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				b, _ := io.ReadAll(r.Body)
				if r.URL.Path != "/internal/commerce/purchase-config" || r.Header.Get("X-Autodata-Internal-Token") != "fixture-token" || string(b) != "{}" {
					t.Error("wrong seam")
				}
				io.WriteString(w, raw)
			}))
			defer private.Close()
			c, _ := NewHTTPCommerceClient(private.URL, "fixture-token")
			s := NewServer(staticReadiness{})
			s.commerceClient = c
			pub := httptest.NewServer(s.Handler())
			defer pub.Close()
			client := pub.Client()
			client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
			for _, method := range []string{"GET", "HEAD", "POST", "OPTIONS"} {
				for _, suffix := range []string{"", "?", "?x=1"} {
					for _, conditional := range []bool{false, true} {
						r, _ := http.NewRequest(method, pub.URL+"/workshop/purchase-config.json"+suffix, nil)
						if conditional {
							r.Header.Set("If-None-Match", "*")
							r.Header.Set("If-Modified-Since", "Thu, 01 Jan 2099 00:00:00 GMT")
						}
						resp, e := client.Do(r)
						if e != nil {
							t.Fatal(e)
						}
						b, _ := io.ReadAll(resp.Body)
						resp.Body.Close()
						want := 200
						if raw != purchaseEnabled && raw != purchaseDisabled {
							want = 503
						}
						if suffix != "" {
							want = 400
						}
						if method == "POST" || method == "OPTIONS" {
							want = 405
						}
						if resp.StatusCode != want || resp.Header.Get("Cache-Control") != "no-store" || !strings.HasPrefix(resp.Header.Get("Content-Type"), "application/json") || resp.Header.Get("ETag") != "" || resp.Header.Get("Last-Modified") != "" {
							t.Fatalf("%s %s: %d %v %s", method, suffix, resp.StatusCode, resp.Header, b)
						}
						if method == "HEAD" && len(b) != 0 {
							t.Fatal("HEAD body")
						}
						if want == 405 && resp.Header.Get("Allow") != "GET, HEAD" {
							t.Fatal("Allow")
						}
					}
				}
			}
			if calls != 4 {
				t.Fatal("calls", calls)
			}
			for _, path := range []string{"/workshop", "/workshop/", "/workshop/app.mjs"} {
				for _, method := range []string{"GET", "HEAD", "POST", "OPTIONS"} {
					r, _ := http.NewRequest(method, pub.URL+path, nil)
					resp, e := client.Do(r)
					if e != nil {
						t.Fatal(e)
					}
					io.Copy(io.Discard, resp.Body)
					resp.Body.Close()
					want := 200
					if path == "/workshop" {
						want = 301
					}
					if method == "POST" || method == "OPTIONS" {
						want = 405
						if resp.Header.Get("Allow") != "GET, HEAD" || resp.Header.Get("Location") != "" {
							t.Fatal("unsafe static redirect", resp.Header)
						}
					}
					if resp.StatusCode != want {
						t.Fatalf("%s %s: %d", method, path, resp.StatusCode)
					}
				}
			}
		})
	}
	s := NewServer(staticReadiness{})
	w := httptest.NewRecorder()
	s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/workshop/purchase-config.json", nil))
	var got map[string]any
	json.Unmarshal(w.Body.Bytes(), &got)
	if w.Code != 200 || got["enabled"] != false || len(got) != 7 {
		t.Fatal(w.Code, w.Body.String())
	}
}

func TestPurchaseConfigBoundariesAndUnavailable(t *testing.T) {
	for _, tc := range []struct {
		field, value string
		valid        bool
	}{
		{"tax_notice", strings.Repeat("x", 1024), true}, {"tax_notice", strings.Repeat("x", 1025), false},
		{"tax_notice", "a\nb", false}, {"tax_notice", "a\u2028b", false}, {"tax_notice", "a\u007fb", false}, {"tax_notice", " ", false}, {"tax_notice", "\ufeff", false}, {"tax_notice", " \ufeff ", false},
		{"terms_url", "https://legal.example.test/" + strings.Repeat("x", 2048-len("https://legal.example.test/")), true},
		{"terms_url", "https://legal.example.test/" + strings.Repeat("x", 2049-len("https://legal.example.test/")), false},
		{"terms_url", "https://a.co/", true}, {"terms_url", "https://a.c/", false},
		{"terms_url", "https://" + strings.Repeat("x", 63) + ".test/", true}, {"terms_url", "https://" + strings.Repeat("x", 64) + ".test/", false},
		{"terms_url", "https://a." + strings.Repeat("x", 63) + "/", true}, {"terms_url", "https://a." + strings.Repeat("x", 64) + "/", false},
		{"terms_url", "https://" + strings.Repeat(strings.Repeat("x", 63)+".", 3) + strings.Repeat("x", 61) + "/", true},
		{"terms_url", "https://" + strings.Repeat(strings.Repeat("x", 63)+".", 3) + strings.Repeat("x", 62) + "/", false},
	} {
		var obj map[string]any
		json.Unmarshal([]byte(purchaseEnabled), &obj)
		obj[tc.field] = tc.value
		b, _ := json.Marshal(obj)
		_, e := decodeWorkshopPurchaseConfig(b)
		if (e == nil) != tc.valid {
			t.Fatalf("boundary %s %d: %v", tc.field, len(tc.value), e)
		}
	}
	for _, n := range []int{16384, 16385} {
		_, e := decodeWorkshopPurchaseConfig([]byte(purchaseDisabled + strings.Repeat(" ", n-len(purchaseDisabled))))
		if (e == nil) != (n == 16384) {
			t.Fatal(n, e)
		}
	}
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { t.Error("redirect followed") }))
	defer target.Close()
	for _, handler := range []http.HandlerFunc{
		func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, target.URL, 307) },
		func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(500); io.WriteString(w, "secret failure") },
		func(w http.ResponseWriter, r *http.Request) {
			io.WriteString(w, strings.Repeat("x", maxCommerceResponseBytes+1))
		},
		func(w http.ResponseWriter, r *http.Request) { time.Sleep(2100 * time.Millisecond) },
	} {
		private := httptest.NewServer(handler)
		c, _ := NewHTTPCommerceClient(private.URL, "fixture-token")
		s := NewServer(staticReadiness{})
		s.commerceClient = c
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/workshop/purchase-config.json", nil))
		private.Close()
		if w.Code != 503 || w.Header().Get("Cache-Control") != "no-store" || !strings.Contains(w.Body.String(), "COMMERCE_UNAVAILABLE") || strings.Contains(w.Body.String(), "secret") {
			t.Fatal(w.Code, w.Body.String())
		}
	}
}

// Run only under the separate owned Python lifecycle fixture. This is regression
// evidence, not an addition to the frozen commerce or browser inventories.
func TestWorkshopPurchaseConfigAuthorityIntegration(t *testing.T) {
	required := os.Getenv("AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION") == "1"
	bridge := os.Getenv("AUTODATA_PURCHASE_CONFIG_GO_BRIDGE") == "1"
	if !required && !bridge {
		t.Skip("separate Task59 lifecycle bridge required")
	}
	if !required || !bridge {
		t.Fatal("mismatched Task59 bridge flags")
	}
	fixtureURL, token, artifact := os.Getenv("AUTODATA_PURCHASE_CONFIG_FIXTURE_URL"), os.Getenv("AUTODATA_PURCHASE_CONFIG_FIXTURE_TOKEN"), os.Getenv("AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR")
	parsed, e := url.Parse(fixtureURL)
	if e != nil || parsed.Scheme != "http" || parsed.Hostname() != "127.0.0.1" || parsed.Port() == "" || parsed.Path != "" || parsed.RawQuery != "" || parsed.ForceQuery || parsed.Fragment != "" || parsed.User != nil || token == "" || !filepath.IsAbs(artifact) {
		t.Fatal("invalid owned fixture inputs")
	}
	info, e := os.Stat(artifact)
	if e != nil || !info.IsDir() {
		t.Fatal("fixture artifacts missing")
	}
	control := func(path string, output any) {
		t.Helper()
		r, _ := http.NewRequest("POST", fixtureURL+path, strings.NewReader(`{}`))
		r.Header.Set("X-Autodata-Internal-Token", token)
		c := &http.Client{Timeout: 5 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		resp, e := c.Do(r)
		if e != nil {
			t.Fatal("fixture control unavailable")
		}
		defer resp.Body.Close()
		if resp.StatusCode != 200 {
			t.Fatal("fixture control rejected", resp.StatusCode)
		}
		if e = json.NewDecoder(io.LimitReader(resp.Body, 16384)).Decode(output); e != nil {
			t.Fatal("invalid control reply")
		}
	}
	var boot struct {
		Database string `json:"database"`
		Session  string `json:"session"`
		Cases    []struct {
			Key             string `json:"key"`
			ConfigurationID string `json:"configuration_id"`
		} `json:"cases"`
	}
	control("/task59/bootstrap", &boot)
	if !strings.HasPrefix(boot.Database, "lifecycle_test_") || len(boot.Cases) != 3 {
		t.Fatal("invalid synthetic bootstrap")
	}
	// Actual PostgreSQL-backed opaque session validation plus production CSRF.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	pool, e := pgxpool.New(ctx, "postgres://lifecycle_test:lifecycle_test_only@postgres/"+boot.Database+"?sslmode=disable")
	if e != nil {
		t.Fatal("fixture database unavailable")
	}
	defer pool.Close()
	store := &postgresCustomerSessions{pool: pool}
	if store.CheckSchema(ctx) != nil {
		t.Fatal("fixture identity schema unavailable")
	}
	c, e := NewHTTPCommerceClient(fixtureURL, token)
	if e != nil {
		t.Fatal("fixture commerce configuration")
	}
	s := NewServer(staticReadiness{})
	s.commerceClient = c
	s.customerAuth = &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"}, store: store, verifier: &customerVerifierFixture{}}
	pub := httptest.NewServer(s.Handler())
	defer pub.Close()
	client := pub.Client()
	request := func(method, path, body string, headers map[string]string, authenticated bool) (int, []byte) {
		t.Helper()
		r, _ := http.NewRequest(method, pub.URL+path, strings.NewReader(body))
		for k, v := range headers {
			r.Header.Set(k, v)
		}
		if authenticated {
			r.AddCookie(&http.Cookie{Name: customerSessionName, Value: boot.Session})
		}
		resp, e := client.Do(r)
		if e != nil {
			t.Fatal("public fixture request failed")
		}
		defer resp.Body.Close()
		b, e := io.ReadAll(io.LimitReader(resp.Body, 16384))
		if e != nil {
			t.Fatal(e)
		}
		if resp.Header.Get("Cache-Control") != "no-store" {
			t.Fatal("missing no-store")
		}
		return resp.StatusCode, b
	}
	status, b := request("GET", "/workshop/purchase-config.json", "", nil, false)
	cfg, e := decodeWorkshopPurchaseConfig(b)
	if status != 200 || e != nil || !cfg.Enabled {
		t.Fatal("enabled config fetch failed")
	}
	var paused struct {
		Paused bool `json:"paused"`
	}
	control("/task59/pause", &paused)
	if !paused.Paused {
		t.Fatal("fixture did not pause")
	}
	observations := []map[string]any{}
	for i, tc := range boot.Cases {
		if !commerceUUID(tc.Key) || !commerceScopeValid(tc.ConfigurationID, "US") {
			t.Fatal("invalid fixture scope")
		}
		body := `{"configuration_id":"` + tc.ConfigurationID + `","region":"US","terms_version":"workshop-v1"}`
		headers := map[string]string{"Content-Type": "application/json", "Origin": "https://cars.example", "X-CSRF-Token": customerCSRF(boot.Session), "Idempotency-Key": tc.Key}
		if i == 0 {
			status, _ = request("POST", "/v1/workshop/checkout-sessions", body, headers, false)
			if status != 401 {
				t.Fatal("unauthenticated checkout accepted", status)
			}
			bad := map[string]string{}
			for k, v := range headers {
				bad[k] = v
			}
			bad["X-CSRF-Token"] = "wrong"
			status, _ = request("POST", "/v1/workshop/checkout-sessions", body, bad, true)
			if status != 403 {
				t.Fatal("invalid CSRF accepted", status)
			}
		}
		status, b = request("POST", "/v1/workshop/checkout-sessions", body, headers, true)
		if status != 503 || commerceErrorCode(b) != "COMMERCE_UNAVAILABLE" {
			t.Fatalf("paused authority case %d: %d %s", i, status, b)
		}
		observations = append(observations, map[string]any{"case": i, "status": status, "code": commerceErrorCode(b)})
	}
	status, b = request("GET", "/workshop/purchase-config.json", "", nil, false)
	cfg, e = decodeWorkshopPurchaseConfig(b)
	if status != 200 || e != nil || cfg.Enabled {
		t.Fatal("paused config unavailable")
	}
	raw, _ := json.MarshalIndent(observations, "", "  ")
	if os.WriteFile(filepath.Join(artifact, "go-authority-observations.json"), raw, 0600) != nil {
		t.Fatal("cannot retain bridge observations")
	}
}
