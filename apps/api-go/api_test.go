package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeAuthenticator struct {
	principal Principal
	err       error
}

func (f *fakeAuthenticator) Authenticate(_ *http.Request) (Principal, error) {
	return f.principal, f.err
}

func TestCreateDatasetRequestRequiresAuthentication(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodPost, "/dataset-requests", strings.NewReader(`{"product_id":"product-1","vehicle_key":"toyota-corolla-2024","region":"US"}`))
	request.Header.Set("Idempotency-Key", "request-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
	assertErrorCode(t, response, "UNAUTHENTICATED")
}

func TestHandlerAssignsRequestIDToResponseAndError(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/datasets/dataset-1", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	requestID := response.Header().Get("X-Request-ID")
	if requestID == "" || requestID == "request-unassigned" {
		t.Fatalf("X-Request-ID = %q, want generated request ID", requestID)
	}
	var body map[string]any
	decodeJSON(t, response, &body)
	errorBody := body["error"].(map[string]any)
	if errorBody["request_id"] != requestID {
		t.Fatalf("error request_id = %#v, want %q", errorBody["request_id"], requestID)
	}
}

func TestHandlerPreservesCallerRequestID(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/datasets/dataset-1", nil)
	request.Header.Set("X-Request-ID", "client-request-42")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if got := response.Header().Get("X-Request-ID"); got != "client-request-42" {
		t.Fatalf("X-Request-ID = %q, want caller value", got)
	}
}

func TestHandlerForwardsValidTraceparentForCrossServiceCorrelation(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/datasets/dataset-1", nil)
	request.Header.Set("traceparent", "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if got := response.Header().Get("traceparent"); got != request.Header.Get("traceparent") {
		t.Fatalf("traceparent = %q, want valid caller value", got)
	}
}

func TestCreateDatasetRequestReturnsNotYetViewableStatus(t *testing.T) {
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	server := NewServerWithDependencies(staticReadiness{}, auth, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodPost, "/dataset-requests", strings.NewReader(`{"product_id":"product-1","vehicle_key":"toyota-corolla-2024","region":"US"}`))
	request.Header.Set("Idempotency-Key", "request-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusAccepted)
	}
	var body map[string]any
	decodeJSON(t, response, &body)
	if body["status"] != "fast_lane_processing" {
		t.Fatalf("status body = %#v, want fast_lane_processing", body["status"])
	}
	if len(body["sections"].([]any)) == 0 {
		t.Fatal("expected section readiness in request response")
	}
}

func TestDuplicateDatasetRequestReturnsTheOriginalRequest(t *testing.T) {
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	server := NewServerWithDependencies(staticReadiness{}, auth, newMemoryRequestStore())
	first := newDatasetRequest(t, server, "request-1")
	second := newDatasetRequest(t, server, "request-1")

	if first.Code != http.StatusAccepted || second.Code != http.StatusOK {
		t.Fatalf("duplicate statuses = %d, %d, want %d, %d", first.Code, second.Code, http.StatusAccepted, http.StatusOK)
	}
	var firstBody, secondBody map[string]any
	decodeJSON(t, first, &firstBody)
	decodeJSON(t, second, &secondBody)
	if firstBody["dataset_request_id"] != secondBody["dataset_request_id"] {
		t.Fatalf("request IDs differ: %#v vs %#v", firstBody["dataset_request_id"], secondBody["dataset_request_id"])
	}
}

func TestGetDatasetRequestRejectsAnotherOrganization(t *testing.T) {
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	server := NewServerWithDependencies(staticReadiness{}, auth, newMemoryRequestStore())
	created := newDatasetRequest(t, server, "request-1")
	var createdBody map[string]any
	decodeJSON(t, created, &createdBody)
	auth.principal.OrganizationID = "org-2"
	request := httptest.NewRequest(http.MethodGet, "/dataset-requests/"+createdBody["dataset_request_id"].(string), nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusForbidden)
	}
	assertErrorCode(t, response, "ENTITLEMENT_REQUIRED")
}

func TestCreateDatasetRequestRejectsMissingIdempotencyKey(t *testing.T) {
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	server := NewServerWithDependencies(staticReadiness{}, auth, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodPost, "/dataset-requests", strings.NewReader(`{"product_id":"product-1","vehicle_key":"toyota-corolla-2024","region":"US"}`))
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
	assertErrorCode(t, response, "INVALID_REQUEST")
}

func newDatasetRequest(t *testing.T, server *Server, idempotencyKey string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodPost, "/dataset-requests", strings.NewReader(`{"product_id":"product-1","vehicle_key":"toyota-corolla-2024","region":"US"}`))
	request.Header.Set("Idempotency-Key", idempotencyKey)
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	return response
}

func decodeJSON(t *testing.T, response *httptest.ResponseRecorder, target any) {
	t.Helper()
	data, err := io.ReadAll(response.Result().Body)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		t.Fatalf("decode %s: %v", data, err)
	}
}

func assertErrorCode(t *testing.T, response *httptest.ResponseRecorder, want string) {
	t.Helper()
	var body struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	decodeJSON(t, response, &body)
	if body.Error.Code != want {
		t.Fatalf("error code = %q, want %q", body.Error.Code, want)
	}
}

func TestCustomerAuthOpenAPIHasExplicitCookieAndCSRFContract(t *testing.T) {
	body, err := dashboardFiles.ReadFile("openapi.json")
	if err != nil {
		t.Fatal(err)
	}
	var spec struct {
		Paths      map[string]map[string]json.RawMessage `json:"paths"`
		Components struct {
			SecuritySchemes map[string]struct{ Type, In, Name string } `json:"securitySchemes"`
		} `json:"components"`
	}
	if err := json.Unmarshal(body, &spec); err != nil {
		t.Fatal(err)
	}
	cookie := spec.Components.SecuritySchemes["customerSession"]
	if cookie.Type != "apiKey" || cookie.In != "cookie" || cookie.Name != customerSessionName {
		t.Fatal("missing opaque cookie scheme")
	}
	for path, method := range map[string]string{"/auth/config": "get", "/auth/session": "get", "/auth/firebase/session": "post", "/auth/logout": "post"} {
		var operation struct {
			Security  []map[string][]string      `json:"security"`
			Responses map[string]json.RawMessage `json:"responses"`
		}
		if err := json.Unmarshal(spec.Paths[path][method], &operation); err != nil {
			t.Fatalf("missing %s %s: %v", method, path, err)
		}
		if path == "/auth/config" || path == "/auth/firebase/session" {
			if len(operation.Security) != 0 {
				t.Fatal("public route requires session", path)
			}
		} else if len(operation.Security) != 1 || operation.Security[0]["customerSession"] == nil {
			t.Fatal("session route lacks cookie security", path)
		}
		if len(operation.Responses) == 0 {
			t.Fatal("missing responses", path)
		}
	}
	for _, text := range []string{"X-Autodata-Session-Exchange", "X-CSRF-Token", "auth_time", "no-store", "12 hours"} {
		if !strings.Contains(string(body), text) {
			t.Fatal("missing auth contract", text)
		}
	}
}
