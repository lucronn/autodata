package main

import (
	"context"
	"errors"
	"net/http/httptest"
	"testing"
	"time"
)

type customerSessionFixture struct {
	session   customerSession
	lookupErr error
	revoked   bool
}

func (f *customerSessionFixture) Rotate(context.Context, VerifiedCustomerIdentity, []byte, []byte, time.Time, time.Time) (customerSession, error) {
	return f.session, nil
}
func (f *customerSessionFixture) Lookup(context.Context, []byte, time.Time) (customerSession, error) {
	if f.revoked {
		return customerSession{}, ErrUnauthenticated
	}
	return f.session, f.lookupErr
}
func (f *customerSessionFixture) Revoke(context.Context, []byte, time.Time) error {
	f.revoked = true
	return nil
}
func (f *customerSessionFixture) CheckSchema(context.Context) error { return nil }

type customerVerifierFixture struct {
	checkErr error
	identity VerifiedCustomerIdentity
	checks   int
}

func (f *customerVerifierFixture) VerifyLogin(context.Context, string) (VerifiedCustomerIdentity, error) {
	return f.identity, nil
}
func (f *customerVerifierFixture) CheckUser(context.Context, string, string, int64) error {
	f.checks++
	return f.checkErr
}
func TestCustomerSessionChecksCurrentIdentityAndCSRF(t *testing.T) {
	now := time.Now().UTC()
	token, hash, err := newCustomerSessionToken()
	if err != nil || len(hash) != 32 {
		t.Fatal("token generation failed")
	}
	store := &customerSessionFixture{session: customerSession{AccountID: "account", OrganizationID: "organization", ProjectID: "fixture-project", UID: "uid", AuthTime: now.Unix(), ExpiresAt: now.Add(time.Hour)}}
	verifier := &customerVerifierFixture{}
	service := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"}, store: store, verifier: verifier, now: func() time.Time { return now }}
	request := httptest.NewRequest("GET", "https://cars.example/datasets/id", nil)
	request.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
	principal, err := service.Authenticate(request)
	if err != nil || principal.OrganizationID != "organization" || !principal.HasRole("dataset_viewer") || principal.HasRole("platform_admin") {
		t.Fatal("customer authority incorrect", err)
	}
	verifier.checkErr = ErrUnauthenticated
	if _, err = service.Authenticate(request); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("revoked Firebase user accepted")
	}
	verifier.checkErr = ErrCustomerDependency
	if _, err = service.Authenticate(request); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("Firebase outage authenticated stale state")
	}
	verifier.checkErr = nil
	request.Method = "POST"
	if _, err = service.Authenticate(request); !errors.Is(err, ErrCustomerCSRF) {
		t.Fatal("cookie mutation without CSRF accepted")
	}
	request.Header.Set("Origin", "https://cars.example")
	request.Header.Set("X-CSRF-Token", customerCSRF(token))
	if _, err = service.Authenticate(request); err != nil {
		t.Fatal(err)
	}
	request.Header.Set("Authorization", "Bearer ignored")
	if _, err = service.Authenticate(request); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("Authorization silently fell back to cookie")
	}
}
func TestCustomerSessionCookieAndTokenBoundary(t *testing.T) {
	token, _, err := newCustomerSessionToken()
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	cookie := customerSessionCookie(token, now.Add(12*time.Hour), now)
	if !cookie.Secure || !cookie.HttpOnly || cookie.Path != "/" || cookie.Domain != "" || cookie.MaxAge > 43200 {
		t.Fatal("unsafe cookie")
	}
	if customerCSRF(token) == customerCSRF(token+"x") {
		t.Fatal("CSRF not session bound")
	}
	request := httptest.NewRequest("GET", "/", nil)
	request.AddCookie(cookie)
	if _, _, err := customerRequestToken(request); err != nil {
		t.Fatal(err)
	}
	request.AddCookie(cookie)
	if _, _, err := customerRequestToken(request); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("ambiguous cookies accepted")
	}
}
