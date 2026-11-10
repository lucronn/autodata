# Workshop Article Search and Step Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search normalized vehicle articles by summary, description, and structured blocks, and preserve description-only procedure instructions in the Workshop document.

**Architecture:** Extend article lookup to search consumer-visible text in top-level and normalized blocks without indexing structural metadata. Extend the existing step text fallback to preserve descriptions and nested instructions. Keep query scoring, source fallback, block schema, and rendering unchanged.

**Tech Stack:** Python 3, `unittest` and `pytest` in `workers/ingestion-python`.

**Spec:** `docs/verification/2026-11-10-workshop-article-search-step-description.md`

## Global Constraints

- This is a bounded content-correctness slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) and [Project #8](https://github.com/users/lucronn/projects/8); other Issue #184 work remains open.
- Do not change architecture, article schema, source fetch, payment, grants, production service state, or live traffic.
- Baseline focused article tests pass: 44 tests at planning start.
- Follow red-green TDD and record the exact planning base before implementation.

## Concrete todo

- [x] Add regression tests for local search in summary, description, and blocks; watch the expected misses.
- [x] Add regression tests for step-level and instruction-item description text; watch the expected placeholder-text failures.
- [x] Add only the missing search and text-fallback fields, then rerun focused/full ingestion tests.
- [ ] Correct reviewer-found normalized-block, metadata, nested-instruction, and whitespace-fallback gaps with red-first regressions.
- [ ] Record exact-SHA verification and independent review, require green CI and live branch protection before merge.

### Task 1: Index existing article content fields

**Files:** `workers/ingestion-python/tests/test_vehicle_article_query.py`, `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py`.

**Interfaces:** `query_vehicle_articles(vehicle, query, indexed_articles, *, fetcher=None, limit=10)` retains its public contract and returns `status: found` for local matches.

- [x] **Step 1: Write failing tests.** Add three cases beside the existing local-hit test. Each article has a neutral `article_id` and title, and only one distinguishing value: `summary: "bleeder screw"`, `description: "coolant bleed valve"`, or `blocks: [{"type": "paragraph", "text": "ground strap location"}]`. Query the unique phrase and assert `status == "found"`, one matching article ID, and no fallback call.
- [x] **Step 2: Verify red.** Run `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_vehicle_article_query.py`; the three new cases failed by invoking the forbidden fallback after the local miss, not from import or fixture errors.
- [x] **Step 3: Implement minimally.** Add `"summary", "description", "blocks"` to the tuple of fields in `_article_text`; preserve all existing fields, tokenization, ranking, and fallback behavior.
- [x] **Step 4: Verify green.** Rerun the focused query test file; all six cases passed.
- [x] **Step 5: Commit.** Query test and implementation: `3ebefd8`.

### Task 2: Preserve description-only step instructions

**Files:** `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/src/autodata_ingestion/article_document.py`.

**Interfaces:** `build_ordered_document(article, raw_blocks)` still emits validated `step` blocks with existing schema and source order.

- [x] **Step 1: Write failing tests.** Add a `build_ordered_document` test for `{"kind": "step", "number": 1, "description": "Inspect the ground strap."}` and one for `{"kind": "step", "number": 2, "instructions": [{"description": "Tighten the ground strap nut."}]}`. For each, assert `validate_ordered_document(document) == []`, one step block, and the literal expected `text`.
- [x] **Step 2: Verify red.** Run `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_article_document.py -k description_only_step`; both new tests failed because the normalized step text was the placeholder `Step 1`/`Step 2`.
- [x] **Step 3: Implement minimally.** Add `raw.get("description")` to `_step_block`'s `text_candidates` after existing body fallback; add `item.get("description")` after existing body fallback for mapping instruction items. Do not alter non-empty higher-priority text or image behavior.
- [x] **Step 4: Verify green.** Both description-only tests and all 49 focused article tests passed.
- [x] **Step 5: Commit.** Step test and implementation: `d505261`.

### Task 3: Correct review-found content boundaries

**Files:** `workers/ingestion-python/tests/test_vehicle_article_query.py`, `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py`, `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/src/autodata_ingestion/article_document.py`.

**Interfaces:** `query_vehicle_articles` and `build_ordered_document` retain their public signatures and return shapes.

- [ ] **Step 1: Write failing query tests.** Normalize a table-only source article with `normalize_procedure_article({"article_id": "article-normalized", "title": "Service notes", "blocks": [{"kind": "table", "rows": [{"cells": ["Ground strap bolt", "12 Nm"]}]}]})`; assert a `ground strap bolt` query returns `found` from the local index without source fallback. Separately index `{"article_id": "article-metadata", "title": "Service notes", "blocks": [{"type": "paragraph", "text": "Replace timing belt."}]}` and assert a `paragraph` query returns `not_found` without a fetcher.
- [ ] **Step 2: Verify red query cases.** Run the two new tests by name with `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_vehicle_article_query.py -k 'normalized_blocks or block_metadata'`; expect the normalized visible-cell case to miss and the metadata-only case to falsely match.
- [ ] **Step 3: Implement visible block text.** Keep scalar article fields as before. For `steps`, top-level `blocks`, and `normalized_document.blocks`, recursively collect string values only from visible text keys (`text`, `label`, `title`, `caption`, `alt`, `description`, `value`, `content`, `body`, `action`, `instruction`) and descend through list/container keys (`items`, `rows`, `cells`, `columns`, `blocks`, `instructions`, `images`). Do not index dictionary keys, `type`, IDs, image URLs, or evidence metadata. Preserve existing scoring and source-fallback decisions.
- [ ] **Step 4: Verify green query cases.** Run the focused query test file; all existing and new tests must pass.
- [ ] **Step 5: Write failing step tests.** For a step with `description: "Inspect mounting bolt."` plus `instructions: [{"text": "Torque bolt to 12 Nm."}]`, assert normalized step text contains both literal sentences. For an instruction item with `text: "   "` and `description: "Check ground strap."`, assert normalized step text equals the nonempty description.
- [ ] **Step 6: Verify red step cases.** Run `PYTHONPATH=workers/ingestion-python/src python -m pytest -q workers/ingestion-python/tests/test_article_document.py -k 'description_and_instructions or whitespace_text'`; expect lost nested text and placeholder text, respectively.
- [ ] **Step 7: Implement step preservation.** Clean each instruction-item candidate before selecting the first nonempty one. Keep existing higher-priority step text/action/instruction/value/content/body behavior. When those fields are empty, combine a nonempty step description with nonempty cleaned instruction text in source order; otherwise use whichever exists.
- [ ] **Step 8: Verify and commit.** Rerun focused article tests, then full ingestion with pinned Stripe dependency and a private temp directory outside the runner `/tmp/.git` marker. Commit and push the review corrections.

### Task 4: Verify and integrate

**Files:** This plan, the verification document, Issue #184, and Project #8 item.

**Interfaces:** No additional code interface changes.

- [x] **Step 1:** The full ingestion suite passed with the pinned Stripe dependency and a private temp directory outside this runner's `/tmp/.git` marker: 1,178 passed, 475 skipped, 178 subtests passed. `python -m compileall -q workers/ingestion-python/src/autodata_ingestion` and `git diff --check` passed.
- [ ] **Step 2:** Update the verification document with red/green counts and exact commit SHA, then obtain an independent read-only review of that exact head.
- [ ] **Step 3:** Open a PR; require current CI, no blocking review findings/threads, and live branch-protection satisfaction before merging. Update Issue #184's remaining checklist and Project item without closing the broad issue for this slice alone.

This plan is not evidence of live origin recovery or consumer purchase acceptance.
