BEGIN;

CREATE TABLE IF NOT EXISTS source_fetch_jobs (
    source_fetch_job_id uuid PRIMARY KEY,
    provider_slug text NOT NULL CHECK (length(btrim(provider_slug)) > 0),
    canonical_vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    source_vehicle_ref text NOT NULL,
    source_article_ref text,
    source_article_refs text[] NOT NULL DEFAULT '{}',
    source_locator text,
    selector_source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    source_version text NOT NULL,
    connector_name text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'needs_review', 'failed', 'dead_letter')),
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(checkpoint) = 'object'),
    last_error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_fetch_jobs_status_idx
    ON source_fetch_jobs (status, updated_at);
CREATE INDEX IF NOT EXISTS source_fetch_jobs_vehicle_idx
    ON source_fetch_jobs (canonical_vehicle_id, provider_slug, source_version);
CREATE INDEX IF NOT EXISTS source_fetch_jobs_provider_vehicle_ref_idx
    ON source_fetch_jobs (provider_slug, source_vehicle_ref);

COMMENT ON TABLE source_fetch_jobs IS
    'Provider-neutral AutoData source-fetch job lifecycle; opaque provider references and historical idempotency are retained.';

-- Preserve every existing Bankone job identity and retry state. Re-running this
-- migration or applying it after a partial generic import cannot duplicate a key.
LOCK TABLE autoapi_article_fetch_jobs IN SHARE ROW EXCLUSIVE MODE;

INSERT INTO source_fetch_jobs
    (source_fetch_job_id, provider_slug, canonical_vehicle_id,
     source_vehicle_ref, source_article_ref, source_article_refs, source_locator,
     selector_source_snapshot_id, source_snapshot_id, source_version,
     connector_name, idempotency_key, status, retry_count, checkpoint,
     last_error, created_at, updated_at)
SELECT autoapi_article_fetch_job_id, 'bankone', vehicle_id, vehicle_key,
       NULL, '{}'::text[], source_location,
       selector_source_snapshot_id, source_snapshot_id, source_version,
       adapter_name, idempotency_key, status, attempt_count, checkpoint,
       last_error, created_at, updated_at
FROM autoapi_article_fetch_jobs
ON CONFLICT (idempotency_key) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM autoapi_article_fetch_jobs legacy
        LEFT JOIN source_fetch_jobs generic USING (idempotency_key)
        WHERE generic.source_fetch_job_id IS NULL
           OR generic.source_fetch_job_id <> legacy.autoapi_article_fetch_job_id
           OR generic.canonical_vehicle_id <> legacy.vehicle_id
           OR generic.source_vehicle_ref <> legacy.vehicle_key
           OR generic.source_locator IS DISTINCT FROM legacy.source_location
           OR generic.source_article_ref IS NOT NULL
           OR generic.source_article_refs <> '{}'::text[]
           OR generic.status <> legacy.status
           OR generic.retry_count <> legacy.attempt_count
           OR generic.selector_source_snapshot_id IS DISTINCT FROM legacy.selector_source_snapshot_id
           OR generic.source_snapshot_id IS DISTINCT FROM legacy.source_snapshot_id
    ) THEN
        RAISE EXCEPTION 'source_fetch_jobs migration did not preserve every legacy job identity/state';
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('036_source_fetch_jobs')
ON CONFLICT (version) DO NOTHING;

COMMIT;
