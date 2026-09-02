CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_key text NOT NULL UNIQUE,
    make text NOT NULL,
    model text NOT NULL,
    model_year integer NOT NULL CHECK (model_year BETWEEN 1886 AND 2100),
    region text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    source_watermark text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_specifications (
    vehicle_specification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    name text NOT NULL,
    value_json jsonb NOT NULL,
    unit text,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_id, name)
);

ALTER TABLE dataset_requests
    ADD COLUMN IF NOT EXISTS vehicle_id uuid REFERENCES vehicles(vehicle_id);

CREATE INDEX IF NOT EXISTS vehicles_selector_idx
    ON vehicles (make, model, model_year, region);

INSERT INTO schema_migrations (version)
VALUES ('003_canonical_vehicle')
ON CONFLICT (version) DO NOTHING;
