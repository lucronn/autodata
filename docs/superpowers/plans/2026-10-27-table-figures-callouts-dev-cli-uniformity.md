# Hardening for Table Figures, Callout Titles, Step Fallbacks, and Dev CLI URL Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` by supporting attached direct images and title/heading labels in `_table_block`, normalizing content, body, and label in `_table_cell`, preserving custom titles and bullet items in `_callout_block`, extracting title, name, and text fallbacks in `document_from_steps` and `_blocks_from_steps`, add `--url`, `--api-url`, `--base-url`, and `--knowledge-url` aliases across developer smoke scripts (`universal_article_smoke.py`, `smoke_local_stack.py`, `fake_integrations_smoke.py`, `api_runtime_smoke.py`), expand CLI argument assertions in `scripts/dev/test_storage_messaging_operations.py`, expand unit tests in `workers/ingestion-python/tests/test_article_document.py`, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Table Figures, Callout Titles, and Step Normalization in `article_document.py`:**
   - In `_table_block(article, source_order, raw, evidence_ids)`:
     - Support direct attached `images` from `raw.get("images")`: normalize valid mapping images using `_normalize_cell_image(image)` and preserve them in `extra_fields["images"]`, mirroring `_list_block`, `_callout_block`, `_step_block`, and `paragraph`.
     - Extract table label from `raw.get("label") or raw.get("caption") or raw.get("title") or raw.get("heading")`.
   - In `_table_cell(value)`:
     - Support `content`, `body`, and `label` in direct cell mappings (`value.get("text") or value.get("value") or value.get("content") or value.get("body") or value.get("label")`) and in nested cell blocks (`child.get("text") or child.get("value") or child.get("content") or child.get("body") or child.get("label")`).
   - In `_callout_block(article, source_order, raw, evidence_ids, kind)`:
     - Preserve custom author title/heading: `label = _clean_text(raw.get("label") or raw.get("title") or raw.get("heading")) or kind.upper()`.
     - Synthesize composite text from `raw.get("items")` when callout `text` is omitted.
   - In `document_from_steps(article)`:
     - Safely extract step heading/title/label/name from `step.get("heading") or step.get("action") or step.get("title") or step.get("label") or step.get("name")`.
     - When heading/action is omitted and `instructions` is empty, fallback to `step.get("text") or step.get("instruction") or step.get("content") or step.get("body")`.
   - In `_blocks_from_steps(steps)`:
     - Safely extract step action/heading/title/label/name from `step.get("action") or step.get("heading") or step.get("title") or step.get("label") or step.get("name")`.
     - When step action is omitted and `instructions` is empty, fallback to `step.get("text") or step.get("instruction") or step.get("content") or step.get("body")`.
2. **Developer Operations & CLI Uniformity in `scripts/dev`:**
   - In `scripts/dev/universal_article_smoke.py`:
     - Add `--api-url`, `--base-url`, `--knowledge-url`, and `--url` CLI arguments as aliases to `--live-url`, harmonizing knowledge lookup smoke testing with the rest of the developer toolchain.
   - In `scripts/dev/smoke_local_stack.py`:
     - Add `--url` alias alongside `--base-url` and `--api-url`.
   - In `scripts/dev/api_runtime_smoke.py`:
     - Add `--url` alias alongside `--base-url` and `--api-url`.
   - In `scripts/dev/fake_integrations_smoke.py`:
     - Add `--url` alias alongside `--base-url` and `--api-url`.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Assert `--url` support across `smoke_local_stack.py`, `api_runtime_smoke.py`, `fake_integrations_smoke.py`, and `universal_article_smoke.py`.
     - Assert `--api-url`, `--base-url`, `--knowledge-url` support on `universal_article_smoke.py`.
3. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit test verifying `_table_block` preserves attached images and title/heading labels.
     - Add unit test verifying `_table_cell` extracts `content`, `body`, and `label` in direct and nested cell blocks.
     - Add unit test verifying `_callout_block` preserves custom titles and synthesizes bullet items.
     - Add unit test verifying `document_from_steps` extracts step title/name and text fallbacks.
     - Add unit test verifying `_blocks_from_steps` extracts step heading/title and text fallbacks.
4. **Workspace & Documentation Housekeeping:**
   - In `docs/architecture/infrastructure-and-dev.md`: Document table image preservation, cell content normalization, callout title/items handling, step compatibility normalization, and dev CLI URL uniformity.
   - Update `.env.example` with universal article smoke URL options.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/176

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Support direct attached images and title/heading labels in _table_block in article_document.py.
- [x] Normalize cell content, body, and label in _table_cell in article_document.py.
- [x] Preserve custom titles/headings and extract bullet items in _callout_block in article_document.py.
- [x] Support step title, name, and text fallbacks in document_from_steps and _blocks_from_steps in article_document.py.
- [x] Add --url, --api-url, --base-url, and --knowledge-url aliases in scripts/dev/universal_article_smoke.py, smoke_local_stack.py, api_runtime_smoke.py, and fake_integrations_smoke.py.
- [x] Expand CLI argument assertions in scripts/dev/test_storage_messaging_operations.py.
- [x] Add unit tests for table figures, cell normalization, callout titles, and step fallbacks in workers/ingestion-python/tests/test_article_document.py.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Update .env.example with universal article smoke URL options.
- [x] Record delivery in docs/agents/records/2026-10-27-table-figures-callouts-dev-cli-uniformity.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
