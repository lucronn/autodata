# Workshop PG17 Acquisition Overlay Successor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent exact-checkpoint review and a fresh coordinator Task1A dispatch. This planning task creates/starts no container and executes no download, retry, package install, image mutation or harness.

**Goal:** Replace only the blocked read-only PG17 APK acquisition root with a disposable inspected writable overlay, require stopped overlay/baseline audits before accepting APK output, and preserve offline installation, separate harness authority and every production/readiness denial.

**Architecture:** Use the existing inspected exact-ID acquisition container with a disposable writable container root overlay, retaining the four bounded private tmpfs mounts and original two private bind mounts. Audit its stopped root filesystem and baseline package/trust/PG hashes before accepting any downloaded APK bytes, then destroy it without commit or reuse. Offline simulation/install/final-image review and actual harness Task2 remain governed by their separate existing contracts.

**Tech Stack:** Cached PostgreSQL17.11 Alpine3.24.3, apk-tools/libapk3.0.8-r0, Docker exact-ID create/inspect/diff/cp/rm, host-only bounded supervision and pure Python guard fixtures.

**Spec:** `docs/superpowers/plans/2026-11-04-workshop-pg17-inspected-preparation.md`; `docs/superpowers/plans/2026-11-04-workshop-pg17-apk-log.md`; `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Planning base: `226cb50fabfbc53c9f674dd72fae9b42aa3775d0` (retained second fail-closed Task1A).
Original immutable harness: `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`.

## Global constraints and precedence

This supersedes only Task1A's `--read-only` acquisition-root requirement and the acquisition branch of the APK-log guard that previously asserted ReadonlyRootfs=true. It removes that flag for one fresh acquisition container and requires ReadonlyRootfs=false. The existing APK payload, exact cached image/source pins, root uid0:0, sole DAC_OVERRIDE capability, official repository/network scope, private bind/tmpfs configuration, deadlines, output bounds and cleanup are unchanged. Do not add a database tmpfs or guess more APK flags. Original offline simulation/install/commit phase configuration is unchanged; the final nonroot Python inspection and original Task2 remain read-only and separately authorized.

No tracked implementation edit, source/secret/production mount, host package install, Docker exec/build/pull/push, privileged container, host namespace/network, arbitrary shell, production role/grant/runtime/provider/cloud/DNS action, integration or readiness claim. No package script or apk add/upgrade/fix/install runs in acquisition. Its writable layer is disposable and must never be committed/exported/imported as an image, restarted, reused by another phase or mounted into an installer. Only independently audited, signed, frozen APK bytes may cross into the unchanged offline stage.

## Two actual blockers and diagnosis

First acquisition under6d65a5: exact container5ea0276a... exited99 at `apk update` with `Unable to open log: Read-only file system`,0 APKs. The independently approved log correction added private4MiB `/var/log` tmpfs, retaining the read-only acquisition root.

Second acquisition under adopted log gate `00aa840e84428a7205314299b4be97c7dd2267d0`: exact container `c3ee9e673c030fc6bf2c47bb8f3932d9f397d089bb77b3aa9dac0440ca056961` passed full pre-start and log guards, then `apk update` exited99 with `Unable to lock database: Read-only file system` and `Failed to open apk database: Read-only file system`. stdout/stderr3229/112 bytes, no timeout/overflow;0 APK files. Exact-owned container removed/absence verified, volume inventory unchanged. No simulation/install/image commit/compilation/server/harness action occurred. Preserve both attempts and their raw receipts, never relabel either as success.

Second raw receipt: `/home/corp/autodata-evidence/pg17-apk-log-prep-20261104-01/evidence/task1a-blocker.json`, SHA256 `76b0b24692aa3e62a317437cd87451a23d63ca296accfbe2f6de78aa6689b18f`. First receipt remains in the preceding canonical evidence index. Dedicated successor evidence `docs/agents/records/2026-11-04-workshop-pg17-acquisition-overlay-evidence.json` retains hashes and exact red facts.

The observed second error demonstrates that the approved update command requires writable APK database state beyond log/cache tmpfs. Rather than approve successive additional writable mounts around individual paths, grant one explicit isolated acquisition overlay and verify all its changed paths/state before its output is trusted. This is a capability change limited to a container root layer, not a writable host filesystem or changed production role. Existing offline installation already uses its own inspected writable root; it receives no additional authority here. No claim is made that the next command/network/signature step will succeed.

## Exact future create and pre-start boundary

After approval only, allocate a fresh private owner1000:1000 mode0700 preparation directory and RUN_ID; retain prior failed directories unchanged. Use the original validated realpath/control-script/private artifact naming rules and fixed original acquire.sh SHA256 `323d24180ae395abbfeb495a70678428336f8902cb00cf25e5d92654f321bdb7`. BASE is literal local `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085`, RepoDigest `postgres@sha256:266d3c257594e195b309ae9d1805e54c788f1d7b375f56bf6c367aac6c917e7b`. The only create-argv policy change is omission of `--read-only`:

```sh
docker create --pull=never --name "autodata-pg17-acquire-$RUN_ID" \
  --cidfile "$PREP/evidence/acquire.cid" --label "autodata.pg17.gate=$GATE_SHA" \
  --network=bridge --user=0:0 --cap-drop=ALL --cap-add=DAC_OVERRIDE \
  --security-opt=no-new-privileges --pids-limit=128 --memory=512m --cpus=2 \
  --restart=no --no-healthcheck --stop-signal=SIGTERM --stop-timeout=10 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/cache/apk:rw,noexec,nosuid,nodev,size=128m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/log:rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700 \
  --mount "type=bind,src=$PREP/apks,dst=/apks" \
  --mount "type=bind,src=$PREP/control,dst=/control,readonly" \
  --entrypoint /bin/sh "$BASE" /control/acquire.sh
```

Inspect the captured full ID while State.Status=created, RestartCount=0. Require Image exactlyBASE, ReadonlyRootfs=false, User0:0, entrypoint/bin/sh, Cmd exactly/control/acquire.sh, no TTY/stdin, no restart/healthcheck/privileged/device/socket/host namespace or port binding, bridge network only, exactly original caps/no-new-privileges/resource limits, exactly two binds and four tmpfs/options. Full original guard remains mandatory except its obsolete acquisition RO assertion; replace that single predicate with the explicit false assertion. Do not weaken all-phase guard behavior or accept a missing ReadonlyRootfs field. Offline and Task2 guard logic does not inherit this override.

Before start, retain complete inspect/config/volume inventories and read-only `docker cp` snapshots from the created root layer of `/lib/apk/db`, `/etc/apk/world`, `/etc/apk/repositories`, `/etc/apk/keys` and fixed PG tool/header hashes. Compare with the pinned saved-image/base manifest. Snapshot existence/type/uid/gid/mode/content hashes; record explicitly absent optional DB files rather than fabricate a hash. No payload or source bind beyond the original private control/APK paths. Only then start that inspected exact ID under original300s deadline,4096-byte streamed attach and1MiB cap per stdout/stderr; on overflow/timeout stop/kill/retain failure. Root512MiB,pid128,cpu2 and existing tmpfs quotas remain. The overlay is not claimed to have a new hard filesystem quota: its accepted diff/file count/content size is bounded below; an unexpected storage/resource error fails and cleans the exact attempt.

## Stopped acquisition audit before any output acceptance

A zero process exit is necessary, not sufficient. After independently confirming stopped exit0, OOMKilled=false and State.Error empty, retain `docker diff ID` and bounded `docker cp` root-state snapshots before removal. Treat APK output as quarantined until this audit and cleanup pass; failure never enters simulation/install or image provenance.

1. Parse all diff rows as exact actionA/C/D and absolute normalized paths; at most128 rows, no NUL/newline ambiguity, repeated path, traversal or symlink escape. No deletion action is permitted. Full diff must be retained in bounded evidence, never filtered into apparent success.
2. The only new/changed root-layer data object allowed is regular `/lib/apk/db/lock` (A/C), root uid/gid0:0, single-link, no execute/setuid/setgid/group-or-other-write bits, size<=4096 bytes. It may be absent if update removes its lock. Retain its hash/type/mode/owner if present; never execute it. `C` directory metadata rows at `/lib`, `/lib/apk`, `/lib/apk/db`, `/var`, `/var/cache`, `/var/log` are allowed only with baseline directory identity/type/uid/gid/mode unchanged (timestamps excluded). No added directories or changed mounts are implicitly accepted.
3. `C` rows for baseline `/lib/apk/db/installed`, `/lib/apk/db/triggers`, `/lib/apk/db/scripts.tar` or `/etc/apk/world` are permitted only when existence/type/uid/gid/mode/content hash is exactly baseline; time-only copy-up is not a package change. If optional files were absent, newly creating them fails. No `.new`, backup, alternate DB, package scripts, fetched APK or arbitrary cache file is allowed in the root layer. Other DB state changes are blockers, not an invitation to expand the allowlist.
4. `/var/cache/apk`, `/var/log`, `/tmp` and PGDATA retain their inspected bounded tmpfs; cache/log contents belong only there. Any child cache/log/tmp/PGDATA path in the root-layer diff rejects as an unexpected write/mount failure. Output APK files exist only in the private `/apks` bind. Installed-base package map/installed DB and `/etc/apk/world` must be unchanged; all key/repository and PG tool/header baseline hashes must match. Diff outside the exact allowlist rejects even if an attacker restores a high-level package list.
5. Maximum allowed changed root-layer regular-file content is4096 bytes (the optional lock); metadata rows do not authorize code/data writes. Preserve base/final snapshots and diff hashes; independently review any unfamiliar row before a new gate, never waive it during this attempt. This is a post-run acceptance bound for trusted fixed acquisition commands, not a claim of an enforced runtime disk quota or protection against a malicious Docker daemon/host root.

The pure parser below validates only the diff path/action portion; the baseline/type/hash/size checks above and original complete config/mount checks remain separately mandatory:

```python
LOCK_PATH = '/lib/apk/db/lock'
DIRECTORIES = {'/lib', '/lib/apk', '/lib/apk/db', '/var', '/var/cache', '/var/log'}
BASELINE_FILES = {'/lib/apk/db/installed', '/lib/apk/db/triggers',
                  '/lib/apk/db/scripts.tar', '/etc/apk/world'}
def validate_acquisition_diff(rows):
    assert type(rows) is list and len(rows) <= 128
    seen = set()
    for row in rows:
        assert type(row) is str and len(row) <= 256 and '\n' not in row and '\x00' not in row
        assert len(row) >= 4 and row[1] == ' ' and row[0] in ('A', 'C')
        action, path = row[0], row[2:]
        assert path.startswith('/') and '//' not in path
        assert all(part not in ('', '.', '..') for part in path.split('/')[1:])
        assert path not in seen
        seen.add(path)
        assert path == LOCK_PATH or (action == 'C' and path in DIRECTORIES | BASELINE_FILES)
```

A separate pre-start fixture uses the retained actual second inspect: it fails the explicit ReadonlyRootfs=false predicate. A synthetic copy changing only that field passes that predicate; it is not a real container or successful acquisition. Diff fixtures must accept empty and permitted lock/metadata rows and reject deletion, code/repository/cache/log changes, traversal, symlink-target path spelling, unknown action, duplicates and over-bound inventories. Execute only these pure predicates locally; retain actual red hashes separately from synthetic fixture results.

## Output freeze, cleanup and downstream boundary

Even after zero exit and audit pass, require the original signed-index/package verification, exact official repositories, APK manifest/hashes/arch, no baseline upgrade and bounded attach receipts. No package install/script occurs in online acquisition. Fixed bridge authority is command-bound, not a claimed egress firewall. Network/TLS/signature/package/command failures remain blockers; no fallback flags, repos, rootcap or broader policy change. This plan does not authorize any retry after a new failure.

Remove only the captured exact acquisition ID using original bounded stop10s/kill then rm --volumes/absence30s and before/after normalized volume inventories. Do not restart it to audit, perform docker exec, commit/save/export its overlay, reuse the stopped object or convert it into the offline installer. Only read-only inspect/diff/cp operations on stopped state are allowed during audit. Private APK output stays quarantined on failure and is preserved as failed evidence, never reused as a passed input. Destroy the entire acquisition root layer with its exact container; rootfs audit/cleanup failure means no accepted APK closure even when the download succeeded.

After all checks and cleanup succeed, separately review/freeze only the APK closure for the already defined network-none simulation/install stage, whose create/mount/capability/log and stopped-installer commit rules are unchanged. New installer starts independently from the exactBASE; no acquisition overlay/root files carry forward. Final image review, sentinel compilation and actual Task2 remain separately gated; every production/runtime/grant/schema/service/deployment/readiness denial remains false/unavailable. No planner integration or retry occurs here.

## Concrete todo record

- [ ] Synchronize both preserved exit99 attempts, acquisition-only overlay decision, exact create/audit/cleanup contracts and unchanged offline/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent exact-checkpoint review and fresh coordinator Task1A dispatch only, create a new exact-base acquisition container with one disposable writable root overlay and unchanged private mounts/caps/network/commands; inspect its full created configuration and record baseline file hashes before start.
- [ ] Run only the unchanged signed official APK acquisition payload under the existing bounded supervisor; require zero exit, unchanged baseline package/key/repository/PG data and an exact stopped docker diff audit before freezing any APK output.
- [ ] Never commit, restart or reuse acquisition containers; retain every failure/audit/cleanup receipt, remove only the captured exact-owned ID/volumes and verify absence/unchanged volume inventory before downstream use.
- [ ] Keep offline simulation/install/commit configuration and original Task2 separately authorized and unchanged; no image/toolchain/harness/runtime/production readiness follows from plan synchronization or synthetic guard fixtures.

Acquisition-overlay successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621400986 and Project8 readback at `2026-11-04T03:04:46.045770+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


Acquisition-overlay adoption: approved checkpoint `26989e1de7a71ac4f7c23da043dd367548e2ba45` (receipt `80d4a20dcd7603a81d1ef96307e94fafe32caafe`) adopted at `1fe22c943143d8955624ed75c0f378bdb2dc0439`, directly after actual second failed evidence `226cb50fabfbc53c9f674dd72fae9b42aa3775d0`. Five harness54ab files and both raw exit99 receipts unchanged. Issue186/Project8 live readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621449880 at 2026-11-04T03:08:28.641173+00:00; exact hashes in dedicated overlay record and full predecessor Project index preserved verbatim in comment. This is adoption only: no Docker/create/start/download/retry/install/image commit; adopted full-SHA preflight and root verification/new Task1A dispatch required. Offline stages/Task2 remain separately unauthorized; runtime/production/readiness unverified.


## PG17 empty bind-target diff successor: plan only

Permit only proven Docker-created empty acquisition bind-target directories in the stopped overlay diff, retain every other audit and cleanup constraint, and keep all quarantined APKs unusable.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-bind-targets.md`; record `docs/agents/records/2026-11-04-workshop-pg17-bind-targets.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-targets.json`. Retained e1ca208 attempt exited0/signatures33 but failed strict diff on A /apks and A /control;33 APKs remain quarantined and never reusable. Only exact added empty root-owned directories may pass after absent saved-base targets, exact prestart binds and bounded created/stopped underlying filesystem export audits. Files/children/other paths/missing proof reject. All original constraints, offline/Task2 authority and cleanup unchanged. No planning Docker/download/retry/harness; independent exact-gate review/new dispatch pending.

Concrete todo:

- [ ] Synchronize exact red receipt, bounded structural audit and context-bound diff guard in Issue186/Project8/canonical docs; push exact gate and pinned preflight for independent review.
- [ ] After independent exact-gate review/adoption and fresh coordinator Task1A dispatch only, create a fresh acquisition container and collect full prestart bind inventory plus bounded underlying filesystem structural audit before start.
- [ ] Require exact empty directory metadata before/after, absent saved-base targets, unchanged 27 baseline records and original complete stopped diff/signature/exit audits; reject files, descendants, aliases, deletions and missing proof.
- [ ] Retain prior 33 quarantined APKs as failed evidence, never accept/reuse them; any future fresh output requires all audits and exact-owned removal/absence/volume proof.
- [ ] Keep acquisition commands/network/caps/mounts and offline simulation/install/image/Task2 authorities unchanged; no planning Docker/download/retry/harness action or readiness claim.

Bind-target successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621533357 and Project8 readback at `2026-11-04T03:13:58.668948+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned bind-target successor checkpoint: `016ea37722f36fa0c8b2b509884e75bef6ac41b2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-targets-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621541625. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed bind-target gate adoption and mandatory operation ordering

Adopted source gate `016ea37722f36fa0c8b2b509884e75bef6ac41b2`, receipt `c7d57a3347621c5559d5a671997142da1a1f43dc`; exact reviewed plan SHA256 `40e0591c8742a37983cf289d565c9df7d4e263c7caa5cc4e8e7f38b3b36f49ed`. Coordinator relayed independent approval of this exact plan. Adoption branch `codex/workshop-pg17-bind-target-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-target-adoption.json`. This adoption performs no Docker operation or retry and conveys no production/harness readiness.

**Mandatory future order (resolves the created-state mountpoint feasibility condition):** (1) create exact-owned fresh acquisition container under the unchanged approved argv, validate full created inspect/config/bind inventory and pinned base archive; (2) complete **all inherited prestart `docker cp` baseline snapshots** and the unchanged27-record saved-base comparison while still created/never-started; these existing copy operations materialize the bind-target directories; (3) only **after those copies finish successfully**, perform the first bounded created-state underlying filesystem export and full prestart diff, requiring the exact empty root-owned `/apks` and `/control` directories plus `A /apks` and `A /control`; (4) only after every inherited and new prestart guard passes may the coordinator-dispatched payload start; (5) after stopped exit0, perform the bounded stopped export/full diff/unchanged-baseline audits, then exact-owned cleanup and output acceptance boundary. Never run the first export/diff before the inherited copies or start merely to materialize targets. Failed copies, missing/changed/nonempty targets or any ambiguity fail closed and clean the exact owned attempt. No extra container command, mount or authority is added.

All prior export bounds/source semantics checks, acquisition payload/image/network/caps/resources/mounts, signature verification, quarantine, baseline/row/type/empty checks and cleanup remain mandatory. This ordering clarification does not accept or reuse the historical33 quarantined APKs. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged. No deployment, integration, production grant/runtime action or readiness follows.

Concrete adoption todo:

- [ ] Record independent approval of exact gate016ea377 and reviewed plan SHA256, synchronize adoption Issue186/Project8/canonical docs, then push and pin passing full-SHA preflight.
- [ ] Only after new coordinator dispatch, validate exact created acquisition ID/config/bind inventory; complete every inherited prestart docker cp baseline snapshot and unchanged27-record comparison BEFORE first created-state export/diff.
- [ ] Then require bounded created-state underlying empty-directory export and exact A /apks,A /control diff; only after all guards pass may the fixed acquisition payload start.
- [ ] Require matching stopped structural export, complete original baseline/diff/signature/exit audits and exact-owned cleanup/absence/volume proof before accepting any newly acquired APK closure.
- [ ] Never accept/reuse historical33 quarantined APKs; no Docker/download/install/harness on adoption turn; offline stages/Task2 and all production/readiness denials unchanged.

Reviewed bind-target adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621594414 and Project8 readback at `2026-11-04T03:18:09.877892+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed bind-target adoption checkpoint: `76fd86e5a356ae611d643e621f9ae03660d50206`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621597936. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 complete mount-record ordering successor: plan only

Correct only order-sensitive acquisition Mounts inspection comparison using complete records keyed by unique exact Destination, retaining all raw/canonical hashes, red receipts and unchanged acquisition guards.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-mount-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-mount-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order.json`. Base da1f42a; actual fresh acquisition attempt stopped before startup on inspect Mounts array order only,0 APKs, exact-owned cleanup/absence and unchanged volume inventory. Preserve red result/diagnosis exact hashes in dedicated evidence. Replace only top-level Mounts array order-sensitive equality with complete-record canonical JSON by unique exact Destination; duplicates/missing/extra paths or any field drift reject. All original config/structural/baseline/signature/diff/payload/cleanup and offline/Task2 limits unchanged. Live tracking synchronized; independent exact-checkpoint review/root dispatch remain pending. No retry authority. No planning Docker/retry/download/harness.

Concrete todo:

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
