BEGIN;

ALTER TABLE vehicle_configurations
    ADD COLUMN engine_variant text,
    ADD COLUMN engine_variant_market_verified boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT vehicle_configurations_engine_variant_check
        CHECK (engine_variant IN ('CNG', 'LNG', 'LPG', 'FLEX FUEL'));

INSERT INTO schema_migrations(version) VALUES ('052_vehicle_engine_variant')
ON CONFLICT DO NOTHING;

COMMIT;
