# Workshop purchase availability status implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Workshop activity status must never claim a vehicle can be purchased when the rendered Buy action is unavailable or the action is sign-in instead.

**Architecture:** Reuse the existing `renderPurchase()` decision and its visible explanation after an entitlement-required response. Do not change quote validation, order state, checkout, entitlement, or API behavior. Keep the valid-quote purchase invitation unchanged.

**Tech Stack:** Native Workshop JavaScript; Node's actual-function VM tests; Go API regression tests.

**Spec:** `docs/verification/2026-11-08-workshop-purchase-availability-status.md`

## Global Constraints

- This is a client-only Workshop copy/feedback correction. No architecture, server, payment, grant, authentication, schema, or production deployment changes.
- Only an exact-scope valid quote and configured merchant can make Buy available; a validated processing order stays no-repay.
- Preserve the $20 USD price and existing accessible visible purchase explanation.
- Track this work against [Issue #388](https://github.com/lucronn/autodata/issues/388), [parent Issue #186](https://github.com/lucronn/autodata/issues/186), and [Project #8](https://github.com/users/lucronn/projects/8).

## Concrete todo

- [x] Reproduce the contradiction through actual `operation()` and `renderPurchase()` with a missing quote; verify the focused test fails on the planning base.
- [x] Use the rendered purchase explanation when Buy is unavailable; retain the available-to-purchase status when Buy is enabled.
- [x] Cover invalid merchant configuration, sign-in, and exact-scope processing order without a false purchase invitation.
- [ ] Run focused/full Workshop Node tests, Go API tests, syntax, diff checks, independent review, and required CI; leave the PR unmerged until the written CODEOWNERS gate is reconciled.

### Task 1: Match activity to purchase availability

**Files:** `apps/api-go/workshop-client.test.mjs`, `apps/api-go/workshop/app.mjs`, `docs/verification/2026-11-08-workshop-purchase-availability-status.md`.

**Interfaces:** `operation(work, retry)` consumes the existing `renderPurchase()`, `status()`, `purchase-action`, and `purchase-message` UI state; it introduces no public interface.

- [x] **Step 1:** Add actual-function tests using `paidPurchaseLifecycleHarness`: an `ENTITLEMENT_REQUIRED` response with `quote=null` must leave Buy disabled and announce purchasing unavailable; with a valid exact-scope quote it must retain the purchase invitation. Add merchant-unconfigured, sign-in, and validated processing-order controls. Start with this red case:

```js
test('purchase availability status reports unavailable without a quote', async () => {
  const required = Object.assign(new Error('Access not ready'), {
    status: 403, code: 'ENTITLEMENT_REQUIRED',
  });
  const h = paidPurchaseLifecycleHarness([]);
  h.context.quote = null;
  await h.context.operation(async () => { throw required; });
  assert.equal(h.$('purchase-action').disabled, true);
  assert.match(h.statuses.at(-1).message, /Purchasing is currently unavailable/);
});
```
- [x] **Step 2:** Run the focused test by name with `node --test --test-name-pattern='purchase availability status' apps/api-go/workshop-client.test.mjs`; the missing-quote case must fail with the old “available to purchase” text.
- [x] **Step 3:** After `renderPurchase()` in the entitlement-required branch, call `status()` with the original available-to-purchase text only when the rendered Buy action is enabled; otherwise reuse the existing purchase-message text. Do not infer entitlement or payment from a URL alone:

```js
status(!$('purchase-action').disabled &&
  $('purchase-action').textContent === 'Buy for $20 USD'
    ? 'This vehicle is available to purchase.'
    : $('purchase-message').textContent);
```
- [x] **Step 4:** Rerun focused and full Workshop tests; record red/green evidence in the spec/verification document.
- [ ] **Step 5:** Commit the app/test milestone and push the branch.

### Task 2: Verify and prepare integration

**Files:** `docs/verification/2026-11-08-workshop-purchase-availability-status.md`, this plan, and the GitHub Issue/Project item.

**Interfaces:** No code interface changes.

- [x] **Step 1:** Run `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check`.
- [ ] **Step 2:** Record exact-head evidence and request independent read-only review; repair any important finding and rerun affected tests.
- [ ] **Step 3:** Push the final candidate, create a PR against `master`, wait for exact-head required CI, and update Issue/Project evidence. Do not merge while the written CODEOWNERS-review requirement remains unmet.

The task is app-safety work, not proof of live checkout, grants, article access, or production readiness.
