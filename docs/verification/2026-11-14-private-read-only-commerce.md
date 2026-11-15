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

Coordinator review of99b1c619 found inherited quote purchasable:true was inaccurate in read_only mode. Plan/architecture/record amended before corrective code: preserve quote fields but set purchasable:false only for read_only, with direct and real privateHTTP regressions. Real subprocess read_only startup without Stripe keys now passes in isolatedPG; new suite10passed/36subtests before quote correction.

## Quote review correction and current validation

Quote amendment0b2460f576b7ef8511f8435f574b60b062015468 passed preflight and Issue414comment6886693949/Project8 readbacks matched before code. Added direct and real privateHTTP assertions failed3 cases red on purchasable:true. Minimal subclass override now preserves quote DTO/price/scope and returns purchasable:false. Actual private HTTP subprocess startup with production/public origin, isolatedDB and explicit read_only pins, no Stripe secret/webhook variables, passes health/purchase-config/quote.

After correction: focused new+existing commerce/PG/HTTP47passed,53subtests. Full ingestion unit suite before quote override:1205passed,477skipped,232subtests in132.46seconds. Prior actual-runtime-image unittest77passed and complete isolated catalog acceptance115passed/42subtests. No serving mutation or external provider/payment/model request.

Cross-PR deployment dependency: public Go quote validation in c115dcd rejects purchasable:false; Go#412 owner is implementing a mode-bound read_only allowance/public regression. No compatible public/private rollout until both changes are reviewed/merged with currentCI/protection and a new gate explicitly approves private mode plus source mount. Parent will merge#412 first; #417 must update base and rerun strictCI afterward.

## Protected-base integration checkpoint

Go PR#412 merged as exact master3a18d9c7ca51606a1dfb6d7691d3039d6d27c9f3. Concrete todo: synchronize this plan/Issue414/Project8/record before integration; merge that exact base without rewriting published history; retain Python implementation scope and truthful purchasable:false; rerun focused isolated commerce/runtime and public Go compatibility checks, requiredCI and independent exact-head review. Hold merge for coordinator. No live runtime mutation or SVG/image dependency change. Final private runtime gate remains separate and must pin the protected source before SVG#419.

## Updated protected Go base verification

Gate d01463a1e67e1e3fb595b1b0eec7af453732468b passed synchronized/errors[]; Issue414 comment6886925832 and Project8 readbacks matched. Merged exact protected3a18d9c7ca51606a1dfb6d7691d3039d6d27c9f3 without conflict at2e53453ad547aef528655e40fb11252e974d997c. Python source/tests are byte-identical to reviewed9a39f0971e3db1f1c2551f9813027f6d9c2fc41b; the Go read_only quote validator is now in ancestry.

After integration: isolated PostgreSQL/new+existing commerce/privateHTTP47passed,53subtests; network-disabled public Go tests matching ReadOnly|CommercePublic|Quote passed. Actual pinned image5c8e79b93db4 startup on production/public origin with internal fixtureDB, explicitread_only, noStripekeys/provider: health200, purchaseenabledfalse, providerNone, transaction_read_onlyon. Synthetic container9cfcb5486f9952a817cbc47b60e1a49bb5e2ab1f124a922071ae6b559db3c7a8 retained stopped; no serving changes. Initial rerun harness lacked/artifacts (46pass,1fail,2teardownerrors); initial manual startup probe usedGET on POST-only purchase endpoint404. Added fixture tmpfs and corrected request method, then both passed; no application code repair.

Diff whitespace check passed. RequiredCI and coordinator final exact-head review remain pending; no merge/deployment authority implied. Private runtime source/image/mode rollout still requires its separate synchronized gate and exact protected merge source, excluding SVG419 dependency changes.
