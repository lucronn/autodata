ALTER TABLE catalog_articles
    ADD COLUMN IF NOT EXISTS content_source_snapshot_id uuid
        REFERENCES source_snapshots(source_snapshot_id),
    ADD COLUMN IF NOT EXISTS content_source_locator text,
    ADD COLUMN IF NOT EXISTS content_extraction_evidence_id uuid
        REFERENCES extraction_evidence(extraction_evidence_id);

CREATE INDEX IF NOT EXISTS catalog_articles_content_evidence_idx
    ON catalog_articles (content_extraction_evidence_id)
    WHERE content_extraction_evidence_id IS NOT NULL;

COMMENT ON COLUMN catalog_articles.content_source_snapshot_id IS
    'Source snapshot containing the article body when article metadata and document content arrive as separate resources.';

COMMENT ON COLUMN catalog_articles.content_source_locator IS
    'Locator for the persisted article body within content_source_snapshot_id.';

COMMENT ON COLUMN catalog_articles.content_extraction_evidence_id IS
    'Evidence record for article body content; distinct from the metadata/index evidence when required.';

INSERT INTO schema_migrations (version)
VALUES ('019_article_content_provenance')
ON CONFLICT (version) DO NOTHING;
