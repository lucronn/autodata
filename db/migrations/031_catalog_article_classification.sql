ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS provider text;

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS content_kind text;

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS procedure_kind text;

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS component text;

ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS content_status text NOT NULL DEFAULT 'list_only';

ALTER TABLE catalog_articles
    DROP CONSTRAINT IF EXISTS catalog_articles_content_status_check;

ALTER TABLE catalog_articles
    ADD CONSTRAINT catalog_articles_content_status_check
    CHECK (content_status = ANY (ARRAY['list_only'::text, 'content_complete'::text]));

CREATE INDEX IF NOT EXISTS catalog_articles_content_status_idx
    ON catalog_articles (vehicle_id, content_status);

COMMENT ON COLUMN catalog_articles.provider IS
    'Source adapter that produced the article (for example autoapitwo).';
COMMENT ON COLUMN catalog_articles.content_kind IS
    'Typed article kind such as procedure or parts_and_labor.';
COMMENT ON COLUMN catalog_articles.procedure_kind IS
    'Procedure phase classification such as removal, installation, or removal_and_installation.';
COMMENT ON COLUMN catalog_articles.component IS
    'Normalized component key when known for the article.';
COMMENT ON COLUMN catalog_articles.content_status IS
    'list_only for index/title rows; content_complete when instructional body/steps are stored.';

INSERT INTO schema_migrations (version)
VALUES ('031_catalog_article_classification')
ON CONFLICT (version) DO NOTHING;
