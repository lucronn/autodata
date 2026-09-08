package main

import (
	"errors"
	"sort"
	"strings"
	"sync"
	"time"
)

var (
	ErrSourceReviewNotFound = errors.New("source review item not found")
	ErrSourceReviewConflict = errors.New("source review item has already been decided")
	ErrInvalidSourceReview  = errors.New("source review decision or reason is invalid")
)

type SourceReviewItemRecord struct {
	SourceReviewItemID string         `json:"source_review_item_id"`
	ItemKey            string         `json:"item_key"`
	ItemKind           string         `json:"item_kind"`
	ReasonCode         string         `json:"reason_code"`
	Status             string         `json:"status"`
	SourceSnapshotIDs  []string       `json:"source_snapshot_ids"`
	EvidenceIDs        []string       `json:"extraction_evidence_ids"`
	Payload            map[string]any `json:"payload"`
	ReviewerID         string         `json:"reviewer_id,omitempty"`
	ReviewReason       string         `json:"review_reason,omitempty"`
	CreatedAt          string         `json:"created_at,omitempty"`
	UpdatedAt          string         `json:"updated_at,omitempty"`
}

type SourceReviewQueueRecord struct {
	Status string                   `json:"status"`
	Items  []SourceReviewItemRecord `json:"items"`
}

type SourceReviewStore interface {
	List(Principal, string, int) (SourceReviewQueueRecord, error)
	Review(string, SourceReviewReviewInput, Principal) (SourceReviewItemRecord, error)
}

type SourceReviewReviewInput struct {
	Decision string `json:"decision"`
	Reason   string `json:"reason"`
}

type memorySourceReviewStore struct {
	mu    sync.RWMutex
	items map[string]SourceReviewItemRecord
}

func newMemorySourceReviewStore() *memorySourceReviewStore {
	return &memorySourceReviewStore{items: make(map[string]SourceReviewItemRecord)}
}

func (s *memorySourceReviewStore) put(item SourceReviewItemRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if item.SourceSnapshotIDs == nil {
		item.SourceSnapshotIDs = []string{}
	}
	if item.EvidenceIDs == nil {
		item.EvidenceIDs = []string{}
	}
	if item.Payload == nil {
		item.Payload = map[string]any{}
	}
	s.items[item.SourceReviewItemID] = item
}

func (s *memorySourceReviewStore) List(_ Principal, status string, limit int) (SourceReviewQueueRecord, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	items := make([]SourceReviewItemRecord, 0, len(s.items))
	for _, item := range s.items {
		if status == "" || item.Status == status {
			items = append(items, item)
		}
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].CreatedAt != items[j].CreatedAt {
			return items[i].CreatedAt < items[j].CreatedAt
		}
		return items[i].SourceReviewItemID < items[j].SourceReviewItemID
	})
	if limit < len(items) {
		items = items[:limit]
	}
	return SourceReviewQueueRecord{Status: status, Items: items}, nil
}

func (s *memorySourceReviewStore) Get(id string, _ Principal) (SourceReviewItemRecord, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	item, ok := s.items[id]
	if !ok {
		return SourceReviewItemRecord{}, ErrSourceReviewNotFound
	}
	return item, nil
}

func (s *memorySourceReviewStore) Review(id string, input SourceReviewReviewInput, principal Principal) (SourceReviewItemRecord, error) {
	input = normalizedSourceReviewDecision(input)
	if err := validateSourceReviewInput(input); err != nil {
		return SourceReviewItemRecord{}, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	item, ok := s.items[id]
	if !ok {
		return SourceReviewItemRecord{}, ErrSourceReviewNotFound
	}
	wantStatus := input.Decision
	if item.Status != "pending" && item.Status != wantStatus {
		return SourceReviewItemRecord{}, ErrSourceReviewConflict
	}
	if item.Status == wantStatus {
		return item, nil
	}
	now := time.Now().UTC().Format(time.RFC3339)
	item.Status = wantStatus
	item.ReviewerID = principal.OrganizationID
	item.ReviewReason = strings.TrimSpace(input.Reason)
	item.UpdatedAt = now
	s.items[id] = item
	return item, nil
}

func validateSourceReviewInput(input SourceReviewReviewInput) error {
	if input.Decision != "approved" && input.Decision != "rejected" && input.Decision != "approve" && input.Decision != "reject" {
		return ErrInvalidSourceReview
	}
	if input.Decision == "approve" {
		input.Decision = "approved"
	} else if input.Decision == "reject" {
		input.Decision = "rejected"
	}
	if len([]rune(strings.TrimSpace(input.Reason))) > 2000 {
		return ErrInvalidSourceReview
	}
	return nil
}

func normalizedSourceReviewDecision(input SourceReviewReviewInput) SourceReviewReviewInput {
	input.Decision = strings.TrimSpace(strings.ToLower(input.Decision))
	if input.Decision == "approve" {
		input.Decision = "approved"
	} else if input.Decision == "reject" {
		input.Decision = "rejected"
	}
	input.Reason = strings.TrimSpace(input.Reason)
	return input
}
