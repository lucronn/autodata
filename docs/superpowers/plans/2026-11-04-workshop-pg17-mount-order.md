# Workshop PG17 Complete Mount-Record Ordering Successor Plan

**Goal:** Correct only order-sensitive acquisition Mounts inspection comparison using complete records keyed by unique exact Destination, retaining all raw/canonical hashes, red receipts and unchanged acquisition guards.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Draft base: `da1f42a974b8131f4a771986ab7af9704c6576a1`; adopted gate `76fd86e5a356ae611d643e621f9ae03660d50206`.

## Exact scope and red evidence

Local draft only until coordinator tracking-slot release, live Issue/Project synchronization, committed checkpoint and pinned passing machine preflight. No Docker/create/start/export/download/retry/install/harness action while planning. Independent exact-checkpoint review/adoption and fresh Task1A dispatch remain mandatory. This corrects only top-level inspection `Mounts` array comparison: array record order is irrelevant, every record field remains relevant. All original configuration expectations, `HostConfig` equality, bind sources/permissions/propagation, image/payload/network/caps/resources, created-copy-before-export ordering, archive bounds/type/empty checks, full diff/context/27baseline/signature/exit audits and exact-owned cleanup remain unchanged. Offline stages/Task2/production authority do not expand.

Raw evidence directory `/home/corp/autodata-evidence/pg17-bind-target-prep-20261104-01/evidence`:

- `task1a-result.json` SHA256 `6db4e39f3b01adb90b42985b44a6949b6670774fc8fc9e0f84ab7be96c4f5c4d`.
- `task1a-diagnosis.json` SHA256 `5654ed1637e63f2facb6ee2b52a8589fb685e7996bac0e44498b130db2376695`.
- `created-export-before.stdout` SHA256 `67bc8ce15fc8b8b98c69e7a827f36eafd2ce4d1b330c40addbe09bb78cd07f3e`.
- `created-export-after.stdout` SHA256 `cf66f6a4aa14ace4a810c5ca67d2833ea48ca7bf7eb902616284c2de38e0ac76`.

Fresh exact container `95b5d80d07ade5f47a62c471c23922f30fd06e4a279cb0443e10055936ec1438` stayed created/never-started. All inherited prestart copies and unchanged27 comparison passed before the bounded created export (exit0,299682304 stdout bytes,0 stderr, no timeout/overflow). Then order-sensitive list equality rejected only record order `/apks,/control` versus `/control,/apks`; complete State and HostConfig were identical. Exact container removed/absence verified, normalized volume inventory unchanged;0 APKs fetched. No retry. The structural parser reached post-inspect comparison, but normalized target metadata receipt was not yet written and the exact owned export archive was deleted during cleanup; do not infer or recreate missing proof. This attempt remains failed.

Full mount records are canonically equivalent: Type=bind, exact Sources under that fresh private run's `/apks` and `/control`, Destination respectively `/apks` and `/control`, Mode empty, RW respectively true/false, Propagation=rprivate. Canonical JSON SHA256 `7692124c79b10f42cb12fa67a67ed6215f8c8fccaf2328d81fa9c8157c475c94` uses sorted complete records and keys with compact comma/colon separators. Historical33 APKs from the previous overlay attempt remain quarantined and never reusable; this zero-APK failure does not change them.

## Fixed comparison contract

For every acquisition top-level `Mounts` inspection comparison, including complete prestart expected-config validation and created/stopped export before/after validation, replace only order-sensitive list equality with equality of canonical complete-record JSON bytes below. Re-run the full original bind inventory/configuration validator on actual input; canonical equality alone never approves configuration. The exact two planned Sources, Type, RW, Mode and Propagation must retain their prescribed values; no missing or unexpected record field is approved by this amendment. Do not normalize `HostConfig.Mounts`, other arrays, source paths, strings, booleans or values. Full original HostConfig and State checks remain as specified by each phase.

Input is the complete raw inspect document from the same full ID/image/gate, with original phase/ownership checks. Retain original bytes and their SHA256 before parsing. Reject duplicate JSON object keys, non-JSON constants, wrong top-level shape or invalid encoding rather than let the JSON decoder silently overwrite fields. `Mounts` must be a list of exactly two complete dictionaries with unique string Destinations exactly `/apks` and `/control`; unknown, duplicate, missing or extra destinations fail. Never build a map before duplicate validation, select a field subset, default a missing field, strip unknown fields or compare only path/RW. Complete record key additions/removals/type/value changes must alter canonical bytes and reject against the unchanged expected/before record.

```python
import json
import hashlib
EXPECTED_DESTINATIONS = {'/apks', '/control'}
def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result
        result[key] = value
    return result

def parse_inspect(raw):
    def reject_constant(value):
        raise ValueError('non-JSON constant: ' + value)
    result = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                        parse_constant=reject_constant)
    assert type(result) is list and len(result) == 1 and type(result[0]) is dict
    return result[0]

def canonical_mounts(mounts):
    assert type(mounts) is list and len(mounts) == len(EXPECTED_DESTINATIONS)
    seen = set()
    for record in mounts:
        assert type(record) is dict
        destination = record['Destination']
        assert type(destination) is str and destination in EXPECTED_DESTINATIONS
        assert destination not in seen
        seen.add(destination)
    assert seen == EXPECTED_DESTINATIONS
    ordered = sorted(mounts, key=lambda record: record['Destination'])
    return json.dumps(ordered, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')

def compare_complete_mounts(before, after):
    left, right = canonical_mounts(before), canonical_mounts(after)
    assert left == right
    return hashlib.sha256(left).hexdigest()
```

The host receipt must retain both raw inspect filenames/hashes, phase/full ID/image/gate, canonicalization version/complete-record contract, exact destination inventory, before/after canonical SHA256 (equal on success), original config/phase validation results and full original Mounts arrays. No success receipt may hide a rejected raw document. This is a collection-order correction only; it adds no Docker command or retry authority. New fresh attempts still require both created and stopped structural export receipts and all27 baseline/diff/cleanup proof; the red historical arrays alone cannot substitute.

## Verification and concrete todo

Execute only pure host predicates during planning: retained before/after arrays must fail old list equality and pass complete canonical equality with the recorded hash. Synthetic mutations must reject duplicates, missing/extra/unknown destinations, missing or extra record fields, Source/Type/RW/Mode/Propagation changes and type drift; JSON duplicate-key/nonfinite/malformed input must reject. Raw facts remain distinct from synthetic results. No container, package, harness or production result follows.

- [ ] Synchronize the narrow mount-order plan, exact red receipts and complete-record fixtures with Issue186/Project8/canonical docs only after coordinator releases tracking slot; commit/push and pin passing full-SHA preflight for independent review.
- [ ] Require independent exact-checkpoint review/adoption and fresh coordinator Task1A dispatch before any new Docker operation; use a new private run and never restart/reuse prior failed containers or APKs.
- [ ] Retain raw before/after inspect bytes and SHA256; canonicalize only top-level Mounts array record order by unique exact Destination, require exactly /apks and /control and preserve every complete record field/value.
- [ ] Require original complete config/mount predicates plus canonical equality at every acquisition Mounts comparison; duplicate/missing/extra destinations, field/type/value drift, invalid JSON or ambiguous input fail closed.
- [ ] Keep all predecessor created-copy/export/diff ordering, structural/exit/signature/baseline/resource/network/payload/cleanup bounds and offline/Task2 separation unchanged; no planning Docker/retry/download/harness or readiness claim.

Mount-order successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621665171 and Project8 readback at `2026-11-04T03:23:07.931845+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned mount-order successor checkpoint: `cdbedc871104484d931113ce74c84be0b8ba449e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621669759. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed complete mount-record ordering adoption: plan only

Adopt independently approved source gate `cdbedc871104484d931113ce74c84be0b8ba449e`, receipt `1e43e64a9b1b8237bbc9656aa311d0c7d13d5698`; exact reviewed plan SHA256 `8eb158a7101959b23a096487366692b6f8990c73e6ad4b79c303eb4cae5a302b`. Source review evidence `/tmp/autodata-pg17-mount-order-cdbedc87-review.json` retained as `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-review.json` with original hash. Adoption branch `codex/workshop-pg17-mount-order-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order-adoption.json`. Live tracking synchronized after coordinator slot release. Root must verify the full adopted-SHA preflight and issue fresh Task1A dispatch before any runtime action.

The sole correction is top-level Mounts array comparison by complete records keyed/sorted by unique exact Destination. Retain every record field and raw before/after inspect hashes plus canonical hash; missing/extra/duplicate destinations, field additions/removals/type/value drift or malformed/duplicate-key JSON fail closed. All original config predicates and HostConfig equality remain. No extra Docker command, mount, capability, source, network or retry authority. All inherited created-copy27-baseline-before-export/diff ordering, exact empty underlying-target proof, bounded exports, full stopped diff/context/baseline/signature/exit audits and exact-owned removal/absence/volume inventory remain mandatory.

The prior created-state attempt remains failed with0 APKs; result SHA256 `6db4e39f3b01adb90b42985b44a6949b6670774fc8fc9e0f84ab7be96c4f5c4d`, diagnosis SHA256 `5654ed1637e63f2facb6ee2b52a8589fb685e7996bac0e44498b130db2376695`. Missing structural metadata is not inferred retroactively. Historical33APKs remain quarantined and never reusable. Root must verify full adopted-SHA preflight and separately dispatch any new Task1A. No adoption Docker/create/start/export/retry/download/install/image commit/PG startup/harness action; offline stages/Task2 and production/provider/cloud/runtime authority unchanged. All readiness remains false.

Concrete adoption todo:

- [ ] After coordinator tracking-slot release, synchronize exact independent approval/plan hash and unchanged Task1A scope in Issue186/Project8/canonical docs, preserve CURRENT prior Project index verbatim/hash, commit/push and pin full-SHA preflight.
- [ ] Only after root verifies adopted pinned preflight and dispatches fresh Task1A, use a new exact-owned private run; compare complete Mounts records by unique exact Destination, retaining raw before/after/canonical hashes and rejecting any missing/extra/duplicate destination or field drift.
- [ ] Keep all inherited complete config checks, mandatory prestart cp27 baseline comparison BEFORE created export/diff, bounded created/stopped empty-target proof, full stopped diff/signature/exit audits and exact-owned cleanup/absence/volume inventory unchanged.
- [ ] Preserve all prior failed/quarantined outputs and red receipts; never reuse historical33APKs or restart/reuse failed containers; no offline simulation/install/image commit/PG startup/harness on this adoption turn.
- [ ] Keep Task2/production/provider/cloud/runtime actions separately unauthorized and all readiness unverified; adoption alone is not a fresh retry dispatch.

Reviewed mount-order adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621749496 and Project8 readback at `2026-11-04T03:28:59.162164+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed mount-order adoption checkpoint: `3c96b04df9ff4b7929ca8955a92d89eef6cc7617`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621754534. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 acquisition diagnostics and structured volume receipts: plan only

Correct only acquisition diagnostic false positives and volume inventory serialization by anchored status checks and bounded structured complete-volume inspection, retaining all existing guards and failed-output quarantine.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-receipts.md`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-receipts.json`. Retained second-attempt result/diagnosis hashes and full offline replay in `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-evidence.json`. Attempt exited0 and passed structural/context/baseline guards, then failed host substring/Labels CSV order checks; all33 fresh APKs quarantined NEVER reusable, prior33 also never reusable. Correct only anchored status/empty-stderr diagnostics and bounded read-only complete structured volume inspect metadata by unique Name; every field/value retained, only JSON key order ignored. Explicit new metadata-read authority requires reviewed/adopted gate/root dispatch. All other Task1A/Task2 constraints unchanged; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Replay the revised fixed pure predicates against complete retained second-attempt evidence and all existing positive/negative fixtures; synchronize goal/plan/todo/red evidence/structured inventory authority with Issue186/Project8/canonical docs after coordinator slot release; commit/push and pin full-SHA preflight.
- [ ] Require independent exact-gate review/adoption and root verification/fresh Task1A dispatch before any Docker/retry; use a new private exact-owned run, never historical quarantined APKs or failed containers.
- [ ] Use unchanged bounded fixed acquisition payload and source/signature/index/hash checks; classify only empty stderr plus successful supervised attach/stopped status and reject anchored diagnostic forms, preserving full raw output and hashes.
- [ ] Before create and after exact-owned removal, capture bounded volume ls names and one bounded read-only structured volume inspect per exact name; compare complete objects by unique Name preserving every field/value and ignoring JSON object key order only.
- [ ] Keep mandatory27 prestart copies BEFORE first created export/diff, complete Mounts canonical guard, empty underlying target audits, full stopped diff/context/baseline/exit checks and owned cleanup unchanged; no offline/install/image/PG/harness/production readiness follows.

Acquisition-receipts successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621817348 and Project8 readback at `2026-11-04T03:33:51.920926+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned acquisition-receipts successor checkpoint: `4bc40e26ca12521be8f20282b897f5af68d0195e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621820832. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 diagnostic Unicode Cc review correction: plan only

Correct only the blocked acquisition diagnostic character filter to reject Unicode Cc controls except LF/tab; preserve all existing receipt guards, quarantine and runtime denials.

Corrected plan `docs/superpowers/plans/2026-11-04-workshop-pg17-control-filter.md`; record `docs/agents/records/2026-11-04-workshop-pg17-control-filter.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-control-filter.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.json`. Prior4bc40e26 remains independently BLOCKED for DEL/C1 acceptance. Only diagnostic unicodedata import/Cc predicate changed, LF/tab sole control exceptions; complete83-case offline replay plus65 Cc probes pass (148total/0fail). All structured-volume and predecessor constraints unchanged; both33APK sets quarantined NEVER reusable. Independent exact-corrected-checkpoint re-review/adoption/root dispatch required; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Preserve exact blocked gate/plan hash and reproduced DEL/C1 negatives; update only diagnostic Cc filter/import, rerun complete83-case pure/replay suite plus65 Cc probes, then synchronize Issue186/Project8/canonical docs after coordinator tracking-slot release.
- [ ] Commit/push docs-only corrected checkpoint, pin passing full-SHA preflight and exact tracking readback while preserving CURRENT Python SIGTERM and PG predecessor index verbatim/hash.
- [ ] Require independent exact-corrected-checkpoint re-review/adoption, root verification and fresh Task1A dispatch before any Docker/retry/download/harness; previous blocked gate grants no adoption authority.
- [ ] Keep structured complete volume metadata collection/comparison and every original source/payload/config/mount/copy/export/diff/baseline/signature/cleanup bound unchanged; both33APK sets remain quarantined NEVER reusable.
- [ ] Retain all red receipts as failed and offline replay as predicate evidence only; no retrospective acceptance, offline install/image commit/PG startup/harness/production action or readiness claim.

Unicode Cc corrected successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621857074 and Project8 readback at `2026-11-04T03:36:44.664156+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned Unicode Cc corrected successor checkpoint: `b96a68e59a370314a207e67b98d67a9949584432`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-control-filter-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621859742. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed Cc-safe acquisition receipt adoption

Adopt independently approved corrected gate `b96a68e59a370314a207e67b98d67a9949584432`, receipt `eee037dd1857cec1d0817b1b3421c7280c9284f6`; exact reviewed control-filter plan SHA256 `ad2a433f532e1b7b8000588d126d9789392f6e593a5c460681b900bff403420e`. Approval was relayed directly by coordinator after independent re-review. Historical predecessor4bc40e26 remains a blocked superseded checkpoint; this adoption consumes only the corrected approved chain. Adoption branch `codex/workshop-pg17-receipts-adoption`; record `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-receipts-adoption.json`.

The fixed classifier requires empty stderr and zero successful supervised/stopped status, rejects anchored diagnostic forms, and rejects every UnicodeCc character except LF/tab. All original source-output/index/key/signature/package/hash checks remain mandatory. Structured volume metadata uses bounded read-only ls names plus one complete inspect object per exactName: <=32names,60s total inventory,10s each inspect,512KiBstdout/64KiBstderr each,16MiB totalstdout/2MiBstderr. Exact same Name set; compare COMPLETE objects including all fields/values and null/map distinctions, ignore only JSON object key order; duplicate/missing/extra names/fields or any drift fail. Raw/hash/canonical receipts are mandatory. No CSV Labels substitution or four-field projection.

Full predecessor chain retained: exact cached image/payload/repositories; no source/secret bind; private inherited PGDATA override plus original tmpfs/binds; original network/caps/security/resources/output/deadline bounds; complete config and uniqueDestination Mounts records; ALL27 inherited prestart cp snapshots+unchanged comparison BEFORE first created export/diff; bounded created/stopped underlying empty target proof; complete stopped diff/context/baseline/signature/exit audits; exact-owned stop/rm--volumes/absence/structured inventory proof. No acquisition commit/restart/reuse; no arbitrary retry/guard change. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged.

Both historical33APK sets (overlay first and bound-target second payload attempts) remain quarantined, unaccepted and NEVER reusable. Red result/diagnosis and missing prior structured proof are not rewritten. Pure148-case/replay success is predicate evidence only. Root must independently verify full adopted-SHA preflight and issue a FRESH Task1A dispatch before any new Docker operation. This docs-only adoption performs no Docker/create/start/export/retry/download/install/image/PG/harness/implementation or production action; no readiness follows.

Concrete adoption todo:

- [ ] Synchronize exact corrected independent approval/plan hash and full Task1A guard chain in Issue186/Project8/canonical docs while preserving CURRENT prior Project index/detail verbatim/hash; commit/push and pin full-SHA passing preflight.
- [ ] Require root independent adopted-gate verification and FRESH Task1A dispatch before any Docker/retry; use a new private exact-owned run and never historical failed containers/APKs.
- [ ] Use the fixed anchored diagnostic/status classifier rejecting all UnicodeCc except LF/tab, empty stderr and successful supervised/stopped status; retain complete raw outputs/hashes and all original source/index/signature/hash checks.
- [ ] Collect complete structured volume inspect objects for exact boundedls names before create/after owned removal:32names/60s inventory/10s perinspect/512KiBstdout64KiBstderr perinspect/16MiB totalstdout2MiBstderr; compare complete objects by uniqueName, all fields/values preserved and only JSON key order ignored.
- [ ] Keep all inherited image/payload/network/caps/resources/private mount guards,27 prestart copies BEFORE first export/diff, complete Mounts comparison, bounded empty underlying target exports, full stopped diff/context/baseline/exit and owned cleanup/absence checks; both33APK sets remain quarantined NEVER reusable.
- [ ] No adoption Docker/retry/download/install/image commit/PG startup/harness/implementation/integration/production/provider/cloud action; offline stages/Task2 separate and all readiness remains unverified.

Reviewed Cc-safe acquisition receipt adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621879747 and Project8 readback at `2026-11-04T03:38:22.919883+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed Cc-safe acquisition receipt adoption checkpoint: `691f187302440509c23da99f4fb9e1adb9cd52a4`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621883014. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 independently approved frozen closure: docs-only index

Record independent acceptance of the exact Task1A frozen signed33APK closure as input only, preserve acquisition/cleanup evidence and keep Task1B/image/Task2 unauthorized pending a new gate/review/root dispatch.

Acceptance plan `docs/superpowers/plans/2026-11-04-workshop-pg17-closure-acceptance.md`; record `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-closure-acceptance.json`; exact evidence index `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-evidence.json`. Executed691f187 result SHA19002cbf07ce2879e277e1a3e7bc1d69ac28ae8e919e29a85bc4d7a415ee3d43; frozen33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238. Independent audit approval saved at `/tmp/autodata-pg17-task1a-closure-review.md`, SHA256 `bb0173a6f7a46f52fd7a4c3bfbcfcf00d2db5714f179abfe1124675a69616b5b`, and relayed directly by coordinator; all174receipt refs/33host hashes verified, exact cleanup/absence/four-volume equality passed. Accepted as frozen input only; raw pending-review status remains immutable. NEW Task1B gate/review/root dispatch required; offline simulation/install/image/Task2 remain unauthorized/unexecuted, both prior33APK quarantines NEVER reusable. JS deadline slot released; frozen-input acceptance index synchronized. No Docker/install/harness.

Concrete todo:

- [ ] After JS deadline coordinator releases Issue186/Project8 slot, synchronize exact reviewed closure/result/manifest/hash acceptance in Issue186/Project8 and canonical docs, preserving CURRENT full index/detail verbatim/hash; commit/push and pin docs-only full-SHA preflight.
- [ ] Keep raw Task1A receipts and accepted-apk-manifest bytes immutable; use this adjacent acceptance index to record independent review without rewriting the original pending-review manifest status or either failed/quarantined attempt.
- [ ] Accept only exact33APK filenames/versions/architectures/hashes in the pinned manifest as future input; verify all host hashes again before any later authorized consumer and reject mutation or substitution.
- [ ] Require a NEW decision-complete synchronized Task1B gate, independent review, root verification and fresh dispatch before offline simulation/install/image commit or toolchain inspection; no execution authority follows from closure acceptance.
- [ ] Keep original Task2 PG startup/harness separately unauthorized, all runtime/production/grants/services/deployment readiness unverified, and both historical33APK sets quarantined NEVER reusable.

Frozen-input closure acceptance synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621963547 and Project8 readback at `2026-11-04T03:44:34.583302+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Input closure independent approval recorded; NEW Task1B synchronized gate/review/root dispatch required; no Docker/install/image/PG/harness actions.

Pinned frozen-input closure acceptance index checkpoint: `04093a5e176499e7d8de18e9573f9fea3abe9d3a`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621970383. Frozen input independently accepted only; NEW Task1B gate/review/root dispatch required. No container/image/package/harness action or readiness claim.


## PG17 Task1B offline simulation-only successor

Gate one bounded offline Task1B simulation of the immutable independently accepted33APK closure using exact20 new-package inputs, unchanged baseline and complete cleanup; installation/image/Task2 remain separately unauthorized.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`; record `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-task1b-simulation.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`. Independent feasibility report SHA256e82b42d46639d0149b7cf644cb0bbdd29f86bb020cf5410fcdfcea007779ab88. Accepted33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238 remains immutable; exact20 add operands/all33 verification, created/stopped empty bind targets, exact inherited0600zero lock, deterministic Cc-safe parser/unchanged45+27 baseline, pinned BusyBox trigger.58 metadata dependencies (36base/22new) and 95 pure parser fixtures are NOT solver success. Docs only; simulation denied until independent review/adoption/root verification/fresh dispatch. Installation/image/Task2/production remain unauthorized/unverified, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only simulation successor in Issue186/Project8/canonical notes, preserving CURRENT full prior index/detail verbatim and SHA256; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent review of this exact simulation-only checkpoint; require coordinator adoption/root verification and fresh one-attempt dispatch before any Docker command.
- [ ] On authorized fresh simulation only, reverify all33 immutable APK hashes/signatures, use exact20 literal apk-add paths, inspect complete offline resources/mounts and mandatory prestart27 copies before created export/diff.
- [ ] Require deterministic bounded parser with exactly20 additions and no baseline actions, complete unchanged27/package45/world/keys/PG/scripts/trigger/lock state and created/stopped empty bind-target proof; fail closed/quarantine/no retry.
- [ ] After exact-owned removal/absence/complete-volume equality, independently review simulation receipts; a NEW installation gate must pin same20 APK argv and audit BusyBox-trigger effects. No installation/image commit/PG/harness/readiness is authorized now.

Task1B simulation-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622084338 and Project8 readback at `2026-11-04T03:53:46.055147+00:00`; full prior closure index/detail preserved verbatim/hash in comment and dedicated record. Independent exact-checkpoint review/adoption/root verification/fresh dispatch required; no Docker/retry/install/image/harness operation or solver success.

Pinned Task1B simulation-only successor gate: `808225f5fa14ca0c7dc308a5d39cd65396c694f7`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622095482. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.

Pinned Task1B simulation-only successor gate: `dafbdea85477437e8cf20969b3c6571aa59c2c50`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-corrected-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622103154. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.


## PG17 Task1B CapAdd-only ordering successor: plan only

Correct only full HostConfig.CapAdd array order comparison while preserving exact three approved unique capabilities and all other simulation guards; gate ONE fresh offline Task1B simulation after exact review/adoption/root dispatch.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-cap-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-cap-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-cap-order.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-cap-order-evidence.json`. Failed resultSHAf870e36f11b4eea70478f0932ea446aa904631bcda8f89b28e65dbbc6bea8224/diagnosisSHA067a4cb3284da093479301eada2519a7944a07c36839e9262a2e241f8218e37d: never started, exact cleanup/absence/all33 inputs/full4volumes unchanged; independent diagnosis/cleanup acceptance ONLY. Only HostConfig.CapAdd order may normalize after proving exact3unique approved strings; all other complete comparisons/95+148 guards unchanged. 123 new pure cases pass incl6 permutations and negative field/type/duplication drift. NEW empty PREP/container and exact review/adoption/root preflight/fresh ONE-attempt dispatch required. No planning Docker/simulation/install/image/PG/harness; all readiness false, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only CapAdd successor with Issue186/Project8/canonical notes and preserve CURRENT complete prior index/detail verbatim plus SHA256; commit/push then pin full-SHA passing preflight.
- [ ] Obtain independent exact-checkpoint review, coordinator adoption/root full-SHA preflight and fresh ONE-attempt simulation-only dispatch before Docker; use NEW empty private PREP, unique name/cidfile and newly created exact-owned container.
- [ ] Compare only HostConfig.CapAdd order-insensitively with exactly three unique strings CAP_CHOWN/CAP_FOWNER/CAP_DAC_OVERRIDE; retain all complete raw objects/hashes and reject any missing/extra/duplicate/type or non-CapAdd field drift.
- [ ] Retain and rerun all95 simulation parser plus148 predecessor fixtures and the new six-permutation/negative suite; preserve immutable failed-run result/diagnosis and all accepted/quarantined APK boundaries.
- [ ] On separately dispatched simulation, retain unchanged exact script/hash,33 verification/20 selection, offline caps/resources, created-copy-before-export/diff, stopped baseline/lock/trigger/mount/diff, cleanup/absence/full-volume proofs; any discrepancy stops with no retry, installation/image/PG/harness unauthorized.

CapAdd-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622201950 and Project8 readback at `2026-11-04T04:02:37.852702+00:00`; full CURRENT JS index/detail/pin retained verbatim/hash in comment and record. Independent exact-checkpoint review/adoption/root preflight/fresh dispatch required; no Docker/simulation/install/image/PG/harness and no retrospective acceptance.

Pinned CapAdd-only successor checkpoint `cde9652c0e3dce9a9083540d15cb25b3682f144d`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-cap-order-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622210398. Independent exact review/adoption/root preflight/fresh ONE-attempt dispatch still required. Historical run blocked; no Docker/simulation/install/image/harness or readiness authority.


## PG17 explicit offline APK/OOM lifecycle successor: LOCAL DRAFT ONLY

Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

Draft plan `docs/superpowers/plans/2026-11-04-workshop-pg17-offline.md`; record `docs/agents/records/2026-11-04-workshop-pg17-offline.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-offline.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`. Failed resultc1f6af1f/diagnosis0660472e remain immutable FAILED; cleanup accepted only. Exact3.0.8 global no-network+empty repositories file on all5 invocations; original repositories cmp/keys/signatures and empty stderr unchanged. ExactEngine GitCommit source plus retained raw supports ONLY OomKillDisable false-created/null-stopped on pinned unsupported cgroupv2 context; CapAdd rule/other full fields unchanged. 107 new+366prior pure checks passed; no runtime. LOCAL UNSYNCHRONIZED pending draft review and later coordinator tracking slot; no Docker/retry/install/image/PG/harness or readiness.

Concrete todo:

- [ ] Keep this draft LOCAL/UNSYNCHRONIZED pending independent draft review; do not mutate Issue186/Project8 while publisher owns tracking and do not run Docker/retry/install/image/PG/harness.
- [ ] Independently review exact new script/argv/zero-byte override/source proof and phase-bound OomKillDisable predicate plus all pure negative fixtures; preserve failed result/diagnosis as failed, no retrospective acceptance.
- [ ] Only after coordinator authorizes tracking: preserve full CURRENT Project index/detail verbatim/hash, synchronize Issue186/Project8/canonical docs/task, commit/push a new gate and pin full-SHA passing preflight.
- [ ] Only after independent exact synchronized-gate review/adoption/root verification/fresh dispatch: one NEW empty PREP/container, exact33 verification/20 selected simulation, every apk invocation explicitly offline with pinned empty override, unchanged original repositories/keys, empty stderr.
- [ ] Require created/stopped empty bind target/export/diff/27+45 baseline/lock/BusyBox/Config/Mounts/CapAdd/cleanup/volume proofs; normalize only exact false-created to null-stopped on exact unsupported engine context; any other discrepancy stops/no retry. Installation/image/Task2 remain unauthorized.
