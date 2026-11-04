# Workshop PG17 Task1B CapAdd Ordering Successor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent review of this exact checkpoint, coordinator adoption/root full-SHA preflight and a NEW explicit ONE-attempt Task1B simulation-only dispatch. This checkpoint is docs only; no Docker or implementation action.

**Goal:** Correct only full HostConfig.CapAdd array order comparison while preserving exact three approved unique capabilities and all other simulation guards; gate ONE fresh offline Task1B simulation after exact review/adoption/root dispatch.

**Architecture:** Preserve the entire adopted Task1B simulation plan and change only comparison of `HostConfig.CapAdd`. Normalize its order after proving exactly the three approved unique string values. No other list, object field or runtime authority is relaxed.

**Tech Stack:** Existing host Python pure guards; unchanged cached PG17.11/Alpine3.24.3/apk3.0.8/Docker28.5.2 execution contract.

**Spec:** `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`; canonical `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Branch `codex/workshop-pg17-cap-order-plan`, base receipt `c16f40a2730e7bc8a5fb3afd3ac2d10abf551637`; failed adopted simulation gate `dafbdea85477437e8cf20969b3c6571aa59c2c50`.

## Actual failed attempt and immutable evidence

Fresh run `/home/corp/autodata-evidence/pg17-task1b-simulation-20261104-01`, exact container `582ebd012879d9d5116c6691d2f9942409a291836142b538988bc1c02a3c0583`, stopped BEFORE startup on complete HostConfig comparison. Result `evidence/task1b-result.json` SHA256 `f870e36f11b4eea70478f0932ea446aa904631bcda8f89b28e65dbbc6bea8224`; read-only diagnosis `evidence/task1b-diagnosis.json` SHA256 `067a4cb3284da093479301eada2519a7944a07c36839e9262a2e241f8218e37d`. The only complete Config/HostConfig difference was:

```text
expected HostConfig.CapAdd: [CAP_CHOWN, CAP_FOWNER, CAP_DAC_OVERRIDE]
observed HostConfig.CapAdd: [CAP_CHOWN, CAP_DAC_OVERRIDE, CAP_FOWNER]
```

Exact owned `rm --volumes`, inspect absence and empty exact-ID ps result passed; all33 accepted APK/control hashes unchanged. Complete four-volume canonical inventory SHA256 `f42cd1adad61342478239168328249caab09bcee912cf608ab5dbe84b4de2985`. No payload/signature verification/simulation/install/PG/harness ran in this attempt.148 predecessor+95 simulation pure fixtures ran before Docker; these are guard evidence, not solver success. Coordinator relayed independent ACCEPTANCE of diagnosis/cleanup ONLY; Task1B remains blocked. No separate saved failed-run review report path supplied; provenance is identified explicitly in `docs/agents/records/2026-11-04-workshop-pg17-cap-order-evidence.json`.

Replaying raw created inspect through the new pure predicate diagnoses equivalence only; it does not accept the historical container, prove its missing created/stopped audits, or authorize reuse/restart/retry. Preserve all red raw bytes/result/diagnosis exactly. The removed container and old PREP must never be reused.

## Exact narrow change and fixed complete-record predicate

The previous supervisor synthesized an order-sensitive CapAdd array while Docker reordered the identical three strings. Replace only `v['HostConfig'] == expected_HostConfig` (including created/stopped comparisons) with `compare_complete_hostconfig_capadd(expected_HostConfig, v['HostConfig'])` below. Retain complete raw before/after inspect bytes/SHA256, expected Config/HostConfig/Mounts records, canonical HostConfig SHA256, existing canonical Mounts SHA256 and full non-CapAdd comparison proof. Validate parsed JSON with the inherited recursive duplicate-key/nonfinite/type rejection before this predicate. Do not catch predicate failure and continue.

Both sides must contain a CapAdd JSON array of exactly three UNIQUE strings, exact spelling/membership `CAP_CHOWN`, `CAP_FOWNER`, `CAP_DAC_OVERRIDE`. Non-list/tuple/null/string/object, non-string item, duplicate, missing, extra, alternate capability/casing all fail. Sort ONLY these validated arrays; preserve every other field/value/type and list order. Object-key order remains JSON-insignificant under the existing complete-object rules. Other Config remains complete strict equality; Mounts retain the inherited complete-record comparison by unique exact Destination, preserving every field/value and rejecting duplicate/missing/extra target. The existing permitted Mounts ordering rule is unchanged; this gate adds no new normalization outside CapAdd.

```python
import copy, hashlib, json
APPROVED_CAP_ADD = frozenset({"CAP_CHOWN", "CAP_FOWNER", "CAP_DAC_OVERRIDE"})
def canonical_hostconfig_capadd(value):
    assert type(value) is dict and "CapAdd" in value
    caps = value["CapAdd"]
    assert type(caps) is list and len(caps) == 3
    assert all(type(cap) is str for cap in caps)
    assert len(set(caps)) == 3 and set(caps) == APPROVED_CAP_ADD
    result = copy.deepcopy(value)
    result["CapAdd"] = sorted(caps)
    # No other array, field, value or type is discarded or reordered.
    return json.dumps(result, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
def compare_complete_hostconfig_capadd(expected, actual):
    left = canonical_hostconfig_capadd(expected)
    right = canonical_hostconfig_capadd(actual)
    assert left == right
    return hashlib.sha256(left).hexdigest()
```

The canonical helper returns hash only after byte-exact canonical equality of both complete HostConfig objects. No dropped CapAdd field, set-only partial HostConfig comparison, global list sorting, coercion, capability addition, subset/superset, normalized capability aliases or filtered inspect acceptance. `Config`, `.Image`, `.State` phase rules, identity, labels, exact argv and all other HostConfig fields still require the adopted plan's complete predicates. Default MemorySwap and all resource/mount/network settings remain as already rendered by the approved create argv, not newly chosen here.

## One future fresh simulation: unchanged executable contract and lifecycle

This successor proposes at most ONE fresh attempt. Synchronization/preflight is not dispatch. Before any future Docker command, independently review this exact checkpoint; coordinator must adopt it, rerun its full-SHA preflight and explicitly dispatch the attempt. Allocate NEW absent private `PREP` (uid1000:1000 mode0700), NEW unique RUN_ID/name/empty cidfile, NEW container from exact cached BASE using the predecessor's literal create argv, with only these approved owned substitutions: new PREP/control/evidence, unique name/cidfile, full newly adopted gate label. `FROZEN_APKS` remains exactly the accepted03 path, not copied/changed input. Never reuse the removed container or old PREP; no second retry on any discrepancy.

The referenced Task1B plan is normative in full. Preserve exact script SHA256 `068cb46037387a6d38491f2fbcf1d71c99797223dfce7649c015d7bc61d114de`, parser SHA256 `f2a0c79a1c27acbdb66a4d269ff3e922b49c628989487229e31bad55bea04dca`,33 immutable APK verification before/start/after and exact20 literal `apk add --simulate --no-network` operands. Accepted manifest SHA256 `cfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238`; exact cached BASE `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085`. Both earlier33APK quarantines remain NEVER reusable. No index/network/resolver/input/flag change.

Preserve network none, root0:0, exact3caps/dropALL/no-new-privileges,128pids/1GiB/2CPU, three private bounded tmpfs including inherited PGDATA override, only two read-only APK/control binds, no source/evidence/secrets bind or anonymous volume. Preserve all148+95 pure checks before runtime, full created configuration check and10 prestart cp snapshots/27baseline comparison BEFORE first bounded created export/diff, absent base bind targets and exact empty root-owned /apks,/control directory metadata in created and stopped exports. Preserve export size/time/parse completion failure rules, exact full diff only A/apks+A/control, stopped exit0/noOOM/emptyError, deterministic95-fixture parser exactly20 additions, unchanged45/27 complete state/copy context/world/keys/PG/zero0600lock/BusyBox trigger/scripts, raw hashes and exact-owned cleanup/absence/complete structured volume inventory. New discrepancy fails closed, quarantines the new simulation result and stops without retry or guard modification.

Even a future PASS is simulation-only and requires independent simulation receipt review. Installation needs NEW reviewed gate/root dispatch with identical selected20 operands (only `--simulate` removed), explicit BusyBox trigger/file/symlink/capability audit; image commit/runner inspection/PG startup/harness/original Task2 remain separately unauthorized. No source/application/production runtime/grant/provider/cloud/DNS/service/deployment or readiness authority.

## Pure verification and concrete todo

New fixed-predicate fixtures: 123 passed. All6 CapAdd permutations accept; duplicates/missing/extra/non-list/member type/casing/membership and mutations to every other HostConfig field, unrelated list order, Config fields and complete Mounts fields reject. Complete retained failed-run replay is diagnostic only. All95 unchanged simulation parser fixtures and148 predecessor pure/replay/Cc checks freshly reran successfully; total 366 pure checks, no Docker invoked while preparing this gate. Full cases/results/fragment/raw hashes in `docs/agents/records/2026-11-04-workshop-pg17-cap-order-evidence.json`.

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


## PG17 offline/OOM successor synchronized planning checkpoint

Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

Reviewed local draft `d3edce5094896dc4c11cc6e186ce4738418ac6c2`: coordinator relayed independent read-only draft PASS, all473 pure checks, no blockers. This is not runtime approval. Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-offline.md`; record `docs/agents/records/2026-11-04-workshop-pg17-offline.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`; branch `codex/workshop-pg17-offline-plan`. Failed result `c1f6af1f8242eff80da993cef370e8bdd7cbd47da2a7f4fc5c2731bbf36d9c29`/diagnosis `0660472e7f2a2a72403cd609ce60ef615e0e301c830e4c08f5e2e2c279edf4ab` immutable FAILED; diagnosis/cleanup only accepted. One NEW empty PREP/container is conditional on independent exact-checkpoint review, root preflight/adoption and fresh dispatch. All five apk invocations explicitly no-network with pinned zero-byte repository override; original repositories cmp/keys/all33 signatures and empty stderr unchanged. Only exact-source-proven OomKillDisable created false/stopped null on pinned unsupported engine context, plus prior CapAdd-order rule; all other complete fields and lifecycle/source/mount/export/baseline/cleanup/volume guards unchanged. Historical results cannot be accepted retrospectively; both33 APK quarantines remain forbidden. No Docker/retry/install/image/PG/harness/production/readiness authority.

Concrete todo:

- [ ] Independent local draft review PASS at d3edce5094896dc4c11cc6e186ce4738418ac6c2 (473 pure checks); synchronize only this reviewed docs-only scope, preserving all prior histories and denials.
- [ ] Obtain independent exact synchronized-checkpoint review, root full-SHA preflight/adoption and fresh ONE-attempt simulation dispatch before any Docker operation.
- [ ] Preserve CURRENT Stage0/staging/PG/JS Project index and all detail/pin bodies verbatim/hash; verify exact Issue186/Project8 readback and pin committed full-SHA passing preflight.
- [ ] Only after independent exact synchronized-gate review/adoption/root verification/fresh dispatch: one NEW empty PREP/container, exact33 verification/20 selected simulation, every apk invocation explicitly offline with pinned empty override, unchanged original repositories/keys, empty stderr.
- [ ] Require created/stopped empty bind target/export/diff/27+45 baseline/lock/BusyBox/Config/Mounts/CapAdd/cleanup/volume proofs; normalize only exact false-created to null-stopped on exact unsupported engine context; any other discrepancy stops/no retry. Installation/image/Task2 remain unauthorized.

Exact live Issue186 body/detail https://github.com/lucronn/autodata/issues/186#issuecomment-6622351785 and Project8 readback verified at `2026-11-04T04:13:41.594272+00:00`; source preservation/index/detail/pin bodies and hashes in `docs/agents/records/2026-11-04-workshop-pg17-offline-tracking.json`. This supersedes earlier LOCAL DRAFT/UNSYNCHRONIZED lifecycle text only; technical predicates unchanged. Exact committed checkpoint/full-SHA preflight follows; no runtime authority.
