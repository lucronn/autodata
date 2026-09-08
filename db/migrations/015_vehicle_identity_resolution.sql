CREATE TABLE IF NOT EXISTS vehicle_identity_bases (
    vehicle_identity_base_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_base_key text NOT NULL UNIQUE,
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    make text NOT NULL,
    model text NOT NULL,
    model_year integer NOT NULL CHECK (model_year BETWEEN 1886 AND 2100),
    region text NOT NULL,
    body_style text,
    drivetrain text,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    source_locator text NOT NULL,
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_configurations (
    vehicle_configuration_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    configuration_key text NOT NULL UNIQUE,
    vehicle_identity_base_id uuid NOT NULL REFERENCES vehicle_identity_bases(vehicle_identity_base_id),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    trim text,
    engine_displacement_l numeric(4, 1) CHECK (engine_displacement_l IS NULL OR engine_displacement_l > 0),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    source_locator text NOT NULL,
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_aliases (
    vehicle_alias_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    vehicle_configuration_id uuid REFERENCES vehicle_configurations(vehicle_configuration_id),
    alias_kind text NOT NULL,
    raw_value text NOT NULL,
    canonical_value text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    source_locator text NOT NULL,
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vehicle_id, alias_kind, raw_value, canonical_value, source_snapshot_id, source_locator)
);

CREATE TABLE IF NOT EXISTS vehicle_identity_observations (
    vehicle_identity_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    observation_key text NOT NULL UNIQUE,
    vehicle_id uuid REFERENCES vehicles(vehicle_id),
    vehicle_identity_base_id uuid REFERENCES vehicle_identity_bases(vehicle_identity_base_id),
    vehicle_configuration_id uuid REFERENCES vehicle_configurations(vehicle_configuration_id),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    source_locator text NOT NULL,
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    raw_observation jsonb NOT NULL,
    canonical_observation jsonb NOT NULL,
    resolution_status text NOT NULL CHECK (resolution_status IN ('matched', 'ambiguous', 'unmatched', 'rejected', 'needs_review')),
    resolution_reason text,
    selected_candidate_key text,
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(candidates) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog_article_vehicle_links (
    catalog_article_vehicle_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    canonical_catalog_article_id uuid NOT NULL REFERENCES catalog_articles(catalog_article_id),
    duplicate_catalog_article_id uuid NOT NULL UNIQUE REFERENCES catalog_articles(catalog_article_id),
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    reviewer_state text NOT NULL CHECK (reviewer_state IN ('pending', 'approved', 'rejected')),
    link_state text NOT NULL DEFAULT 'duplicate'
        CHECK (link_state IN ('canonical', 'duplicate', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (canonical_catalog_article_id <> duplicate_catalog_article_id)
);

CREATE INDEX IF NOT EXISTS vehicle_identity_bases_vehicle_idx
    ON vehicle_identity_bases (vehicle_id);
CREATE INDEX IF NOT EXISTS vehicle_configurations_vehicle_idx
    ON vehicle_configurations (vehicle_id);
CREATE INDEX IF NOT EXISTS vehicle_aliases_vehicle_idx
    ON vehicle_aliases (vehicle_id, alias_kind);
CREATE INDEX IF NOT EXISTS vehicle_identity_observations_vehicle_idx
    ON vehicle_identity_observations (vehicle_id, source_snapshot_id);
CREATE INDEX IF NOT EXISTS catalog_article_vehicle_links_vehicle_idx
    ON catalog_article_vehicle_links (vehicle_id, canonical_catalog_article_id);

COMMENT ON TABLE catalog_article_vehicle_links IS
    'Canonical/duplicate article links resolve catalog_articles by the source-scoped replay identity (vehicle_id, article_id, source_snapshot_id, source_locator); catalog_articles remains the immutable article association row.';

INSERT INTO schema_migrations (version)
VALUES ('015_vehicle_identity_resolution')
ON CONFLICT (version) DO NOTHING;
