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
	rotations int
}

func (f *customerSessionFixture) Rotate(context.Context, VerifiedCustomerIdentity, []byte, []byte, time.Time, time.Time) (customerSession, error) {
	f.rotations++
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
	loginErr error
	identity VerifiedCustomerIdentity
	checks   int
}

func (f *customerVerifierFixture) VerifyLogin(context.Context, string) (VerifiedCustomerIdentity, error) {
	return f.identity, f.loginErr
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

func TestStagingTesterEverySessionLookupChecksProjectAndUID(t *testing.T) {
	now := time.Now().UTC()
	token, _, _ := newCustomerSessionToken()
	request := httptest.NewRequest("GET", "https://cars.example/auth/session", nil)
	request.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
	for _, checkUser := range []bool{false, true} {
		for _, tc := range []struct {
			project, uid string
			deny         bool
		}{{"fixture-project", "fixture-user", false}, {"fixture-project", "removed-user", true}, {"other-project", "fixture-user", true}} {
			verifier := &customerVerifierFixture{}
			store := &customerSessionFixture{session: customerSession{ProjectID: tc.project, UID: tc.uid, ExpiresAt: now.Add(time.Hour)}}
			service := &customerAuthService{config: stagingTesterTestConfig(t, `["fixture-user"]`), store: store, verifier: verifier, now: func() time.Time { return now }}
			_, _, err := service.session(request, checkUser)
			if tc.deny {
				if !errors.Is(err, ErrCustomerBlocked) || verifier.checks != 0 {
					t.Errorf("restricted existing cookie accepted, project=%s checkUser=%v", tc.project, checkUser)
				}
			} else if err != nil {
				t.Fatal(err)
			}
		}
	}
	// A reconstructed configuration removes membership without trusting an old cookie.
	service := &customerAuthService{config: stagingTesterTestConfig(t, `["replacement-user"]`), store: &customerSessionFixture{session: customerSession{ProjectID: "fixture-project", UID: "fixture-user", ExpiresAt: now.Add(time.Hour)}}, verifier: &customerVerifierFixture{}, now: func() time.Time { return now }}
	if _, err := service.Authenticate(request); !errors.Is(err, ErrCustomerBlocked) {
		t.Fatal("stale cookie survived tester removal", err)
	}
}

func TestStagingTesterApprovedSessionStillChecksFirebaseRevocation(t *testing.T) {
	now := time.Now().UTC()
	token, _, _ := newCustomerSessionToken()
	r := httptest.NewRequest("GET", "https://cars.example/auth/session", nil)
	r.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
	verifier := &customerVerifierFixture{checkErr: ErrUnauthenticated}
	service := &customerAuthService{config: stagingTesterTestConfig(t, `["fixture-user"]`), store: &customerSessionFixture{session: customerSession{ProjectID: "fixture-project", UID: "fixture-user", ExpiresAt: now.Add(time.Hour)}}, verifier: verifier, now: func() time.Time { return now }}
	if _, err := service.Authenticate(r); !errors.Is(err, ErrUnauthenticated) || verifier.checks != 1 {
		t.Fatal("approved audience bypassed Firebase revocation", err)
	}
}
