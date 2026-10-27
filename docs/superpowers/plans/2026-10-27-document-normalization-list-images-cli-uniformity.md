# Hardening for Document Step Compatibility, List Image Preservation, and Dev CLI Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` by extracting clean text from dictionary/mapping instruction elements in `document_from_steps` and `_blocks_from_steps`, preserve attached images on `_list_block` via `_normalize_cell_image`, pre-scan list item images in `build_ordered_document` to prevent duplicate trailing figures, add `--api-url` to `scripts/dev/smoke_local_stack.py` and `--base-url`/`--api-url` to `scripts/dev/fake_integrations_smoke.py`, expand CLI argument and database resolver assertions in `scripts/dev/test_storage_messaging_operations.py`, expand unit tests in `workers/ingestion-python/tests/test_article_document.py`, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Document Step Compatibility & List Image Preservation in `article_document.py`:**
   - In `document_from_steps(article)`:
     - When iterating over `step.get("instructions")`: safely inspect mapping items to extract clean text from `text`, `action`, `instruction`, `value`, `content`, or `body`, preventing Python dictionary reprs from being serialized into step instruction text strings.
   - In `_blocks_from_steps(steps)`:
     - Safely extract clean text from mapping elements in `step.get("instructions")` before creating text blocks.
   - In `_list_block(article, source_order, raw, evidence_ids, kind)`:
     - Inspect `raw.get("images")`: normalize valid mapping images using `_normalize_cell_image(image)` and preserve them in `extra_fields["images"]`, mirroring `_callout_block`, `_step_block`, and `paragraph`.
   - In `build_ordered_document(article, blocks)`:
     - During the initial `seen_image_keys` pre-scan across `source_blocks`, inspect item-level images when items in list blocks are mappings (`for item in (block.get("items") or block.get("values") or []): if isinstance(item, Mapping): for item_img in item.get("images") or []: ... seen_image_keys.update(_image_identities(item_img))`). This prevents item-attached images from being re-inserted by `figure_queue` as duplicate trailing figures.
2. **Developer Operations & CLI Uniformity in `scripts/dev`:**
   - In `scripts/dev/smoke_local_stack.py`:
     - Add `--api-url` as an alias alongside `--base-url` with `parser.add_argument("--base-url", "--api-url", dest="base_url", default=None)`.
   - In `scripts/dev/fake_integrations_smoke.py`:
     - Add `--base-url` and `--api-url` CLI arguments with `dest="base_url"`.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Expand `test_developer_scripts_support_cli_argv` to assert `--database-url` across `operational_metrics.py`, `payment_reconciliation_smoke.py`, `reconcile_payments.py`, `replay_outbox.py`, `outbox_relay.py`, `deep_lane_smoke.py`, `ingest_bankone_batch.py`, `ingest_bankone_service.py`, and `ingest_banktwo_service.py`.
     - Assert `--api-url` support on `smoke_local_stack.py` and `fake_integrations_smoke.py`.
     - Assert `_resolve_database_address` in `autodata_enrichment.publisher`.
     - Clean up duplicate read in `test_health_and_reconcile_scripts_use_safe_env_defaults`.
3. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit test verifying `document_from_steps` extracts clean text from mapping items in instructions.
     - Add unit test verifying `_blocks_from_steps` unpacks mapping items in instructions.
     - Add unit test verifying `_list_block` preserves attached images.
     - Add unit test verifying `build_ordered_document` pre-scan prevents duplicate trailing figures for list item images.
4. **Workspace & Documentation Housekeeping:**
   - In `docs/architecture/infrastructure-and-dev.md`: Document list block image preservation, mapping instruction extraction, and developer CLI uniformity.
   - Update `.env.example` with API URL options.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/174

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Extract clean text from mapping instructions in document_from_steps and _blocks_from_steps in article_document.py.
- [x] Preserve attached images on _list_block and pre-scan list item images in build_ordered_document.
- [x] Add --api-url alias to scripts/dev/smoke_local_stack.py and --base-url/--api-url to fake_integrations_smoke.py.
- [x] Expand CLI argument assertions and enrich publisher checks in scripts/dev/test_storage_messaging_operations.py.
- [x] Add unit tests for step mapping instructions, list images, and pre-scan deduplication in workers/ingestion-python/tests/test_article_document.py.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Update .env.example with API URL options.
- [x] Record delivery in docs/agents/records/2026-10-27-document-normalization-list-images-cli-uniformity.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
