# Workshop Terminal Order Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep “Check payment status” available for a pending Workshop order, but remove the old order action once that order is paid, expired, canceled, revoked, or not found.

**Architecture:** No architecture change. The existing `checkOrder()` browser function owns the order ID and native button. It should clear both after a current terminal response or current 404, while retaining its current pending timeout/retry path and generation guard. `pollOrder()`, checkout, settlement, entitlements, and server contracts stay unchanged.

**Tech Stack:** Native browser JavaScript; Node's existing VM-based Workshop client tests; Go API tests for regression coverage.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md` limits the manual order check to a pending order. The actual `checkOrder()` implementation in `apps/api-go/workshop/app.mjs` is the flow being corrected.

**Tracking:** [Issue #377](https://github.com/lucronn/autodata/issues/377) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-terminal-order-status.md).

## Global Constraints

- Do not change the price, payment provider, checkout idempotency, order state contract, authentication, grants, or vehicle/article access.
- A pending or timed-out still-pending order keeps its manual status action and ID; no automatic replacement purchase is created.
- Only the current navigation generation may clear an order action or checkout attempt after an asynchronous result.
- Keep the existing visible status/error messages and native button; no new UI component or architecture.
- Change only Workshop browser state, its Node tests, and required tracking documents. No production deployment or live payment.

---

## Concrete todo

- [x] Add failing tests of the real `checkOrder()` function for terminal and current 404 outcomes, plus pending and stale-generation controls.
- [x] Clear the order ID and hide its button only when the current order is terminal or 404.
- [ ] Run focused/full Workshop Node and Go API tests, syntax/diff checks, independent review, and required CI before integration.

### Task 1: Clear terminal payment-status actions

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` near the navigation/order tests.
- Modify: `apps/api-go/workshop/app.mjs` inside `checkOrder()`.
- Update: `docs/verification/2026-11-08-workshop-terminal-order-status.md` with exact evidence.

**Interfaces:**
- Consumes: `checkOrder(g, id)`, `pollOrder()`, `g.current()`, `currentOrder`, and `#check-order`.
- Produces: an empty order ID and hidden button after current paid/expired/canceled/revoked/404 outcomes; the existing pending ID/button remain usable.

- [x] **Step 1: Write red tests.** Use the existing `appSection('async function checkOrder(', 'async function purchase()')` helper with `runInNewContext`. Stub only `pollOrder` (external asynchronous order read), `selectVehicle`, `invalidate`, status rendering, and checkout storage. For full v1 order DTOs returned as `paid`, `expired`, and `canceled`, call the actual `checkOrder()` and assert `currentOrder === ''` and `#check-order.hidden === true`. For a current 404, assert the same and one checkout clear. For `processing` with `timedOut: true`, assert the ID remains and the button remains visible. For a generation that becomes stale before 404, assert no checkout or current-order state is cleared. The terminal tests must fail against the initial implementation because `checkOrder()` sets the ID/button visible and never clears them.
- [x] **Step 2: Confirm red.** Run `node --test --test-name-pattern='order status clears terminal action|order status clears missing action|order status retains pending action|stale order status' apps/api-go/workshop-client.test.mjs`. Expect terminal/current-404 assertions to fail before editing `app.mjs`; pending/stale controls may pass.
- [x] **Step 3: Minimal browser change.** In `checkOrder()`, after `if (!g.current()) return`, clear `currentOrder` and hide `#check-order` for `paid`, `expired`, `canceled`, or `revoked` before their existing handlers. In `catch`, perform checkout clear plus the same browser cleanup only when `g.current()` and `error.status === 404`; rethrow every error as before. Do not call `invalidate()` for paid/expired/canceled, because that also clears protected article state.
- [x] **Step 4: Confirm green and broader checks.** Run the focused test, `node --test --test-reporter=dot apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check` sequentially. Record exact results and any environmental failures honestly.
- [ ] **Step 5: Review and integrate.** Inspect the scoped diff, update the verification document and Issue #377, commit/push, request read-only independent review at the exact candidate SHA, and merge only after required GitHub checks and repository policy permit. Close/check Issue #377 and set its Project item Done after verified merge.
