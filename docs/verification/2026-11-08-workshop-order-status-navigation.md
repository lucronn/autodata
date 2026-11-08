# Workshop order-status navigation

The Workshop's manual payment-status button belongs to a specific order. `checkOrder()` stores that ID and shows the button, but the navigation invalidation path cancels work without clearing either. A prior order can therefore leave a visible status action on a different vehicle or view.

The bounded correction clears the old order ID and hides its button when the customer leaves that order context. Active order polling and its manual retry remain unchanged until navigation, as do checkout, grants, and all server contracts.

Acceptance and verification:

- [ ] Navigation invalidation clears the old order ID and hides “Check payment status”.
- [ ] Active pending-order polling and manual retry behavior remain unchanged.
- [ ] Focused red/green regression, full Workshop client and demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.
- [ ] Independent review and required CI pass before integration.

Tracking: [Issue #375](https://github.com/lucronn/autodata/issues/375) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-order-status-navigation.md).
