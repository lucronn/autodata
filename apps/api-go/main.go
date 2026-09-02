package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"time"
)

const dependencyTimeout = 250 * time.Millisecond

// ReadinessChecker is intentionally small so tests can model dependency
// failures without requiring a running local stack.
type ReadinessChecker interface {
	Check() map[string]string
}

type tcpReadiness struct {
	targets map[string]string
	timeout time.Duration
}

func (r tcpReadiness) Check() map[string]string {
	statuses := make(map[string]string, len(r.targets))
	for name, target := range r.targets {
		connection, err := net.DialTimeout("tcp", target, r.timeout)
		if err != nil {
			statuses[name] = "unavailable"
			continue
		}
		_ = connection.Close()
		statuses[name] = "ready"
	}
	return statuses
}

type staticReadiness struct{}

func (staticReadiness) Check() map[string]string {
	return map[string]string{
		"database":       "ready",
		"nats":           "ready",
		"object_storage": "ready",
	}
}

type Server struct {
	readiness ReadinessChecker
}

func NewServer(readiness ReadinessChecker) *Server {
	return &Server{readiness: readiness}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.health)
	mux.HandleFunc("GET /readyz", s.ready)
	return mux
}

func (s *Server) health(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) ready(response http.ResponseWriter, _ *http.Request) {
	dependencies := s.readiness.Check()
	status := http.StatusOK
	for _, dependencyStatus := range dependencies {
		if dependencyStatus != "ready" {
			status = http.StatusServiceUnavailable
			break
		}
	}
	writeJSON(response, status, dependencies)
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	if err := json.NewEncoder(response).Encode(value); err != nil {
		log.Printf("write response: %v", err)
	}
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func configuredReadiness() ReadinessChecker {
	if os.Getenv("AUTODATA_READINESS_MODE") == "static" {
		return staticReadiness{}
	}
	return tcpReadiness{
		targets: map[string]string{
			"database":       envOrDefault("AUTODATA_DB_ADDRESS", "postgres:5432"),
			"nats":           envOrDefault("AUTODATA_NATS_ADDRESS", "nats:4222"),
			"object_storage": envOrDefault("AUTODATA_S3_ADDRESS", "minio:9000"),
		},
		timeout: dependencyTimeout,
	}
}

func main() {
	address := envOrDefault("AUTODATA_API_ADDR", ":8080")
	server := &http.Server{
		Addr:              address,
		Handler:           NewServer(configuredReadiness()).Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("autodata api listening on %s", address)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(fmt.Errorf("serve API: %w", err))
	}
}
