package main

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/lucronn/autodata/packages/contracts/go"
)

// postgresProjectionStore keeps entitlement and projection authorization in the
// same database boundary as the purchaser-facing read. A later managed-
// database adapter can satisfy ProjectionStore without changing the API.
type postgresProjectionStore struct {
	pool *pgxpool.Pool
}

func newPostgresProjectionStore(ctx context.Context) (*postgresProjectionStore, error) {
	address := os.Getenv("AUTODATA_DB_ADDRESS")
	if address == "" {
		address = "postgres:5432"
	}
	host, port := splitDatabaseAddress(address)
	databaseURL := &url.URL{
		Scheme: "postgres",
		Host:   net.JoinHostPort(host, port),
		Path:   "/" + envOrDefault("AUTODATA_POSTGRES_DB", "autodata"),
		User:   url.UserPassword(envOrDefault("AUTODATA_POSTGRES_USER", "autodata"), os.Getenv("AUTODATA_POSTGRES_PASSWORD")),
	}
	config, err := pgxpool.ParseConfig(databaseURL.String())
	if err != nil {
		return nil, err
	}
	config.MaxConns = int32(envInt("AUTODATA_API_DB_MAX_CONNS", 8))
	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, err
	}
	pingContext, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	if err := pool.Ping(pingContext); err != nil {
		pool.Close()
		return nil, err
	}
	return &postgresProjectionStore{pool: pool}, nil
}

func (s *postgresProjectionStore) Close() {
	if s.pool != nil {
		s.pool.Close()
	}
}

func (s *postgresProjectionStore) GetDataset(datasetID string, principal Principal, revisionID string) (DatasetReadRecord, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return DatasetReadRecord{}, err
	}
	revision, err := s.revision(datasetID, revisionID)
	if err != nil {
		return DatasetReadRecord{}, err
	}
	sections, err := s.sections(datasetID)
	if err != nil {
		return DatasetReadRecord{}, err
	}
	return DatasetReadRecord{
		DatasetID:       datasetID,
		RevisionID:      revision.RevisionID,
		Availability:    revision.Availability,
		SourceWatermark: revision.SourceWatermark,
		Sections:        sections,
		Data:            revision.Data,
		Warnings:        sectionWarnings(sections),
	}, nil
}

func (s *postgresProjectionStore) ListSections(datasetID string, principal Principal) (DatasetReadRecord, error) {
	record, err := s.GetDataset(datasetID, principal, "")
	if err != nil {
		return DatasetReadRecord{}, err
	}
	record.Data = nil
	record.Warnings = nil
	return record, nil
}

func (s *postgresProjectionStore) ListRevisions(datasetID string, principal Principal) (DatasetRevisionList, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return DatasetRevisionList{}, err
	}
	rows, err := s.pool.Query(context.Background(), `
		SELECT dataset_revision_id::text, revision_number, availability,
		       source_watermark, changelog, content, COALESCE(published_at::text, '')
		FROM dataset_revisions
		WHERE dataset_projection_id = $1 AND published_at IS NOT NULL
		ORDER BY revision_number DESC`, datasetID)
	if err != nil {
		return DatasetRevisionList{}, err
	}
	defer rows.Close()
	result := DatasetRevisionList{DatasetID: datasetID, Revisions: []DatasetRevisionRecord{}}
	for rows.Next() {
		revision, err := scanRevision(rows)
		if err != nil {
			return DatasetRevisionList{}, err
		}
		result.Revisions = append(result.Revisions, revision)
	}
	if err := rows.Err(); err != nil {
		return DatasetRevisionList{}, err
	}
	return result, nil
}

func (s *postgresProjectionStore) GetEvidence(datasetID, evidenceID string, principal Principal) (EvidenceRecord, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return EvidenceRecord{}, err
	}
	evidence, err := scanEvidence(s.pool.QueryRow(context.Background(), `
		SELECT ee.extraction_evidence_id::text, ee.source_snapshot_id::text,
		       ee.extraction_run_id::text, ee.dataset_revision_id::text,
		       ee.locator, ee.artifact_key, ee.extracted_text,
		       ee.confidence, ee.reviewer_state, ee.reviewer_id::text,
		       ee.reviewed_at::text, ee.review_reason
		FROM extraction_evidence ee
		JOIN dataset_requests dr ON dr.source_snapshot_id = ee.source_snapshot_id
		JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
		JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
		WHERE dp.dataset_projection_id = $1
		  AND ee.extraction_evidence_id = $2
		  AND e.organization_id::text = $3
		  AND ee.dataset_revision_id IS NOT NULL`, datasetID, evidenceID, principal.OrganizationID))
	if errors.Is(err, pgx.ErrNoRows) {
		return EvidenceRecord{}, ErrInvalidEvidence
	}
	if err != nil {
		return EvidenceRecord{}, err
	}
	if evidence.ReviewerState != "approved" {
		return EvidenceRecord{}, ErrReviewRequired
	}
	return evidence, nil
}

func (s *postgresProjectionStore) SearchEvidence(datasetID string, query []float64, limit int, principal Principal) (EvidenceSearchResponse, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return EvidenceSearchResponse{}, err
	}
	vector, err := formatPGVector(query)
	if err != nil {
		return EvidenceSearchResponse{}, err
	}
	rows, err := s.pool.Query(context.Background(), `
		SELECT ee.extraction_evidence_id::text, ee.dataset_revision_id::text,
		       ee.locator, ee.extracted_text, ee.confidence,
		       1 - (ee.embedding <=> $2::vector) AS score
		FROM extraction_evidence ee
		JOIN dataset_revisions dvr ON dvr.dataset_revision_id = ee.dataset_revision_id
		WHERE dvr.dataset_projection_id = $1
		  AND dvr.published_at IS NOT NULL
		  AND ee.reviewer_state = 'approved'
		  AND ee.embedding IS NOT NULL
		ORDER BY ee.embedding <=> $2::vector, ee.extraction_evidence_id
		LIMIT $3`, datasetID, vector, limit)
	if err != nil {
		return EvidenceSearchResponse{}, err
	}
	defer rows.Close()
	result := EvidenceSearchResponse{DatasetID: datasetID, Results: []EvidenceSearchHit{}}
	for rows.Next() {
		var hit EvidenceSearchHit
		if err := rows.Scan(&hit.EvidenceID, &hit.RevisionID, &hit.Locator, &hit.ExtractedText, &hit.Confidence, &hit.Score); err != nil {
			return EvidenceSearchResponse{}, err
		}
		result.Results = append(result.Results, hit)
	}
	if err := rows.Err(); err != nil {
		return EvidenceSearchResponse{}, err
	}
	return result, nil
}

func (s *postgresProjectionStore) SubmitFeedback(datasetID string, input FeedbackInput, principal Principal) (FeedbackRecord, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return FeedbackRecord{}, err
	}
	if err := validateFeedbackInput(input); err != nil {
		return FeedbackRecord{}, err
	}
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return FeedbackRecord{}, err
	}
	defer tx.Rollback(context.Background())
	revisionID := input.RevisionID
	if revisionID != "" {
		var exists bool
		if err := tx.QueryRow(context.Background(), `
			SELECT EXISTS (
				SELECT 1 FROM dataset_revisions
				WHERE dataset_revision_id::text = $1
				  AND dataset_projection_id = $2
				  AND published_at IS NOT NULL
			)`, revisionID, datasetID).Scan(&exists); err != nil {
			return FeedbackRecord{}, err
		}
		if !exists {
			return FeedbackRecord{}, ErrRevisionNotFound
		}
	}
	if input.EvidenceID != "" {
		var reviewerState string
		var evidenceRevisionID *string
		err := tx.QueryRow(context.Background(), `
			SELECT ee.reviewer_state, ee.dataset_revision_id::text
			FROM extraction_evidence ee
			JOIN dataset_revisions dvr ON dvr.dataset_revision_id = ee.dataset_revision_id
			WHERE ee.extraction_evidence_id::text = $1
			  AND dvr.dataset_projection_id = $2
			  AND dvr.published_at IS NOT NULL`, input.EvidenceID, datasetID).
			Scan(&reviewerState, &evidenceRevisionID)
		if errors.Is(err, pgx.ErrNoRows) {
			return FeedbackRecord{}, ErrInvalidEvidence
		}
		if err != nil {
			return FeedbackRecord{}, err
		}
		if reviewerState != "approved" {
			return FeedbackRecord{}, ErrReviewRequired
		}
		if evidenceRevisionID != nil {
			if revisionID != "" && revisionID != *evidenceRevisionID {
				return FeedbackRecord{}, ErrInvalidFeedback
			}
			revisionID = *evidenceRevisionID
		}
	}
	var record FeedbackRecord
	var recordRevisionID, recordEvidenceID *string
	err = tx.QueryRow(context.Background(), `
		INSERT INTO feedback_items
			(organization_id, dataset_projection_id, dataset_revision_id,
			 extraction_evidence_id, category, body, status)
		VALUES ($1, $2, NULLIF($3, '')::uuid, NULLIF($4, '')::uuid, $5, $6, 'open')
		RETURNING feedback_item_id::text, dataset_revision_id::text,
		          extraction_evidence_id::text, category, body, status, created_at::text`,
		principal.OrganizationID, datasetID, revisionID, input.EvidenceID,
		input.Category, strings.TrimSpace(input.Body)).
		Scan(&record.FeedbackID, &recordRevisionID, &recordEvidenceID,
			&record.Category, &record.Body, &record.Status, &record.CreatedAt)
	if err != nil {
		return FeedbackRecord{}, err
	}
	record.DatasetID = datasetID
	if recordRevisionID != nil {
		record.RevisionID = *recordRevisionID
	}
	if recordEvidenceID != nil {
		record.EvidenceID = *recordEvidenceID
	}
	if err := tx.Commit(context.Background()); err != nil {
		return FeedbackRecord{}, err
	}
	return record, nil
}

func (s *postgresProjectionStore) ReviewEvidence(datasetID, evidenceID string, input EvidenceReviewInput, principal Principal) (EvidenceRecord, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return EvidenceRecord{}, err
	}
	if err := validateEvidenceReview(input); err != nil {
		return EvidenceRecord{}, err
	}
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return EvidenceRecord{}, err
	}
	defer tx.Rollback(context.Background())
	evidence, err := scanEvidence(tx.QueryRow(context.Background(), `
		SELECT ee.extraction_evidence_id::text, ee.source_snapshot_id::text,
		       ee.extraction_run_id::text, ee.dataset_revision_id::text,
		       ee.locator, ee.artifact_key, ee.extracted_text,
		       ee.confidence, ee.reviewer_state, ee.reviewer_id::text,
		       ee.reviewed_at::text, ee.review_reason
		FROM extraction_evidence ee
		JOIN dataset_requests dr ON dr.source_snapshot_id = ee.source_snapshot_id
		JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
		WHERE dp.dataset_projection_id = $1
		  AND ee.extraction_evidence_id::text = $2
		FOR UPDATE`, datasetID, evidenceID))
	if errors.Is(err, pgx.ErrNoRows) {
		return EvidenceRecord{}, ErrInvalidEvidence
	}
	if err != nil {
		return EvidenceRecord{}, err
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
		var reviewedAt *string
		if err := tx.QueryRow(context.Background(), `
			UPDATE extraction_evidence
			SET reviewer_state = $1, reviewer_id = NULLIF($2, '')::uuid,
			    reviewed_at = now(), review_reason = $3
			WHERE extraction_evidence_id::text = $4
			RETURNING reviewed_at::text`, wantState, principal.OrganizationID,
			strings.TrimSpace(input.Reason), evidenceID).Scan(&reviewedAt); err != nil {
			return EvidenceRecord{}, err
		}
		evidence.ReviewerState = wantState
		evidence.ReviewerID = stringPointer(principal.OrganizationID)
		evidence.ReviewedAt = reviewedAt
		evidence.ReviewReason = strings.TrimSpace(input.Reason)
	}
	if err := tx.Commit(context.Background()); err != nil {
		return EvidenceRecord{}, err
	}
	return evidence, nil
}

func (s *postgresProjectionStore) ReviewFeedback(datasetID, feedbackID string, input FeedbackReviewInput, principal Principal) (FeedbackRecord, error) {
	if err := s.authorize(datasetID, principal); err != nil {
		return FeedbackRecord{}, err
	}
	if err := validateFeedbackReview(input); err != nil {
		return FeedbackRecord{}, err
	}
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return FeedbackRecord{}, err
	}
	defer tx.Rollback(context.Background())
	feedback, err := scanFeedback(tx.QueryRow(context.Background(), `
		SELECT feedback_item_id::text, dataset_revision_id::text,
		       extraction_evidence_id::text, category, body, status,
		       created_at::text, applied_revision_id::text,
		       reviewer_id::text, reviewed_at::text, review_reason
		FROM feedback_items
		WHERE dataset_projection_id = $1
		  AND feedback_item_id::text = $2
		  AND organization_id::text = $3
		FOR UPDATE`, datasetID, feedbackID, principal.OrganizationID))
	if errors.Is(err, pgx.ErrNoRows) {
		return FeedbackRecord{}, ErrFeedbackNotFound
	}
	if err != nil {
		return FeedbackRecord{}, err
	}
	feedback.DatasetID = datasetID
	wantStatus := "rejected"
	if input.Decision == "resolve" {
		wantStatus = "resolved"
		if input.AppliedRevisionID == "" {
			return FeedbackRecord{}, ErrInvalidFeedbackReview
		}
		var exists bool
		if err := tx.QueryRow(context.Background(), `
			SELECT EXISTS (
				SELECT 1 FROM dataset_revisions
				WHERE dataset_revision_id::text = $1
				  AND dataset_projection_id = $2
				  AND published_at IS NOT NULL
			)`, input.AppliedRevisionID, datasetID).Scan(&exists); err != nil {
			return FeedbackRecord{}, err
		}
		if !exists {
			return FeedbackRecord{}, ErrRevisionNotFound
		}
	} else if input.AppliedRevisionID != "" {
		return FeedbackRecord{}, ErrInvalidFeedbackReview
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
	var appliedRevisionID, reviewerID, reviewedAt, reviewReason *string
	if err := tx.QueryRow(context.Background(), `
		UPDATE feedback_items
		SET status = $1, applied_revision_id = NULLIF($2, '')::uuid,
		    reviewer_id = NULLIF($3, '')::uuid, reviewed_at = now(),
		    review_reason = $4
		WHERE feedback_item_id::text = $5
		RETURNING applied_revision_id::text, reviewer_id::text,
		          reviewed_at::text, review_reason`, wantStatus,
		input.AppliedRevisionID, principal.OrganizationID, strings.TrimSpace(input.Reason), feedbackID).
		Scan(&appliedRevisionID, &reviewerID, &reviewedAt, &reviewReason); err != nil {
		return FeedbackRecord{}, err
	}
	feedback.Status = wantStatus
	if appliedRevisionID != nil {
		feedback.AppliedRevisionID = *appliedRevisionID
	}
	feedback.ReviewerID = reviewerID
	feedback.ReviewedAt = reviewedAt
	if reviewReason != nil {
		feedback.ReviewReason = *reviewReason
	}
	if err := tx.Commit(context.Background()); err != nil {
		return FeedbackRecord{}, err
	}
	return feedback, nil
}

func scanEvidence(row rowScanner) (EvidenceRecord, error) {
	var evidence EvidenceRecord
	var reviewReason *string
	if err := row.Scan(
		&evidence.EvidenceID, &evidence.SourceSnapshotID, &evidence.ExtractionRunID,
		&evidence.DatasetRevisionID, &evidence.Locator, &evidence.ArtifactKey,
		&evidence.ExtractedText, &evidence.Confidence, &evidence.ReviewerState,
		&evidence.ReviewerID, &evidence.ReviewedAt, &reviewReason,
	); err != nil {
		return EvidenceRecord{}, err
	}
	if reviewReason != nil {
		evidence.ReviewReason = *reviewReason
	}
	return evidence, nil
}

func scanFeedback(row rowScanner) (FeedbackRecord, error) {
	var record FeedbackRecord
	var revisionID, evidenceID, appliedRevisionID, reviewerID, reviewedAt, reviewReason *string
	if err := row.Scan(
		&record.FeedbackID, &revisionID, &evidenceID,
		&record.Category, &record.Body, &record.Status, &record.CreatedAt,
		&appliedRevisionID, &reviewerID, &reviewedAt,
		&reviewReason,
	); err != nil {
		return FeedbackRecord{}, err
	}
	if revisionID != nil {
		record.RevisionID = *revisionID
	}
	if evidenceID != nil {
		record.EvidenceID = *evidenceID
	}
	if appliedRevisionID != nil {
		record.AppliedRevisionID = *appliedRevisionID
	}
	record.ReviewerID = reviewerID
	record.ReviewedAt = reviewedAt
	if reviewReason != nil {
		record.ReviewReason = *reviewReason
	}
	return record, nil
}

func stringPointer(value string) *string {
	return &value
}

func (s *postgresProjectionStore) authorize(datasetID string, principal Principal) error {
	var entitlementStatus, requestStatus string
	err := s.pool.QueryRow(context.Background(), `
		SELECT e.status, dr.status
		FROM dataset_projections dp
		JOIN dataset_requests dr ON dr.dataset_request_id = dp.dataset_request_id
		JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
		WHERE dp.dataset_projection_id = $1
		  AND e.organization_id::text = $2`, datasetID, principal.OrganizationID).
		Scan(&entitlementStatus, &requestStatus)
	if errors.Is(err, pgx.ErrNoRows) {
		var exists bool
		if err := s.pool.QueryRow(context.Background(), `SELECT EXISTS (SELECT 1 FROM dataset_projections WHERE dataset_projection_id = $1)`, datasetID).Scan(&exists); err != nil {
			return err
		}
		if !exists {
			return ErrDatasetNotFound
		}
		return ErrEntitlementRequired
	}
	if err != nil {
		return err
	}
	if entitlementStatus == "revoked" || requestStatus == "revoked" {
		return ErrEntitlementRevoked
	}
	return nil
}

func (s *postgresProjectionStore) revision(datasetID, revisionID string) (DatasetRevisionRecord, error) {
	query := `
		SELECT dataset_revision_id::text, revision_number, availability,
		       source_watermark, changelog, content, COALESCE(published_at::text, '')
		FROM dataset_revisions
		WHERE dataset_projection_id = $1 AND published_at IS NOT NULL`
	args := []any{datasetID}
	if revisionID != "" {
		query += " AND dataset_revision_id::text = $2"
		args = append(args, revisionID)
	}
	query += " ORDER BY revision_number DESC LIMIT 1"
	revision, err := scanRevision(s.pool.QueryRow(context.Background(), query, args...))
	if errors.Is(err, pgx.ErrNoRows) {
		if revisionID != "" {
			return DatasetRevisionRecord{}, ErrRevisionNotFound
		}
		return DatasetRevisionRecord{}, ErrDatasetNotViewable
	}
	return revision, err
}

func (s *postgresProjectionStore) sections(datasetID string) ([]contracts.DatasetSection, error) {
	rows, err := s.pool.Query(context.Background(), `
		SELECT section_name, status, last_published_revision_id::text, updated_at::text
		FROM dataset_section_status
		WHERE dataset_projection_id = $1
		ORDER BY section_name`, datasetID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	sections := make([]contracts.DatasetSection, 0)
	for rows.Next() {
		var section contracts.DatasetSection
		if err := rows.Scan(&section.Name, &section.Status, &section.LastPublishedRevision, &section.UpdatedAt); err != nil {
			return nil, err
		}
		sections = append(sections, section)
	}
	return sections, rows.Err()
}

type rowScanner interface {
	Scan(...any) error
}

func scanRevision(row rowScanner) (DatasetRevisionRecord, error) {
	var revision DatasetRevisionRecord
	var changelogJSON, contentJSON []byte
	err := row.Scan(&revision.RevisionID, &revision.RevisionNumber, &revision.Availability,
		&revision.SourceWatermark, &changelogJSON, &contentJSON, &revision.PublishedAt)
	if err != nil {
		return DatasetRevisionRecord{}, err
	}
	if err := json.Unmarshal(changelogJSON, &revision.Changelog); err != nil {
		return DatasetRevisionRecord{}, err
	}
	if len(contentJSON) > 0 && string(contentJSON) != "null" {
		if err := json.Unmarshal(contentJSON, &revision.Data); err != nil {
			return DatasetRevisionRecord{}, err
		}
	}
	return revision, nil
}

func splitDatabaseAddress(address string) (string, string) {
	host, port, err := net.SplitHostPort(address)
	if err == nil {
		return host, port
	}
	parts := strings.Split(address, ":")
	if len(parts) == 2 && parts[1] != "" {
		return parts[0], parts[1]
	}
	return address, "5432"
}

func envInt(name string, fallback int) int {
	value, err := strconv.Atoi(os.Getenv(name))
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}
