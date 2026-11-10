# Workshop Article Search and Step Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search normalized vehicle articles by summary, description, and structured blocks, and preserve description-only procedure instructions in the Workshop document.

**Architecture:** Extend the existing field list in `_article_text` and the existing text fallback lists in `_step_block`. Keep query scoring, source fallback, block schema, and rendering unchanged.

**Tech Stack:** Python 3, `unittest` and `pytest` in `workers/ingestion-python`.

**Spec:** `docs/verification/2026-11-10-workshop-article-search-step-description.md`

## Global Constraints

- This is a bounded content-correctness slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) and [Project #8](https://github.com/users/lucronn/projects/8); other Issue #184 work remains open.
- Do not change architecture, article schema, source fetch, payment, grants, production service state, or live traffic.
- Baseline focused article tests pass: 44 tests at planning start.
- Follow red-green TDD and record the exact planning base before implementation.

## Concrete todo

- [ ] Add regression tests for local search in summary, description, and blocks; watch the expected misses.
- [ ] Add regression tests for step-level and instruction-item description text; watch the expected empty-text failures.
- [ ] Add only the missing search and text-fallback fields, then rerun focused/full ingestion tests.
- [ ] Record exact-SHA verification and independent review, require green CI and live branch protection before merge.

### Task 1: Index existing article content fields

**Files:** `workers/ingestion-python/tests/test_vehicle_article_query.py`, `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py`.

**Interfaces:** `query_vehicle_articles(vehicle, query, indexed_articles, *, fetcher=None, limit=10)` retains its public contract and returns `status: found` for local matches.

- [ ] **Step 1: Write failing tests.** Add three cases beside the existing local-hit test. Each article has a neutral `article_id` and title, and only one distinguishing value: `summary: "bleeder screw"`, `description: "coolant bleed valve"`, or `blocks: [{"type": "paragraph", "text": "ground strap location"}]`. Query the unique phrase and assert `status == "found"`, one matching article ID, and no fallback call.
- [ ] **Step 2: Verify red.** Run `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_vehicle_article_query.py`; the three new cases must fail as `not_found`, not import or fixture errors.
- [ ] **Step 3: Implement minimally.** Add `"summary", "description", "blocks"` to the tuple of fields in `_article_text`; preserve all existing fields, tokenization, ranking, and fallback behavior.
- [ ] **Step 4: Verify green.** Rerun the focused query test file; all cases must pass.
- [ ] **Step 5: Commit.** Commit the query test and implementation as one reviewable milestone.

### Task 2: Preserve description-only step instructions

**Files:** `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/src/autodata_ingestion/article_document.py`.

**Interfaces:** `build_ordered_document(article, raw_blocks)` still emits validated `step` blocks with existing schema and source order.

- [ ] **Step 1: Write failing tests.** Add a `build_ordered_document` test for `{"kind": "step", "number": 1, "description": "Inspect the ground strap."}` and one for `{"kind": "step", "number": 2, "instructions": [{"description": "Tighten the ground strap nut."}]}`. For each, assert `validate_ordered_document(document) == []`, one step block, and the literal expected `text`.
- [ ] **Step 2: Verify red.** Run `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_article_document.py -k description_only_step`; the new tests must fail because the normalized step text is empty.
- [ ] **Step 3: Implement minimally.** Add `raw.get("description")` to `_step_block`'s `text_candidates` after existing body fallback; add `item.get("description")` after existing body fallback for mapping instruction items. Do not alter non-empty higher-priority text or image behavior.
- [ ] **Step 4: Verify green.** Rerun the description-only tests, then both focused article test files.
- [ ] **Step 5: Commit.** Commit the step tests and implementation as one reviewable milestone.

### Task 3: Verify and integrate

**Files:** This plan, the verification document, Issue #184, and Project #8 item.

**Interfaces:** No additional code interface changes.

- [ ] **Step 1:** Run the full ingestion test suite with `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests`, `python -m compileall -q workers/ingestion-python/src/autodata_ingestion`, and `git diff --check`.
- [ ] **Step 2:** Update the verification document with red/green counts and exact commit SHA, then obtain an independent read-only review of that exact head.
- [ ] **Step 3:** Open a PR; require current CI, no blocking review findings/threads, and live branch-protection satisfaction before merging. Update Issue #184's remaining checklist and Project item without closing the broad issue for this slice alone.

This plan is not evidence of live origin recovery or consumer purchase acceptance.
