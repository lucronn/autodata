# Workshop PG17 APK Log Tmpfs Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent exact-checkpoint review and a new coordinator dispatch. This checkpoint is plan-only; it creates/starts no container, downloads nothing and retries no preparation or harness.

**Goal:** Permit only an independently reviewed PG17 preparation retry with an explicit bounded private APK log tmpfs and pre-start guard, preserving the actual exit99 blocker, exact-owned cleanup, offline provenance and separate harness authority.

**Architecture:** Add one private bounded tmpfs at the existing APK default log directory to each already approved APK phase. Require an exact pre-start log guard in addition to the full existing image/mount/network/ownership validation. Keep the original read-only acquisition root, command payload, signatures, official repositories, isolated offline simulation/install and exact-owned cleanup.

**Tech Stack:** Cached PostgreSQL17.11 Alpine3.24.3, apk-tools/libapk3.0.8-r0, Docker inspected-create route, local Python-only guard fixtures.

**Spec:** `docs/superpowers/plans/2026-11-04-workshop-pg17-inspected-preparation.md`; `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Planning base: `6577207980f24e61c51ab0fcc8198ded18c0d1a4` (retained real Task1A blocker).
Prior approved amendment gate: `6d65a512172f28a9f7f0960ecf41409db78455c2`; unchanged harness54ab7dce19c36ce7ea3403259dd1ecc66bf323aa.

## Global constraints and precedence

This corrects only the missing APK log write sink in prior Task1A and the same sink for later APK simulation/install phases. It does not change any APK subcommand or add a no-log/force/untrusted/upgrade option. No other mount, capability, repository, entrypoint, source/image pin, deadline, package closure, install/provenance criterion or Task2 authority changes. No tracked implementation files, integration, actual retry, host package installation, production secret/runtime/grant/provider/cloud/DNS or readiness action is allowed in this planning task. The Python-only fixture below is guard logic evidence, never proof that APK update/acquisition will succeed.

## Actual red proof and read-only diagnosis

The retained exact-owned Task1A container `5ea0276a7dbc38de2f3bbea2dfcb14605dd128fba13c486071316d933a910bdc` passed its original image/mount validation, then fixed `apk update` exited99 with `ERROR: Unable to open log: Read-only file system`. apk-tools reported3.0.8-r0;0 APKs were fetched. The container was removed with verified absence and unchanged volume inventory. No simulation, install, image commit, PostgreSQL or harness ran. Preserve the raw receipt and failed evidence directory; no retelling this attempt as success.

Raw evidence directory: `/home/corp/autodata-evidence/pg17-inspected-prep-20261104-01/evidence`. Dedicated correction evidence `docs/agents/records/2026-11-04-workshop-pg17-apk-log-evidence.json` includes hashes of task1a-blocker.json, attach stderr/stdout and pre-start inspect, plus saved-image binary identities and pure guard fixture outcomes.

Read-only saved-layer inspection of cached base `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085` confirms `/var/log` is a directory and apk.log exists in base layers. `usr/lib/libapk.so.3.0.0` contains the literals `var/log/apk.log`, `var/log` and `Unable to open log: %s`; its SHA256 is `12a612195b5c7918ff48fa2aa84753025be7167f57d055353a81d338d3f1ae13`. `sbin/apk` SHA256 is `80ac076736f35434f0df4a041578ec8f760eb545a71424fd6b6e1403a8a65312`, installed package metadata3.0.8-r0/source commit4588b452722bd4800efdc6cce4f6e980e02a997f. Its option strings include `logfile`; strings alone do not establish no-log syntax/behavior, so no unverified option is selected.

The retained pre-start inspect has ReadonlyRootfs=true and tmpfs only at `/tmp`, `/var/cache/apk`, `/var/lib/postgresql/data`; `/var/log` is not a bind or tmpfs. Thus the observed default log cannot be opened for writing. No additional container or binary execution was used to diagnose this. Saved-layer evidence and the actual stderr support the narrow sink correction; they do not prove future update/download/network/package behavior.

## Exact correction and phase-specific mount contract

Add this exact option to acquisition, offline simulation and offline installer create argv, before the unchanged entrypoint/image/script:

```text
--tmpfs /var/log:rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700
```

It is private in-memory storage for APK's existing `/var/log/apk.log`, not a host path, Docker volume or writable root. It deliberately hides the base image's historical log while that container exists. No mkdir/chmod of the image root, writable `/var`, file bind or anonymous log volume is permitted. The original private PGDATA tmpfs remains separately required and unused. New quotas/owners/options must match exactly; duplicates, submounts/symlinks/overlapping bind destinations, extra permissions or wrong quotas reject.

The acquisition now has exactly four tmpfs targets: original PGDATA16m, `/tmp`64m, `/var/cache/apk`128m, and `/var/log`4m. Root filesystem remains read-only; original two binds stay `/apks` writable and `/control` read-only. Offline simulation/installer now have exactly three tmpfs: original PGDATA16m, `/tmp`128m, `/var/log`4m; their two binds remain read-only APK/control inputs and their original isolated root layer policy remains unchanged. Non-APK final Python/C inspection has no new log mount and retains its original two tmpfs/two read-only binds. Do not apply log-mount permission as a blanket optional mount for other phases.

All log writes are bounded by4MiB and the existing phase deadlines. ENOSPC/logging errors remain failed prerequisites; no deletion/truncation/disabled logging or quota increase to force success. Capture required repository/index/package/signature/hash steps and their exit status through the attached stdout/stderr and structured receipts, never the ephemeral logfile alone. The host supervisor must stream in4096-byte chunks with a1MiB cap per stdout/stderr stream (retain at most cap+1); overflow fails the attempt and triggers the existing exact-owned stop/cleanup, never truncates into success. Attach stdout/stderr, exit status, stopped inspect and cleanup remain mandatory retained evidence; transient log contents are not acceptance receipts. Log files are tmpfs-only, not available from stopped-container tmpfs by assumption. No new log dump or customer/secret payload enters receipts. If additional log data is needed later, a separate bounded reviewed emission contract is required.

## Exact pre-start guard addition

Run this pure guard against the full created-container inspect before any start, after the original complete validation. It adds no replacement validator or permissive fallback. The caller supplies phase exactly `acquire`, `simulate` or `install`; unrecognized phases reject. Preserve validated private realpath binds, cap/network/entrypoint/user/source/image/argv/resource and zero-volume checks from the canonical inspected-preparation plan.

```python
LOG_TMPFS = 'rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700'
def validate_apk_log_guard(value, phase):
    assert phase in ('acquire', 'simulate', 'install')
    config = value['HostConfig']
    expected_targets = {'/var/lib/postgresql/data', '/tmp', '/var/log'}
    if phase == 'acquire':
        expected_targets.add('/var/cache/apk')
        assert config['ReadonlyRootfs'] is True
    assert set(config['Tmpfs']) == expected_targets
    options = config['Tmpfs']['/var/log'].split(',')
    assert len(options) == len(set(options)) == 8
    assert set(options) == set(LOG_TMPFS.split(','))
    for mount in value['Mounts']:
        destination = mount['Destination']
        assert mount['Type'] != 'volume'
        assert not (destination == '/var/log' or destination.startswith('/var/log/'))
        assert not (destination != '/' and '/var/log'.startswith(destination.rstrip('/') + '/'))
```

Docker's pre-start inspect represents `--tmpfs` in HostConfig.Tmpfs; the retained actual pre-start .Mounts contains only the two binds. The guard rejects a competing mount at/above/below the log path and any Docker volume; original complete validation still rejects all unexpected binds, `/` mounts and other configuration. Compare option sets only after rejecting duplicates; no default/missing key success. Failure means do not start and clean only the exact created ID/volume objects proven owned by that attempt.

Local fixture uses the retained original inspect as red: it fails this guard because `/var/log` is missing. A synthetic copy adding only the exact new tmpfs passes the log guard; it is explicitly not an executed-container observation. Mutations for wrong quota, owner, mode, missing safety flag, duplicate flag, log bind/child bind, unexpected Docker volume and writable acquisition root must reject. Compile/exercise the exact embedded guard AST locally with no subprocess/Docker call; retain inputs/results/hash in the dedicated evidence record. No retry is authorized by a pure fixture pass.

## Concrete todo record

- [ ] Synchronize the exact APK log-path diagnosis, retained red proof, bounded tmpfs guard and unchanged preparation/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent corrected-checkpoint review and a new coordinator Task1A dispatch only, create a fresh exact-base acquisition container with the additional private4MiB /var/log tmpfs and validate the complete original mount contract plus exact new log guard before start.
- [ ] Execute only the unchanged approved signed-APK acquisition payload after its inspected log guard passes; preserve the previous exit99 and every new failure, bounded attach/log metadata and exact-owned stop/removal/volume-absence evidence.
- [ ] Require the same private log tmpfs and guard for later approved offline simulation/install containers, with no log bytes entering the committed added layer; preserve no-upgrade/signature/package/file/layer/configuration and frozen-image review requirements.
- [ ] Keep image/toolchain/sentinel/harness outcomes unverified until actually observed under their separate approved steps; preserve original Task2 authority and every production/runtime/grant/service/deployment/readiness denial.

## Execution and evidence boundary

After live tracking sync, commit/push and exact-SHA preflight, obtain independent corrected-plan review and a fresh coordinator Task1A dispatch before creating anything. Adopt/re-pin on the owned preparation branch through coordinator action only. Use a fresh owned directory/run ID/container; never restart the failed container or reuse its APK directory as success. Add the exact log option to the original fixed create command, inspect full created configuration plus this guard, then execute only the original acquire.sh with signed official repositories. If another prerequisite fails, preserve it and stop without unapproved repair/retry.

All prior exact-owned stop/kill/rm --volumes/absence and before/after volume inventory requirements remain, with log tmpfs included. Later offline simulation/install must include the same guarded log sink; stopped-container commit's added layer must contain no new `/var/log/apk.log` change or log-mount bytes. The fixed base's historical log stays in its immutable base layers and is not falsely called newly generated evidence. Original package no-upgrade checks, read-only frozen inputs, nonroot final image/provenance review and separately authorized actual PG17 Task2 remain unchanged. Production/readiness flags remain false.

APK-log correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621303386 and Project8 readback at `2026-11-04T02:57:35.939965+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned APK-log correction checkpoint: `bd59558a78a11448f89e35ef34f910bbb64cedbe`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-apk-log-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621306675. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.
