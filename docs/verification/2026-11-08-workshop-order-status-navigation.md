# Workshop order-status navigation

The Workshop's manual payment-status button belongs to a specific order. `checkOrder()` stores that ID and shows the button, but the navigation invalidation path cancels work without clearing either. A prior order can therefore leave a visible status action on a different vehicle or view.

The bounded correction clears the old order ID and hides its button when the customer leaves that order context. Active order polling and its manual retry remain unchanged until navigation, as do checkout, grants, and all server contracts.

Acceptance and verification:

- [x] Navigation invalidation clears the old order ID and hides “Check payment status”.
- [x] Active pending-order polling and manual retry behavior remain unchanged.
- [x] Focused red/green regression, full Workshop client and demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.
- [ ] Independent review and required CI pass before integration.

Local evidence: the new production-boundary regression failed before the app change (`#check-order.hidden` was `false`) and passed afterward. The real pending-order `checkOrder()` path and its button listener were not changed. The full Workshop client/demo Node suite, the Go API suite when run separately, JavaScript syntax, and `git diff --check` passed. An initial *concurrent* Node/Go run had five Node fixture failures because its strict DOM fixture omitted `#check-order`; the fixture now includes the production node. That concurrent run also exceeded a 3-second bound in `TestFirebaseADCCredentialRefreshHasIndependentTimeout`; a sequential full Go rerun and three isolated repeats passed. This is local test evidence, not live payment or release acceptance.

Tracking: [Issue #375](https://github.com/lucronn/autodata/issues/375) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-order-status-navigation.md).
