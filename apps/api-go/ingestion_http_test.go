package main

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeIngestionClient struct {
	path           string
	body           []byte
	idempotencyKey string
	status         int
	responseBody   []byte
}

func (f *fakeIngestionClient) Do(_ *http.Request, path string, body []byte, idempotencyKey string) (int, []byte, error) {
	f.path = path
	f.body = append([]byte(nil), body...)
	f.idempotencyKey = idempotencyKey
	return f.status, f.responseBody, nil
}

func TestArticleIntakeAPIRequiresIngestionOperator(t *testing.T) {
	client := &fakeIngestionClient{status: http.StatusOK, responseBody: []byte(`{"status":"ready"}`)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
	request := httptest.NewRequest(http.MethodPost, "/article-intakes", strings.NewReader(`{"source_uri":"https://source.example/42","vehicle":{}}`))
	request.Header.Set("Idempotency-Key", "article-intake-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusForbidden)
	}
}

func TestKnowledgeQueryAPIForwardsVehicleQueryAndIdempotency(t *testing.T) {
	client := &fakeIngestionClient{status: http.StatusOK, responseBody: []byte(`{"status":"cache_hit","results":[]}`)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
	body := []byte(`{"vehicle":{"year":1999,"make":"Chevy","model":"Silverado 1500","region":"US"},"query":"brake caliper"}`)
	request := httptest.NewRequest(http.MethodPost, "/knowledge-queries", bytes.NewReader(body))
	request.Header.Set("Idempotency-Key", "knowledge-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if client.path != "/v1/knowledge-queries" || string(client.body) != string(body) || client.idempotencyKey != "knowledge-1" {
		t.Fatalf("forwarded request = path %q body %q key %q", client.path, client.body, client.idempotencyKey)
	}
	if content, _ := io.ReadAll(response.Body); !strings.Contains(string(content), `"cache_hit"`) {
		t.Fatalf("body = %s, want cache_hit", content)
	}
}

func TestJobPlanAPIForwardsNaturalLanguageRequestAndIdempotency(t *testing.T) {
	client := &fakeIngestionClient{status: http.StatusOK, responseBody: []byte(`{"status":"ready","labor":{"total_labor_hours":4.25}}`)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
	body := []byte(`{"vehicle":{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US"},"query":"replace alternator and starter"}`)
	request := httptest.NewRequest(http.MethodPost, "/job-plans", bytes.NewReader(body))
	request.Header.Set("Idempotency-Key", "job-plan-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if client.path != "/v1/job-plans" || string(client.body) != string(body) || client.idempotencyKey != "job-plan-1" {
		t.Fatalf("forwarded request = path %q body %q key %q", client.path, client.body, client.idempotencyKey)
	}
}

func TestKnowledgeQueryAPIRequiresIdempotencyKey(t *testing.T) {
	client := &fakeIngestionClient{status: http.StatusOK, responseBody: []byte(`{"status":"cache_hit"}`)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
	request := httptest.NewRequest(http.MethodPost, "/knowledge-queries", strings.NewReader(`{"vehicle":{},"query":"brake"}`))
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
}

func TestKnowledgeQueryAPIRejectsTrailingJSON(t *testing.T) {
	client := &fakeIngestionClient{status: http.StatusOK, responseBody: []byte(`{"status":"cache_hit"}`)}
	server := NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
	request := httptest.NewRequest(http.MethodPost, "/knowledge-queries", strings.NewReader(`{"vehicle":{},"query":"brake"}{"unexpected":true}`))
	request.Header.Set("Idempotency-Key", "knowledge-trailing-json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
}
