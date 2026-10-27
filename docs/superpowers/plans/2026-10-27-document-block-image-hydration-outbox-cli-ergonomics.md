# Hardening for Document Block Image Hydration, List Normalization, Outbox CLI Ergonomics, and Dev Resilience

**Goal:** Enhance `hydrate_article_image_urls` in `autodata_ingestion.procedure_images` to hydrate direct `images` lists on arbitrary blocks and traverse `children` blocks in `normalized_document`, expand dictionary item text keys in `article_document._list_block` and support callout images in `_callout_block`, add `--address`/`--database-url` and `--nats-url` CLI arguments to `scripts/dev/replay_outbox.py` and `scripts/dev/outbox_relay.py`, add template variables to `.env.example`, expand test suites in ingestion worker and dev scripts, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Document Block Image Hydration in `procedure_images.py`:**
   - In `hydrate_article_image_urls(article, embed_data_uri=False)`:
     - In `hydrate_block(block)`:
       - Hydrate direct `images` lists on arbitrary blocks (`block.get("images")`), ensuring localized `storage_key` and `image_id` are hydrated to `artifact://{image_id}` or inline `data:image/...` URLs when `embed_data_uri=True`.
       - Recursively traverse child blocks under `block.get("children")` in addition to `block.get("blocks")`.
2. **List Item & Callout Document Normalization in `article_document.py`:**
   - In `_list_block(article, source_order, raw, evidence_ids, kind)`:
     - For dictionary list items, inspect `content`, `body`, and `message` in addition to `text`, `value`, and `label`.
   - In `_callout_block(article, source_order, raw, evidence_ids, kind)`:
     - Support normalizing and attaching direct `images` lists from `raw.get("images")` using `_normalize_cell_image(img)`.
3. **Outbox Replay & Relay CLI Ergonomics in `scripts/dev`:**
   - In `scripts/dev/replay_outbox.py`:
     - Add `--address` and `--database-url` options.
     - Pass the resolved address into `_db_connection(address: str | None = None)`.
   - In `scripts/dev/outbox_relay.py`:
     - Add `--address`, `--database-url`, and `--nats-url` options.
     - Wire resolved addresses into environment variables `AUTODATA_DB_ADDRESS` and `AUTODATA_NATS_URL` before invoking `relay_pending_events`.
4. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_procedure_images.py`:
     - Add unit tests verifying `hydrate_article_image_urls` hydrates direct block images on arbitrary blocks (e.g. callouts, steps, sections) and nested child blocks under `children`, for both default artifact URLs and `embed_data_uri=True`.
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit tests verifying `_list_block` dictionary items with `content`, `body`, and `message`, and `_callout_block` with images.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Include `"outbox_relay.py"` in `test_developer_scripts_discover_worker_virtualenvs`.
     - Expand `test_developer_scripts_support_cli_argv` to assert `--address` for `replay_outbox.py` and `--address`, `--nats-url` for `outbox_relay.py`.
5. **Workspace & Documentation Housekeeping:**
   - In `.env.example`: Add `AUTODATA_IMAGE_URL_KEY`, `AUTODATA_NATS_URL`, and `AUTODATA_OUTBOX_*` configuration variables.
   - In `docs/architecture/infrastructure-and-dev.md`: Document document block image hydration, list normalization, callout images, and outbox CLI ergonomics.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/168

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Enhance `hydrate_article_image_urls` in `autodata_ingestion.procedure_images` to hydrate direct block `images` lists and traverse `children` blocks.
- [x] Expand dictionary list item normalization keys in `article_document._list_block` and support callout images in `_callout_block`.
- [x] Add `--address` and `--database-url` arguments in `scripts/dev/replay_outbox.py`.
- [x] Add `--address`, `--database-url`, and `--nats-url` arguments in `scripts/dev/outbox_relay.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_procedure_images.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_article_document.py`.
- [x] Expand virtualenv discovery and CLI argument assertions in `scripts/dev/test_storage_messaging_operations.py`.
- [x] Add template variables to `.env.example`.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-document-block-image-hydration-outbox-cli-ergonomics.json`.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
