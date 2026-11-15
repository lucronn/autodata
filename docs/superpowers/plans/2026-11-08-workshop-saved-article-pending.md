# Workshop Saved Article Pending Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a saved Workshop article link usable while its account's article index is incomplete, without claiming an absent article exists after index completion.

**Architecture:** No architecture change. The existing `loadArticles()` function reads the account-scoped index, optionally opens a requested article, and reports preparation state. Its absent-ID branch must distinguish an incomplete index from a complete one and carry the requested ID into its existing manual retry. No new endpoint, client authority, or polling behavior is introduced.

**Tech Stack:** Native browser JavaScript; Node's existing actual-function Workshop client harness; Go API regression suite.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md` requires paid/preparing articles to remain openable and retryable. `apps/api-go/workshop/catalog.mjs` explicitly returns an incomplete collection after a bounded polling window. The affected flow is `loadArticles()` in `apps/api-go/workshop/app.mjs`.

**Tracking:** [Issue #379](https://github.com/lucronn/autodata/issues/379) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-saved-article-pending.md).

## Global Constraints

- Do not change checkout, auth, grants, API contracts, index polling limits, source publication, or article detail access.
- Open a saved article immediately when its ID appears in the returned index, including a partial index.
- Only an explicitly complete index may make an absent saved article a definitive unavailable error.
- Preserve the requested article ID on a manual retry of a nonterminal incomplete index. Terminal index failure keeps the existing failure message and does not invent availability.
- Keep navigation-generation guards and the native status/Retry controls. Change only Workshop browser flow, its Node tests, and tracking documents. No production deployment.

---

## Concrete todo

- [x] Reproduce the incomplete-index saved-link error using the actual `loadArticles()` function and confirm the completed-index control.
- [x] Make a minimal `loadArticles()` branch correction and preserve the requested ID on manual retry.
- [ ] Run focused/full Workshop Node and Go API tests, syntax/diff checks, independent review, and required CI before integration.

### Task 1: Preserve a saved article through index preparation

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` near the `articleIndexHarness` tests.
- Modify: `apps/api-go/workshop/app.mjs` inside `loadArticles()`.
- Update: `docs/verification/2026-11-08-workshop-saved-article-pending.md` with exact evidence.

**Interfaces:**
- Consumes: `loadArticles(g, articleID)`, `readCollection()`, `data.complete`, `data.progress`, and `g.current()`.
- Produces: the existing pending/failed status for an absent ID in an incomplete index, a retry retaining `articleID`, and an unavailable error only for a complete index without the ID.

- [x] **Step 1: Write red tests.** With `articleIndexHarness`, supply three hydrated pending responses without `saved/article`, then a completed response containing it. `await h.load('saved/article')` must leave the index visible with preparation status, no opened article, and a Retry action. Invoke that action and assert it opens `saved/article`. Add a completed response missing the ID and assert the existing unavailable error. Add a terminal failed response missing the ID and assert the existing failure status, without an article-missing error or retry.
- [x] **Step 2: Confirm red.** Run `node --test --test-name-pattern='saved article link.*incomplete|saved article link.*complete|saved article link.*failed' apps/api-go/workshop-client.test.mjs`. The pending and failed cases failed against the baseline because `loadArticles()` threw for every missing requested ID. The complete/missing control passed.
- [x] **Step 3: Minimal browser change.** In `loadArticles()`, call `loadArticle(articleID, g)` when the requested ID exists; throw the existing unavailable error only when `data.complete === true` and the ID is absent. Otherwise fall through to the existing pending or terminal-failure status branches. Change the pending Retry callback to call `loadArticles(next, articleID)` so it retains the saved target. Keep every other status and generation guard unchanged.
- [x] **Step 4: Confirm green and broader checks.** Run the focused test, `node --test --test-reporter=dot apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check`. Record exact results and any environmental failures honestly.
- [ ] **Step 5: Review and integrate.** Inspect the scoped diff, update the verification record and Issue #379, commit/push, obtain independent read-only review at the exact candidate, and merge only after required GitHub checks and repository policy permit. Close/check Issue #379 and set its Project item Done after verified merge.
