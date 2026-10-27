# Hardening for Document Image Deduplication, Asset Reference Preservation, and Developer Script Ergonomics

**Goal:** Eliminate duplicate document image blocks when images are already present in source blocks or table cells in `article_document`, preserve asset resource references and non-empty falsy attributes during source bundle candidate image normalization in `source_bundle`, add worker virtual environment auto-discovery and programmatic `main(argv=None)` across all remaining developer and smoke scripts, expand regression test coverage, and update canonical architecture documentation.

**Architecture:**
1. **Document Image Deduplication:** In `workers/ingestion-python/src/autodata_ingestion/article_document.py`, track image identities (`image_id`, `storage_key`, `asset_id`, `url`, `content_sha256`) already processed in `source_blocks` (both standalone image blocks and nested table cell images). Filter `figure_queue` so pre-existing images are not appended again as duplicates at the end of ordered documents, while preserving contiguous `source_order` and `block_id` sequences.
2. **Asset Reference & Non-Empty Attribute Preservation:** In `workers/ingestion-python/src/autodata_ingestion/source_bundle.py`, preserve image records in `_resolve_document_images` that contain `asset_resource_ref` or `image_id` even when `url` or `storage_key` is not yet hydrated. Preserve falsy but non-empty values (such as `page: 0` or boolean flags) during dictionary attribute filtering. In `_document_content_record`, preserve `asset_resource_ref` during candidate identity merging.
3. **Developer Script Ergonomics & Virtual Environment Discovery:** In `scripts/dev/api_runtime_smoke.py`, `scripts/dev/backup_restore_smoke.py`, and `scripts/dev/operational_metrics.py`, auto-discover worker virtual environment site-packages in `sys.path` and support programmatic `main(argv=None)`. In `scripts/dev/payment_reconciliation_smoke.py`, `scripts/dev/universal_article_smoke.py`, and `scripts/dev/knowledge_warm_path_benchmark.py`, auto-discover worker virtual environment site-packages in `sys.path`.
4. **Codebase Housekeeping & Test Verification:** In `workers/ingestion-python/tests/test_article_document.py`, add unit tests asserting that pre-existing image blocks in `source_blocks` and nested table cells are not duplicated by `figure_queue`. In `workers/ingestion-python/tests/test_source_bundle.py`, add unit tests asserting preservation of images with `asset_resource_ref` and preservation of non-empty falsy attributes (`page: 0`). In `scripts/dev/test_storage_messaging_operations.py`, expand virtual environment auto-discovery tests and CLI argument parsing tests to cover all modernized developer scripts.
5. **Documentation Housekeeping:** Canonical documentation in `docs/architecture/infrastructure-and-dev.md` reflects document image deduplication, asset reference preservation, and universal developer script virtual environment discovery.

**Tech Stack:** Python 3.12+, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/157

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Track pre-existing image and table cell blocks to eliminate duplicate figure queue insertions in `autodata_ingestion.article_document`.
- [x] Preserve `asset_resource_ref` and non-empty falsy attributes in `autodata_ingestion.source_bundle` image normalization.
- [x] Add worker venv discovery and `main(argv=None)` to `scripts/dev/api_runtime_smoke.py`, `scripts/dev/backup_restore_smoke.py`, and `scripts/dev/operational_metrics.py`.
- [x] Add worker venv discovery to `scripts/dev/payment_reconciliation_smoke.py`, `scripts/dev/universal_article_smoke.py`, and `scripts/dev/knowledge_warm_path_benchmark.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_article_document.py` and `workers/ingestion-python/tests/test_source_bundle.py`.
- [x] Expand `scripts/dev/test_storage_messaging_operations.py` for venv discovery and CLI parsing across all modernized developer scripts.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-document-image-deduplication-developer-ergonomics.json`.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage and database adapters maintain isolated connection parameters and fall back safely to local developer defaults.
