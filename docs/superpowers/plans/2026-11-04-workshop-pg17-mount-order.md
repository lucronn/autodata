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
