package main

import (
	"context"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// dashboardFiles contains the small local developer dashboard. It is served
// by the API so the browser uses the same origin and authentication boundary.
//
//go:embed dashboard/*
var dashboardFiles embed.FS

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
	readiness                  ReadinessChecker
	auth                       Authenticator
	requests                   RequestStore
	projections                ProjectionStore
	knowledgeFallbackPublisher KnowledgeFallbackPublisher
	sourceReviews              SourceReviewStore
	ingestionClient            IngestionClient
	vehicleIdentity            VehicleIdentityStore
	metrics                    *apiMetrics
}

func NewServer(readiness ReadinessChecker) *Server {
	return NewServerWithDependencies(readiness, HeaderAuthenticator{}, newMemoryRequestStore())
}

func NewServerWithDependencies(readiness ReadinessChecker, auth Authenticator, requests RequestStore, projections ...ProjectionStore) *Server {
	return NewServerWithDependenciesAndPublisher(readiness, auth, requests, newMemoryKnowledgeFallbackPublisher(), projections...)
}

func NewServerWithDependenciesAndPublisher(readiness ReadinessChecker, auth Authenticator, requests RequestStore, publisher KnowledgeFallbackPublisher, projections ...ProjectionStore) *Server {
	projectionStore := ProjectionStore(newMemoryProjectionStore())
	if len(projections) > 0 && projections[0] != nil {
		projectionStore = projections[0]
	}
	if publisher == nil {
		publisher = newMemoryKnowledgeFallbackPublisher()
	}
	return &Server{
		readiness:                  readiness,
		auth:                       auth,
		requests:                   requests,
		projections:                projectionStore,
		knowledgeFallbackPublisher: publisher,
		sourceReviews:              newMemorySourceReviewStore(),
		vehicleIdentity:            newMemoryVehicleIdentityStore(),
		metrics:                    new(apiMetrics),
	}
}

// NewServerWithVehicleIdentityStore injects the canonical identity persistence
// boundary without coupling handlers to PostgreSQL or Python workers.
func NewServerWithVehicleIdentityStore(readiness ReadinessChecker, auth Authenticator, requests RequestStore, identity VehicleIdentityStore, projections ...ProjectionStore) *Server {
	server := NewServerWithDependencies(readiness, auth, requests, projections...)
	if identity != nil {
		server.vehicleIdentity = identity
	}
	return server
}

// NewServerWithSourceReviewStore injects the operator review queue without
// coupling handlers to PostgreSQL or a particular review UI.
func NewServerWithSourceReviewStore(readiness ReadinessChecker, auth Authenticator, requests RequestStore, reviews SourceReviewStore, projections ...ProjectionStore) *Server {
	server := NewServerWithDependencies(readiness, auth, requests, projections...)
	if reviews != nil {
		server.sourceReviews = reviews
	}
	return server
}

// NewServerWithIngestionClient injects the internal worker boundary for API
// tests and local adapters without coupling handlers to a transport.
func NewServerWithIngestionClient(readiness ReadinessChecker, auth Authenticator, requests RequestStore, client IngestionClient, projections ...ProjectionStore) *Server {
	server := NewServerWithDependencies(readiness, auth, requests, projections...)
	server.ingestionClient = client
	return server
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /dashboard", func(response http.ResponseWriter, request *http.Request) {
		http.Redirect(response, request, "/dashboard/", http.StatusMovedPermanently)
	})
	mux.HandleFunc("GET /dashboard/", func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Path == "/dashboard/" {
			body, err := dashboardFiles.ReadFile("dashboard/index.html")
			if err != nil {
				http.Error(response, "dashboard unavailable", http.StatusInternalServerError)
				return
			}
			response.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = response.Write(body)
			return
		}
		assets, err := fs.Sub(dashboardFiles, "dashboard")
		if err != nil {
			http.Error(response, "dashboard unavailable", http.StatusInternalServerError)
			return
		}
		http.StripPrefix("/dashboard/", http.FileServer(http.FS(assets))).ServeHTTP(response, request)
	})
	mux.HandleFunc("GET /healthz", s.health)
	mux.HandleFunc("GET /readyz", s.ready)
	mux.HandleFunc("GET /metrics", s.metrics.handler)
	mux.Handle("POST /dataset-requests", s.requireRole("dataset_viewer", s.createDatasetRequest))
	mux.Handle("POST /vehicle-identities/resolve", s.requireRole("dataset_viewer", s.resolveVehicleIdentity))
	mux.Handle("GET /vehicle-identities/selectors", s.requireRole("dataset_viewer", s.listVehicleIdentitySelectors))
	mux.Handle("GET /source-review-items", s.requireRole("data_reviewer", s.listSourceReviewItems))
	mux.Handle("POST /source-review-items/{id}/review", s.requireRole("data_reviewer", s.reviewSourceItem))
	mux.Handle("POST /article-intakes", s.requireRole("ingestion_operator", s.createArticleIntake))
	mux.Handle("POST /knowledge-queries", s.requireRole("dataset_viewer", s.createKnowledgeQuery))
	mux.Handle("POST /job-plans", s.requireRole("dataset_viewer", s.createJobPlan))
	mux.Handle("GET /dataset-requests/{id}", s.requireRole("dataset_viewer", s.getDatasetRequest))
	mux.Handle("GET /datasets/{id}", s.requireRole("dataset_viewer", s.getDataset))
	mux.Handle("GET /datasets/{id}/sections", s.requireRole("dataset_viewer", s.getDatasetSections))
	mux.Handle("GET /datasets/{id}/revisions", s.requireRole("dataset_viewer", s.getDatasetRevisions))
	mux.Handle("GET /datasets/{id}/evidence/{evidence_id}", s.requireRole("dataset_viewer", s.getDatasetEvidence))
	mux.Handle("GET /datasets/{id}/search", s.requireRole("dataset_viewer", s.searchEvidence))
	mux.Handle("GET /datasets/{id}/knowledge", s.requireRole("dataset_viewer", s.searchKnowledge))
	mux.Handle("POST /datasets/{id}/feedback", s.requireRole("dataset_viewer", s.submitFeedback))
	mux.Handle("POST /datasets/{id}/feedback/{feedback_id}/review", s.requireRole("data_reviewer", s.reviewFeedback))
	mux.Handle("POST /datasets/{id}/evidence/{evidence_id}/review", s.requireRole("data_reviewer", s.reviewEvidence))
	return withRequestObservability(mux)
}

type authenticatedHandler func(http.ResponseWriter, *http.Request, Principal)

func (s *Server) requireRole(role string, next authenticatedHandler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		principal, err := s.auth.Authenticate(request)
		if err != nil {
			s.metrics.recordUnauthenticated()
			writeAPIError(response, request, http.StatusUnauthorized, "UNAUTHENTICATED", err.Error(), false)
			return
		}
		if !principal.HasRole(role) {
			s.metrics.recordForbidden()
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
	if errors.Is(err, ErrInvalidRequest) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if err != nil {
		log.Printf("create dataset request %s: %v", requestIDFrom(request), err)
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
	if errors.Is(err, ErrInvalidRequest) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if errors.Is(err, ErrRequestNotFound) {
		writeAPIError(response, request, http.StatusNotFound, "REVISION_NOT_FOUND", "dataset request was not found", false)
		return
	}
	if errors.Is(err, ErrEntitlementRequired) {
		writeAPIError(response, request, http.StatusForbidden, "ENTITLEMENT_REQUIRED", err.Error(), false)
		return
	}
	if err != nil {
		log.Printf("read dataset request %s: %v", requestIDFrom(request), err)
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
	if !s.writeProjectionError(response, request, err) {
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
	if !s.writeProjectionError(response, request, err) {
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
	if !s.writeProjectionError(response, request, err) {
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
	if !s.writeProjectionError(response, request, err) {
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
	if !s.writeProjectionError(response, request, err) {
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
	if !s.writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusCreated, record)
}

func (s *Server) reviewEvidence(response http.ResponseWriter, request *http.Request, principal Principal) {
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
	var input EvidenceReviewInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "review body is invalid", false)
		return
	}
	evidence, err := s.projections.ReviewEvidence(datasetID, evidenceID, input, principal)
	if !s.writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, evidence)
}

func (s *Server) reviewFeedback(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	feedbackID := strings.TrimSpace(request.PathValue("feedback_id"))
	if feedbackID == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "feedback ID is required", false)
		return
	}
	var input FeedbackReviewInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "feedback review body is invalid", false)
		return
	}
	record, err := s.projections.ReviewFeedback(datasetID, feedbackID, input, principal)
	if !s.writeProjectionError(response, request, err) {
		return
	}
	writeJSON(response, http.StatusOK, record)
}

func datasetPathValue(request *http.Request) (string, bool) {
	value := strings.TrimSpace(request.PathValue("id"))
	return value, value != ""
}

func (s *Server) writeProjectionError(response http.ResponseWriter, request *http.Request, err error) bool {
	if err == nil {
		return true
	}
	switch {
	case errors.Is(err, ErrEntitlementRequired):
		s.metrics.recordForbidden()
		writeAPIError(response, request, http.StatusForbidden, "ENTITLEMENT_REQUIRED", err.Error(), false)
	case errors.Is(err, ErrEntitlementRevoked):
		s.metrics.recordForbidden()
		writeAPIError(response, request, http.StatusGone, "ENTITLEMENT_REVOKED", err.Error(), false)
	case errors.Is(err, ErrDatasetNotViewable):
		writeAPIError(response, request, http.StatusConflict, "DATASET_NOT_VIEWABLE", err.Error(), true)
	case errors.Is(err, ErrRevisionNotFound), errors.Is(err, ErrDatasetNotFound):
		writeAPIError(response, request, http.StatusNotFound, "REVISION_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrInvalidEvidence):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_EVIDENCE", err.Error(), false)
	case errors.Is(err, ErrInvalidFeedback):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	case errors.Is(err, ErrInvalidReview):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	case errors.Is(err, ErrReviewConflict):
		writeAPIError(response, request, http.StatusConflict, "REVIEW_REQUIRED", err.Error(), false)
	case errors.Is(err, ErrInvalidFeedbackReview):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	case errors.Is(err, ErrFeedbackConflict):
		writeAPIError(response, request, http.StatusConflict, "FEEDBACK_CONFLICT", err.Error(), false)
	case errors.Is(err, ErrFeedbackNotFound):
		writeAPIError(response, request, http.StatusNotFound, "FEEDBACK_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrReviewRequired):
		writeAPIError(response, request, http.StatusConflict, "REVIEW_REQUIRED", err.Error(), true)
	default:
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "dataset could not be read", true)
	}
	return false
}

func writeAPIError(response http.ResponseWriter, request *http.Request, status int, code, message string, retryable bool) {
	requestID := requestIDFrom(request)
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
	requestStore, projectionStore, cleanup, err := configuredStores(context.Background())
	if err != nil {
		log.Fatal(fmt.Errorf("configure API stores: %w", err))
	}
	defer cleanup()
	publisher, err := configuredKnowledgeFallbackPublisher(projectionStore)
	if err != nil {
		log.Fatal(fmt.Errorf("configure knowledge fallback publisher: %w", err))
	}
	application := NewServerWithDependenciesAndPublisher(configuredReadiness(), HeaderAuthenticator{}, requestStore, publisher, projectionStore)
	if durableProjections, ok := projectionStore.(*postgresProjectionStore); ok {
		application.vehicleIdentity = newLayeredVehicleIdentityStore(durableProjections.pool)
		application.sourceReviews = newPostgresSourceReviewStore(durableProjections.pool)
	}
	if endpoint := strings.TrimSpace(os.Getenv("AUTODATA_INGESTION_URL")); endpoint != "" {
		client, err := NewHTTPIngestionClient(
			endpoint,
			os.Getenv("AUTODATA_INGESTION_INTERNAL_TOKEN"),
			envDurationSeconds("AUTODATA_INGESTION_TIMEOUT_SECONDS", 30),
		)
		if err != nil {
			log.Fatal(fmt.Errorf("configure ingestion client: %w", err))
		}
		application.ingestionClient = client
	}
	server := &http.Server{
		Addr:              address,
		Handler:           application.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("autodata api listening on %s", address)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(fmt.Errorf("serve API: %w", err))
	}
}

var configuredProjectionStoreOpener = newPostgresProjectionStore

func configuredStores(ctx context.Context) (RequestStore, ProjectionStore, func(), error) {
	requestStore := RequestStore(newMemoryRequestStore())
	projectionStore := ProjectionStore(newMemoryProjectionStore())
	if os.Getenv("AUTODATA_PROJECTION_STORE") != "postgres" {
		return requestStore, projectionStore, func() {}, nil
	}
	store, err := configuredProjectionStoreOpener(ctx)
	if err != nil {
		return nil, nil, func() {}, err
	}
	return newPostgresRequestStore(store.pool), store, store.Close, nil
}

func configuredKnowledgeFallbackPublisher(projection ProjectionStore) (KnowledgeFallbackPublisher, error) {
	if os.Getenv("AUTODATA_PROJECTION_STORE") != "postgres" {
		return newMemoryKnowledgeFallbackPublisher(), nil
	}
	store, ok := projection.(*postgresProjectionStore)
	if !ok || store == nil || store.pool == nil {
		return nil, fmt.Errorf("postgres projection store is required for durable knowledge fallback publishing")
	}
	return newPostgresKnowledgeFallbackPublisher(store.pool), nil
}
