CREATE TABLE IF NOT EXISTS vehicle_catalog_years (
    vehicle_catalog_year_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    source_version text NOT NULL,
    year integer NOT NULL CHECK (year >= 1886 AND year <= 2100),
    source_uri text NOT NULL,
    response_hash text NOT NULL,
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, source_version, year)
);

ALTER TABLE vehicle_catalog_years
    ADD COLUMN IF NOT EXISTS source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id);

CREATE INDEX IF NOT EXISTS vehicle_catalog_years_lookup_idx
    ON vehicle_catalog_years (provider, source_version, year);

COMMENT ON TABLE vehicle_catalog_years IS
    'Immutable provider-backed year manifest used to populate vehicle selectors before deeper catalog traversal.';

INSERT INTO schema_migrations (version)
VALUES ('030_vehicle_catalog_years')
ON CONFLICT (version) DO NOTHING;
