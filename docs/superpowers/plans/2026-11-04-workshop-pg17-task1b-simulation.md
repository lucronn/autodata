# Workshop PG17 Task1B Simulation-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent exact-checkpoint review, coordinator adoption/root verification and fresh Task1B SIMULATION-ONLY dispatch. This checkpoint is docs only; no Docker operation or package execution occurs while drafting/synchronizing it.

**Goal:** Gate one bounded offline Task1B simulation of the immutable independently accepted33APK closure using exact20 new-package inputs, unchanged baseline and complete cleanup; installation/image/Task2 remain separately unauthorized.

**Architecture:** Consume the independently accepted frozen33APK manifest without altering its bytes. A single fresh exact-ID cached-base container runs offline simulation with the exact20 absent-package files, then is structurally audited and removed. Independent simulation review is a new boundary before any installation plan; no solver success is inferred from metadata or synthetic fixtures.

**Tech Stack:** Cached PostgreSQL17.11/Alpine3.24.3 amd64, Docker28.5.2+dfsg4/API1.51/overlay2, apk-tools3.0.8-r0; host Python3 pure guards.

**Spec:** Independent report `/tmp/autodata-pg17-task1b-preflight-review.md`, SHA256 `e82b42d46639d0149b7cf644cb0bbdd29f86bb020cf5410fcdfcea007779ab88`; complete bytes and hashes in `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`. Canonical gate `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Branch `codex/workshop-pg17-task1b-simulation-plan`; base closure receipt `fdf1f8191c0648cbebd1f236707e31fa09a730a9`; input-acceptance gate `04093a5e176499e7d8de18e9573f9fea3abe9d3a`.

## Global constraints and exact precedence

This successor replaces only the older inspected-preparation Task1B simulation wildcard, ambiguous bind-target/lock rules and unbounded output acceptance. It proposes only ONE fresh offline simulation attempt after review/adoption/root dispatch. The old Task1B installation and Task1C image creation are explicitly held, including addgroup/adduser/source creation, package extraction/scripts/triggers, image commit, nonroot toolchain inspection and image save. A subsequent reviewed installation gate must use the identical frozen selection/input hashes and apk-add options except removal of `--simulate`; no extra package, force, no-scripts, no-triggers, untrusted/key change, version drift or fallback may be smuggled into that later phase. This plan does not authorize future installer script changes or runtime now.

All predecessor acquisition guards, accepted closure provenance, canonical full Mounts comparison, Cc-safe classifier, structured full-volume equality and cleanup bounds remain mandatory where applicable. Original source/harness54ab7dce19c36ce7ea3403259dd1ecc66bf323aa remains unchanged and unmounted here; original Task2 PG startup/harness requires separate authority. No build/pull/push/commit/import, Docker exec, Compose/service, host package install, new network/download, secrets/source/evidence mount, host namespace, production runtime/grants/provider/cloud/DNS/deployment or readiness claim. Both prior33APK sets remain quarantined NEVER reusable. Task1A accepted raw manifest's historical pending-review status remains immutable; input acceptance is adjacent metadata only.

## Exact accepted input and five review corrections

Use only `/home/corp/autodata-evidence/pg17-bind-target-prep-20261104-03/apks`,33 regular root-owned0644 APKs /89812028bytes, beneath validated private uid1000 mode0700 ancestors; mount this exact directory read-only. Verify no symlinks/hardlinks/extra/hidden files, exact33 filenames/sizes/SHA256 before create, before start and after removal against immutable `evidence/accepted-apk-manifest.json` SHA256 `cfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238`. Task1A result SHA256 `19002cbf07ce2879e277e1a3e7bc1d69ac28ae8e919e29a85bc4d7a415ee3d43`; closure independent report SHA256 `bb0173a6f7a46f52fd7a4c3bfbcfcf00d2db5714f179abfe1124675a69616b5b`. Missing/mutated bytes stop; do not fetch or reuse a quarantined set.

1. Verify all33, but pass only the following20 absent-package files, in accepted manifest order, to `apk add`. The13 baseline packages remain signature/hash-verified mounted input, excluded only from add selection. Full selection entries/hashes and excluded13 entries are in `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`.
2. Carry explicit created AND stopped underlying bind-target/context proof into this offline phase. Two empty mountpoint directories are permitted; files/children/other paths are rejected.
3. Preserve inherited `/lib/apk/db/lock` exactly: regular type0, uid0/gid0, mode0600, size0, empty linkname, SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. No deletion, new lock, changed metadata or transient-lock exception.
4. Pin script bytes/argv and parse complete bounded stdout deterministically;20 additions only, zero baseline actions; reconstruct complete unchanged stopped state. Ordinary signed package descriptions containing error are valid in their exact baseline section.
5. Pin inherited BusyBox trigger and scripts archive. Simulation success cannot prove actual trigger effects or capability sufficiency; later installation needs separate explicit diff/symlink/trigger audit before dispatch.

## Task1B-S1: Validate inputs and freeze payload without Docker execution

**Files:** only host-private `PREP/control/simulate.sh`, `PREP/control/repositories`, host-only `PREP/evidence` after runtime dispatch; no tracked implementation files.
**Consumes:** exact accepted manifest, cached BASE and adopted gate SHA. **Produces:** immutable script/hash, argv and preflight receipts.

- [ ] Reverify exact BASE `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085`, RepoDigest `postgres@sha256:266d3c257594e195b309ae9d1805e54c788f1d7b375f56bf6c367aac6c917e7b`, platform/rootfs10layers, retained base archive SHA256 `60ae29e1f3496f1ec842b48995fcc631d9c6e918b20da48a154fd7258fa3106d`, matching base45 and image27 baseline SHA256 `eb41e13ccdbaf76e8f84eba2a6e09af0af77376ce91ddb4564c56a3d221d9178`. No tag or registry resolution.
- [ ] Allocate a NEW unique private absolute `PREP` under `/home/corp/autodata-evidence`, uid1000/gid1000 mode0700, never reuse prior artifact paths. `RUN_ID` is new `[a-z0-9-]{1,32}`, exact name/cidfile absent. Resolve each source via realpath, reject symlinks, colon/comma/newline/control characters. `FROZEN_APKS` is the exact accepted path above, never a copy with changed ownership/provenance. `GATE_SHA` is a full reviewed/adopted/passing checkpoint. Create only control/evidence in PREP. Control files0444, directory0700; evidence host-only. No inherited host env-file/proxy/custom DNS.
- [ ] `control/repositories` has exactly these UTF-8 bytes including final LF:

```text
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community
```

- [ ] Write `simulate.sh` exactly as below, LF endings; require SHA256 `068cb46037387a6d38491f2fbcf1d71c99797223dfce7649c015d7bc61d114de`. Hash all control files before create/start and after cleanup. No parameter-supplied package names, wildcard selection, arbitrary commands or extra payload.

```sh
#!/bin/sh
set -eu
umask 022
cmp /etc/apk/repositories /control/repositories
printf '%s\n' 'AUTODATA_PG17_BASELINE_BEFORE_BEGIN'
apk info -vv
printf '%s\n' 'AUTODATA_PG17_BASELINE_BEFORE_END'
printf '%s\n' 'AUTODATA_PG17_VERIFY_BEFORE_BEGIN'
apk verify /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gdbm-1.26-r0.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libcrypto3-3.5.9-r0.apk /apks/libexpat-2.10.0-r0.apk /apks/libffi-3.5.2-r1.apk /apks/libgcc-15.2.0-r5.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libncursesw-6.6_p20260516-r0.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/libssl3-3.5.9-r0.apk /apks/libstdc++-15.2.0-r5.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-1.2.6-r3.apk /apks/musl-dev-1.2.6-r3.apk /apks/ncurses-terminfo-base-6.6_p20260516-r0.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/readline-8.3.3-r1.apk /apks/sqlite-libs-3.53.4-r0.apk /apks/xz-libs-5.8.4-r0.apk /apks/zlib-1.3.2-r1.apk /apks/zstd-libs-1.5.7-r2.apk
printf '%s\n' 'AUTODATA_PG17_VERIFY_BEFORE_END'
printf '%s\n' 'AUTODATA_PG17_SIMULATION_BEGIN'
apk add --simulate --no-network /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libexpat-2.10.0-r0.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-dev-1.2.6-r3.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/sqlite-libs-3.53.4-r0.apk
printf '%s\n' 'AUTODATA_PG17_SIMULATION_END'
printf '%s\n' 'AUTODATA_PG17_VERIFY_AFTER_BEGIN'
apk verify /apks/binutils-2.45.1-r1.apk /apks/gcc-15.2.0-r5.apk /apks/gdbm-1.26-r0.apk /apks/gmp-6.3.0-r4.apk /apks/isl26-0.26-r2.apk /apks/jansson-2.15.0-r0.apk /apks/libatomic-15.2.0-r5.apk /apks/libbz2-1.0.8-r6.apk /apks/libcrypto3-3.5.9-r0.apk /apks/libexpat-2.10.0-r0.apk /apks/libffi-3.5.2-r1.apk /apks/libgcc-15.2.0-r5.apk /apks/libgcc-static-15.2.0-r5.apk /apks/libgomp-15.2.0-r5.apk /apks/libncursesw-6.6_p20260516-r0.apk /apks/libpanelw-6.6_p20260516-r0.apk /apks/libssl3-3.5.9-r0.apk /apks/libstdc++-15.2.0-r5.apk /apks/mpc1-1.3.1-r1.apk /apks/mpdecimal-4.0.1-r0.apk /apks/mpfr4-4.2.2-r0.apk /apks/musl-1.2.6-r3.apk /apks/musl-dev-1.2.6-r3.apk /apks/ncurses-terminfo-base-6.6_p20260516-r0.apk /apks/pyc-3.14.10-r1.apk /apks/python3-3.14.10-r1.apk /apks/python3-pyc-3.14.10-r1.apk /apks/python3-pycache-pyc0-3.14.10-r1.apk /apks/readline-8.3.3-r1.apk /apks/sqlite-libs-3.53.4-r0.apk /apks/xz-libs-5.8.4-r0.apk /apks/zlib-1.3.2-r1.apk /apks/zstd-libs-1.5.7-r2.apk
printf '%s\n' 'AUTODATA_PG17_VERIFY_AFTER_END'
printf '%s\n' 'AUTODATA_PG17_BASELINE_AFTER_BEGIN'
apk info -vv
printf '%s\n' 'AUTODATA_PG17_BASELINE_AFTER_END'
```

The exact20 selected literal paths are the sole `apk add` operands. Both verification phases enumerate all33 explicitly. Future installer contract is this same ordered20 vector and same add options except removing `--simulate`; installation remains unauthorized and needs a new gate.

Read-only dependency metadata:45 installed BASE +20 absent packages satisfy58 declarations (36 BASE-provided/22 new-provided), including repeated declarations as distinct records. Only minimum constraints are BASE libssl3 3.5.9-r0>=3.3.0 and new libexpat2.10.0-r0>=2.9.0; exact constraints match. The evidence index retains all58 requirements and exact provider,20 `.PKGINFO` records/hashes and base45 versions/provides. No selected non-directory payload path collides with a baseline-owned file per independent review. These facts and source inspection are NOT solver/installability success.

## Task1B-S2: Inspect one new network-disabled container before start

**Consumes:** pinned script/input hashes and exact BASE. **Produces:** exact full container ID, created state/mount/export/diff/context/baseline receipts.

- [ ] Capture bounded complete-volume inventory BEFORE create using inherited structured protocol: `docker volume ls --format '{{json .}}'` under10s/256KiBstdout/64KiBstderr, max32 names; inspect each exact name with `docker volume inspect NAME` under10s/512KiBstdout/64KiBstderr; total60s/16MiBstdout/2MiBstderr; chunk65536. Reject duplicate JSON keys/names, null/malformed/unknown/truncated/overflow records. Preserve complete inspect objects keyed unique Name; no dropped fields or Labels/name/driver/scope changes, only JSON object key order normalized. No Docker volume operation is allowed in this planning turn.
- [ ] After runtime dispatch only, render this complete fixed create argv (no `--rm`):

```sh
docker create --pull=never --name "autodata-pg17-simulate-$RUN_ID" \
  --cidfile "$PREP/evidence/simulate.cid" --label "autodata.pg17.gate=$GATE_SHA" \
  --network=none --user=0:0 --cap-drop=ALL \
  --cap-add=CHOWN --cap-add=FOWNER --cap-add=DAC_OVERRIDE \
  --security-opt=no-new-privileges --pids-limit=128 --memory=1g --cpus=2 \
  --restart=no --no-healthcheck --stop-signal=SIGTERM --stop-timeout=10 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=128m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/log:rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700 \
  --mount "type=bind,src=$FROZEN_APKS,dst=/apks,readonly" \
  --mount "type=bind,src=$PREP/control,dst=/control,readonly" \
  --entrypoint /bin/sh "$BASE" /control/simulate.sh
```

The isolated root overlay is writable solely for this bounded simulator; no writable host bind. Preserve inherited offline CHOWN/FOWNER/DAC_OVERRIDE capabilities exactly, no added authority. No SETUID/SETGID/NET_RAW/SYS_ADMIN/host network/ports/volume-from/privilege; no source/evidence/secret bind. Exactly two read-only binds and three bounded tmpfs; inherited PGDATA VOLUME is overridden, never allocated anonymously. No `/var/cache/apk` host or tmpfs mount is introduced. Ephemeral `/var/log` shadows base logs; tmpfs logs cannot be sole evidence. Runtime Docker-managed hosts/hostname/resolv/dev/shm/proc/sys paths are recorded separately.

- [ ] Retain full raw created inspect, require Image exact BASE, Status created/RestartCount0, entrypoint/args/env/user/network/resources/caps/security/restart/healthcheck matching above. Validate full `.HostConfig` and exactly two complete `.Mounts` records, unique exact Destinations /apks,/control, exact source realpaths, bind type, RW=false, Mode/Propagation and ALL other fields. Canonical comparison sorts complete records only by unique Destination and JSON object keys; duplicate/missing/extra target or field drift fails. Retain each raw inspect SHA256 and canonical JSON SHA256. Record tmpfs configuration separately with exact flags/sizes/owners. Validate no owned or unexpected volume and base absent target proof before further inspection.
- [ ] Mandatory operation ordering: copy all inherited27 created-state baseline records using the predecessor read-only `docker cp ID:PATH -` snapshot protocol BEFORE the first created export or diff. Use exactly these ten cp source operands, each as `docker cp ID:PATH -`: `/lib`, `/var`, `/etc/apk`, `/usr/local/bin/postgres`, `/usr/local/bin/initdb`, `/usr/local/bin/pg_ctl`, `/usr/local/bin/psql`, `/usr/local/bin/pg_config`, `/usr/local/include/postgresql/server/pg_config.h`, `/usr/local/include/postgresql/server/postgres.h`. Retain complete raw archives (including inherited `/var`/`/lib` context), independently reconstruct exact27 path/record fields in image-baseline index and reject unexplained context changes. Each copy30s/32MiBstdout/1MiBstderr,4096byte chunks; complete safe tar parse/normalized exact path/type/uid/gid/mode/size/linkname/content SHA, duplicates/PAXescape/hardlink ambiguity rejected. Require reconstructed map EXACTLY equals image27 baseline, not a subset. This also materializes underlying empty bind targets. Hash/recheck control and33APKs; no start until all snapshots and checks pass.
- [ ] Only then capture first created `docker diff ID` and bounded `docker export ID`. Require exact Docker diff rows `A /apks` and `A /control`, unique/unordered, no extras. Authenticate prior base-image archive hash/layer order and absence of either path or descendants. Reconstruct created export under60s, stdout512MiB/stderr1MiB,65536byte chunks, max50000entries/cumulative uncompressed512MiB, complete EOF/two zero blocks and no unsupported trailing data, duplicate/ambiguous/PAXextended path, symlink/hardlink escape or truncation. Exact underlying /apks,/control each type5 root0:0 mode0755 size0 linkname empty, no descendants/content. Record complete metadata/canonical hashes. `docker export` exposes underlying root-layer directory for a mounted target rather than host mounted contents, as pinned Docker bind-target plan documents/source proves; cross-check full pre/post inspect inventory and raw archives. Any exporter timeout/limit/parse/semantic ambiguity blocks; no partial acceptance. Delete only exact private export archive after retaining its byte/hash/audit receipts; no import/save-image/reconstruction.

## Task1B-S3: One bounded simulation, deterministic output, unchanged stopped state

**Consumes:** fully validated created ID. **Produces:** raw bounded attach/status, exact20 proposal and unchanged baseline proofs; never installed packages.

- [ ] Start only the full inspected ID once with `docker start --attach ID`, stdin closed, no TTY, supervisor180s, read4096 chunks, max1MiB stdout and1MiB stderr. Store raw bytes/lengths/SHA256 and complete argv/timestamps. Deadline/overflow/incomplete framing/any stderr/invalid UTF8/Cc other than LF/tab fails. On failure retain stopped inspect/diff if possible, exact-owned cleanup and failed/quarantined receipt; never retry, loosen guards or accept partial output. Attachment return0 alone is insufficient: stopped inspect must be exited, Running=false, ExitCode0, OOMKilled=false, State.Error empty, no restart.
- [ ] Apply the exact pure parser below to raw stdout/stderr with the evidence index's selected20 `(pkgname,pkgver)`, exact45 baseline-info text and expected33 signature lines. Check full source payload and key hashes as well; the parser is not a substitute for cryptographic input or state proof. Default noninteractive verbosity/noTTY is fixed; unexpected progress/extra output or a format differing from pinned APK3 source is a blocker, not a parser fallback. Both package-info sections must match the full known baseline text, including benign description `Common error description library`. Actions may be solver-ordered but every one must be unique exact selected name/version with consecutive correctly padded1..20 counters/denominator20. Exactly one bounded `OK:`65packages summary follows; no unresolved dependency/removal/reinstall/upgrade/replacement/pinning/script/trigger/unknown line. Humanized size grammar is presentation only; independent state/package maps establish content.

```python
import re, unicodedata

def accept_simulation(stdout, stderr, selected, baseline, verified):
    assert isinstance(stdout, bytes) and isinstance(stderr, bytes)
    assert len(stdout) <= 1048576 and stderr == b""
    text = stdout.decode("utf-8", errors="strict")
    assert text.endswith("\n")
    assert all(unicodedata.category(c) != "Cc" or c in "\n\t" for c in text)
    lines = text.split("\n")[:-1]
    assert not any(re.match(r"^[ \t]*(?:WARNING:|ERROR:|UNTRUSTED(?:[ :]|$)|BAD SIGNATURE(?:[ :]|$))", line) for line in lines)
    assert len(selected) == 20 and len({name for name, version in selected}) == 20
    cursor = 0
    sections = {}
    for label in ("BASELINE_BEFORE", "VERIFY_BEFORE", "SIMULATION", "VERIFY_AFTER", "BASELINE_AFTER"):
        begin, end = "AUTODATA_PG17_" + label + "_BEGIN", "AUTODATA_PG17_" + label + "_END"
        assert lines[cursor] == begin
        cursor += 1
        start = cursor
        while cursor < len(lines) and lines[cursor] != end:
            assert not lines[cursor].startswith("AUTODATA_PG17_")
            cursor += 1
        assert cursor < len(lines)
        sections[label] = lines[start:cursor]
        cursor += 1
    assert cursor == len(lines)
    assert sections["BASELINE_BEFORE"] == baseline.splitlines() == sections["BASELINE_AFTER"]
    assert sections["VERIFY_BEFORE"] == verified.splitlines() == sections["VERIFY_AFTER"]
    actions = sections["SIMULATION"]
    assert len(actions) == 21
    expected, seen = set(selected), set()
    for number, line in enumerate(actions[:20], 1):
        prefix = f"({number:2d}/20) Installing "
        assert line.startswith(prefix)
        match = re.fullmatch(r"([a-z0-9][a-z0-9+_.-]*) \(([A-Za-z0-9+_.~-]+)\)", line[len(prefix):])
        assert match is not None
        pair = match.groups()
        assert pair in expected and pair not in seen
        seen.add(pair)
    assert seen == expected
    # No free-form postamble, scripts, triggers, progress controls, repositories or unresolved action is accepted.
    assert re.fullmatch(r"OK: (?:[0-9]{1,9}|[0-9]{1,9}\.[0-9]) (?:B|KiB|MiB|GiB|TiB) in 65 packages", actions[-1])
    return {"added": 20, "baseline_changed": 0, "simulator_output_only": True}
```

Read-only source evidence pins apk-tools v3.0.8 `commit.c` SHA256 `d1ffe78256e6d9b061be8cecee94f3076b665b1de830fbc3156107a8405edd24`: action format lines67-109, all non-new actions76-99, simulate suppresses install490-491, package total/proposed-size522-541. `database.c` SHA256 `70ed32b5276d67b75a1cb923bfe503f2e698e8f3fb6e764176c0d29926d0b335` lines2319-2320 suppresses config writes under simulate. `package.c` SHA256 `6d7abea38f045d3132d73da0720f5e193658644548b53e85d8110af0db5e55b6` lines751-752 suppresses install/trigger scripts; commit hooks likewise skip simulate. `print.c` pins humanized units/noTTY progress behavior. Full source URLs/bytes/hashes in evidence; this is command/parser feasibility, not proof of the cached binary's runtime result. Unknown output fails closed.

- [ ] Copy identical27 snapshots from STOPPED ID, reconstruct independently and require exact base/pre/post equality; retain raw tar/record hashes. Reparse installed DB into exact45 name/version map, no20 added entries, unchanged `/etc/apk/world`, lock record, scripts.tar.gz, trigger file, signing keys/repos/arch, PG tools/headers. Equality covers all record fields and bytes; no transient-state exception. Baseline scripts archive SHA256 `6d38f42e96d5c90c2b83996d7bd49440b63378d94a2af851cda5f919dfef54d9`. No user/group/source changes authorized. APK log is ephemeral; attach/package/signature/exit and independent stopped receipts provide retained evidence.
- [ ] Capture complete stopped inspect and full diff, repeated bounded structural export and full Mounts canonical hash comparison with created state. Preserve all complete records, allow only phase State changes; compare container identity/config/HostConfig/mounts/input hashes. Stopped diff must again be EXACT set `A /apks`,`A /control`; NO changed files, database/world/cache/lock directories, users/groups or other root-layer paths are accepted for simulation. Exact empty directory metadata/absence of descendants must match created; mounted host contents cannot be used as underlying proof. The strict diff may fail on a genuine unexplained simulator write: retain and stop for a new reviewed gate rather than broaden to generic APK side effects. Any new transient lock or unexplained metadata/path rejects.

## BusyBox trigger boundary and separate future work

The downloaded33 APKs have no install/upgrade/trigger scripts, but BASE does. Exact retained trigger `busybox-1.37.0-r31.X1b5405ebc02f7dd8be95b6265c54b243d5456ab8f.trigger`, SHA256 `c7840b111dd82669de2074ea3c7e345c063928db2bbff650a81289777b3ff98f`, complete bytes in evidence. Trigger registration covers `/bin /usr/bin /sbin /usr/sbin /lib/modules/* /usr/lib/modules/*`; applicable directory changes invoke `/bin/busybox --install -s` (and existing bbsuid/busybox-extras branches); module paths may invoke BusyBox depmod under its explicit condition. Simulation must execute none and leave script/registration bytes unchanged. Script absence in downloads is not a claim of no installed trigger. Future installation gate must enumerate expected selected signed payload changes, BusyBox-created/replaced symlinks, registration/script/database/world changes, preserve baseline package/PG/key/user state except separately approved changes, and audit any capability error/path drift. No automatic capability addition, `--no-scripts`/`--no-triggers` or blanket symlink exception. Actual installer/image behavior remains untested and unauthorized.

## Task1B-S4: Exact-owned cleanup and independent simulation review

- [ ] On success OR failure, retain all bounded raw receipts and final inspect before removing only captured exact-owned ID. Use stop10s if running, kill only same captured ID if needed, inspect/reap/remove30s; `docker rm --volumes ID`, then exact inspect absence with expected no-such-container and bounded empty `docker ps -a --no-trunc --filter id=ID` result. Unexpected volume means do not start: retain exact owned volume identification, remove only owned container/proven-created volume and verify absence; no prune/bulk/prefix cleanup. If removal/absence is ambiguous, fail and alert coordinator; never claim pass.
- [ ] Re-run complete bounded structured volume protocol after removal, exact same unique Name set and ALL complete object fields/values as before, only JSON object key ordering normalized. Retain raw list/inspect hashes and complete canonical comparison SHA. Rehash all33 APK/control bytes and retain untouched accepted input manifest. No new output APKs, network acquisition or raw accepted-manifest mutation. Dispose only exact private temporary exports/control as allowed by retained evidence; immutable input and raw original receipts remain intact.
- [ ] Write adjacent simulation result with gate/base/accepted-manifest/control/parser hashes, timestamps, exact ID/argv, raw receipt hashes, selected20/actions/status/baseline/diff/mount/export/volume/cleanup result; no installation-success flag. Any failure leaves a red/quarantined simulation result, no retry. Submit exact result to independent review. Even PASS ends with removed simulation container; no installer creation/start/commit/PG/harness until NEW synchronized installation gate, independent review/root verification/fresh dispatch. Task1C and Task2 remain separate authority. No production readiness follows.

## Planning verification and concrete todo

Read-only local verification rehashed33APKs, report/manifest/result and pinned metadata. Pure parser fixtures: 95 passed, including synthetic20 proposals/reversed solver order, all forbidden C0/DEL/C1 controls, diagnostics/nonempty stderr/signature drift/truncation/overflow, malformed markers/counters, missing/extra/duplicate/wrong packages, baseline actions and trigger output. The valid fixture includes signed baseline descriptions with error. Fixture output is deliberately synthetic and NOT actual solver output; solver has NOT run. Original inherited guard fixtures remain mandatory before dispatch; this amendment changes no prior export/mount/volume predicate.

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
