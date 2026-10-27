# Hardening for Document Image Localization, Preflight CLI Validation, and Developer Ergonomics

**Goal:** Enhance `_collect_image_records` in `autodata_ingestion.procedure_images` to recursively discover images in `normalized_document` blocks and table/grid cells, ensure `localize_procedure_images` and `_rewrite_document_images` localize figures and data-URIs originating directly from `normalized_document`, implement programmatic `main(argv)` and CLI argument parsing for `scripts/autonomy/pre_implementation.py`, improve error handling in `scripts/dev/smoke_local_stack.py` for connection failures, expand regression test suites, prune merged automation branches, and update canonical architecture documentation.

**Architecture:**
1. **Document Image Localization & Collection in `procedure_images.py`:**
   - Update `_collect_image_records(article)` to inspect `article.get("normalized_document")` when present, recursively collecting image dictionaries from `image` blocks, `table` and `grid` rows/cells (both direct cell `images` lists and child blocks within cells).
   - In `localize_procedure_images`: When images are discovered (including those originating from `normalized_document`), fetch opaque asset references via `_fetch_asset_resources` and persist them into object storage via `_store_image_bytes`.
   - In `_rewrite_document_images`: Handle document image blocks and cell figures whose assets were stored or provided as inline data-URIs, ensuring `storage_key`, `asset_id`, `image_id`, and `url` (`artifact://{image_id}`) are populated and `status` is set to `"available"`.
2. **Pre-Implementation Preflight CLI Interface in `scripts/autonomy/pre_implementation.py`:**
   - Add `main(argv: list[str] | None = None) -> int` with `argparse` CLI arguments:
     - `--record`: Path to pre-implementation JSON record (required).
     - `--base-sha`: Base commit SHA (optional, defaults to `git rev-parse HEAD`).
     - `--repo-root`: Repository root path (optional, defaults to parent of scripts/autonomy).
     - `--policy`: Path to `.autodata-autonomy-policy.json` (optional, defaults to root policy).
   - Return exit code 0 when valid with a structured status payload, and exit code 1 with descriptive diagnostics on stderr when invalid.
3. **Developer Script Ergonomics & Error Resilience in `scripts/dev/`:**
   - In `scripts/dev/smoke_local_stack.py`: Wrap `urllib.request.urlopen` calls with clean handling for `urllib.error.URLError` and connection failures to output clear diagnostic messages rather than raw unhandled stack traces.
4. **Codebase Housekeeping & Regression Testing:**
   - In `workers/ingestion-python/tests/test_procedure_images.py`: Add unit tests for `_collect_image_records` discovering images from `normalized_document`, `localize_procedure_images` localizing figures from document-only articles, and table cell image localization with inline data-URIs.
   - In `scripts/autonomy/test_pre_implementation.py`: Add unit tests for `main(argv)` CLI execution covering valid records (exit code 0), invalid records (exit code 1), missing arguments, and custom base SHAs.
   - In `scripts/dev/test_storage_messaging_operations.py`: Expand `test_developer_scripts_support_cli_argv` to assert CLI argument support for `universal_article_smoke.py` (`--live-url`) and `knowledge_warm_path_benchmark.py` (`--query`).
5. **Workspace Housekeeping:**
   - Prune merged automation remote branches to keep repository references clean.
6. **Documentation Housekeeping:**
   - In `docs/architecture/infrastructure-and-dev.md`: Document `normalized_document` image collection and localization, `pre_implementation.py` CLI validation, and developer tooling ergonomics.

**Tech Stack:** Python 3.12+, Go 1.24, PostgreSQL with pgvector, MinIO / S3, NATS JetStream, Docker Compose.

**Issue:** https://github.com/lucronn/autodata/issues/163

**Project:** https://github.com/users/lucronn/projects/8

## Concrete Todo

- [x] Enhance `_collect_image_records` in `autodata_ingestion.procedure_images` to collect images from `normalized_document` blocks and table/grid cells.
- [x] Enhance `localize_procedure_images` and `_rewrite_document_images` to localize and persist images discovered in `normalized_document`.
- [x] Implement programmatic `main(argv)` and CLI argument parsing in `scripts/autonomy/pre_implementation.py`.
- [x] Improve connection failure handling in `scripts/dev/smoke_local_stack.py`.
- [x] Add unit tests in `workers/ingestion-python/tests/test_procedure_images.py`.
- [x] Add unit tests in `scripts/autonomy/test_pre_implementation.py`.
- [x] Expand CLI argument validation in `scripts/dev/test_storage_messaging_operations.py`.
- [x] Update canonical architecture documentation in `docs/architecture/infrastructure-and-dev.md`.
- [x] Record delivery in `docs/agents/records/2026-10-27-document-image-localization-preflight-cli.json`.
- [x] Prune merged remote git branches.

## Security and Credential Isolation Rules

- No credentials, tokens, private source data, or production identifiers are included.
- Object storage and database adapters maintain isolated connection parameters and fall back safely to local developer defaults.
