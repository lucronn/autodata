CREATE TABLE IF NOT EXISTS chat_queries (
    query_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    message text NOT NULL CHECK (length(btrim(message)) > 0),
    idempotency_key text NOT NULL UNIQUE,
    correlation_id uuid NOT NULL,
    status text NOT NULL CHECK (status IN (
        'awaiting_vehicle', 'processing', 'available', 'failed', 'revoked'
    )),
    selected_vehicle_id uuid REFERENCES vehicles(vehicle_id),
    answer_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_watermark text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(answer_snapshot) = 'object')
);

CREATE TABLE IF NOT EXISTS chat_query_options (
    chat_query_option_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id uuid NOT NULL REFERENCES chat_queries(query_id),
    option_number integer NOT NULL CHECK (option_number > 0),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    display_label text NOT NULL,
    confidence numeric(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (query_id, option_number),
    UNIQUE (query_id, vehicle_id),
    CHECK (jsonb_typeof(evidence) = 'array')
);

CREATE TABLE IF NOT EXISTS chat_job_plans (
    chat_job_plan_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id uuid NOT NULL UNIQUE REFERENCES chat_queries(query_id),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    derived_article_identity text NOT NULL UNIQUE,
    request_fingerprint char(64) NOT NULL,
    status text NOT NULL CHECK (status IN (
        'pending', 'processing', 'available', 'complete', 'failed',
        'dead_letter', 'needs_review'
    )),
    processing_version text NOT NULL,
    source_watermarks jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_answer_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(source_watermarks) = 'array'),
    CHECK (jsonb_typeof(raw_answer_snapshot) = 'object')
);

CREATE TABLE IF NOT EXISTS parts_price_snapshots (
    parts_price_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_part_id text NOT NULL,
    source_part_number text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    amount numeric(12, 2) NOT NULL CHECK (amount >= 0),
    currency char(3) NOT NULL,
    priced_at timestamptz NOT NULL,
    freshness text NOT NULL CHECK (freshness IN ('fresh', 'stale', 'unknown')),
    refresh_status text NOT NULL CHECK (refresh_status IN (
        'current', 'queued', 'processing', 'failed'
    )),
    markup_applied boolean NOT NULL DEFAULT false CHECK (markup_applied = false),
    source_uri text,
    source_part_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (canonical_part_id, source_snapshot_id, priced_at),
    CHECK (jsonb_typeof(source_part_payload) = 'object')
);

CREATE TABLE IF NOT EXISTS chat_quote_revisions (
    chat_quote_revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_job_plan_id uuid NOT NULL REFERENCES chat_job_plans(chat_job_plan_id),
    revision_number integer NOT NULL CHECK (revision_number > 0),
    quote_fingerprint char(64) NOT NULL,
    required_hours numeric(8, 2) NOT NULL CHECK (required_hours >= 0),
    recommended_hours numeric(8, 2) NOT NULL CHECK (recommended_hours >= 0),
    total_hours numeric(8, 2) NOT NULL CHECK (total_hours >= 0),
    overlap_hours_removed numeric(8, 2) NOT NULL CHECK (overlap_hours_removed >= 0),
    overlap_operations jsonb NOT NULL DEFAULT '[]'::jsonb,
    parts jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    procedure jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_watermarks jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL CHECK (status IN ('provisional', 'published', 'needs_review', 'failed')),
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (chat_job_plan_id, revision_number),
    UNIQUE (chat_job_plan_id, quote_fingerprint),
    CHECK (jsonb_typeof(overlap_operations) = 'array'),
    CHECK (jsonb_typeof(parts) = 'array'),
    CHECK (jsonb_typeof(evidence) = 'array'),
    CHECK (jsonb_typeof(procedure) = 'object'),
    CHECK (jsonb_typeof(source_watermarks) = 'array')
);

CREATE TABLE IF NOT EXISTS chat_visual_artifacts (
    chat_visual_artifact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_quote_revision_id uuid NOT NULL REFERENCES chat_quote_revisions(chat_quote_revision_id),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    source_artifact_key text NOT NULL,
    derived_artifact_key text NOT NULL,
    source_uri text,
    processor text NOT NULL,
    processor_version text NOT NULL,
    review_state text NOT NULL CHECK (review_state IN ('pending', 'approved', 'rejected')),
    label text NOT NULL DEFAULT 'AI-enhanced / UNREVIEWED',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_artifact_key, processor, processor_version),
    UNIQUE (chat_quote_revision_id, derived_artifact_key)
);

CREATE TABLE IF NOT EXISTS chat_worker_events (
    chat_worker_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id uuid NOT NULL REFERENCES chat_queries(query_id),
    event_id uuid NOT NULL,
    event_type text NOT NULL,
    event_version integer NOT NULL CHECK (event_version > 0),
    sequence_number bigint GENERATED ALWAYS AS IDENTITY,
    stage text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'dead_letter')),
    data_state text NOT NULL CHECK (data_state IN (
        'normalized', 'source_unnormalized', 'normalizing', 'mixed', 'unavailable', 'needs_review'
    )),
    redacted_message text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text NOT NULL UNIQUE,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (query_id, event_id),
    UNIQUE (query_id, sequence_number),
    CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX IF NOT EXISTS chat_queries_status_idx
    ON chat_queries (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS chat_query_options_query_idx
    ON chat_query_options (query_id, option_number);
CREATE INDEX IF NOT EXISTS chat_job_plans_status_idx
    ON chat_job_plans (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS parts_price_snapshots_lookup_idx
    ON parts_price_snapshots (canonical_part_id, priced_at DESC);
CREATE INDEX IF NOT EXISTS chat_quote_revisions_plan_idx
    ON chat_quote_revisions (chat_job_plan_id, revision_number DESC);
CREATE INDEX IF NOT EXISTS chat_worker_events_query_idx
    ON chat_worker_events (query_id, sequence_number);

CREATE OR REPLACE FUNCTION prevent_published_chat_quote_revision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION 'published chat quote revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS chat_quote_revisions_immutable ON chat_quote_revisions;
CREATE TRIGGER chat_quote_revisions_immutable
    BEFORE UPDATE OR DELETE ON chat_quote_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_published_chat_quote_revision_mutation();

COMMENT ON TABLE chat_queries IS
    'Durable natural-language requests; idempotency prevents duplicate source/model work.';
COMMENT ON TABLE chat_job_plans IS
    'Vehicle-scoped deterministic orchestration state for immediate and progressive answers.';
COMMENT ON TABLE parts_price_snapshots IS
    'Source/catalog prices only; markup is structurally prohibited and stale values remain readable.';
COMMENT ON TABLE chat_quote_revisions IS
    'Immutable published quote/procedure answer revisions with overlap arithmetic and evidence.';
COMMENT ON TABLE chat_visual_artifacts IS
    'Source-backed vector redraws; no artifact may exist without an original source visual.';
COMMENT ON TABLE chat_worker_events IS
    'Redacted, replayable worker progress stream correlated to one chat query.';

INSERT INTO schema_migrations (version)
VALUES ('025_chat_quote_procedure')
ON CONFLICT (version) DO NOTHING;
