# Workshop paid-order access pending

An owner-only order status can report `paid` before the Workshop client successfully reads that vehicle's article index. The existing client clears the Check payment status action on `paid` before that read and can show Buy again if the read returns `ENTITLEMENT_REQUIRED`. This bounded app correction keeps a no-repay pending state and the existing check action until access is confirmed.

Acceptance and verification:

- [ ] A paid order followed by `ENTITLEMENT_REQUIRED` does not expose Buy or start a new checkout; the owner can check status again.
- [ ] A later successful article-index read clears the order action and shows owned access.
- [ ] Other post-payment article errors retain the no-repay status action; expired, canceled, revoked, and still-processing order behavior remain intact.
- [ ] Focused red/green tests, full Workshop client/demo Node tests, Go API tests, syntax/diff checks, independent review, and required CI pass before integration.

These are local app safety tests, not live Stripe settlement, grant reconciliation, paid article access, or production-release acceptance. No production deployment or live payment is authorized.

Tracking: [Issue #383](https://github.com/lucronn/autodata/issues/383) under [paid Workshop Issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-paid-access-pending.md).
