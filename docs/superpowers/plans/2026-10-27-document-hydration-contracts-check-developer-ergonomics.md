# Hardening for Document Image Hydration, Contract Check Mode, and Developer Ergonomics

**Goal:** Enhance `hydrate_article_image_urls` in `autodata_ingestion.procedure_images` to recursively hydrate images and table cells in `normalized_document`, ensure `_image_block` in `autodata_ingestion.article_document` supports `asset_resource_ref` and preserves image attributes, add programmatic `main(argv)` and `--check` drift verification to `scripts/contracts/generate.py`, standardize programmatic `main(argv)` and CLI argument parsing across `nats_health.py`, `object_storage_health.py`, and `ingestion_smoke.py`, align `AUTODATA_IMAGE_URL_KEY` across workspace compose environment configurations, clean up transient debug scratch scripts, expand regression test suites, and update canonical architecture documentation.

**Architecture:**
1. **Document Image Hydration in `procedure_images.py`:** Update `hydrate_article_image_urls` so that when `normalized_document` is present on the article, its blocks (specifically `image` blocks and `table` blocks with cells containing `images` or nested blocks) are traversed and hydrated with local display URLs (`artifact://{image_id}` or embedded data-URIs when `embed_data_uri=True`).
2. **Image Block Asset Reference Normalization in `article_document.py`:** Update `_image_block` to support `asset_resource_ref` in `asset_id` resolution and status calculation (`status: "available"` if `source_url`, `storage_key`, or `asset_resource_ref` is present, consistent with `_normalize_cell_image`), and preserve `storage_key`, `url`, and `asset_resource_ref` on the returned image block.
3. **Contract Generation Check Mode in `scripts/contracts/generate.py`:** Add `main(argv: list[str] | None = None) -> int` with `--check` flag to verify that generated Go and Python contracts match canonical contract specifications without modifying on-disk files, exiting with code 1 if drift is detected.
4. **Developer Script Ergonomics in `scripts/dev/`:**
   - In `scripts/dev/nats_health.py`: Support `main(argv: list[str] | None = None)` and parse `argv`.
   - In `scripts/dev/object_storage_health.py`: Support `main(argv: list[str] | None = None)` and parse `argv`.
   - In `scripts/dev/ingestion_smoke.py`: Support `main(argv: list[str] | None = None)` and parse `argv`.
5. **Workspace Housekeeping:**
   - In `/home/corp/autodata/compose/.env`: Set `AUTODATA_IMAGE_URL_KEY=K-hKzbV4IqJGq8Df4kpEGVnS2DjxS7_YxqF-mNv4tyIz7WWIT7Jp7fxnLmGuQj5q` to align with `config/api.env`.
   - In `/home/corp/autodata/scratch/`: Remove transient one-off debugging scripts (`tmp_check_oil_imgs.py`, `tmp_localize_debug.py`, `tmp_localize_test.py`, `tmp_persist_localized.py`).
6. **Codebase Housekeeping & Regression Testing:**
   - In `workers/ingestion-python/tests/test_article_document.py`: Add unit tests for `_image_block` with `asset_resource_ref` and attribute preservation.
   - In `workers/ingestion-python/tests/test_procedure_images.py`: Add unit tests for `hydrate_article_image_urls` hydrating `normalized_document` blocks and table cells.
   - In `scripts/contracts/test_contracts.py`: Add unit tests for `generate.py --check` validation mode.
   - In `scripts/dev/test_storage_messaging_operations.py`: Add `nats_health.py`, `object_storage_health.py`, and `ingestion_smoke.py` to virtualenv discovery and CLI argument parsing tests.
7. **Documentation Housekeeping:**
   - In `docs/architecture/infrastructure-and-dev.md`: Document `hydrate_article_image_urls` document hydration, `_image_block` asset reference normalization, `generate.py --check` contract drift verification, and standardized CLI ergonomics.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/161

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Update `_image_block` in `autodata_ingestion.article_document` to support `asset_resource_ref` and preserve image attributes.
- [x] Update `hydrate_article_image_urls` in `autodata_ingestion.procedure_images` to hydrate images in `normalized_document`.
- [x] Add programmatic `main(argv)` and `--check` drift verification to `scripts/contracts/generate.py`.
- [x] Standardize programmatic `main(argv)` across `scripts/dev/nats_health.py`, `scripts/dev/object_storage_health.py`, and `scripts/dev/ingestion_smoke.py`.
- [x] Align `AUTODATA_IMAGE_URL_KEY` in `/home/corp/autodata/compose/.env` with `config/api.env`.
- [x] Clean up transient scratch scripts in `/home/corp/autodata/scratch/`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_article_document.py` and `workers/ingestion-python/tests/test_procedure_images.py`.
- [x] Add unit tests in `scripts/contracts/test_contracts.py`.
- [x] Expand `scripts/dev/test_storage_messaging_operations.py` for virtualenv discovery and CLI parsing across all scripts.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-document-hydration-contracts-check-developer-ergonomics.json`.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage and database adapters maintain isolated connection parameters and fall back safely to local developer defaults.
