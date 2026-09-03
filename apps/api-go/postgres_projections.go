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
	s.pool.Close()
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
	var evidence EvidenceRecord
	var extractionRunID *string
	var confidence float64
	var reviewerState string
	err := s.pool.QueryRow(context.Background(), `
		SELECT ee.extraction_evidence_id::text, ee.source_snapshot_id::text,
		       ee.extraction_run_id::text, ee.locator, ee.artifact_key,
		       ee.extracted_text, ee.confidence, ee.reviewer_state
		FROM extraction_evidence ee
		JOIN dataset_requests dr ON dr.source_snapshot_id = ee.source_snapshot_id
		JOIN dataset_projections dp ON dp.dataset_request_id = dr.dataset_request_id
		JOIN entitlements e ON e.entitlement_id = dp.entitlement_id
		WHERE dp.dataset_projection_id = $1
		  AND ee.extraction_evidence_id = $2
		  AND e.organization_id::text = $3`, datasetID, evidenceID, principal.OrganizationID).
		Scan(&evidence.EvidenceID, &evidence.SourceSnapshotID, &extractionRunID,
			&evidence.Locator, &evidence.ArtifactKey, &evidence.ExtractedText,
			&confidence, &reviewerState)
	if errors.Is(err, pgx.ErrNoRows) {
		return EvidenceRecord{}, ErrInvalidEvidence
	}
	if err != nil {
		return EvidenceRecord{}, err
	}
	evidence.ExtractionRunID = extractionRunID
	evidence.Confidence = confidence
	evidence.ReviewerState = reviewerState
	if reviewerState != "approved" {
		return EvidenceRecord{}, ErrReviewRequired
	}
	return evidence, nil
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
