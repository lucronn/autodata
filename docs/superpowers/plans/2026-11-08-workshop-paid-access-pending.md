# Workshop Paid Access Pending Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Never invite a second purchase after an owner-only Workshop order reports paid when the subsequent article-access read fails.

**Architecture:** No architecture change. Keep the paid order ID and its existing Check payment status action until `selectVehicle()` confirms article-index access. If that read fails, retain a distinct client-only pending-access state, a clear no-repay message, and a disabled purchase button. A validated processing checkout order must survive a focus/bootstrap recheck through the existing owner-only `?order=` route; no URL value grants access or changes server authority.

**Tech Stack:** Native Workshop browser JavaScript and existing Node VM client tests; Go API regression suite.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-commerce.md` defines owner-only paid order status with `retry_disposition: "do_not_repay"` and a durable grant. `apps/api-go/workshop/app.mjs` contains `checkOrder()`, `selectVehicle()`, `operation()`, and `renderPurchase()`; [paid Workshop Issue #186](https://github.com/lucronn/autodata/issues/186) is the parent scope. This plan describes an app-only safety behavior; it does not assert that live payment or grant reconciliation succeeds.

**Tracking:** [Issue #383](https://github.com/lucronn/autodata/issues/383), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-paid-access-pending.md).

## Global Constraints

- No payment API, grant, order, auth, server state, Stripe, schema, or architecture changes.
- The order response must be validated by the existing owner-only `pollOrder()` before any pending-access UI is shown.
- Never treat `paid` as article access granted; only a successful current article-index read can end the pending state.
- Preserve the existing expired, canceled, revoked, and truly pending order behavior, checkout idempotency, and stale-navigation guard.
- Keep the exact $20 USD price and terms contract unchanged. No production deployment or live payment.

---

## Concrete todo

- [x] Reproduce a paid order followed by an entitlement-required article read that currently exposes Buy again.
- [x] Keep a no-repay, retryable paid-access state until article-index access succeeds.
- [x] Cover paid post-order 410/other article failures and focus/bootstrap restoration without a second Buy invitation.
- [x] Preserve confirmed-paid no-repay handling when a newer article/open-index operation supersedes a hydrating paid check.
- [x] Cover all newer-operation errors for confirmed paid access, including 404/410/503 no-repay and revoked terminal cleanup.
- [ ] Run focused/full Workshop client and Go tests, syntax/diff checks, independent review, and required CI before integration.

### Task 1: Keep the paid-order action until access is confirmed

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` near `orderStatusHarness` and purchase-readiness tests.
- Modify: `apps/api-go/workshop/app.mjs` in `checkOrder()` and `renderPurchase()` for the initial correction.
- Update: `docs/verification/2026-11-08-workshop-paid-access-pending.md` with exact red/green evidence.

**Interfaces:**
- Consumes: `checkOrder(g, id)`, validated `pollOrder` response, `selectVehicle(g)`, `renderPurchase()`, `status()`, `currentOrder`, and `access`.
- Produces: a visible existing Check payment status action and disabled purchase CTA while a confirmed paid order lacks a successful article-index read; unchanged terminal order behavior otherwise.

- [x] **Step 1: Write red tests.** Extend the actual-function `orderStatusHarness` to simulate a paid order followed by `ENTITLEMENT_REQUIRED`, assert that `checkOrder()` does not throw, leaves the order action visible, keeps the settled checkout attempt, and reports a no-repay pending-access state. Assert that a later successful `selectVehicle()` clears the action; update the existing paid terminal-action expectation accordingly. Adjust the existing paid article 404 control to require the action to stay available without a new checkout. Extract actual `renderPurchase()` into a VM fixture with valid quote/merchant and authenticated session; assert pending access shows explanatory text and a disabled non-Buy action even when merchant configuration is unavailable.

  ```js
  const required = Object.assign(new Error('Access not ready'), {
    status: 403, code: 'ENTITLEMENT_REQUIRED',
  });
  const paidOrder = {
    version: 'v1', order_id: orderID, ...scope, state: 'paid',
    retry_disposition: 'do_not_repay', timedOut: false,
  };
  const h = orderStatusHarness(paidOrder, { selectionError: required });
  await h.check();
  assert.equal(h.context.currentOrder, orderID);
  assert.equal(h.button.hidden, false);
  assert.equal(h.checkoutClears(), 0);
  assert.equal(h.context.access, 'pending');
  // Separately run actual renderPurchase() with access='pending':
  // purchase-action.disabled=true and its text is not Buy.
  ```
- [x] **Step 2: Confirm red.** Run `node --test --test-name-pattern='paid access|paid article 404' apps/api-go/workshop-client.test.mjs`; verify failures are the premature order-action clear and Buy CTA, not fixture errors. The first run exposed a missing test import; after correcting it, all three tests failed for the expected production behavior.
- [x] **Step 3: Minimal app change.** In `checkOrder()`, defer clearing `currentOrder` and hiding `check-order` for `paid` until current `selectVehicle(g)` returns successfully. On its `ENTITLEMENT_REQUIRED` failure, set client `access = "pending"`, call `renderPurchase()`, show the welcome section and a no-repay/check-status message, and return; on other non-revoked post-payment errors retain pending state and rethrow for existing error handling. Preserve revoked behavior by clearing the order action before rethrowing `ENTITLEMENT_REVOKED`. Add a pending-access message before the merchant-unavailable message and a disabled `Payment received` CTA in `renderPurchase()` while leaving valid quote/terms checks and `purchase()` unchanged.

  ```js
  if (result.state === 'paid') {
    vehicle = { id: result.configuration_id, region: result.region };
    try {
      await selectVehicle(g);
    } catch (error) {
      if (!g.current()) return;
      if (error.code === 'ENTITLEMENT_REVOKED') {
        currentOrder = '';
        $("check-order").hidden = true;
        throw error;
      }
      access = 'pending';
      renderPurchase();
      if (error.code !== 'ENTITLEMENT_REQUIRED') throw error;
      show('welcome');
      status('Payment received. Access is not ready. Check payment status again; do not pay again.', { error: true });
      return;
    }
    if (!g.current()) return;
    currentOrder = '';
    $("check-order").hidden = true;
  }
  ```
- [x] **Step 4: Confirm green and broader checks.** Rerun the focused test; then run `node --test --test-reporter=dot apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check` sequentially. Focused 7/7, full Workshop 218, Go API 8.699s, syntax and diff checks passed locally.
- [x] **Step 5: Review the first candidate.** Independent read-only review of `dda39d9` found two blocking paid-order paths: a 410 article read is reset by outer `operation()`, and a focus/bootstrap recheck loses a paid order reached through `checkout.start()` processing. A generic retry action also points to a no-op purchase. Keep PR #384 unmerged.

### Task 2: Preserve validated paid status across error and focus boundaries

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` with actual-function purchase/operation/bootstrap/restoreRoute coverage.
- Modify: `apps/api-go/workshop/app.mjs` in `checkOrder()`, `purchase()`, and the existing URL-order lifecycle only.
- Update: `docs/verification/2026-11-08-workshop-paid-access-pending.md` with red/green and exact-head review/CI evidence.

**Interfaces:** Existing validated `checkout.start()` processing response, owner-only `pollOrder()`, `?order=` route in `restoreRoute()`, `operation()`, `selectVehicle()`, and `renderPurchase()`. The order query parameter is a resume pointer, not an entitlement or purchase authority; `pollOrder()` still validates it for the signed-in owner.

- [x] **Step 6: Write red integration tests.** Exercise the real `purchase()` → `operation()` → `checkOrder()` path with a paid order whose article read returns `CATALOG_WITHDRAWN` (410); assert no Buy invitation, no checkout retry, retained Check payment status, and no new checkout. Exercise a validated processing response followed by paid/`ENTITLEMENT_REQUIRED`, then the actual `bootstrap()`/`restoreRoute()` path; assert the pending order is rechecked instead of switching to Buy. Add successful access and 401 sign-in recovery controls.
- [x] **Step 7: Confirm red.** The two new integration tests failed on `dda39d9` with `access: unknown` instead of pending after the 410 and one rather than two owner-only order reads across focus; no fixture failures.
- [x] **Step 8: Minimal repair.** On current paid order plus non-revoked/non-401 post-payment article failure, clear protected partial-index content, then show a no-repay state without outer `operation()` resetting it or exposing an ineffective purchase retry. Record a validated processing order ID in the existing `?order=` route before checking it, preserve it through search/URL updates during a partial index, allow owner-only revalidation on focus, and remove the marker after confirmed article access or terminal non-paid order. Preserve sign-in recovery on unauthenticated order reads and never treat the URL as an entitlement. Additional red/green partial-200-then-410 and search/focus tests pass; all 224 Workshop Node tests pass locally.
- [ ] **Step 9: Verify and integrate.** Run focused and full Workshop Node/Go suites, syntax/diff checks; commit/push, obtain independent review of exact repair SHA, await required CI, merge only if policy permits, then close/check the Issue and Project item. No production deployment or live payment.

### Task 3: Guard newer operations during confirmed paid hydration

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` with actual-function partial-index, newer-operation, and entitlement failure coverage.
- Modify: `apps/api-go/workshop/app.mjs` in `operation()`, `invalidate()`, `checkOrder()`, and the local confirmed-paid state only.
- Update: `docs/verification/2026-11-08-workshop-paid-access-pending.md` with red/green, review, and CI evidence.

**Interfaces:** A confirmed `paid` result from owner-only `pollOrder()` is distinct from `currentOrder`, which also tracks a still-processing order. A newer `operation()` can invalidate the original paid check while a partial index is visible; an `ENTITLEMENT_REQUIRED` error from that newer read must still be no-repay. The marker is client-only, never grants access, and is cleared on navigation invalidation, terminal order, missing order, or successful article-index access.

- [x] **Step 10: Write red race regression.** Use the real partial `loadArticles()`/`readCollection()` path. After its first hydrating response, open a visible article in a newer operation and reject it with `ENTITLEMENT_REQUIRED`; assert a validated paid order remains checkable and the CTA is disabled/non-Buy. Add processing-order and different-vehicle controls so an unconfirmed or unrelated order never masquerades as paid.
- [x] **Step 11: Confirm red and repair.** The race test on `df2421d` failed with `access: missing` instead of pending. A client-only confirmed-paid marker is now set only from a validated paid result and bound to the exact configuration/region. Generic entitlement handling preserves pending/no-repay only for that order and scope, while clearing protected content. The marker clears on invalidation, terminal or missing order, revoked access, and successful article-index access. Focused controls and 227 Workshop Node tests pass locally.
- [ ] **Step 12: Verify and integrate.** Run focused/full Workshop and Go suites, syntax/diff, exact-head independent rereview, and required CI. Update Issue/Project/verification evidence. Merge only after all gates permit; no production deployment or live payment.

### Task 4: Complete confirmed-paid error and terminal handling

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` with partial-paid-index/newer-operation 404/410/503 and revoked controls.
- Modify: `apps/api-go/workshop/app.mjs` in `operation()` only.
- Update: `docs/verification/2026-11-08-workshop-paid-access-pending.md` with red/green and final evidence.

**Interfaces:** The Task 3 scope-bound marker already distinguishes owner-validated paid status from a processing order. Any current newer-operation failure other than authentication or revocation must keep the order check visible, clear potentially protected partial content, and render a disabled no-repay pending state. A current `ENTITLEMENT_REVOKED` failure must clear the marker, order action, and resume route while showing revoked state. A 401 still requires sign-in and leaves the route for owner-only recovery.

- [x] **Step 13: Write red sibling/terminal tests.** Reuse the actual partial-index/open-article path; reject the newer article operation with 404, 410, and 503 in turn, requiring cleared protected rows, retained paid order/action/route, and disabled non-Buy copy. Reject it with `ENTITLEMENT_REVOKED` and require cleared order marker/action/route and revoked messaging. Add a 401 sign-in/recovery control.
- [x] **Step 14: Confirm red and repair.** On `25b1a35`, the 404/503 tests failed with owned access, 410 with unknown access, and revoked with a retained order action. The exact-scope confirmed-paid branch in `operation()` now handles all non-401/non-revoked errors; a current revocation clears the terminal marker/order/route/action. The 401 control requires sign-in and recovers the order through owner-only revalidation. All 232 Workshop Node tests pass locally.
- [ ] **Step 15: Verify and integrate.** Rerun focused/full Workshop and Go tests, syntax/diff, independent exact-head review, and required CI. Update Issue/Project/verification evidence; merge only if gates permit. No production deployment or live payment.
