BEGIN;

CREATE TABLE IF NOT EXISTS customer_accounts (
    customer_account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_project_id text NOT NULL CHECK (btrim(firebase_project_id) <> ''),
    firebase_uid text NOT NULL CHECK (btrim(firebase_uid) <> ''),
    personal_organization_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firebase_project_id, firebase_uid)
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_token_hash bytea PRIMARY KEY CHECK (octet_length(session_token_hash) = 32),
    customer_account_id uuid NOT NULL REFERENCES customer_accounts(customer_account_id),
    firebase_auth_time bigint NOT NULL CHECK (firebase_auth_time > 0),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at AND expires_at <= created_at + interval '12 hours'),
    revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS auth_sessions_account_idx ON auth_sessions(customer_account_id);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry_idx ON auth_sessions(expires_at);

INSERT INTO schema_migrations(version) VALUES('039_production_identity_sessions') ON CONFLICT DO NOTHING;
COMMIT;
