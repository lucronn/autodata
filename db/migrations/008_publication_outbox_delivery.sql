ALTER TABLE publication_events
    ADD COLUMN IF NOT EXISTS producer text NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS delivery_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS delivery_attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_delivery_error jsonb,
    ADD COLUMN IF NOT EXISTS delivered_at timestamptz;

ALTER TABLE publication_events
    DROP CONSTRAINT IF EXISTS publication_events_delivery_status_check;

ALTER TABLE publication_events
    ADD CONSTRAINT publication_events_delivery_status_check
    CHECK (delivery_status IN ('pending', 'published', 'failed', 'dead_letter'));

ALTER TABLE publication_events
    DROP CONSTRAINT IF EXISTS publication_events_delivery_attempts_check;

ALTER TABLE publication_events
    ADD CONSTRAINT publication_events_delivery_attempts_check
    CHECK (delivery_attempts >= 0);

UPDATE publication_events
SET producer = CASE
    WHEN event_type = 'dataset.viewable' THEN 'ingestion-worker'
    ELSE 'enrichment-worker'
END
WHERE producer = 'unknown';

CREATE INDEX IF NOT EXISTS publication_events_delivery_idx
    ON publication_events (delivery_status, created_at);

INSERT INTO schema_migrations (version)
VALUES ('008_publication_outbox_delivery')
ON CONFLICT (version) DO NOTHING;
