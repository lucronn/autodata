package main

import (
	"fmt"
	"net/http"
	"sync/atomic"
)

// apiMetrics is intentionally dependency-free. A production scraper can
// collect this endpoint alongside the durable database metrics exporter.
type apiMetrics struct {
	unauthenticated atomic.Uint64
	forbidden       atomic.Uint64
}

func (m *apiMetrics) recordUnauthenticated() {
	m.unauthenticated.Add(1)
}

func (m *apiMetrics) recordForbidden() {
	m.forbidden.Add(1)
}

func (m *apiMetrics) handler(response http.ResponseWriter, _ *http.Request) {
	response.Header().Set("Content-Type", "text/plain; version=0.0.4")
	response.WriteHeader(http.StatusOK)
	fmt.Fprintf(response, "# TYPE autodata_api_access_denied_total counter\n")
	fmt.Fprintf(response, "autodata_api_access_denied_total{reason=\"unauthenticated\"} %d\n", m.unauthenticated.Load())
	fmt.Fprintf(response, "autodata_api_access_denied_total{reason=\"forbidden\"} %d\n", m.forbidden.Load())
}
