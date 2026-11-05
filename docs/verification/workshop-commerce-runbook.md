# Workshop commerce verification

This lane adds durable $20 USD ownership of one canonical vehicle configuration
and region. A verified Stripe payment grants permanent ownership; current source
availability and content preparation remain separate. UI and paid catalog/media
source implementations now exist at pinned product source
`6949eb1b1a5b93c9b2eb0579328e24c697f6f331`; their current-source runtime and
release acceptance remain separate gates. This document does not approve deployment.

## Configuration

`AUTODATA_COMMERCE_MODE` is explicitly `disabled`, `stripe_test` or `stripe_live`.
The committed manifests keep it disabled. Disabled routes return 503 and never
construct a Stripe client. Enabled ingestion HTTP and the existing payment
reconciler require the Stripe 16.1.0 production image and secret-managed
`AUTODATA_STRIPE_SECRET_KEY`, `AUTODATA_STRIPE_WEBHOOK_SECRET`,
`AUTODATA_INGESTION_INTERNAL_TOKEN`; expected `AUTODATA_STRIPE_ACCOUNT_ID` and
`AUTODATA_STRIPE_PRICE_ID` are server configuration. Keep test/live databases
separate. No secret key or webhook secret belongs in the Go API or browser.

Enabled startup verifies the actual merchant, active one-time Price for exactly
2000 minor USD units, mode, migration 040, product and existing order merchant/mode.
Missing configuration or conflicting database ownership prevents readiness.
`AUTODATA_ENV` and `AUTODATA_PUBLIC_ORIGIN` must match identity configuration:
production exactly `https://cars.tk`; staging/development HTTPS; test may use
HTTP on localhost or a parsed loopback IP. Return origins forbid credentials,
path, query, fragment and malformed ports. Both Checkout returns are the fixed
`<origin>/workshop/?order=<stored UUID>`; returns never grant access.

The Base44 dependency-only image does not include Stripe and remains explicitly
commerce-disabled in this lane. Enabling commerce there requires a separately
gated dependency-image change. No runtime pip installation is introduced.
The legacy fake payment smoke is accepted only while commerce is disabled and
is not payment readiness evidence.

## Required isolated acceptance

The coordinator creates an immutable plain clone, exact input manifest, private
fixture network and owned PostgreSQL/S3/NATS resources using the existing
lifecycle fixture. No host ports, Docker socket mounts, external credentials,
Firebase emulator or live provider calls are needed. The fixture image installs
its dependencies from ingestion pyproject, including Stripe 16.1.0. The official
SDK's HTTP transport is replaced by a deterministic local fixture; HMAC webhook
verification still runs through the actual SDK.

Run the committed collector inside that owned fixture:

```text
python scripts/dev/workshop_commerce_smoke.py --mode fixture --candidate-sha <exact40hex> --output /artifacts/workshop-commerce.json
```

Its child runs exactly the approved three pytest modules, setting
`AUTODATA_LIFECYCLE_TEST=1` and `AUTODATA_REQUIRE_COMMERCE_INTEGRATION=1`.
All fourteen exact unparameterized commerce cases and the migration cases must
execute without skips, failures or timeouts. Missing required fixtures fail.
The first case also executes the exact required Go client root against its actual
Python HTTP server and PostgreSQL rows, validating quote, existing checkout,
status, empty library and missing grant without adding an order. Raw Go JSON
and stderr are required in the ten-file evidence inventory.
The raw JUnit, stdout/stderr, safe synthetic PostgreSQL rows, actual SDK transport
observations and before/after input/Git provenance are retained and hashed in an
allowlisted inventory. A result with missing evidence cannot report success.
The coordinator independently validates these files, runs the current040 R3
and identity regression supervisors, and separately builds/probes the exact
production ingestion image with `import stripe; assert stripe.VERSION ==
'16.1.0'`. Fixture-image proof alone is insufficient for the production image.

## Runtime operations

The existing payment reconciler retries immutable pending signed facts and
leases paid preparation intents. It schedules the actual shared two-provider
catalog index outside financial transactions. A crash or local scheduling
outage retains ownership and retries with bounded backoff. Index acknowledgement
does not fetch every article or promise completed content. A paid library item
can remain `paid` without a requested body. Library readiness checks exact
configuration/region, identity review, membership, descriptor/body/resource
rights and quarantine before reporting a readable current article.

Do not manufacture a replacement Checkout after a local timeout or elapsed
one-hour timer. Unknown creation is replayed with the same stored provider key
only within 23 hours; later ambiguity requires reconciliation. An old session and
intent need authoritative nonchargeable proof before a fresh explicit client key
can allocate a replacement. Paid scopes always return owned without another
provider create. Full refunds/lost full disputes revoke monotonically; an early
refund creates an owner-visible tombstone even before any grant exists.

Live merchant configuration, webhook routing/signing secret, independent final
acceptance, UI, paid-reader/media authorization and release/deployment approvals
remain separate prerequisites. Never put actual tokens, raw provider payloads,
customer email or real payment identifiers in verification artifacts.

## Task59 application configuration/interlock — planning synchronized, not operational enablement

Plan: `docs/superpowers/plans/2026-11-05-workshop-purchase-config-interlock.md`.
Verification: `docs/verification/2026-11-05-workshop-purchase-config-interlock.md`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Task59 planning/tracking is synchronized after independent corrected-draft PASS29 and root preserved readbacks; execution remains blocked and no implementation has been dispatched. Root authorized only the eight-document checkpoint commit/push, with external exact-checkpoint seal/preflights/review and explicit dispatch still required. Future tests below are defined, not executed. The existing fourteen-commerce collector and five-identity/paid producer inventories remain frozen; a separate three-case required-mode PG module and named Go bridge produce Task59 regression evidence only, never accepted case credit. The exact separate command/artifact/no-skip contract is in the Task59 verification file. Fixture-only enabled injection is the sole change allowed to the two existing commerce/paid fixture modules.

The optional nonsecret AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON input will be read only by Python commerce composition, at startup, at most16KiB UTF-8. Omitted/exact-empty or complete canonical false input gives disabled; malformed nonempty input gives disabled and one fixed redacted composition diagnostic without removing otherwise valid webhook/status/grant recovery. Existing mode/merchant/price/origin/schema/ownership startup failures remain strict. No config content, URL, notice or parser exception may be logged. Public Go GET/HEAD exposes exactly the seven fields with no-store; private token-authenticated POST purchase-config accepts exactly{}. No secret values are requested here.

For purchase-only pause retain enabled stripe_test/stripe_live commerce and configure purchase enabled:false through the separately approved production delivery path. Whole AUTODATA_COMMERCE_MODE=disabled removes the subsystem and is not a purchase-only pause. No hot reload or mutable enable endpoint exists. Do not execute a pause from this planning checkpoint: production schema/renderer/config-hash support for the new variable still needs a separate synchronized follow-up. Never hand-edit container environment.

Once separately delivered, coordinated maintenance/drain and complete process replacement must be proved before calling a pause effective. Rolling old enabled replicas can still accept; issued Checkout URLs may settle after pause and must retain legitimate financial recovery. Old binaries do not enforce this interlock. Data compatibility without a migration does not establish pause-preserving rollback; compatible rollback needs its own approved controls.

Owner-approved terms/privacy/refund/contact URLs/content, support identity and truthful tax notice remain missing. URLs pass syntax checks only; tests do not approve legal content or ownership. Tax obligations and handling within exactly USD20 total need owner/adviser decision; extra tax requires a separate financial-contract change. Actual Firebase project/authorized domains, Stripe merchant/price/keys/webhook, protected secret delivery, authentic identity/payment/staging/restore/host/TLS proof, API21/DTO120/final180 and release approval remain blocked. cars.tk DNS is managed through Vercel by current user direction; no DNS operation follows from application source verification.

Current implementation allowlist=[], all authorities=false, implementation_dispatch:false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified.

## Coordinator tracking readback — planning synchronized

Issue comment https://github.com/lucronn/autodata/issues/186#issuecomment-6650475758, created 2026-11-05T05:24:57Z, and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` retain the literal goal, six todos, eight gate paths, fifteen future implementation paths and canonical references. Fresh before snapshot `/home/corp/autodata-evidence/task59-before-tracking.json` SHA256 `4dc68f829e038886b114c2d79daabd27c505b6c2e1dbc40c7646ed0a71a6448d`; after snapshot `/home/corp/autodata-evidence/task59-after-tracking.json` SHA256 `f32db5549893ecba8e2f36d2fd920d86b6b391cc653066e7df4c1cababa56f64`. The Issue body and all262 prior comments are unchanged; other Project fields are unchanged and the previous Project Source text is preserved verbatim in the comment. Source before SHA256 `27c5c9fc62dfa3274e966cc04d63c0e10e071134248962cbd744c7c4f2355f7f`, after SHA256 `0b6a39a6cc2c1872c38014c65e4d2131c45b98026745d0e53be8d330fb2d0d2a`. Root completed synchronization; this planning agent verified the saved literal/preservation readbacks without additional GitHub writes.

Independent corrected-draft review `/home/corp/autodata-evidence/task59-gate-draft-review/REPORT.md` SHA256 `ce210040dbe65be7c2add415dfa8b8f8a01d032f6736aec485bccc942d20e751` passed29 checks after the slashless method-guard correction. Reviewed draft bytes are retained externally under `/home/corp/autodata-evidence/task59-purchase-config-checkpoint/reviewed-draft/`. Synchronization changes only tracking/envelope/canonical status bytes, preserving approved application contract, URL vectors, routing matrix, financial/preservation limits and fifteen-path future scope.

Standalone/nested records and Task59 spec/task/queue planning/tracking status are synchronized at 2026-11-05T05:25:42Z; execution remains blocked, current implementation allowlist=[], all authorities=false, implementation_dispatch:false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. Root authorized only the eight-document planning checkpoint commit/push. Externally seal the actual checkpoint SHA/tree and require both exact-checkpoint errors=[] preflights, independent synchronized-checkpoint review and explicit coordinator fifteen-path dispatch before implementation. Future checkpoint/source hashes remain external to these predecessor bytes. No implementation, Issue/Project/PR, live-config, merchant, secret, merge/deploy/DNS action is authorized here.


## Task61 historical merchant fixtures — planning synchronized; execution blocked (2026-11-05)

Goal: Isolate historical Task54 merchant-preparation fixtures from the evolving application tree, preserving the exact validator contract and Task59 server-owned configuration authority.

Task59 source `8d9f1a379924ae6636369e4b3b8e01ab6c258ccb` tree `ea2992091f0d00e10d3aa89f967ba735176f284d` remains the current application dependency. Task54 merchant preparation is an offline historical-byte consistency tool. Its frozen SOURCE/BUILD/EMBED/BASELINE pins are not a Task59 runtime binding. The proposed repair changes only test input provenance: archived30491-byte historical main.go and168-byte disabled JSON under scripts/dev plus the merchant test module. Keep live Dockerfile928-byte pin. Never restore the deleted workshop/purchase-config.json asset; current Python server-owned configuration and Go dynamic `/workshop/purchase-config.json` route remain authoritative.

Plan `docs/superpowers/plans/2026-11-05-workshop-merchant-fixture-compatibility.md`; spec `docs/agents/specs/2026-11-05-workshop-merchant-fixture-compatibility.json`; verification `docs/verification/2026-11-05-workshop-merchant-fixture-compatibility.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Root completed fresh tracking synchronization in Issue186 comment6650911660 and Project8 with independent draft PASS15 and preservation PASS10. Root authorized only eight-document checkpoint commit/push; external exact SHA/tree seal, dual preflights, independent checkpoint review and explicit three-path dispatch remain required. All prior Task59 gate/source records and queue/root fields remain historical evidence.

Fixture consistency provides no owner identity, legal/tax/publication, secret/Firebase/Stripe, production config delivery/restart/drain/rollback, authentic TEST/runtime/staging/host/TLS, API21/DTO120/final180, merge/deployment/live-sales or Vercel DNS authority. All authorities false/current implementation allowlist empty; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Existing protected release blockers remain in force.


## Task62 purchase configuration delivery — planning synchronized (Operations and verification runbook)

Task62 planning only; no source delivery capability is implemented by this amendment. Plan `docs/superpowers/plans/2026-11-05-workshop-purchase-config-delivery.md`, spec `docs/agents/specs/2026-11-05-workshop-purchase-config-delivery.json`, record `docs/agents/records/2026-11-05-workshop-purchase-config-delivery.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-purchase-config-delivery.json`, verification `docs/verification/2026-11-05-workshop-purchase-config-delivery.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8 are synchronized for Task62 by the coordinator. Parent `e200cfd6b473e9231844d133f63244f3a627a356` / tree `269bd94410df22a8718f005c1d0b0142238cdafc` preserves Task59/Task61 histories. All authorities=false, current implementation allowlist=[], accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified.

Required host schema_version=2 deliberately rejects host-v1/missing/null/partial/unknown purchase config; release manifest remains v1. Required seven-key `workshop_purchase_config` is original structured nonsecret data included in service_config_sha256; explicit disabled means enabled=false, terms_version=workshop-v1, all four URLs and tax_notice=null. Enabled requires unchanged Task59 syntactic URL/scalar/Unicode/UTF-8 semantics, four HTTPS URLs <=2048bytes each and single-line notice <=1024bytes. No owner content/domain/tax approval follows from syntax.

Installed validator stays self-contained. Canonical UTF-8 JSON replaces every U+0024 with six ASCII `\u0024` characters; emitted wire <=16384bytes, otherwise fixed redacted `purchase_config_transport_limit` before render. Task59-valid dollar-heavy9343byte raw/54883byte escaped data is intentionally non-deployable. No normalization, shell expansion, ambient override or runtime parser change. Derived AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON goes only to ingestion-http; Go gets authenticated Task59 HTTP projection. Existing api/ingestion-http token numeric references must be identical; actual credentials remain separate protected tmpfs file delivery, never Config.Env. Final no-dollar guard and payment-reconciler role/default remain unchanged.

Synthetic proof after a fresh gate uses actual renderer, copied wrapper with secret_root-only replacement and UID/GID1000 protections, unchanged parser, frozen enabled→disabled reconstruction and pre-factory checkout denial. Local Compose config parsing uses no daemon or production startup and required mode cannot silently skip. Existing Task59 PG/Go authority roots remain separate; synthetic transport supplies zero acceptance credit.

Pause is a new reviewed configuration/hash and process reconstruction; keep commerce mode, Stripe settlement/webhook/reconciliation and paid recovery intact. Existing objects cannot hot reload. Real maintenance/drain/fencing/bounded in-flight policy/install/all commerce replica and affected API replacement/projection equality/checkout denial/resume remain separately blocked. Issued Stripe URLs cannot be claimed retroactively canceled. Immutable same-source config generations, retention/atomic switch/recovery are missing; never overwrite installed source directories or invent empty commits. Automatic rollback requires same config hash/platform/SQL tree and independently reviewed Task59-capable source. A pause hash bars automatic return to earlier enabled config; config-changing rollback is a separate reviewed release, and failed recovery retains maintenance.

Only four future implementation paths: `infra/deploy/gce/runtime-check.py`, `infra/deploy/gce/test_host_runtime.py`, `infra/deploy/gce/test_purchase_config_delivery.py`, `infra/deploy/gce/release.env.example`. No application/DB/endpoints/frontend, runtime-entrypoint, Compose, release schema, Dockerfile/workflow/cloud adapter/protected variable changes. Task60 publication ownership and frozen evidence/acceptance ledgers remain intact.

Remaining actual owner/legal/tax/support/merchant/Firebase/token/project/resource facts, protected config-generation/install/drain/restart/rollback, authentic TEST/staging/host/TLS/restore/current-source browser/runtime/API21/DTO120/final180 and fresh source/PR CI are unmet. Cars.tk DNS is Vercel by trusted coordinator/user direction; no DNS/cloud action is authorized. Independent draft review and literal six-todo/nine+four-path Issue/Project preservation readbacks passed; committed/pushed checkpoint, external actual SHA/tree seal, standalone+nested exact-base errors=[] preflights, independent checkpoint review and explicit dispatch remain required. Any Task61 source change or CI failure blocks synchronization.


## Coordinator tracking readback — planning synchronized

Updated at 2026-11-05T06:11:06Z. Root synchronized the exact goal, six literal todos, nine gate paths and four prospective implementation paths in https://github.com/lucronn/autodata/issues/186#issuecomment-6651122921; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` indexes that comment. Before snapshot `/home/corp/autodata-evidence/task62-config-delivery-before-tracking.json` SHA256 185dea24ec804d096f159a9ded443477ea0cff0a8ded02c884eb037e46220044; after snapshot `/home/corp/autodata-evidence/task62-config-delivery-after-tracking.json` SHA256 c0d321f6d22bb037cd168a5b2a598372bb80219c70af47a9131f03e859e49ba5. Preservation `/home/corp/autodata-evidence/task62-config-delivery-tracking-verify.json` SHA256 739d2d0b1bacf132bd8ef144146c4d13b0811f0927cc90dfaa8dacf1433c5f7f passed10 checks; independent draft review `/home/corp/autodata-evidence/task62-config-delivery-draft-independent/REPORT.json` SHA256 e303d03951a62f6d38c82f549948f1371d8a04646bf053a228e3d927d1b0096d passed15 checks. Issue body and prior comments, other Project fields and prior Project Source were preserved. This agent performed no Issue/Project writes.

Status/planning/tracking are synchronized; execution remains blocked, current implementation allowlist=[], all authorities=false, credits0, verified_case_ids=[], release_state=unverified. Planning synchronized by root with Issue186 comment6651122921/Project8 preservation PASS10 and independent draft PASS15. Nine-document planning-only checkpoint commit/push authorized. External actual SHA/tree seal, standalone+nested exact-checkpoint errors=[] preflights, independent checkpoint review and explicit four-path dispatch remain required. Task61 PR290/full CI dependency evidence remains pending. Execution blocked; all authorities false/current implementation allowlist empty; no predecessor self-hash. Task61 PR290/full CI remains pending and supplies no inherited green. Historical draft/proposal observations above remain provenance, not fresh implementation evidence.
