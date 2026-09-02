CREATE TABLE IF NOT EXISTS dataset_products (
    dataset_product_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_key text NOT NULL,
    product_version integer NOT NULL CHECK (product_version > 0),
    vehicle_selector jsonb NOT NULL,
    minimum_sections jsonb NOT NULL,
    price_minor bigint NOT NULL CHECK (price_minor >= 0),
    currency char(3) NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (product_key, product_version)
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    source_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    adapter_name text NOT NULL,
    source_uri text NOT NULL,
    source_version text NOT NULL,
    content_sha256 char(64) NOT NULL UNIQUE,
    object_key text NOT NULL,
    license_metadata jsonb NOT NULL,
    takedown_status text NOT NULL DEFAULT 'active'
        CHECK (takedown_status IN ('active', 'takedown', 'expired')),
    retrieved_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payment_events (
    payment_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name text NOT NULL,
    provider_event_id text NOT NULL UNIQUE,
    event_type text NOT NULL,
    verified boolean NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_requests (
    dataset_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_product_id uuid NOT NULL REFERENCES dataset_products(dataset_product_id),
    vehicle_key text NOT NULL,
    region text NOT NULL,
    status text NOT NULL CHECK (status IN (
        'purchased', 'fast_lane_processing', 'viewable', 'enriching',
        'complete', 'failed', 'needs_review', 'revoked'
    )),
    lane text NOT NULL CHECK (lane IN ('fast', 'deep')),
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    correlation_id uuid NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    processing_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entitlements (
    entitlement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    dataset_request_id uuid NOT NULL REFERENCES dataset_requests(dataset_request_id),
    payment_event_id uuid REFERENCES payment_events(payment_event_id),
    provider_event_id text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('active', 'revoked')),
    granted_at timestamptz NOT NULL,
    revoked_at timestamptz,
    revoke_reason text,
    UNIQUE (organization_id, dataset_request_id)
);

CREATE TABLE IF NOT EXISTS dataset_projections (
    dataset_projection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_product_id uuid NOT NULL REFERENCES dataset_products(dataset_product_id),
    dataset_request_id uuid NOT NULL UNIQUE REFERENCES dataset_requests(dataset_request_id),
    entitlement_id uuid NOT NULL UNIQUE REFERENCES entitlements(entitlement_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_revisions (
    dataset_revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_projection_id uuid NOT NULL REFERENCES dataset_projections(dataset_projection_id),
    revision_number integer NOT NULL CHECK (revision_number > 0),
    availability text NOT NULL CHECK (availability IN ('viewable', 'complete', 'needs_review', 'revoked')),
    source_watermark text NOT NULL,
    schema_version integer NOT NULL CHECK (schema_version > 0),
    changelog jsonb NOT NULL,
    content jsonb NOT NULL,
    published_at timestamptz,
    UNIQUE (dataset_projection_id, revision_number)
);

CREATE TABLE IF NOT EXISTS dataset_section_status (
    dataset_section_status_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_projection_id uuid NOT NULL REFERENCES dataset_projections(dataset_projection_id),
    section_name text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'processing', 'viewable', 'complete', 'failed', 'needs_review')),
    last_published_revision_id uuid REFERENCES dataset_revisions(dataset_revision_id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_projection_id, section_name)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    ingestion_job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_request_id uuid NOT NULL REFERENCES dataset_requests(dataset_request_id),
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    lane text NOT NULL CHECK (lane IN ('fast', 'deep')),
    processing_version text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    extraction_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_job_id uuid REFERENCES ingestion_jobs(ingestion_job_id),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    processor_name text NOT NULL,
    processor_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'needs_review')),
    confidence numeric(5, 4) CHECK (confidence >= 0 AND confidence <= 1),
    input_hash char(64) NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS extraction_evidence (
    extraction_evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_run_id uuid REFERENCES extraction_runs(extraction_run_id),
    locator text NOT NULL,
    artifact_key text NOT NULL,
    extracted_text text NOT NULL,
    confidence numeric(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    embedding vector(1536),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS publication_events (
    publication_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type text NOT NULL,
    event_version integer NOT NULL CHECK (event_version > 0),
    dataset_request_id uuid REFERENCES dataset_requests(dataset_request_id),
    dataset_projection_id uuid REFERENCES dataset_projections(dataset_projection_id),
    dataset_revision_id uuid REFERENCES dataset_revisions(dataset_revision_id),
    correlation_id uuid NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback_items (
    feedback_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    dataset_projection_id uuid NOT NULL REFERENCES dataset_projections(dataset_projection_id),
    dataset_revision_id uuid REFERENCES dataset_revisions(dataset_revision_id),
    category text NOT NULL CHECK (category IN ('correction', 'missing', 'quality', 'safety')),
    body text NOT NULL,
    status text NOT NULL CHECK (status IN ('open', 'in_review', 'resolved', 'rejected')),
    reviewer_id uuid,
    applied_revision_id uuid REFERENCES dataset_revisions(dataset_revision_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dataset_revisions_projection_idx
    ON dataset_revisions (dataset_projection_id, revision_number DESC);
CREATE INDEX IF NOT EXISTS extraction_evidence_embedding_idx
    ON extraction_evidence USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION prevent_published_revision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION 'published dataset revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS dataset_revisions_immutable ON dataset_revisions;
CREATE TRIGGER dataset_revisions_immutable
    BEFORE UPDATE OR DELETE ON dataset_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_published_revision_mutation();

INSERT INTO schema_migrations (version)
VALUES ('002_platform_spine')
ON CONFLICT (version) DO NOTHING;
