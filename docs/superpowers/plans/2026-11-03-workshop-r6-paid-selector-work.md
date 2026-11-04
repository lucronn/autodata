# Paid selector-work receipt consistency implementation plan

> **For agentic workers:** Use superpowers:executing-plans after independent exact-checkpoint review and passing pinned preflight. No implementation is authorized by this planning document alone.

**Goal:** Add one internal paid selector-work receipt consistency layer for the two GrantBeforeWork bank cases; preserve unavailable results, no verified cases and every disabled profile and false authority flag.

**Architecture:** Extend the existing internal paid common → PG → migration receipt chain with one disconnected selector-work inspector. It interprets only metadata selector requests, fixed provider trace routes and work-counter relationships for `TestPostgresPaidCatalogGrantBeforeWork` crossed with Bankone/Banktwo. Receipt consistency supplies no execution, authorship, authorization or product-verification authority.

**Tech Stack:** Python standard library, existing confined ArtifactStore, strict JSON and explicit typed functions; inline synthetic unittest fixtures.

**Spec:** [Canonical assembler boundary](2026-11-03-workshop-product-evidence-assembler.md), sections 1 and 4a/4b; [runbook](../../verification/release-acceptance-runbook.md).
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8
**Source inspection SHA:** `eddcf724028683dbb083191e4f8c42064b866bf0`.
**Status:** Plan only; independent coordinator gate review remains required. The exact checkpoint SHA is an external preflight input, never a self-referential committed field.

## Global constraints

- Execution: `gpt-6.1-sol`, medium, Fast/priority, no fallback.
- Prospective implementation allowlist is exactly `scripts/dev/release_acceptance.py`, `scripts/dev/test_release_acceptance.py`, `docs/verification/release-acceptance-runbook.md`. No standalone fixtures or additional paths.
- This planning checkpoint modifies documentation/task/record/queue only in its owned worktree. Root integration checkout and active acceptance Docker remain untouched.
- No Docker/browser/provider/cloud/DNS/secret operations, execution of retained SQL or supervisor code, candidate imports, arbitrary schema dispatch, policy/controller/runner/workflow changes, profile promotion or deployment.
- Preserve 2 MiB envelope, 4 MiB raw JSON, 8 MiB per-file and 64 MiB total transport ceilings; every read uses declared artifacts and existing confined reopen/recheck rules.
- Existing `r6-release.json` product_evidence profiles remain byte-for-byte disabled/unpromoted. The new task references that profile source and carries no independent enabling contract.
- This successor authorizes only the family below after review; broad historical first3 plans do not expand this dispatch. DTO, browser, licensed bodies/media, SQL semantics, migration execution, live/staging enrollment, CI/ancestry and authority remain separately gated.

## Inspected source and private evidence boundary

At the source SHA, assembler SHA256 is `fe4fa7fe6397ab43c3027e2b899b76d53a23cda045375e434a22c91cf0b68716`; test SHA256 `dd219d3f30a88aabb757e8af11fb0209013716cc4e427d8c59b1df553cc35640`. The Go producer `apps/api-go/postgres_catalog_access_test.go` hashes to `0775d2a5d30a990be41f177a4cf6e16b6703d75442b3b690c08597934bdadb31`; collector `scripts/dev/workshop_paid_access_smoke.py` to `1acaa6bffaf35b122b40757c78dbf01fb06244803720c951b2b828133232632f`. They are read-only schema references, not implementation paths.

Historical private receipt root `/tmp/autodata-paid-access-040-acceptance-2de36a1-v2/artifacts` retains collector SHA256 `d153111cc265b04536ad893951e5d89023428b73de8713491673622bd5775bc2`, candidate `2de36a1305bfbe45992995e6caf0ba52f30fddcc` and external v2 supervisor SHA256 `dbb39a6ac987df69f0d9e9085ee08b62e2fa4ca497abefd8b3cae854c9c50ec4`. Read-only inspection observed the closed shapes below in both banks. These historical identities cannot be relabeled to this source SHA, the new checkpoint or a future candidate. Do not copy private PG/HTTP/session bytes into the repository, Issue or test fixtures. Tests independently construct synthetic safe identifiers and JSON.

## Closed typed contract: one family

Public internal signature:

```python
def inspect_paid_selector_work(store, *, candidate_sha, trusted_base_sha,
    profile_sha256, input_manifest_sha256, host_before_sha256,
    expected_driver_sha256, profile_version='paid-selector-v2') -> dict:
    # First invoke inspect_paid_migration_receipts with these same arguments.
    # Read fixed case measured-runtime.json references through ArtifactStore.
    # Apply the following literal checks; never select this function from CLI.
    ...
```

No new producer format is introduced: the explicit selector remains `paid-selector-v2`, raw collector/case/measured receipts remain schema version 1. The prior common/PG/migration chain validates all twelve identities/hash/copy seams first. Apply the added semantics only to literal `TestPostgresPaidCatalogGrantBeforeWork-bankone` and `...-banktwo`. Other ten cases keep exactly their existing validation depth. Fixed paths are `paid-access/{bank}/TestPostgresPaidCatalogGrantBeforeWork/measured-runtime.json`, plus the existing matching case/result/measurement references already bound by the chain. No filesystem discovery or filename dispatch.

The prior closed snapshot schema is unchanged. Examine six phase names `before`, `selectors`, `unpaid`, `expired`, `paid_cold`, `unavailable`, plus `final_snapshot`: fourteen diagnostic snapshots total. `final_snapshot` intentionally omits `reader_calls` and `identity_checks`; never invent them.

Each `selector_ensure_requests` item has exactly eight fields:

| Field | Exact contract |
| --- | --- |
| `completed` | bool, literal true |
| `duration_seconds` | finite JSON number, excluding bool/string, exact-decimal inclusive 0–120 |
| `started_at`, `finished_at` | timezone-aware UTC timestamps using existing parser; case start <= start <= finish <= case finish; monotonic duration is not asserted equal to wall-clock difference |
| `payload` | closed scope-specific object below |
| `request_id` | literal empty string, the frozen v2 test transport value |
| `scope` | exactly `makes`, `models` or `configurations` |
| `status` | integer excluding bool, literal 200 |

Parse receipt number tokens with existing strict parser's `exact_floats=True` (only for this explicitly invoked layer), then compare `int`/`Decimal` without binary-float conversion. Preserve existing default parser behavior and limits. Do not canonical-serialize Decimal receipt objects through the existing float serializer; perform typed field equality for this family. A negative nonzero tiny decimal must not underflow to accepted negative zero; 120 plus a tiny decimal must not round to 120. Existing nonfinite/overflow rejection stays intact.

Payload exact key inventories:

| Scope | Keys and values |
| --- | --- |
| makes | `scope: makes`, `year: 2024` (exact int), `region: US`, `idempotency_key` |
| models | makes inventory plus `make: example`, with `scope: models` |
| configurations | models inventory plus `model: car`, with `scope: configurations` |

`idempotency_key` is a string matching `^catalog-hydration:[a-f0-9]{24}$`; the three scope keys are distinct. No article/vehicle/configuration IDs or additional payload fields are accepted. This layer checks shape and retained stability only: it does not rederive this key from candidate code or assert independent request provenance.

Before has no selector requests and exact selector counters `{entered:0,completed:0,active:0}`. Each later phase and final has exactly three requests with the exact scope set once each and `{entered:3,completed:3,active:0}`. Request list ordering may reflect concurrency: initial inventory is a three-element list in any order. Each later list must preserve the selectors list and all item fields exactly, compared by typed parsed values; independently reordering a later copy is drift. Additional/missing/duplicate requests fail.

Provider calls are closed two-bank integer maps. Before has zero per bank and empty traces. Selectors and every later phase/final each have three per bank and the exact unordered route set below once each; trace order may differ between banks due to concurrency, but each later per-bank list must equal its selectors list. Compare literal strings so duplicate params, encoded path tricks, absolute URLs, fragments, extra query keys and alternative route spelling fail:

```text
/v1/catalog/makes?year=2024
/v1/catalog/models?year=2024&make=example
/v1/catalog/configurations?year=2024&make=example&model=car
```

For all fourteen snapshots, `ensure == {entered:0,completed:0,active:0}` and `ensure_requests == []`; all six `counts` keys from `PAID_PG_COUNT_TABLES` are zero; source/asset calls are zero for both banks; model/payment calls are zero. Proxy has its existing exact six fields with all four integer counters zero, `response_captured: false`, `errors: []`; workers are empty. The six phase snapshots have `reader_calls: 0`. These stronger literal fixture expectations are observed at both banks and are consistent with the existing Go `paidSelectorsMetadataOnly`/`paidWorkUnchanged` predicates. Preserve intentional mutable account/session/grant/SQL rows; no whole-snapshot/immutable-row equality across phases.

`grant_calls` and `identity_checks` keep prior nonnegative type checks; require phase progression to be nondecreasing in the explicit order before→selectors→unpaid→expired→paid_cold→unavailable, and selector phase both zero. Require final grant_calls equal unavailable grant_calls. Do not hard-code historical incidental grant/identity counts or invent final identity counters. HTTP status/body/header observations remain opaque under the prior layer: these work observations alone do not prove denial/status outcomes.

Result extends the prior migration result with exactly `observed_selector_case_ids` (two literal IDs in bankone/banktwo order) and `observed_selector_snapshot_count: 14`; these are diagnostics and add zero logical cases. Preserve prior observed IDs and migration/PG diagnostics. Always retain `status: unavailable`, `complete: false`, `verified_case_ids: []` and all five FLAGS false. Retain every inherited missing family, including `paid_selector_work_and_model`, then add exactly `paid_selector_http_outcomes` and `paid_selector_request_provenance`. HTTP denial/metadata content, model/lifecycle semantics, source/PG provenance, authority and every other family remain incomplete. Never remove a missing family because this layer passed.

## Task 1: selector receipt inspector and adversarial tests

**Files:** modify only the three allowlisted paths. Consumes the existing paid chain and confined store. Produces only the internal function and additive diagnostics above.

- [ ] Add a test class with independently constructed inline synthetic all-twelve common/PG/migration fixture, populating selector receipts only in the two target cases. The new positive invocation fails initially because the function is absent; record that red output outside the repo.
- [ ] Add independent mutations below, repairing affected parent hashes/copies in each synthetic fixture so rejection exercises the new semantic check rather than an unrelated preexisting digest mismatch. Also keep dedicated un-repaired copy/hash mutations to prove existing chain checks remain active.
- [ ] Implement the explicit function and small private typed helpers in release_acceptance.py. Reuse fixed chain/inventory/identity/confinement checks; exact-decimal parse target receipts from confined `store.read` bytes and enforce existing reserved identities, never import candidate modules.
- [ ] Exercise at least one positive and each transport/mutation class through the real confined ArtifactStore; call recheck before returning. CLI tests patch this new inspector to raise if dispatched in fixture/staging plan or validate. Positive inspection remains unavailable with no verified IDs and false flags.
- [ ] Update the runbook with exact interpreted fields, opaque families and diagnostic limits. Run bounded checks below, commit/push a coherent three-path candidate, and request independent exact-SHA review. Do not execute actual acceptance or promote trust.

Required independent negative mutations: each unknown/missing receipt or payload field; bool/string/null/nonfinite durations or status; exact-decimal -tiny and 120+tiny (with 0 and120 accepted); reversed/out-of-case/non-UTC timestamps; request_id changed; bad idempotency prefix/length/uppercase/duplicate scope key; wrong year/make/model/region/scope; duplicate/missing/extra scopes; entered/completed/list mismatch; changed later request payload/timestamp/order; source/asset/model/reader/payment work increments; article ensure or any six count increments; proxy counter/capture/error mutation; nonempty workers; provider count mismatch; missing/extra/duplicate/absolute/escaped/fragment/query-mutated routes; changed later trace order; decreasing grant/identity counters and final grant drift; cross-bank/candidate/base/profile identity drift; mixed historical candidate; unknown selector version; raw hash/copy mismatch; missing artifact, symlink replacement or post-read mutation; accidental CLI dispatch, any true flag, verified ID, dropped missing family, DTO/profile edits or nonzero CLI count.

## Bounded verification and concrete todo

Run after the independent gate and implementation, from the owned checkout, with logs outside the repo:

```sh
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
python3 -c 'import ast,pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ("scripts/dev/release_acceptance.py", "scripts/dev/test_release_acceptance.py")]'
git diff --check
```

The focused module includes existing shallow-clone and disabled-profile regressions. Exact changed-path comparison must equal a subset of the three implementation paths relative to the authorizing checkpoint. No Docker/provider/browser/cloud command belongs to these checks. Synthetic parser checks never establish actual fixture acceptance.

Concrete synchronized todo:

- [ ] Synchronize this single selector-work family, closed schema, three-path allowlist and todo in Issue186/Project8 and canonical plan/task/record/queue; commit/push and pass pinned preflight before independent gate review.
- [ ] Add failing inline synthetic tests for closed selector request fields, exact typed payloads and route inventories, phase counter contradictions, numeric boundaries, copy seams and confined-store mutation.
- [ ] Implement only inspect_paid_selector_work chained after inspect_paid_migration_receipts, with two fixed observed selector identities and fourteen phase/final snapshot diagnostics, retaining every prior missing family and adding explicit selector HTTP and request-provenance gaps.
- [ ] Keep plan and validate disconnected from every internal typed inspector; preserve zero CLI counts, no verified case IDs, unavailable/incomplete results, all profiles disabled, enabled_tiers empty and every verification/deployment/cutover flag false.
- [ ] Run focused/developer/autonomy, syntax, shallow-clone and three-path scope checks; update the runbook, commit/push the coherent candidate and obtain independent exact-SHA review before integration.

## Exact planning preflight and handoff

Commit/push the synchronized documentation checkpoint B, then run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-r6-paid-selector-work.json --base-sha <full-B-SHA> --repo-root <owned-worktree>
```

Require `status: synchronized`, `errors: []`; independently review B, all exact schema decisions, closed scope and live Issue/Project readback before builder dispatch. The later implementation candidate requires its own independent review and integration. Current same-head product180 execution, its failures/results, complete final-candidate support/CI/security/image evidence and registered provenance remain coordinator-owned and separate. No final180, staging, deployment or cutover claim follows from this plan.

Live tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6619139974; exact Issue body SHA256 `1149c8c6bacccad6fe9079a444eb8adff56095dabea535a939b92443728a1765`. Project8 existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, status In Progress, source/dependency field SHA256 `9682bd24f8eb74c2c85bd3d3f8926544ea74ed5a9fbd7c0cc57ce2b7d536275d`, read back `2026-11-04T00:30:56.950795+00:00`. Full prior Project field (SHA256 `0a1d7564da5b9e26b365fc471272c5fc0c092e409abe53efbbf8fe185cb7089d`) is preserved verbatim in that Issue comment before its compact index update; the initial compact index omitted prior DTO comment6617902111, discovered during independent review. The corrected readback below supersedes that index-completeness claim; the original comments/hashes remain retained.

## Tracking correction after independent review

Independent review of checkpoint `2222ce2123016f35a192fea312e9ff19749840b8` found missing prior DTO comment `6617902111` in the compact Project index. The full predecessor field was already retained verbatim in original plan comment6619139974. Restored that exact ID by literal insertion beside DTO6618124676; every other field byte is unchanged. The 816-character corrected field was reread exactly and machine comparison of predecessor/current comment-ID sets found no omissions. Existing Project item remains In Progress; implementation still awaits independent gate re-review.

Correction Issue receipt: https://github.com/lucronn/autodata/issues/186#issuecomment-6619194720; body SHA256 `7aa718e316d14718354e2206242f8470fc945bdcbfa1edf20c794c02e4de6db3`. Corrected Source/dependency field SHA256 `293ca347ec9b6848b5e8e339b8dce6a0c5bdbe02019ef5feae45e0cbc5db4f93`, read back `2026-11-04T00:34:12.496441+00:00`. Preserve original checkpoint receipt https://github.com/lucronn/autodata/issues/186#issuecomment-6619164328, body SHA256 `02829f35c348a6466e0d64f0afac56427aa4b1e9815bfe902edec6a0cef45b18`, and its pre-correction field SHA256 `60cdeedf507f0f0f0b91cc08da08a357099f75dc08e9a6d1b1086e12b575ac65`. Original plan comment/hash and first planning-readback/predecessor hashes above remain historical facts. The task and record retain both original receipt sets plus this corrected readback; original all-ID-retained claims are superseded. Goal, five concrete todos, schema, original three-path implementation allowlist and disabled authority remain unchanged. Commit/push a new docs-only checkpoint and pass its full-SHA preflight for re-review; no implementation is authorized.
