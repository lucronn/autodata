ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS source_locator text NOT NULL DEFAULT '';

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_vehicle_id_article_id_source_snapshot_id_key;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_vehicle_article_source_locator_key;

CREATE UNIQUE INDEX IF NOT EXISTS catalog_articles_vehicle_article_source_locator_idx
    ON catalog_articles (vehicle_id, article_id, source_snapshot_id, source_locator);

INSERT INTO schema_migrations (version)
VALUES ('005_preserve_duplicate_article_ids')
ON CONFLICT (version) DO NOTHING;
