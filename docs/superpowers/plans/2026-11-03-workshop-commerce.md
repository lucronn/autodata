# Workshop Orders, Stripe and Permanent Library Implementation Plan

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Status: implementation dispatched from synchronized checkpoint `3e9d06253bf747d69b21e4a8371daa742b0391f4` after verified R5 integration and passing exact-base preflight. The 39-path task and record define the authorized boundary. Concrete todo is in Verification and delivery checkpoints; historical planning notes below retain their original context.

Planning draft only. No implementation/gate expansion is authorized. Basis: committed `docs/architecture/workshop-commerce.md`, `docs/superpowers/plans/2026-11-03-workshop-firebase-identity.md` (official Firebase Admin v4.22.0), existing Python Stripe adapter/reconciler and Go ingestion seam. Original inspection root `322cdf131afc138faaa70be5f6791b85c6aac7ec`; production packaging/canonical-preparation revision reinspected actual objects at `521385fea0d0a57c92ba52cbb209a4dc79705c9a`. The Firebase identity plan is a coordinator-owned planned dependency, not asserted committed at521385f. Coordinator must re-pin after verified R3 and039 identity integration, independently review this bounded lane and synchronize canonical docs/task/Issue186/Project8 before exact-base preflight. Builder/reviewer gpt-6.1-sol, medium, Fast/priority, no fallback. Follow meaningful validated commit/push cadence on assigned owned branch; no live charging/cloud action in this lane.

## Fixed decisions

One authority: extend the existing PRIVATE Python ingestion HTTP service with commerce handlers; retain StripePaymentProvider and payment_reconciliation as its payment/fulfillment authority. Go owns public same-origin routes and verified customer session/CSRF; it delegates commerce operations, never creates a second fulfillment ledger or separate commerce deployment. Existing ingestion commands remain intact.

SKU `workshop-configuration-v1`: server-resolved canonical configuration UUID plus region, USD2000 minor units, one-time, quantity1, immediate card only, automatic capture. No coupon/promotion code, automatic tax, shipping, optional subscription, delayed method or browser-priced line item. Store a versioned product row using existing dataset_products; initial price includes the published charge, with applicable tax/legal applicability requiring owner confirmation before live launch. Never assert an unconfigured merchant is ready. Both-bank eligible articles join through existing verified configuration mapping; no title/fuzzy/provider-ID merge. Permanent grant has no normal expiry and survives session/device/redeployment/content retry. It cannot override source withdrawal or an explicit audited refund/revocation.

## API and trusted service seam

Public Go routes, with bounded JSON and no-store: UUID values are canonical UUID strings; region is an uppercase two-letter code matching the resolved configuration; unknown request fields are rejected. Order/library IDs are opaque UUIDs, times RFC3339 UTC, price integer minor units and error envelopes use existing safe API codes/request IDs.

- `GET /v1/workshop/quote?configuration_id=<uuid>&region=<code>`: public safe DB-only quote, no provider fetch/model/detail.200 `{version:"v1",product_key:"workshop-configuration-v1",configuration_id,region,configuration_label,amount_minor:2000,currency:"USD",purchase_terms_version:"workshop-v1",purchasable:true}`. Resolve existing active/nonrejected configuration and its actual region; invalid/mismatched scope404. No article/body/source/private processing or upstream key. A quote does not reserve a mutable browser price; checkout revalidates server product.
- `POST /v1/workshop/checkout-sessions`: customer session, exact-origin+CSRF and `Idempotency-Key` UUID required. JSON exactly `{configuration_id,region,terms_version:"workshop-v1"}`. Server derives account/personal org; no owner/product/price/status accepted from browser.201 newly confirmed session,200 reused/owned,202 unresolved creation/payment with Retry-After2. Response discriminant `state: checkout|processing|owned`; order_id, configuration_id,region; checkout_url/provider_expires_at only in checkout; library_item_id only in owned. Fixed checkout URL must be provider HTTPS hosted URL from validated SDK response, never caller-controlled redirect. Existing revoked scope403 ENTITLEMENT_REVOKED; mismatched idempotency request409 IDEMPOTENCY_CONFLICT.
- `GET /v1/workshop/orders/{order_id}`: owner-only session; unknown/other owner404. Return exactly `{version:"v1",order_id,configuration_id,region,state,retry_disposition}`. State is creating,open,processing,paid,expired,canceled,reconciliation_required or revoked; retry_disposition is `new_key` only for expired/canceled, otherwise `do_not_repay`. No retryable boolean or library ID is added to this DTO; no purchaser/provider IDs, secrets or payload. Do not mutate financial state through an unverified success parameter. Lookup may request bounded provider reconciliation outside DB transactions; network failure preserves pending and returns safe retryable503.
- `GET /v1/workshop/library?cursor=<opaque>&limit=<1..50>`: owner-only session. Stable account-scoped keyset pagination, default20. Return `{version:"v1",items:[{library_item_id,configuration_id,region,label,access_state:"paid|preparing|viewable|revoked",granted_at,revoked_at?,dataset_id?,content_error_code?}],next_cursor}`. library_item_id is order UUID; no expiry field/no promised fixed snapshot. paid means durable grant but no materialization dispatched; preparing means pending/running or retryable preparation failure; viewable means at least one eligible shared source/canonical article has readable current content under the exact scope/current-rights readiness query below; it does not promise all articles complete or require a legacy dataset snapshot; revoked tombstone remains visible. A verified full refund can create a revoked order before any entitlement was granted; include that owner-visible tombstone using an order-led left join. `granted_at` is JSON null only for a revoked order that was never granted; all granted items carry the actual RFC3339 grant time. Never fabricate a grant time or omit the refund tombstone. No invented percentage/completeness. No session token, email, Stripe IDs or private source URI. Other-account cursor is invalid400; never leak another owner's counts.
- `POST /v1/payments/stripe/webhook`: no customer session/CSRF; bounded raw bytes1MiB, bounded Stripe-Signature header4KiB, POST only. Forward unchanged bytes and that signature to the authenticated private handler. Signature verification/settlement authority is Python, not Go. Invalid signature/body400, accepted/duplicate/verified unsupported type200 with `{status}` where the value is accepted, pending, quarantined or ignored; DB/provider dependency unavailable503 so Stripe retries. Do not log body/signature/secret, redirect or silently accept truncated bytes. No CORS or account header is trusted.

Private POST routes `/internal/commerce/quote`, `/internal/commerce/checkouts`, `/internal/commerce/orders/status`, `/internal/commerce/library`, `/internal/commerce/grants/check` use JSON. `/internal/commerce/stripe/webhook` consumes raw bytes BEFORE generic JSON parsing. Require nonempty secret-managed internal token unconditionally on every commerce route, constant-time comparison; missing configured token disables commerce startup/readiness. Ingestion's optional local token behavior is not a commerce bypass. Same existing listener, private network, no new public port. Go HTTPCommerceClient uses explicit safe constructed account/org JSON from Principal; never forwards incoming X-Autodata-Owner-Id/Organization-Id, bearer/cookie or arbitrary headers. Preserve only sanitized request correlation plus server-configured internal authentication and bounded Stripe signature for webhook. Python rechecks account active and account→personal-org mapping before owner operations. Quote/webhook still require internal authentication at this boundary.

Grant-check contract for next access lane: `CheckVehicleGrant(ctx, customer_account_id, organization_id, configuration_id, region) -> {entitlement_id,order_id,configuration_id,region}` or typed `required|revoked|unavailable`. Go passes only the current verified Principal account and organization; Python rechecks that exact active owner pair. Internal grants/check performs one current DB read of active account + exact structured active entitlement and returns no body/content. Missing/adjacent/legacy-unscoped grant is required; revoked tombstone is revoked; DB/transport error unavailable. Next Go access lane MUST call it before catalog detail/source/media/protected progress hydration/model/S3, then separately enforce existing current source rights. Current customer dataset_viewer role alone is never a paid grant. This lane does not edit catalog/media enforcement; release cannot complete until that separate lane is integrated.

Timeouts: private read/quote/library/grant checks2s total; checkout/status provider operations20s total at Go/private boundary, with each Stripe call<=8s, no SDK automatic retries and at most two calls per request. Longer reconciliation resumes via the existing background process. Webhook persistence/verification has20s total; defer/retry provider-dependent resolution rather than exceed deadline. DB transaction/lock timeout3s; no external API call while holding a row/advisory transaction lock. Sanitize all dependency errors.

## Migration040: exact additive storage contract

`db/migrations/040_workshop_commerce.sql`, self-contained BEGIN/body/own040 marker/COMMIT after039. Historical SQL001–039 immutable. Create exactly two commerce tables, extending existing entitlements/products/events rather than adding another grant ledger:

1. `workshop_orders`: order_id UUID PK; customer_account_id FK; organization_id UUID; configuration_id FK vehicle_configurations; region nonempty normalized uppercase text matching resolved identity; dataset_product_id FK; terms_version fixed nonempty text; amount_minor bigint CHECK=2000; currency char(3) CHECK='USD'; stripe_account_id nonempty; livemode boolean; expected_price_id nonempty; provider_idempotency_key nonempty UNIQUE (server-derived `workshop:checkout:<order_uuid>:v1`); status enum-check `creating|open|processing|paid|expired|canceled|reconciliation_required|revoked`; checkout_session_id nullable UNIQUE; payment_intent_id nullable UNIQUE; provider_expires_at nullable; first_create_attempt_at; last_reconciled_at; dataset_request_id nullable UNIQUE FK; entitlement_id nullable UNIQUE FK; created_at/updated_at/paid_at/revoked_at; revocation_reason_code nullable check `full_refund|chargeback_lost|administrative`. Immutable financial/scope fields after creation enforced in store transitions and tests. Never store card data, raw webhook, credentials or checkout client secret. A returned checkout URL may be stored server-side only until expiry; no evidence/log copy.
2. `workshop_checkout_requests`: customer_account_id FK + client_idempotency_key UUID composite PK; canonical_request_sha256 bytea32; order_id FK; created_at. This maps all concurrent client request keys to the single owned order, including different keys that reused it. Same key with changed normalized body/terms409. No TTL that silently lets a recent replay create a new order.

Add to existing entitlements nullable `customer_account_id` FK, `configuration_id` FK, `region`, `commerce_order_id` UNIQUE FK workshop_orders. Legacy rows keep all four NULL; CHECK all-null or all-present. Add partial unique active-grant index(customer_account_id,configuration_id,region) WHERE status='active' AND customer_account_id IS NOT NULL. New order/customer entitlement organization must equal customer_accounts.personal_organization_id: add unique(customer_account_id,personal_organization_id) on039's account table and composite owner FKs using corresponding account/org columns. The forward040 constraint does not change039 SQL bytes. New grants always have full structured scope; never promote arbitrary legacy vehicle_key strings into paid ownership.

Orders have partial unique live-slot index(account,configuration,region) WHERE status IN(creating,open,processing,paid,reconciliation_required). Revoked scope remains repurchase-blocked until separate explicit administrative resolution; no self-service repurchase/refund loop. Enforce account+scope serialization via a deterministic transaction-level advisory lock, then re-read grant/current order before insertion; collisions may serialize extra work but cannot grant wrong scope. Use the same lock ordering everywhere (scope then order then entitlement) and unique constraints as the final race guard. Events remain in existing payment_events with unique provider_event_id and safe normalized payload; persist provider session/payment/order association in order row, not a parallel payments ledger.

Seed/upsert the exact versioned product through migration040 with amount2000/currencyUSD and selector declaring configuration+region scope; do not seed merchant-specific price IDs/secrets. Expect one configured immutable Stripe price mapping for this product version. Product mismatch/inactive state denies new checkout.

Runtime configuration: `AUTODATA_COMMERCE_MODE=disabled|stripe_test|stripe_live` is explicit; no automatic live switch. Python alone receives secret-manager `AUTODATA_STRIPE_SECRET_KEY` and `AUTODATA_STRIPE_WEBHOOK_SECRET`; both services receive expected `AUTODATA_STRIPE_ACCOUNT_ID` and immutable `AUTODATA_STRIPE_PRICE_ID` as needed, with the existing internal-service secret. Enabled mode missing any required Python secret/merchant/price/internal token fails commerce readiness; disabled routes return sanitized503. Test/live deployments use isolated databases. All order/owned/library/grant queries bind the configured mode and merchant through the order row; a test-mode order/event is never a live grant. Refuse enabled startup on an existing commerce database containing another mode/merchant rather than silently adopting it.

### Server-owned checkout return origin

The Workshop composition reads only server configuration `AUTODATA_ENV` and `AUTODATA_PUBLIC_ORIGIN`, matching the Go identity service. Reject missing/unknown environment; accept only development, test, staging or production. Production requires exactly `https://cars.tk`; staging and development require an explicit HTTPS origin. Preserve the existing identity/Compose CI test-only exception: test mode may use HTTP only for localhost or a parsed loopback IP. Every origin needs a hostname and no user information, path, query, fragment or opaque URL; reject malformed ports/URLs. Validate configuration before constructing the Workshop payment provider, preserving the neutral adapter’s existing explicit injected-URL contract. Both success and cancel URLs are exactly `<validated-origin>/workshop/?order=<stored-order-UUID>`; no disposition/status parameter is required and the browser always resolves owner-only server status. No client return URL, request Host, Origin or forwarding header selects the destination. The approved runtime manifests supply the same explicit environment/origin to both services; no new file is authorized. Controlled tests may inject fixture URLs through explicit test dependencies, never a production bypass. This correction enables isolated HTTPS staging without redirecting its customers to the live site; it changes no price, account, financial validation or grant rules.

### Reviewed Stripe URL and pre-payment validation corrections

The official Checkout Session object documentation includes hosted URLs with an
opaque fragment. Preserve that provider-returned fragment verbatim. Require HTTPS,
exact hostname checkout.stripe.com, a supported nonempty `/c/pay/` path, and no
userinfo, explicit port, whitespace or control characters. Do not invent a required
fragment prefix, strip/reconstruct provider URL components, or accept client URLs.
This allowance applies to the provider's hosted Checkout URL; configured app
return origins still forbid fragments and query strings.

Before enabled commerce readiness, retrieve the configured merchant and actual
Stripe Price using the pinned official SDK. Require the exact configured active,
one-time Price with integer unit_amount2000 and currencyUSD, matching test/live
mode; reject recurring, variable/tiered/custom-unit or incompatible prices.
Startup can perform these bounded calls outside transactions. Validate the created
Checkout Session's mode, amount_total and currency before returning its URL,
alongside identity/metadata/mode and stored financial scope. A settlement-time
quarantine cannot repair a wrong amount already charged. Extend existing adapter,
configuration and checkout regressions within the39 paths; no live call is required.

No dataset request is created for an unpaid order. On verified settlement, create the existing dataset_request with server org, structured scope-derived vehicle_key/region and status purchased, then grant/projection in the same DB transaction. This avoids lying with purchased status before payment and avoids a new generic unpaid request status. Materialization may remain unavailable: payment/grant commit survives that condition. Commit the explicit canonical-index preparation intent on the order in the same settlement transaction; the separately specified order scanner below advances it, without relying on the legacy dataset.fast.requested/source-URI branch. Recheck the immutable resolved scope/product identity and expected financial terms before grant. Later account blocking, source withdrawal or content unavailability does not erase a valid settled payment: retain the paid ownership record and let separate current-account/source-rights enforcement deny content where required. Do not turn a post-checkout source outage into payment failure or an extra charge.

Append exact040 to shell canonical manifest/Python static expectation and append040 at all FOUR already039-inclusive complete-transaction case sites. Add both new tables to known-table baseline rejection. Preserve advisory migration lock(186,3738),033 behavior,039 account/session schema and historical prefixes. Update current-head tests/real-PG upgrade039→040/full replay/rollback/concurrency while retaining explicit historical038/039 cases. R3 bridge's current-head assertion/evidence keys become exact001_040; coordinator separately updates/reviews scratch validators for040 without altering earlier acceptance records.

## Checkout and stale-session state machine

1. In short transaction: validate active account/terms/product/normalized scope; acquire account-scope lock; insert/check client idempotency mapping; return owned if active grant. Reuse current creating/open/processing/reconciliation_required order for any new key. If none, reserve exactly one creating order with immutable expected merchant/environment/price and provider key; commit before Stripe call.
2. Stripe create uses that same server key and identical stored parameters on every retry: mode payment, card only, automatic capture, quantity1, expected configured Price ID, fixed `/workshop/` success/cancel paths beneath the validated server-configured public origin with opaque local order ID, expires_at one hour, metadata order ID on Checkout Session AND payment_intent_data. Include no browser-selected account/price/return location. Store response under order lock, validating returned identity/URL/expiry. A webhook may settle first; response persistence must not downgrade paid/revoked or mint another order.
3. Lost create response retries the same provider key/parameters only within23hours of first_create_attempt_at (below Stripe's minimum24h idempotency retention). After that, uncertainty becomes reconciliation_required; never reuse a potentially pruned key to create another session. Matching signed webhook/session reconciliation can resolve it; otherwise require audited operator reconciliation, not another charge. No optimistic local timeout makes a new order safe.
4. Local/provider expires_at does not release the slot by itself. Before replacement, retrieve the old session from the configured merchant/environment. Complete+paid settles old order. Open old session must be explicitly expired; verify expired/canceled state. If it has a payment intent, require canceled/no-intent before replacement; cancellable unconfirmed intent is explicitly canceled then rechecked, processing/succeeded/uncertain intent blocks replacement and is reconciled. Provider failure preserves the old slot. Multiple bounded requests/background iterations may be needed; never exceed per-request call budget.
5. Only a confirmed nonchargeable old order transitions expired/canceled and releases the slot. A new client key may then reserve a fresh order. A replay of the old client key returns that old order/disposition, never a fresh checkout. Same-key altered body409. Existing paid grant always returns owned with no Stripe call, even if a stale open-order response arrives.

## Authoritative settlement and revocation

Extend StripePaymentProvider rather than duplicating it. Official SDK verifies raw signature with300-second signing-timestamp tolerance; retries are replay-safe through the event ledger and old event.created alone is not rejected; supported events normalize to typed trusted facts including provider event ID/type/time, order ID, session ID, payment-intent ID, merchant/environment, mode/status, amount_total/currency and expected price/quantity. Retrieve authoritative session/line-items/intent as needed under configured merchant credentials; missing facts are unresolved, never trusted metadata. Expect livemode to equal server mode, merchant binding to match configured account, price ID/quantity1, USD2000, paid=true/settled automatic card payment, and event/session/intent/order associations to match. No Stripe Connect or alternate accounts in this lane. Verify configured SDK account at runtime composition/staging; do not assume signature alone proves all financial facts.

Verified unsupported event types return ignored200 without a grant. Bad signature400; supported but transiently unresolved state is durably pending and acknowledged only after commit; database failure503. Signed permanent invariant conflict is durably failed/quarantined with sanitized reason and200, with operational alert; do not endlessly retry a provably wrong price/owner event or grant it. Normalization retains only safe required facts, not raw Stripe customer/card payload. Freeze the canonical signed-event fields once; keep later mutable session/charge retrieval observations on the order/reconciliation outcome, outside the immutable event replay payload, so the same signed event cannot conflict merely because provider state advanced. Current PaymentIntent defaults fake/provider metadata handling must not be reachable as production proof: legacy fake smoke branch remains explicit fixture-only.

Under account-scope/order lock, compare replay payload with stored canonical facts, check owner/account→org plus immutable order scope/product/financial facts, create request+existing entitlement+projection once, set order paid and record event. Reuse existing reconcile_payment_event durable pending/fulfilled/conflict and outbox mechanisms, extending its order-aware branch; do not trust its old purchaser_id metadata path for public checkout. Deterministic request IDs derive from order; event retries and distinct legitimate provider events for the same session cannot duplicate grants. Canonical preparation failure is retryable through the durable order scanner below; a missing legacy source snapshot cannot leave payment fulfillment pending, roll back a settled durable grant or cause a fresh charge. Set the commerce payment event fulfilled once its paid grant/projection/preparation intent commit; the preparation scanner reads orders independently of pending payment events.

Handle signed `charge.refunded` only as full refund when authoritative amount_refunded equals the full2000 and charge is fully refunded; partial refund records an audit/pending-support outcome and retains access. Handle `charge.dispute.closed` status lost for the full2000 as confirmed chargeback revocation. Dispute-open/partial/won events do not silently revoke or restore. Resolve these through exact payment-intent/order association (including intent metadata for early events), revalidate merchant/mode, and call existing auditable revoke_entitlement within the order transaction. Revoked order/grant is monotonic; late completed/paid events cannot reactivate it. Out-of-order full refund/lost-chargeback first establishes the order's revoked financial tombstone, then later settlement records facts without granting active access. Library shows revoked; no normal expiry. Restoration/repurchase requires a separately authorized audited administrative action, not a webhook or login reset.

Public terms version workshop-v1 must say one-time configuration+region access, no normal renewal/expiry, permanent account ownership subject to source rights and full refund/confirmed full lost chargeback or explicit audited administrative revocation. Owner must publish actual refund/contact/legal terms before live charging. No unsupported refund entitlement promise is inferred.

## Exact bounded files

Create:

```text
apps/api-go/commerce.go
apps/api-go/commerce_http.go
apps/api-go/commerce_http_test.go
apps/api-go/commerce_client.go
apps/api-go/commerce_client_test.go
workers/ingestion-python/src/autodata_ingestion/commerce_service.py
workers/ingestion-python/tests/test_commerce_service.py
workers/ingestion-python/tests/test_commerce_postgres.py
db/migrations/040_workshop_commerce.sql
scripts/dev/workshop_commerce_smoke.py
scripts/dev/test_workshop_commerce_smoke.py
docs/verification/workshop-commerce-runbook.md
```

Modify:

```text
apps/api-go/main.go
apps/api-go/openapi.json
apps/api-go/openapi.yaml
workers/ingestion-python/src/autodata_ingestion/http_service.py
workers/ingestion-python/src/autodata_ingestion/stripe_adapter.py
workers/ingestion-python/src/autodata_ingestion/payment_reconciliation.py
workers/ingestion-python/tests/test_http_service.py
workers/ingestion-python/tests/test_stripe_adapter.py
workers/ingestion-python/tests/test_payment_reconciliation.py
workers/ingestion-python/tests/test_article_lifecycle_migrations.py
workers/ingestion-python/tests/test_catalog_api_integration.py
workers/ingestion-python/pyproject.toml
workers/ingestion-python/Dockerfile
packages/contracts/python/autodata_contracts/payment.py
scripts/dev/reconcile_payments.py
scripts/dev/payment_reconciliation_smoke.py
scripts/dev/production_access_smoke.py
scripts/dev/migrate_sql.sh
scripts/dev/test_migrations.py
scripts/dev/test_api_runtime.py
scripts/dev/test_k8s_manifests.py
infra/compose/compose.yaml
infra/compose/compose.ci.yaml
docker-compose.base44.yml
infra/k8s/base.yaml
docs/operations/migration-runner.md
docs/architecture/workshop-interface.md
```

39 paths. Pin `stripe==16.1.0` in pyproject.toml; official PyPI metadata reports non-yanked, Python>=3.9, compatible with the existing Python3.14 images. Verified wheel `stripe-16.1.0-py3-none-any.whl` SHA256 `3798e07a0603c8923710414cd1942ae847ed43cebbf34c3258417c189711ea70`; metadata/wheel API evidence retained in `/tmp/autodata-workshop-stripe-sdk-evidence.json`. Public metadata source https://pypi.org/pypi/stripe/16.1.0/json ; official project https://github.com/stripe/stripe-python . No package installation or merchant call was performed.

Production `workers/ingestion-python/Dockerfile` currently ignores the copied pyproject for dependency installation and hardcodes a package list lacking Stripe. Replace only that dependency-install step with the same Python tomllib project.dependencies-driven pip install approach already used by the fixture image. Both images must therefore install the same exact stripe16.1.0 pin; keep production source/script copies/runtime unchanged. No interactive deployment install or new image/service; no fixture Dockerfile/support-file rewrite.

Freeze the inspected SDK shape: `stripe.StripeClient(api_key, max_network_retries=0, http_client=stripe.RequestsClient(timeout=8))`; `client.v1.checkout.sessions.create(params, options={"idempotency_key": stored_key})`, `.retrieve(session_id, params={...})`, `.expire(session_id)`, `client.v1.payment_intents.retrieve/cancel`, and `client.v1.accounts.retrieve_current()` for the credentials-owning merchant. Compare retrieve_current().id with configured expected account before enabling commerce readiness; do not set a Stripe-Account Connect override or merely retrieve an arbitrary configured account ID. Verification uses `stripe.Webhook.construct_event(raw_bytes, signature, configured_secret, tolerance=300)`. Update adapter fakes to this actual v1 params/options API, retaining the existing neutral adapter boundary; old SDK kwargs are not presumed supported. The installed SDK requires requests>=2.20 and typing_extensions>=4.7 through normal metadata resolution; do not confuse those transitive ranges with the exact Stripe pin. Existing fake adapter signatures retain optional/new argument compatibility or are adapted in explicit fixture-owned smoke above without enabling fake production mode; if existing contracts/fakes.py actually needs a changed signature, stop for a separately reviewed exact one-path amendment rather than silently widening. No Workshop UI, catalog/source/media policy implementation, identity039 SQL edit, or repository autonomy/supervisor edit in this lane. Canonical commerce/task/tracking planning synchronization is coordinator-owned checkpoint work separate from this builder list.

## Explicit durable canonical preparation and honest readiness

Selected mechanism: the existing payment-reconciler process advances paid orders into durable SHARED catalog-index preparation. Article-body/rewrite work remains on demand in the later grant-checked reader lane. This is deliberate bounded index preparation, not a promise to materialize every paid article eagerly or a hidden dependency on legacy dataset/source snapshots.

Add order columns in040: preparation_state CHECK pending/index_queued/index_ready/retry/blocked; preparation_attempts nonnegative default0; preparation_next_attempt_at defaultnow(); preparation_lease_owner UUID nullable; preparation_lease_expires_at nullable; preparation_index_job_ids UUID[] default empty; preparation_last_error_code nullable fixed safe code. At settlement set pending/next_attempt now atomically with paid ownership. Do not create a second preparation table or a per-customer canonical article. Revocation stops that order's scanner participation; it does not cancel shared jobs serving other customers.

`scripts/dev/reconcile_payments.py` retains financial-event reconciliation and then calls a new `commerce_service.reconcile_workshop_preparation(connection, limit=10)` each existing polling cycle. It claims due paid orders under SKIP LOCKED with a30-second lease, commits the claim, and only then performs catalog scheduling outside financial/claim transactions. Crash/lease expiry makes the intent claimable again. On scheduling failure persist retry with15,30,60…900-second capped backoff and a safe code, preserving active grant/paid status. Successful pending index state is observed every15seconds; index_ready is a durable acknowledgement and need not be rescanned forever, although library readiness reads current shared state. No provider/model network call occurs in the scanner itself. All actual source/index/rewrite workers retain their existing retry machinery.

Call the ACTUAL `catalog_service.ensure_catalog_hydration(json.dumps({"scope":"articles","vehicle_id":str(configuration_id),"vehicle_configuration_id":str(configuration_id),"idempotency_key":"workshop-index:<configuration_uuid>:<region>:v1"}))`. Public function routes articles to bounded `_ensure_lifecycle_catalog`, which proves configuration/vehicle identity and calls `catalog_coverage.ensure_article_catalog_jobs(repo, vehicle_id=<resolved vehicle>, vehicle_configuration_id=<exact configuration>)`. It commits/reuses the two provider scope/index jobs in PostgreSQL under existing identities. Persist returned exact job IDs and acknowledgement state after rechecking the order/lease; a crash after ensure but before acknowledgement retries the same real ensure and reuses its durable jobs. No legacy source_uri, source_snapshot, file fixture, fabricated provider reference or dataset.fast.requested event is used to schedule this commerce branch. Source-URI legacy reconciliation remains for existing explicit fixtures/legacy products, not the Workshop SKU.

Library readiness authority is a DB query in commerce_service over exact configuration+region, canonical_articles/current catalog_article_current, catalog_article_provider_scopes/source_fetch_jobs and the existing current-rights predicates. Require membership active, configuration/identity not rejected, active descriptor/body/resource rights and no unapproved quarantine of the corresponding snapshots (same association checks as R3 lifecycleEligibleSQL, not globally shared content hash as access authority). `viewable` requires at least one exact-scope eligible current row with availability=available and nonempty readable document blocks, whether content_origin is source or canonical. Merely having a dataset_projection, completed index, acknowledged job or paid event is insufficient. It is a safe readiness hint; the later protected read revalidates full grant/current rights. Do not expose private IDs/status to public quote.

Map the existing library states deterministically: revoked order/grant→revoked; eligible readable source/canonical row→viewable; pending index or actual exact-scope active/retryable article job→preparing; otherwise durable paid ownership→paid, with fixed safe content_error_code for retry/needs-review/unavailable as appropriate. In particular, an index_ready scope with no requested article body returns paid and can be opened; do not spin indefinitely claiming a rewrite is running. Readiness regression/source withdrawal does not delete the grant. Existing content from another customer's prior preparation is immediately reused through the same canonical identity, without a second rewrite/payment.

Later paid-reader lane is explicitly responsible for `CheckVehicleGrant` BEFORE article ensure, then actual `catalog_service.ensure_catalog_hydration` with scope=article, the proven configuration IDs and exact verified canonical_article_id. That existing path calls `source_job_persistence.ensure_article_job` using the article's stored target normalization/rewrite versions. It cannot substitute an adjacent/family ID or title match. Its required acceptance must prove grant-before-ensure, real durable article acknowledgement, source-readable-while-rewriting and reuse across two entitled customers. This commerce lane does NOT claim that deferred article-body work has already executed.

Strengthen existing `test_payment_survives_source_unavailable_and_restart` (no fifteenth test): seed a valid canonical configuration with NO legacy source snapshot or HTTP/file URI, settle exactly once and prove active durable grant/order intent even if catalog scheduler DB availability initially fails. Restart a fresh scanner instance after lease/retry state, recover controlled local DB scheduling, call the real catalog ensure functions and observe committed/reused bankone+banktwo catalog-index jobs and saved acknowledgement. Repeat scanner/crash-after-ensure recovery and a second customer's same-scope purchase; job IDs are shared, no duplicate customer rewrite. With no article requested/readable yet assert index_ready plus honest library paid, not fabricated viewable/completed. Optionally drive the existing local lifecycle fixture's real article workers to readable source to check the query changes to viewable; if deferred, the later reader lane MUST execute that part before launch. In all cases assert one checkout/settlement/grant per owner and no dependency on legacy dataset.fast.requested. Model an actual scheduler/connection failure using controlled repository availability and real PG recovery, not a mocked legacy event advertised as canonical completion.

## Production packaging verification

Extend already scoped test_api_runtime.py to assert production and fixture dependency installation consume project.dependencies and retain exact stripe pin; unit adapter tests exercise the installed official SDK constructor/params/options and injected local transport. Separately build the actual production ingestion Dockerfile at the reviewed candidate in release verification and run a no-secret/no-network import/version probe (`importlib.metadata.version("stripe") == "16.1.0"`, import stripe and existing service/reconciler). Record production image ID and installed package/version proof independently from the fixture image. No Docker build was run in this planning revision. Fixture-only package availability cannot satisfy release packaging acceptance; no credential or live charge is needed for this probe.

## Frozen commerce PostgreSQL test inventory

In `workers/ingestion-python/tests/test_commerce_postgres.py`, required mode uses the existing `fresh_database` fixture and executes these exact fourteen unparameterized pytest roots; each may exercise its stated positive/negative transitions internally. Collector requires the complete exact set, not fourteen arbitrary passing names:

```text
test_orders_create_and_owner_scope
test_same_key_replay_and_conflict
test_concurrent_keys_share_one_checkout
test_scope_races_single_active_grant
test_lost_create_response_and_retention_boundary
test_expiry_requires_remote_nonchargeable_proof
test_completion_races_expiry_without_recharge
test_webhook_before_create_response
test_settlement_binds_financial_owner_scope
test_duplicate_and_distinct_events_grant_once
test_refund_chargeback_ordering_and_monotonic_revocation
test_payment_survives_source_unavailable_and_restart
test_library_is_owner_only_and_paginated
test_grant_check_exact_scope_legacy_and_revoked
```

Set `AUTODATA_LIFECYCLE_TEST=1` and `AUTODATA_REQUIRE_COMMERCE_INTEGRATION=1` before collection; missing fixture/services in required mode fail. Collector child command:

```text
python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/workshop-commerce-tests.xml scripts/dev/test_migrations.py workers/ingestion-python/tests/test_article_lifecycle_migrations.py workers/ingestion-python/tests/test_commerce_postgres.py
```

Use real PostgreSQL transactions/pools and actual threaded private/public HTTP where HTTP boundaries are asserted, with deterministic in-process Stripe transport. Injected provider idempotency must model one remote session for identical keys even when multiple SDK create calls race; do not incorrectly require zero retry network calls. No source/model/provider network dependency or sleeps as concurrency proof; use barriers and actual committed competing transactions. Source-readiness failure is a controlled local fixture, not a bank request.

## Verification and delivery checkpoints

- [ ] Freeze product/order/terms/route/error/datatype/financial transition contracts, SDK pin, exact39 paths, migration040 and dependency on verified039. Independently review, synchronize Issue186/Project8/canonical docs/task; commit/re-pin and require machine preflight before code.
- [ ] Add failing injected-SDK adapter and private/public HTTP tests: raw signature bytes unchanged, no customer/header price authority, mandatory internal auth, owner-only library/status, CSRF/origin, bounded bodies/timeouts, safe ignored types/errors, price/mode/account/session/owner conflicts. Implement authority/service routes and public Go delegation until passing.
- [ ] Real PostgreSQL no-skip tests under existing lifecycle fixture:40 bootstrap/039 upgrade/replay/rollback; concurrent same/different client keys and account-scope lock/unique guards; lost provider response/key retention boundary; old session completion vs expiry/replacement; webhook before create response; duplicate/distinct/out-of-order events; full refund/chargeback before/after settlement; two-customer isolation; grant persists through content unavailability/restart and no extra provider create after ownership; strict active-grant check for adjacent and legacy-unscoped access. Stripe network is an injected official-client/local-transport seam; no live charge.
- [ ] Collector `python scripts/dev/workshop_commerce_smoke.py --mode fixture --candidate-sha <exact40hex> --output /artifacts/workshop-commerce.json` runs developer migration checks plus test_article_lifecycle_migrations.py and test_commerce_postgres.py in required fixture mode. Require measured040, explicit exact test inventory/nonzero count/zero skips and candidate/input/host/runner provenance under the reviewed R3-owned fixture/supervisor protocol; require the exact fourteen commerce IDs below plus the complete separately enumerated migration module inventory, not an arbitrary “tests passed” string. Preserve five identity PG cases and eight R3 content regressions with040-aware validators separately. Go tests and Python unit/contracts/runtime/manifest checks plus diff --check; no narrowed assertion or ignored skipped DB test substitutes.
- [ ] Independent exact-SHA security/replay/account/scope review, then validated coherent commits/pushes on owned branch. Deliver public DTOs, private grant-check/error contract and deployment secret names to paid-access/UI lanes. No production launch claim until their integration and separate live acceptance.

External configuration later: actual Stripe merchant/account and supported-country onboarding, official SDK pin, test-mode key/webhook signing secret, immutable USD20 one-time Price ID, validated server-origin success/cancel URLs (production cars.tk; explicit HTTPS staging), webhook event subscription, live-mode equivalents through secret manager, actual refund/contact/tax terms and reconciler monitoring. Production secrets never appear in Go/browser/tracked configuration/evidence. Test events cannot unlock live orders. Staging must verify real hosted test checkout, signed webhook retries, amount/account/mode matching, expiry races, refund/revocation and persistence with exact candidate before live charging. No such configuration or external call was performed for this draft.

## Revision history

Original independently reviewed draft SHA256: `3a4be1766016e25979248b090590f34883691ec569bda28b6f5ab9dd4b5fb85e` (retained hash-named sibling). Revision resolves both P1 findings in `/tmp/autodata-workshop-commerce-plan-review.md`: actual production Dockerfile is38th path with shared manifest installation/probe; official Stripe16.1.0 version/checksum/constructor API verified; paid order's durable index intent/scanner/retry/readiness and explicitly deferred grant-checked article preparation replace the legacy source-URI dead end. Same fourteen test roots; later paid-access enforcement remains a release prerequisite. No implementation or repository edits.


## Canonical incorporation

Independent review approved draft766c2ba715189eda19cb5e5e5565985e26564297d30685da0c969ea3d03e8776 after resolving both production packaging and canonical preparation blockers. Review a6cb1030ba4324a2bd834b13b48f31e0187665531c98ac4d57166e2ecd2f9615 is retained at /tmp/autodata-workshop-commerce-plan-review.md; the original failed planning review remains preserved. This canonical copy adds tracking and incorporation metadata only. Before dispatch, reinspect verified039 identity interfaces and commit the synchronized task/Issue/Project checkpoint with passing machine preflight.


## Verified identity interface amendment before dispatch

Read-only inspection of actual R5 successor
`b4f3dc86a18a8087f8ff664e37bec594909eae80` found compatible customer account,
session Principal, CSRF and HTTP DTO interfaces. One current-head verification
dependency requires an explicit39th implementation path:
`scripts/dev/production_access_smoke.py`. Its committed039 collector otherwise
rejects the new040 database created by its unchanged real-PG bridge. Update
the measured current manifest/head to exact001–040, change only the current-head
assertion name to fresh_migration_head_040 and result migration_head to
040_workshop_commerce. Preserve the separate historical038 startup-refusal
database/ledger, all five exact identity Go scenarios, nine assertion positions,
eight raw files, safe row allowlists and required no-skip/provenance checks.
The pure collector tests derive key sets from collector constants and need no
additional path; inspect after implementation rather than assuming a pass.

The coordinator must create independently reviewed040 successor supervisors
for identity and R3 regressions; retain original039 supervisors and receipts
unchanged. R3's current migration replay/schema/row inventory must include the
new040 commerce tables without reducing any earlier scenario/measurement.
No identity implementation or historical039 SQL changes are authorized by this
amendment. Actual039 runtime acceptance and integration still precede the
commerce gate. The earlier38-path planning review is retained as historical
evidence; this explicit amendment requires review before dispatch.

Independent review approved the bounded39th-path amendment: `/tmp/autodata-commerce-039-interface-amendment-review.md`, SHA256 `14105d71e52e14855cd60482254f56408810699ad6ae148c87fcf7607eca1431`. It found no additional identity implementation/test path necessary.


## Synchronized implementation checkpoint

Firebase candidate b4f3dc86a18a8087f8ff664e37bec594909eae80 is verified and
integrated at3fdcd0bc0ac993dd15ad2219df9d09ffeed27a4e. Full CI41696273960
passed at472492dd868122b2b0da00dc84e15c5424aa0276, including live Compose.
The exact39-path plan, actual session/CSRF/account interfaces and collector040
amendment passed independent review. Issue186/Project8 and canonical task/todo
are saved and read back; commit this checkpoint and pass exact-base preflight
before implementation. No deployment or live charge is part of this gate.


### Checkout-origin amendment review

Independent review accepted the server-owned origin correction with explicit
test-loopback compatibility and fixed `order` query binding. The 39-path scope
remains unchanged. A new synchronized checkpoint/preflight is required before
the affected Workshop composition/configuration code; prior independently scoped
SQL/transaction work remains covered by the original 3e9d062 checkpoint.


### Early core review corrections

Independent review of immutable506eecc identified the provider-fragment restriction,
missing pre-payment remote Price validation, early-refund library omission and
missing descriptor-snapshot active-rights predicate in library readiness. Correct
all four within the existing39 paths and preserve focused red/green evidence.
Final fourteen-case PostgreSQL acceptance and exact-candidate review remain required.


### Actual Go-to-Python commerce contract regression

Independent API review atad2b088 against the actual Python service found missing
organization_id in grant checks and missing version in checkout responses. Keep
Python’s exact active owner-pair validation; extend the Go checker with trusted
organization_id. Every checkout/processing/owned response includes versionv1, and
owned always returns HTTP200, including settlement before create response.

Strengthen the existing `test_orders_create_and_owner_scope` PostgreSQL case; do
not add a fifteenth case or change the67 outer pytest IDs plus7 native subtests.
Its actual private HTTP server and PostgreSQL store invoke the new Go root
`TestWorkshopCommercePythonIntegration` in already-approved commerce_client_test.go.
Structured argv, cwd `/workspace/apps/api-go`:
`go test -json -run '^TestWorkshopCommercePythonIntegration$' -count=1 .`.

Normal Go mode skips this explicit fixture root. Required mode
`AUTODATA_REQUIRE_COMMERCE_INTEGRATION=1` must fail on missing/malformed inputs.
Pass only owned fixture values via AUTODATA_COMMERCE_FIXTURE_URL, ACCOUNT_ID,
ORGANIZATION_ID, CONFIGURATION_ID, IDEMPOTENCY_KEY, ORDER_ID and REGION (each name
has the AUTODATA_COMMERCE_FIXTURE_ prefix). Region is US; token is the synthetic
literal fixture-internal. URL must be exactly HTTP127.0.0.1 with a valid explicit
port, no userinfo/path/query/fragment; IDs are canonical UUIDs. Retain fixture-only
execution, finite subprocess timeout, isolated Go caches/toolchain and no external
network/provider authority.

The actual HTTPCommerceClient requests quote, reuses the existing checkout key
(expect200/same order/versionv1), reads order status, reads the empty owner library,
and invokes grant check (typed required403). Project each non-grant reply through
the real commercePublicResult validation. No additional order/request/grant rows
are created; the first case’s existing row invariants stay intact. Ownerorg and
version regressions must fail this actual seam, not only handwritten fake DTOs.

Collector raw inventory becomes ten files: prior eight plus
`workshop-commerce-go-events.jsonl` and `workshop-commerce-go-stderr.log`.
Result and raw-row top-level objects add go_root, go_exit_code and go_timed_out.
Require the exact single root run/pass and package pass, no failures/skips/extra
case identity, zeroexit/no timeout, tied to the first actual PostgreSQL case flag.
The17 existing assertion keys are unchanged. The independently reviewed commerce
supervisor must reopen and parse the Go JSON before accepting that case; a boolean
alone is insufficient. Preserve old and draft evidence unchanged. No extra path,
new fake backend, expanded payment scope or actual provider call is authorized.
