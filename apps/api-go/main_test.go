package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeReadiness struct {
	ready bool
}

func (f fakeReadiness) Check() map[string]string {
	if f.ready {
		return map[string]string{"database": "ready", "nats": "ready", "object_storage": "ready"}
	}
	return map[string]string{"database": "unavailable", "nats": "ready", "object_storage": "ready"}
}

func TestHealthEndpointReturnsHealthy(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	res := httptest.NewRecorder()

	NewServer(fakeReadiness{ready: true}).Handler().ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("health status = %d, want %d", res.Code, http.StatusOK)
	}
	if body, _ := io.ReadAll(res.Result().Body); !strings.Contains(string(body), `"status":"ok"`) {
		t.Fatalf("health body = %s, want status ok", body)
	}
}

func TestReadinessEndpointReportsDependencyFailure(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	res := httptest.NewRecorder()

	NewServer(fakeReadiness{ready: false}).Handler().ServeHTTP(res, req)

	if res.Code != http.StatusServiceUnavailable {
		t.Fatalf("readiness status = %d, want %d", res.Code, http.StatusServiceUnavailable)
	}
	if body, _ := io.ReadAll(res.Result().Body); !strings.Contains(string(body), `"database":"unavailable"`) {
		t.Fatalf("readiness body = %s, want database failure", body)
	}
}

func TestMetricsEndpointReportsAccessDenied(t *testing.T) {
	server := NewServer(fakeReadiness{ready: true})

	denied := httptest.NewRecorder()
	server.Handler().ServeHTTP(denied, httptest.NewRequest(http.MethodGet, "/datasets/demo", nil))
	if denied.Code != http.StatusUnauthorized {
		t.Fatalf("denied status = %d, want %d", denied.Code, http.StatusUnauthorized)
	}

	metrics := httptest.NewRecorder()
	server.Handler().ServeHTTP(metrics, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if metrics.Code != http.StatusOK {
		t.Fatalf("metrics status = %d, want %d", metrics.Code, http.StatusOK)
	}
	body, _ := io.ReadAll(metrics.Result().Body)
	if !strings.Contains(string(body), `autodata_api_access_denied_total{reason="unauthenticated"} 1`) {
		t.Fatalf("metrics body = %s, want unauthenticated denial count", body)
	}
}
