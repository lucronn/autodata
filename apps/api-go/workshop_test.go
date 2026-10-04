package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWorkshopAssetsAvailableWithoutCatalogCredentials(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, asset := range []struct{ path, contentType string }{
		{"/workshop/", "text/html"},
		{"/workshop/styles.css", "text/css"},
		{"/workshop/app.mjs", "javascript"},
		{"/workshop/catalog.mjs", "javascript"},
		{"/workshop/fonts/InstrumentSans.ttf", "font/ttf"},
	} {
		t.Run(asset.path, func(t *testing.T) {
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, asset.path, nil))
			if response.Code != http.StatusOK || response.Body.Len() == 0 {
				t.Fatalf("asset unavailable: status=%d bytes=%d", response.Code, response.Body.Len())
			}
			if !strings.Contains(response.Header().Get("Content-Type"), asset.contentType) {
				t.Fatalf("wrong MIME type: %s", response.Header().Get("Content-Type"))
			}
		})
	}
	for _, path := range []string{"/workshop/missing-file.js", "/workshop/missing-page"} {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, path, nil))
		if response.Code != http.StatusNotFound {
			t.Fatalf("missing asset %s returned %d", path, response.Code)
		}
	}
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/", nil))
	for _, marker := range []string{"source-review", "source-review-frame", "View stored source", "Load beside article"} {
		if !strings.Contains(response.Body.String(), marker) {
			t.Fatalf("workshop HTML is missing source review marker %q", marker)
		}
	}
}

func TestWorkshopRedirectPreservesSeparateEntryPoint(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop", nil))
	if response.Code != http.StatusMovedPermanently || response.Header().Get("Location") != "/workshop/" {
		t.Fatalf("unexpected redirect: %d %s", response.Code, response.Header().Get("Location"))
	}
}
