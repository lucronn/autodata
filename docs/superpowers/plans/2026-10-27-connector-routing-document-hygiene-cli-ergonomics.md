# Hardening for Connector Routing Resilience, Document Block Image Hygiene, List Normalization, and Ingestion Smoke CLI Ergonomics

**Goal:** Enhance `_read_asset_resource` in `autodata_ingestion.procedure_images` to dynamically resolve connector prefixes and check registered source connectors, enhance `_collect_image_records` and `_rewrite_document_images` to collect and rewrite direct `images` lists on arbitrary blocks in `normalized_document`, fix dictionary list item handling in `article_document._list_block` and expand callout block text fields, add `--address`, `--s3-endpoint`, and `--nats-url` CLI arguments to `scripts/dev/ingestion_smoke.py`, expand test suites, update canonical architecture documentation, prune merged automation branches, and record verified delivery.

**Architecture:**
1. **Connector Routing Resilience in `procedure_images.py`:**
   - In `_read_asset_resource(resource_ref: str)`: Inspect `source_connector_registry(include_defaults=True)`. If `resource_ref` contains a connector prefix (e.g. `bankone:asset/...`, `banktwo:asset/...`), resolve that connector; otherwise default to `banktwo`. If the connector is missing from the registry, raise a descriptive `ValueError` rather than an unhandled `KeyError`.
2. **Block Image Localization & Document Structure Hygiene:**
   - In `_collect_image_records(article)`: In addition to table/grid cells and dedicated `image` blocks, traverse `normalized_document` blocks and collect direct `images` lists on any block (callouts, steps, sections) as well as nested blocks under `children`.
   - In `_rewrite_document_images(article, original_images, stored=None)`: Recursively rewrite direct `images` lists on blocks so that localized `storage_key`, `asset_id`, `image_id`, `url` (`artifact://{image_id}`), and `status: "available"` are accurately populated.
3. **List & Callout Normalization Hygiene in `article_document.py`:**
   - In `_list_block(article, source_order, raw, evidence_ids, kind)`: When items are dictionaries, extract clean text from `text`, `value`, or `label` keys, preventing raw dictionary string representations like `"{'text': 'step 1'}"`.
   - In `_callout_block(article, source_order, raw, evidence_ids, kind)`: Check `message`, `content`, and `body` in addition to `text` and `value` to extract clean callout text.
4. **Ingestion Smoke CLI Ergonomics in `scripts/dev/ingestion_smoke.py`:**
   - Add `--address`, `--s3-endpoint`, and `--nats-url` options with defaults from `resolve_database_address()`, `resolve_s3_endpoint()`, and `resolve_nats_url()`.
   - Pass the resolved connection parameters into `_read_database`, `_read_object`, and `_read_event`.
5. **Codebase Housekeeping & Test Verification:**
   - Add unit tests in `workers/ingestion-python/tests/test_procedure_images.py` verifying connector prefix routing in `_read_asset_resource`, descriptive error handling for unconfigured connectors, and collection/rewriting of arbitrary block `images`.
   - Add unit tests in `workers/ingestion-python/tests/test_article_document.py` verifying dictionary items in `_list_block` and message/content in `_callout_block`.
   - In `scripts/dev/test_storage_messaging_operations.py`: Expand `test_developer_scripts_support_cli_argv` to assert `--address`, `--s3-endpoint`, and `--nats-url` for `ingestion_smoke.py`.
6. **Workspace Housekeeping:**
   - Prune merged automation remote branches.
7. **Documentation Housekeeping:**
   - Update `docs/architecture/infrastructure-and-dev.md` with connector prefix routing, block image localization, list normalization, and ingestion smoke CLI ergonomics.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/165

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Enhance `_read_asset_resource` in `autodata_ingestion.procedure_images` with dynamic connector prefix routing and descriptive error handling.
- [x] Enhance `_collect_image_records` and `_rewrite_document_images` in `procedure_images.py` to handle direct block `images` lists and child blocks.
- [x] Fix dictionary list item normalization in `article_document._list_block` and expand text keys in `_callout_block`.
- [x] Add `--address`, `--s3-endpoint`, and `--nats-url` arguments in `scripts/dev/ingestion_smoke.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_procedure_images.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_article_document.py`.
- [x] Expand CLI argument assertion in `scripts/dev/test_storage_messaging_operations.py`.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-connector-routing-document-hygiene-cli-ergonomics.json`.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage, database, and connector adapters maintain isolated connection parameters and fall back safely to local developer defaults.
