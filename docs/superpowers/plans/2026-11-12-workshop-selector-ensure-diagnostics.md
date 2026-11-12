# Workshop Selector Ensure Failure Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify the internal stage that makes a real Workshop selector hydration request return HTTP 502 without exposing provider details or changing catalog behavior.

**Architecture:** No architecture change. Keep the existing Go selector read, ingestion ensure route, provider resolution, and durable coverage writes. In the existing Python ensure function, emit one structured error record when an unexpected exception escapes provider setup, resolution, row persistence, coverage persistence, or deepening scheduling; re-raise so the existing HTTP handler continues returning its generic redacted response.

**Tech Stack:** Python 3, standard-library `logging` and `unittest`, existing ingestion service.

**Spec:** `docs/verification/2026-11-12-workshop-selector-ensure-diagnostics.md` defines the bounded evidence and acceptance for [Issue #401](https://github.com/lucronn/autodata/issues/401).

**Tracking:** [Issue #401](https://github.com/lucronn/autodata/issues/401), [Project #8](https://github.com/users/lucronn/projects/8), and the verification document above.

## Global Constraints

- Log only a fixed selector scope, a fixed stage label, and the exception class name. Never log exception messages, request bodies, provider URLs, credentials, article content, or arbitrary caller-provided identifiers.
- Preserve current provider traversal, partial-row handling, completeness markers, idempotency, HTTP status and body, and production configuration.
- Do not deploy or invoke live provider APIs in this task. The current public selector response and host metadata are diagnostic evidence, not end-to-end release acceptance.

---

## Concrete todo

- [ ] Add red-first tests that force failures at resolver and durable-write boundaries and assert one safe stage record without secret-bearing exception text.
- [ ] Add bounded stage logging to the existing selector ensure path while re-raising failures unchanged.
- [ ] Run focused and full ingestion tests, syntax/diff checks, independent exact-head review, required CI, and Project/Issue synchronization; do not merge or deploy until live protection permits.

### Task 1: Redacted selector ensure stage record

**Files:**
- Modify: `workers/ingestion-python/tests/test_catalog_service.py` (the existing `CatalogServiceTests` class).
- Modify: `workers/ingestion-python/src/autodata_ingestion/catalog_service.py` (`ensure_catalog_hydration`).
- Update: `docs/verification/2026-11-12-workshop-selector-ensure-diagnostics.md` with exact test and review evidence.

**Interfaces:**
- Consumes: the existing `ensure_catalog_hydration(serialized_request: str)` request and its configured providers/persistence functions.
- Produces: the existing result or exception unchanged, plus one `autodata_ingestion.catalog_service` ERROR record containing `scope=makes`, a fixed `stage` value, and `error_type=RuntimeError` or the actual exception class.

- [ ] **Step 1: Write the failing tests.** In `CatalogServiceTests`, use unique `idempotency_key` values and `unittest.mock.patch` to force `CacheFirstCatalogService.resolve` to raise `RuntimeError("provider-secret")`, then force `_persist_hydration_scope` to raise `OSError("database-secret")` after a successful empty `CatalogResult`. Under `self.assertLogs("autodata_ingestion.catalog_service", level="ERROR")`, assert the exception still propagates, the respective `stage=resolve` or `stage=coverage_persistence` appears exactly once, and neither secret string appears in logs.
- [ ] **Step 2: Verify red.** Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_catalog_service.CatalogServiceTests.test_selector_ensure_logs_redacted_failure_stage` from `workers/ingestion-python/tests`. Expect failure because the existing ensure path emits no stage record.
- [ ] **Step 3: Implement the minimum.** Add a module logger. In the existing `ensure_catalog_hydration` provider branch, set a fixed stage before each of provider configuration, resolution, row persistence, coverage persistence, and deepening scheduling. Wrap those operations in `try/except Exception`, log `"catalog selector ensure failed scope=%s stage=%s error_type=%s"` with fixed scope/stage and `type(error).__name__`, then `raise` unchanged. Do not log `str(error)` or the serialized request.
- [ ] **Step 4: Verify green and regression scope.** Run the focused test, then `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_catalog_service` and `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_http_service` from `workers/ingestion-python/tests`; run `python3 -m compileall -q workers/ingestion-python/src/autodata_ingestion/catalog_service.py` with bytecode directed to `/tmp`, plus `git diff --check`. If the full HTTP service suite requires unavailable external fixtures, report that precisely and run its isolated tests without claiming the full suite.
- [ ] **Step 5: Review and integrate only under gates.** Update the verification document with exact commands/results and the immutable head, commit/push a reviewable PR, obtain independent exact-head AI review, wait for required CI, and check live branch protection. Do not deploy or assert that the live 2024 scope is repaired; the log becomes useful only after a separately authorized rollout and fresh host observation.
