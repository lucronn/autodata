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
- [x] Run focused/full Workshop Node tests, Go API tests, syntax, diff checks, independent review, and required CI on the original app candidate `832d955`.
- [x] Recheck the final branch after the single-maintainer review rule is integrated on `master` as `fd1a877e68c23c8441be674cacfba43a8f4189e3`; merge only with current exact-head review, CI, and live branch protection.

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
- [x] **Step 5:** Commit the app/test milestone and push the branch.

### Task 2: Verify and prepare integration

**Files:** `docs/verification/2026-11-08-workshop-purchase-availability-status.md`, this plan, and the GitHub Issue/Project item.

**Interfaces:** No code interface changes.

- [x] **Step 1:** Run `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check`.
- [x] **Step 2:** Record original exact-head evidence and obtain independent read-only review; `832d955` had no Critical, Important, or Minor findings.
- [x] **Step 3:** Update [PR #389](https://github.com/lucronn/autodata/pull/389) to the reconciled policy base, rerun checks and exact-head review, and integrate only if the live gates pass. The app PR merged at `2a1ef1cda802c7fbcddbfd6bcec0dccf302e272c`; Issue #388 and Project #8 receive final Done state after this documentation closure.

The task is app-safety work, not proof of live checkout, grants, article access, or production readiness.

The written single-maintainer review rule is now present on `master` at
`fd1a877e68c23c8441be674cacfba43a8f4189e3`, with the same tree as reviewed
policy candidate `a442cfbcce08399d7d046d94182497d5cf686e3d`. The
policy PR #390 record was closed after a 502 response left it unmarked as
merged despite that protected-master squash commit. This resolves the written
review-rule mismatch; it does not waive PR #389's current checks or review.

Final app integration: exact head `a053558cf95dd87d4e485811d4697e216f117221`
passed separate read-only review with zero Critical, Important, or Minor findings,
253 Workshop Node tests, isolated Go API tests, JavaScript syntax, and diff
checks. [CI run 42798577653](https://github.com/lucronn/autodata/actions/runs/42798577653)
passed all three jobs, including the strict required policy/evidence check.
Live branch protection required zero GitHub approvals; there were no blocking
review threads. [PR #389](https://github.com/lucronn/autodata/pull/389)
squash-merged on protected `master` as
`2a1ef1cda802c7fbcddbfd6bcec0dccf302e272c`. This is client-safety
integration, not live commerce or production release acceptance.
