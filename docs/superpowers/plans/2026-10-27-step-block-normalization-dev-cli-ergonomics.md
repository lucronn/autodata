# Hardening for Step Block Normalization, Paragraph Content Fallback, and Dev CLI Ergonomics

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` with dedicated `_step_block` handling action, instruction, number, and direct images, expand paragraph and heading text extraction to support `content` and `body` fallbacks and direct images, add `--address`/`--database-url` CLI arguments to `scripts/dev/deep_lane_smoke.py` and `scripts/dev/reconcile_payments.py`, add `--database-url` aliases to `operational_metrics.py` and `payment_reconciliation_smoke.py`, update `.env.example`, expand regression tests, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Step Block Normalization & Action/Instruction Extraction in `article_document.py`:**
   - In `_step_block(article, source_order, raw, evidence_ids)`:
     - For `kind in {"step", "instruction"}`:
       - Extract text from `text`, `action`, `instruction`, `value`, `content`, `body`, or joined items in `instructions`.
       - Resolve step numbers from `number`, `step_number`, `index`, or numbered text patterns (`_numbered_text`).
       - Preserve step metadata (`label`, `title`, `action`) and normalize direct `images` lists using `_normalize_cell_image(img)`.
   - In `build_ordered_document`:
     - Dispatch `kind in {"step", "instruction"}` directly to `_step_block`.
     - Expand paragraph/heading fallback text resolution to check `content` and `body` in addition to `text` and `value`, preventing valid provider CMS paragraphs from being categorized as `unknown`.
     - Support and preserve direct `images` on paragraph blocks using `_normalize_cell_image`.
2. **Developer Operations & CLI Ergonomics in `scripts/dev`:**
   - In `scripts/dev/deep_lane_smoke.py`:
     - Add `--address` and `--database-url` CLI options.
     - Pass the resolved address into `resolve_database_address(address)` and `resolve_viewable_projection_id(args.projection_id, address=address)`.
     - Set `os.environ["AUTODATA_DB_ADDRESS"] = address` when specified.
   - In `scripts/dev/reconcile_payments.py`:
     - Add `--address` and `--database-url` CLI options.
     - Wire `--address` through `run_once(batch_size=args.batch_size, address=args.address)` into `db_connection(address)`.
   - In `scripts/dev/operational_metrics.py` and `scripts/dev/payment_reconciliation_smoke.py`:
     - Support `--database-url` as an alias alongside `--address`.
3. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit tests verifying `_step_block` handling of action/instructions/number/images.
     - Add unit tests verifying paragraph blocks with `content`/`body` keys and direct `images`.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Expand `test_developer_scripts_support_cli_argv` asserting `--address` for `deep_lane_smoke.py` and `reconcile_payments.py`.
4. **Workspace & Documentation Housekeeping:**
   - In `.env.example`: Add `AUTODATA_PAYMENT_RECONCILE_*` configuration variables.
   - In `docs/architecture/infrastructure-and-dev.md`: Document step block normalization, paragraph content fallback, and developer CLI ergonomics.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/170

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Add _step_block handler in autodata_ingestion.article_document supporting action, instruction, instructions, number, and direct images.
- [x] Expand paragraph and heading fallback text resolution to inspect content and body keys and preserve direct images in article_document.
- [x] Add --address and --database-url arguments in scripts/dev/deep_lane_smoke.py.
- [x] Add --address and --database-url arguments in scripts/dev/reconcile_payments.py.
- [x] Support --database-url alias in scripts/dev/operational_metrics.py and payment_reconciliation_smoke.py.
- [x] Add unit tests in workers/ingestion-python/tests/test_article_document.py.
- [x] Expand CLI argument assertions in scripts/dev/test_storage_messaging_operations.py.
- [x] Add payment reconciliation variables to .env.example.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Record delivery in docs/agents/records/2026-10-27-step-block-normalization-dev-cli-ergonomics.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
