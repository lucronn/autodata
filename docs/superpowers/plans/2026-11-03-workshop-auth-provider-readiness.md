# Workshop auth provider readiness Implementation Plan

> For agentic workers: use superpowers:executing-plans only after the coordinator establishes the synchronized gate at the pinned checkpoint SHA. This planning checkpoint alone authorizes no implementation; coordinator integration, re-pinning and independent gate review remain required.

**Gate status:** synchronized at `2026-11-03T22:22:29.570981+00:00`. Coordinator saved and read back [Issue186 comment6616892250](https://github.com/lucronn/autodata/issues/186#issuecomment-6616892250) and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` with this exact goal, six todos, scope and evidence limits. Commit/push this planning checkpoint and run preflight at its exact SHA; coordinator integration, re-pinning and independent gate review precede implementation.

**Goal:** Ensure Workshop sign-in readiness always includes an initialized Google provider after overlapping logout SDK preparation and session bootstrap, and recover consistently from synchronous popup invocation errors and asynchronous popup rejections.

**Architecture:** Construct the Google provider in the same synchronous initialization segment as the Firebase auth instance, before awaiting persistence or checking the originating epoch again. In the existing-auth branch, retry Google provider construction when it is absent before awaiting persistence; constructor or persistence errors must remain contained with ready false and safe feedback. Keep epoch checks on UI publication. Invoke the popup inside the existing async operation's try block before its first await, preserving the explicit gesture while routing synchronous errors through the existing cleanup and finally logic. Preserve the session exchange and cookie authority contracts.

**Tech stack:** Existing production ESM createSession, bundled official Firebase SDK, node:test with deferred mocked SDK promises. No dependency additions.

**Spec:** docs/superpowers/plans/2026-11-03-workshop-customer-ui.md and docs/agents/pre-implementation-gate.md.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: docs/superpowers/plans/2026-11-03-workshop-auth-provider-readiness.md
Record: docs/agents/records/2026-11-03-workshop-auth-provider-readiness.json
Task: docs/agents/tasks/2026-11-03-production-release/workshop-auth-provider-readiness.json
Canonical repository updates: the customer UI plan, this dedicated plan, and docs/agents/tasks/2026-11-03-production-release/queue.json.
Diagnosis source SHA: `87f4d8b44d9ecccd3f0ead1d4f31a4a5f136f6cf`. Planning source integration base: `1b9b6fff6a482a7c82a7291e0732132e15ead6ed`. Planning branch: `codex/workshop-auth-provider-plan`. Live synchronization is complete. Commit/push the planning checkpoint and run exact-commit preflight; the coordinator then integrates it, re-pins the machine gate and independently reviews before implementation dispatch.

## Evidence and limits

The one-off /tmp/autodata-auth-epoch-repro.mjs imports real createSession from the exact diagnosis checkout. Its deferred mocked SDK proves cookie-only bootstrap -> logout initialization paused in first setPersistence -> a second bootstrap401 -> existing-auth persistence completes -> old persistence completes after epoch changes -> ready true while GoogleAuthProvider construction count is zero. Popup receives undefined. The script exits0 with assertions for both synchronous-validation and asynchronous-rejection stubs.

The synchronous stub escapes the error and strands ready false with the previous sign-in message. The asynchronous stub is caught and produces the generic unavailable message. Bundled Firebase signInWithPopup invokes its provider validation synchronously. Therefore the initialization invariant defect is deterministic, but it is not a proven explanation of the original WebKit failure.

Preserve the failed full21 receipt at /tmp/autodata-workshop-browser-api-87f4d8b unchanged. It records20 passes and WebKit Banktwo account_scope_and_revocation failure. Do not reclassify it as passing, replace it with a diagnostic repeat, or attribute it conclusively to this repair. Preserve the exact API21/DTO120 acceptance graph, case identities, supervisor/image pins, SDK bytes, provider fixtures, request boundaries, deadlines, provenance, and cleanup rules.

## Implementation scope

Modify only:
- apps/api-go/workshop/auth.mjs — provider initialization ordering and synchronous popup error containment.
- apps/api-go/workshop-client.test.mjs — deterministic race and popup failure regressions using real exported createSession.

No changes to browser fixtures, test selection/inventories, transport, provider handlers, SDK bundle, commerce/catalog/server behavior, or timeout/retry policy. Sanitized browser failure diagnostics require a separate scoped gate; do not fold them into this change.

## Concrete todo for Issue186 / Project8 / record synchronization

1. Synchronize the goal, exact two-file scope, evidence limits, dedicated plan, canonical customer UI plan, queue, task and record in Issue186/Project8; commit and push the planning checkpoint and pass exact-SHA preflight before implementation.
2. Add a failing deterministic Node regression for cookie-only logout preparation overlapping epoch-changing bootstrap, asserting every ready state has a constructed provider and the next explicit sign-in receives that provider and completes cookie exchange.
3. Add failing regressions for synchronous popup invocation throw and asynchronous popup rejection, requiring the same safe message, SDK sign-out cleanup, restored readiness, and no escaped rejection; retain immediate popup invocation within the user gesture.
4. Construct provider before the persistence await and move popup invocation inside the existing async try without an intervening await; retain epoch guards, memory-only persistence, fresh token checks, session exchange and cookie-session authority.
5. Run the focused red/green Node cases, full Workshop Node tests, applicable Go tests and diff/scope/provenance checks; commit and promptly push the coherent fix, then obtain independent exact-commit review.
6. Coordinator integrates the reviewed fix and collects fresh immutable-candidate API21/DTO120 evidence using the frozen infrastructure; selected-case repeats remain diagnostic only and the original failed receipt remains retained.

## Task 1: Regressions and minimal repair

- [ ] Add a node:test race next to the tests at workshop-client.test.mjs182-225. Use explicit deferred promises, not timeouts. Begin with a valid cookie session so SDK load count is0. Start logout; wait for the first setPersistence call to begin and leave it unresolved. Have request('/auth/logout') set the stub cookie authority false. Start a second bootstrap; its config/session returns valid config/401. Resolve the second setPersistence call and await that bootstrap. Require provider construction count1 when ready becomes true. Resolve first persistence and await logout. Require provider passed to signInWithPopup is an instance of the stub GoogleAuthProvider; complete getIdTokenResult, POST exchange and cookie GET; require authenticated true and initialized auth/provider counts1. The current implementation fails construction-count assertion0 before the popup.
- [ ] Add a deterministic constructor-failure/retry case with an initially unauthenticated cookie response. Make the provider constructor throw on its first two calls and succeed on its third. First bootstrap initializes auth but fails constructor preparation; require ready false and safe generic feedback with no escaped rejection. Second bootstrap takes the existing-auth branch, retries provider construction and fails again; require ready false, no popup availability and no escaped rejection. Third bootstrap retries construction successfully, awaits persistence and becomes ready; require auth initialized once, provider construction attempted three times, and the next explicit sign-in receives the constructed provider and completes cookie exchange. This fails against current code because the second bootstrap skips construction and reports ready true.
- [ ] Add separate sync-throw and async-rejection cases with fully prepared sessions. Both popup stubs use a safe error code auth/internal-error; one throws synchronously, the other returns Promise.reject. Require session.signIn() returns a promise, await it without escaped rejection, verify generic unavailable message and ready true, authenticated false, cleared CSRF, one SDK cleanup signOut. Record an event synchronously in the popup stub; before awaiting the returned promise require that event already exists, proving no popup deferral.
- [ ] Run `node --test --test-name-pattern='logout preparation|provider constructor|popup invocation|popup rejection' apps/api-go/workshop-client.test.mjs` and retain the expected red assertions. Do not weaken assertions to fit existing behavior.
- [ ] In auth.mjs prepare, move `provider = new sdk.GoogleAuthProvider()` directly after initializeAuth and before `await sdk.setPersistence`. In the existing-auth branch, execute `if (!provider) provider = new sdk.GoogleAuthProvider()` before `await sdk.setPersistence(auth, sdk.inMemoryPersistence)`. Contain constructor/persistence failures in that branch using the same safe preparation-failure behavior: only for the current epoch, set ready false, set message to authMessage(error), and call changed(); do not escape a rejection or enable the popup. A later bootstrap may retry construction. Keep stale epochs from publishing failure feedback or readiness. Do not move UI readiness before persistence; retain current===epoch checks. Provider construction must not be skipped merely because a later bootstrap owns the UI epoch, and every branch that sets ready true must have a constructed provider.
- [ ] In signIn, remove the outer `const popup = ...` and make popup invocation the first expression inside the existing async IIFE's try: `const result = await (state.confirm && auth.currentUser ? sdk.reauthenticateWithPopup(auth.currentUser, provider) : sdk.signInWithPopup(auth, provider));`. There is no await before invocation. Existing catch/finally now handles both sync throw and async rejection. Preserve all other branches.
- [ ] Re-run focused tests, then `node --test apps/api-go/workshop-client.test.mjs`. Run the existing appropriate Go API verification command in the owned offline test environment because auth.mjs is embedded; do not introduce a browser/provider call into Node tests. Run `git diff --check` and verify implementation diff contains exactly the two allowlisted files. Confirm frozen browser inputs and API21/DTO120 graph remain unchanged.
- [ ] Commit with `fix(workshop): keep provider ready across session rechecks`, push the assigned feature branch promptly after validation, and request independent exact-SHA review before coordinator integration.

## Gate record handoff

The standalone record and nested task record contain the identical Goal and six concrete todo entries above with `status: synchronized` and timestamp `2026-11-03T22:22:29.570981+00:00`. repository_doc_refs include the dedicated plan, canonical customer UI plan and queue. Live synchronization evidence is [Issue186 comment6616892250](https://github.com/lucronn/autodata/issues/186#issuecomment-6616892250) and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, saved and read back by the coordinator. This checkpoint must pass exact-commit machine preflight; coordinator integration, re-pinning and independent gate review remain required before code dispatch. The /tmp reproduction remains diagnosis support and confers no browser acceptance.
