# Development test discovery repair

**Goal:** Make the existing backfill pytest module importable by clean development unittest discovery without relying on inherited fixture PYTHONPATH or changing coverage.

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8

**Decision:** Preserve the workflow and tests. The pytest backfill module under scripts/dev is also imported by the existing unittest discovery. It adds only scripts/dev to sys.path, then imports lifecycle_support from workers/ingestion-python/tests. The ingestion pytest invocation automatically supplies that directory, but the separate CI development command does not. The actual CI run41625088678 at31d1582 reaches development discovery after ingestion dependencies/tests pass, then fails with ModuleNotFoundError: lifecycle_support. Retained log: /tmp/autodata-ci-31d1582-failed.log. Fixture PYTHONPATH on developer hosts can mask this import defect.

**Exact implementation scope:** scripts/dev/test_backfill_article_lifecycle.py only. Add the absolute workers/ingestion-python/tests path derived from Path(__file__).resolve().parents[2] before its lifecycle_support import. Preserve existing scripts/dev path setup, all imports, fixture use and six database assertions. No conditional import/skip, duplicated helper, migration change, product behavior or workflow modification. No new implementation-mirroring test is needed; the actual previously failing discovery command and existing DB cases are the regression checks.

## Concrete todo

- [ ] Preserve actual CI run41625088678 import-failure evidence, synchronize Issue186/Project8 and canonical verification, commit this checkpoint and pass exact-base preflight.
- [ ] Add only the absolute repository ingestion-tests directory to the existing test module import path before importing lifecycle_support; retain all six DB tests and their assertions.
- [ ] Reproduce the unmodified CI development unittest command in clean Python3.12 without inherited PYTHONPATH, then verify the six backfill cases in the isolated PostgreSQL runner.
- [ ] Review the exact one-file candidate independently, integrate unchanged, and retain the next actual GitHub verification result alongside the separate migration repair.

## Required verification

1. In a clean Python3.12 environment, install the same declared ingestion pyproject dependencies and pytest already installed before this CI step. Mount only read-only code and private artifacts; no DB/source/host credentials. Explicitly omit inherited PYTHONPATH and AUTODATA_LIFECYCLE_TEST. Run the exact unchanged `python -m unittest discover -s scripts/dev -p 'test_*.py' -v` before and after the one-file fix; retain separate logs and actual exit/count. Use a clean disposable plain clone or extraction so Git ownership checks see the actual candidate correctly. Never count pytest functions as executed by unittest.
2. Run `python -m pytest -q -p no:cacheprovider scripts/dev/test_backfill_article_lifecycle.py` in the existing private lifecycle fixture Compose runner with real PostgreSQL and its existing required environment. Require all six cases pass with no skips; retain JUnit and exact candidate/command provenance. Do not alter the concurrently owned migration fixture or use another worker's project.
3. Confirm only the one allowed test file differs, original assertions/body are unchanged, `git diff --check` passes, and exact candidate checkout is clean. Obtain independent exact-SHA code review. Coordinator merges the reviewed candidate and the separately reviewed migration runner, then records actual GitHub CI; local discovery alone is not CI success.

Execution remains Sol6.1 / medium / Fast(priority), no fallback. Implementation starts only after the synchronized record is committed and machine preflight passes. No deployment or production access.

## Synchronized record

```json
{
  "goal": "Make the existing backfill pytest module importable by clean development unittest discovery without relying on inherited fixture PYTHONPATH or changing coverage.",
  "plan_ref": "docs/superpowers/plans/2026-11-03-dev-test-discovery.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/verification/2026-11-03-canonical-article-lifecycle.md",
    "docs/superpowers/plans/2026-11-03-production-release-orchestration.md"
  ],
  "todo": [
    "Preserve actual CI run41625088678 import-failure evidence, synchronize Issue186/Project8 and canonical verification, commit this checkpoint and pass exact-base preflight.",
    "Add only the absolute repository ingestion-tests directory to the existing test module import path before importing lifecycle_support; retain all six DB tests and their assertions.",
    "Reproduce the unmodified CI development unittest command in clean Python3.12 without inherited PYTHONPATH, then verify the six backfill cases in the isolated PostgreSQL runner.",
    "Review the exact one-file candidate independently, integrate unchanged, and retain the next actual GitHub verification result alongside the separate migration repair."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-03T11:17:00.878858+00:00"
}
```
