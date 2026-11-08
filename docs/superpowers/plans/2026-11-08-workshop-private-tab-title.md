# Workshop Private Tab Title Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the public Workshop browser title when a purchased article is no longer being displayed, including navigation and protected-state invalidation.

**Architecture:** No architecture change. `renderArticle()` already sets an article-specific `document.title`. The existing `show()` route transition and `clearProtected()` invalidation boundaries should restore the static public title from `workshop/index.html`; the reader render remains the only place that writes an article title. No new state or browser API is introduced.

**Tech Stack:** Native browser JavaScript; existing Node VM-based Workshop client tests; Go API regression suite.

**Spec:** `apps/api-go/workshop/index.html` defines the public title `AutoData — The workshop reference`. `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md` requires protected article content to be cleared on account changes and navigation. The current article title write is in `apps/api-go/workshop/app.mjs`.

**Tracking:** [Issue #381](https://github.com/lucronn/autodata/issues/381) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-private-tab-title.md).

## Global Constraints

- Do not alter authentication, article access, source/media content, payment, API contracts, or browser history.
- The article title remains visible in the tab after a current article render; it is cleared on route transitions and protected-state invalidation, including pagehide/sign-out paths.
- Use the exact public Workshop title already present in `index.html`; do not introduce a different product title.
- Change only Workshop client state, its Node tests, and required tracking documents. No production deployment or live payment.

---

## Concrete todo

- [x] Reproduce stale article tab title through the actual render/navigation and protected-clear functions.
- [x] Restore the public title at both boundaries without changing article rendering.
- [ ] Run focused/full Workshop Node and Go API tests, syntax/diff checks, independent review, and required CI before integration.

### Task 1: Clear the tab title when leaving a protected article

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` near the actual article-media harness tests.
- Modify: `apps/api-go/workshop/app.mjs` inside `show()` and `clearProtected()`.
- Update: `docs/verification/2026-11-08-workshop-private-tab-title.md` with exact evidence.

**Interfaces:**
- Consumes: `document.title`, `show(id)`, `clearProtected()`, and `renderArticle(article, g)`.
- Produces: the public title on route transition/invalidation and an article-specific title only while rendering that article.

- [x] **Step 1: Write red tests.** Use `articleMediaHarness` to render an article, assert the existing article title, call the actual `clearProtected()`, and expect the public title. Separately extract the actual `show()` function with the existing `appSection()`/VM technique, set a private title, navigate to `catalog` and `library`, and assert that each transition restores the public title without altering which section is visible.
- [x] **Step 2: Confirm red.** Run `node --test --test-name-pattern='article tab title' apps/api-go/workshop-client.test.mjs`. Both transition tests failed against the baseline because neither existing boundary changed `document.title`.
- [x] **Step 3: Minimal client change.** Set `document.title` to `AutoData — The workshop reference` in `show()` and `clearProtected()`. Leave `renderArticle()`'s article-specific title write unchanged. Do not add a new title state or refactor unrelated navigation.
- [x] **Step 4: Confirm green and broader checks.** Run the focused test, `node --test --test-reporter=dot apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check` sequentially. Record exact results and environmental failures honestly.
- [ ] **Step 5: Review and integrate.** Inspect the scoped diff, update verification and Issue #381, commit/push, obtain independent read-only review at the exact candidate, and merge only after required GitHub checks and policy permit. Close/check Issue #381 and set its Project item Done after verified merge.
