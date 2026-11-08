# Workshop terminal order-status action

The current Workshop order-status function marks `#check-order` visible before polling. A reproducible expired-order response leaves that button visible and retains the old order ID despite reporting that the payment attempt ended. A paid response has the same missing cleanup; a current 404 clears checkout storage but not the button. The narrow correction makes the manual action belong only to a still-pending order.

Acceptance and verification:

- [ ] Paid, expired, canceled, revoked, and current not-found outcomes clear the old order ID and hide “Check payment status”.
- [ ] Pending/timed-out orders keep the manual action; stale asynchronous outcomes cannot clear a newer order or checkout attempt.
- [ ] Focused red/green regression, full Workshop client/demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.
- [ ] Independent review and required CI pass before integration.

The one-off baseline probe of the actual `checkOrder()` function with an expired response printed `{"currentOrder":"22222222-2222-4222-8222-222222222222","checkOrderHidden":false}`. Baseline Workshop Node and Go API suites passed before this change. This is local behavior evidence, not live payment or release acceptance.

Tracking: [Issue #377](https://github.com/lucronn/autodata/issues/377) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-terminal-order-status.md).
