ALTER TABLE extraction_evidence
    ADD COLUMN IF NOT EXISTS reviewer_id uuid,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
    ADD COLUMN IF NOT EXISTS review_reason text;

INSERT INTO schema_migrations (version)
VALUES ('010_evidence_review_metadata')
ON CONFLICT (version) DO NOTHING;
