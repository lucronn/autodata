ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS operations jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_operations_array_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_operations_array_check
    CHECK (jsonb_typeof(operations) = 'array');

CREATE INDEX IF NOT EXISTS catalog_articles_operations_idx
    ON catalog_articles USING gin (operations);

COMMENT ON COLUMN catalog_articles.operations IS
    'Normalized labor operations joined to the source article; each operation retains evidence_ids for auditability.';

INSERT INTO schema_migrations (version)
VALUES ('024_catalog_article_operations')
ON CONFLICT (version) DO NOTHING;
