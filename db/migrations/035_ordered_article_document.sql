ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS normalized_document jsonb NOT NULL
        DEFAULT '{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[]}'::jsonb;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_normalized_document_object_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_normalized_document_object_check
    CHECK (
        jsonb_typeof(normalized_document) = 'object'
        AND jsonb_typeof(normalized_document->'blocks') = 'array'
    );

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS normalization_version text NOT NULL DEFAULT 'ordered-article-v1';

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS canonical_article_key text;

UPDATE catalog_articles
SET canonical_article_key = COALESCE(
    canonical_article_key,
    NULLIF(CONCAT(COALESCE(provider, 'unknown'), ':', article_id), ':')
)
WHERE canonical_article_key IS NULL;

CREATE INDEX IF NOT EXISTS catalog_articles_canonical_key_idx
    ON catalog_articles (vehicle_id, canonical_article_key);

COMMENT ON COLUMN catalog_articles.normalized_document IS
    'Authoritative ordered article document; body, steps, and images are compatibility projections.';
COMMENT ON COLUMN catalog_articles.normalization_version IS
    'Deterministic normalizer version that produced normalized_document.';
COMMENT ON COLUMN catalog_articles.canonical_article_key IS
    'Provider-scoped article identity used to resolve list-only/detail observations to one public article.';

INSERT INTO schema_migrations (version)
VALUES ('035_ordered_article_document')
ON CONFLICT (version) DO NOTHING;
