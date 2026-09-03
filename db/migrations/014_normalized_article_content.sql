ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS body text,
    ADD COLUMN IF NOT EXISTS steps jsonb,
    ADD COLUMN IF NOT EXISTS normalized_fingerprint text;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_steps_array_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_steps_array_check
    CHECK (steps IS NULL OR jsonb_typeof(steps) = 'array');

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_normalized_fingerprint_format_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_normalized_fingerprint_format_check
    CHECK (
        normalized_fingerprint IS NULL
        OR normalized_fingerprint ~ '^[0-9a-f]{64}$'
    );

CREATE INDEX IF NOT EXISTS catalog_articles_normalized_fingerprint_idx
    ON catalog_articles (vehicle_id, normalized_fingerprint)
    WHERE normalized_fingerprint IS NOT NULL;

COMMENT ON COLUMN catalog_articles.normalized_fingerprint IS
    'Exact SHA-256 identity of canonical article body and steps for duplicate and replay lookup; exact lookup only, with no schema-level similarity index; semantic near-duplicate quarantine belongs to the normalized source bundle path.';

INSERT INTO schema_migrations (version)
VALUES ('014_normalized_article_content')
ON CONFLICT (version) DO NOTHING;
