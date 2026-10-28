# Hardening for Callout/Step Images, Image Lookup Resilience, Persistence Address Propagation, and CLI Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` by supporting attached item-level images in `_callout_block` and `_step_block`, supporting `uri` and `path` in `_image_identities`, supporting `title` fallback for caption in `_normalize_cell_image`, expand image lookup in `autodata_ingestion.procedure_images` to resolve `source_url`, `src`, `href`, `uri`, and `path`, include `source_url` in `autodata_ingestion.source_bundle` image identity resolution, add `address` override parameter to `persist_derived_article` in `derived_article_persistence.py`, add `address` override parameter to `persist_bankone_article_fetch_jobs` in `bankone_job_persistence.py`, add `address` parameter to `execute_bankone_batch` in `bankone_batch.py` and pass `address=args.address` in `ingest_bankone_batch.py`, add `--address` and `--database-url` CLI arguments to `scripts/dev/backup_restore_smoke.py`, expand CLI argument and persistence assertions in `scripts/dev/test_storage_messaging_operations.py`, expand unit tests in `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/tests/test_procedure_images.py`, `workers/ingestion-python/tests/test_derived_article_persistence.py`, and `workers/ingestion-python/tests/test_bankone_job_persistence.py`, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Document Normalization & Image Hygiene in `article_document.py`:**
   - In `_image_identities(image: Mapping[str, Any]) -> set[str]`:
     - Add `image.get("uri")` and `image.get("path")` to the identity key tuple, ensuring image URI/path identifiers deduplicate properly against the document figure queue.
   - In `_normalize_cell_image(raw: Mapping[str, Any]) -> dict[str, Any]`:
     - Support `title` fallback for `caption` (`_clean_text(raw.get("caption") or raw.get("label") or raw.get("description") or raw.get("legend") or raw.get("title"))`), aligning with `_image_block`.
   - In `_callout_block(article, source_order, raw, evidence_ids, kind)`:
     - Support attached item-level images from `item.get("images")` for dictionary items in `raw.get("items")`, aggregating them into `clean_images` and deduplicating by `_image_identities`, preserving them in `extra_fields["images"]`.
   - In `_step_block(article, source_order, raw, evidence_ids)`:
     - Support attached item-level images from `item.get("images")` for dictionary instructions in `raw.get("instructions")`, aggregating them into `clean_images` and deduplicating by `_image_identities`, preserving them in `extra_fields["images"]`.
2. **Image Lookup Resilience & Bundle Normalization in `procedure_images.py` & `source_bundle.py`:**
   - In `_rewrite_document_images` (`workers/ingestion-python/src/autodata_ingestion/procedure_images.py`):
     - In `by_ref` initialization: add `image.get("source_url")`, `image.get("uri")`, and `image.get("path")` to the identity key loop.
     - In `_lookup(obj)`: add `obj.get("source_url")`, `obj.get("src")`, `obj.get("href")`, `obj.get("uri")`, and `obj.get("path")` to candidates.
   - In `_normalize_artifacts_images` and `_document_content_record` (`workers/ingestion-python/src/autodata_ingestion/source_bundle.py`):
     - Include `image.get("source_url")` in identity key computation, matching `article_document.py`.
3. **Persistence Address Propagation & Ingestion Batch Ergonomics in `derived_article_persistence.py`, `bankone_job_persistence.py`, and `bankone_batch.py`:**
   - In `persist_derived_article` (`workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py`):
     - Add `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`, fixing unpassed address overrides.
   - In `persist_bankone_article_fetch_jobs` (`workers/ingestion-python/src/autodata_ingestion/bankone_job_persistence.py`):
     - Add `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`.
   - In `execute_bankone_batch` / `execute_bank_batch` (`workers/ingestion-python/src/autodata_ingestion/bankone_batch.py`):
     - Add `address: str | None = None` parameter and pass it to `persist_source_bundle` and `persist_bankone_article_fetch_jobs`.
   - In `scripts/dev/ingest_bankone_batch.py`:
     - Pass `address=args.address` to `execute_bank_batch`.
4. **Developer Operations & CLI Uniformity in `scripts/dev`:**
   - In `backup_restore_smoke.py` (`scripts/dev/backup_restore_smoke.py`):
     - Add `--address` and `--database-url` CLI arguments as aliases, setting `os.environ["AUTODATA_DB_ADDRESS"]` when provided.
   - In `test_storage_messaging_operations.py` (`scripts/dev/test_storage_messaging_operations.py`):
     - Assert `--address` and `--database-url` on `backup_restore_smoke.py`.
     - Assert `_resolve_database_address` in `derived_article_persistence.py` and `bankone_job_persistence.py`.
5. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit test verifying `_image_identities` includes `uri` and `path`.
     - Add unit test verifying `_normalize_cell_image` caption falls back to `title`.
     - Add unit test verifying `_callout_block` aggregates item-level images from `items`.
     - Add unit test verifying `_step_block` aggregates item-level images from `instructions`.
   - In `workers/ingestion-python/tests/test_procedure_images.py`:
     - Add unit test verifying `_rewrite_document_images` resolves images with `source_url`, `src`, and `href`.
   - In `workers/ingestion-python/tests/test_derived_article_persistence.py`:
     - Add unit test verifying `persist_derived_article` accepts explicit `address` parameter.
   - In `workers/ingestion-python/tests/test_bankone_job_persistence.py`:
     - Add unit test verifying `persist_bankone_article_fetch_jobs` accepts explicit `address` parameter.
6. **Workspace & Documentation Housekeeping:**
   - Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
   - Update `.env.example` with developer CLI options.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/180

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Add uri and path to _image_identities in article_document.py.
- [x] Support title fallback for caption in _normalize_cell_image in article_document.py.
- [x] Support attached item-level images in _callout_block in article_document.py.
- [x] Support attached item-level images in _step_block in article_document.py.
- [x] Add source_url, src, href, uri, path to image rewriting lookup in procedure_images.py.
- [x] Include source_url in image identity resolution in source_bundle.py.
- [x] Add address parameter to persist_derived_article in derived_article_persistence.py.
- [x] Add address parameter to persist_bankone_article_fetch_jobs in bankone_job_persistence.py.
- [x] Add address parameter to execute_bankone_batch in bankone_batch.py and pass from ingest_bankone_batch.py.
- [x] Add --address and --database-url CLI options in backup_restore_smoke.py.
- [x] Expand CLI argument and persistence assertions in test_storage_messaging_operations.py.
- [x] Add unit tests for callout item images, step item images, image identities uri/path, and cell image caption title fallback in test_article_document.py.
- [x] Add unit test for procedure_images source_url, src, href resolution in test_procedure_images.py.
- [x] Add unit test for persist_derived_article address parameter in test_derived_article_persistence.py.
- [x] Add unit test for persist_bankone_article_fetch_jobs address parameter in test_bankone_job_persistence.py.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Update .env.example with developer CLI options.
- [x] Record delivery in docs/agents/records/2026-10-27-callout-step-images-persistence-address-cli.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
