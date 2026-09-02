package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
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
	auth      Authenticator
	requests  RequestStore
}

func NewServer(readiness ReadinessChecker) *Server {
	return NewServerWithDependencies(readiness, HeaderAuthenticator{}, newMemoryRequestStore())
}

func NewServerWithDependencies(readiness ReadinessChecker, auth Authenticator, requests RequestStore) *Server {
	return &Server{readiness: readiness, auth: auth, requests: requests}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.health)
	mux.HandleFunc("GET /readyz", s.ready)
	mux.Handle("POST /dataset-requests", s.requireRole("dataset_viewer", s.createDatasetRequest))
	mux.Handle("GET /dataset-requests/{id}", s.requireRole("dataset_viewer", s.getDatasetRequest))
	return mux
}

type authenticatedHandler func(http.ResponseWriter, *http.Request, Principal)

func (s *Server) requireRole(role string, next authenticatedHandler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		principal, err := s.auth.Authenticate(request)
		if err != nil {
			writeAPIError(response, request, http.StatusUnauthorized, "UNAUTHENTICATED", err.Error(), false)
			return
		}
		if !principal.HasRole(role) {
			writeAPIError(response, request, http.StatusForbidden, "FORBIDDEN", "the caller lacks the required role", false)
			return
		}
		next(response, request, principal)
	})
}

func (s *Server) createDatasetRequest(response http.ResponseWriter, request *http.Request, principal Principal) {
	if request.Header.Get("Idempotency-Key") == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	var input DatasetRequestInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil || input.ProductID == "" || input.VehicleKey == "" || input.Region == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "product_id, vehicle_key, and region are required", false)
		return
	}
	record, duplicate, err := s.requests.Create(principal, input, request.Header.Get("Idempotency-Key"))
	if errors.Is(err, ErrEntitlementRequired) {
		writeAPIError(response, request, http.StatusForbidden, "ENTITLEMENT_REQUIRED", err.Error(), false)
		return
	}
	if err != nil {
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "request could not be created", true)
		return
	}
	status := http.StatusAccepted
	if duplicate {
		status = http.StatusOK
	}
	writeJSON(response, status, record)
}

func (s *Server) getDatasetRequest(response http.ResponseWriter, request *http.Request, principal Principal) {
	id := strings.TrimSpace(request.PathValue("id"))
	if id == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset request ID is required", false)
		return
	}
	record, err := s.requests.Get(id, principal)
	if errors.Is(err, ErrRequestNotFound) {
		writeAPIError(response, request, http.StatusNotFound, "REVISION_NOT_FOUND", "dataset request was not found", false)
		return
	}
	if errors.Is(err, ErrEntitlementRequired) {
		writeAPIError(response, request, http.StatusForbidden, "ENTITLEMENT_REQUIRED", err.Error(), false)
		return
	}
	if err != nil {
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "request could not be read", true)
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func writeAPIError(response http.ResponseWriter, request *http.Request, status int, code, message string, retryable bool) {
	requestID := request.Header.Get("X-Request-ID")
	if requestID == "" {
		requestID = "request-unassigned"
	}
	writeJSON(response, status, map[string]any{
		"error": map[string]any{
			"code":       code,
			"message":    message,
			"request_id": requestID,
			"retryable":  retryable,
			"details":    map[string]any{},
		},
	})
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
