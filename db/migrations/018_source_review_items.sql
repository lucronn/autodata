CREATE TABLE IF NOT EXISTS source_review_items (
    source_review_item_id uuid PRIMARY KEY,
    item_key text NOT NULL UNIQUE,
    item_kind text NOT NULL CHECK (item_kind IN ('conflict', 'quarantine')),
    reason_code text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    source_snapshot_ids jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(source_snapshot_ids) = 'array'),
    extraction_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(extraction_evidence_ids) = 'array'),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(payload) = 'object'),
    reviewer_id text,
    review_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_review_items_status_idx
    ON source_review_items (status, item_kind, created_at);

CREATE INDEX IF NOT EXISTS source_review_items_reason_idx
    ON source_review_items (reason_code, status);

COMMENT ON TABLE source_review_items IS
    'Durable, payload-free review queue for source conflicts and quarantine decisions; provenance remains addressable through snapshot and evidence UUIDs.';

INSERT INTO schema_migrations (version)
VALUES ('018_source_review_items')
ON CONFLICT (version) DO NOTHING;
