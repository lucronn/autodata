# Hardening for List Labels, Asset Resource Refs, Bundle Persistence Address, and CLI Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` by supporting `asset_resource_ref` in `_image_identities`, supporting description/legend in `_image_block` caption and alt extraction, preserving author-defined `label`, `title`, and `heading` in `_list_block` along with item-level image aggregation, supporting title/name and url/target in `link` blocks, add `address` override parameter to `persist_source_bundle` in `bundle_persistence.py`, add `--address` and `--database-url` CLI arguments to `scripts/dev/normalize_source_directory.py`, add `--base-url`, `--api-url`, and `--url` aliases to `scripts/dev/consumer_agent.py`, expand CLI argument and persistence assertions in `scripts/dev/test_storage_messaging_operations.py`, expand unit tests in `workers/ingestion-python/tests/test_article_document.py` and `workers/ingestion-python/tests/test_bundle_persistence.py`, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Document Normalization & Image Hygiene in `article_document.py`:**
   - In `_image_identities(image: Mapping[str, Any]) -> set[str]`:
     - Add `image.get("asset_resource_ref")` to identity keys tuple, aligning with `_normalize_cell_image` and `_image_block`, preventing duplicate figure queue insertions when source blocks reference images via `asset_resource_ref`.
   - In `_image_block(article, source_order, raw, evidence_ids)`:
     - Support `description`, `legend`, and `title` fallback for `caption` (`_clean_text(raw.get("caption") or raw.get("label") or raw.get("description") or raw.get("legend"))`), and support `description` and `legend` fallback in `alt` text.
   - In `_list_block(article, source_order, raw, evidence_ids, kind)`:
     - Support author-defined `label`, `title`, and `heading` (`_clean_text(raw.get("label") or raw.get("title") or raw.get("heading"))`), preserving list labels in `extra_fields["label"]` (e.g., "Special Tools Required", "Required Materials"), aligning with `_table_block`, `_callout_block`, `_step_block`, and `paragraph`.
     - Support item-level image aggregation from `value.get("images")` for dictionary list items, preserving them in `extra_fields["images"]`.
   - In `build_ordered_document(article, blocks)` for `link` / `anchor` blocks:
     - Support `title`, `name`, `value`, and `content` fallbacks for `text` (`raw.get("text") or raw.get("label") or raw.get("title") or raw.get("name") or raw.get("value") or raw.get("content")`).
     - Support `url`, `link`, and `target` fallbacks for `href` (`raw.get("href") or raw.get("url") or raw.get("link") or raw.get("target")`).
2. **Bundle Persistence Address Argument & Directory Normalization in `bundle_persistence.py` & `normalize_source_directory.py`:**
   - In `persist_source_bundle` (`workers/ingestion-python/src/autodata_ingestion/bundle_persistence.py`):
     - Accept optional `address: str | None = None` parameter and pass it into `_resolve_database_address(address)`, fixing the unpassed address override.
   - In `normalize_source_directory.py` (`scripts/dev/normalize_source_directory.py`):
     - Add `--address` and `--database-url` CLI arguments.
     - Pass `address=args.address` to `persist_source_bundle` when `--persist` is specified.
3. **Developer Operations & CLI Uniformity in `scripts/dev`:**
   - In `consumer_agent.py` (`scripts/dev/consumer_agent.py`):
     - Add `--base-url`, `--api-url`, and `--url` CLI options as aliases to `--api-base-url`.
   - In `test_storage_messaging_operations.py` (`scripts/dev/test_storage_messaging_operations.py`):
     - Assert `--address` and `--database-url` on `normalize_source_directory.py`.
     - Assert `--api-base-url`, `--base-url`, `--api-url`, and `--url` on `consumer_agent.py`.
     - Assert `_resolve_database_address` in `autodata_enrichment.outbox`.
4. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit test verifying `_image_identities` includes `asset_resource_ref` and deduplicates against the figure queue.
     - Add unit test verifying `_image_block` extracts caption from `description` and `legend`.
     - Add unit test verifying `_list_block` preserves `label`, `title`, and `heading` and aggregates item-level images.
     - Add unit test verifying `link` block extracts `title`/`name` text and `url`/`target` href.
   - In `workers/ingestion-python/tests/test_bundle_persistence.py`:
     - Add unit test verifying `persist_source_bundle` accepts and uses explicit `address` override.
5. **Workspace & Documentation Housekeeping:**
   - Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
   - Update `.env.example` with developer CLI options.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/178

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Add asset_resource_ref to _image_identities in article_document.py.
- [x] Support description, legend, and title in _image_block caption and alt in article_document.py.
- [x] Preserve label, title, and heading and collect item-level images in _list_block in article_document.py.
- [x] Support title, name, and url, link, target fallbacks in link blocks in article_document.py.
- [x] Add address parameter to persist_source_bundle in bundle_persistence.py.
- [x] Add --address and --database-url CLI options in normalize_source_directory.py.
- [x] Add --base-url, --api-url, and --url aliases to consumer_agent.py.
- [x] Expand CLI argument and persistence assertions in test_storage_messaging_operations.py.
- [x] Add unit tests for list labels, item images, asset_resource_ref identities, image captions, and links in test_article_document.py.
- [x] Add unit test for persist_source_bundle address parameter in test_bundle_persistence.py.
- [x] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [x] Update .env.example with developer CLI options.
- [x] Record delivery in docs/agents/records/2026-10-27-list-labels-asset-refs-cli-uniformity.json.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
