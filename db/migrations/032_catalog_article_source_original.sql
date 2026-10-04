ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS source_original jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_source_original_object_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_source_original_object_check
    CHECK (jsonb_typeof(source_original) = 'object');

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS rewrite_status text NOT NULL DEFAULT 'pending';

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_rewrite_status_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_rewrite_status_check
    CHECK (
        rewrite_status = ANY (
            ARRAY[
                'pending'::text,
                'rewritten'::text,
                'skipped'::text,
                'failed'::text
            ]
        )
    );

COMMENT ON COLUMN catalog_articles.source_original IS
    'Immutable provider snapshot (blocks, body, provider image URLs, retrieval metadata) retained for audit.';
COMMENT ON COLUMN catalog_articles.rewrite_status IS
    'DIY phrase-rewrite outcome: pending, rewritten, skipped, or failed.';

INSERT INTO schema_migrations (version)
VALUES ('032_catalog_article_source_original')
ON CONFLICT (version) DO NOTHING;
