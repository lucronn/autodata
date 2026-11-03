package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func customerAuthHandler(service *customerAuthService) http.Handler {
	mux := http.NewServeMux()
	service.mountRoutes(mux)
	return mux
}
func customerHTTP(t *testing.T, handler http.Handler, method, path, body string, headers map[string]string, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(method, "https://cars.example"+path, bytes.NewBufferString(body))
	for k, v := range headers {
		r.Header.Set(k, v)
	}
	if cookie != nil {
		r.AddCookie(cookie)
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	if w.Header().Get("Cache-Control") != "no-store" {
		t.Fatal("auth response may be cached")
	}
	return w
}
func TestCustomerAuthErrorCachePolicy(t *testing.T) {
	service := &customerAuthService{config: customerAuthConfig{Mode: "firebase"}}
	for _, failure := range []struct {
		name, code, message    string
		err                    error
		status                 int
		retryable, clearCookie bool
	}{
		{"unauthenticated", "UNAUTHENTICATED", "Authentication is required.", ErrUnauthenticated, 401, false, true},
		{"blocked", "FORBIDDEN", "Access is denied.", ErrCustomerBlocked, 403, false, false},
		{"csrf", "FORBIDDEN", "Request origin or CSRF token is invalid.", ErrCustomerCSRF, 403, false, false},
		{"dependency", "AUTHENTICATION_UNAVAILABLE", "Authentication is temporarily unavailable.", ErrCustomerDependency, 503, true, false},
	} {
		for _, policy := range []struct{ name, initial, want string }{
			{"protected", "private, no-store", "private, no-store"},
			{"unset", "", "no-store"},
			{"auth", "no-store", "no-store"},
			{"unsafe", "public, max-age=3600", "no-store"},
		} {
			t.Run(failure.name+"/"+policy.name, func(t *testing.T) {
				r := httptest.NewRequest("GET", "https://cars.example/v1/catalog/years", nil)
				r = r.WithContext(context.WithValue(r.Context(), requestIDContextKey, "cache-policy-request"))
				w := httptest.NewRecorder()
				if policy.initial != "" {
					w.Header().Set("Cache-Control", policy.initial)
				}
				service.writeError(w, r, failure.err)
				if got := w.Header().Get("Cache-Control"); got != policy.want {
					t.Errorf("Cache-Control = %q, want %q", got, policy.want)
				}
				if w.Code != failure.status {
					t.Errorf("status = %d, want %d", w.Code, failure.status)
				}
				var body struct {
					Error struct {
						Code, Message string
						Retryable     bool
						RequestID     string `json:"request_id"`
						Details       struct {
							LoginAvailable bool `json:"login_available"`
						}
					}
				}
				if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
					t.Fatal(err)
				}
				if body.Error.Code != failure.code || body.Error.Message != failure.message || body.Error.Retryable != failure.retryable || body.Error.RequestID != "cache-policy-request" || !body.Error.Details.LoginAvailable {
					t.Errorf("unexpected error body: %s", w.Body.String())
				}
				cookies := w.Result().Cookies()
				if failure.clearCookie {
					if len(cookies) != 1 || cookies[0].Name != "__Host-autodata_session" || cookies[0].Value != "" || cookies[0].MaxAge != -1 || !cookies[0].Secure || !cookies[0].HttpOnly || cookies[0].Path != "/" {
						t.Errorf("unauthenticated response must clear the secure session cookie: %v", cookies)
					}
				} else if len(cookies) != 0 {
					t.Errorf("error must preserve the session cookie: %v", cookies)
				}
			})
		}
	}
}

func TestCustomerAuthProtectedCachePolicy(t *testing.T) {
	now := time.Now().UTC()
	token, _, err := newCustomerSessionToken()
	if err != nil {
		t.Fatal(err)
	}
	service := &customerAuthService{
		config:   customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"},
		store:    &customerSessionFixture{session: customerSession{AccountID: "account", OrganizationID: "org", ProjectID: "fixture-project", UID: "fixture-user", AuthTime: now.Unix(), ExpiresAt: now.Add(time.Hour)}},
		verifier: &customerVerifierFixture{},
		now:      func() time.Time { return now },
	}
	server := NewServer(staticReadiness{})
	server.customerAuth, server.auth = service, service
	for _, tc := range []struct {
		name, method, origin, csrf string
		cookie                     bool
		status                     int
	}{
		{"missing_session", "GET", "", "", false, 401},
		{"invalid_origin", "POST", "https://foreign.example", "invalid", true, 403},
		{"invalid_csrf", "POST", "https://cars.example", "invalid", true, 403},
	} {
		t.Run(tc.name, func(t *testing.T) {
			called := false
			handler := server.paidCatalogAuthenticated(func(http.ResponseWriter, *http.Request, Principal) { called = true })
			r := httptest.NewRequest(tc.method, "https://cars.example/v1/catalog/years", nil)
			if tc.origin != "" {
				r.Header.Set("Origin", tc.origin)
			}
			if tc.csrf != "" {
				r.Header.Set("X-CSRF-Token", tc.csrf)
			}
			if tc.cookie {
				r.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
			}
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, r)
			if w.Code != tc.status || called {
				t.Errorf("protected boundary: status = %d, next called = %v", w.Code, called)
			}
			if got := w.Header().Get("Cache-Control"); got != "private, no-store" {
				t.Errorf("Cache-Control = %q, want private, no-store", got)
			}
			if got := w.Header().Get("X-Content-Type-Options"); got != "nosniff" {
				t.Errorf("X-Content-Type-Options = %q, want nosniff", got)
			}
		})
	}
}

func TestCustomerAuthHTTPBoundaries(t *testing.T) {
	now := time.Now().UTC()
	identity := VerifiedCustomerIdentity{ProjectID: "fixture-project", UID: "fixture-user", AuthTime: now.Unix(), IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix()}
	store := &customerSessionFixture{session: customerSession{AccountID: "account", OrganizationID: "org", ProjectID: identity.ProjectID, UID: identity.UID, AuthTime: identity.AuthTime, ExpiresAt: now.Add(time.Hour)}}
	verifier := &customerVerifierFixture{identity: identity}
	service := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example", ProjectID: "fixture-project", APIKey: "public-key", AppID: "1:123:web:abc", AuthDomain: "fixture-project.firebaseapp.com"}, store: store, verifier: verifier, now: func() time.Time { return now }}
	handler := customerAuthHandler(service)
	w := customerHTTP(t, handler, "GET", "/auth/config", "", nil, nil)
	if w.Code != 200 || !bytes.Contains(w.Body.Bytes(), []byte(`"login_available":true`)) {
		t.Fatal("missing Firebase public config", w.Code)
	}
	for _, tc := range []struct{ method, path string }{{"GET", "/auth/session"}, {"POST", "/auth/logout"}} {
		if w = customerHTTP(t, handler, tc.method, tc.path, "", nil, nil); w.Code != 401 {
			t.Fatal("missing session accepted", tc.path, w.Code)
		}
	}
	good := map[string]string{"Origin": "https://cars.example", "Content-Type": "application/json", "X-Autodata-Session-Exchange": "1"}
	for _, headers := range []map[string]string{nil, {"Origin": "https://foreign.example", "Content-Type": "application/json", "X-Autodata-Session-Exchange": "1"}, {"Origin": "https://cars.example", "Content-Type": "application/json"}} {
		if w = customerHTTP(t, handler, "POST", "/auth/firebase/session", `{"id_token":"fixture"}`, headers, nil); w.Code != 403 {
			t.Fatal("unbound exchange accepted", w.Code)
		}
	}
	if w = customerHTTP(t, handler, "POST", "/auth/firebase/session", `{"id_token":"fixture","roles":["platform_admin"]}`, good, nil); w.Code != 400 {
		t.Fatal("extra authority fields accepted", w.Code)
	}
	w = customerHTTP(t, handler, "POST", "/auth/firebase/session", `{"id_token":"fixture"}`, good, nil)
	if w.Code != 204 || len(w.Result().Cookies()) != 1 {
		t.Fatal("exchange did not commit cookie", w.Code)
	}
	cookie := w.Result().Cookies()[0]
	w = customerHTTP(t, handler, "GET", "/auth/session", "", nil, cookie)
	if w.Code != 200 {
		t.Fatal("session unavailable", w.Code)
	}
	var session map[string]any
	json.Unmarshal(w.Body.Bytes(), &session)
	if len(session) != 4 || session["authenticated"] != true {
		t.Fatal("unsafe public session")
	}
	for _, headers := range []map[string]string{
		{"Origin": "https://foreign.example", "X-CSRF-Token": session["csrf_token"].(string)},
		{"Origin": "https://cars.example", "X-CSRF-Token": "invalid"},
	} {
		if w = customerHTTP(t, handler, "POST", "/auth/logout", "", headers, cookie); w.Code != 403 || store.revoked {
			t.Fatal("unbound logout accepted", w.Code)
		}
	}
	verifier.checkErr = ErrCustomerDependency
	w = customerHTTP(t, handler, "GET", "/auth/session", "", nil, cookie)
	if w.Code != 503 || len(w.Result().Cookies()) != 0 {
		t.Fatal("outage must preserve cookie and deny", w.Code)
	}
	w = customerHTTP(t, handler, "POST", "/auth/logout", "", map[string]string{"Origin": "https://cars.example", "X-CSRF-Token": session["csrf_token"].(string)}, cookie)
	if w.Code != 204 || !store.revoked {
		t.Fatal("local logout failed during Firebase outage", w.Code)
	}
	service.verifier = nil
	if w = customerHTTP(t, handler, "POST", "/auth/firebase/session", `{"id_token":"fixture"}`, good, nil); w.Code != 503 || len(w.Result().Cookies()) != 0 {
		t.Fatal("exchange dependency outage must preserve cookie and deny", w.Code)
	}
}
func TestCustomerLocalLoginUnavailable(t *testing.T) {
	handler := customerAuthHandler(&customerAuthService{config: customerAuthConfig{Mode: "local", Origin: "https://cars.example"}})
	for _, tc := range []struct {
		method, path string
		status       int
	}{{"GET", "/auth/config", 200}, {"GET", "/auth/session", 401}, {"POST", "/auth/firebase/session", 503}} {
		w := customerHTTP(t, handler, tc.method, tc.path, "", nil, nil)
		if w.Code != tc.status || !bytes.Contains(w.Body.Bytes(), []byte(`"login_available":false`)) || len(w.Result().Cookies()) > 0 {
			t.Fatal("local browser login available", w.Code, w.Body.String())
		}
	}
}

func testFirebaseExchangeAndUserRevocation(t *testing.T, persist customerSessionStore) {
	f := newFirebaseSDKFixture(t)
	service := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example", ProjectID: "fixture-project"}, store: persist, verifier: f.verifier, now: func() time.Time { return f.now }}
	api := NewServer(staticReadiness{})
	api.customerAuth, api.auth = service, service
	server := httptest.NewServer(api.Handler())
	defer server.Close()
	exchange := func(token string, cookie *http.Cookie) *http.Response {
		body, _ := json.Marshal(map[string]string{"id_token": token})
		r, _ := http.NewRequestWithContext(context.Background(), "POST", server.URL+"/auth/firebase/session", bytes.NewReader(body))
		r.Header.Set("Origin", "https://cars.example")
		r.Header.Set("Content-Type", "application/json")
		r.Header.Set("X-Autodata-Session-Exchange", "1")
		if cookie != nil {
			r.AddCookie(cookie)
		}
		response, err := http.DefaultClient.Do(r)
		if err != nil {
			t.Fatal(err)
		}
		io.Copy(io.Discard, response.Body)
		response.Body.Close()
		return response
	}
	token := f.token(t, nil)
	response := exchange(token, nil)
	if response.StatusCode != 204 {
		t.Fatal("real SDK exchange failed", response.StatusCode)
	}
	old := response.Cookies()[0]
	response = exchange(token, old)
	if response.StatusCode != 204 {
		t.Fatal("fresh token re-exchange rejected")
	}
	cookie := response.Cookies()[0]
	protectedStatus := func(cookie *http.Cookie) int {
		request, _ := http.NewRequest("GET", server.URL+"/v1/catalog/years", nil)
		request.AddCookie(cookie)
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			t.Fatal(err)
		}
		io.Copy(io.Discard, response.Body)
		response.Body.Close()
		return response.StatusCode
	}
	if status := protectedStatus(old); status != 401 {
		t.Fatal("old cookie survived rotation", status)
	}
	if status := protectedStatus(cookie); status != 200 {
		t.Fatal("protected request denied", status)
	}
	if response = exchange(f.token(t, func(c map[string]any) { c["aud"] = "foreign" }), nil); response.StatusCode != 401 {
		t.Fatal("wrong project accepted")
	}
	f.mu.Lock()
	f.validSince = f.now.Unix() + 1
	f.mu.Unlock()
	if status := protectedStatus(cookie); status != 401 {
		t.Fatal("Firebase revocation ignored", status)
	}
	f.mu.Lock()
	f.validSince = 0
	f.disabled = true
	f.mu.Unlock()
	if status := protectedStatus(cookie); status != 401 {
		t.Fatal("Firebase disabled ignored", status)
	}
	f.mu.Lock()
	f.disabled = false
	f.status = 403
	f.mu.Unlock()
	if status := protectedStatus(cookie); status != 503 {
		t.Fatal("Firebase outage accepted stale state", status)
	}
}

func TestConfiguredCustomerAuthRequiresPersistenceAndWiresServer(t *testing.T) {
	config := customerAuthConfig{Mode: "firebase", Origin: "https://cars.example", ProjectID: "fixture-project"}
	if _, err := newConfiguredCustomerAuth(context.Background(), config, nil, &customerVerifierFixture{}); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("Firebase memory persistence accepted")
	}
	if _, err := newConfiguredCustomerAuth(context.Background(), config, &customerSessionFixture{}, &customerVerifierFixture{}); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("Firebase in-memory persistence accepted")
	}
	t.Setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
	if _, err := newConfiguredCustomerAuth(context.Background(), config, &customerSessionFixture{}, &customerVerifierFixture{}); err == nil {
		t.Fatal("emulator startup accepted")
	}
	t.Setenv("FIREBASE_AUTH_EMULATOR_HOST", "")
	service, err := newConfiguredCustomerAuth(context.Background(), customerAuthConfig{Mode: "local", Origin: "https://cars.example"}, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	server := NewServer(staticReadiness{})
	server.customerAuth = service
	response := customerHTTP(t, server.Handler(), "GET", "/auth/config", "", nil, nil)
	if response.Code != 200 {
		t.Fatal("auth routes missing from API")
	}
}
