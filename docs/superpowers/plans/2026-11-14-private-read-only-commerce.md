# Private read-only Workshop commerce

Goal: Preserve private Workshop quote and entitled library/grant reads under explicit read_only composition while denying payment-capable operations and all provider I/O.
Issue https://github.com/lucronn/autodata/issues/414
Project https://github.com/users/lucronn/projects/8
Architecture docs/architecture/workshop-private-read-only-commerce.md
Verification docs/verification/2026-11-14-private-read-only-commerce.md
Record docs/agents/records/2026-11-14-private-read-only-commerce.json
Implementation parent c115dcde11bee0ecc64052e8d51d15de7e572da9. Complements Go PR#412/Issue411.

## Contract and decisions

Current Python startup rejects stripe_test on the public production origin before starting HTTP. Completely disabled commerce removes existing paid grant/library reads. Add explicit outer AUTODATA_COMMERCE_MODE=read_only. Require AUTODATA_COMMERCE_READ_ONLY_MODE literally stripe_test or stripe_live to pin retained entitlement livemode independently of outer transport mode; require existing valid acct_/price_ identifiers and nonempty internal token. Validate existing environment/origin with current origin validator. Never initialize Stripe, read Stripe secret/webhook configuration, verify merchant remotely, or issue any provider request in this mode. These configured identifiers are operator pins, not independently reverified Stripe facts.

Add a small ReadOnlyCommerceService subclass of existing CommerceService, retaining CommerceConfig underlying pinned stripe mode and explicit read_only=True capability. Constructor always forces PurchaseConfig.disabled and provider=None. Reuse existing quote/library/grant methods and account/org/configuration/region/reviewer/product predicates. Add exact expected_price_id predicate for read-only grant/library reads, alongside existing configured merchant account and livemode; do not relax ordinary stripe paths. Read-only grant checks also validate the requested configuration scope through _scope. Mark every read-only service DB transaction READ ONLY before queries, and validate migration040/product locally at startup. No schema or entitlement change.

Explicitly reject checkout, webhook, order_status, reconcile_event, expiry reconciliation and demo_mode_status immediately with COMMERCE_UNAVAILABLE503 before argument processing, DB or provider work. Guard both direct service calls and private HTTP/dispatch. HTTP keeps internal-token authentication before any mode decision, then rejects all paths outside purchase-config/quote/library/grants-check before body decoding or dispatch; unknown operations failclosed. Public/private purchase config remains literal enabled:false even if purchase JSON is enabled/malformed. Allowed operations retain exact DTO validation and existing response formats; quote remains informational and cannot enable checkout. Go#412 independently enforces its own allowlist and local disabled config.

## Allowed implementation and tests

Only workers/ingestion-python/src/autodata_ingestion/commerce_service.py and http_service.py, new focused workers/ingestion-python/tests/test_commerce_read_only.py, and necessary focused additions to existing HTTP/commerce tests. Canonical docs/record/verification may update. No Go/UI/Stripe adapter/source connector/schema change. Do not alter live service/env or prepare deployable new-mode runtime until independent review, CI, merge and a separate synchronized rollout gate.

1. Write failing tests before code: public-production read_only startup with fixturemerchant/pinnedmode and no Stripe/DBwrites; missing/invalidpins fail503; existing stripe_test public refusal unchanged. Direct payment methods plus dispatch/actual authenticatedHTTP deny checkout/webhook/status/reconcile/demo/unknown operations before any provider/DB/handler call, including invalidbody; badtoken401 remains. Private purchase disabled irrespective enabledJSON.
2. IsolatedPG tests seed only synthetic existing settled grant/orders and verify correctaccount/org/configuration/region/merchant/livemode/price, revoked/wrongowner/wrongscope denial, library filtering, unchanged quote, and rollback/no writes. Assert transactionreadonly. Use existing internal fixture stack and task-only credentials/data; no live/provider/payment/model calls.
3. Implement smallest composition/guards preserving existing stripe_test/live behavior and existing merchant/scope checks. Preserve generic redacted errors.
4. Focused new tests, existing commerce/HTTP suites, full ingestion suite with meaningful skips reported, runtime-image public-origin startup smoke with no network, syntax/diff checks. Separate read-only exact-head review and requiredCI/protection before merge. No live configuration or deployment in implementation task.

## Concrete todo

- [ ] Commit/synchronize the decision-complete plan, Issue414, Project8 and canonical docs; pass machine preflight at pinned planning SHA before implementation.
- [ ] Add red-first service/startup/HTTP and isolatedDB regressions for explicit merchant/livemode/price pins, allowed scoped reads, forced disabled purchase and zero-call blocked operations.
- [ ] Implement minimal read-only commerce composition with scoped read predicates and read-only DB transactions; deny checkout/webhook/order-status/reconciliation/demo at service and dispatch boundaries.
- [ ] Run focused/full ingestion/runtime startup checks and independent exact-head review/requiredCI before integration; retain separate fresh rollout gate before live config or service changes.
