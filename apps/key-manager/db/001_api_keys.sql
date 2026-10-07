CREATE TABLE IF NOT EXISTS managed_api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service text NOT NULL CHECK (service IN ('bankone', 'banktwo')),
    label text NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
    key_digest bytea NOT NULL UNIQUE CHECK (octet_length(key_digest) = 32),
    key_prefix text NOT NULL CHECK (length(key_prefix) BETWEEN 8 AND 32),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    last_used_at timestamptz,
    CONSTRAINT managed_api_keys_id_service_key UNIQUE (id, service),
    CHECK (expires_at IS NULL OR expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS managed_api_keys_service_active_idx
    ON managed_api_keys (service, created_at DESC)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS managed_api_key_audit (
    id bigserial PRIMARY KEY,
    key_id uuid NOT NULL,
    service text NOT NULL CHECK (service IN ('bankone', 'banktwo')),
    action text NOT NULL CHECK (action IN ('created', 'revoked')),
    actor text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT managed_api_key_audit_key_service_fk
        FOREIGN KEY (key_id, service) REFERENCES managed_api_keys(id, service) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS managed_api_key_audit_key_time_idx
    ON managed_api_key_audit (key_id, occurred_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bankone_key_runtime') THEN
        CREATE ROLE bankone_key_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'banktwo_key_runtime') THEN
        CREATE ROLE banktwo_key_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'api_key_manager') THEN
        CREATE ROLE api_key_manager NOLOGIN;
    END IF;
END $$;

REVOKE ALL ON managed_api_keys, managed_api_key_audit FROM PUBLIC;
ALTER TABLE managed_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE managed_api_keys FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'managed_api_keys' AND policyname = 'bankone_key_runtime_scope') THEN
        CREATE POLICY bankone_key_runtime_scope ON managed_api_keys
            TO bankone_key_runtime USING (service = 'bankone') WITH CHECK (service = 'bankone');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'managed_api_keys' AND policyname = 'banktwo_key_runtime_scope') THEN
        CREATE POLICY banktwo_key_runtime_scope ON managed_api_keys
            TO banktwo_key_runtime USING (service = 'banktwo') WITH CHECK (service = 'banktwo');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_policies WHERE tablename = 'managed_api_keys' AND policyname = 'api_key_manager_scope') THEN
        CREATE POLICY api_key_manager_scope ON managed_api_keys
            TO api_key_manager USING (true) WITH CHECK (true);
    END IF;
END $$;
GRANT SELECT (id, service, key_digest, expires_at, revoked_at), UPDATE (last_used_at)
    ON managed_api_keys TO bankone_key_runtime, banktwo_key_runtime;
GRANT SELECT, INSERT, UPDATE (revoked_at) ON managed_api_keys TO api_key_manager;
GRANT INSERT ON managed_api_key_audit TO api_key_manager;
GRANT USAGE, SELECT ON SEQUENCE managed_api_key_audit_id_seq TO api_key_manager;
