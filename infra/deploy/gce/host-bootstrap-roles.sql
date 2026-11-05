-- Fixed fresh-install identities. Password assignment is supplied separately on
-- bounded stdin. Existing roles are permitted only after explicit journal audit.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
DO $roles$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['autodata_migrator','autodata_api','autodata_http',
    'autodata_article','autodata_reconciler','autodata_metrics','autodata_outbox']
  LOOP
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname=role_name) THEN
      EXECUTE pg_catalog.format('CREATE ROLE %I LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',role_name);
    END IF;
  END LOOP;
END
$roles$;
REVOKE ALL ON DATABASE autodata FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE autodata TO autodata_migrator;
ALTER SCHEMA public OWNER TO autodata_migrator;
