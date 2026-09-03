ALTER TABLE feedback_items
    ADD COLUMN IF NOT EXISTS review_reason text,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

INSERT INTO schema_migrations (version)
VALUES ('011_feedback_review_metadata')
ON CONFLICT (version) DO NOTHING;
