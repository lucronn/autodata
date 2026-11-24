package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
	"testing"
	"time"
)

type selectedIndexAuthenticator struct {
	Authenticator
	blocked bool
	calls   int
}

func (a *selectedIndexAuthenticator) Authenticate(r *http.Request) (Principal, error) {
	a.calls++
	if a.blocked {
		return Principal{}, ErrCustomerBlocked
	}
	return a.Authenticator.Authenticate(r)
}

func TestSelectedIndexConfirmsOnlyTheExchangedCookie(t *testing.T) {
	s, catalog, grant := paidHTTPServer()
	now := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	identity := VerifiedCustomerIdentity{
		ProjectID: "fixture-project", UID: "fixture-user", AuthTime: now.Unix(),
		IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix(),
	}
	verifier := &customerVerifierFixture{identity: identity}
	expires := now.Add(customerSessionLifetime)
	s.customerAuth = &customerAuthService{
		config:   customerAuthConfig{Mode: "firebase", Origin: "https://localhost", ProjectID: identity.ProjectID},
		verifier: verifier,
		store: &customerSessionFixture{session: customerSession{
			AccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "22222222-2222-4222-8222-222222222222",
			ProjectID: identity.ProjectID, UID: identity.UID, AuthTime: identity.AuthTime, ExpiresAt: expires,
		}},
		now: func() time.Time { return now },
	}
	s.auth = s.customerAuth
	handler := s.Handler()
	exchangeHeaders := map[string]string{
		"Origin": "https://localhost", "Content-Type": "application/json",
		"X-Autodata-Session-Exchange": "1",
	}
	ordinary := customerHTTP(t, handler, http.MethodPost, "/auth/firebase/session",
		`{"id_token":"fixture"}`, exchangeHeaders, nil)
	if ordinary.Code != 204 || ordinary.Header().Get("X-CSRF-Token") != "" || len(ordinary.Result().Cookies()) != 1 {
		t.Fatalf("ordinary exchange status=%d with unexpected receipt", ordinary.Code)
	}
	exchangeHeaders["Prefer"] = "unrelated, " + selectedIndexSessionPreference
	exchange := customerHTTP(t, handler, http.MethodPost, "/auth/firebase/session",
		`{"id_token":"fixture"}`, exchangeHeaders, nil)
	cookies := exchange.Result().Cookies()
	if exchange.Code != 204 || len(cookies) != 1 || !cookies[0].HttpOnly || !cookies[0].Secure {
		t.Fatalf("opt-in exchange status=%d did not install the secure cookie", exchange.Code)
	}
	cookie := cookies[0]
	receipt := exchange.Header().Get("X-CSRF-Token")
	if receipt != customerCSRF(cookie.Value) || exchange.Header().Get("Preference-Applied") != selectedIndexSessionPreference ||
		exchange.Header().Get("Cache-Control") != "no-store" {
		t.Fatal("exchange receipt is missing or has the wrong cookie binding")
	}
	otherCookie := ordinary.Result().Cookies()[0]
	quotes := 0
	s.commerceClient = paidIndexQuoteClient{grant, func(_ context.Context, op string, _ []byte, _ string) (int, []byte, error) {
		if op != "quote" {
			t.Fatalf("unexpected commerce operation %q", op)
		}
		quotes++
		return 503, []byte(`{"error":{"code":"COMMERCE_UNAVAILABLE"}}`), nil
	}}
	index := "/v1/catalog/vehicles/" + paidTestConfiguration + "/articles"
	catalog.progress = &CatalogArticleProgress{Complete: true, Status: "completed"}
	fillPaidIndexPageFixture(catalog, 101)
	for _, tc := range []struct {
		name, query, code string
		cookie            *http.Cookie
		authErr, grantErr error
		status, checks    int
		grants, reads     int
		proof, duplicate  bool
	}{
		{name: "owned", query: "?region=CA", cookie: cookie, status: 200, checks: 1, grants: 1, reads: 2, proof: true},
		{name: "purchase needed", query: "?region=CA", cookie: cookie, grantErr: ErrVehicleGrantRequired, status: 403, code: "ENTITLEMENT_REQUIRED", checks: 1, grants: 1, proof: true},
		{name: "grant revoked", query: "?region=CA", cookie: cookie, grantErr: ErrVehicleGrantRevoked, status: 403, code: "ENTITLEMENT_REVOKED", checks: 1, grants: 1, proof: true},
		{name: "grant unavailable", query: "?region=CA", cookie: cookie, grantErr: ErrVehicleGrantUnavailable, status: 503, code: "CATALOG_UNAVAILABLE", checks: 1, grants: 1, proof: true},
		{name: "different cookie", query: "?region=CA", cookie: otherCookie, status: 403, code: "FORBIDDEN", checks: 1},
		{name: "missing cookie", query: "?region=CA", status: 401, code: "UNAUTHENTICATED"},
		{name: "duplicate receipt", query: "?region=CA", cookie: cookie, status: 403, code: "FORBIDDEN", checks: 1, duplicate: true},
		{name: "Firebase revoked", query: "?region=CA", cookie: cookie, authErr: ErrUnauthenticated, status: 401, code: "UNAUTHENTICATED", checks: 1},
		{name: "Firebase unavailable", query: "?region=CA", cookie: cookie, authErr: ErrCustomerDependency, status: 503, code: "AUTHENTICATION_UNAVAILABLE", checks: 1},
		{name: "wrong region", query: "?region=US", cookie: cookie, status: 404, checks: 1},
		{name: "search", query: "?region=CA&q=pump", cookie: cookie, status: 200, checks: 1, grants: 1, reads: 2},
	} {
		t.Run(tc.name, func(t *testing.T) {
			verifier.checkErr, grant.err = tc.authErr, tc.grantErr
			verifier.checks, grant.calls, catalog.protected, quotes = 0, 0, 0, 0
			req := httptest.NewRequest(http.MethodGet, index+tc.query, nil)
			if tc.cookie != nil {
				req.AddCookie(tc.cookie)
			}
			req.Header.Set("Prefer", selectedIndexSessionPreference)
			req.Header.Add("Prefer", catalogIndexPagesPreference)
			if tc.name == "purchase needed" {
				req.Header.Add("Prefer", purchaseQuotePreference)
			}
			req.Header.Set("X-CSRF-Token", receipt)
			if tc.duplicate {
				req.Header.Add("X-CSRF-Token", receipt)
			}
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, req)
			gotProof := slices.Contains(w.Header().Values("Preference-Applied"), selectedIndexSessionPreference)
			gotPages := slices.Contains(w.Header().Values("Preference-Applied"), catalogIndexPagesPreference)
			gotExpiry := w.Header().Get("Workshop-Session-Expires")
			if w.Code != tc.status || gotProof != tc.proof || gotPages != (tc.name == "owned") || verifier.checks != tc.checks ||
				grant.calls != tc.grants || catalog.protected != tc.reads ||
				(tc.code != "" && !strings.Contains(w.Body.String(), tc.code)) ||
				w.Header().Get("Cache-Control") != "private, no-store" ||
				(tc.proof && gotExpiry != expires.Format(time.RFC3339)) || (!tc.proof && gotExpiry != "") {
				t.Fatalf("status=%d proof=%v expiry=%q checks=%d grants=%d reads=%d body=%s",
					w.Code, gotProof, gotExpiry, verifier.checks, grant.calls, catalog.protected, w.Body)
			}
			if tc.name == "different cookie" && len(w.Result().Cookies()) != 0 {
				t.Fatal("mismatched exchange cleared the other tab's valid cookie")
			}
			if tc.name == "purchase needed" {
				if quotes != 1 || !slices.Contains(w.Header().Values("Preference-Applied"), purchaseQuotePreference) ||
					!strings.Contains(w.Body.String(), `"purchase_quote":null`) {
					t.Fatal("session confirmation displaced the negotiated purchase quote")
				}
			} else if quotes != 0 {
				t.Fatal("unexpected commerce quote call")
			}
		})
	}
	t.Run("configured authenticator remains authoritative", func(t *testing.T) {
		guard := &selectedIndexAuthenticator{Authenticator: s.customerAuth, blocked: true}
		s.auth = guard
		wrappedHandler := s.Handler()
		wrappedExchange := customerHTTP(t, wrappedHandler, http.MethodPost, "/auth/firebase/session",
			`{"id_token":"fixture"}`, exchangeHeaders, nil)
		if wrappedExchange.Code != 204 || wrappedExchange.Header().Get("X-CSRF-Token") != "" {
			t.Fatalf("wrapped auth advertised unsupported negotiation, status=%d", wrappedExchange.Code)
		}
		grant.calls = 0
		request := func() *httptest.ResponseRecorder {
			r := httptest.NewRequest(http.MethodGet, index+"?region=CA", nil)
			r.AddCookie(cookie)
			r.Header.Set("Prefer", selectedIndexSessionPreference)
			r.Header.Set("X-CSRF-Token", receipt)
			w := httptest.NewRecorder()
			wrappedHandler.ServeHTTP(w, r)
			return w
		}
		if response := request(); response.Code != 403 || guard.calls != 1 || grant.calls != 0 ||
			response.Header().Get("Workshop-Session-Expires") != "" {
			t.Fatalf("wrapped policy was bypassed, status=%d auth=%d grants=%d", response.Code, guard.calls, grant.calls)
		}
		guard.blocked = false
		if response := request(); response.Code != 200 || guard.calls != 2 || grant.calls != 1 ||
			response.Header().Get("Workshop-Session-Expires") != "" {
			t.Fatalf("wrapped legacy read status=%d auth=%d grants=%d", response.Code, guard.calls, grant.calls)
		}
	})
}
