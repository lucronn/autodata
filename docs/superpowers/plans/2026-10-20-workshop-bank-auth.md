# Restore Server-Side Bankone and Banktwo Authentication for Workshop Plan

**Goal:** Restore server-side authentication for the Bankone and Banktwo calls used by Workshop, preserving service isolation and keeping plaintext credentials out of browser assets, logs, and version control.

**Architecture:** AutoData accesses independent upstream bank connectors via HTTP Source Connector v1 interfaces (`https://bankone.cars.tk` and `https://banktwo.cars.tk`). Ingestion services authenticate to each bank using isolated server-side credentials (`AUTODATA_BANKONE_API_KEY` and `AUTODATA_BANKTWO_API_KEY`) with graceful fallback to legacy tokens (`BANKONE_API_TOKEN` and `BANKTWO_API_TOKEN`). All authentication happens server-side within the ingestion HTTP and worker services; browser Workshop clients interact exclusively with AutoData Go API endpoints without access to upstream bank secrets.

**Tech Stack:** Go API, Python 3.12+ ingestion service, Source Connector v1, PostgreSQL with pgvector, MinIO / S3mock, Docker Compose, systemd.

**Issue:** https://github.com/lucronn/autodata/issues/139

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Reconcile managed API-key names with the registry and custom-origin facade; retain per-bank legacy-token fallback.
- [x] Pass independent credentials to Compose ingestion HTTP/worker services; document existing Kubernetes runtime Secret configuration.
- [x] Provision separate managed keys through the protected manager into ignored local mode-0600 configuration. Preserve all pre-existing keys.
- [x] Implement HTTP catalog hydration dispatcher (`/v1/catalog/ensure`) and background selector deepening thread (makes -> models -> configurations) to hydrate PostgreSQL cache.
- [x] Add HAL-JSON media type classification, embedded HAL article handling, and line-break preserving visible text parser for structured intake.
- [x] Run focused header isolation, fallback, catalog and Compose checks: 52 passed. Confirm no real keys occur in tracked files.
- [x] Run live canaries: Bankone 43 years / 33 makes for 2020; Banktwo 62 years / 55 makes for 2020. Both reject cross-service credentials with 401.
- [x] Bring up the local ingestion/database/NATS/object-storage backend and complete Workshop selection/article validation.

## Security and Credential Isolation Rules

- Each bank must have an independent credential (`AUTODATA_BANKONE_API_KEY` vs `AUTODATA_BANKTWO_API_KEY`).
- Ingestion services must never leak one bank's credentials to the other bank origin.
- Cross-service credentials must be rejected by upstreams with 401 Unauthorized.
- Plaintext API keys must never appear in version control, tracked files, test fixtures, docker images, or browser assets.
- Configuration containing real API keys must use local mode 0600 files ignored by git.
