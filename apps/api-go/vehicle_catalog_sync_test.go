package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type catalogSyncCapture struct {
	called chan struct{}
	path   string
	body   string
	key    string
}

func (c *catalogSyncCapture) Do(_ *http.Request, path string, body []byte, key string) (int, []byte, error) {
	c.path = path
	c.body = string(body)
	c.key = key
	select {
	case c.called <- struct{}{}:
	default:
	}
	return http.StatusAccepted, []byte(`{"status":"scheduled"}`), nil
}

func TestSelectorsScheduleCatalogWarmupWhenDurableCatalogIsEmpty(t *testing.T) {
	capture := &catalogSyncCapture{called: make(chan struct{}, 1)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		capture,
	)
	request := httptest.NewRequest(http.MethodGet, "/vehicle-identities/selectors", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	select {
	case <-capture.called:
	case <-time.After(time.Second):
		t.Fatal("selector read did not schedule catalog warmup")
	}
	if capture.path != "/v1/catalog-sync/ensure" {
		t.Fatalf("path = %q, want /v1/catalog-sync/ensure", capture.path)
	}
	if !strings.Contains(capture.body, `"provider":"autoapitwo"`) {
		t.Fatalf("body = %s, want autoapitwo provider", capture.body)
	}
	if capture.key != "catalog-sync:autoapitwo:autoapitwo-fleet-v1" {
		t.Fatalf("idempotency key = %q", capture.key)
	}
	if !strings.Contains(response.Body.String(), `"catalog_sync"`) {
		t.Fatalf("body = %s, want catalog_sync readiness", response.Body.String())
	}
}
