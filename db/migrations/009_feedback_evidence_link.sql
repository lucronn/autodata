ALTER TABLE feedback_items
    ADD COLUMN IF NOT EXISTS extraction_evidence_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'feedback_items_evidence_fk'
          AND conrelid = 'feedback_items'::regclass
    ) THEN
        ALTER TABLE feedback_items
            ADD CONSTRAINT feedback_items_evidence_fk
            FOREIGN KEY (extraction_evidence_id)
            REFERENCES extraction_evidence(extraction_evidence_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS feedback_items_projection_idx
    ON feedback_items (dataset_projection_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('009_feedback_evidence_link')
ON CONFLICT (version) DO NOTHING;
