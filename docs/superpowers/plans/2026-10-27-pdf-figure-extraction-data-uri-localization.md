# Hardening for PDF Figure Extraction, Data-URI Image Localization, and Developer Script Ergonomics

**Goal:** Provide browser-safe figure extraction from PDF source documents with cross-page deduplication, inline data-URI figure localization into MinIO/S3 object storage (`procedure-images/<sha256>`), endpoint resolution parity across procedure image persistence, worker virtual environment auto-discovery across developer and smoke scripts, standalone test execution, and canonical documentation updates.

**Architecture:**
1. **PDF Embedded Figure Extraction & Deduplication:** In `workers/ingestion-python/src/autodata_ingestion/source_adapters.py`, extract embedded images from PDF pages, normalize payloads to browser-safe RGB PNG/JPEG via PIL, filter recurring header/footer logos appearing across multiple pages, and attach figure records to the first candidate page text. In `source_bundle.py`, preserve image records during candidate merging and deduplicate by storage key or URL. In `article_document.py`, pull figures into document blocks when "Figure X" captions are referenced, append remaining figures, and keep `source_order` and `block_id` sequences contiguous.
2. **Data-URI Figure Localization & Endpoint Probing:** In `workers/ingestion-python/src/autodata_ingestion/procedure_images.py`, implement `_localize_data_uri_image` to decode base64 data URIs, calculate SHA256 digests, persist objects to `procedure-images/<sha256>` in S3/MinIO, and assign `artifact://` URLs. Ensure `_put_object` and `_read_storage_bytes` import and use `_resolve_s3_endpoint` from `bundle_persistence` to maintain developer host probing (`127.0.0.1:9000`).
3. **Developer Script Ergonomics & Virtual Environment Discovery:** In `scripts/dev/normalize_source_directory.py`, `scripts/dev/reconcile_payments.py`, `scripts/dev/ingest_bankone_service.py`, `scripts/dev/ingest_banktwo_service.py`, `scripts/dev/deep_lane_smoke.py`, and `scripts/dev/smoke_local_stack.py`, auto-discover worker virtual environment site-packages in `sys.path` and support programmatic `main(argv=None)`. In `deep_lane_smoke.py`, remove duplicate import definitions.
4. **Workspace Housekeeping:** Organize ad-hoc debugging scripts from the workspace root `/home/corp/autodata` into `/home/corp/autodata/scratch/`.
5. **Codebase Housekeeping & Test Verification:** In `workers/ingestion-python/tests/test_procedure_images.py`, add `sys.path` initialization for standalone test execution, and add unit tests for `_localize_data_uri_image` (successful payload persistence and malformed URI error handling). In `scripts/dev/test_storage_messaging_operations.py`, test worker virtual environment discovery and CLI argument parsing across all updated developer scripts.
6. **Documentation Housekeeping:** Canonical documentation in `docs/architecture/infrastructure-and-dev.md` reflects PDF figure extraction, inline data-URI localization, and developer script virtual environment discovery.

**Tech Stack:** Python 3.12+, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/155

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Implement browser-safe PDF figure extraction and deduplication in `autodata_ingestion.source_adapters`.
- [x] Merge document candidate image records and deduplicate in `autodata_ingestion.source_bundle`.
- [x] Pull figures into document blocks on caption reference and renumber in `autodata_ingestion.article_document`.
- [x] Implement `_localize_data_uri_image` and restore `_resolve_s3_endpoint` in `autodata_ingestion.procedure_images`.
- [x] Add worker venv discovery and `main(argv=None)` to `scripts/dev/normalize_source_directory.py`.
- [x] Add worker venv discovery to `scripts/dev/reconcile_payments.py`.
- [x] Add worker venv discovery and `main(argv=None)` to `scripts/dev/ingest_bankone_service.py` and `scripts/dev/ingest_banktwo_service.py`.
- [x] Clean up duplicate imports, add worker venv discovery, and support `main(argv=None)` in `scripts/dev/deep_lane_smoke.py`.
- [x] Support `main(argv=None)` in `scripts/dev/smoke_local_stack.py`.
- [x] Organize workspace root temporary scripts into `/home/corp/autodata/scratch/`.
- [x] Add standalone test setup and unit tests for `_localize_data_uri_image` in `test_procedure_images.py`.
- [x] Add tests for developer scripts venv discovery and CLI parsing in `scripts/dev/test_storage_messaging_operations.py`.
- [x] Update canonical documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-pdf-figure-extraction-data-uri-localization.json`.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage and database adapters maintain isolated connection parameters and fall back safely to local developer defaults.
