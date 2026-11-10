# Workshop Table-Row Image Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a table-row image once beside its Workshop table, not again as a trailing unrelated figure, when the article-level media list references the same image.

**Approach:** The existing ordered-document pre-scan records image identities before queuing unattached article-level figures. Include images attached to table row mappings. The Workshop table renderer must also display the resulting table-block image references immediately after the semantic table, using only the authorized article image pool and without repeating images already shown in cells. Preserve the table block, original source bytes, and the existing figure queue for genuinely unattached media.

**Tech Stack:** Python 3 and pytest in `workers/ingestion-python`; JavaScript and Node's built-in test runner in `apps/api-go/workshop`.

**Spec:** `docs/verification/2026-11-10-workshop-table-row-image-dedup.md`

## Global Constraints

- This is a bounded Workshop content-correctness slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) in [Project #8](https://github.com/users/lucronn/projects/8). The broader issue remains open.
- Do not change document schema, source capture, payment, grants, live services, or production traffic. Limit the reader change to the existing table branch.
- The focused `test_article_document.py` baseline passes 45 tests on master before implementation.
- The plan, Issue/Project tracking, verification document, and synchronized record must be committed at the exact preflight base SHA before implementation edits.

## Concrete todo

- [x] Add a failing regression with a row-attached image duplicated in the article-level image list and a distinct unattached image.
- [x] Include table row mapping `images` in the existing image-identity pre-scan; leave table block and figure queue semantics otherwise unchanged.
- [ ] Red-first test and implement table-block image rendering in the Workshop reader, keeping the semantic table, authorized pool lookup, missing-image fallback, and cell-image de-duplication.
- [ ] Run focused and full relevant suites, syntax/diff checks, exact-head independent review, required CI, and live branch-protection check before merge.

### Task 1: Keep row-attached images at their source position

**Files:** `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/src/autodata_ingestion/article_document.py`.

**Interfaces:** `build_ordered_document(article, blocks)` keeps its signature and ordered-document schema. Table row mappings keep their existing `images` field.

- [x] **Step 1: Write the failing test.** Build an article whose top-level `images` contain `row-image` with storage key `media/row-image` and `unattached-image` with storage key `media/unattached-image`. Supply one table block with a row mapping whose `images` contain the matching `row-image`. Assert the normalized block types are exactly `["table", "image"]`, the table retains `row-image`, and the only trailing image is `unattached-image`.
- [x] **Step 2: Verify red.** The named test failed with actual block types `["table", "image", "image"]` before implementation.
- [x] **Step 3: Implement minimally.** In `build_ordered_document`'s `table`/`grid` pre-scan, collect `_image_identities` from each row mapping's `images` before visiting its cells. Do not change `_table_block` or image identity rules.
- [x] **Step 4: Verify green.** The named test and all 46 `test_article_document.py` tests passed; the row-attached image remains in the table and the distinct image remains trailing.
- [x] **Step 5: First review.** The full ingestion suite passed 1,191 tests with 475 skips and 192 subtests at code commit `e7716076d96f71f9762de179619a84b5219243bb`; Python compilation and `git diff --check` passed. Independent review found that the reader ignored table-block images, so PR #395 became draft and must not merge yet.

### Task 2: Make row images visible in the Workshop reader

**Files:** `apps/api-go/workshop-client.test.mjs`, `apps/api-go/workshop/app.mjs`.

**Interfaces:** The existing `renderBlocks` table branch and `addImage` helper; no API or document schema change.

- [ ] **Step 1: Write failing reader regressions.** Cover one table-block image appearing immediately after the semantic table and before the next paragraph; confirm source and canonical render paths, `alt`/authorized local URL, no unrelated-pool substitution for a missing ID, and no duplicate when the same image is already in a cell.
- [ ] **Step 2: Verify red.** Run only the named Node tests and record the missing figure (or duplicate) failure.
- [ ] **Step 3: Implement minimally.** In the table branch, render `block.images` after the table wrapper through `addImage`, guarded by a real asset/image ID and resolved via `find(ref)`. Skip a block-level image already resolved/rendered in a cell. Keep the `<table>` markup and caption unchanged.
- [ ] **Step 4: Verify green.** Run the named tests and the full Workshop client test file. Confirm no provider inline URL or ID-less reference can supply an unrelated image.
- [ ] **Step 5: Verify and integrate.** Run relevant Python/Node tests, syntax and diff checks, obtain a new independent exact-head review and current required CI, then merge only if live protection permits.

The plan does not claim that the live Workshop origin, paid access, or image retrieval works.
