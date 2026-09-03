package main

import (
	"errors"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/lucronn/autodata/packages/contracts/go"
)

var (
	ErrDatasetNotFound       = errors.New("dataset projection not found")
	ErrEntitlementRevoked    = errors.New("dataset entitlement has been revoked")
	ErrDatasetNotViewable    = errors.New("dataset does not have a viewable revision")
	ErrRevisionNotFound      = errors.New("dataset revision not found")
	ErrInvalidEvidence       = errors.New("evidence reference is invalid")
	ErrReviewRequired        = errors.New("evidence is pending human review")
	ErrInvalidFeedback       = errors.New("feedback category or body is invalid")
	ErrInvalidReview         = errors.New("review decision or reason is invalid")
	ErrReviewConflict        = errors.New("evidence review state has already changed")
	ErrInvalidFeedbackReview = errors.New("feedback review decision or reason is invalid")
	ErrFeedbackNotFound      = errors.New("feedback item not found")
	ErrFeedbackConflict      = errors.New("feedback review state has already changed")
)

// ProjectionStore is the authorization-aware read boundary for purchaser-facing
// data. Handlers never depend on canonical table layout or a specific database.
type ProjectionStore interface {
	GetDataset(string, Principal, string) (DatasetReadRecord, error)
	ListSections(string, Principal) (DatasetReadRecord, error)
	ListRevisions(string, Principal) (DatasetRevisionList, error)
	GetEvidence(string, string, Principal) (EvidenceRecord, error)
	SearchEvidence(string, []float64, int, Principal) (EvidenceSearchResponse, error)
	SearchKnowledge(string, string, string, int, string, Principal) (KnowledgeSearchResponse, error)
	SubmitFeedback(string, FeedbackInput, Principal) (FeedbackRecord, error)
	ReviewEvidence(string, string, EvidenceReviewInput, Principal) (EvidenceRecord, error)
	ReviewFeedback(string, string, FeedbackReviewInput, Principal) (FeedbackRecord, error)
}

type KnowledgeSearchResponse = contracts.KnowledgeSearchResponse

type DatasetReadRecord struct {
	DatasetID       string                     `json:"dataset_id"`
	RevisionID      string                     `json:"revision_id"`
	Availability    string                     `json:"availability"`
	SourceWatermark string                     `json:"source_watermark"`
	Sections        []contracts.DatasetSection `json:"sections"`
	Data            map[string]any             `json:"data,omitempty"`
	Warnings        []map[string]any           `json:"warnings,omitempty"`
}

type DatasetRevisionRecord struct {
	RevisionID      string         `json:"revision_id"`
	RevisionNumber  int            `json:"revision_number"`
	Availability    string         `json:"availability"`
	SourceWatermark string         `json:"source_watermark"`
	Changelog       map[string]any `json:"changelog"`
	PublishedAt     string         `json:"published_at,omitempty"`
	Data            map[string]any `json:"data,omitempty"`
}

type DatasetRevisionList struct {
	DatasetID string                  `json:"dataset_id"`
	Revisions []DatasetRevisionRecord `json:"revisions"`
}

type EvidenceRecord struct {
	EvidenceID        string    `json:"evidence_id"`
	SourceSnapshotID  string    `json:"source_snapshot_id"`
	ExtractionRunID   *string   `json:"extraction_run_id"`
	DatasetRevisionID *string   `json:"dataset_revision_id,omitempty"`
	Locator           string    `json:"locator"`
	ArtifactKey       string    `json:"artifact_key,omitempty"`
	ExtractedText     string    `json:"extracted_text,omitempty"`
	Confidence        float64   `json:"confidence"`
	ReviewerState     string    `json:"reviewer_state,omitempty"`
	Embedding         []float64 `json:"-"`
	ReviewerID        *string   `json:"reviewer_id,omitempty"`
	ReviewedAt        *string   `json:"reviewed_at,omitempty"`
	ReviewReason      string    `json:"review_reason,omitempty"`
}

type EvidenceReviewInput struct {
	Decision string `json:"decision"`
	Reason   string `json:"reason"`
}

type EvidenceSearchResponse struct {
	DatasetID string              `json:"dataset_id"`
	Results   []EvidenceSearchHit `json:"results"`
}

type EvidenceSearchHit struct {
	EvidenceID    string  `json:"evidence_id"`
	RevisionID    string  `json:"revision_id"`
	Locator       string  `json:"locator"`
	ExtractedText string  `json:"extracted_text"`
	Confidence    float64 `json:"confidence"`
	Score         float64 `json:"score"`
}

type FeedbackInput struct {
	Category   string `json:"category"`
	Body       string `json:"body"`
	RevisionID string `json:"revision_id,omitempty"`
	EvidenceID string `json:"evidence_id,omitempty"`
}

type FeedbackRecord struct {
	FeedbackID        string  `json:"feedback_id"`
	DatasetID         string  `json:"dataset_id"`
	RevisionID        string  `json:"revision_id,omitempty"`
	EvidenceID        string  `json:"evidence_id,omitempty"`
	Category          string  `json:"category"`
	Body              string  `json:"body"`
	Status            string  `json:"status"`
	CreatedAt         string  `json:"created_at"`
	AppliedRevisionID string  `json:"applied_revision_id,omitempty"`
	ReviewerID        *string `json:"reviewer_id,omitempty"`
	ReviewedAt        *string `json:"reviewed_at,omitempty"`
	ReviewReason      string  `json:"review_reason,omitempty"`
}

type FeedbackReviewInput struct {
	Decision          string `json:"decision"`
	Reason            string `json:"reason"`
	AppliedRevisionID string `json:"applied_revision_id,omitempty"`
}

type memoryDataset struct {
	datasetID         string
	organizationID    string
	entitlementStatus string
	requestStatus     string
	revisions         []DatasetRevisionRecord
	sections          []contracts.DatasetSection
	evidence          map[string]EvidenceRecord
	feedback          []FeedbackRecord
}

type memoryProjectionStore struct {
	mu       sync.RWMutex
	datasets map[string]memoryDataset
}

func newMemoryProjectionStore() *memoryProjectionStore {
	return &memoryProjectionStore{datasets: make(map[string]memoryDataset)}
}

func (s *memoryProjectionStore) put(dataset memoryDataset) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.datasets[dataset.datasetID] = dataset
}

func (s *memoryProjectionStore) authorize(datasetID string, principal Principal) (memoryDataset, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	dataset, ok := s.datasets[datasetID]
	if !ok {
		return memoryDataset{}, ErrDatasetNotFound
	}
	if dataset.organizationID != principal.OrganizationID {
		return memoryDataset{}, ErrEntitlementRequired
	}
	if dataset.entitlementStatus == "revoked" || dataset.requestStatus == "revoked" {
		return memoryDataset{}, ErrEntitlementRevoked
	}
	if len(dataset.revisions) == 0 || dataset.requestStatus == "purchased" || dataset.requestStatus == "fast_lane_processing" || dataset.requestStatus == "failed" {
		return memoryDataset{}, ErrDatasetNotViewable
	}
	return dataset, nil
}

func (s *memoryProjectionStore) GetDataset(datasetID string, principal Principal, revisionID string) (DatasetReadRecord, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return DatasetReadRecord{}, err
	}
	revision, err := selectRevision(dataset.revisions, revisionID)
	if err != nil {
		return DatasetReadRecord{}, err
	}
	return DatasetReadRecord{
		DatasetID:       dataset.datasetID,
		RevisionID:      revision.RevisionID,
		Availability:    revision.Availability,
		SourceWatermark: revision.SourceWatermark,
		Sections:        dataset.sections,
		Data:            revision.Data,
		Warnings:        sectionWarnings(dataset.sections),
	}, nil
}

func (s *memoryProjectionStore) ListSections(datasetID string, principal Principal) (DatasetReadRecord, error) {
	record, err := s.GetDataset(datasetID, principal, "")
	if err != nil {
		return DatasetReadRecord{}, err
	}
	record.Data = nil
	record.Warnings = nil
	return record, nil
}

func (s *memoryProjectionStore) ListRevisions(datasetID string, principal Principal) (DatasetRevisionList, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return DatasetRevisionList{}, err
	}
	return DatasetRevisionList{DatasetID: dataset.datasetID, Revisions: dataset.revisions}, nil
}

func (s *memoryProjectionStore) GetEvidence(datasetID, evidenceID string, principal Principal) (EvidenceRecord, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return EvidenceRecord{}, err
	}
	evidence, ok := dataset.evidence[evidenceID]
	if !ok {
		return EvidenceRecord{}, ErrInvalidEvidence
	}
	if evidence.ReviewerState != "approved" {
		return EvidenceRecord{}, ErrReviewRequired
	}
	return evidence, nil
}

func (s *memoryProjectionStore) SearchEvidence(datasetID string, query []float64, limit int, principal Principal) (EvidenceSearchResponse, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return EvidenceSearchResponse{}, err
	}
	published := make(map[string]struct{}, len(dataset.revisions))
	for _, revision := range dataset.revisions {
		published[revision.RevisionID] = struct{}{}
	}
	results := make([]EvidenceSearchHit, 0)
	for _, evidence := range dataset.evidence {
		if evidence.ReviewerState != "approved" || len(evidence.Embedding) == 0 || evidence.DatasetRevisionID == nil {
			continue
		}
		if _, ok := published[*evidence.DatasetRevisionID]; !ok {
			continue
		}
		results = append(results, EvidenceSearchHit{
			EvidenceID:    evidence.EvidenceID,
			RevisionID:    *evidence.DatasetRevisionID,
			Locator:       evidence.Locator,
			ExtractedText: evidence.ExtractedText,
			Confidence:    evidence.Confidence,
			Score:         cosineSimilarity(query, evidence.Embedding),
		})
	}
	sort.SliceStable(results, func(i, j int) bool {
		if results[i].Score == results[j].Score {
			return results[i].EvidenceID < results[j].EvidenceID
		}
		return results[i].Score > results[j].Score
	})
	if limit < len(results) {
		results = results[:limit]
	}
	return EvidenceSearchResponse{DatasetID: datasetID, Results: results}, nil
}

func (s *memoryProjectionStore) SearchKnowledge(datasetID, query, kind string, limit int, revisionID string, principal Principal) (KnowledgeSearchResponse, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return KnowledgeSearchResponse{}, err
	}
	revision, err := selectRevision(dataset.revisions, revisionID)
	if err != nil {
		return KnowledgeSearchResponse{}, err
	}
	return searchKnowledgeRevision(datasetID, revision, dataset.sections, dataset.evidence, query, kind, limit), nil
}

func (s *memoryProjectionStore) SubmitFeedback(datasetID string, input FeedbackInput, principal Principal) (FeedbackRecord, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return FeedbackRecord{}, err
	}
	if err := validateFeedbackInput(input); err != nil {
		return FeedbackRecord{}, err
	}
	revisionID := input.RevisionID
	if revisionID != "" {
		if _, err := selectRevision(dataset.revisions, revisionID); err != nil {
			return FeedbackRecord{}, err
		}
	}
	if input.EvidenceID != "" {
		evidence, ok := dataset.evidence[input.EvidenceID]
		if !ok {
			return FeedbackRecord{}, ErrInvalidEvidence
		}
		if evidence.ReviewerState != "approved" {
			return FeedbackRecord{}, ErrReviewRequired
		}
		if evidence.DatasetRevisionID != nil {
			if revisionID != "" && *evidence.DatasetRevisionID != revisionID {
				return FeedbackRecord{}, ErrInvalidFeedback
			}
			revisionID = *evidence.DatasetRevisionID
		}
	}
	feedbackID, err := newRequestID()
	if err != nil {
		return FeedbackRecord{}, err
	}
	record := FeedbackRecord{
		FeedbackID: feedbackID,
		DatasetID:  datasetID,
		RevisionID: revisionID,
		EvidenceID: input.EvidenceID,
		Category:   input.Category,
		Body:       strings.TrimSpace(input.Body),
		Status:     "open",
		CreatedAt:  time.Now().UTC().Format(time.RFC3339),
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	current := s.datasets[datasetID]
	current.feedback = append(current.feedback, record)
	s.datasets[datasetID] = current
	return record, nil
}

func (s *memoryProjectionStore) ReviewEvidence(datasetID, evidenceID string, input EvidenceReviewInput, principal Principal) (EvidenceRecord, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return EvidenceRecord{}, err
	}
	if err := validateEvidenceReview(input); err != nil {
		return EvidenceRecord{}, err
	}
	evidence, ok := dataset.evidence[evidenceID]
	if !ok {
		return EvidenceRecord{}, ErrInvalidEvidence
	}
	if evidence.DatasetRevisionID != nil {
		return EvidenceRecord{}, ErrReviewConflict
	}
	wantState := "rejected"
	if input.Decision == "approve" {
		wantState = "approved"
	}
	if evidence.ReviewerState != "pending" && evidence.ReviewerState != wantState {
		return EvidenceRecord{}, ErrReviewConflict
	}
	if evidence.ReviewerState == "pending" {
		reviewedAt := time.Now().UTC().Format(time.RFC3339)
		reviewerID := principal.OrganizationID
		evidence.ReviewerState = wantState
		evidence.ReviewerID = &reviewerID
		evidence.ReviewedAt = &reviewedAt
		evidence.ReviewReason = strings.TrimSpace(input.Reason)
		s.mu.Lock()
		current := s.datasets[datasetID]
		current.evidence[evidenceID] = evidence
		s.datasets[datasetID] = current
		s.mu.Unlock()
	}
	return evidence, nil
}

func (s *memoryProjectionStore) ReviewFeedback(datasetID, feedbackID string, input FeedbackReviewInput, principal Principal) (FeedbackRecord, error) {
	dataset, err := s.authorize(datasetID, principal)
	if err != nil {
		return FeedbackRecord{}, err
	}
	if err := validateFeedbackReview(input); err != nil {
		return FeedbackRecord{}, err
	}
	if input.Decision == "resolve" {
		if input.AppliedRevisionID == "" {
			return FeedbackRecord{}, ErrInvalidFeedbackReview
		}
		if _, err := selectRevision(dataset.revisions, input.AppliedRevisionID); err != nil {
			return FeedbackRecord{}, err
		}
	} else if input.AppliedRevisionID != "" {
		return FeedbackRecord{}, ErrInvalidFeedbackReview
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	current := s.datasets[datasetID]
	for index, feedback := range current.feedback {
		if feedback.FeedbackID != feedbackID {
			continue
		}
		wantStatus := "rejected"
		if input.Decision == "resolve" {
			wantStatus = "resolved"
		}
		if feedback.Status != "open" && feedback.Status != "in_review" && feedback.Status != wantStatus {
			return FeedbackRecord{}, ErrFeedbackConflict
		}
		if feedback.Status == wantStatus {
			if input.Decision == "resolve" && feedback.AppliedRevisionID != input.AppliedRevisionID {
				return FeedbackRecord{}, ErrFeedbackConflict
			}
			return feedback, nil
		}
		reviewedAt := time.Now().UTC().Format(time.RFC3339)
		reviewerID := principal.OrganizationID
		feedback.Status = wantStatus
		feedback.AppliedRevisionID = input.AppliedRevisionID
		feedback.ReviewerID = &reviewerID
		feedback.ReviewedAt = &reviewedAt
		feedback.ReviewReason = strings.TrimSpace(input.Reason)
		current.feedback[index] = feedback
		s.datasets[datasetID] = current
		return feedback, nil
	}
	return FeedbackRecord{}, ErrFeedbackNotFound
}

func validateFeedbackInput(input FeedbackInput) error {
	switch input.Category {
	case "correction", "missing", "quality", "safety":
	default:
		return ErrInvalidFeedback
	}
	body := strings.TrimSpace(input.Body)
	if body == "" || len(body) > 4000 {
		return ErrInvalidFeedback
	}
	return nil
}

func validateEvidenceReview(input EvidenceReviewInput) error {
	if input.Decision != "approve" && input.Decision != "reject" {
		return ErrInvalidReview
	}
	reason := strings.TrimSpace(input.Reason)
	if reason == "" || len(reason) > 4000 {
		return ErrInvalidReview
	}
	return nil
}

func validateFeedbackReview(input FeedbackReviewInput) error {
	if input.Decision != "resolve" && input.Decision != "reject" {
		return ErrInvalidFeedbackReview
	}
	reason := strings.TrimSpace(input.Reason)
	if reason == "" || len(reason) > 4000 {
		return ErrInvalidFeedbackReview
	}
	return nil
}

func selectRevision(revisions []DatasetRevisionRecord, revisionID string) (DatasetRevisionRecord, error) {
	if revisionID != "" {
		for _, revision := range revisions {
			if revision.RevisionID == revisionID {
				return revision, nil
			}
		}
		return DatasetRevisionRecord{}, ErrRevisionNotFound
	}
	if len(revisions) == 0 {
		return DatasetRevisionRecord{}, ErrDatasetNotViewable
	}
	ordered := append([]DatasetRevisionRecord(nil), revisions...)
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].RevisionNumber > ordered[j].RevisionNumber })
	return ordered[0], nil
}

func sectionWarnings(sections []contracts.DatasetSection) []map[string]any {
	warnings := make([]map[string]any, 0)
	for _, section := range sections {
		if section.Status == "failed" || section.Status == "needs_review" {
			warnings = append(warnings, map[string]any{
				"section": section.Name,
				"status":  section.Status,
			})
		}
	}
	return warnings
}
