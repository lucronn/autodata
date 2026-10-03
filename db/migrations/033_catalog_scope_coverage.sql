-- Track successful query-scoped catalog hydration so a partial local result
-- cannot suppress the one-time source read required to complete that scope.
CREATE TABLE IF NOT EXISTS vehicle_catalog_hydration_scopes (
    scope_key text PRIMARY KEY,
    scope text NOT NULL,
    model_year integer NOT NULL CHECK (model_year >= 1886 AND model_year <= 2100),
    make text NOT NULL DEFAULT '',
    model text NOT NULL DEFAULT '',
    region text NOT NULL DEFAULT '',
    provenance jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(provenance) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vehicle_catalog_hydration_scopes_lookup_idx
    ON vehicle_catalog_hydration_scopes (scope, model_year, lower(make), lower(model), region);

-- This row was created by a provider response that put the Silverado model in
-- the make field. Preserve the source evidence, but keep the malformed identity
-- out of the public selector until a human explicitly repairs it.
UPDATE vehicle_configurations
SET reviewer_state = 'rejected', updated_at = now()
WHERE vehicle_identity_base_id IN (
    SELECT vehicle_identity_base_id
    FROM vehicle_identity_bases
    WHERE lower(make) = 'silverado' AND lower(model) = '1500'
);

UPDATE vehicle_identity_bases
SET reviewer_state = 'rejected', updated_at = now()
WHERE lower(make) = 'silverado' AND lower(model) = '1500';
