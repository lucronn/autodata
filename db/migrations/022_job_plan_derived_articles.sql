CREATE TABLE IF NOT EXISTS derived_articles (
    derived_article_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id text NOT NULL UNIQUE,
    vehicle_id uuid NOT NULL REFERENCES vehicles(vehicle_id),
    title text NOT NULL,
    article_kind text NOT NULL DEFAULT 'composed'
        CHECK (article_kind = 'composed'),
    current_revision_number integer NOT NULL DEFAULT 0
        CHECK (current_revision_number >= 0),
    current_status text NOT NULL
        CHECK (current_status IN ('processing', 'ready', 'needs_review', 'failed')),
    creating_job_plan_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS derived_article_revisions (
    derived_article_revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    derived_article_id uuid NOT NULL REFERENCES derived_articles(derived_article_id),
    revision_number integer NOT NULL CHECK (revision_number > 0),
    normalized_fingerprint char(64) NOT NULL,
    source_watermark text NOT NULL,
    body text NOT NULL,
    steps jsonb NOT NULL CHECK (jsonb_typeof(steps) = 'array'),
    labor jsonb NOT NULL,
    images jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(images) = 'array'),
    provenance jsonb NOT NULL,
    model text,
    contract_version integer NOT NULL CHECK (contract_version > 0),
    status text NOT NULL
        CHECK (status IN ('processing', 'ready', 'needs_review', 'failed')),
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (derived_article_id, revision_number),
    UNIQUE (derived_article_id, normalized_fingerprint)
);

CREATE TABLE IF NOT EXISTS derived_article_lineage (
    derived_article_lineage_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    derived_article_revision_id uuid NOT NULL REFERENCES derived_article_revisions(derived_article_revision_id),
    source_article_identifier text NOT NULL,
    source_snapshot_id uuid REFERENCES source_snapshots(source_snapshot_id),
    extraction_evidence_id uuid REFERENCES extraction_evidence(extraction_evidence_id),
    lineage_role text NOT NULL CHECK (lineage_role IN ('article', 'evidence', 'operation', 'image')),
    source_locator text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (derived_article_revision_id, source_article_identifier, extraction_evidence_id, lineage_role)
);

CREATE INDEX IF NOT EXISTS derived_articles_vehicle_idx
    ON derived_articles (vehicle_id, current_status);
CREATE INDEX IF NOT EXISTS derived_article_revisions_fingerprint_idx
    ON derived_article_revisions (normalized_fingerprint);
CREATE INDEX IF NOT EXISTS derived_article_lineage_source_idx
    ON derived_article_lineage (source_article_identifier);

CREATE OR REPLACE FUNCTION prevent_published_derived_article_revision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION 'published derived article revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS derived_article_revisions_immutable ON derived_article_revisions;
CREATE TRIGGER derived_article_revisions_immutable
    BEFORE UPDATE OR DELETE ON derived_article_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_published_derived_article_revision_mutation();

INSERT INTO schema_migrations (version)
VALUES ('022_job_plan_derived_articles')
ON CONFLICT (version) DO NOTHING;
