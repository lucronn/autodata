ALTER TABLE payment_events
    ADD COLUMN IF NOT EXISTS fulfillment_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS fulfillment_attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_fulfillment_error text,
    ADD COLUMN IF NOT EXISTS fulfilled_at timestamptz;

ALTER TABLE payment_events
    DROP CONSTRAINT IF EXISTS payment_events_fulfillment_status_check;

ALTER TABLE payment_events
    ADD CONSTRAINT payment_events_fulfillment_status_check
    CHECK (fulfillment_status IN ('pending', 'fulfilled', 'failed'));

ALTER TABLE payment_events
    DROP CONSTRAINT IF EXISTS payment_events_fulfillment_attempts_check;

ALTER TABLE payment_events
    ADD CONSTRAINT payment_events_fulfillment_attempts_check
    CHECK (fulfillment_attempts >= 0);

CREATE INDEX IF NOT EXISTS payment_events_fulfillment_idx
    ON payment_events (fulfillment_status, recorded_at, payment_event_id);

UPDATE payment_events pe
SET fulfillment_status = 'fulfilled',
    fulfillment_attempts = GREATEST(fulfillment_attempts, 1),
    fulfilled_at = COALESCE(fulfilled_at, e.granted_at)
FROM entitlements e
WHERE e.payment_event_id = pe.payment_event_id
  AND e.status = 'active'
  AND pe.fulfillment_status = 'pending';

INSERT INTO schema_migrations (version)
VALUES ('012_payment_fulfillment_reconciliation')
ON CONFLICT (version) DO NOTHING;
