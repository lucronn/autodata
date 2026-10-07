DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM managed_api_key_audit audit
        JOIN managed_api_keys api_key ON api_key.id = audit.key_id
        WHERE api_key.service <> audit.service
    ) THEN
        RAISE EXCEPTION 'Existing API-key audit rows contain mismatched service values; repair them before applying migration 002';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'managed_api_keys'::regclass
          AND conname = 'managed_api_keys_id_service_key'
    ) THEN
        ALTER TABLE managed_api_keys
            ADD CONSTRAINT managed_api_keys_id_service_key UNIQUE (id, service);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'managed_api_key_audit'::regclass
          AND conname = 'managed_api_key_audit_key_service_fk'
    ) THEN
        ALTER TABLE managed_api_key_audit
            ADD CONSTRAINT managed_api_key_audit_key_service_fk
            FOREIGN KEY (key_id, service) REFERENCES managed_api_keys(id, service) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION reject_api_key_identity_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.service IS DISTINCT FROM OLD.service
       OR NEW.key_digest IS DISTINCT FROM OLD.key_digest
       OR NEW.key_prefix IS DISTINCT FROM OLD.key_prefix
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
        RAISE EXCEPTION 'API key identity fields are immutable';
    END IF;
    IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'API key revocation is permanent';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS managed_api_key_identity_immutable ON managed_api_keys;
CREATE TRIGGER managed_api_key_identity_immutable
    BEFORE UPDATE ON managed_api_keys
    FOR EACH ROW EXECUTE FUNCTION reject_api_key_identity_change();

CREATE OR REPLACE FUNCTION reject_api_key_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'API key audit records are append-only';
END $$;

DROP TRIGGER IF EXISTS managed_api_key_audit_append_only ON managed_api_key_audit;
CREATE TRIGGER managed_api_key_audit_append_only
    BEFORE UPDATE OR DELETE ON managed_api_key_audit
    FOR EACH ROW EXECUTE FUNCTION reject_api_key_audit_mutation();
