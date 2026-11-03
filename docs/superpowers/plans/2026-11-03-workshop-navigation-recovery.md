# Workshop Navigation Recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this bounded plan task-by-task after coordinator authorization and the canonical gate. Steps use checkbox syntax for tracking. This checkpoint authorizes planning only until exact-SHA preflight and independent coordinator approval.

**Goal:** Prevent stale source-review failures from changing a newer selection and restore the requested Workshop library, article or order route after successful Google sign-in.

**Architecture:** Keep the existing navigation generations, `loadSource`, `handleSourceError`, `signIn` and `restoreRoute`. Capture the event's generation in its rejection closure and route successful login through the existing validated route dispatcher. Exercise production closures/functions in Node VM contexts; add no browser fixture or exported production API.

**Tech Stack:** Existing browser ESM, Node built-in node:test/assert/fs/vm; no new dependency, framework or runtime.

**Spec:** `docs/architecture/workshop-navigation-recovery.md` and `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Synchronized record:** `docs/agents/tasks/2026-11-03-production-release/2026-11-03-workshop-navigation-recovery.json` (`pre_implementation.status: synchronized`). Coordinator synchronized/read back Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6616750128 and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` (In Progress). Commit/push this planning checkpoint, run exact-commit preflight and pin the actual full checkpoint SHA externally at dispatch after independent coordinator review. The inspected source SHA is not an implementation authorization.

## Global constraints

- Source inspection base: `3578d981942092ecc738a3ea7bc1776cefddd9b6`; all29 existing Workshop Node tests pass there. Read `docs/agents/pre-implementation-gate.md` before work.
- Only two implementation files: `apps/api-go/workshop/app.mjs` and `apps/api-go/workshop-client.test.mjs`. No module extraction, production export, dependency, identity/commerce/backend or browser-fixture change.
- Builders/reviewers use gpt-6.1-sol, medium, Fast/priority, no fallback, as already required by release orchestration.
- Preserve40 existing DTO scenarios x3 engines=120 and7 real-API cases x3 engines=21, the R3/identity/commerce/paid-access8+5+14+12 dependencies and existing graph/receipts. No case relabel/drop or assertions weakened.
- Separate from `2026-11-03-workshop-browser-client-response-loss`; that gate alone owns `scripts/dev/workshop_browser_smoke.py` and `scripts/dev/test_workshop_browser_smoke.py`. This lane edits neither.
- No checkout POST, popup, replacement order or financial authority is added to route restoration. Existing exact-scope authorized article prepare remains the existing article-open behavior.
- No provider/cloud/credential/DNS/deployment action. Coordinator owns actual browser acceptance using frozen inputs and one clean immutable integrated SHA.

## Evidence and decisions

At the source base, app.mjs1107–1111 passes the old generation into `loadSource` but rereads mutable global `viewGeneration` in catch. Evaluating the original event-listener closure in Node and rejecting source A after assigning B delivers the error to B with `current() === true`. Current existing source-review-change-in-flight coverage clicks Back without creating B and checks only empty source DOM; it cannot detect this mismatch.

app.mjs975–979 handles only order or in-memory scope after login. Evaluating the original `signIn` with `?view=library`, authenticated login and no selected scope dispatches zero operations. With a saved article it calls `selectVehicle(g)` without its ID. Existing `restoreRoute` already implements correct order/library/article routing and validation, so use it rather than duplicating routing rules.

## Task1: Pin source-review errors to their originating navigation

**Files:** Modify/test `apps/api-go/workshop-client.test.mjs`; modify `apps/api-go/workshop/app.mjs` at the source-review-load listener. No changed `loadSource` or `handleSourceError` semantics.

**Interfaces:** Consume existing `NavigationGeneration`, event listener and `loadSource(value,g)` Promise. Preserve `handleSourceError(error,g)` and its current-generation status/denial behavior.

- [ ] Add a test-local `fs.readFile`/`vm.runInNewContext` harness that reads the real app.mjs. Extract the complete listener between the exact source-review-load and back listener boundaries; assert both boundaries exist uniquely and are ordered. Evaluate the actual production listener with `$` capturing its callback. No copied substitute listener or source rewriting. Inject deferred `loadSource`, currentArticle, mutable viewGeneration and recording `handleSourceError` which performs the real generation guard before recording mutation.
- [ ] Parameterize rejection as AbortError,401,403 and410. Activate source A, change viewGeneration to B and set A.current false/B.current true, reject A, drain microtasks and assert no B status/clearing mutation. Also assert handler receives A rather than B. Add same-generation401/403/410 controls proving denial is still delivered for clearing, plus no-current-article/no-current-generation controls proving zero source calls. Use a `vm` context setter to change the actual global binding; avoid a test-local shadow that never reaches production.
- [ ] Run `node --test --test-name-pattern='source review' apps/api-go/workshop-client.test.mjs`; before the fix, expect the A→B cases to fail because the real listener forwards B.
- [ ] Replace only the listener with this behavior:

```javascript
$("source-review-load").addEventListener("click", () => {
  const g = viewGeneration;
  if (currentArticle && g?.current())
    void loadSource(currentArticle.source_review?.url, g).catch(
      (error) => handleSourceError(error, g),
    );
});
```

- [ ] Rerun targeted tests, full `node --test apps/api-go/workshop-client.test.mjs`, `node --check apps/api-go/workshop/app.mjs` and `git diff --check`. Verify modified implementation paths are exactly the two listed. Commit and promptly push the validated milestone with message `fix(workshop): retain source review navigation generation`.

## Task2: Restore the requested route after successful login

**Files:** Modify/test the same `apps/api-go/workshop-client.test.mjs`; modify `apps/api-go/workshop/app.mjs` at `signIn` only.

**Interfaces:** Consume actual `session.signIn()` and `session.state.authenticated`. Reuse async `restoreRoute()` unchanged, including existing order/library/article routing and generation invalidation; keep the signingIn guard and checkout-attempt clearing.

- [ ] Add a test-local helper that extracts complete real named `signIn` and `restoreRoute` definitions using their unique next-function boundaries (`bootstrap` and the selector-listener loop respectively), failing closed on missing/duplicate boundaries. Evaluate both definitions in one VM context with URLSearchParams, mutable location.search, minimal `$` value objects, actual route dispatch and controlled session/operation/loadOptions/selectVehicle/library/checkOrder dependencies. `operation(work)` invokes its real work callback with a current generation. Await signIn so route completion is measurable. Do not copy route selection into the test.
- [ ] Assert `?view=library` dispatches library once even when an old valid vehicle is present; direct `?configuration=<uuid>&region=US&article=<uuid>` dispatches selectVehicle with that exact article; selector-hierarchy saved article retains it after loadOptions; `?order=<uuid>&view=library` dispatches checkOrder and never library. Record checkout start calls and assert zero in all cases. For canceled/failed signIn resolving unauthenticated, assert zero route/read/prepare/checkout dispatch; signingIn resets. For an already-running signIn, assert no second popup. For a rejected signIn Promise, preserve rejection/finally behavior and zero route restoration.
- [ ] Run `node --test --test-name-pattern='login route' apps/api-go/workshop-client.test.mjs`; before the fix expect library and article-return assertions to fail.
- [ ] Replace only the successful-authentication branch of `signIn` with:

```javascript
if (session.state.authenticated) await restoreRoute();
```

  Preserve checkout.clear, signingIn try/finally, user gesture/popup handling, restoreRoute validation/precedence, session authority and explicit unauthenticated outcomes.
- [ ] Rerun targeted and full Node tests plus `node --check` and `git diff --check`. Commit/push a second coherent milestone: `fix(workshop): restore requested route after sign in`.

## Task3: Independent review and unchanged acceptance handoff

- [ ] Coordinator obtains independent review at the exact candidate SHA, including stale401/403/410 isolation, same-generation denial controls, saved article and library restoration, canceled login and zero checkout replay.
- [ ] Integrate the two-file candidate separately from reviewed browser response-loss repair. Rebase/re-pin any implementation gate if shared HEAD changes before dispatch; never claim the historical source SHA is a passed current gate.
- [ ] Run existing unchanged120 DTO and21 real-API browser acceptance via the coordinator-owned frozen fixture image/supervisor and exact clean integrated SHA. Keep all original failure artifacts. Record raw receipts, engine/provider inventory, actual test results and cleanup ownership; existing backend inventories remain prerequisites. Do not run ad hoc live providers or alter frozen scripts to make this change pass.
- [ ] Update this plan and canonical navigation doc with actual commit/check commands/review/CI/browser outcome. Until then status is implementation/release unverified; unit PASS alone is insufficient.

## Concrete todo

- [ ] Synchronize Issue186/Project8, this plan, canonical navigation-recovery document and task record; commit the checkpoint, pass exact-base preflight and obtain coordinator approval before implementation.
- [ ] Add failing regressions executing the real source-load click closure after navigation A to B; capture the original generation so stale abort/auth/rights errors cannot change B, while current-generation denials still clear protected state.
- [ ] Add failing regressions executing the real signIn and restoreRoute functions; resume library, saved article and order routes after successful sign-in without checkout replay, and retain canceled/failed-sign-in behavior.
- [ ] Run all Workshop Node tests, JavaScript syntax and scope/diff checks; commit/push two coherent validated milestones and obtain independent exact-candidate review.
- [ ] Coordinator integrates the reviewed UI fix separately from browser response-loss repair, then reruns unchanged120 DTO and21 real-API browser inventories at one immutable integrated SHA with frozen acceptance inputs and independently inspected receipts.
