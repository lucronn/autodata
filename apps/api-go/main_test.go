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
