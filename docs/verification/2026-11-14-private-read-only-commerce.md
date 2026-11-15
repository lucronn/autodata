# Private read-only commerce verification

Issue https://github.com/lucronn/autodata/issues/414; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-private-read-only-commerce.md; architecture docs/architecture/workshop-private-read-only-commerce.md.

Status: planning only. Exact current-source isolated startup reproduced COMMERCE_CONFIGURATION_INVALID503 for legacy public stripe_test; no provider request or live service change.

Goal: Preserve private Workshop quote and entitled library/grant reads under explicit read_only composition while denying payment-capable operations and all provider I/O.

Concrete todo:

- [ ] Commit/synchronize the decision-complete plan, Issue414, Project8 and canonical docs; pass machine preflight at pinned planning SHA before implementation.
- [ ] Add red-first service/startup/HTTP and isolatedDB regressions for explicit merchant/livemode/price pins, allowed scoped reads, forced disabled purchase and zero-call blocked operations.
- [ ] Implement minimal read-only commerce composition with scoped read predicates and read-only DB transactions; deny checkout/webhook/order-status/reconciliation/demo at service and dispatch boundaries.
- [ ] Run focused/full ingestion/runtime startup checks and independent exact-head review/requiredCI before integration; retain separate fresh rollout gate before live config or service changes.
