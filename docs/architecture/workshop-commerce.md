# Paid Workshop launch contract

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

This records the current product direction. It is not an implementation
authorization or a production-readiness claim. Each implementation lane still
requires the committed planning gate and an exact-base preflight.

## Product and ownership

The Workshop launch is a one-time purchase of one vehicle dataset for **$20**.
The currency is **USD**, with exactly **2000 minor units total**. The
customer-facing domain is **https://cars.tk**, with DNS managed through **Vercel**
under the current user direction. This is a planning fact; no DNS action is recorded.

The initial purchasable unit is the selected normalized vehicle configuration
and region. The server resolves this scope from the catalog; clients cannot
invent vehicle keys or substitute a broader vehicle-family ID at checkout.
Eligible articles from both banks belong to that scope through existing
verified vehicle associations. Similar titles or provider IDs do not establish
cross-bank identity. Selection and price are shown before payment.

A purchase belongs to a durable customer account. Its entitlement has no normal
expiry and needs no subscription or renewal payment. Logging out, changing
devices, deploying the app, or retrying ingestion does not remove ownership.
Existing source-rights withdrawal and explicit, auditable refund/revocation
remain separate policy transitions. The launch does not promise offline export
or a fixed immutable copy of all future content.

The same shared canonical article is rewritten once per source/transformation
identity and reused by entitled customers. Readable source content remains
available while rewriting completes. Source, canonical content and media obey
the same purchased-scope and current-rights checks.

## Customer flow

1. Browse safe vehicle selectors and see the selected configuration, region
   and one-time price.
2. Sign in with Firebase. Google sign-in is the proposed initial provider.
   Map the verified Firebase project and UID to a server-owned account and
   personal organization; email and browser-supplied claims cannot assign
   ownership or staff privileges.
3. Create or reuse a server-owned order, then enter hosted Stripe Checkout.
   A success redirect cannot grant access. Only verified settled payment
   matching the stored order, session, scope, amount and currency may do so.
4. Show payment processing until the durable grant exists. Keep payment state
   separate from content preparation; retrying preparation never charges again.
5. Open the purchased configuration from a persistent **My vehicles** library.
   Unpaid or adjacent scopes remain locked, including direct API/media calls.

Production authentication will use secure same-origin sessions rather than the
current local demo bearer. Full article, source, processing and media reads
must check entitlement before hydration or storage access. Public browsing
exposes selectors and a safe quote, with bounded catalog hydration.

## Reuse and implementation sequence

The repository already has a Stripe adapter, durable payment reconciliation,
non-expiring organization entitlements and protected dataset projections.
Customer identity, checkout/webhook HTTP wiring and owner-scoped library reads
are implemented and verified. Purchased Workshop catalog authorization and the
customer UI are being completed against these reviewed interfaces.

The customer design supersedes the generic OIDC-only assumptions and
role-only shared-catalog rule in the earlier R5 plan. That older plan does not
authorize the expanded commerce implementation unchanged.

Concrete todo:

- [x] Freeze and verify Firebase account/session contracts and additive
  migration 039 against the integrated R3 interfaces and shared migration runner.
- [x] Freeze server-owned orders, authoritative USD 2000 pricing, idempotent
  Stripe settlement, durable grants and explicit refund/revocation handling.
- [x] Retain source implementations of safe browse/quote, owned library and
  purchased article/source/processing/media checks at product
  `6949eb1b1a5b93c9b2eb0579328e24c697f6f331`; this records source presence,
  not current-source runtime or live acceptance. See
  `docs/verification/2026-11-04-workshop-launch-source-readiness.md`.
- [x] Retain source UI for sign-in, checkout return, My vehicles and
  source/canonical reader at the same pinned product source; browser,
  accessibility and same-candidate final180 acceptance remain pending.
  See `docs/verification/workshop-customer-ui-runbook.md`.
- [ ] Verify configured identity, Stripe test payment/webhook, both banks,
  persistence, backup/restore, monitoring and the exact release candidate.
- [ ] Deploy the verified candidate to the selected host and validate cars.tk.

## Hosting decisions still to resolve

The user has Google Cloud/Firebase and Vercel available and permits self hosting.
Firebase identity with Google Cloud hosting is the proposed deployment. The
specific project is awaiting the user's selection. No resources, DNS changes,
live payments or production deployment have been made for this plan.

The current runtime includes persistent PostgreSQL, NATS, S3-compatible storage
and long-running workers, so hosting must support those dependencies. A static
Vercel deployment alone is insufficient. The deployment plan must freeze service
placement, region, capacity, secret delivery and operating cost before creation.
The user's launch goal authorizes preparing and executing a concrete release;
earlier orchestration-only deployment restrictions are historical scope, not a
reason to abandon the launch request. No code or infrastructure gate is waived.


### Concurrent Workshop delivery

The user requested three concurrent builders. The canonical parallel plan is `docs/superpowers/plans/2026-11-03-workshop-parallel-delivery.md`: twelve article-access paths, four protected-media paths and thirty-two UI paths have exclusive owners. Reviewed interfaces permit parallel implementation after synchronized preflight while the coordinator completes dependency/runtime acceptance. This replaces serial dispatch timing, not production acceptance requirements. Commerce candidate `d2eb70fa9b96fcebe1c33ef6cddcdad5c4a5eec7` is verified as a development dependency: all14 commerce/5identity/8R3 cases, the actual ingestion production-image import proof and full CI41705272372 passed. Evidence: `docs/verification/2026-11-03-workshop-commerce.md`. Production deployment remains unverified.

## Task59 runtime purchase authority — synchronized planning amendment

The synchronized Task59 plan is `docs/superpowers/plans/2026-11-05-workshop-purchase-config-interlock.md`; its spec/record/task/verification are the dedicated 2026-11-05 purchase-config-interlock gate. Independent corrected-draft PASS29 and root Issue186/Project8 synchronization are complete. Root authorized only the eight-document planning checkpoint commit/push; external actual SHA/tree seal, both exact-checkpoint preflights, independent synchronized-checkpoint review and explicit dispatch remain required. Current implementation allowlist=[], every authority=false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. No future implementation/test is claimed. Task58 remains independently owned and unchanged.

Planned Python CommerceService owns immutable startup purchase/legal config; Go strictly projects it at the existing public URL, never independently enabling checkout. Missing/malformed/disabled config yields canonical disabled notices and503 for every checkout POST before transactions/idempotency/order/provider operations, including stored creating/open-key replays. Existing ownership/library/status, webhook/reconciliation and valid late settlement/refund/revocation remain available. Quotes retain existing purchasable eligibility semantics and exactly USD20 total.

AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON is a bounded nonsecret runtime input, with strict seven-key workshop-v1 schema; tests use synthetic approved-shape values only. Owner legal/privacy/refund/contact/support and truthful tax notice are not supplied or approved here. Tax treatment within USD20 still requires owner/adviser decision; adding tax on top is outside this contract. Secrets, actual Firebase/Stripe configuration and staging/release proof remain outside this application lane.

Production's closed renderer/schema/config-hash delivery currently does not admit the new input. A separately owned synchronized deployment-config follow-up is a mandatory deliverability blocker; no manual env mutation or config-hash bypass is permitted. Effective pause needs coordinated maintenance/drain and replacement of every commerce process. Old enabled replicas/binaries may still accept checkout; previously issued Stripe URLs may settle and legitimate recovery remains required. Compatible rollback must preserve pause through an approved operational plan. No instant fleet kill switch is promised.

Vercel manages cars.tk DNS under current user direction; source application verification authorizes no DNS/cutover, merchant/live-sales enablement, secret delivery, merge or deployment.

## Coordinator tracking readback — planning synchronized

Issue comment https://github.com/lucronn/autodata/issues/186#issuecomment-6650475758, created 2026-11-05T05:24:57Z, and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` retain the literal goal, six todos, eight gate paths, fifteen future implementation paths and canonical references. Fresh before snapshot `/home/corp/autodata-evidence/task59-before-tracking.json` SHA256 `4dc68f829e038886b114c2d79daabd27c505b6c2e1dbc40c7646ed0a71a6448d`; after snapshot `/home/corp/autodata-evidence/task59-after-tracking.json` SHA256 `f32db5549893ecba8e2f36d2fd920d86b6b391cc653066e7df4c1cababa56f64`. The Issue body and all262 prior comments are unchanged; other Project fields are unchanged and the previous Project Source text is preserved verbatim in the comment. Source before SHA256 `27c5c9fc62dfa3274e966cc04d63c0e10e071134248962cbd744c7c4f2355f7f`, after SHA256 `0b6a39a6cc2c1872c38014c65e4d2131c45b98026745d0e53be8d330fb2d0d2a`. Root completed synchronization; this planning agent verified the saved literal/preservation readbacks without additional GitHub writes.

Independent corrected-draft review `/home/corp/autodata-evidence/task59-gate-draft-review/REPORT.md` SHA256 `ce210040dbe65be7c2add415dfa8b8f8a01d032f6736aec485bccc942d20e751` passed29 checks after the slashless method-guard correction. Reviewed draft bytes are retained externally under `/home/corp/autodata-evidence/task59-purchase-config-checkpoint/reviewed-draft/`. Synchronization changes only tracking/envelope/canonical status bytes, preserving approved application contract, URL vectors, routing matrix, financial/preservation limits and fifteen-path future scope.

Standalone/nested records and Task59 spec/task/queue planning/tracking status are synchronized at 2026-11-05T05:25:42Z; execution remains blocked, current implementation allowlist=[], all authorities=false, implementation_dispatch:false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. Root authorized only the eight-document planning checkpoint commit/push. Externally seal the actual checkpoint SHA/tree and require both exact-checkpoint errors=[] preflights, independent synchronized-checkpoint review and explicit coordinator fifteen-path dispatch before implementation. Future checkpoint/source hashes remain external to these predecessor bytes. No implementation, Issue/Project/PR, live-config, merchant, secret, merge/deploy/DNS action is authorized here.


## Task61 historical merchant fixtures — planning synchronized; execution blocked (2026-11-05)

Goal: Isolate historical Task54 merchant-preparation fixtures from the evolving application tree, preserving the exact validator contract and Task59 server-owned configuration authority.

Task59 source `8d9f1a379924ae6636369e4b3b8e01ab6c258ccb` tree `ea2992091f0d00e10d3aa89f967ba735176f284d` remains the current application dependency. Task54 merchant preparation is an offline historical-byte consistency tool. Its frozen SOURCE/BUILD/EMBED/BASELINE pins are not a Task59 runtime binding. The proposed repair changes only test input provenance: archived30491-byte historical main.go and168-byte disabled JSON under scripts/dev plus the merchant test module. Keep live Dockerfile928-byte pin. Never restore the deleted workshop/purchase-config.json asset; current Python server-owned configuration and Go dynamic `/workshop/purchase-config.json` route remain authoritative.

Plan `docs/superpowers/plans/2026-11-05-workshop-merchant-fixture-compatibility.md`; spec `docs/agents/specs/2026-11-05-workshop-merchant-fixture-compatibility.json`; verification `docs/verification/2026-11-05-workshop-merchant-fixture-compatibility.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Root completed fresh tracking synchronization in Issue186 comment6650911660 and Project8 with independent draft PASS15 and preservation PASS10. Root authorized only eight-document checkpoint commit/push; external exact SHA/tree seal, dual preflights, independent checkpoint review and explicit three-path dispatch remain required. All prior Task59 gate/source records and queue/root fields remain historical evidence.

Fixture consistency provides no owner identity, legal/tax/publication, secret/Firebase/Stripe, production config delivery/restart/drain/rollback, authentic TEST/runtime/staging/host/TLS, API21/DTO120/final180, merge/deployment/live-sales or Vercel DNS authority. All authorities false/current implementation allowlist empty; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Existing protected release blockers remain in force.
