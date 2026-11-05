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

-- Dedicated relay LOGIN must already exist with no ownership or memberships.
-- Provisioning must audit/revoke inherited PUBLIC and column-level grants and
-- unrelated schema grants; this script cannot remove ownership/member authority.
REVOKE ALL ON DATABASE autodata FROM autodata_outbox;
REVOKE ALL ON SCHEMA public FROM autodata_outbox;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM autodata_outbox;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM autodata_outbox;
GRANT CONNECT ON DATABASE autodata TO autodata_outbox;
GRANT USAGE ON SCHEMA public TO autodata_outbox;
GRANT SELECT ON TABLE public.publication_events TO autodata_outbox;
GRANT UPDATE (delivery_status, delivery_attempts, delivery_lease_owner, delivery_lease_token,
              delivery_lease_expires_at, last_delivery_error, next_delivery_at, delivered_at)
    ON TABLE public.publication_events TO autodata_outbox;
