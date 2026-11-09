# Workshop paid-order access pending

An owner-only order status can report `paid` before the Workshop client successfully reads that vehicle's article index. The existing client clears the Check payment status action on `paid` before that read and can show Buy again if the read returns `ENTITLEMENT_REQUIRED`. This bounded app correction keeps a no-repay pending state and the existing check action until access is confirmed.

Acceptance and verification:

- [x] A paid order followed by `ENTITLEMENT_REQUIRED` does not expose Buy or start a new checkout; the owner can check status again.
- [x] A later successful article-index read clears the order action; the existing index response sets owned access.
- [x] Other post-payment article errors retain the no-repay status action; expired, canceled, revoked, and still-processing order behavior remain intact.
- [ ] Outer purchase/operation handling of a 410 article failure never invites a second purchase or exposes a no-op retry.
- [ ] A validated processing checkout order that becomes paid remains recoverable through focus/bootstrap without a second Buy invitation.
- [ ] Focused red/green tests, full Workshop client/demo Node tests, Go API tests, syntax/diff checks, independent review, and required CI pass before integration.

These are local app safety tests, not live Stripe settlement, grant reconciliation, paid article access, or production-release acceptance. No production deployment or live payment is authorized.

The baseline on merge `734640d3c1418928a1f45076cd4e54ad65bc807b` passed 216 Workshop Node tests and the full Go API suite. After test fixture correction, three focused regressions failed on the baseline client: the paid action was cleared before the article 404 result; the entitlement-required error escaped instead of retaining a paid-access state; and the pending state rendered generic checking or Buy copy. The first client candidate `dda39d9` passed those regressions and the paid/expired/canceled/revoked order controls (7 focused tests), then the full Workshop client/demo suite (218 tests) and Go API suite (latest `ok github.com/lucronn/autodata/apps/api-go 8.699s`). JavaScript syntax and diff checks passed. Independent review of that exact candidate found blocking outer-error and focus-recovery paths, so PR #384 remains unmerged. The additional integration regressions, repair, exact-head review, and CI disposition remain pending.

Tracking: [Issue #383](https://github.com/lucronn/autodata/issues/383) under [paid Workshop Issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-paid-access-pending.md).
