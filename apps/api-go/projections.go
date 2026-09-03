package main

import (
	"errors"
	"sort"
	"sync"

	"github.com/lucronn/autodata/packages/contracts/go"
)

var (
	ErrDatasetNotFound    = errors.New("dataset projection not found")
	ErrEntitlementRevoked = errors.New("dataset entitlement has been revoked")
	ErrDatasetNotViewable = errors.New("dataset does not have a viewable revision")
	ErrRevisionNotFound   = errors.New("dataset revision not found")
	ErrInvalidEvidence    = errors.New("evidence reference is invalid")
	ErrReviewRequired     = errors.New("evidence is pending human review")
)

// ProjectionStore is the authorization-aware read boundary for purchaser-facing
// data. Handlers never depend on canonical table layout or a specific database.
type ProjectionStore interface {
	GetDataset(string, Principal, string) (DatasetReadRecord, error)
	ListSections(string, Principal) (DatasetReadRecord, error)
	ListRevisions(string, Principal) (DatasetRevisionList, error)
	GetEvidence(string, string, Principal) (EvidenceRecord, error)
}

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
	EvidenceID       string  `json:"evidence_id"`
	SourceSnapshotID string  `json:"source_snapshot_id"`
	ExtractionRunID  *string `json:"extraction_run_id"`
	DatasetRevisionID *string `json:"dataset_revision_id,omitempty"`
	Locator          string  `json:"locator"`
	ArtifactKey      string  `json:"artifact_key,omitempty"`
	ExtractedText    string  `json:"extracted_text,omitempty"`
	Confidence       float64 `json:"confidence"`
	ReviewerState    string  `json:"reviewer_state,omitempty"`
}

type memoryDataset struct {
	datasetID         string
	organizationID    string
	entitlementStatus string
	requestStatus     string
	revisions         []DatasetRevisionRecord
	sections          []contracts.DatasetSection
	evidence          map[string]EvidenceRecord
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
