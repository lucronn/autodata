# Workshop Order Status Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the prior order's “Check payment status” action when a customer navigates to another Workshop view or vehicle, without interrupting an active pending-order check.

**Architecture:** No architecture change. The existing `invalidate()` boundary already cancels work and clears protected view state on vehicle, route, library, browse, logout, and pagehide transitions. Reset only the browser's order ID and native status button there; leave checkout, `pollOrder`, and order APIs unchanged.

**Tech Stack:** Native browser JavaScript and the existing Node VM-based Workshop client tests.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md` requires order polling to stop on selection changes and to offer a manual status check only for the pending order. The existing Workshop navigation and checkout implementation is the concrete behavior being corrected.

**Tracking:** [Issue #375](https://github.com/lucronn/autodata/issues/375) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and [verification record](../../verification/2026-11-08-workshop-order-status-navigation.md).

## Global Constraints

- Do not alter checkout idempotency, order polling, order/quote APIs, authentication, selected vehicle scope, or source content.
- A pending order retains its manual status action until the customer leaves that order context.
- Vehicle, browse, library, history, logout, and pagehide invalidation must not retain a clickable prior-order control.
- Keep navigation-generation cancellation and protected-content clearing unchanged.
- Change only Workshop browser state, its Node tests, and required tracking documents.

---

## Concrete todo

- [ ] Add a failing regression that runs the real `invalidate()` function with a visible prior-order action.
- [ ] Clear the prior order ID and hide its status button at that navigation boundary.
- [ ] Run focused/full Workshop Node and Go API tests, syntax and diff checks, obtain independent review, and integrate only after CI/policy gates pass.

### Task 1: Clear obsolete payment-status action on navigation

**Files:**
- Modify: `apps/api-go/workshop-client.test.mjs` (actual app-boundary tests)
- Modify: `apps/api-go/workshop/app.mjs` (`invalidate()`)
- Update: `docs/verification/2026-11-08-workshop-order-status-navigation.md`

**Interfaces:**
- Consumes: current `currentOrder`, `#check-order`, and existing navigation invalidation calls.
- Produces: cleared order ID and hidden native status button on navigation; no API or data-contract change.

- [ ] **Step 1: Write the failing test.** Evaluate `appSection('function invalidate(', 'async function operation(')` in `runInNewContext` with an actual visible `#check-order` node, a prior order ID, and only navigation/`clearProtected` dependencies stubbed. Call `invalidate()` and assert the button is hidden and the order ID is empty. The production omission of both resets must make this test fail.
- [ ] **Step 2: Confirm red.** Run `node --test --test-name-pattern='navigation invalidation clears prior order status' apps/api-go/workshop-client.test.mjs`; expect `#check-order.hidden` to remain `false` before the implementation change.
- [ ] **Step 3: Implement the minimal fix.** Add `currentOrder = "";` and `$("check-order").hidden = true;` inside `invalidate()` after `navigation.clear()`. Do not change `checkOrder()`, `pollOrder()`, or its manual button listener; these continue to set a visible action for the active pending order.
- [ ] **Step 4: Confirm green and broader checks.** Run the focused test, `node --test --test-reporter=dot apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check`.
- [ ] **Step 5: Review and integrate.** Inspect the scoped diff, update verification evidence and Issue #375, commit and push the feature branch, request independent review, and merge only after required CI and repository policy gates pass.
