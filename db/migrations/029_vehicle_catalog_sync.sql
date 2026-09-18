CREATE TABLE IF NOT EXISTS vehicle_catalog_syncs (
    vehicle_catalog_sync_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    source_version text NOT NULL,
    traversal_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'partial', 'failed', 'dead_letter')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(checkpoint) = 'object'),
    row_count integer NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    last_error text,
    next_retry_at timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, source_version, traversal_version)
);

CREATE TABLE IF NOT EXISTS vehicle_catalog_sync_scopes (
    vehicle_catalog_sync_scope_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_catalog_sync_id uuid NOT NULL REFERENCES vehicle_catalog_syncs(vehicle_catalog_sync_id) ON DELETE CASCADE,
    scope_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'dead_letter')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    response_hash text,
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(checkpoint) = 'object'),
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_catalog_sync_id, scope_key)
);

CREATE INDEX IF NOT EXISTS vehicle_catalog_sync_status_idx
    ON vehicle_catalog_syncs (provider, status, updated_at);
CREATE INDEX IF NOT EXISTS vehicle_catalog_sync_scopes_status_idx
    ON vehicle_catalog_sync_scopes (vehicle_catalog_sync_id, status, updated_at);

COMMENT ON TABLE vehicle_catalog_syncs IS
    'Idempotent, resumable catalog-only provider warm-up state; it never represents repair article ingestion.';

INSERT INTO schema_migrations (version)
VALUES ('029_vehicle_catalog_sync')
ON CONFLICT (version) DO NOTHING;
