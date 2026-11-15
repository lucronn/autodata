# Private read-only commerce verification

Issue https://github.com/lucronn/autodata/issues/414; Project https://github.com/users/lucronn/projects/8; plan docs/superpowers/plans/2026-11-14-private-read-only-commerce.md; architecture docs/architecture/workshop-private-read-only-commerce.md.

Status: planning only. Exact current-source isolated startup reproduced COMMERCE_CONFIGURATION_INVALID503 for legacy public stripe_test; no provider request or live service change.

Goal: Preserve private Workshop quote and entitled library/grant reads under explicit read_only composition while denying payment-capable operations and all provider I/O.

Concrete todo:

- [ ] Commit/synchronize the decision-complete plan, Issue414, Project8 and canonical docs; pass machine preflight at pinned planning SHA before implementation.
- [ ] Add red-first service/startup/HTTP and isolatedDB regressions for explicit merchant/livemode/price pins, allowed scoped reads, forced disabled purchase and zero-call blocked operations.
- [ ] Implement minimal read-only commerce composition with scoped read predicates and read-only DB transactions; deny checkout/webhook/order-status/reconciliation/demo at service and dispatch boundaries.
- [ ] Run focused/full ingestion/runtime startup checks and independent exact-head review/requiredCI before integration; retain separate fresh rollout gate before live config or service changes.

## Implementation checkpoint

Committed planning basef4c4350f8dcd6e3bdb03fdc3c9e6fedb23e8c1a8 passed machine preflight with synchronized/errors[]; Issue414 comment6886632842 and Project8 itemPVTI_lAHOCSJ8cc4BiQ2BzhIzXro readbacks matched before code.

Red-first actual-runtime-image unittest failed4 cases because ReadOnlyCommerceService was absent and configured_commerce rejected the new mode; invalid-pin and legacy public/test-refusal cases already passed. Host-only first attempt also lacked StripeSDK, so the authoritative red/green runs used pinned actual runtime image5c8e79b93db4, no network, application env keys scrubbed, test-only pytest imports mounted from existing runner.

Implementation adds explicit read_only composition with independent COMMERCE_READ_ONLY_MODE pin; local schema040/product validation; no Stripe client/secret/webhook or remote merchant probe. A small service subclass forces disabled purchase, has providerNone and rejects all payment/demo methods before arguments/I/O. HTTP auth remains first; allowed-path checks precede body decoding and dispatcher execution. Allowed reads preserve existing ownership/scope checks with exact read-only price filtering and DB READ ONLY transactions.

- Actual runtime-image relevant unittest:77passed.
- Complete isolatedPG commerce/newHTTP selected suite:45passed,49subtests before final additional startup/write-rejection coverage.
- Final new focused suite with PostgreSQL:9passed,36subtests; verifies test/live grant scope, wrongowner/org/configuration/region/merchant/mode/price rejection, revoked state, unchanged protected rows and actual UPDATE rejection under transaction_read_only.
- No provider/model/payment network request or serving configuration/service/database mutation was performed. Test stack uses only task-created internal PostgreSQL/SeaweedFS/NATS fixtures and deterministic fake transports.

Full unit suite, independent exact-head review, requiredCI and merge remain pending. Any live private read_only change requires a new merged-source rollout gate and retained writable rollback.
