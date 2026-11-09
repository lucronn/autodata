# Workshop Paid Access Pending Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Never invite a second purchase after an owner-only Workshop order reports paid when the subsequent article-access read fails.

**Architecture:** No architecture change. Keep the paid order ID and its existing Check payment status action until `selectVehicle()` confirms article-index access. If that read fails with `ENTITLEMENT_REQUIRED`, retain a distinct client-only pending-access state, a clear no-repay message, and a disabled purchase button; other failures keep the paid-order action without changing server authority.

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
- [ ] Run focused/full Workshop client and Go tests, syntax/diff checks, independent review, and required CI before integration.

### Task 1: Keep the paid-order action until access is confirmed

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` near `orderStatusHarness` and purchase-readiness tests.
- Modify: `apps/api-go/workshop/app.mjs` in `checkOrder()` and `renderPurchase()` only.
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
- [ ] **Step 5: Review and integrate.** Inspect the scoped diff, update verification and the child Issue, commit/push, obtain independent read-only review of the exact candidate, and merge only after required GitHub checks and policy permit. Close/check the issue and set its Project item Done only after verified merge.
