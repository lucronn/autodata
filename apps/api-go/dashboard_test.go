package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDashboardRouteServesMinimalVehicleSelector(t *testing.T) {
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
	for _, marker := range []string{
		"AutoData vehicle selector",
		"Choose a vehicle",
		"id=\"decade-list\"",
		"id=\"year-list\"",
		"id=\"make-letter-list\"",
		"id=\"make-list\"",
		"id=\"selected-vehicle\"",
		`/dashboard/app.js?v=vehicle-selector-v1`,
	} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard body does not contain %q", marker)
		}
	}
	for _, forbidden := range []string{
		`id="chat-log"`,
		`id="worker-terminal"`,
		`id="procedure-steps"`,
		`id="detail-toggle"`,
		"<textarea",
		"<select",
	} {
		if strings.Contains(body, forbidden) {
			t.Fatalf("minimal dashboard still contains %q", forbidden)
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

func TestDashboardRouteServesSelectorJavaScript(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/dashboard/app.js", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	body := response.Body.String()
	for _, marker := range []string{
		`fetch("/vehicle-identities/selectors"`,
		"renderDecades",
		"renderYears",
		"renderMakeLetters",
		"renderMakes",
		"groupMakesByInitial",
		`data-decade`,
		`data-year`,
		`data-make-initial`,
		`data-make`,
		"selectedVehicle",
	} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard JavaScript does not contain %q", marker)
		}
	}
	if strings.Contains(body, "/chat/queries") {
		t.Fatal("minimal selector dashboard must not initialize the chatbot flow")
	}
}

func TestDashboardRouteServesSelectorStyles(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	request := httptest.NewRequest(http.MethodGet, "/dashboard/styles.css", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	body := response.Body.String()
	for _, marker := range []string{".selector-grid", ".choice-button", ".make-letter", "prefers-reduced-motion"} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard CSS does not contain %q", marker)
		}
	}
}
