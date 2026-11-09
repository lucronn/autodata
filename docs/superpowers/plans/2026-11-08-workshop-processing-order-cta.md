# Workshop processing-order purchase action plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development for each implementation step. Keep this task client-only.

**Goal:** A validated processing Workshop order must not show an enabled Buy action for the same configuration and region while payment confirmation remains unresolved.

**Approach:** Keep a client-only marker for the order ID and exact scope after the existing checkout response or owner-only order poll validates a `processing` result. Render a disabled, explicitly confirmation-pending purchase action and retain Check payment status. This does not assert that payment was received or grant access. Clear the marker on a paid or terminal result, a validated missing-order result, or navigation invalidation. A different vehicle is not blocked by an older order marker.

**Tech stack:** Existing native Workshop browser JavaScript, actual-function Node VM tests, and the Go API regression suite. No server, payment, grant, authentication, schema, or architecture change.

**Tracking:** [Issue #385](https://github.com/lucronn/autodata/issues/385), [Project #8](https://github.com/users/lucronn/projects/8), [parent #186](https://github.com/lucronn/autodata/issues/186), and [verification record](../../verification/2026-11-08-workshop-processing-order-cta.md).

## Constraints

- A URL order ID alone cannot establish pending status or entitlement. Only an existing validated checkout response or owner-only `pollOrder()` result may set the marker.
- Distinguish `processing` from `paid`: do not show “Payment received,” owned articles, or any new entitlement for a processing order.
- Preserve existing idempotency, 401 sign-in recovery, stale-navigation guards, terminal states, paid-access behavior from PR #384, and the exact $20 USD terms contract.
- Keep Check payment status available while confirmation remains unresolved. A disabled purchase action must have visible non-color explanatory text; the existing status region should announce the result without noisy polling announcements.
- Do not deploy production or attempt live payment.

## Concrete todo

- [x] Add actual-function tests that reproduce the enabled Buy action after a processing checkout and timed-out order poll, then confirm they fail on the pinned baseline.
- [x] Implement exact-scope validated processing-order state for the existing purchase render and handler; retain a status check without claiming paid access.
- [x] Cover owner-only route recovery, different-scope selection, 404, paid, expired, canceled, and revoked transitions with controls.
- [ ] Run focused/full Workshop Node, Go API, syntax, and diff checks; obtain independent exact-head review and required CI before merge.

### Task 1: Reproduce and fix the processing-order action

**Files:** `apps/api-go/workshop-client.test.mjs`, `apps/api-go/workshop/app.mjs`, and `docs/verification/2026-11-08-workshop-processing-order-cta.md`.

- [x] Write a test through actual `purchase()`, `checkOrder()`, and `renderPurchase()` functions using a validated `processing` checkout response and a timed-out processing poll. Assert that Check payment status stays visible, the purchase action is disabled and does not say Buy or Payment received, the message says confirmation is pending and not to pay again, and no second checkout starts on direct handler invocation.
- [x] Run the focused test on the pinned implementation baseline and record the expected failure.
- [x] Add the smallest client-only exact-scope processing marker; set it from validated checkout/poll responses, render the pending-confirmation state, and guard `purchase()` against direct repeat submission while it is active.
- [x] Rerun the focused test green. Check that the existing status text remains accurate and the native button and status region follow the retrieved forms/accessibility guidance.

### Task 2: Terminal and scope controls

**Files:** the same app/test/verification files.

- [x] Add controls for an owner-only processing route recheck and a different vehicle; a URL-only order must not imply paid or processing status. Confirm a current processing order blocks Buy only for its validated exact scope.
- [x] Add controls for 404, paid, expired, canceled, and revoked: resolve/clear the processing marker at the right boundary, preserve PR #384 paid pending-access handling, and allow a new purchase only when the existing terminal behavior permits it.
- [x] Implement only the behavior demanded by those red controls, then rerun focused and full Workshop tests.

### Task 3: Verification and integration

- [x] Run `node --test apps/api-go/workshop-client.test.mjs apps/api-go/workshop-demo.test.mjs`, `/home/corp/.local/go1.23.4/go/bin/go -C apps/api-go test -count=1 ./...`, `node --check apps/api-go/workshop/app.mjs`, and `git diff --check` on the exact candidate.
- [ ] Update the verification record and Issue/Project evidence, commit and push the reviewable candidate, obtain independent exact-head review, and wait for the required GitHub check. Merge only if branch protection and autonomy policy permit; then close/check Issue #385 and mark its Project item Done.

The tests above are client-safety evidence, not proof of live settlement, grant delivery, paid article access, or production readiness.
