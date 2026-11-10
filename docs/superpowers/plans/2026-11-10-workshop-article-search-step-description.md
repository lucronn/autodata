# Workshop Article Search and Step Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search normalized vehicle articles in the ingestion query utility by summary, description, and structured blocks, and preserve description-only procedure instructions in the Workshop document. The Workshop UI search box is separate and out of scope.

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
- [x] Correct reviewer-found normalized-block, metadata, nested-instruction, and whitespace-fallback gaps with red-first regressions.
- [x] Preserve description/instruction content through the JSON bound-article adapter and match normalized-block search to rendered text by block type.
- [ ] Close reviewer-found full-normalization projection, empty-block adapter, whitespace-shadow, and nested rendered-field gaps with red-first regressions.
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

- [x] **Step 1: Write failing query tests.** The normalized table-only article and metadata-only block cases were added to the query tests.
- [x] **Step 2: Verify red query cases.** Both new tests failed for the expected missing/false-match behavior.
- [x] **Step 3: Implement visible block text.** Scalar article fields remained; `steps`, top-level `blocks`, and `normalized_document.blocks` now contribute visible text without structural metadata.
- [x] **Step 4: Verify green query cases.** All eight focused query tests passed.
- [x] **Step 5: Write failing step tests.** Combined description/instruction and whitespace-only item-text cases were added.
- [x] **Step 6: Verify red step cases.** Both new tests failed for the expected lost-detail behavior.
- [x] **Step 7: Implement step preservation.** Each instruction candidate is cleaned before selection; step description and nested instructions are combined only when no higher-priority step text exists.
- [x] **Step 8: Verify and commit.** Focused article tests passed (53), full ingestion passed (1,182 with 475 skips and 178 subtests), compilation and diff checks passed; corrections committed as `2ccd549`.

### Task 4: Close source-adapter and rendered-step-label gaps

**Files:** `workers/ingestion-python/tests/test_source_adapters.py`, `workers/ingestion-python/src/autodata_ingestion/source_adapters.py`, `workers/ingestion-python/tests/test_vehicle_article_query.py`, `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py`.

**Interfaces:** `adapt_bound_article(resource, context)` keeps its return shape; `query_vehicle_articles` keeps its signature and result schema.

- [x] **Step 1: Write failing source-path test.** JSON `steps` with description and nested instruction must survive `adapt_bound_article` and `build_ordered_document` as complete step text.
- [x] **Step 2: Verify red source path.** The new source-path test failed with `Step 1` before the adapter change.
- [x] **Step 3: Preserve source step fields.** JSON mapping steps now retain `description` and `instructions` during adaptation; string steps are unchanged.
- [x] **Step 4: Verify green source path.** The named test and all 31 source-adapter tests passed (60 subtests).
- [x] **Step 5: Write failing search tests.** Hidden normalized step/list labels have negative tests; displayed callout/table labels have positive controls.
- [x] **Step 6: Verify red search cases.** Hidden step and list label cases falsely matched before the visibility corrections.
- [x] **Step 7: Match rendered block fields.** Normalized blocks now contribute only the fields their Workshop rendering branches display; raw provider blocks retain generic visible-text traversal.
- [x] **Step 8: Verify and commit.** Focused suites passed 87 tests and 62 subtests; full ingestion passed 1,186 tests, 475 skips, and 180 subtests; compilation/diff checks passed. Code was committed as `cdd424e`.

### Task 5: Close full-path content gaps

**Files:** `workers/ingestion-python/tests/test_vehicle_article_query.py`, `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py`, `workers/ingestion-python/tests/test_source_adapters.py`, `workers/ingestion-python/src/autodata_ingestion/source_adapters.py`.

**Interfaces:** Keep `query_vehicle_articles`, `adapt_bound_article`, and rendered document schemas unchanged.

- [ ] **Step 1: Red-first full normalization test.** Build an ordered step/list document with unique hidden labels, pass it through `normalize_procedure_article`, and assert that each hidden-label query is `not_found` while visible step/list text is found. A normalized document is authoritative over compatibility `body`, `steps`, and raw blocks in local lookup.
- [ ] **Step 2: Red-first adapter tests.** Adapt JSON with `blocks: []` and populated description-only `steps`; also adapt a step whose `text` is whitespace and `instruction` is nonblank. Assert non-placeholder normalized step text. Use `steps` when `blocks` is empty, and forward candidate fields independently so the normalizer cleans them.
- [ ] **Step 3: Red-first nested rendered-field tests.** Under normalized callout, list, and table blocks, assert hidden image `caption` and item/cell `label` values do not match, but rendered `alt`/`text` values do. Extract fields by nested rendered shape rather than generic recursion.
- [ ] **Step 4: Verify.** Run focused and full ingestion suites, compilation, diff check, independent exact-head review, current GitHub CI, and branch protection. Update verification evidence and PR description to avoid claiming Workshop UI content search.

### Task 6: Verify and integrate

**Files:** This plan, the verification document, Issue #184, and Project #8 item.

**Interfaces:** No additional code interface changes.

- [x] **Step 1:** The final full ingestion suite passed with the pinned Stripe dependency and a private temp directory outside this runner's `/tmp/.git` marker: 1,186 passed, 475 skipped, 180 subtests passed. `python -m compileall -q workers/ingestion-python/src/autodata_ingestion` and `git diff --check` passed.
- [ ] **Step 2:** Update the verification document with red/green counts and exact commit SHA, then obtain an independent read-only review of that exact head.
- [ ] **Step 3:** Open a PR; require current CI, no blocking review findings/threads, and live branch-protection satisfaction before merging. Update Issue #184's remaining checklist and Project item without closing the broad issue for this slice alone.

This plan is not evidence of live origin recovery or consumer purchase acceptance.
