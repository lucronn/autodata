# R6 paid exact-scope HTTP and no-work receipts implementation plan — synchronized tracking

> For agentic workers: use superpowers:executing-plans after coordinator adoption, committed synchronized gate, exact-base preflight, independent checkpoint review and explicit dispatch. This documentation draft grants no implementation authority.

**Goal:** Add one unselected internal consistency inspector for both ExactScopeAndOwnerIsolation bank cases, covering exactly 22 projected HTTP observations, exact configuration/owner/region row relationships and two no-work/final snapshot pairs; preserve zero verified cases and all false authority flags.

**Architecture:** Extend the existing paid common → PG → migration → selector-work → GrantBeforeWork HTTP chain. Interpret the next fixed producer case, with strict schemas and repaired-copy semantic tests. Do not refactor existing inspectors or introduce a generic dispatcher. DTO120 remains independently inspected and unverified; its source-constant rebase and missing provenance require separate gates.

**Tech stack:** Python standard library, existing ArtifactStore and strict raw JSON parsers, inline unittest fixtures.
**Spec:** docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md §§4a/4b; docs/superpowers/plans/2026-11-03-release-acceptance.md; docs/superpowers/plans/2026-11-04-workshop-r6-paid-http-receipts.md; docs/verification/release-acceptance-runbook.md.
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8 (existing item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4)
**Inspection source:** 545f32098a659c75c11e4dd7ad7c00fbc9a2a976, latest R6 HTTP completion branch. Code is 66781084bde3ea382b35b4e33cdeace713f1096a. Read-only live PR check: draft/open PR200 has exact code head; draft/open PR202 has exact completion head and bases on the code branch. This planning worktree is based on exact source545f32098; no merge or broader application integration is claimed.
**Status:** tracking synchronized after independent live readback. Commit/push, full-SHA preflight, independent exact-checkpoint review and explicit builder dispatch remain required. Tracking synchronization grants no implementation authority.

**Task:** `docs/agents/tasks/2026-11-03-production-release/r6-paid-scope-receipts.json`
**Record:** `docs/agents/records/2026-11-04-r6-paid-scope-receipts.json`
**Application evidence:** historical candidate `2de36a1305bfbe45992995e6caf0ba52f30fddcc` only; future application candidate is unselected. Planning source `545f32098a659c75c11e4dd7ad7c00fbc9a2a976`, predecessor code `66781084bde3ea382b35b4e33cdeace713f1096a`, future checkpoint and future implementation candidate are distinct identities. No source checkout or synthetic test constitutes application acceptance.

## Constraints and boundaries

- Execute with gpt-6.1-sol / medium / Fast or priority, no fallback.
- Literal implementation allowlist: scripts/dev/release_acceptance.py; scripts/dev/test_release_acceptance.py; docs/verification/release-acceptance-runbook.md. No new fixtures or producer changes.
- Preserve every pre-existing inspector's behavior, static missing-family inventory/order and existing observed diagnostics. Reuse helpers only where their contracts exactly match; do not generalize them in this milestone.
- Profiles stay disabled; enabled_tiers stays []; r6-release.json, evaluator, policy, CLI and parser ceilings remain byte-for-byte unchanged (2MiB envelope;4MiB raw JSON;8MiB per file;64MiB aggregate).
- No application, browser, DTO fixture, timeout, supervisor, workflow, Compose, SQL, staging, cloud, API21 evidence or retained private-evidence changes. No runtime, Docker/browser/provider execution, arbitrary imports/commands, network or secret access from assembler.
- Independent inspector results always status unavailable, complete false, verified_case_ids empty and all FLAGS false. Diagnostics add zero logical acceptance cases. No tier/profile promotion, merge/deploy/cutover authority.
- Historical candidate 2de36a1305bfbe45992995e6caf0ba52f30fddcc is immutable history. Source/tool/checkpoint/future candidate are distinct identities.
- This milestone does not close raw-wire, temporal SQL history, licensed-source, supervisor, reviewer or execution authority. Projected bodies cannot reconstruct raw body hashes/sizes.

## Why this milestone, and the eventual promotion path

PR200 covers only GrantBeforeWork x2/36 HTTP observations after common/PG/migration/selector layers. DTO inspector covers120 tuple/schema receipts while retaining ten missing provenance families. Existing r6-release task only supports disabled profiles. Enabling a slot would require a new contract, and current six required fixture slots total180 (5+8+14+12+120+21); paid12/DTO120 alone cannot set fixture_verified.

The next two exact-scope cases are an independent, short closed producer branch with22 observations and no worker/model/media complexity. Building all remaining paid cases, CI provenance and profile activation together would not be a bounded milestone. After this milestone the remaining PrepareSourceThenCanonicalReuse, ContextualMediaAndRevocation, HistoricalSourceAndRights, CustomerLegacyRoutesDenied semantic families remain separately reviewable work. Then freeze actual raw inventories/input/runtime/migration/supervisor/reviewer identities, authenticated CI archive provenance, current tool and complete Git provenance contract; add enabled-slot/profile integration and supporting identity/catalog/commerce/API21 validators under a separate checkpoint. If complete independently attested scenario/transport/process facts are absent from retained receipts, separately gate producer/supervisor collection and recapture the final immutable candidate; parser success cannot invent those facts. Final exact-head180/support/security/images/SDK/license/CI/reviewer proof and all eight real staging gates still precede corresponding release claims.

## Source and retained read-only observations

At source545f32098:
- scripts/dev/release_acceptance.py SHA256 ffa465196188c7dac214eb089857193533fed4d201300064f0865621b50dcd4e
- scripts/dev/test_release_acceptance.py SHA256 1f8df9345d2363a64e45c9b9162a981b868b8f6917882f0401484046765e3ad2
- apps/api-go/postgres_catalog_access_test.go SHA256 0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31
- docs/verification/release-acceptance-runbook.md SHA256 0f4c1ccb66bc1b5fcfa65ccbb3ebd00205d6be478208330fb768abc623d23ea5

Producer contract is TestPostgresPaidCatalogExactScopeAndOwnerIsolation (lines509..549 at current unchanged source), paidFixture.observe/call, paidHTTPObservation. Retained private artifact root is /tmp/autodata-paid-access-040-acceptance-2de36a1-v2/artifacts. Target go-measurement.json SHA256: bankone7a5f8263e54f9db88bb7b1765623cb9b74539c2f4f27ead574c5c667691251f3; banktwo174bba96282973819ae1151274787fafd55d12705e9931d27833496f2e417895. These hashes document historical inspection and are not future-case constants or test fixtures.

Each target has11 HTTP rows; final reader0/identity11; held_model_receipt null; observed_views null/empty; isolated snapshot grant9/identity11/reader0. Final snapshot has grant9 but intentionally no reader/identity keys. Isolated and final snapshots otherwise agree in historical bytes. All provider/source/asset/model/payment/article/selector/proxy/worker work receipts are zero/empty. The snapshot is after revocation followed by intentional legacy-unscoping; it cannot attest the earlier revoked database state.

## Exact internal API and fixed reads

Add:
```python
def inspect_paid_scope_receipts(store, *, candidate_sha, trusted_base_sha,
        profile_sha256, input_manifest_sha256, host_before_sha256,
        expected_driver_sha256, profile_version='paid-selector-v2'):
    result = inspect_paid_http_receipts(store, candidate_sha=candidate_sha,
        trusted_base_sha=trusted_base_sha, profile_sha256=profile_sha256,
        input_manifest_sha256=input_manifest_sha256,
        host_before_sha256=host_before_sha256,
        expected_driver_sha256=expected_driver_sha256, profile_version=profile_version)
    # Fixed two-case semantics below; no dynamic case/profile dispatch.
    # store.recheck() immediately before adding diagnostics and returning.
```

Read only declared paid-access/{bank}/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/{measured-runtime.json,go-measurement.json,result.json} and workshop-paid-access.json through existing confined bound readers. Inherit all twelve-case common/PG/migration/hash/identity checks first. Use exact numeric parsing for the new layer with the existing4MiB ceiling. No raw kind, CLI option or profile selects the API.

New diagnostics only: observed_scope_case_ids, exactly the two target IDs in bankone/banktwo order; observed_scope_http_observation_count22; observed_scope_snapshot_count4. Preserve all inherited fields and gaps; append paid_scope_temporal_entitlement_provenance to explain that terminal rows cannot prove interim revoked state. Do not remove inherited paid_pg_row_semantics, paid_http_media_rights, wire or transport gaps.

## Binding rules (never pin randomized historical UUIDs)

For each isolated snapshot let S=article, C=S.vehicle_configuration_id, V=S.vehicle_id, A=S.canonical_article_id. Strict lowercase UUID shape using existing helper; C!=V. Bind A to exactly one immutable canonical_articles row for current bank/C/V. Canonical IDs unique via inherited checks. Require exactly8 canonical rows: for each bank exactly one row at selected C, adjacent D, other-region R and null configuration U. All vehicle IDs V; C,D,R,V mutually distinct. Determine D from the unique workshop_order for paid-owner-b's customer account; determine C from paid-owner-a's order and require it agrees with S. Determine R as the only remaining third nonnull canonical configuration under the frozen producer contract. The retained PAID_PG_TABLES inventory has no vehicle_configurations region row: its producer-designated other-region/CA role is a contract label, not independently derived region proof. Validate the literal ?region=CA denial and order/request US scopes below, but do not claim that canonical rows independently establish R is CA. Bind per-bank adjacent/unscoped article IDs from those rows; do not infer either bank's article ID from a matching title. Both bank rows at C/D/R/null required exactly once.

Find customer accounts by fixed fixture firebase_uid paid-owner-a / paid-owner-b, distinct IDs and personal organization IDs, both active and fixture-project; the existing PG checker enforces closed row shapes, account/session typing and only some active-entitlement/order scope links. It does not establish the complete order/request/projection/organization/product chain; the new inspector must enforce the bounded predicates below explicitly. Exactly two paid orders, one for each account. Each order2000/USD, livemode false, status paid, region US; owner-a configuration C, owner-b D. Do not introduce external Stripe proof. Owner-a final entitlement linked by its dataset_request_id/entitlement_id remains status active but customer_account_id/configuration_id/region/commerce_order_id null and revoked_at null, revoke_reason fixture. Owner-b entitlement stays active/accountB/D/US/orderB with revoked_at/revoke_reason null. The new inspector, rather than the predecessor, must enforce exactly two orders, two dataset_requests, two dataset_projections and two entitlements, with one complete chain for each fixture owner. Validate lowercase UUID shape and uniqueness within each primary-key column: workshop_orders.order_id, dataset_requests.dataset_request_id, dataset_projections.dataset_projection_id and entitlements.entitlement_id. Require UUID-shaped order.dataset_request_id, order.entitlement_id, order.dataset_product_id; request.dataset_product_id, request.organization_id and request.correlation_id; projection.dataset_request_id, projection.entitlement_id and projection.dataset_product_id; entitlement.dataset_request_id and entitlement.organization_id. Each order.organization_id and its request.organization_id and entitlement.organization_id must equal its customer account.personal_organization_id (a strict UUID). For each owner order O, exactly one request D has D.dataset_request_id=O.dataset_request_id and D.correlation_id=O.order_id; exactly one entitlement E has E.entitlement_id=O.entitlement_id and E.dataset_request_id=D.dataset_request_id; exactly one projection P has P.dataset_request_id=D.dataset_request_id and P.entitlement_id=E.entitlement_id. Require O.dataset_product_id=D.dataset_product_id=P.dataset_product_id, UUID-shaped, with both owner chains using the same declared product UUID, without claiming an independent dataset_products row or payment-provider proof. Request D.vehicle_key must exactly equal O.configuration_id (C for owner-a, adjacent D-configuration for owner-b), and D.region=O.region=US. The bound two orders, requests, projections and entitlements must exhaust their respective arrays, preventing dangling, duplicated and cross-owner substitutes. The owner-a legacy-null entitlement is still bound to its retained request/entitlement IDs and organization even though its structured customer/configuration/region/commerce-order fields are intentionally null; do not require the null commerce_order_id to equal O.order_id. Owner-b commerce_order_id must equal its O.order_id as specified above. Apply every predicate to isolated and final terminal rows after inherited shape/hash/copy checks. These are terminal consistency predicates, not proof of the earlier revoked transition. No permissive legacy entitlement substitutes or complete commerce semantics claim is allowed. Bind final immutable_rows/paid_rows/article and all no-work values to isolated copies; inherited schema/row digest and populated replay seams run first.

## HTTP closed schema and sequence

Every row exactly the same13 fields used by GrantBeforeWork: method,path,owner_index,status,headers,body,body_sha256,body_size,body_truncated,reader_before,reader_after,identity_before,identity_after. Types strict; bool cannot substitute integers; body_sha256 lowercase64hex; body_size1..262144; body_truncated is False; body object. These digest/size fields remain declarations. Each reader before/after0; row i identity before i and after i+1. Final totals reader0/identity11 agree across measured/Go copies; snapshot isolated reader0/identity11; no fabricated final reader/identity fields.

Let L=/v1/catalog/vehicles/C/articles; L(X)=same listing with configuration X; Q=adjacent current-bank article; U=unscoped current-bank article. Sequence all GET:

| index | path | owner | status |
| --- | --- | --- | --- |
|0|L|0|200|
|1|L|1|403|
|2|L(V)|0|404|
|3|L(D)|0|403|
|4|L(R)|0|403|
|5|L?region=CA|0|404|
|6|L/Q|0|404|
|7|L/U|0|404|
|8|L/legacy|0|404|
|9|L|0|403|
|10|L|0|403|

Paths literal with canonical lowercase UUIDs, no encoded alternatives/extra query/order/slashes/URL/fragment. Headers exactly Content-Type application/json, Cache-Control private, no-store, X-Content-Type-Options nosniff. Full wire headers are not retained; do not claim unobserved header absence.

Row0 body exactly complete,hydrating,items,progress,version; true,false,versionv1. Progress exactly complete=true,percent100,phaseindexing,processed2,retryablefalse,statuscompleted,total2, strict types. Exactly two descriptor items, order independent, same14-field schema as existing HTTP row14. Bind IDs to selected C's two canonical bank rows; id=canonical_article_id, vehicle_id=C, title exactly bound row title. availability unavailable; complete false; content_status list_only; images[]; review_status UNREVIEWED; canonical_revision_id/content_origin/processing/source_revision_id/view_revision null. Bound current_source_revision_id/current_canonical_revision_id/current_job_id null.

Rows1..10 body exactly error; error exactly code,details,message,request_id,retryable. details{}; retryable false; request_id lowercase UUID shape unique across10 errors, without requiring RFC version bits. Rows1,3,4,10 code ENTITLEMENT_REQUIRED/message Purchase access to this vehicle configuration.; rows2,5,6,7,8 CATALOG_NOT_FOUND/message Catalog resource was not found.; row9 ENTITLEMENT_REVOKED/message Access to this vehicle configuration was revoked. Do not treat error text or status as independent issuer authority.

## No-work snapshot rules

For isolated and final: all counts0; ensure and selector_ensure exactly entered/completed/active0; request lists[]; model_calls/payment_calls0; every provider/source/asset count0; provider traces[] per bank; workers[]; proxy counters0,response_captured false,errors[]. Grant calls9 in both. Isolated reader0/identity11. Held model null, observed views null/empty, worker_exits[] inherited. Enforce terminal snapshot equality for all shared fields; do not require absent reader/identity final keys.

## One implementation task and concrete tests

Modify only the three implementation paths. Add PaidScopeReceiptTests using independently constructed inline data extending predecessor all-twelve fixture and resealing utilities. Copy reviewed literal expected values into tests; never import expected contracts from new production helpers. Populate both target measurements, phase/result/collector copies, terminal rows/immutable digest/replay copies and enclosing artifact hashes explicitly.

- [ ] Red: positive valid22-row scope fixture calls missing inspect_paid_scope_receipts; retain external log. Add shuffled-descriptor/canonical-row positive; randomized internally consistent UUIDs/title; body digest arbitrary well-formed and sizes1/262144 accepted; all inherited gaps/allfalse preserved.
- [ ] Red: independent mutations for each row owner/status/method/route/order; missing/extra/duplicate/reordered row; physical V/C confusion; adjacent/current-bank/unscoped/other-bank substitutions; region query encoding/additional keys; every nested missing/extra field and primitive type; header/error/message/progress/descriptor/cardinality/title/current-revision drift; duplicate error request IDs.
- [ ] Red: consistent rehashed/copy-repaired owner/account/order/config/region/entitlement-ID swaps; other bank article swap; missing/duplicate C/D/R/null canonical rows; null required UUID or C=V; owner-a legacy grant bound to account/config/order again; owner-b revoked/unscoped; missing/extra/duplicate orders, requests, projections and entitlements; malformed/duplicate primary UUIDs; dangling and cross-owner request/entitlement/projection links; order.entitlement_id or dataset_request_id drift; request.correlation_id/order_id mismatch; each organization/account join and each order/request/projection dataset_product_id join changed independently; request vehicle_key/configuration or region drift; terminal matching copies changed together must fail the intended semantic check. Each such negative repairs every affected copy, immutable digest and enclosing artifact hash. Tests must also accept consistently randomized valid product/chain UUIDs and must retain the explicit missing-region-row limitation: changing an unretained CA region fact cannot be independently checked from canonical rows.
- [ ] Red: reader work/identity discontinuity/phase-total drift; source/provider/asset/model/payment/selector/ensure/proxy/worker work; final shared-field drift. Repair all copies/hashes so each failure reaches paid_scope_inventory/row/route/headers/body/counter/binding/work, not an unrelated hash failure. Keep distinct unrepaired hash/identity/seam negatives.
- [ ] Green: implement API and minimal private helpers with static paid_scope_* ContractError codes; keep predecessor code bytes stable and no dynamic imports/command/profile dispatch.
- [ ] Add real ArtifactStore positive and missing/symlink/hash/post-read mutation cases; secret sentinel in synthetic invalid title/query never appears in returned diagnostic/exception codes. Patch new API to raise in existing disabled CLI plan/validate tests, proving no dispatch/no evidence-root I/O in plan/zero counts/allfalse.
- [ ] Controlled red/green: temporarily delete one required owner/route predicate, prove targeted test fails, restore source. Never commit deliberate mutant. Keep logs external.
- [ ] Update runbook with22 observation/four snapshot diagnostics, terminal-state limits, all missing authority and no verified counts.
- [ ] Run exact checks below, commit/push one coherent green milestone promptly, then independent exact-SHA review before coordinator integration.

Checks from implementation worktree:
```sh
python3 -m unittest scripts.dev.test_release_acceptance.PaidScopeReceiptTests -v
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
python3 -c 'import ast,pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ("scripts/dev/release_acceptance.py","scripts/dev/test_release_acceptance.py")]'
git diff --check
```
Check exact diff allowlist and byte equality of r6-release.json/policy/CLI/DTO/predecessor inspectors/limits relative to adopted gate. Use fresh shallow clone exact pushed candidate for focused tests; this is parser-tool verification, never ancestry proof. Reread remote branch SHA and clean worktree. Existing PR200 completion reports92 focused/244 developer/146 autonomy; do not hardcode future counts or reuse those as fresh evidence.

## Coordinator adoption checkpoint and gate record

The coordinator explicitly selected exact source `545f32098a659c75c11e4dd7ad7c00fbc9a2a976` (PR202 completion containing PR200 code `66781084bde3ea382b35b4e33cdeace713f1096a`) for this new docs-only planning branch. This is source adoption for planning, not a merge or application acceptance. Any later rebase requires coordinator ownership and a new exact gate check. Do not alter the separate API21 completion writer, candidate/branch/evidence or inventory. The coordinator remains sole Issue/Project writer. Its live detail6624437136 and Project Source update have now been independently read back; the receipt below authorizes only this docs-only checkpoint commit/push and preflight, with no implementation dispatch.

Coordinator-owned planning allowlist (separate from implementation allowlist); this synchronization handoff additionally authorizes the exact evidence path in item7:
1. Create docs/superpowers/plans/2026-11-04-workshop-r6-paid-scope-receipts.md from reviewed draft.
2. Create docs/agents/tasks/2026-11-03-production-release/r6-paid-scope-receipts.json.
3. Create docs/agents/records/2026-11-04-r6-paid-scope-receipts.json.
4. Update docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md.
5. Update docs/superpowers/plans/2026-11-03-release-acceptance.md.
6. Update docs/agents/tasks/2026-11-03-production-release/queue.json with exact bounded scope and unverified release status.
7. Create docs/agents/records/2026-11-04-r6-paid-scope-tracking-evidence.json containing complete live tracking readback and predecessor preservation.
No implicit catch-all docs permission. Existing canonical runbook is referenced and changed only by authorized builder after gate.

Synchronize identical goal and following five todos in plan/task/record/queue, Issue186 comment and existing Project8 item Source/dependency field; preserve current issue body/predecessor comments/current Project full fields verbatim before mutation; retain every prior pointer and capture readback hashes. Do not create another Project item or mark Done. Serialize tracking writer with coordinator. Required todos:
1. Synchronize closed two-case exact-scope22-observation/four-snapshot contract, literal three-path scope and references; commit/push checkpoint and pass exact-base preflight plus independent review before implementation.
2. Add independent inline red/green fixtures and repaired-semantic/unrepaired-transport adversarial tests for scope/owner/region/legacy/revocation projections, no-work and confined transport.
3. Implement only unselected inspect_paid_scope_receipts after existing paid HTTP chain, add diagnostic IDs/counts and terminal-entitlement gap; preserve predecessor/DTO/CLI/policy/profile bytes and allfalse/unavailable/emptyverified behavior.
4. Run focused/developer/autonomy/syntax/shallow/exact-scope checks, update runbook, commit/push coherent green milestones and obtain independent exact-SHA review.
5. Retain complete paid12/DTO120/final-head180/support/CI/security/image/SDK/license/reviewer/staging blockers; enable no tier/profile and leave API21/live evidence and later collection separately gated.

The current record is `status: synchronized` only after the live readback below; every authorization flag remains false. Its required shape is: goal above; plan_ref new plan; issue_ref Issue186; project_ref Project8; repository_doc_refs existing canonical assembler plan/release-acceptance plan/runbook; todo exact five above; status synchronized only after live identical readback; updated_at actual readback UTC. Task contains exact three allowed_paths/output refs, execution profile and same pre_implementation record. Pin new committed/pushed full40 SHA B (containing all synchronized planning files), not historical/source/tool SHA. Run:
```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-r6-paid-scope-receipts.json --base-sha "$R6_SCOPE_CHECKPOINT_SHA" --repo-root "$R6_SCOPE_WORKTREE"
```
Require exit0/status synchronized/errors[], remote sameSHA, clean owned tree, independent exact-checkpoint approval and explicit coordinator dispatch before builder edits implementation files. A /tmp draft or coordinator natural-language acknowledgement cannot replace this gate.

## Independent review criteria

Review exact checkpoint before code, exact pushed code afterward. Reject any scope/profile/CLI/DTO/evaluator/policy drift, missing predecessor checks, altered missing-family inventory, count promotion, dynamic dispatch, evidence mutation or hidden API21 change. Verify independent test construction and that repaired semantic mutations reach correct new predicates. Rerun new class plus disabled CLI/no-dispatch regression, inspect ArtifactStore freshness and allfalse output. Confirm projection/body-size/hash limits are described honestly, final entitlement rows cannot prove historical revocation, fixture synthetic grants are not actual Stripe/licensed-source proof, and historical candidate cannot be relabeled. Review source/task/checkpoint/code/candidate roles and both GitHub/Project readback/preflight receipts. Final independent PASS authorizes only coordinator consideration of integration; it supplies no release acceptance or deployment authority.


## Live tracking readback — planning only

Issue186 [detail6624437136](https://github.com/lucronn/autodata/issues/186#issuecomment-6624437136) exactly matches the goal/five todos/three-file implementation allowlist/canonical references,3006UTF8 bytes and SHA256 `2f815f6ac0a2cb584f740b5162baa56e759309add23e2096074e2c9af5cedc93`. Project8 existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` Source is996 characters, SHA256 `7dc2f3e86b4b2d7aa8ff225b19be9e4c3eac9ebe580e3d632f1d15700df4d2f9`; Status remains In Progress and all seven other field values match the retained predecessor. Readback captured at `2026-11-04T06:42:35.484222+00:00`. `docs/agents/records/2026-11-04-r6-paid-scope-tracking-evidence.json` preserves the complete current Issue body/all133 comment bodies/full Project item and all fields, plus the coordinator-supplied complete Source before/after. All131 retained historical predecessor comment bodies and Issue body match the prior completion evidence. Newer predecessor comments are preserved from this current capture; no absent pre-update snapshot is invented. The new detail is independently identical to the prepared update text.

Independent draft review identified that predecessor `_paid_pg_rows` does not establish the complete order/request/projection/organization/product chain. This corrected contract assigns all listed joins, strict UUID/cardinality/uniqueness predicates and independently repaired-copy negatives to the new inspector. It also states that R is only the third configuration under the frozen producer contract; no retained vehicle_configurations region row establishes CA. These corrections preserve the synchronized goal/five todos/scope and weaken no acceptance requirement. Exact corrected-draft/checkpoint review remains separately required.

This readback permits only commit/push of the seven-path docs checkpoint and full-SHA preflight. It does not authorize implementation, browser/runtime/provider/cloud execution, profile promotion, verified cases, merge, deployment or cutover. The coordinator remains sole GitHub writer. Any exact pin comment or Project index adjustment must be proposed to the coordinator before its mutation; this worker performs none.
