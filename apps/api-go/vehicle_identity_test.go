package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestVehicleIdentityResolveMergesCoarseAndRichRows(t *testing.T) {
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	store := newMemoryVehicleIdentityStore()
	server := NewServerWithVehicleIdentityStore(staticReadiness{}, auth, newMemoryRequestStore(), store)
	body := `{"vehicles":[{"year":"99","make":"Chevy","model":"Silverado 1500","region":"US","drivetrain":"2wd"},{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"2WD","engine_displacement_l":5.3}]}`
	request := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	request.Header.Set("Idempotency-Key", "vehicles-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusCreated)
	}
	var result VehicleIdentityResolveRecord
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		t.Fatal(err)
	}
	if len(result.Vehicles) != 1 {
		t.Fatalf("families = %d, want 1", len(result.Vehicles))
	}
	if result.Vehicles[0].VehicleIDKey != "chevrolet-silverado-1500-1999-us" {
		t.Fatalf("key = %q", result.Vehicles[0].VehicleIDKey)
	}
	if len(result.Vehicles[0].Configurations) != 2 {
		t.Fatalf("configurations = %d, want 2", len(result.Vehicles[0].Configurations))
	}
}

func TestVehicleIdentityResolveIsIdempotent(t *testing.T) {
	server := NewServer(staticReadiness{})
	body := `{"vehicles":[{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US"}]}`
	first := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	first.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	first.Header.Set("Idempotency-Key", "vehicles-2")
	firstResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(firstResponse, first)
	second := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	second.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	second.Header.Set("Idempotency-Key", "vehicles-2")
	secondResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(secondResponse, second)
	if firstResponse.Code != http.StatusCreated || secondResponse.Code != http.StatusOK {
		t.Fatalf("statuses = %d, %d", firstResponse.Code, secondResponse.Code)
	}
}

func TestVehicleIdentityResolveRequiresIdempotencyKey(t *testing.T) {
	server := NewServer(staticReadiness{})
	request := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(`{"vehicles":[{"year":1999,"make":"Chevrolet","model":"Silverado 1500"}]}`))
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
}

func TestVehicleIdentityResolveMarksConflictingBaseDimensionsForReview(t *testing.T) {
	server := NewServer(staticReadiness{})
	body := `{"vehicles":[{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"2WD"},{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"4WD"}]}`
	request := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Idempotency-Key", "vehicles-conflict")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	var result VehicleIdentityResolveRecord
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		t.Fatal(err)
	}
	if result.Vehicles[0].Status != "needs_review" {
		t.Fatalf("status = %q, want needs_review", result.Vehicles[0].Status)
	}
}

func TestVehicleIdentityIdempotencyKeyCannotCrossOrganizations(t *testing.T) {
	server := NewServer(staticReadiness{})
	body := `{"vehicles":[{"year":1999,"make":"Chevrolet","model":"Silverado 1500"}]}`
	first := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	first.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	first.Header.Set("Idempotency-Key", "vehicles-cross-org")
	firstResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(firstResponse, first)
	second := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	second.Header.Set("Authorization", "Bearer local:org-2:dataset_viewer")
	second.Header.Set("Idempotency-Key", "vehicles-cross-org")
	secondResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(secondResponse, second)
	if secondResponse.Code != http.StatusConflict {
		t.Fatalf("status = %d, want %d", secondResponse.Code, http.StatusConflict)
	}
}
