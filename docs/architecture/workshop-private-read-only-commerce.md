# Private Workshop read-only commerce

Goal: Preserve private Workshop quote and entitled library/grant reads under explicit read_only composition while denying payment-capable operations and all provider I/O.
Issue https://github.com/lucronn/autodata/issues/414; Project https://github.com/users/lucronn/projects/8. Plan docs/superpowers/plans/2026-11-14-private-read-only-commerce.md; Go counterpart PR412/Issue411.

Explicit outer read_only mode requires an independently pinned stripe_test/stripe_live entitlement mode, merchant account, price, internal token and valid origin/environment. Only purchase-config, quote, library and exact grants/check are exposed. Purchases always disabled; all payment-capable/demo/unknown paths reject before dispatch and service I/O. Existing internal authentication/DTO validation and scoped entitlement predicates remain; read-only reads additionally pin expected price and use DB READ ONLY transactions. No Stripe client/secret/remote merchant startup probe is used. Schema040/product startup reads are local.

This private mode and Go read_only are independent enforcement layers. Configured IDs do not prove current Stripe merchant verification or supplier rights. No grant creation, entitlement bypass, source data change, schema change or live rollout is part of implementation. A separately synchronized merged-source rollout must approve explicit mode pins, backup/protected-state baseline and retained runtime rollback.

Concrete todo:

- [x] Commit/synchronize the decision-complete plan, Issue414, Project8 and canonical docs; pass machine preflight at pinned planning SHA before implementation.
- [x] Add red-first service/startup/HTTP and isolatedDB regressions for explicit merchant/livemode/price pins, allowed scoped reads, forced disabled purchase and zero-call blocked operations.
- [x] Implement minimal read-only commerce composition with scoped read predicates and read-only DB transactions; deny checkout/webhook/order-status/reconciliation/demo at service and dispatch boundaries.
- [ ] Run focused/full ingestion/runtime startup checks and independent exact-head review/requiredCI before integration; retain separate fresh rollout gate before live config or service changes.

Read-only quotes retain product/scope/price data and explicitly set purchasable:false. Purchase config remains disabled. This capability boolean is preserved through the public Go transport. Review correction tracked on#414/#417 before integration.
