CREATE TABLE IF NOT EXISTS chat_runtime_queries (
    query_id text PRIMARY KEY CHECK (length(btrim(query_id)) > 0),
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) > 0),
    request_fingerprint char(64) NOT NULL
        CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    owner_id text,
    organization_id text,
    query_snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(query_snapshot) = 'object')
);

CREATE TABLE IF NOT EXISTS chat_runtime_queue (
    query_id text NOT NULL,
    work_kind text NOT NULL CHECK (work_kind IN ('source', 'price_refresh')),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid,
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (query_id, work_kind),
    CHECK ((lease_token IS NULL) = (lease_expires_at IS NULL))
);

CREATE TABLE IF NOT EXISTS chat_runtime_event_contexts (
    query_id text PRIMARY KEY CHECK (length(btrim(query_id)) > 0),
    correlation_id uuid NOT NULL,
    request_id uuid NOT NULL,
    projection_id uuid NOT NULL,
    owner_id text,
    organization_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_runtime_events (
    event_sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_id text NOT NULL,
    event_id uuid NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    occurred_at timestamptz NOT NULL,
    event_snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (query_id, event_id),
    CHECK (jsonb_typeof(event_snapshot) = 'object')
);

CREATE TABLE IF NOT EXISTS chat_runtime_event_retries (
    query_id text NOT NULL,
    stage text NOT NULL CHECK (length(btrim(stage)) > 0),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    terminal_result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (query_id, stage),
    CHECK (terminal_result IS NULL OR jsonb_typeof(terminal_result) = 'object')
);

CREATE INDEX IF NOT EXISTS chat_runtime_queries_owner_idx
    ON chat_runtime_queries (organization_id, owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS chat_runtime_queue_due_idx
    ON chat_runtime_queue (work_kind, available_at, lease_expires_at);
CREATE INDEX IF NOT EXISTS chat_runtime_events_query_idx
    ON chat_runtime_events (query_id, event_sequence);
CREATE INDEX IF NOT EXISTS chat_runtime_event_retries_active_idx
    ON chat_runtime_event_retries (updated_at)
    WHERE terminal_result IS NULL;

COMMENT ON TABLE chat_runtime_queries IS
    'Redacted internal chat state shared by the HTTP and worker processes.';
COMMENT ON TABLE chat_runtime_queue IS
    'Leased source and price-refresh work; expired leases are eligible for reclaim.';
COMMENT ON TABLE chat_runtime_event_contexts IS
    'Stable query correlation and ownership used to authorize replay.';
COMMENT ON TABLE chat_runtime_events IS
    'Bounded redacted progress envelopes ordered for replay.';
COMMENT ON TABLE chat_runtime_event_retries IS
    'Durable bounded attempt and terminal dead-letter state by query stage.';

INSERT INTO schema_migrations (version)
VALUES ('027_chat_runtime_durable_state')
ON CONFLICT (version) DO NOTHING;
