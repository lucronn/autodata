package main

import (
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/lucronn/autodata/packages/contracts/go"
)

func TestGetDatasetReturnsEntitledProjectionWithSectionReadiness(t *testing.T) {
	principal := Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}
	store := newMemoryProjectionStore()
	store.put(memoryDatasetFixture())
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: principal}, newMemoryRequestStore(), store)

	request := httptest.NewRequest(http.MethodGet, "/datasets/dataset-1", nil)
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	var body struct {
		DatasetID       string           `json:"dataset_id"`
		RevisionID      string           `json:"revision_id"`
		Availability    string           `json:"availability"`
		SourceWatermark string           `json:"source_watermark"`
		Sections        []map[string]any `json:"sections"`
		Data            map[string]any   `json:"data"`
	}
	decodeJSON(t, response, &body)
	if body.DatasetID != "dataset-1" || body.RevisionID != "revision-2" || body.Availability != "viewable" {
		t.Fatalf("unexpected projection envelope: %#v", body)
	}
	if body.SourceWatermark != "sample-2026-09-03" || len(body.Sections) != 2 {
		t.Fatalf("unexpected projection metadata: %#v", body)
	}
	if body.Sections[0]["status"] != "viewable" || body.Sections[1]["status"] != "enriching" {
		t.Fatalf("section readiness not exposed: %#v", body.Sections)
	}
	if body.Data["vehicle_key"] != "toyota-corolla-2024-us" {
		t.Fatalf("projection data = %#v", body.Data)
	}
}

func TestDatasetReadsEnforceOrganizationEntitlementAndRevocation(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	store.put(fixture)

	otherOrg := Principal{OrganizationID: "org-2", Roles: []string{"dataset_viewer"}}
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: otherOrg}, newMemoryRequestStore(), store)
	response := performRequest(server, http.MethodGet, "/datasets/dataset-1")
	if response.Code != http.StatusForbidden {
		t.Fatalf("missing entitlement status = %d, want %d", response.Code, http.StatusForbidden)
	}
	assertErrorCode(t, response, "ENTITLEMENT_REQUIRED")

	fixture.entitlementStatus = "revoked"
	store.put(fixture)
	owner := Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}
	server = NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: owner}, newMemoryRequestStore(), store)
	response = performRequest(server, http.MethodGet, "/datasets/dataset-1")
	if response.Code != http.StatusGone {
		t.Fatalf("revoked entitlement status = %d, want %d", response.Code, http.StatusGone)
	}
	assertErrorCode(t, response, "ENTITLEMENT_REVOKED")
}

func TestDatasetReadsExposeStaleRevisionsAndSectionFailures(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.sections[1].Status = "failed"
	store.put(fixture)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1?revision_id=revision-1")
	if response.Code != http.StatusOK {
		t.Fatalf("stale revision status = %d, want %d", response.Code, http.StatusOK)
	}
	var body map[string]any
	decodeJSON(t, response, &body)
	if body["revision_id"] != "revision-1" {
		t.Fatalf("revision ID = %#v, want revision-1", body["revision_id"])
	}
	sections := body["sections"].([]any)
	if sections[1].(map[string]any)["status"] != "failed" {
		t.Fatalf("section failure was not localized: %#v", sections)
	}
}

func TestDatasetRevisionAndEvidenceEndpointsHandleReviewState(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	pending := fixture.evidence["evidence-pending"]
	pending.ReviewerState = "pending"
	fixture.evidence["evidence-pending"] = pending
	store.put(fixture)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/revisions")
	if response.Code != http.StatusOK {
		t.Fatalf("revisions status = %d, want %d", response.Code, http.StatusOK)
	}
	var revisions struct {
		DatasetID string `json:"dataset_id"`
		Revisions []any  `json:"revisions"`
	}
	decodeJSON(t, response, &revisions)
	if revisions.DatasetID != "dataset-1" || len(revisions.Revisions) != 2 {
		t.Fatalf("unexpected revisions response: %#v", revisions)
	}

	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/evidence/evidence-pending")
	if response.Code != http.StatusConflict {
		t.Fatalf("pending evidence status = %d, want %d", response.Code, http.StatusConflict)
	}
	assertErrorCode(t, response, "REVIEW_REQUIRED")

	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/evidence/missing")
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("missing evidence status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
	assertErrorCode(t, response, "INVALID_EVIDENCE")
}

func TestEvidenceSearchReturnsOnlyApprovedRevisionScopedResults(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.evidence["evidence-approved"] = EvidenceRecord{
		EvidenceID:        "evidence-approved",
		SourceSnapshotID:  "snapshot-1",
		ExtractionRunID:   stringPtr("run-2"),
		DatasetRevisionID: stringPtr("revision-2"),
		Locator:           "page=9",
		ExtractedText:     "brake fluid DOT 4",
		Confidence:        0.99,
		ReviewerState:     "approved",
		Embedding:         fixtureVector(1),
	}
	fixture.evidence["evidence-no-vector"] = EvidenceRecord{
		EvidenceID:    "evidence-no-vector",
		ExtractedText: "unindexed approved text",
		Confidence:    0.99,
		ReviewerState: "approved",
	}
	store.put(fixture)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/search?q=brake+fluid&limit=5")

	if response.Code != http.StatusOK {
		t.Fatalf("search status = %d, want %d", response.Code, http.StatusOK)
	}
	var body EvidenceSearchResponse
	decodeJSON(t, response, &body)
	if body.DatasetID != "dataset-1" || len(body.Results) != 1 {
		t.Fatalf("unexpected search response: %#v", body)
	}
	if body.Results[0].EvidenceID != "evidence-approved" || body.Results[0].RevisionID != "revision-2" {
		t.Fatalf("search result is not revision-scoped evidence: %#v", body.Results[0])
	}
}

func TestKnowledgeSearchReturnsTypedArticleAndProcedureResultsFromSelectedRevision(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[0].Data["articles"] = []any{
		map[string]any{
			"article_id":      "article-old",
			"article_key":     "article:old",
			"bucket":          "Service Bulletin",
			"title":           "Older brake inspection article",
			"bulletin_number": "TSB-OLD",
			"release_date":    "2026-09-02",
			"body":            "Inspect the brake hose before replacement.",
			"evidence_id":     "evidence-old",
			"content_locator": "body.articleDetails[0]",
			"source_uri":      "provider://old/article",
			"source_version":  "source-old",
			"source_sha256":   "sha-old",
			"content_sha256":  "sha-old",
		},
	}
	fixture.revisions[0].Data["vehicle_identity"] = map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"make":        "Toyota",
		"model":       "Corolla",
		"model_year":  float64(2024),
		"region":      "US",
	}
	fixture.revisions[1].Data["articles"] = []any{
		map[string]any{
			"article_id":      "article-new",
			"article_key":     "article:new",
			"bucket":          "Service Bulletin",
			"title":           "Brake caliper replacement bulletin",
			"bulletin_number": "TSB-NEW",
			"release_date":    "2026-09-03",
			"body":            "Replace the brake caliper and torque the guide pins.",
			"steps":           []any{"Remove the wheel.", "Torque the guide pins."},
			"evidence_ids":    []any{"evidence-article"},
			"content_locator": "body.articleDetails[1]",
			"source_uri":      "provider://new/article",
			"source_version":  "source-new",
			"content_sha256":  "sha-new",
		},
	}
	fixture.revisions[1].Data["procedures"] = map[string]any{
		"section":            "procedures",
		"source_snapshot_id": "snapshot-2",
		"records": []any{
			map[string]any{
				"source_evidence_id": "evidence-procedure",
				"locator":            "page:12",
				"artifact_key":       "sources/brakes.pdf",
				"text":               "Procedure: remove the caliper, install the replacement, and torque the bolts.",
				"confidence":         0.97,
				"matched_terms":      []any{"procedure", "install", "torque"},
			},
		},
	}
	fixture.evidence["evidence-article"] = EvidenceRecord{
		EvidenceID:        "evidence-article",
		SourceSnapshotID:  "snapshot-2",
		ExtractionRunID:   stringPtr("run-article"),
		DatasetRevisionID: stringPtr("revision-2"),
		Locator:           "body.articleDetails[1]",
		ArtifactKey:       "sources/article.json",
		ExtractedText:     "Replace the brake caliper and torque the guide pins.",
		Confidence:        0.94,
		ReviewerState:     "approved",
	}
	fixture.evidence["evidence-procedure"] = EvidenceRecord{
		EvidenceID:        "evidence-procedure",
		SourceSnapshotID:  "snapshot-2",
		ExtractionRunID:   stringPtr("run-procedure"),
		DatasetRevisionID: stringPtr("revision-2"),
		Locator:           "page:12",
		ArtifactKey:       "sources/brakes.pdf",
		ExtractedText:     "Procedure: remove the caliper, install the replacement, and torque the bolts.",
		Confidence:        0.97,
		ReviewerState:     "approved",
	}
	store.put(fixture)
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), publisher, store)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=brake+caliper&kind=all&limit=10")
	if response.Code != http.StatusOK {
		t.Fatalf("knowledge status = %d, want %d", response.Code, http.StatusOK)
	}
	var body KnowledgeSearchResponse
	decodeJSON(t, response, &body)
	if body.DatasetID != "dataset-1" || body.RevisionID != "revision-2" || body.Availability != "viewable" {
		t.Fatalf("unexpected knowledge envelope: %#v", body)
	}
	if body.VehicleIdentity["vehicle_key"] != "toyota-corolla-2024-us" || len(body.Sections) != 2 {
		t.Fatalf("knowledge metadata missing: %#v", body)
	}
	if len(body.Results) != 2 || body.Results[0].Kind != "article" || body.Results[1].Kind != "procedure" {
		t.Fatalf("unexpected typed knowledge results: %#v", body.Results)
	}
	if body.Results[0].Article == nil || body.Results[0].Article.Title != "Brake caliper replacement bulletin" || len(body.Results[0].Article.Steps) != 2 {
		t.Fatalf("article metadata missing: %#v", body.Results[0])
	}
	if body.Results[1].Procedure == nil || !strings.Contains(body.Results[1].Procedure.Excerpt, "torque the bolts") {
		t.Fatalf("procedure excerpt missing: %#v", body.Results[1])
	}
	if len(body.Results[0].Evidence) != 1 || body.Results[0].Evidence[0].EvidenceID != "evidence-article" || body.Results[0].Evidence[0].SourceURI != "provider://new/article" || len(body.Results[1].Evidence) != 1 || body.Results[1].Evidence[0].Locator != "page:12" || body.Results[1].Evidence[0].SourceSnapshotID != "snapshot-2" {
		t.Fatalf("inline provenance missing: %#v", body.Results)
	}
	if body.Results[0].Score <= 0 || body.Results[1].Score <= 0 {
		t.Fatalf("knowledge results must have positive scores: %#v", body.Results)
	}
	if events := publisher.Events(); len(events) != 0 {
		t.Fatalf("warm knowledge read published %d events, want 0", len(events))
	}
}

func TestKnowledgeSearchIsRevisionScopedAndValidatesKind(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[0].Data["articles"] = []any{map[string]any{
		"article_id": "article-old", "title": "Old oil filter procedure", "body": "Old revision only",
	}}
	fixture.revisions[1].Data["articles"] = []any{map[string]any{
		"article_id": "article-new", "title": "New brake article", "body": "New revision only",
	}}
	store.put(fixture)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=oil&kind=article&revision_id=revision-1")
	if response.Code != http.StatusOK {
		t.Fatalf("stale knowledge status = %d, want %d", response.Code, http.StatusOK)
	}
	var body KnowledgeSearchResponse
	decodeJSON(t, response, &body)
	if body.RevisionID != "revision-1" || len(body.Results) != 1 || body.Results[0].Article.ArticleID != "article-old" {
		t.Fatalf("knowledge escaped selected revision: %#v", body)
	}

	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=oil&kind=unsupported")
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("invalid kind status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
	assertErrorCode(t, response, "INVALID_REQUEST")
}

func TestKnowledgeFallbackCacheHitIsFetchedWithoutPublishing(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[1].Data["vehicle_identity"] = map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"region":      "US",
	}
	fixture.revisions[1].Data["articles"] = []any{map[string]any{
		"article_id": "article-brakes",
		"title":      "Brake caliper replacement",
		"body":       "Replace the brake caliper.",
	}}
	store.put(fixture)
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=brake+caliper&fallback=true")
	if response.Code != http.StatusOK {
		t.Fatalf("fallback cache hit status = %d, want %d", response.Code, http.StatusOK)
	}
	var body KnowledgeSearchResponse
	decodeJSON(t, response, &body)
	if events := publisher.Events(); len(events) != 0 {
		t.Fatalf("cache hit published %d events, want 0", len(events))
	}
}

func TestKnowledgeWarmCacheMissRemainsReadOnly(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[1].Data["vehicle_identity"] = map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"region":      "US",
	}
	store.put(fixture)
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing")
	if response.Code != http.StatusOK {
		t.Fatalf("warm cache miss status = %d, want %d", response.Code, http.StatusOK)
	}
	if events := publisher.Events(); len(events) != 0 {
		t.Fatalf("warm cache miss published %d events, want 0", len(events))
	}
}

func TestKnowledgeFallbackCacheMissPublishesExactVersionedEnvelope(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[1].Data["vehicle_identity"] = map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"region":      "US",
	}
	store.put(fixture)
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)

	request := httptest.NewRequest(http.MethodGet, "/datasets/dataset-1/knowledge?q=brake+caliper&kind=article&limit=7&fallback=true", nil)
	request.Header.Set("X-Request-ID", "fallback-request-1")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusAccepted {
		t.Fatalf("fallback cache miss status = %d, want %d", response.Code, http.StatusAccepted)
	}
	var responseBody KnowledgeSearchResponse
	decodeJSON(t, response, &responseBody)
	if responseBody.FallbackStatus != "pending" || responseBody.FallbackRequestID == "" {
		t.Fatalf("fallback response status = %q request = %q, want pending and request ID", responseBody.FallbackStatus, responseBody.FallbackRequestID)
	}
	events := publisher.Events()
	if len(events) != 1 {
		t.Fatalf("published events = %d, want 1", len(events))
	}
	event := events[0]
	if event.EventType != "dataset.knowledge.fallback.requested" || event.EventVersion != 1 {
		t.Fatalf("event identity = %q v%d, want dataset.knowledge.fallback.requested v1", event.EventType, event.EventVersion)
	}
	if event.Producer != "autodata-api" || event.RequestID != "fallback-request-1" || event.ProjectionID != "dataset-1" || !validUUID(event.CorrelationID) {
		t.Fatalf("event routing fields = %#v", event)
	}
	if event.RevisionID == nil || *event.RevisionID != "revision-2" || event.EventID == "" || event.IdempotencyKey == "" {
		t.Fatalf("event identity fields = %#v", event)
	}
	wantPayload := map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"region":      "US",
		"query":       "brake caliper",
		"keywords":    []string{"brake", "caliper"},
		"kind":        "article",
		"dataset_id":  "dataset-1",
		"revision_id": "revision-2",
	}
	if !reflect.DeepEqual(event.Payload, wantPayload) {
		t.Fatalf("event payload = %#v, want %#v", event.Payload, wantPayload)
	}
}

func TestKnowledgeFallbackDuplicateRequestPublishesOnce(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.revisions[1].Data["vehicle_identity"] = map[string]any{
		"vehicle_key": "toyota-corolla-2024-us",
		"region":      "US",
	}
	store.put(fixture)
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)

	first := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=true")
	second := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=true")
	if first.Code != http.StatusAccepted || second.Code != http.StatusAccepted {
		t.Fatalf("duplicate statuses = %d, %d, want %d, %d", first.Code, second.Code, http.StatusAccepted, http.StatusAccepted)
	}
	if events := publisher.Events(); len(events) != 1 {
		t.Fatalf("duplicate published %d events, want 1", len(events))
	}
}

func TestKnowledgeFallbackPreservesAuthenticationAndEntitlementBoundaries(t *testing.T) {
	store := newMemoryProjectionStore()
	store.put(memoryDatasetFixture())
	publisher := newMemoryKnowledgeFallbackPublisher()

	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore(), publisher, store,
	)
	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=true")
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("unauthenticated status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
	assertErrorCode(t, response, "UNAUTHENTICATED")

	server = NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-2", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)
	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=true")
	if response.Code != http.StatusForbidden {
		t.Fatalf("wrong entitlement status = %d, want %d", response.Code, http.StatusForbidden)
	}
	assertErrorCode(t, response, "ENTITLEMENT_REQUIRED")

	fixture := memoryDatasetFixture()
	fixture.entitlementStatus = "revoked"
	store.put(fixture)
	server = NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)
	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=true")
	if response.Code != http.StatusGone {
		t.Fatalf("revoked entitlement status = %d, want %d", response.Code, http.StatusGone)
	}
	assertErrorCode(t, response, "ENTITLEMENT_REVOKED")
	if events := publisher.Events(); len(events) != 0 {
		t.Fatalf("unauthorized requests published %d events, want 0", len(events))
	}
}

func TestKnowledgeFallbackRejectsInvalidFallbackInput(t *testing.T) {
	store := newMemoryProjectionStore()
	store.put(memoryDatasetFixture())
	publisher := newMemoryKnowledgeFallbackPublisher()
	server := NewServerWithDependenciesAndPublisher(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(), publisher, store,
	)

	response := performRequest(server, http.MethodGet, "/datasets/dataset-1/knowledge?q=missing&fallback=maybe")
	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("invalid fallback status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
	assertErrorCode(t, response, "INVALID_REQUEST")
	if events := publisher.Events(); len(events) != 0 {
		t.Fatalf("invalid request published %d events, want 0", len(events))
	}
}

func TestFeedbackSubmissionCreatesOpenReviewItemLinkedToRevision(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	fixture.evidence["evidence-approved"] = EvidenceRecord{
		EvidenceID:        "evidence-approved",
		DatasetRevisionID: stringPtr("revision-2"),
		Locator:           "page=9",
		ExtractedText:     "brake fluid DOT 4",
		Confidence:        0.99,
		ReviewerState:     "approved",
		Embedding:         fixtureVector(1),
	}
	store.put(fixture)
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}
	server := NewServerWithDependencies(staticReadiness{}, auth, newMemoryRequestStore(), store)
	request := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/feedback", strings.NewReader(`{"category":"correction","body":"The procedure omits the ground connection.","revision_id":"revision-2","evidence_id":"evidence-approved"}`))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusCreated {
		t.Fatalf("feedback status = %d, want %d", response.Code, http.StatusCreated)
	}
	var body FeedbackRecord
	decodeJSON(t, response, &body)
	if body.DatasetID != "dataset-1" || body.Status != "open" || body.RevisionID != "revision-2" || body.EvidenceID != "evidence-approved" {
		t.Fatalf("unexpected feedback response: %#v", body)
	}
}

func TestFeedbackSubmissionRejectsUnapprovedEvidence(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	pending := fixture.evidence["evidence-pending"]
	pending.DatasetRevisionID = stringPtr("revision-2")
	fixture.evidence["evidence-pending"] = pending
	store.put(fixture)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)
	request := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/feedback", strings.NewReader(`{"category":"quality","body":"Please review this fact.","revision_id":"revision-2","evidence_id":"evidence-pending"}`))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusConflict {
		t.Fatalf("pending evidence status = %d, want %d", response.Code, http.StatusConflict)
	}
	assertErrorCode(t, response, "REVIEW_REQUIRED")
}

func TestReviewerCanApprovePendingEvidenceWithoutMutatingPublishedRevisions(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	store.put(fixture)
	principal := Principal{OrganizationID: "org-1", Roles: []string{"data_reviewer", "dataset_viewer"}}
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: principal}, newMemoryRequestStore(), store)
	request := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/evidence/evidence-pending/review", strings.NewReader(`{"decision":"approve","reason":"Source locator and extracted text verified."}`))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("review status = %d, want %d", response.Code, http.StatusOK)
	}
	var review EvidenceRecord
	decodeJSON(t, response, &review)
	if review.EvidenceID != "evidence-pending" || review.ReviewerState != "approved" {
		t.Fatalf("unexpected review response: %#v", review)
	}

	response = performRequest(server, http.MethodGet, "/datasets/dataset-1/evidence/evidence-pending")
	response = performRequest(server, http.MethodGet, "/datasets/dataset-1?revision_id=revision-1")
	if response.Code != http.StatusOK {
		t.Fatalf("published revision status = %d, want %d", response.Code, http.StatusOK)
	}
}

func TestEvidenceReviewRequiresReviewerRole(t *testing.T) {
	store := newMemoryProjectionStore()
	store.put(memoryDatasetFixture())
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)
	request := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/evidence/evidence-pending/review", strings.NewReader(`{"decision":"approve","reason":"not authorized"}`))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusForbidden {
		t.Fatalf("reviewer role status = %d, want %d", response.Code, http.StatusForbidden)
	}
	assertErrorCode(t, response, "FORBIDDEN")
}

func TestReviewerCanResolveFeedbackOnlyByLinkingPublishedRevision(t *testing.T) {
	store := newMemoryProjectionStore()
	fixture := memoryDatasetFixture()
	store.put(fixture)
	principal := Principal{OrganizationID: "org-1", Roles: []string{"data_reviewer", "dataset_viewer"}}
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{principal: principal}, newMemoryRequestStore(), store)
	create := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/feedback", strings.NewReader(`{"category":"correction","body":"Correct the published procedure.","revision_id":"revision-1"}`))
	create.Header.Set("Content-Type", "application/json")
	createdResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(createdResponse, create)
	if createdResponse.Code != http.StatusCreated {
		t.Fatalf("feedback create status = %d, want %d", createdResponse.Code, http.StatusCreated)
	}
	var created FeedbackRecord
	decodeJSON(t, createdResponse, &created)

	review := httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/feedback/"+created.FeedbackID+"/review", strings.NewReader(`{"decision":"resolve","reason":"Replacement revision was published.","applied_revision_id":"revision-2"}`))
	review.Header.Set("Content-Type", "application/json")
	reviewResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(reviewResponse, review)
	if reviewResponse.Code != http.StatusOK {
		t.Fatalf("feedback review status = %d, want %d", reviewResponse.Code, http.StatusOK)
	}
	var resolved FeedbackRecord
	decodeJSON(t, reviewResponse, &resolved)
	if resolved.DatasetID != "dataset-1" || resolved.Status != "resolved" || resolved.AppliedRevisionID != "revision-2" {
		t.Fatalf("unexpected resolved feedback: %#v", resolved)
	}

	review = httptest.NewRequest(http.MethodPost, "/datasets/dataset-1/feedback/"+created.FeedbackID+"/review", strings.NewReader(`{"decision":"reject","reason":"conflicting second decision"}`))
	review.Header.Set("Content-Type", "application/json")
	reviewResponse = httptest.NewRecorder()
	server.Handler().ServeHTTP(reviewResponse, review)
	if reviewResponse.Code != http.StatusConflict {
		t.Fatalf("second feedback review status = %d, want %d", reviewResponse.Code, http.StatusConflict)
	}
	assertErrorCode(t, reviewResponse, "FEEDBACK_CONFLICT")
}

func performRequest(server *Server, method, path string) *httptest.ResponseRecorder {
	request := httptest.NewRequest(method, path, nil)
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	return response
}

func memoryDatasetFixture() memoryDataset {
	return memoryDataset{
		datasetID:         "dataset-1",
		organizationID:    "org-1",
		entitlementStatus: "active",
		requestStatus:     "enriching",
		revisions: []DatasetRevisionRecord{
			{RevisionID: "revision-1", RevisionNumber: 1, Availability: "viewable", SourceWatermark: "sample-2026-09-02", Changelog: map[string]any{"reason": "fast_lane"}, PublishedAt: "2026-09-02T00:00:00Z", Data: map[string]any{"vehicle_key": "toyota-corolla-2024-us"}},
			{RevisionID: "revision-2", RevisionNumber: 2, Availability: "viewable", SourceWatermark: "sample-2026-09-03", Changelog: map[string]any{"reason": "deep_lane"}, PublishedAt: "2026-09-03T00:00:00Z", Data: map[string]any{"vehicle_key": "toyota-corolla-2024-us"}},
		},
		sections: []contracts.DatasetSection{
			{Name: "vehicle", Status: "viewable", LastPublishedRevision: stringPtr("revision-2"), UpdatedAt: "2026-09-03T00:00:00Z"},
			{Name: "diagnostics", Status: "enriching", LastPublishedRevision: stringPtr("revision-1"), UpdatedAt: "2026-09-03T00:00:00Z"},
		},
		evidence: map[string]EvidenceRecord{
			"evidence-pending": {EvidenceID: "evidence-pending", SourceSnapshotID: "snapshot-1", ExtractionRunID: stringPtr("run-1"), Locator: "page=1", ArtifactKey: "sources/sample.pdf", ExtractedText: "pending text", Confidence: 0.81, ReviewerState: "pending"},
		},
	}
}

func stringPtr(value string) *string { return &value }

func fixtureVector(first float64) []float64 {
	vector := make([]float64, 1536)
	vector[0] = first
	return vector
}
