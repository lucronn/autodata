ALTER TABLE extraction_evidence
    ADD COLUMN IF NOT EXISTS dataset_revision_id uuid REFERENCES dataset_revisions(dataset_revision_id);

CREATE INDEX IF NOT EXISTS extraction_evidence_revision_idx
    ON extraction_evidence (dataset_revision_id);

INSERT INTO schema_migrations (version)
VALUES ('007_link_evidence_to_revision')
ON CONFLICT (version) DO NOTHING;
