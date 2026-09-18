package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type catalogSyncCapture struct {
	calls chan catalogSyncCall
}

type catalogSyncCall struct {
	path string
	body string
	key  string
}

type selectorFixtureStore struct {
	selectors VehicleIdentitySelectors
}

func (s *selectorFixtureStore) Resolve(Principal, VehicleIdentityResolveInput, string) (VehicleIdentityResolveRecord, bool, error) {
	return VehicleIdentityResolveRecord{}, false, nil
}

func (s *selectorFixtureStore) Selectors(Principal) (VehicleIdentitySelectors, error) {
	return s.selectors, nil
}

func (c *catalogSyncCapture) Do(_ *http.Request, path string, body []byte, key string) (int, []byte, error) {
	call := catalogSyncCall{path: path, body: string(body), key: key}
	select {
	case c.calls <- call:
	default:
	}
	return http.StatusAccepted, []byte(`{"status":"scheduled"}`), nil
}

func TestSelectorsScheduleCatalogWarmupWhenDurableCatalogIsEmpty(t *testing.T) {
	capture := &catalogSyncCapture{calls: make(chan catalogSyncCall, 2)}
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
	calls := map[string]catalogSyncCall{}
	deadline := time.After(time.Second)
	for len(calls) < 2 {
		select {
		case call := <-capture.calls:
			calls[call.path] = call
		case <-deadline:
			t.Fatal("selector read did not schedule both catalog warmups")
		}
	}
	for _, path := range []string{"/v1/catalog-years/ensure", "/v1/catalog-sync/ensure"} {
		call, ok := calls[path]
		if !ok {
			t.Fatalf("scheduled paths = %#v, missing %s", calls, path)
		}
		if !strings.Contains(call.body, `"provider":"autoapitwo"`) {
			t.Fatalf("body = %s, want autoapitwo provider", call.body)
		}
	}
	if calls["/v1/catalog-years/ensure"].key != "catalog-years:autoapitwo:autoapitwo-fleet-v1" {
		t.Fatalf("year manifest idempotency key = %q", calls["/v1/catalog-years/ensure"].key)
	}
	if calls["/v1/catalog-sync/ensure"].key != "catalog-sync:autoapitwo:autoapitwo-fleet-v1" {
		t.Fatalf("catalog idempotency key = %q", calls["/v1/catalog-sync/ensure"].key)
	}
	if !strings.Contains(response.Body.String(), `"catalog_sync"`) {
		t.Fatalf("body = %s, want catalog_sync readiness", response.Body.String())
	}
}

func TestSelectorsPreserveDurableCompletedCatalogStatus(t *testing.T) {
	capture := &catalogSyncCapture{calls: make(chan catalogSyncCall, 2)}
	server := NewServerWithVehicleIdentityStore(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		&selectorFixtureStore{selectors: VehicleIdentitySelectors{
			Years:       []int{1999},
			CatalogSync: &CatalogSyncStatus{Provider: "autoapitwo", SourceVersion: "autoapitwo-fleet-v1", Status: "completed", RowCount: 123},
		}},
	)
	server.ingestionClient = capture
	request := httptest.NewRequest(http.MethodGet, "/vehicle-identities/selectors", nil)
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	var selectors VehicleIdentitySelectors
	if err := json.NewDecoder(response.Body).Decode(&selectors); err != nil {
		t.Fatal(err)
	}
	if selectors.CatalogSync == nil || selectors.CatalogSync.Status != "completed" || selectors.CatalogSync.RowCount != 123 {
		t.Fatalf("catalog sync = %#v, want completed row_count 123", selectors.CatalogSync)
	}
}
