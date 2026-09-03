DELETE FROM catalog_articles AS legacy
WHERE legacy.source_locator = ''
  AND EXISTS (
      SELECT 1
      FROM catalog_articles AS located
      WHERE located.vehicle_id = legacy.vehicle_id
        AND located.article_id = legacy.article_id
        AND located.source_snapshot_id = legacy.source_snapshot_id
        AND located.source_locator = legacy.evidence_locator
  );

UPDATE catalog_articles
SET source_locator = evidence_locator
WHERE source_locator = '';

INSERT INTO schema_migrations (version)
VALUES ('006_backfill_article_source_locators')
ON CONFLICT (version) DO NOTHING;
