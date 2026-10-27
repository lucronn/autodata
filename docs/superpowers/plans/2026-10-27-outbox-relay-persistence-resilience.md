# Hardening for Outbox Relay CLI, Persistence Endpoint Resilience, Provider-Neutral Batch Aliases, and Directory Normalizer

**Goal:** Provide graceful fallback and clean output during offline publication outbox relay batches, add standard CLI flag support (`--once`, `--limit`, `--max-attempts`, `--poll-seconds`) to `outbox_relay.py`, implement host database and S3 endpoint resolution in worker persistence modules, export canonical provider-neutral bank batch aliases, and support `--limit` in the directory normalizer.

**Architecture:** 
1. **Outbox Relay Ergonomics & NATS Resilience:** `scripts/dev/outbox_relay.py` runs on developer host environments outside Docker. Worker virtual environment discovery and `sys.path` resolution ensure `autodata_enrichment` is importable. `outbox.py` resolves NATS URL via `_resolve_nats_url` (probing `127.0.0.1:4222` and container hostname resolution) and configures a silent error callback to report `skipped (broker unreachable: ...)` cleanly without polluting `stderr` with unhandled tracebacks.
2. **Ingestion Persistence Endpoint Resilience:** Ingestion worker persistence modules (`autodata_ingestion.bundle_persistence`, `vehicle_selection_persistence`, and `derived_article_persistence`) automatically probe `127.0.0.1:5432` and `127.0.0.1:9000` via `_resolve_database_address` and `_resolve_s3_endpoint`, eliminating connection failures on host runs when container DNS aliases (`postgres`, `minio`) are not exported.
3. **Provider-Neutral Bank Batch Aliases:** `autodata_ingestion.bankone_batch` exports canonical provider-neutral aliases `BankBatch`, `execute_bank_batch`, and `build_bank_batch_plan`, enabling `scripts/dev/ingest_banktwo_service.py` and future multi-bank connectors to ingest catalog batches neutrally.
4. **Source Directory Normalizer Ergonomics:** `scripts/dev/normalize_source_directory.py` supports `--limit` to bound source resource adaptation and extraction during quick local exploratory inspections.

**Tech Stack:** Python 3.12+, NATS JetStream, MinIO / S3, PostgreSQL with pgvector, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/151

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Add worker `sys.path` resolution and `argparse` CLI parsing (`--once`, `--limit`, `--max-attempts`, `--poll-seconds`) to `scripts/dev/outbox_relay.py`.
- [x] Add `_resolve_nats_url` and silent error callback handling for unreachable NATS brokers in `workers/enrichment-python/src/autodata_enrichment/outbox.py`.
- [x] Add `_resolve_database_address` and `_resolve_s3_endpoint` to `workers/ingestion-python/src/autodata_ingestion/bundle_persistence.py`.
- [x] Integrate `_resolve_database_address` into `autodata_ingestion.vehicle_selection_persistence` and `autodata_ingestion.derived_article_persistence`.
- [x] Export provider-neutral aliases (`BankBatch`, `execute_bank_batch`, `build_bank_batch_plan`) in `autodata_ingestion.bankone_batch`.
- [x] Update `scripts/dev/ingest_banktwo_service.py` to use `BankBatch` and `execute_bank_batch`.
- [x] Add `--limit` CLI option to `scripts/dev/normalize_source_directory.py`.
- [x] Add unit tests in `scripts/dev/test_storage_messaging_operations.py` and `scripts/dev/test_bank_topology.py`.
- [x] Update documentation in `docs/architecture/infrastructure-and-dev.md` and create pre-implementation record in `docs/agents/records/2026-10-27-outbox-relay-persistence-resilience.json`.
- [x] Prune stale remote tracking branches and verify local Compose/daemon stacks.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Persistence and messaging adapters maintain isolated connection parameters and fall back safely to local developer defaults.
