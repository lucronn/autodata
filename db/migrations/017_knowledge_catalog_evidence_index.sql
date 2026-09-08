CREATE INDEX IF NOT EXISTS extraction_evidence_snapshot_locator_idx
    ON extraction_evidence (source_snapshot_id, locator);

COMMENT ON INDEX extraction_evidence_snapshot_locator_idx IS
    'Supports cache-first vehicle knowledge reads that resolve catalog article provenance by source snapshot and evidence locator.';

INSERT INTO schema_migrations (version)
VALUES ('017_knowledge_catalog_evidence_index')
ON CONFLICT (version) DO NOTHING;
