CREATE TABLE IF NOT EXISTS source_artifacts (
    source_artifact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_snapshot_id uuid NOT NULL UNIQUE REFERENCES source_snapshots(source_snapshot_id),
    artifact_kind text NOT NULL CHECK (artifact_kind IN ('structured', 'document', 'diagram', 'quarantine')),
    media_type text NOT NULL,
    content_sha256 char(64) NOT NULL UNIQUE,
    object_key text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_status text NOT NULL CHECK (extraction_status IN ('candidate_ready', 'complete', 'needs_review', 'quarantined')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_models (
    vehicle_model_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    provider_model_id text NOT NULL,
    name text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_id, provider_model_id, source_snapshot_id)
);

CREATE TABLE IF NOT EXISTS powertrains (
    powertrain_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_model_id uuid NOT NULL REFERENCES vehicle_models(vehicle_model_id),
    provider_powertrain_id text NOT NULL,
    name text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_model_id, provider_powertrain_id, source_snapshot_id)
);

CREATE TABLE IF NOT EXISTS inventory_parts (
    inventory_part_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    part_number text NOT NULL,
    description text NOT NULL,
    quantity integer CHECK (quantity IS NULL OR quantity >= 0),
    price_minor bigint CHECK (price_minor IS NULL OR price_minor >= 0),
    currency char(3),
    price_status text NOT NULL CHECK (price_status IN ('normalized', 'needs_review', 'missing')),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_id, part_number, source_snapshot_id)
);

CREATE TABLE IF NOT EXISTS catalog_articles (
    catalog_article_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    article_id text NOT NULL,
    bucket text,
    title text,
    bulletin_number text,
    release_date text,
    sort_order integer,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_id, article_id, source_snapshot_id)
);

CREATE INDEX IF NOT EXISTS source_artifacts_kind_idx ON source_artifacts (artifact_kind, extraction_status);
CREATE INDEX IF NOT EXISTS vehicle_models_vehicle_idx ON vehicle_models (vehicle_id);
CREATE INDEX IF NOT EXISTS powertrains_model_idx ON powertrains (vehicle_model_id);
CREATE INDEX IF NOT EXISTS inventory_parts_vehicle_idx ON inventory_parts (vehicle_id, part_number);
CREATE INDEX IF NOT EXISTS catalog_articles_vehicle_idx ON catalog_articles (vehicle_id, bucket);

INSERT INTO schema_migrations (version)
VALUES ('004_normalized_source_bundle')
ON CONFLICT (version) DO NOTHING;
