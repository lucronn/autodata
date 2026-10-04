package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"testing"
	"time"
)

func TestConfiguredAuthenticatorAcceptsVerifiedServiceKey(t *testing.T) {
	t.Setenv("AUTODATA_AUTH_MODE", "service_key")
	t.Setenv("AUTODATA_SERVICE_KEYS_JSON", serviceKeysJSON(t, "catalog-client", "org-1", []string{"dataset_viewer"}, "catalog-key", time.Now().Add(time.Hour)))

	auth, err := configuredAuthenticator()
	if err != nil {
		t.Fatal(err)
	}
	request, _ := http.NewRequest(http.MethodGet, "/datasets/demo", nil)
	request.Header.Set("Authorization", "Bearer catalog-key")

	principal, err := auth.Authenticate(request)
	if err != nil {
		t.Fatal(err)
	}
	if principal.Subject != "catalog-client" || principal.OrganizationID != "org-1" || !principal.HasRole("dataset_viewer") {
		t.Fatalf("principal = %#v", principal)
	}
}

func TestConfiguredAuthenticatorRejectsForgedServiceKey(t *testing.T) {
	t.Setenv("AUTODATA_AUTH_MODE", "service_key")
	t.Setenv("AUTODATA_SERVICE_KEYS_JSON", serviceKeysJSON(t, "catalog-client", "org-1", []string{"dataset_viewer"}, "catalog-key", time.Now().Add(time.Hour)))

	auth, err := configuredAuthenticator()
	if err != nil {
		t.Fatal(err)
	}
	request, _ := http.NewRequest(http.MethodGet, "/datasets/demo", nil)
	request.Header.Set("Authorization", "Bearer forged-key")

	if _, err := auth.Authenticate(request); err != ErrUnauthenticated {
		t.Fatalf("forged key error = %v, want %v", err, ErrUnauthenticated)
	}
}

func TestConfiguredAuthenticatorRejectsExpiredServiceKey(t *testing.T) {
	t.Setenv("AUTODATA_AUTH_MODE", "service_key")
	t.Setenv("AUTODATA_SERVICE_KEYS_JSON", serviceKeysJSON(t, "catalog-client", "org-1", []string{"dataset_viewer"}, "expired-key", time.Now().Add(-time.Minute)))

	auth, err := configuredAuthenticator()
	if err != nil {
		t.Fatal(err)
	}
	request, _ := http.NewRequest(http.MethodGet, "/datasets/demo", nil)
	request.Header.Set("Authorization", "Bearer expired-key")

	if _, err := auth.Authenticate(request); err != ErrUnauthenticated {
		t.Fatalf("expired key error = %v, want %v", err, ErrUnauthenticated)
	}
}

func TestConfiguredAuthenticatorFailsClosedWithoutServiceKeys(t *testing.T) {
	t.Setenv("AUTODATA_AUTH_MODE", "")
	t.Setenv("AUTODATA_SERVICE_KEYS_JSON", "")

	if _, err := configuredAuthenticator(); err == nil {
		t.Fatal("missing service keys must fail startup configuration")
	}
}

func TestLocalAuthenticatorRequiresExplicitDevelopmentMode(t *testing.T) {
	t.Setenv("AUTODATA_AUTH_MODE", "service_key")
	t.Setenv("AUTODATA_SERVICE_KEYS_JSON", serviceKeysJSON(t, "catalog-client", "org-1", []string{"dataset_viewer"}, "catalog-key", time.Now().Add(time.Hour)))

	auth, err := configuredAuthenticator()
	if err != nil {
		t.Fatal(err)
	}
	request, _ := http.NewRequest(http.MethodGet, "/datasets/demo", nil)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	if _, err := auth.Authenticate(request); err != ErrUnauthenticated {
		t.Fatalf("local token in normal mode error = %v, want %v", err, ErrUnauthenticated)
	}

	t.Setenv("AUTODATA_AUTH_MODE", "local")
	localAuth, err := configuredAuthenticator()
	if err != nil {
		t.Fatal(err)
	}
	principal, err := localAuth.Authenticate(request)
	if err != nil || principal.OrganizationID != "org-1" || !principal.HasRole("dataset_viewer") {
		t.Fatalf("explicit local mode principal=%#v error=%v", principal, err)
	}
}

func serviceKeysJSON(t *testing.T, subject, organizationID string, roles []string, key string, expiresAt time.Time) string {
	t.Helper()
	digest := sha256.Sum256([]byte(key))
	payload, err := json.Marshal([]ServiceKeyCredential{{
		KeySHA256:      hex.EncodeToString(digest[:]),
		Subject:        subject,
		OrganizationID: organizationID,
		Roles:          roles,
		ExpiresAt:      expiresAt.UTC(),
	}})
	if err != nil {
		t.Fatal(err)
	}
	return string(payload)
}
