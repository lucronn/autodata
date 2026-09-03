package main

import (
	"context"
	"encoding/json"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/lucronn/autodata/packages/contracts/go"
)

// requestDatabase and requestTx keep the SQL request store testable without
// replacing the production pgx pool or requiring a live database for unit
// tests.
type requestDatabase interface {
	Begin(context.Context) (requestTx, error)
	QueryRow(context.Context, string, ...any) pgx.Row
}

type requestTx interface {
	QueryRow(context.Context, string, ...any) pgx.Row
	Commit(context.Context) error
	Rollback(context.Context) error
}

type poolRequestDatabase struct {
	pool *pgxpool.Pool
}

func (d poolRequestDatabase) Begin(ctx context.Context) (requestTx, error) {
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	return poolRequestTx{tx: tx}, nil
}

func (d poolRequestDatabase) QueryRow(ctx context.Context, query string, args ...any) pgx.Row {
	return d.pool.QueryRow(ctx, query, args...)
}

type poolRequestTx struct {
	tx pgx.Tx
}

func (t poolRequestTx) QueryRow(ctx context.Context, query string, args ...any) pgx.Row {
	return t.tx.QueryRow(ctx, query, args...)
}

func (t poolRequestTx) Commit(ctx context.Context) error {
	return t.tx.Commit(ctx)
}

func (t poolRequestTx) Rollback(ctx context.Context) error {
	return t.tx.Rollback(ctx)
}

// postgresRequestStore is the durable request boundary used by the running
// API when PostgreSQL projection reads are enabled. Request ownership is
// stored separately from entitlement state so a request can be polled while
// payment fulfillment is still delayed.
type postgresRequestStore struct {
	db requestDatabase
}

func newPostgresRequestStore(pool *pgxpool.Pool) *postgresRequestStore {
	return &postgresRequestStore{db: poolRequestDatabase{pool: pool}}
}

func (s *postgresRequestStore) Create(
	principal Principal, input DatasetRequestInput, idempotencyKey string,
) (DatasetRequestRecord, bool, error) {
	if !validUUID(principal.OrganizationID) || !validUUID(input.ProductID) ||
		strings.TrimSpace(input.VehicleKey) == "" || strings.TrimSpace(input.Region) == "" ||
		strings.TrimSpace(idempotencyKey) == "" {
		return DatasetRequestRecord{}, false, ErrInvalidRequest
	}

	ctx := context.Background()
	tx, err := s.db.Begin(ctx)
	if err != nil {
		return DatasetRequestRecord{}, false, err
	}
	defer tx.Rollback(ctx)

	var record DatasetRequestRecord
	var createdAt string
	err = tx.QueryRow(ctx, `
		INSERT INTO dataset_requests
			(dataset_product_id, vehicle_key, region, status, lane,
			 correlation_id, idempotency_key, processing_version, organization_id)
		SELECT dataset_product_id, $2, upper($3), 'fast_lane_processing', 'fast',
		       gen_random_uuid(), $4, 'fast-v1', $5::uuid
		FROM dataset_products
		WHERE dataset_product_id = $1::uuid
		ON CONFLICT (idempotency_key) DO NOTHING
		RETURNING dataset_request_id::text, dataset_product_id::text,
		          vehicle_key, region, status, organization_id::text,
		          created_at::text`, input.ProductID, input.VehicleKey, input.Region,
		idempotencyKey, principal.OrganizationID).Scan(
		&record.DatasetRequestID, &record.ProductID, &record.VehicleKey,
		&record.Region, &record.Status, &record.OrganizationID, &createdAt)
	if err == nil {
		var minimumSections []byte
		if err := tx.QueryRow(ctx, `
			SELECT minimum_sections
			FROM dataset_products
			WHERE dataset_product_id = $1::uuid`, input.ProductID).Scan(&minimumSections); err != nil {
			return DatasetRequestRecord{}, false, err
		}
		record.Sections, err = pendingRequestSections(minimumSections, createdAt)
		if err != nil {
			return DatasetRequestRecord{}, false, err
		}
		if err := tx.Commit(ctx); err != nil {
			return DatasetRequestRecord{}, false, err
		}
		return record, false, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return DatasetRequestRecord{}, false, err
	}

	// ON CONFLICT DO NOTHING returns no row for an idempotency replay. The
	// existing row is read inside the same transaction so the replay cannot
	// accidentally create a second request or cross organization boundaries.
	record, err = scanDatasetRequest(tx.QueryRow(ctx, requestByIdempotencyQuery, idempotencyKey))
	if errors.Is(err, pgx.ErrNoRows) {
		// A valid UUID with no product is a client error; it must not be retried
		// as if the database were unavailable.
		return DatasetRequestRecord{}, false, ErrInvalidRequest
	}
	if err != nil {
		return DatasetRequestRecord{}, false, err
	}
	if record.OrganizationID != principal.OrganizationID {
		return DatasetRequestRecord{}, false, ErrEntitlementRequired
	}
	if err := tx.Commit(ctx); err != nil {
		return DatasetRequestRecord{}, false, err
	}
	return record, true, nil
}

func (s *postgresRequestStore) Get(id string, principal Principal) (DatasetRequestRecord, error) {
	if !validUUID(id) || !validUUID(principal.OrganizationID) {
		return DatasetRequestRecord{}, ErrInvalidRequest
	}
	ctx := context.Background()
	record, err := scanDatasetRequest(s.db.QueryRow(ctx, requestByIDQuery), id, principal.OrganizationID)
	if err == nil {
		return record, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return DatasetRequestRecord{}, err
	}

	var exists bool
	if err := s.db.QueryRow(ctx, `
		SELECT EXISTS (
			SELECT 1 FROM dataset_requests WHERE dataset_request_id = $1::uuid
		)`, id).Scan(&exists); err != nil {
		return DatasetRequestRecord{}, err
	}
	if !exists {
		return DatasetRequestRecord{}, ErrRequestNotFound
	}
	return DatasetRequestRecord{}, ErrEntitlementRequired
}

const requestByIdempotencyQuery = `
	SELECT dr.dataset_request_id::text, dr.dataset_product_id::text,
	       dr.vehicle_key, dr.region, dr.status,
	       COALESCE(dr.organization_id::text, ''), dr.created_at::text,
	       p.minimum_sections,
	       COALESCE((
		   SELECT jsonb_agg(jsonb_build_object(
			   'name', ds.section_name,
			   'status', ds.status,
			   'last_published_revision', ds.last_published_revision_id::text,
			   'updated_at', ds.updated_at::text
		   ) ORDER BY ds.section_name)
		   FROM dataset_projections dp
		   JOIN dataset_section_status ds
		     ON ds.dataset_projection_id = dp.dataset_projection_id
		   WHERE dp.dataset_request_id = dr.dataset_request_id
	       ), '[]'::jsonb)
	FROM dataset_requests dr
	JOIN dataset_products p ON p.dataset_product_id = dr.dataset_product_id
	WHERE dr.idempotency_key = $1`

const requestByIDQuery = `
	SELECT dr.dataset_request_id::text, dr.dataset_product_id::text,
	       dr.vehicle_key, dr.region, dr.status,
	       COALESCE(dr.organization_id::text, ''), dr.created_at::text,
	       p.minimum_sections,
	       COALESCE((
		   SELECT jsonb_agg(jsonb_build_object(
			   'name', ds.section_name,
			   'status', ds.status,
			   'last_published_revision', ds.last_published_revision_id::text,
			   'updated_at', ds.updated_at::text
		   ) ORDER BY ds.section_name)
		   FROM dataset_projections dp
		   JOIN dataset_section_status ds
		     ON ds.dataset_projection_id = dp.dataset_projection_id
		   WHERE dp.dataset_request_id = dr.dataset_request_id
	       ), '[]'::jsonb)
	FROM dataset_requests dr
	JOIN dataset_products p ON p.dataset_product_id = dr.dataset_product_id
	WHERE dr.dataset_request_id = $1::uuid
	  AND dr.organization_id = $2::uuid`

func scanDatasetRequest(row pgx.Row, _ ...any) (DatasetRequestRecord, error) {
	var record DatasetRequestRecord
	var createdAt string
	var minimumSections, sectionsJSON []byte
	if err := row.Scan(
		&record.DatasetRequestID, &record.ProductID, &record.VehicleKey,
		&record.Region, &record.Status, &record.OrganizationID, &createdAt,
		&minimumSections, &sectionsJSON,
	); err != nil {
		return DatasetRequestRecord{}, err
	}
	sections, err := decodeRequestSections(sectionsJSON, minimumSections, createdAt)
	if err != nil {
		return DatasetRequestRecord{}, err
	}
	record.Sections = sections
	return record, nil
}

func pendingRequestSections(minimumSections []byte, updatedAt string) ([]contracts.DatasetSection, error) {
	var names []string
	if err := json.Unmarshal(minimumSections, &names); err != nil {
		return nil, err
	}
	sections := make([]contracts.DatasetSection, 0, len(names))
	for _, name := range names {
		name = strings.TrimSpace(name)
		if name == "" {
			continue
		}
		sections = append(sections, contracts.DatasetSection{
			Name:      name,
			Status:    "pending",
			UpdatedAt: updatedAt,
		})
	}
	return sections, nil
}

func decodeRequestSections(
	sectionsJSON, minimumSections []byte, updatedAt string,
) ([]contracts.DatasetSection, error) {
	var sections []contracts.DatasetSection
	if len(sectionsJSON) > 0 && string(sectionsJSON) != "[]" && string(sectionsJSON) != "null" {
		if err := json.Unmarshal(sectionsJSON, &sections); err != nil {
			return nil, err
		}
		return sections, nil
	}
	return pendingRequestSections(minimumSections, updatedAt)
}

func validUUID(value string) bool {
	value = strings.TrimSpace(value)
	if len(value) != 36 || value[8] != '-' || value[13] != '-' || value[18] != '-' || value[23] != '-' {
		return false
	}
	for index, character := range value {
		if index == 8 || index == 13 || index == 18 || index == 23 {
			continue
		}
		if !((character >= '0' && character <= '9') ||
			(character >= 'a' && character <= 'f') ||
			(character >= 'A' && character <= 'F')) {
			return false
		}
	}
	return true
}
