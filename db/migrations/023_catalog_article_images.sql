ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS images jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_images_array_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_images_array_check
    CHECK (jsonb_typeof(images) = 'array');

CREATE INDEX IF NOT EXISTS catalog_articles_images_idx
    ON catalog_articles USING gin (images);

COMMENT ON COLUMN catalog_articles.images IS
    'Safe source-media references retained with the normalized article; binary media remains in S3-compatible object storage.';

INSERT INTO schema_migrations (version)
VALUES ('023_catalog_article_images')
ON CONFLICT (version) DO NOTHING;
