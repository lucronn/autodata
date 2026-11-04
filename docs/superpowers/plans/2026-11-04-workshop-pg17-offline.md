# Workshop PG17 Explicit Offline APK and OOM Lifecycle Successor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent review, synchronized committed gate/full-SHA preflight, adoption/root verification and fresh ONE-attempt simulation dispatch. SYNCHRONIZED PLAN ONLY; exact-checkpoint review/adoption/fresh dispatch still required; no Docker or implementation authority.

**Goal:** Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

**Architecture:** Preserve the accepted33/selected20 offline simulator and every guard, modifying only APK argv to exclude all repository loading/network on all five invocations and a source-proven single HostConfig lifecycle representation. Never accept warnings or bypass signatures; never normalize another field.

**Tech Stack:** Exact cached PG17.11/Alpine3.24.3/apk3.0.8, Engine28.5.2+dfsg4/API1.51/cgroupv2/overlay2; host pure Python evidence.

**Spec:** `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`, `docs/superpowers/plans/2026-11-04-workshop-pg17-cap-order.md`, canonical `docs/agents/pre-implementation-gate.md`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Local branch `codex/workshop-pg17-offline-plan`; base adopted receipt `581e6c1d35e2b3c4d8ddedea2fbbd11e029cfcc1`. Status SYNCHRONIZED PLAN ONLY after independent local draft review PASS and coordinator-authorized tracking slot; no runtime until independent exact synchronized-gate review/adoption/root dispatch.

## Failed history and actual observations

Under adopted gate `cde9652c0e3dce9a9083540d15cb25b3682f144d`, fresh exact container `1b176532694e08222daaff096bc6489fc769f96f1a51f95f4c2c28ef93feac67` ran one payload in network none and was removed. Raw `/home/corp/autodata-evidence/pg17-task1b-simulation-20261104-02/evidence/task1b-result.json` SHA256 `c1f6af1f8242eff80da993cef370e8bdd7cbd47da2a7f4fc5c2731bbf36d9c29`; diagnosis `task1b-diagnosis.json` SHA256 `0660472e7f2a2a72403cd609ce60ef615e0e301c830e4c08f5e2e2c279edf4ab`.

Prestart guards/27copies-before-export/diff passed. Process exit0/noOOM/emptyError, stdout8914bytes and stderr837bytes. Stderr had six WARNING lines: official main/community index DNS transient warnings twice and missing-cache warnings once. Only `apk add` had explicit `--no-network`; `info`/`verify` retained global repository initialization. The warnings are rejected, never suppressed or reclassified as success. Exact command attribution is a source-backed diagnosis, not separately framed per-command stderr proof. Network namespace none prevented successful repository acquisition; no package fetch/install occurred. stdout20 proposed additions/66 signature OK lines/65-package summary is diagnostic ONLY. Stopped27 copies/export were not run after fail; missing proof blocks retrospective acceptance regardless of a new predicate.

Read-only full retained HostConfig comparison separately finds ONLY created `OomKillDisable: false` to stopped `null`. Raw complete inspect/hashes and source facts are in `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`. Config and prior complete Mounts predicates remain unchanged. Exact-owned rm--volumes/absence/empty exact-ID ps, all33/control unchanged hashes and full4volume equality passed. Independent coordinator accepted failure diagnosis/cleanup ONLY, not simulation success. Preserve all failed receipts and both quarantined historical33APK sets; never reuse old container/PREP or treat new pure replay as acceptance.

## Narrow APK CLI remedy supported by exact3.0.8 source

Pin apk-tools source commit `44dcdfc255c26a4e19a4a27f66a54169cce5ca72` (v3.0.8). `src/apk.c` SHA256 `929d3ae791aaf8fa7f3ae0881e307822ca0b38bb08a3debc23038d4d7115e5d9`: global network BOOL and repositories-file ARG options lines65/74, handling159-160/186-187; parser338-397 implements `no-` for BOOL;411-415 applies global options to every applet;579 onward parses argv. The explicit full option spelling is supported before info/verify/add, not a guessed shorthand. `src/database.c` SHA256 `70ed32b5276d67b75a1cb923bfe503f2e698e8f3fb6e764176c0d29926d0b335` lines1538-1539 avoids remote update when APK_NO_NETWORK;2170-2180 uses ONLY non-null explicit repositories_file instead of `/etc/apk/repositories` AND the etc/lib repositories.d trees. Empty regular file therefore supplies zero repositories. `--no-network` alone can still warn about missing configured cached indexes, so use BOTH options on EVERY invocation.

Preserve `cmp /etc/apk/repositories /control/repositories` and original official two-line repository bytes. Do not edit/empty the image repositories file, remove keys, add repositories/indexes, prefill caches, change roots, bypass trust, accept warnings or add force/no-scripts flags. New additional control file `empty-repositories` is regular uid1000-owned0444, zero bytes, SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, no symlink/hardlink, under same private read-only `/control` bind. Hash exact three control files before create/start/after removal; reject extra/mutated files. No new mount/cap/env needed. All33 APK paths, accepted manifest and signing keys/signature verification remain identical.

Source load_config reads APK_CONFIG or `/etc/apk/config`, then `/lib/apk/config` before argv. Complete retained exact-base `/etc/apk` and `/lib` snapshots prove both default config files absent, inherited Env has no APK_CONFIG/APK_ variables; require those absence facts unchanged in new prestart snapshots/full Config. No arbitrary inherited environment or command-line `--repository`/`--repository-config`. This makes the explicit empty-file repository override effective without hidden configured repository_list additions. These are read-only source/baseline proofs, not an executed new-payload claim.

After future authority only, write exact fixed `simulate.sh`, SHA256 `ece9cb3058ebb2210c91e8d56e572c495b5e1522084d7fc13c658cd1949d73bf`; preserve parser SHA256 `f2a0c79a1c27acbdb66a4d269ff3e922b49c628989487229e31bad55bea04dca` unchanged:

```sh
#!/bin/sh
set -eu
umask 022
cmp /etc/apk/repositories /control/repositories
printf '%s\n' 'AUTODATA_PG17_BASELINE_BEFORE_BEGIN'
apk --no-network --repositories-file /control/empty-repositories info -vv
printf '%s\n' 'AUTODATA_PG17_BASELINE_BEFORE_END'
printf '%s\n' 'AUTODATA_PG17_VERIFY_BEFORE_BEGIN'
apk --no-network --repositories-file /control/empty-repositories verify /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gdbm-1.26-r0.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libcrypto3-3.5.9-r0.apk /apks/libexpat-2.10.0-r0.apk /apks/libffi-3.5.2-r1.apk /apks/libgcc-15.2.0-r5.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libncursesw-6.6_p20260516-r0.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/libssl3-3.5.9-r0.apk /apks/libstdc++-15.2.0-r5.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-1.2.6-r3.apk /apks/musl-dev-1.2.6-r3.apk /apks/ncurses-terminfo-base-6.6_p20260516-r0.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/readline-8.3.3-r1.apk /apks/sqlite-libs-3.53.4-r0.apk /apks/xz-libs-5.8.4-r0.apk /apks/zlib-1.3.2-r1.apk /apks/zstd-libs-1.5.7-r2.apk
printf '%s\n' 'AUTODATA_PG17_VERIFY_BEFORE_END'
printf '%s\n' 'AUTODATA_PG17_SIMULATION_BEGIN'
apk --no-network --repositories-file /control/empty-repositories add --simulate /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libexpat-2.10.0-r0.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-dev-1.2.6-r3.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/sqlite-libs-3.53.4-r0.apk
printf '%s\n' 'AUTODATA_PG17_SIMULATION_END'
printf '%s\n' 'AUTODATA_PG17_VERIFY_AFTER_BEGIN'
apk --no-network --repositories-file /control/empty-repositories verify /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gdbm-1.26-r0.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libcrypto3-3.5.9-r0.apk /apks/libexpat-2.10.0-r0.apk /apks/libffi-3.5.2-r1.apk /apks/libgcc-15.2.0-r5.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libncursesw-6.6_p20260516-r0.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/libssl3-3.5.9-r0.apk /apks/libstdc++-15.2.0-r5.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-1.2.6-r3.apk /apks/musl-dev-1.2.6-r3.apk /apks/ncurses-terminfo-base-6.6_p20260516-r0.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/readline-8.3.3-r1.apk /apks/sqlite-libs-3.53.4-r0.apk /apks/xz-libs-5.8.4-r0.apk /apks/zlib-1.3.2-r1.apk /apks/zstd-libs-1.5.7-r2.apk
printf '%s\n' 'AUTODATA_PG17_VERIFY_AFTER_END'
printf '%s\n' 'AUTODATA_PG17_BASELINE_AFTER_BEGIN'
apk --no-network --repositories-file /control/empty-repositories info -vv
printf '%s\n' 'AUTODATA_PG17_BASELINE_AFTER_END'
```

There are exactly five APK invocations, each beginning literal `apk --no-network --repositories-file /control/empty-repositories`. Both info sections and both33-path signature verification sections keep their exact output contract. Add keeps literal20 operands and `--simulate`. Future installation remains denied; any later installation gate must use the same offline/empty-file prefix/selected20 inputs, only removing `--simulate` under a new explicit gate.

## Separate source-proven OomKillDisable lifecycle rule

Exact retained Engine Server GitCommit `3ef3c07c883be49a2e8097bcf6d2952fce1d70eb`, version28.5.2+dfsg4/API1.51, info Driver overlay2/CgroupVersion2/OomKillDisable=false. Read-only GitHub source at THAT full Engine commit resolved (not inferred only from version tag):

- `daemon/create.go` SHA256 `aa0547d665ea755bbe5535f7e689ece376b43a274a40382d99b1e3eb97754da7`: verifyContainerSettings92 BEFORE adaptContainerSettings124.
- `daemon/daemon_unix.go` SHA256 `adf696737ec09d33b2fbee4c6252c8f99d15d018d6555915aef870e5f4cb251d`: adapt377-379 sets nil OomKillDisable pointer to false; verify470-476 resets a nonnil pointer to nil when sysInfo lacks support, warning only if pointer was true.
- `daemon/start.go` SHA256 `e5ca94459cf0eb89fc1c600671886700425cf20c460d15f56aef8e380c35b383`:63-65 re-verifies the same HostConfig before start, discarding unsupported false pointer to nil; typed API pointer `*bool` in hostconfig.go yields JSON null.

Thus pinned unsupported engine context plus raw false-created/null-stopped independently supports this representation transition without disabling OOM killer or changing memory bounds. Source correspondence is exact GitCommit plus observed behavior; it is not blanket source/binary equivalence or a rule for arbitrary Docker versions/hosts.

New guard below carries prior CapAdd-only normalization unchanged. At every created inspection require actual OomKillDisable is literal boolean False and created/never-started phase proof; at every stopped inspection require literal None/null and independently exited/Runningfalse/Exit0/OOMfalse/Error-empty proof. Use the SAME immutable fully validated created HostConfig as anchor, including in stopped export before/after comparisons. Do not compare two stopped objects in isolation or normalize before proving lifecycle. Validate exact full current raw Docker version/info and derive ENGINE_CONTEXT as below, retaining complete raw JSON/hash; unknown/drifted/unsupported context blocks. Do not synthesize or overwrite raw inspect records.

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

EXPECTED_ENGINE_CONTEXT = {"server_version": "28.5.2+dfsg4",
    "server_git_commit": "3ef3c07c883be49a2e8097bcf6d2952fce1d70eb",
    "server_api_version": "1.51", "storage_driver": "overlay2",
    "cgroup_version": "2", "oom_kill_disable_supported": False}
def compare_phase_hostconfig(validated_created, observed, phase, engine_context):
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    assert encode(engine_context) == encode(EXPECTED_ENGINE_CONTEXT)
    assert type(validated_created) is dict and type(observed) is dict
    assert "OomKillDisable" in validated_created and "OomKillDisable" in observed
    assert validated_created["OomKillDisable"] is False
    if phase == "created":
        assert observed["OomKillDisable"] is False
    elif phase == "stopped":
        assert observed["OomKillDisable"] is None
    else:
        raise AssertionError("unknown inspection phase")
    # Copy only after phase/engine/type/field checks; retain original raw false/null records.
    comparison = copy.deepcopy(observed)
    comparison["OomKillDisable"] = False
    return compare_complete_hostconfig_capadd(validated_created, comparison)
```

This allows only createdfalse->stoppednull for OomKillDisable on pinned unsupported context. Creatednull/stoppedfalse/true/numeric0/missing field/unknown phase/engine drift reject. Outside CapAdd order and this exact phase conversion, every complete HostConfig field/type/list order remains strict; Config, identity/labels/argv, State and complete canonical Mounts rules unchanged. No optional capability, resource, network, security, mount or user relaxation. Canonical hash is a comparison artifact; retain original false/null raw records and all original hashes.

## Unchanged lifecycle, next review boundaries and concrete todo

One future NEW empty private PREP/new name/cidfile/new exact-owned container ONLY after independent draft review, coordinator-authorized tracking sync, full-SHA passing gate, independent exact synchronized review/adoption/root verification and fresh dispatch. All accepted33 hash/size/owner/no-link checks, exact20 signature/add selection, original strict empty-stderr/diagnostics/Cc/parser, network none, same3caps,1GiB/2CPU/128pids, three bounded tmpfs/inherited PGDATA override, two readonly binds/no source/secrets/evidence mount remain. New file resides within existing control bind; create argv changes only owned PREP/RUN_ID/gate, never resource authority.

Retain all366 prior pure checks,27base/45package/zero0600lock/BusyBox trigger+script/world/key/PG equality,10prestart cp snapshots BEFORE first created export/diff, empty underlying targets/root-directory metadata, complete created/stopped export limits/tar completion/full diff ONLY A/apks+A/control, all stopped receipts and exact-owned removal/absence/structured full-volume proof. No stderr filtering, retries or relaxed partial state audit. Any difference stops/quarantines the new result and requires a separately reviewed amendment. Installation/image commit/nonroot inspection/PG/harness/Task2/production/provider/cloud/deployment/readiness remain denied.

Local pure tests: 107 new lifecycle/script cases and366 unchanged checks passed (473 total); retained failed-run phase replay is diagnostic only. New payload has NOT executed; no solver success or stopped state audit is claimed. No technical source-support blocker identified for draft review. Blocking work remains independent local draft review; current Issue/Project synchronization/full-SHA machine gate; exact synchronized review/adoption/root verification/fresh dispatch; then actual fully guarded simulation. This draft has no passing synchronized runtime gate.

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

Pinned explicit-offline/OOM successor checkpoint `3e4d1b0b728c81ce8dd1ae84d207df645e6bfbf1`; full-SHA preflight `status: synchronized`, `errors: []`, exit0/empty stderr; receipt `docs/agents/records/2026-11-04-workshop-pg17-offline-preflight.json`; exact Issue186/Project8 full-SHA readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622361427. All nine prior index/detail/pin preservation comments verified verbatim/hash. Independent exact synchronized-checkpoint review/adoption/root verification/fresh ONE-attempt dispatch still required; no Docker/retry/install/image/PG/harness/readiness.


## PG17 offline installation-only successor: synchronized planning gate

Goal: Design one fresh offline actual installation of the accepted33 closure/exact20 selection with a finite source-derived stopped-state audit and exact cleanup; image/PG/harness remain unauthorized.

Corrected local draft independently reviewed PASS (coordinator relayed), exact plan SHA256 `a0a0ce8ac827d60b86f087d305b3a3fdc689edea8f91fb4404bc8a7bf2049387`, evidence SHA256 `d49597e41cf6a65e43d51b84955212a0e8ed4d41974bc8c883ea4db6f411540c`; all584 host-only checks replayed. This is docs-only synchronization, not installation approval. Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-install.md`; record `docs/agents/records/2026-11-04-workshop-pg17-install.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-install.json`; frozen technical evidence `docs/agents/records/2026-11-04-workshop-pg17-install-evidence.json`; branch `codex/workshop-pg17-install-plan`, base receipt `3b67536c17db53064c79fc1f63d2cbda1d0fe935`. Accepted simulation result `ac093352ec670acff88fa28df1712d623fe268a38c30b32b0e623eeb11bb8565` under gate3e4d1b0 is SIMULATION ONLY. Frozen33 manifest `cfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238` unchanged; both historical33 APK quarantines remain forbidden.

Proposed future ONE actual installation uses NEW empty private PREP/new exact-owned cached-base container; exact same20 operands/all33 signature checks, five explicit no-network+empty repository argv and original repositories/keys preserved; only remove --simulate. Source-derived BusyBox304 preexisting targets/EEXIST no-op, exact strings replacement, unchanged45 plus20 full FDB records/27-line checksum world, original10 scripts/exact trigger/zero-byte0600 lock, finite complete payload/hardlink/tree/diff projection. Raw512-byte physical TAR headers must all be counted/preserved/correlated; GNU L/K and PAX x/g/unsupported types reject, including scripts database. New tighter prestart299700000-byte ceiling and conditional stopped535610656-byte bound retain inherited512MiB/50000physical-header/60s limits. Full source/mount/resource/engine/CapAdd/OOM/context/copy/export/cleanup/complete-volume guards remain. Source-derived expected state is not installation success.

Independent exact synchronized-checkpoint review, root preflight/adoption and fresh ONE-attempt dispatch remain mandatory. No Docker, install, image commit/reuse, PG startup, harness/Task2, production/provider/cloud/activation/readiness or implementation-file authority follows. Existing Stage1A/M2A/Stage0/staging/PG/JS authorities/statuses/denials remain unchanged.

Concrete todo:

- [ ] Independent corrected local draft review PASS for exact planSHA a0a0ce8ac827d60b86f087d305b3a3fdc689edea8f91fb4404bc8a7bf2049387/evidenceSHA d49597e41cf6a65e43d51b84955212a0e8ed4d41974bc8c883ea4db6f411540c; retain all584 pure/replay checks and exact reviewed source/predicates.
- [ ] Synchronize docs-only gate preserving COMPLETE current Issue body/all113 comments and full Project index plus Stage1A/M2A/Stage0/staging/PG/JS details/pins verbatim/hash; commit/push, pin full-SHA passing preflight and verify exact full tracking readback.
- [ ] Obtain independent exact synchronized-checkpoint review, coordinator adoption/root full-SHA preflight and fresh ONE-attempt installation-only dispatch before any Docker operation.
- [ ] Only after fresh dispatch: new empty PREP/new exact-owned container, same immutable33/exact20 offline add without --simulate, full prestart/stopped/database/world/script/payload/physical-header/diff/bounds/cleanup proofs; any discrepancy stops/quarantines/no retry/image/PG/harness.

Exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622859754 at `2026-11-04T04:50:23.730780+00:00`; COMPLETE original Issue body/all113 comments/Project index (including Stage1A/M2A histories) retained verbatim+hash in `docs/agents/records/2026-11-04-workshop-pg17-install-tracking.json`. Prior authorities/statuses remain unchanged. Exact committed full-SHA pin follows; no installation authority.

Pinned PG17 offline installation-only planning gate `74dfe57e1d6601429774f7e44e1df17ba1c54144`; full-SHA preflight `status: synchronized`, `errors: []`, exit0/empty stderr. Receipt `docs/agents/records/2026-11-04-workshop-pg17-install-preflight.json`; exact Issue186/Project8 pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622872548. Complete original Issue body/all113 comments/previous M2A Project index and Stage1A/M2A histories preserved verbatim/hash and reread; all114 pre-pin comments unchanged. Independent exact synchronized-gate review/adoption/root verification/fresh ONE-attempt dispatch still required. No Docker/install/image/PG/harness/implementation/readiness authority.


## PG17 failed-install world-order retrospective: synchronized docs-only gate

Goal: Synchronize one host-only read-only retrospective audit of immutable PG17 failed-install raw using source-derived exact27 name ordering; preserve failed/quarantined historical result and all runtime prohibitions.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-world-retrospective.md`; record `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-world-retrospective.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-evidence.json`; branch `codex/workshop-pg17-world-retrospective`, base prior PG installation receipt `d662cb01a35b07cfa0dc3788891248fc4c07d12f`. Independent local draft review PASS relayed by coordinator for exact draft SHA256 `4a51279130fdcf13123fa54f86ea7b4e85ed744620564bbc169e92d93f88d0c0` and support hashes; reviewer verified all211 raw refs, exact source chain and12 negative fixtures. Exact synchronized-checkpoint review is still pending.

Historical result `/home/corp/autodata-evidence/pg17-install-20261104-01/evidence/installation-result.json` SHA256 `124e43a98319c5bfcd2d79b0384925eaa3d29df3148d8bccb05409e8df5c5ffb` remains `installation_blocked_quarantined`. The actual926-byte world SHA256 `ff2c86c23fc594d35e568629e9f400e3eb86f2f0e9e1459dd75af1fab8420aa4` matches independently source-derived name order; old append expectation `626c1405acfdae445028c35986ba1cd58368422a425d986cdf7f39a5453c4b04` was incorrect. Pinned apk3.0.8-r0 APKBUILD/archive/patch/solver.c prove the comparator/call chain; this finding does not prove skipped finite-tree/diff/output/bounds/original27 classification audits. Whole-token sorting is explicitly rejected using python3 prefix-family fixtures.

Scope after a separate exact-gate review/adoption/root verification/fresh dispatch: host-only reads of retained raw, separate new audit evidence, unchanged reviewed guards/bounds, independently reindexed raw physical headers and full semantic projection; only world_expected27/hash changes in a new in-memory projection. Every skipped audit reports separately; original result/raw/gate stay immutable. No Docker, install/retry, image commit/reuse, PG startup, harness/Task2, implementation, provider/cloud/activation/production/readiness. No retrospective audit executed or passed on this docs turn.

Full CURRENT integration Project index gate `2728ac1acaf173d6f244e200e584dac7922fda1d`, receipt `507e3ddb977ddd45910cba978c7255fac3cb669e`, integration detail6622915925+pin6622928529, PG detail6622859754+pin6622872548, Stage1A/M2A/Stage0/staging/JS details and all prior authorities/statuses/denials remain preserved unchanged. The COMPLETE Issue body/all117 prior comments/full Project index are retained verbatim+SHA256 in `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-tracking.json` with exact paginated readback.

Concrete todo:

- [ ] Retain independently reviewed exact local source/draft proof: reviewed draft4a51279130fdcf13123fa54f86ea7b4e85ed744620564bbc169e92d93f88d0c0, all211 immutable raw refs and12 negative fixtures; historical result remains failed/quarantined.
- [ ] Synchronize docs-only gate preserving COMPLETE current Issue body/all117 comments/Project index including integration gate2728ac1acaf173d6f244e200e584dac7922fda1d and receipt507e3ddb977ddd45910cba978c7255fac3cb669e verbatim+hash/readback; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent exact synchronized-checkpoint review, coordinator adoption/root full-SHA preflight, then fresh narrowly scoped host-only read-only audit dispatch; no skipped audit on this docs turn.
- [ ] Only after fresh dispatch: independently reindex immutable retained exports, replace only world projection with source-derived exact27 name order, run each skipped database/tree/diff/output/bounds/original27 classification audit and record individual outcomes; reverify all raw before/after.
- [ ] Independently review and synchronize a separate retrospective result without relabeling historical failure accepted; any installation/retry/image/PG/harness requires entirely separate authority.

Exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6623016400 at `2026-11-04T05:02:01.935195+00:00`; COMPLETE current Issue body/all117 comments/full Project integration index gate2728ac1/receipt507e3d preserved verbatim+hash in `docs/agents/records/2026-11-04-workshop-pg17-world-retrospective-tracking.json`. Prior authorities/statuses/denials unchanged. No skipped audit or Docker/install authority.
