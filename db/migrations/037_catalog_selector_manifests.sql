-- Provider-backed make/model manifests for the vehicle selector.
--
-- `vehicle_catalog_years` (030) already records the year index. Makes and
-- models resolved by selector hydration had no durable home: a make-only row
-- cannot become a `vehicle_identity_bases` row (model/region are NOT NULL), so
-- a completed `makes`/`models` hydration persisted its coverage marker but no
-- values, and the workshop picker could only ever show whatever the seed
-- fixture had written. These manifest tables give each selector scope the same
-- durable, provider-backed index the year manifest already has, so one bounded
-- hydration fills the dropdown and a later read is database-only.
CREATE TABLE IF NOT EXISTS vehicle_catalog_makes (
    vehicle_catalog_make_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    source_version text NOT NULL,
    model_year integer NOT NULL CHECK (model_year >= 1886 AND model_year <= 2100),
    make text NOT NULL,
    region text NOT NULL DEFAULT '',
    source_uri text NOT NULL,
    response_hash text NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, source_version, model_year, make, region)
);

CREATE INDEX IF NOT EXISTS vehicle_catalog_makes_lookup_idx
    ON vehicle_catalog_makes (model_year, lower(make), region);

COMMENT ON TABLE vehicle_catalog_makes IS
    'Provider-backed make manifest used to populate vehicle selectors before deeper catalog traversal.';

CREATE TABLE IF NOT EXISTS vehicle_catalog_models (
    vehicle_catalog_model_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    source_version text NOT NULL,
    model_year integer NOT NULL CHECK (model_year >= 1886 AND model_year <= 2100),
    make text NOT NULL,
    model text NOT NULL,
    region text NOT NULL DEFAULT '',
    source_uri text NOT NULL,
    response_hash text NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, source_version, model_year, make, model, region)
);

CREATE INDEX IF NOT EXISTS vehicle_catalog_models_lookup_idx
    ON vehicle_catalog_models (model_year, lower(make), region);

COMMENT ON TABLE vehicle_catalog_models IS
    'Provider-backed model manifest used to populate vehicle selectors before deeper catalog traversal.';

INSERT INTO schema_migrations (version)
VALUES ('037_catalog_selector_manifests')
ON CONFLICT (version) DO NOTHING;
