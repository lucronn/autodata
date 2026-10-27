# Hardening for Table Figures, Document Image Localization, and Developer Ergonomics

**Goal:** Preserve table cell figures and images during document normalization in `article_document`, expand `validate_ordered_document` to validate list items, sanitize link protocols in `_safe_link`, enhance multi-key image matching and table cell image localization in `procedure_images`, broaden candidate image identifier deduplication in `source_bundle`, add worker virtual environment auto-discovery and CLI execution across migration and smoke tools in `scripts/dev`, clean up redundant workspace dump artifacts, expand regression tests, and synchronize canonical architecture documentation.

**Architecture:**
1. **Table Cell Figure Preservation & Normalization:** In `workers/ingestion-python/src/autodata_ingestion/article_document.py`, update `_table_cell` to preserve cell images when passed directly via `images` or within `blocks` (rather than discarding cell images when `blocks` is absent or empty). Support cell image attributes `asset_resource_ref`, `url`, `storage_key`, `image_id`, and `alt`. Add validation in `validate_ordered_document` for `ordered_list` and `unordered_list` ensuring `items` is an array. Harden `_safe_link` to sanitize unsafe URI protocols (`javascript:`, `vbscript:`, `data:`) in addition to anchor `#`.
2. **Multi-Key Document Image Localization & Source Bundle Hygiene:** In `workers/ingestion-python/src/autodata_ingestion/procedure_images.py`, update `_rewrite_document_images` to broaden lookup keys to include `id`, `artifact_key`, `asset_resource_ref`, `content_sha256`, and `storage_key`. Support both `table` and `grid` kinds. Handle cell images with existing `storage_key` or data-URI URLs, and inspect child blocks inside table cells. In `workers/ingestion-python/src/autodata_ingestion/source_bundle.py`, in `_resolve_document_images`, recognize `image.get("id")` and `image.get("content_sha256")` as valid candidate image identifiers; in `_document_content_record`, preserve `id` and `artifact_key` during candidate identity merging.
3. **Developer Script Ergonomics & Virtual Environment Discovery:** In `scripts/dev/smoke_local_stack.py`, auto-discover worker virtual environment site-packages in `sys.path`. In `scripts/dev/migrate.py`, auto-discover worker virtual environment site-packages in `sys.path`, and support programmatic `main(argv=None)` with CLI options (`--address`, `--timeout`, `--compose-file`). In `scripts/dev/migration_plan.py`, auto-discover worker virtual environment site-packages in `sys.path`, and support programmatic `main(argv=None)` with CLI option (`--migrations-dir`). In `scripts/dev/consumer_agent.py`, auto-discover worker virtual environment site-packages in `sys.path`.
4. **Workspace Housekeeping:** Remove redundant duplicate database dump file `/home/corp/autodata/bin/autodata.dump` from `bin/`, preserving the canonical database dump at `/home/corp/autodata/data/autodata.dump`.
5. **Codebase Housekeeping & Test Verification:** In `workers/ingestion-python/tests/test_article_document.py`, add unit tests asserting table cell direct image preservation, list block validation in `validate_ordered_document`, and `_safe_link` protocol sanitization. In `workers/ingestion-python/tests/test_procedure_images.py`, add unit tests for table cell image rewriting, data-URI localization in table cells, and multi-key reference matching. In `workers/ingestion-python/tests/test_source_bundle.py`, add unit tests asserting identification with `id` and `artifact_key` deduplication. In `scripts/dev/test_storage_messaging_operations.py`, expand virtual environment auto-discovery tests and CLI argument parsing tests to cover `smoke_local_stack.py`, `migrate.py`, `migration_plan.py`, and `consumer_agent.py`.
6. **Documentation Housekeeping:** Canonical documentation in `docs/architecture/infrastructure-and-dev.md` reflects table figure preservation, multi-key document image rewriting, safe link sanitization, and universal worker virtual environment auto-discovery.

**Tech Stack:** Python 3.12+, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/159

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Preserve direct and nested table cell images and attributes in `autodata_ingestion.article_document`.
- [x] Validate list block `items` in `validate_ordered_document` and sanitize unsafe link protocols in `_safe_link`.
- [x] Enhance multi-key image matching and table cell image localization in `autodata_ingestion.procedure_images`.
- [x] Broaden candidate image identifier deduplication in `autodata_ingestion.source_bundle`.
- [x] Add worker venv discovery to `scripts/dev/smoke_local_stack.py` and `scripts/dev/consumer_agent.py`.
- [x] Add worker venv discovery and CLI `main(argv)` to `scripts/dev/migrate.py` and `scripts/dev/migration_plan.py`.
- [x] Remove duplicate `/home/corp/autodata/bin/autodata.dump` workspace artifact.
- [x] Add regression tests in `test_article_document.py`, `test_procedure_images.py`, and `test_source_bundle.py`.
- [x] Expand `test_storage_messaging_operations.py` for venv discovery and CLI parsing across all modernized developer scripts.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-table-figures-document-hygiene-developer-ergonomics.json`.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage and database adapters maintain isolated connection parameters and fall back safely to local developer defaults.
