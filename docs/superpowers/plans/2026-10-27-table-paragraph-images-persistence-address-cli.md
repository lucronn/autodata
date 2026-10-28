# Hardening for Table/Paragraph Images, Persistence Address Propagation, Outbox Parameters, and CLI Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` by supporting attached row-level images in `_table_block`, deduplicating table and paragraph attached images using `_image_identities`, supporting singular `evidence_id` in `_evidence_ids`, and adding `title` fallback for caption in `_image_block`; add `address` override parameter to `persist_vehicle_selection_list` in `vehicle_selection_persistence.py`, `_conninfo` in `catalog_sync.py`, `persist_catalog_years` in `catalog_years.py`, and `persist_fast_lane` in `ingest_fixture.py`; add `address` and `nats_url` parameters to `relay_pending_events` and outbox delivery helpers in `autodata_enrichment.outbox`, passing them from `scripts/dev/outbox_relay.py`; add `--address` and `--s3-address` CLI options to `scripts/dev/object_storage_health.py`, add `--address` and `--nats-address` CLI options to `scripts/dev/nats_health.py` with scheme normalization, add `--endpoint`, `--s3-address`, and `--url` CLI options to `scripts/dev/ingestion_smoke.py`, add `--url` CLI option to `scripts/dev/outbox_relay.py`, add `-q` short option to `scripts/dev/knowledge_warm_path_benchmark.py`; expand assertions in `scripts/dev/test_storage_messaging_operations.py`; expand unit tests in `workers/ingestion-python/tests/test_article_document.py` and `workers/ingestion-python/tests/test_vehicle_selection_persistence.py`; update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`; update `.env.example`; and record verified delivery.

**Architecture:**
1. **Document Normalization & Image Hygiene in `article_document.py`:**
   - In `_table_block(article, source_order, raw, evidence_ids)`:
     - Support row-level attached images from `row.get("images")` for dictionary rows, aggregating them into `clean_images`.
     - Deduplicate all collected table images in `clean_images` using `_image_identities`, aligning with `_list_block`, `_callout_block`, and `_step_block`.
   - In paragraph block normalization (`_document_from_blocks` / `_base_block` text fallback):
     - Deduplicate paragraph images using `_image_identities` before assigning to `extra_fields["images"]`.
   - In `_evidence_ids(raw: Mapping[str, Any], article: Mapping[str, Any]) -> list[str]`:
     - Support `raw.get("evidence_id")` and `article.get("evidence_id")` singular attributes in addition to plural `evidence_ids`.
   - In `_image_block(article, source_order, raw, evidence_ids)`:
     - Add `title` fallback for caption (`_clean_text(raw.get("caption") or raw.get("label") or raw.get("description") or raw.get("legend") or raw.get("title"))`), matching `_normalize_cell_image`.
2. **Persistence Address & Parameter Propagation:**
   - In `persist_vehicle_selection_list` (`workers/ingestion-python/src/autodata_ingestion/vehicle_selection_persistence.py`):
     - Add `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`.
   - In `_conninfo` (`workers/ingestion-python/src/autodata_ingestion/catalog_sync.py`):
     - Add `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`. Propagate `address` through `_claim`, `_finish`, and `_persist_batch`.
   - In `persist_catalog_years` (`workers/ingestion-python/src/autodata_ingestion/catalog_years.py`):
     - Add `address: str | None = None` parameter and pass it into `_conninfo(address=address)`.
   - In `persist_fast_lane` (`workers/ingestion-python/src/autodata_ingestion/ingest_fixture.py`):
     - Add `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`.
3. **Outbox Parameter Propagation in `outbox.py` & `outbox_relay.py`:**
   - In `workers/enrichment-python/src/autodata_enrichment/outbox.py`:
     - Add `address: str | None = None` and `nats_url: str | None = None` parameters to `relay_pending_events`, `claim_pending_events`, `record_delivery_success`, and `record_delivery_failure`. Pass `address` to `_connection_kwargs(address=address)` and `nats_url` to `_resolve_nats_url(nats_url)`.
   - In `scripts/dev/outbox_relay.py`:
     - Pass `address=args.address, nats_url=args.nats_url` to `relay_pending_events`.
4. **Developer Script CLI Ergonomics & URL Uniformity in `scripts/dev`:**
   - In `scripts/dev/object_storage_health.py`:
     - Add `--address` and `--s3-address` CLI arguments as aliases alongside `--endpoint` and `--s3-endpoint`.
   - In `scripts/dev/nats_health.py`:
     - Add `--address` and `--nats-address` CLI arguments as aliases alongside `--url` and `--nats-url`, and normalize host:port strings in `resolve_nats_url` by prepending `nats://` when scheme is absent.
   - In `scripts/dev/ingestion_smoke.py`:
     - Add `--endpoint` and `--s3-address` aliases to `--s3-endpoint`, and add `--url` alias to `--nats-url`.
   - In `scripts/dev/outbox_relay.py`:
     - Add `--url` alias to `--nats-url`.
   - In `scripts/dev/knowledge_warm_path_benchmark.py`:
     - Add `-q` short option alias for `--query`.
5. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit tests for table row-level images and table image deduplication.
     - Add unit test for paragraph image deduplication via `_image_identities`.
     - Add unit test for `_evidence_ids` with singular `evidence_id`.
     - Add unit test for `_image_block` caption fallback to `title`.
   - In `workers/ingestion-python/tests/test_vehicle_selection_persistence.py`:
     - Add unit test for `persist_vehicle_selection_list` with explicit `address` parameter.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Assert `--address` and `--s3-address` on `object_storage_health.py`.
     - Assert `--address` and `--nats-address` on `nats_health.py` and scheme normalization.
     - Assert `--endpoint` and `--s3-address` on `ingestion_smoke.py`.
     - Assert `--url` on `outbox_relay.py`.
     - Assert `-q` on `knowledge_warm_path_benchmark.py`.
     - Assert `_connection_kwargs` address override in `autodata_enrichment.outbox`.
     - Assert `_conninfo` address override in `autodata_ingestion.catalog_sync`.
6. **Workspace & Documentation Housekeeping:**
   - Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
   - Update `.env.example` with developer CLI options.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/182

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Support row-level attached images in _table_block in article_document.py.
- [x] Deduplicate clean_images using _image_identities in _table_block in article_document.py.
- [x] Deduplicate clean_images using _image_identities in paragraph blocks in article_document.py.
- [x] Support singular evidence_id in _evidence_ids in article_document.py.
- [x] Support title fallback for caption in _image_block in article_document.py.
- [x] Add address parameter to persist_vehicle_selection_list in vehicle_selection_persistence.py.
- [x] Add address parameter to _conninfo in catalog_sync.py and propagate to _claim, _finish, and _persist_batch.
- [x] Add address parameter to persist_catalog_years in catalog_years.py.
- [x] Add address parameter to persist_fast_lane in ingest_fixture.py.
- [x] Add address and nats_url parameters to relay_pending_events, claim_pending_events, and delivery helpers in outbox.py.
- [x] Forward address and nats_url arguments from outbox_relay.py to relay_pending_events.
- [x] Add --address and --s3-address CLI arguments to object_storage_health.py.
- [x] Add --address and --nats-address CLI arguments to nats_health.py and normalize scheme.
- [x] Add --endpoint, --s3-address, and --url CLI arguments to ingestion_smoke.py.
- [x] Add --url CLI argument to outbox_relay.py.
- [x] Add -q short option for --query in knowledge_warm_path_benchmark.py.
- [x] Add unit tests for table row images, table image dedup, paragraph image dedup, singular evidence_id, and image block title caption fallback in test_article_document.py.
- [x] Add unit test for persist_vehicle_selection_list address parameter in test_vehicle_selection_persistence.py.
- [x] Expand CLI argument and persistence assertions in test_storage_messaging_operations.py.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Update .env.example with developer CLI options.
- [x] Record delivery in docs/agents/records/2026-10-27-table-paragraph-images-persistence-address-cli.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
