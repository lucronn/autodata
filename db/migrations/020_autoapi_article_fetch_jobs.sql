CREATE TABLE IF NOT EXISTS autoapi_article_fetch_jobs (
    autoapi_article_fetch_job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    vehicle_key text NOT NULL,
    selector_source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    source_location text,
    source_version text NOT NULL,
    adapter_name text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'needs_review', 'failed', 'dead_letter')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(checkpoint) = 'object'),
    last_error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS autoapi_article_fetch_jobs_status_idx
    ON autoapi_article_fetch_jobs (status, updated_at);

CREATE INDEX IF NOT EXISTS autoapi_article_fetch_jobs_vehicle_idx
    ON autoapi_article_fetch_jobs (vehicle_id, source_version);

COMMENT ON TABLE autoapi_article_fetch_jobs IS
    'One idempotent, auditable all-articles fan-out job per AutoAPI vehicle bundle; selector-only vehicles remain pending until their bundle arrives.';

INSERT INTO schema_migrations (version)
VALUES ('020_autoapi_article_fetch_jobs')
ON CONFLICT (version) DO NOTHING;
