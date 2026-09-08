package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPostgresSelectorsSelectDurableVehicleAndConfigurationIDs(t *testing.T) {
	root, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	querySource, err := os.ReadFile(filepath.Join(root, "postgres_vehicle_identity.go"))
	if err != nil {
		t.Fatal(err)
	}
	query := string(querySource)
	for _, selectedID := range []string{
		"vib.vehicle_id::text",
		"vc.vehicle_configuration_id::text",
	} {
		if !strings.Contains(query, selectedID) {
			t.Fatalf("durable selector query does not select %s", selectedID)
		}
	}

	engine := 5.3
	records, _, err := normalizeVehicleIdentityRows([]VehicleIdentityRow{
		{
			Year: 1999, Make: "Chevrolet", Model: "Silverado 1500", Region: "US",
			Drivetrain: "2WD", EngineDisplacementL: &engine,
			vehicleID: "vehicle-1", vehicleConfigurationID: "configuration-1",
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if records[0].VehicleID != "vehicle-1" {
		t.Fatalf("vehicle ID = %q, want vehicle-1", records[0].VehicleID)
	}
	if records[0].Configurations[0].VehicleConfigurationID != "configuration-1" {
		t.Fatalf("configuration ID = %q, want configuration-1", records[0].Configurations[0].VehicleConfigurationID)
	}
}

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

func TestVehicleIdentitySelectorsIncludeEngineAndTrimValues(t *testing.T) {
	server := NewServer(staticReadiness{})
	body := `{"vehicles":[{"year":1999,"make":"Chevy","model":"Silverado 1500","region":"US","trim":"LT","engine_displacement_l":5.3}]}`
	request := httptest.NewRequest(http.MethodPost, "/vehicle-identities/resolve", strings.NewReader(body))
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Idempotency-Key", "selectors-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusCreated {
		t.Fatalf("resolve status = %d, want %d", response.Code, http.StatusCreated)
	}

	selectorsRequest := httptest.NewRequest(http.MethodGet, "/vehicle-identities/selectors", nil)
	selectorsRequest.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	selectorsResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(selectorsResponse, selectorsRequest)
	if selectorsResponse.Code != http.StatusOK {
		t.Fatalf("selector status = %d, want %d", selectorsResponse.Code, http.StatusOK)
	}
	var selectors VehicleIdentitySelectors
	if err := json.NewDecoder(selectorsResponse.Body).Decode(&selectors); err != nil {
		t.Fatal(err)
	}
	if len(selectors.Trims) != 1 || selectors.Trims[0] != "LT" {
		t.Fatalf("trims = %#v", selectors.Trims)
	}
	if len(selectors.EngineDisplacementsL) != 1 || selectors.EngineDisplacementsL[0] != 5.3 {
		t.Fatalf("engines = %#v", selectors.EngineDisplacementsL)
	}
	if len(selectors.Vehicles) != 1 || len(selectors.Vehicles[0].Configurations) != 1 {
		t.Fatalf("structured vehicles = %#v", selectors.Vehicles)
	}
	if selectors.Vehicles[0].Configurations[0].ConfigurationKey != "chevrolet-silverado-1500-1999-us-trim-lt-engine-5-3l" {
		t.Fatalf("configuration = %#v", selectors.Vehicles[0].Configurations)
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

func TestVehicleIdentityResolveRejectsClientSuppliedDurableIDs(t *testing.T) {
	server := NewServer(staticReadiness{})
	request := httptest.NewRequest(
		http.MethodPost,
		"/vehicle-identities/resolve",
		strings.NewReader(`{"vehicles":[{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","vehicle_id":"forged"}]}`),
	)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Idempotency-Key", "reject-forged-id")
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
	if result.Status != "needs_review" {
		t.Fatalf("overall status = %q, want needs_review", result.Status)
	}
	if result.Vehicles[0].Status != "needs_review" {
		t.Fatalf("status = %q, want needs_review", result.Vehicles[0].Status)
	}
	if len(result.Vehicles[0].Configurations) != 1 {
		t.Fatalf("configurations = %d, want only the non-conflicting configuration", len(result.Vehicles[0].Configurations))
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
