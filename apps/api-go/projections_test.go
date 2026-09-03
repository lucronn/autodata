package main

import (
	"net/http"
	"net/http/httptest"
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
