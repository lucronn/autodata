CREATE TABLE IF NOT EXISTS vehicle_provider_mappings (
    vehicle_provider_mapping_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_key text NOT NULL UNIQUE,
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    vehicle_configuration_id uuid REFERENCES vehicle_configurations(vehicle_configuration_id),
    provider text NOT NULL,
    entity_type text NOT NULL CHECK (entity_type IN ('car', 'aces_vehicle', 'aces_engine', 'aces_vec')),
    provider_id text NOT NULL,
    provider_label text,
    source_snapshot_id uuid NOT NULL REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid NOT NULL REFERENCES extraction_evidence(extraction_evidence_id),
    source_locator text NOT NULL,
    evidence_locator text NOT NULL,
    evidence_confidence numeric(5, 4) NOT NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    mapping_status text NOT NULL CHECK (mapping_status IN ('verified', 'pending', 'rejected')),
    raw_mapping jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(raw_mapping) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vehicle_provider_mappings_lookup_idx
    ON vehicle_provider_mappings (provider, entity_type, provider_id, mapping_status);
CREATE INDEX IF NOT EXISTS vehicle_provider_mappings_vehicle_idx
    ON vehicle_provider_mappings (vehicle_id, vehicle_configuration_id);

COMMENT ON TABLE vehicle_provider_mappings IS
    'Provenance-bound external identifiers. mapping_key includes the AutoData vehicle so one ACES identifier may map to many source vehicles.';

INSERT INTO schema_migrations (version)
VALUES ('028_vehicle_provider_mappings')
ON CONFLICT (version) DO NOTHING;
