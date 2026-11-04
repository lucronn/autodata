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

Pinned acquisition-overlay successor checkpoint: `26989e1de7a71ac4f7c23da043dd367548e2ba45`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-acquisition-overlay-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621404413. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.
