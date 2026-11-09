# Workshop processing-order purchase action

A validated `processing` checkout order can return a timed-out `processing` owner-only status. Before this fix, `purchase()` calls `renderPurchase()` after the poll and can re-enable “Buy for $20 USD” while `currentOrder` and Check payment status remain. The server idempotency key still protects the request, but the client invitation is misleading. This client-only task keeps confirmation-pending copy and a disabled purchase action for the validated exact scope.

Acceptance and verification:

- [x] Actual `purchase()` / `checkOrder()` / `renderPurchase()` regression is red on the pinned baseline and green after the fix; no second checkout starts while the same validated order is processing.
- [x] The pending-confirmation state keeps Check payment status, does not claim payment received or owned access, and shows visible no-repay guidance.
- [x] Owner-only route recovery and a different-vehicle control cannot turn an unvalidated or unrelated order ID into a false pending/paid state.
- [x] Paid, 404, expired, canceled, and revoked transitions preserve the existing paid-access and terminal behaviors.
- [ ] Focused/full Workshop Node tests, Go API tests, syntax/diff checks, independent exact-head review, and required CI pass before integration.

Tracking: [Issue #385](https://github.com/lucronn/autodata/issues/385), [Project #8](https://github.com/users/lucronn/projects/8), and [implementation plan](../superpowers/plans/2026-11-08-workshop-processing-order-cta.md). Parent [#186](https://github.com/lucronn/autodata/issues/186). No production deployment or live payment is authorized.

Planning checkpoint `a9442592bdb0761597f0815e34accbe1463b7266` passed exact-SHA preflight with `status: synchronized`, `errors: []` before app edits. On that baseline, the actual-function processing checkout timeout test failed because the purchase message advertised a new purchase instead of pending confirmation. The first implementation made that test green. Terminal controls then exposed a stale disabled action after an owner-only 404; a client rerender on that transition fixed it. Paid/expired/canceled/revoked controls and owner-only route recovery pass; a URL-only 404 does not claim confirmation, and a different configuration with its own purchasable quote is not blocked by the older marker. All 242 Workshop client/demo Node tests pass. The full Go API suite passed in isolated runs (`ok github.com/lucronn/autodata/apps/api-go 8.665s`, `9.961s`, and final `8.728s`); one run concurrent with Node tests failed only the pre-existing wall-clock-sensitive `TestFirebaseADCCredentialRefreshHasIndependentTimeout` (`elapsed=4.008s` above its 3s bound), then passed when rerun alone. JavaScript syntax and diff checks pass. Exact-head independent review and required CI remain pending; these local tests are not release acceptance.
