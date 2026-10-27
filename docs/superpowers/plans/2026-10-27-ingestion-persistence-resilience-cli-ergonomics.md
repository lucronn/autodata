# Hardening for Ingestion Persistence Resilience, Provider-Neutral Batch CLI, and Developer Ergonomics

**Goal:** Provide host-level database and S3 endpoint resolution across all remaining ingestion persistence and runtime modules, add `--limit` CLI option and worker virtual environment discovery to `ingest_bankone_batch.py`, standardize on provider-neutral `BankBatch` and `execute_bank_batch` in `ingest_bankone_service.py` and `ingest_bankone_batch.py`, enhance `replay_outbox.py` and `fake_integrations_smoke.py` with worker site-packages discovery and programmatic `main(argv=None)` invocation, and update technical documentation.

**Architecture:**
1. **Ingestion Worker Host Endpoint Resilience:** Worker modules operating outside container networks probe `127.0.0.1:5432` and `127.0.0.1:9000` via `_resolve_database_address` and `_resolve_s3_endpoint` in `autodata_ingestion.bundle_persistence`. Modules including `bankone_job_persistence.py`, `procedure_images.py`, `catalog_sync.py`, `knowledge_catalog.py`, `catalog_service.py`, `chat_durable_runtime.py`, `knowledge_fallback_runtime.py`, and `ingest_fixture.py` seamlessly use these resolvers, ensuring local developer workstation commands and tests run cleanly without container DNS aliasing.
2. **Provider-Neutral Bank Batch CLI Ergonomics:** `scripts/dev/ingest_bankone_batch.py` imports canonical provider-neutral aliases `BankBatch`, `execute_bank_batch`, and `build_bank_batch_plan`, auto-discovers worker virtual environment packages, supports `--limit` to bound execution, and provides programmatic `main(argv=None)` entry point. `scripts/dev/ingest_bankone_service.py` adopts `BankBatch` and `execute_bank_batch` to align with `ingest_banktwo_service.py`.
3. **Developer Script Ergonomics:** `scripts/dev/replay_outbox.py` and `scripts/dev/fake_integrations_smoke.py` auto-discover worker virtual environment site-packages and support programmatic `main(argv=None)`.
4. **Codebase Housekeeping & Test Verification:** Unit tests in `scripts/dev/test_storage_messaging_operations.py` verify database and S3 resolver adoption across ingestion modules, CLI flag parsing for `--limit` in `ingest_bankone_batch.py`, and programmatic execution in `replay_outbox.py`. Tests in `scripts/dev/test_bank_topology.py` assert provider-neutral alias usage in `ingest_bankone_service.py` and `ingest_bankone_batch.py`.
5. **Documentation Housekeeping:** Canonical documentation in `docs/architecture/infrastructure-and-dev.md` and `docs/architecture/independent-bank-connectors.md` reflects full endpoint resilience, CLI options, and provider-neutral bank batch operations.

**Tech Stack:** Python 3.12+, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/153

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Add `_resolve_database_address` to `autodata_ingestion.bankone_job_persistence` in `create_bankone_jobs` and `_connection`.
- [x] Add `_resolve_s3_endpoint` to `autodata_ingestion.procedure_images` in `_put_object` and `_read_storage_bytes`.
- [x] Add `_resolve_database_address` to `autodata_ingestion.catalog_sync` in `_conninfo`.
- [x] Add `_resolve_database_address` to `autodata_ingestion.knowledge_catalog` in `_search_catalog_articles`.
- [x] Add `_resolve_database_address` to `autodata_ingestion.catalog_service` in `report_catalog_hydration_progress`.
- [x] Add `_resolve_database_address` to `autodata_ingestion.chat_durable_runtime` in `_open_postgres_from_environment`.
- [x] Add `_resolve_database_address` to `autodata_ingestion.knowledge_fallback_runtime` in `_conninfo`.
- [x] Add `_resolve_database_address` and `_resolve_s3_endpoint` to `autodata_ingestion.ingest_fixture`.
- [x] Add worker venv discovery, `--limit`, provider-neutral `BankBatch` aliases, and `main(argv=None)` to `scripts/dev/ingest_bankone_batch.py`.
- [x] Update `scripts/dev/ingest_bankone_service.py` to use `BankBatch` and `execute_bank_batch`.
- [x] Add worker venv discovery and `main(argv=None)` to `scripts/dev/replay_outbox.py` and `scripts/dev/fake_integrations_smoke.py`.
- [x] Add tests in `scripts/dev/test_storage_messaging_operations.py` and `scripts/dev/test_bank_topology.py`.
- [x] Update canonical documentation in `docs/architecture/infrastructure-and-dev.md` and `docs/architecture/independent-bank-connectors.md`.
- [x] Validate preflight gate record in `docs/agents/records/2026-10-27-ingestion-persistence-resilience-cli-ergonomics.json`.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Persistence and messaging adapters maintain isolated connection parameters and fall back safely to local developer defaults.
