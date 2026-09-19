package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDashboardRouteServesVehicleSelectorWorkspace(t *testing.T) {
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
		"AutoData vehicle workspace",
		"Choose a vehicle",
		"id=\"decade-list\"",
		"id=\"year-list\"",
		"id=\"make-letter-list\"",
		"id=\"make-list\"",
		"id=\"model-step\"",
		"id=\"model-list\"",
		"id=\"configuration-step\"",
		"id=\"configuration-list\"",
		"id=\"choice-row\"",
		"id=\"selected-vehicle\"",
		"id=\"back-button\"",
		"id=\"workspace\"",
		"id=\"chat-log\"",
		"id=\"chat-options\"",
		"id=\"chat-input\"",
		"id=\"worker-terminal\"",
		"id=\"procedure-markdown\"",
		`/dashboard/app.js?v=vehicle-workspace-v2`,
	} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard body does not contain %q", marker)
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
		"renderModels",
		"renderConfigurations",
		"refreshSelectors",
		"configurationLabel",
		"showPane",
		"groupMakesByInitial",
		"decade",
		"year",
		"makeInitial",
		"make",
		"model",
		"configuration",
		"selectedVehicle",
		"goBack",
		"openWorkspace",
		"submitChat",
		"renderVehicleOptions",
		"/selections",
		"awaiting_vehicle",
		"The result is ready below",
		"streamChatEvents",
		"worker-terminal",
		"request_params",
		"procedure.markdown",
	} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard JavaScript does not contain %q", marker)
		}
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
	for _, marker := range []string{".selector-grid", ".choice-row", ".choice-button", ".make-letter", ".workspace", ".chat-panel", ".worker-terminal", "prefers-reduced-motion"} {
		if !strings.Contains(body, marker) {
			t.Fatalf("dashboard CSS does not contain %q", marker)
		}
	}
}
