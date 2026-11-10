# Workshop Table-Row Image Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a table-row image from appearing again as a trailing figure in a Workshop article when the same image is also in the article-level media list.

**Architecture:** The existing ordered-document pre-scan records image identities before queuing unattached article-level figures. Extend only that pre-scan to include images attached to table row mappings. Preserve the table block, original source bytes, and the existing figure queue for genuinely unattached media.

**Tech Stack:** Python 3 and pytest in `workers/ingestion-python`.

**Spec:** `docs/verification/2026-11-10-workshop-table-row-image-dedup.md`

## Global Constraints

- This is a bounded Workshop content-correctness slice of [Issue #184](https://github.com/lucronn/autodata/issues/184) in [Project #8](https://github.com/users/lucronn/projects/8). The broader issue remains open.
- Do not change document schema, table rendering, source capture, payment, grants, live services, or production traffic.
- The focused `test_article_document.py` baseline passes 45 tests on master before implementation.
- The plan, Issue/Project tracking, verification document, and synchronized record must be committed at the exact preflight base SHA before implementation edits.

## Concrete todo

- [ ] Add a failing regression with a row-attached image duplicated in the article-level image list and a distinct unattached image.
- [ ] Include table row mapping `images` in the existing image-identity pre-scan; leave table block and figure queue semantics otherwise unchanged.
- [ ] Run the focused and full ingestion suites, compile/diff checks, exact-head independent review, required CI, and live branch-protection check before merge.

### Task 1: Keep row-attached images at their source position

**Files:** `workers/ingestion-python/tests/test_article_document.py`, `workers/ingestion-python/src/autodata_ingestion/article_document.py`.

**Interfaces:** `build_ordered_document(article, blocks)` keeps its signature and ordered-document schema. Table row mappings keep their existing `images` field.

- [ ] **Step 1: Write the failing test.** Build an article whose top-level `images` contain `row-image` with storage key `media/row-image` and `unattached-image` with storage key `media/unattached-image`. Supply one table block with a row mapping whose `images` contain the matching `row-image`. Assert the normalized block types are exactly `["table", "image"]`, the table retains `row-image`, and the only trailing image is `unattached-image`.
- [ ] **Step 2: Verify red.** Run `python -m pytest workers/ingestion-python/tests/test_article_document.py -q -k table_row_image_is_not_appended_again`. The test must fail because the normalized document contains a second `row-image` block, not because of fixture or import errors.
- [ ] **Step 3: Implement minimally.** In `build_ordered_document`'s `table`/`grid` pre-scan, collect `_image_identities` from each row mapping's `images` before visiting its cells. Do not change `_table_block` or image identity rules.
- [ ] **Step 4: Verify green.** Rerun the named test and all of `test_article_document.py`; confirm both the row-attached and genuinely unattached images have their expected positions.
- [ ] **Step 5: Verify and integrate.** Run the full ingestion suite, Python compilation and `git diff --check`; record exact SHA and independent review in the verification document. Push a PR and merge only after current required CI and branch protection pass.

The plan does not claim that the live Workshop origin, paid access, or image retrieval works.
