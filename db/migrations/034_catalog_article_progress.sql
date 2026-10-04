-- Expose durable, vehicle-scoped article catalog progress to the workshop UI.
ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS vehicle_id text NOT NULL DEFAULT '';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'idle';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS phase text NOT NULL DEFAULT 'starting';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS processed_units integer NOT NULL DEFAULT 0;

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS total_units integer NOT NULL DEFAULT 0;

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS current_article_id text NOT NULL DEFAULT '';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS current_title text NOT NULL DEFAULT '';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS progress_detail text NOT NULL DEFAULT '';

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN IF NOT EXISTS progress_percent integer NOT NULL DEFAULT 0;

ALTER TABLE vehicle_catalog_hydration_scopes
    DROP CONSTRAINT IF EXISTS vehicle_catalog_hydration_scopes_status_check;

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD CONSTRAINT vehicle_catalog_hydration_scopes_status_check
    CHECK (status = ANY (ARRAY['idle'::text, 'running'::text, 'completed'::text, 'failed'::text]));

ALTER TABLE vehicle_catalog_hydration_scopes
    DROP CONSTRAINT IF EXISTS vehicle_catalog_hydration_scopes_progress_bounds_check;

ALTER TABLE vehicle_catalog_hydration_scopes
    ADD CONSTRAINT vehicle_catalog_hydration_scopes_progress_bounds_check
    CHECK (
        processed_units >= 0
        AND total_units >= 0
        AND progress_percent >= 0
        AND progress_percent <= 100
    );

CREATE INDEX IF NOT EXISTS vehicle_catalog_hydration_scopes_vehicle_progress_idx
    ON vehicle_catalog_hydration_scopes (scope, vehicle_id, status, updated_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('034_catalog_article_progress')
ON CONFLICT (version) DO NOTHING;
