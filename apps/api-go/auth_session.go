package main

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"net/http"
	"time"
)

var (
	ErrCustomerDependency = errors.New("authentication dependency is unavailable")
	ErrCustomerBlocked    = errors.New("customer account is blocked")
	ErrCustomerCSRF       = errors.New("request origin or CSRF token is invalid")
)

const customerSessionName = "__Host-autodata_session"
const customerSessionLifetime = 12 * time.Hour

type VerifiedCustomerIdentity struct {
	ProjectID, UID              string
	AuthTime, IssuedAt, Expires int64
}
type CustomerIdentityVerifier interface {
	VerifyLogin(context.Context, string) (VerifiedCustomerIdentity, error)
	CheckUser(context.Context, string, string, int64) error
}
type customerSession struct {
	AccountID, OrganizationID, ProjectID, UID string
	AuthTime                                  int64
	ExpiresAt                                 time.Time
}
type customerSessionStore interface {
	Rotate(context.Context, VerifiedCustomerIdentity, []byte, []byte, time.Time, time.Time) (customerSession, error)
	Lookup(context.Context, []byte, time.Time) (customerSession, error)
	Revoke(context.Context, []byte, time.Time) error
	CheckSchema(context.Context) error
}
type customerAuthService struct {
	config   customerAuthConfig
	store    customerSessionStore
	verifier CustomerIdentityVerifier
	now      func() time.Time
}

func (s *customerAuthService) clock() time.Time {
	if s.now != nil {
		return s.now().UTC()
	}
	return time.Now().UTC()
}
func newCustomerSessionToken() (string, []byte, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", nil, err
	}
	token := base64.RawURLEncoding.EncodeToString(b)
	hash := sha256.Sum256([]byte(token))
	return token, hash[:], nil
}
func customerRequestToken(r *http.Request) (string, []byte, error) {
	if len(r.Header.Values("Authorization")) != 0 {
		return "", nil, ErrUnauthenticated
	}
	var token string
	count := 0
	for _, cookie := range r.Cookies() {
		if cookie.Name == customerSessionName {
			token = cookie.Value
			count++
		}
	}
	decoded, err := base64.RawURLEncoding.DecodeString(token)
	if count != 1 || err != nil || len(decoded) != 32 || base64.RawURLEncoding.EncodeToString(decoded) != token {
		return "", nil, ErrUnauthenticated
	}
	hash := sha256.Sum256([]byte(token))
	return token, hash[:], nil
}
func customerCSRF(token string) string {
	mac := hmac.New(sha256.New, []byte(token))
	mac.Write([]byte("autodata/csrf/v1"))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}
func customerSessionCookie(token string, expires, now time.Time) *http.Cookie {
	maxAge := int(expires.Sub(now).Seconds())
	if maxAge > int(customerSessionLifetime.Seconds()) {
		maxAge = int(customerSessionLifetime.Seconds())
	}
	if token == "" {
		maxAge = -1
		expires = time.Unix(1, 0)
	}
	return &http.Cookie{Name: customerSessionName, Value: token, Path: "/", Secure: true, HttpOnly: true, SameSite: http.SameSiteLaxMode, Expires: expires.UTC(), MaxAge: maxAge}
}
func (s *customerAuthService) validOrigin(r *http.Request) bool {
	return r.Header.Get("Origin") == s.config.Origin && s.config.Origin != "" && (r.Header.Get("Sec-Fetch-Site") == "" || r.Header.Get("Sec-Fetch-Site") == "same-origin" || r.Header.Get("Sec-Fetch-Site") == "none")
}
func (s *customerAuthService) session(r *http.Request, checkUser bool) (customerSession, string, error) {
	if s.config.Mode != "firebase" || s.store == nil {
		return customerSession{}, "", ErrUnauthenticated
	}
	token, hash, err := customerRequestToken(r)
	if err != nil {
		return customerSession{}, "", err
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	session, err := s.store.Lookup(ctx, hash, s.clock())
	if err != nil {
		return customerSession{}, "", err
	}
	if !session.ExpiresAt.After(s.clock()) {
		return customerSession{}, "", ErrUnauthenticated
	}
	if checkUser {
		if s.verifier == nil {
			return customerSession{}, "", ErrCustomerDependency
		}
		if err = s.verifier.CheckUser(ctx, session.ProjectID, session.UID, session.AuthTime); err != nil {
			return customerSession{}, "", err
		}
	}
	return session, token, nil
}
func (s *customerAuthService) Authenticate(r *http.Request) (Principal, error) {
	session, token, err := s.session(r, true)
	if err != nil {
		return Principal{}, err
	}
	if r.Method != "GET" && r.Method != "HEAD" && r.Method != "OPTIONS" {
		if !s.validOrigin(r) || !hmac.Equal([]byte(r.Header.Get("X-CSRF-Token")), []byte(customerCSRF(token))) {
			return Principal{}, ErrCustomerCSRF
		}
	}
	return Principal{OrganizationID: session.OrganizationID, Roles: []string{"dataset_viewer"}, CustomerAccountID: session.AccountID, FirebaseProjectID: session.ProjectID, FirebaseUID: session.UID}, nil
}
