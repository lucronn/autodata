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
	verifier.checkErr = ErrCustomerDependency
	w = customerHTTP(t, handler, "GET", "/auth/session", "", nil, cookie)
	if w.Code != 503 || len(w.Result().Cookies()) != 0 {
		t.Fatal("outage must preserve cookie and deny", w.Code)
	}
	w = customerHTTP(t, handler, "POST", "/auth/logout", "", map[string]string{"Origin": "https://cars.example", "X-CSRF-Token": session["csrf_token"].(string)}, cookie)
	if w.Code != 204 || !store.revoked {
		t.Fatal("local logout failed during Firebase outage", w.Code)
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
