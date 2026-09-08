package main

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type postgresSourceReviewStore struct {
	pool *pgxpool.Pool
}

func newPostgresSourceReviewStore(pool *pgxpool.Pool) *postgresSourceReviewStore {
	return &postgresSourceReviewStore{pool: pool}
}

func (s *postgresSourceReviewStore) List(_ Principal, status string, limit int) (SourceReviewQueueRecord, error) {
	rows, err := s.pool.Query(context.Background(), `
		SELECT source_review_item_id::text, item_key, item_kind, reason_code, status,
		       source_snapshot_ids, extraction_evidence_ids, payload,
		       COALESCE(reviewer_id, ''), COALESCE(review_reason, ''),
		       created_at::text, updated_at::text
		FROM source_review_items
		WHERE status = $1
		ORDER BY created_at, source_review_item_id
		LIMIT $2`, status, limit)
	if err != nil {
		return SourceReviewQueueRecord{}, err
	}
	defer rows.Close()
	items := []SourceReviewItemRecord{}
	for rows.Next() {
		item, err := scanSourceReviewItem(rows)
		if err != nil {
			return SourceReviewQueueRecord{}, err
		}
		items = append(items, item)
	}
	if err := rows.Err(); err != nil {
		return SourceReviewQueueRecord{}, err
	}
	return SourceReviewQueueRecord{Status: status, Items: items}, nil
}

func (s *postgresSourceReviewStore) Review(id string, input SourceReviewReviewInput, principal Principal) (SourceReviewItemRecord, error) {
	input = normalizedSourceReviewDecision(input)
	if err := validateSourceReviewInput(input); err != nil {
		return SourceReviewItemRecord{}, err
	}
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return SourceReviewItemRecord{}, err
	}
	defer tx.Rollback(context.Background())
	item, err := scanSourceReviewItem(tx.QueryRow(context.Background(), `
		SELECT source_review_item_id::text, item_key, item_kind, reason_code, status,
		       source_snapshot_ids, extraction_evidence_ids, payload,
		       COALESCE(reviewer_id, ''), COALESCE(review_reason, ''),
		       created_at::text, updated_at::text
		FROM source_review_items
		WHERE source_review_item_id::text = $1
		FOR UPDATE`, id))
	if errors.Is(err, pgx.ErrNoRows) {
		return SourceReviewItemRecord{}, ErrSourceReviewNotFound
	}
	if err != nil {
		return SourceReviewItemRecord{}, err
	}
	wantStatus := input.Decision
	if item.Status != "pending" && item.Status != wantStatus {
		return SourceReviewItemRecord{}, ErrSourceReviewConflict
	}
	if item.Status == wantStatus {
		return item, nil
	}
	now := time.Now().UTC().Format(time.RFC3339)
	if _, err := tx.Exec(context.Background(), `
		UPDATE source_review_items
		SET status = $2, reviewer_id = $3, review_reason = $4, updated_at = $5
		WHERE source_review_item_id::text = $1`, id, wantStatus, principal.OrganizationID, input.Reason, now); err != nil {
		return SourceReviewItemRecord{}, err
	}
	item.Status = wantStatus
	item.ReviewerID = principal.OrganizationID
	item.ReviewReason = input.Reason
	item.UpdatedAt = now
	if err := tx.Commit(context.Background()); err != nil {
		return SourceReviewItemRecord{}, err
	}
	return item, nil
}

type sourceReviewScanner interface {
	Scan(...any) error
}

func scanSourceReviewItem(scanner sourceReviewScanner) (SourceReviewItemRecord, error) {
	var item SourceReviewItemRecord
	var snapshotsJSON, evidenceJSON, payloadJSON []byte
	if err := scanner.Scan(
		&item.SourceReviewItemID, &item.ItemKey, &item.ItemKind, &item.ReasonCode,
		&item.Status, &snapshotsJSON, &evidenceJSON, &payloadJSON,
		&item.ReviewerID, &item.ReviewReason, &item.CreatedAt, &item.UpdatedAt,
	); err != nil {
		return SourceReviewItemRecord{}, err
	}
	if err := json.Unmarshal(snapshotsJSON, &item.SourceSnapshotIDs); err != nil {
		return SourceReviewItemRecord{}, err
	}
	if err := json.Unmarshal(evidenceJSON, &item.EvidenceIDs); err != nil {
		return SourceReviewItemRecord{}, err
	}
	if err := json.Unmarshal(payloadJSON, &item.Payload); err != nil {
		return SourceReviewItemRecord{}, err
	}
	return item, nil
}
