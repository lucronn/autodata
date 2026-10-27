# Hardening for NATS Offline Health Probing, Bank Connector Filtering, and Reconciler Ergonomics

**Goal:** Provide graceful fallback and clean output during offline NATS health probes, implement targeted `--year`, `--make`, and `--limit` filtering for Bankone and Banktwo ingestion services, and add CLI flag support to the payment reconciler.

**Architecture:** 
1. **NATS Messaging & Health Probing:** AutoData developer smoke scripts (`scripts/dev/nats_health.py` and `scripts/dev/ingestion_smoke.py`) run directly on developer workstations outside the Docker network. When NATS is offline, host DNS resolution fails for container-internal `nats:4222`. The URL resolver probes DNS resolution and defaults cleanly to `127.0.0.1:4222`, while nats client error callbacks are configured to suppress noisy tracebacks to `stderr`.
2. **Bank Connector Ingestion Services:** `scripts/dev/ingest_bankone_service.py` and `scripts/dev/ingest_banktwo_service.py` interface with independent upstream banks (`https://bankone.cars.tk` and `https://banktwo.cars.tk`). Traversal functions support optional `target_year`, `target_make`, and `limit` parameters to allow rapid, localized data ingestion and developer validation without triggering full multi-year, multi-make crawls.
3. **Payment Reconciler Ergonomics:** `scripts/dev/reconcile_payments.py` adds standard `argparse` CLI options (`--once`, `--batch-size`, `--poll-seconds`) while maintaining backwards compatibility with environment variables.

**Tech Stack:** Python 3.12+, NATS JetStream, Source Connector v1, PostgreSQL with pgvector, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/149

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Harden `resolve_nats_url` in `nats_health.py` and `ingestion_smoke.py` to test DNS resolution of `"nats"` before falling back to container hostnames.
- [x] Configure silent error callbacks in `inspect_stream` and `ingestion_smoke.py` to cleanly report `skipped (broker unreachable: ...)` without printing uncaught connection exception tracebacks to `stderr`.
- [x] Add `--year`, `--make`, and `--limit` CLI arguments and filtering parameters to `fetch_bankone_batches` in `scripts/dev/ingest_bankone_service.py`.
- [x] Add `--year`, `--make`, and `--limit` CLI arguments and filtering parameters to `fetch_banktwo_batches` in `scripts/dev/ingest_banktwo_service.py`.
- [x] Add `argparse` CLI argument parsing (`--once`, `--batch-size`, `--poll-seconds`) to `scripts/dev/reconcile_payments.py`.
- [x] Add unit tests in `scripts/dev/test_bank_topology.py` and `scripts/dev/test_storage_messaging_operations.py`.
- [x] Update developer documentation in `docs/architecture/infrastructure-and-dev.md` and synchronize pre-implementation record in `docs/agents/records/2026-10-27-nats-resilience-bank-service-filtering.json`.
- [x] Prune stale remote tracking branches and verify local Compose/daemon stacks.

## Security and Credential Isolation Rules

- Connector traversal scripts interact strictly with public Source Connector v1 endpoints using server-side keys without logging sensitive tokens or URL query credentials.
- No real API keys, credentials, or production identifiers are committed to version control.
- Ingestion services maintain isolated credentials per provider (`AUTODATA_BANKONE_API_KEY` vs `AUTODATA_BANKTWO_API_KEY`).
