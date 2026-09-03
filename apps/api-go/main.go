package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
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
	readiness   ReadinessChecker
	auth        Authenticator
	requests    RequestStore
	projections ProjectionStore
}

func NewServer(readiness ReadinessChecker) *Server {
	return NewServerWithDependencies(readiness, HeaderAuthenticator{}, newMemoryRequestStore())
}

func NewServerWithDependencies(readiness ReadinessChecker, auth Authenticator, requests RequestStore, projections ...ProjectionStore) *Server {
	projectionStore := ProjectionStore(newMemoryProjectionStore())
	if len(projections) > 0 && projections[0] != nil {
		projectionStore = projections[0]
	}
	return &Server{readiness: readiness, auth: auth, requests: requests, projections: projectionStore}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.health)
	mux.HandleFunc("GET /readyz", s.ready)
	mux.Handle("POST /dataset-requests", s.requireRole("dataset_viewer", s.createDatasetRequest))
	mux.Handle("GET /dataset-requests/{id}", s.requireRole("dataset_viewer", s.getDatasetRequest))
	mux.Handle("GET /datasets/{id}", s.requireRole("dataset_viewer", s.getDataset))
	mux.Handle("GET /datasets/{id}/sections", s.requireRole("dataset_viewer", s.getDatasetSections))
	mux.Handle("GET /datasets/{id}/revisions", s.requireRole("dataset_viewer", s.getDatasetRevisions))
	mux.Handle("GET /datasets/{id}/evidence/{evidence_id}", s.requireRole("dataset_viewer", s.getDatasetEvidence))
	mux.Handle("GET /datasets/{id}/search", s.requireRole("dataset_viewer", s.searchEvidence))
	mux.Handle("POST /datasets/{id}/feedback", s.requireRole("dataset_viewer", s.submitFeedback))
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

func (s *Server) getDataset(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	record, err := s.projections.GetDataset(datasetID, principal, strings.TrimSpace(request.URL.Query().Get("revision_id")))
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func (s *Server) getDatasetSections(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	record, err := s.projections.ListSections(datasetID, principal)
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func (s *Server) getDatasetRevisions(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	revisions, err := s.projections.ListRevisions(datasetID, principal)
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, revisions)
}

func (s *Server) getDatasetEvidence(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	evidenceID := strings.TrimSpace(request.PathValue("evidence_id"))
	if evidenceID == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "evidence ID is required", false)
		return
	}
	evidence, err := s.projections.GetEvidence(datasetID, evidenceID, principal)
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, evidence)
}

func (s *Server) searchEvidence(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	query := strings.TrimSpace(request.URL.Query().Get("q"))
	if query == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "search query is required", false)
		return
	}
	limit := 10
	if rawLimit := strings.TrimSpace(request.URL.Query().Get("limit")); rawLimit != "" {
		parsed, err := strconv.Atoi(rawLimit)
		if err != nil || parsed < 1 || parsed > 50 {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "limit must be between 1 and 50", false)
			return
		}
		limit = parsed
	}
	vector, err := deterministicQueryEmbedding(query)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	result, err := s.projections.SearchEvidence(datasetID, vector, limit, principal)
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, result)
}

func (s *Server) submitFeedback(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	var input FeedbackInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "feedback body is invalid", false)
		return
	}
	record, err := s.projections.SubmitFeedback(datasetID, input, principal)
	if !writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusCreated, record)
}

func datasetPathValue(request *http.Request) (string, bool) {
	value := strings.TrimSpace(request.PathValue("id"))
	return value, value != ""
}

func writeProjectionError(response http.ResponseWriter, request *http.Request, err error) bool {
	if err == nil {
		return true
	}
	switch {
	case errors.Is(err, ErrEntitlementRequired):
		writeAPIError(response, request, http.StatusForbidden, "ENTITLEMENT_REQUIRED", err.Error(), false)
	case errors.Is(err, ErrEntitlementRevoked):
		writeAPIError(response, request, http.StatusGone, "ENTITLEMENT_REVOKED", err.Error(), false)
	case errors.Is(err, ErrDatasetNotViewable):
		writeAPIError(response, request, http.StatusConflict, "DATASET_NOT_VIEWABLE", err.Error(), true)
	case errors.Is(err, ErrRevisionNotFound), errors.Is(err, ErrDatasetNotFound):
		writeAPIError(response, request, http.StatusNotFound, "REVISION_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrInvalidEvidence):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_EVIDENCE", err.Error(), false)
	case errors.Is(err, ErrInvalidFeedback):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	case errors.Is(err, ErrReviewRequired):
		writeAPIError(response, request, http.StatusConflict, "REVIEW_REQUIRED", err.Error(), true)
	default:
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "dataset could not be read", true)
	}
	return false
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
	projectionStore := ProjectionStore(newMemoryProjectionStore())
	if os.Getenv("AUTODATA_PROJECTION_STORE") == "postgres" {
		store, err := newPostgresProjectionStore(context.Background())
		if err != nil {
			log.Fatal(fmt.Errorf("connect projection store: %w", err))
		}
		defer store.Close()
		projectionStore = store
	}
	server := &http.Server{
		Addr:              address,
		Handler:           NewServerWithDependencies(configuredReadiness(), HeaderAuthenticator{}, newMemoryRequestStore(), projectionStore).Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("autodata api listening on %s", address)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(fmt.Errorf("serve API: %w", err))
	}
}
