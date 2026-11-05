-- Provisioning-time input only. Activation never executes this script.
-- Run as the existing database administrator after the ledger exists.
-- Existing autodata_metrics identity/authentication must be provisioned separately.
-- No role creation, membership, password, ownership or administrative fallback.
REVOKE ALL ON DATABASE autodata FROM PUBLIC, autodata_metrics;
REVOKE ALL ON SCHEMA public FROM PUBLIC, autodata_metrics;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM autodata_metrics;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM autodata_metrics;
GRANT CONNECT ON DATABASE autodata TO autodata_metrics;
GRANT USAGE ON SCHEMA public TO autodata_metrics;
GRANT SELECT ON TABLE public.schema_migrations TO autodata_metrics;
-- PUBLIC or column-level write privileges and grants in other application
-- schemas must be separately revoked by bootstrap. The runtime rejects them.
