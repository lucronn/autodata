# Workshop processing-order purchase action

A validated `processing` checkout order can return a timed-out `processing` owner-only status. Before this fix, `purchase()` calls `renderPurchase()` after the poll and can re-enable “Buy for $20 USD” while `currentOrder` and Check payment status remain. The server idempotency key still protects the request, but the client invitation is misleading. This client-only task keeps confirmation-pending copy and a disabled purchase action for the validated exact scope.

Acceptance and verification:

- [ ] Actual `purchase()` / `checkOrder()` / `renderPurchase()` regression is red on the pinned baseline and green after the fix; no second checkout starts while the same validated order is processing.
- [ ] The pending-confirmation state keeps Check payment status, does not claim payment received or owned access, and shows visible no-repay guidance.
- [ ] Owner-only route recovery and a different-vehicle control cannot turn an unvalidated or unrelated order ID into a false pending/paid state.
- [ ] Paid, 404, expired, canceled, and revoked transitions preserve the existing paid-access and terminal behaviors.
- [ ] Focused/full Workshop Node tests, Go API tests, syntax/diff checks, independent exact-head review, and required CI pass before integration.

Tracking: [Issue #385](https://github.com/lucronn/autodata/issues/385), [Project #8](https://github.com/users/lucronn/projects/8), and [implementation plan](../superpowers/plans/2026-11-08-workshop-processing-order-cta.md). Parent [#186](https://github.com/lucronn/autodata/issues/186). No production deployment or live payment is authorized.
