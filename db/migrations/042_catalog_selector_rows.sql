BEGIN;

-- Sparse make/model enumeration is independent of full configuration deepening.
-- Version zero preserves old markers but makes them eligible for scoped healing.
ALTER TABLE vehicle_catalog_hydration_scopes
    ADD COLUMN selector_rows jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(selector_rows) = 'array'),
    ADD COLUMN completion_version integer NOT NULL DEFAULT 0
        CHECK (completion_version IN (0, 1));

INSERT INTO schema_migrations (version)
VALUES ('042_catalog_selector_rows')
ON CONFLICT (version) DO NOTHING;

COMMIT;
