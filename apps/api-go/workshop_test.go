package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

func TestWorkshopRootEntry(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, method := range []string{http.MethodGet, http.MethodHead} {
		t.Run(method, func(t *testing.T) {
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(method, "/", nil))
			if response.Code != http.StatusFound || response.Header().Get("Location") != "/workshop/" {
				t.Fatalf("%s root redirect = %d %q", method, response.Code, response.Header().Get("Location"))
			}
		})
	}
	t.Run("unknown path", func(t *testing.T) {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/missing-root-route", nil))
		if response.Code != http.StatusNotFound {
			t.Fatalf("unknown root route = %d, want %d", response.Code, http.StatusNotFound)
		}
	})
}

func TestWorkshopAssetsAvailableWithoutCatalogCredentials(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, asset := range []struct{ path, contentType string }{
		{"/workshop/", "text/html"},
		{"/workshop/styles.css", "text/css"},
		{"/workshop/app.mjs", "javascript"},
		{"/workshop/bootstrap.mjs", "javascript"},
		{"/workshop/demo.mjs", "javascript"},
		{"/workshop/auth.mjs", "javascript"},
		{"/workshop/commerce.mjs", "javascript"},
		{"/workshop/article-read.mjs", "javascript"},
		{"/workshop/purchase-config.json", "application/json"},
		{"/workshop/catalog.mjs", "javascript"},
		{"/workshop/firebase-web.mjs", "javascript"},
		{"/workshop/firebase-web.mjs.LEGAL.txt", "text/plain"},
		{"/workshop/firebase-web.provenance.json", "application/json"},
		{"/workshop/fonts/InstrumentSans.ttf", "font/ttf"},
	} {
		t.Run(asset.path, func(t *testing.T) {
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, asset.path, nil))
			if response.Code != http.StatusOK || response.Body.Len() == 0 {
				t.Fatalf("asset unavailable: status=%d bytes=%d", response.Code, response.Body.Len())
			}
			if !strings.Contains(response.Header().Get("Content-Type"), asset.contentType) {
				t.Fatalf("wrong MIME type: %s", response.Header().Get("Content-Type"))
			}
		})
	}
	for _, path := range []string{"/workshop/missing-file.js", "/workshop/missing-page"} {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, path, nil))
		if response.Code != http.StatusNotFound {
			t.Fatalf("missing asset %s returned %d", path, response.Code)
		}
	}
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/", nil))
	for _, marker := range []string{"source-review", "source-review-frame", "View stored source", "Load beside article"} {
		if !strings.Contains(response.Body.String(), marker) {
			t.Fatalf("workshop HTML is missing source review marker %q", marker)
		}
	}
}

func TestWorkshopPurchaseConfigDisabledByDefault(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/purchase-config.json", nil))
	if response.Code != http.StatusOK {
		t.Fatalf("purchase config status=%d", response.Code)
	}
	var config map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &config); err != nil {
		t.Fatal(err)
	}
	if config["enabled"] != false || config["terms_version"] != "workshop-v1" {
		t.Fatal("default purchase config must remain disabled at workshop-v1")
	}
	for _, field := range []string{"terms_url", "privacy_url", "refund_url", "contact_url", "tax_notice"} {
		value, present := config[field]
		if !present || value != nil {
			t.Fatalf("default %s must be present and null", field)
		}
	}
}

func TestWorkshopRealDemoRequiresEnabledNonProductionStripeTest(t *testing.T) {
	cases := []struct {
		name, mode, environment, authMode, origin, config string
		client, enabled                                   bool
	}{
		{"test ready", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, true},
		{"test disabled purchase", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":false}`, true, false},
		{"mismatched private live mode", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_live","purchase_enabled":true}`, true, false},
		{"test invalid response", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true,"extra":1}`, true, false},
		{"test duplicate private mode", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_live","mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"test trailing private JSON", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}{}`, true, false},
		{"test no client", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, false, false},
		{"local auth unavailable", "stripe_test", "test", "local", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"public production origin", "stripe_test", "staging", "firebase", "https://autodata.cars.tk", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"public apex origin", "stripe_test", "staging", "firebase", "https://cars.tk", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"live mode", "stripe_live", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"production", "stripe_test", "production", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"unknown environment", "stripe_test", "unknown", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"disabled mode", "disabled", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			s := NewServer(staticReadiness{})
			s.workshopTestCheckout = workshopTestCheckoutMode(tc.mode, tc.environment, tc.authMode, tc.origin)
			if tc.client {
				s.commerceClient = commerceFixture(func(_ context.Context, op string, body []byte, signature string) (int, []byte, error) {
					calls++
					if op != "demo-mode" || string(body) != "{}" || signature != "" {
						t.Fatal("unexpected private commerce request", op, string(body), signature)
					}
					return 200, []byte(tc.config), nil
				})
			}
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/demo-mode.json", nil))
			if response.Code != 200 || response.Header().Get("Cache-Control") != "no-store" || !strings.Contains(response.Header().Get("Content-Type"), "application/json") {
				t.Fatalf("demo mode response = %d %q", response.Code, response.Body.String())
			}
			var payload map[string]any
			if json.Unmarshal(response.Body.Bytes(), &payload) != nil || !reflect.DeepEqual(payload, map[string]any{"enabled": tc.enabled}) {
				t.Fatalf("demo readiness = %#v, want %v", payload, tc.enabled)
			}
			if want := 0; tc.client && workshopTestCheckoutMode(tc.mode, tc.environment, tc.authMode, tc.origin) {
				want = 1
				if calls != want {
					t.Fatalf("private calls=%d, want %d", calls, want)
				}
			} else if calls != 0 {
				t.Fatalf("non-test mode contacted private commerce: %d", calls)
			}
		})
	}
}

func TestWorkshopRealDemoReadinessMethodAndQuery(t *testing.T) {
	s := NewServer(staticReadiness{})
	for _, tc := range []struct {
		method, path string
		status       int
	}{
		{http.MethodHead, "/workshop/demo-mode.json", 200},
		{http.MethodGet, "/workshop/demo-mode.json?x=1", 400},
		{http.MethodPost, "/workshop/demo-mode.json", 405},
	} {
		response := httptest.NewRecorder()
		s.Handler().ServeHTTP(response, httptest.NewRequest(tc.method, tc.path, nil))
		if response.Code != tc.status || (tc.method == http.MethodHead && response.Body.Len() != 0) {
			t.Fatalf("%s %s = %d %q", tc.method, tc.path, response.Code, response.Body.String())
		}
	}
}

func TestWorkshopRealDemoPrivateModeHandshakeHTTP(t *testing.T) {
	calls := 0
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var body map[string]any
		if r.Method != http.MethodPost || r.URL.Path != "/internal/commerce/demo-mode" ||
			r.Header.Get("X-Autodata-Internal-Token") != "fixture-token" ||
			r.Header.Get("Cookie") != "" || json.NewDecoder(r.Body).Decode(&body) != nil || len(body) != 0 {
			t.Error("demo mode did not use the bounded private authority")
		}
		_, _ = w.Write([]byte(`{"mode":"stripe_test","purchase_enabled":true}`))
	}))
	defer private.Close()
	client, err := NewHTTPCommerceClient(private.URL, "fixture-token")
	if err != nil {
		t.Fatal(err)
	}
	s := NewServer(staticReadiness{})
	s.commerceClient = client
	s.workshopTestCheckout = true
	response := httptest.NewRecorder()
	s.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/demo-mode.json", nil))
	if response.Code != 200 || response.Body.String() != "{\"enabled\":true}\n" || calls != 1 {
		t.Fatalf("public signal = %d %q; private calls=%d", response.Code, response.Body.String(), calls)
	}
}

func TestWorkshopRedirectPreservesSeparateEntryPoint(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop", nil))
	if response.Code != http.StatusMovedPermanently || response.Header().Get("Location") != "/workshop/" {
		t.Fatalf("unexpected redirect: %d %s", response.Code, response.Header().Get("Location"))
	}
}

// Catches missing/stale embedded artifacts and provenance that describes different
// bytes from the SDK and license actually returned to an unauthenticated client.
func TestWorkshopFirebaseServedProvenance(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	serve := func(path string) []byte {
		t.Helper()
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/"+path, nil))
		if response.Code != http.StatusOK {
			t.Fatalf("%s: status=%d", path, response.Code)
		}
		return response.Body.Bytes()
	}
	type artifact struct {
		Path   string `json:"path"`
		SHA256 string `json:"sha256"`
		Bytes  int    `json:"bytes"`
	}
	var provenance struct {
		Schema  string `json:"schema"`
		Version int    `json:"version"`
		SDK     struct {
			Name    string `json:"name"`
			Version string `json:"version"`
		} `json:"sdk"`
		Dependencies map[string]string `json:"dependencies"`
		Build        struct {
			Tool    string `json:"tool"`
			Version string `json:"version"`
			Options struct {
				Bundle        bool   `json:"bundle"`
				Format        string `json:"format"`
				Platform      string `json:"platform"`
				Target        string `json:"target"`
				Minify        bool   `json:"minify"`
				LegalComments string `json:"legalComments"`
				Sourcemap     bool   `json:"sourcemap"`
			} `json:"options"`
		} `json:"build"`
		Inputs   []artifact `json:"inputs"`
		Outputs  []artifact `json:"outputs"`
		Exports  []string   `json:"exports"`
		Licenses []struct {
			ID     string `json:"id"`
			Source string `json:"source"`
			SHA256 string `json:"sha256"`
			Bytes  int    `json:"bytes"`
		} `json:"licenses"`
	}

	const apacheSHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
	const apacheBytes = 11358
	legal := string(serve("firebase-web.mjs.LEGAL.txt"))
	_, terms, found := strings.Cut(legal, "===== Apache-2.0 full license =====\n")
	if !found {
		t.Fatal("served legal asset is missing full Apache-2.0 terms")
	}
	terms, _, found = strings.Cut(terms, "===== End Apache-2.0 full license =====")
	digest := sha256.Sum256([]byte(terms))
	if !found || len(terms) != apacheBytes || hex.EncodeToString(digest[:]) != apacheSHA256 {
		t.Fatal("served Apache-2.0 terms are truncated or altered")
	}
	if !strings.Contains(legal, "Copyright 2017 Google LLC") || !strings.Contains(legal, "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted") {
		t.Fatal("served legal asset lost extracted headers or ISC terms")
	}
	if err := json.Unmarshal(serve("firebase-web.provenance.json"), &provenance); err != nil {
		t.Fatal(err)
	}
	if len(provenance.Licenses) != 1 || provenance.Licenses[0].ID != "Apache-2.0" || provenance.Licenses[0].Source != "https://www.apache.org/licenses/LICENSE-2.0.txt" || provenance.Licenses[0].SHA256 != apacheSHA256 || provenance.Licenses[0].Bytes != apacheBytes {
		t.Fatalf("unexpected official license provenance: %+v", provenance.Licenses)
	}
	if provenance.Schema != "autodata.firebase-web.provenance" || provenance.Version != 1 || provenance.SDK.Name != "firebase" || provenance.SDK.Version != "12.19.0" {
		t.Fatalf("unexpected provenance identity: %+v", provenance)
	}
	if provenance.Dependencies["@firebase/app"] != "0.16.2" || provenance.Dependencies["@firebase/auth"] != "1.13.6" {
		t.Fatalf("unexpected app/auth versions: %v", provenance.Dependencies)
	}
	options := provenance.Build.Options
	if provenance.Build.Tool != "esbuild" || provenance.Build.Version != "0.28.2" || !options.Bundle || options.Format != "esm" || options.Platform != "browser" || options.Target != "es2022" || !options.Minify || options.LegalComments != "external" || options.Sourcemap {
		t.Fatalf("unexpected build contract: %+v", provenance.Build)
	}
	wantExports := []string{"GoogleAuthProvider", "browserPopupRedirectResolver", "getIdTokenResult", "inMemoryPersistence", "initializeApp", "initializeAuth", "reauthenticateWithPopup", "setPersistence", "signInWithPopup", "signOut"}
	if !reflect.DeepEqual(provenance.Exports, wantExports) {
		t.Fatalf("unexpected exports: %v", provenance.Exports)
	}
	wantInputs := []string{"apps/api-go/workshop-client/build.mjs", "apps/api-go/workshop-client/firebase-entry.mjs", "apps/api-go/workshop-client/package-lock.json", "apps/api-go/workshop-client/package.json"}
	if len(provenance.Inputs) != len(wantInputs) {
		t.Fatalf("unexpected inputs: %+v", provenance.Inputs)
	}
	for i, input := range provenance.Inputs {
		digest, err := hex.DecodeString(input.SHA256)
		if input.Path != wantInputs[i] || input.Bytes <= 0 || err != nil || len(digest) != sha256.Size {
			t.Fatalf("invalid input: %+v", input)
		}
	}
	wantOutputs := []string{"apps/api-go/workshop/firebase-web.mjs", "apps/api-go/workshop/firebase-web.mjs.LEGAL.txt"}
	if len(provenance.Outputs) != len(wantOutputs) {
		t.Fatalf("unexpected outputs: %+v", provenance.Outputs)
	}
	for i, output := range provenance.Outputs {
		if output.Path != wantOutputs[i] {
			t.Fatalf("unexpected artifact path: %s", output.Path)
		}
		data := serve(strings.TrimPrefix(output.Path, "apps/api-go/workshop/"))
		digest := sha256.Sum256(data)
		if len(data) == 0 || output.Bytes != len(data) || output.SHA256 != hex.EncodeToString(digest[:]) {
			t.Fatalf("served bytes differ from provenance: %+v", output)
		}
	}
}
