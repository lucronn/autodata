# Hardening for Document Image Pre-Scan Deduplication, Numbered Step Image Preservation, and Dev CLI Uniformity

**Goal:** Enhance document normalization in `autodata_ingestion.article_document` with pre-scan image deduplication across all source blocks to prevent duplicate PDF figure insertions, preserve attached images on numbered paragraphs converted to steps, safely extract clean text from dictionary-based items in step block instructions lists, unify developer script database and service CLI arguments (`--address`, `--database-url`, `--nats-url`, `--s3-endpoint`), expand unit and integration tests, update canonical architecture documentation, and record verified delivery.

**Architecture:**
1. **Document Normalization & Image Pre-Scan Deduplication in `article_document.py`:**
   - In `build_ordered_document`:
     - Scan all blocks in `source_blocks` during the initial `seen_image_keys` pre-pass to collect direct `images` lists (e.g., from `step`, `paragraph`, `callout`, `list`) in addition to existing `image` blocks and `table`/`grid` cells.
     - This ensures that `figure_queue` excludes any images that are already attached to document blocks, eliminating duplicate trailing figures.
     - When fallback text resolves to an explicit numbered step via `_numbered_text(text)`, preserve direct `images` lists onto the resulting `step` block using `_normalize_cell_image`.
   - In `_step_block`:
     - When inspecting `instructions = raw.get("instructions")`, support dictionary/mapping elements by extracting clean text from `text`, `action`, `instruction`, `value`, `content`, or `body`, preventing Python dictionary reprs from being serialized into step instructions.
2. **Developer Operations & CLI Uniformity in `scripts/dev`:**
   - In `scripts/dev/ingest_bankone_batch.py`:
     - Add `--address` and `--database-url` CLI options.
     - When provided, set `os.environ["AUTODATA_DB_ADDRESS"] = args.address`.
   - In `scripts/dev/ingest_bankone_service.py` and `scripts/dev/ingest_banktwo_service.py`:
     - Add `--address` and `--database-url` CLI options.
     - When provided, set `os.environ["AUTODATA_DB_ADDRESS"] = args.address`.
   - In `scripts/dev/migrate.py`:
     - Support `--database-url` as an alias alongside `--address`.
   - In `scripts/dev/ingestion_smoke.py`:
     - Support `--database-url` as an alias alongside `--address`.
   - In `scripts/dev/nats_health.py`:
     - Support `--nats-url` as an alias alongside `--url`.
   - In `scripts/dev/object_storage_health.py`:
     - Support `--s3-endpoint` as an alias alongside `--endpoint`.
3. **Codebase Housekeeping & Test Verification:**
   - In `workers/ingestion-python/tests/test_article_document.py`:
     - Add unit test verifying pre-scan image deduplication with block-level images preventing duplicate trailing figures.
     - Add unit test verifying numbered paragraphs preserve attached images on generated step blocks.
     - Add unit test verifying `_step_block` handles mapping items in `instructions` lists.
   - In `scripts/dev/test_storage_messaging_operations.py`:
     - Assert `--address` and `--database-url` support for `ingest_bankone_batch.py`, `ingest_bankone_service.py`, and `ingest_banktwo_service.py`.
     - Assert `--database-url` alias for `migrate.py` and `ingestion_smoke.py`.
     - Assert `--nats-url` alias for `nats_health.py` and `--s3-endpoint` alias for `object_storage_health.py`.
4. **Workspace & Documentation Housekeeping:**
   - In `docs/architecture/infrastructure-and-dev.md`: Document image pre-scan deduplication, numbered step image preservation, dictionary instruction extraction, and developer CLI uniformity.
   - Update `.env.example` with unified CLI options and environment defaults.
   - Prune merged remote git branches.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/172

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [ ] Enhance build_ordered_document in article_document.py to pre-scan images on all source blocks and preserve images on numbered paragraphs.
- [ ] Support mapping elements in instructions lists in _step_block.
- [ ] Add --address and --database-url arguments to scripts/dev/ingest_bankone_batch.py.
- [ ] Add --address and --database-url arguments to scripts/dev/ingest_bankone_service.py and ingest_banktwo_service.py.
- [ ] Support --database-url alias in scripts/dev/migrate.py and scripts/dev/ingestion_smoke.py.
- [ ] Support --nats-url alias in scripts/dev/nats_health.py and --s3-endpoint alias in scripts/dev/object_storage_health.py.
- [ ] Add unit tests in workers/ingestion-python/tests/test_article_document.py.
- [ ] Expand CLI argument assertions in scripts/dev/test_storage_messaging_operations.py.
- [ ] Update canonical architecture documentation in docs/architecture/infrastructure-and-dev.md.
- [ ] Update .env.example with developer CLI options.
- [ ] Record delivery in docs/agents/records/2026-10-27-document-image-dedup-dev-cli-uniformity.json.
- [ ] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Database, object storage, and messaging connection parameters default safely to local developer configurations.
