package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDashboardServesCatalogLandingWithoutChatUI(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/dashboard/", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if response.Header().Get("Cache-Control") != "no-cache" {
		t.Fatalf("cache control = %q, want no-cache", response.Header().Get("Cache-Control"))
	}
	body := response.Body.String()
	for _, marker := range []string{"AutoData / Catalog service", `href="/workshop/"`, `href="/swagger/"`, `href="/v1/catalog/years"`} {
		if !strings.Contains(body, marker) {
			t.Fatalf("catalog landing does not contain %q", marker)
		}
	}
	for _, forbidden := range []string{"chat-log", "/chat/queries", "textarea", "Ask AutoData"} {
		if strings.Contains(body, forbidden) {
			t.Fatalf("catalog landing still contains chatbot marker %q", forbidden)
		}
	}
}

func TestSwaggerAndOpenAPIRoutesAreAvailableWithoutChatPaths(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, testCase := range []struct {
		path        string
		contentType string
		marker      string
	}{
		{"/swagger/", "text/html; charset=utf-8", "/openapi.json"},
		{"/openapi.json", "application/json; charset=utf-8", "listCatalogMakes"},
		{"/openapi.yaml", "application/yaml; charset=utf-8", "listCatalogModels"},
		{"/swagger/swagger-ui.css", "", ".swagger-ui"},
	} {
		request := httptest.NewRequest(http.MethodGet, testCase.path, nil)
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, request)
		if response.Code != http.StatusOK {
			t.Fatalf("GET %s status = %d, want %d", testCase.path, response.Code, http.StatusOK)
		}
		if testCase.contentType != "" && response.Header().Get("Content-Type") != testCase.contentType {
			t.Errorf("GET %s content type = %q, want %q", testCase.path, response.Header().Get("Content-Type"), testCase.contentType)
		}
		if !strings.Contains(response.Body.String(), testCase.marker) {
			t.Errorf("GET %s body does not contain %q", testCase.path, testCase.marker)
		}
		if strings.Contains(response.Body.String(), "/chat/queries") {
			t.Errorf("GET %s exposes a retired chat route", testCase.path)
		}
	}
}

func TestDashboardRouteRedirectsMissingTrailingSlash(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/dashboard", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusMovedPermanently {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusMovedPermanently)
	}
	if location := response.Header().Get("Location"); location != "/dashboard/" {
		t.Fatalf("location = %q, want /dashboard/", location)
	}
}

func TestChatDashboardAssetsAreRemoved(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, path := range []string{"/dashboard/app.js", "/dashboard/styles.css"} {
		request := httptest.NewRequest(http.MethodGet, path, nil)
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, request)
		if response.Code != http.StatusNotFound {
			t.Errorf("GET %s status = %d, want %d", path, response.Code, http.StatusNotFound)
		}
	}
}
