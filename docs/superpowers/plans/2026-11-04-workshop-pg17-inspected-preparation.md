# Workshop PG17 Inspected Preparation Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after independent exact-checkpoint review and a new coordinator preparation dispatch. This checkpoint is plan-only: no Docker create/start/commit, download, package install, PostgreSQL or harness execution occurs here.

**Goal:** Replace the blocked opaque-builder PG17 preparation step with inspected exact-ID acquisition and offline-install containers plus a stopped-container commit; preserve the separate exact-image harness authorization and every production/readiness denial.

**Architecture:** Replace only Task1's fixed Dockerfile/build mechanism with fully identified, inspectable acquisition, simulation and installation containers created from the exact cached local image ID. Acquire a signed APK closure in the first container, install it offline in the second container's isolated root layer, stop it, inspect its changes and commit that exact stopped container with explicit final configuration. Independent image review and original Task2's separate execution authority remain required.

**Tech Stack:** Existing Docker Engine28.5.2+dfsg4 API1.51/overlay2, cached official PostgreSQL17.11 Alpine3.24.3 amd64, signed Alpine APK packages, Python3, GCC/musl; no BuildKit, Dockerfile/build, new builder or image pull.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-schema-pg17-route.md`; `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Planning base: `79ce883458c1ac41e385cabc8d1f582b0b28cab1` on adopted `codex/workshop-pg17-runner-prep`.
Unchanged harness: `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`; archive SHA256 `4666eec4f3575fcc4f12ec6956af41fe055c740f53430e0057d7163b85096b80`.
Historical corrected route gate: `7988c7de30e6de930d36a3b8d907cdb4e90264ba`; adopted gate `bad940db48d649fd8d5b08d119c66defde19884c` and retained builder blocker remain evidence, not authority for this amendment.

## Global constraints and exact precedence

This amendment supersedes only the earlier route Task1's Dockerfile/local-ID FROM/build-sandbox requirement. That requirement could not be proven from the selected builder metadata, so its owner stopped before any create/start/download/build. Do not describe the blocker as a failed harness run or silently retry a build. This amendment authorizes no tracked implementation changes, integration, package upgrades, production role/grant/runtime/config changes, app/provider/cloud/DNS operation or Task2 execution. Keep all five harness files byte-identical to54ab; the base79ce883 diff confirms that. Only planning/tracking/evidence index documents may change here.

Original bounded PGDATA tmpfs, no unexpected Docker volumes, no production mounts/secrets, exact-owned cleanup, non-root final runner, matching PG17 binary/header/ICU/C sentinel proofs and original Task2's separate exact-image approval remain mandatory. Preparation may only invoke postgres/initdb/pg_ctl/psql/pg_config for their fixed version/configuration inspection; no initdb or server startup. No application services, Compose, Docker exec, image builds, image pushes/pulls, privileged container, host namespaces/network, host package install, Docker socket, broad filesystem bind or bulk cleanup. `status: synchronized` is tracking consistency; it grants neither preparation nor runtime dispatch by itself.

## Read-only feasibility and remaining proof boundary

Read-only Docker help confirms `create --pull=never`, explicit entrypoint/user/network/tmpfs/mount/capability flags and `commit --change` exist. Image metadata is linux/amd64, PG_VERSION17.11, rootfs10 layers, inherited `VOLUME /var/lib/postgresql/data`, postgres entrypoint/default CMD. Read-only saved-layer inspection confirms Alpine3.24.3, no UID/GID1000 collision, built-in Alpine signing keys, and exactly these inherited repositories:

```text
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community
```

Cached local base `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085`; RepoDigest `postgres@sha256:266d3c257594e195b309ae9d1805e54c788f1d7b375f56bf6c367aac6c917e7b`. Exact-ID create with `--pull=never` avoids FROM resolution. Explicit created containers expose mount/network/configuration before payload execution; stopped-container commit avoids opaque build-step sandboxes. This supports a reviewable candidate route; no claim that commands, package compatibility, signatures, capability sufficiency or image/toolchain checks have passed. Missing proof blocks the next step. No container was created to establish feasibility.

The only network-enabled container below runs trusted fixed APK acquisition commands against the two exact official HTTPS repository paths; it does not run fetched package scripts. `bridge` is command-bounded network authority, not a claimed hostname firewall. No proxy/env-file/custom DNS/mirror/redirect workaround is allowed; unexpected repository or TLS/signature behavior blocks. All package installation/scripts and every final image inspection run network-disabled. If enforced hostname-only egress beyond these trusted fixed commands is required, stop for a separate network design rather than imply that Docker bridge provides it.

## Ownership, private artifacts and reusable lifecycle

After approval only, the coordinator names a fresh private evidence/preparation directory outside all checkouts, owned1000:1000 mode0700. In the examples `PREP` is that already validated absolute directory, `RUN_ID` is a newly allocated `[a-z0-9-]{1,32}` suffix, `GATE_SHA` is the full adopted passing amendment checkpoint. Derive exact container names `autodata-pg17-acquire-$RUN_ID`, `autodata-pg17-simulate-$RUN_ID`, `autodata-pg17-install-$RUN_ID`, `autodata-pg17-inspect-$RUN_ID`; require each name/cidfile is absent before creation. Never reuse a failed name/container/directory. Resolve every source with realpath; no symlink, colon/comma/newline-containing path or preexisting artifact directory. `BASE` is the literal full cached local image ID above, not a mutable tag.

Create only `PREP/apks` (empty private output), `PREP/control` (root-readable fixed scripts, read-only at launch), `PREP/evidence` (host-only logs/manifests). File logs may be0644 inside mode0700 ancestors; root-owned acquisition APKs remain readable to the host owner but never world-accessible through the parent. No production/env/source/customer data is copied into any image; repository source is not mounted during acquisition/install. Hash all control scripts before creation and again before start/commit. Record exact argv, Docker version, original base config/layers/digests and read-only installed-base inventory. No arbitrary shell input or inherited host environment appears in a container command.

Every container is created without `--rm`, then inspected before start. Its `.Image` must equal the expected full ID; `.State.Status` is `created`, `.RestartCount=0`; exact entrypoint/argv/user/caps/security/resource limits and network match its phase. `.Mounts` plus `.HostConfig.Tmpfs` must show no volume mount, duplicate/overlapping target, implicit anonymous volume or unexpected bind. Inherited PGDATA is always overridden by:

```text
--tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700
```

Private `/tmp` tmpfs is phase-specific. Docker-managed `/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf`, `/dev`, `/dev/shm` and proc/sys runtime mounts are recorded separately, not application binds; they confer no source/secret/socket access. Reject any configured Docker volume, Docker API socket, volume-from, published port, extra network or host namespace. Retain complete inspect JSON, volume inventory before create and after removal and exact create/start/wait/cleanup timestamps. Start only the inspected full container ID, never its name, using `docker start --attach ID` under a host supervisor. Exit must be independently checked through stopped inspect; attachment success alone is insufficient.

Host supervisor deadlines: acquisition300s, offline install180s, commit120s, each inspection60s; per operation Docker stop10s then kill if needed, reap/inspect/remove30s. Timeout/failure remains failure. Stop/kill/rm only IDs captured by this task's create; retain stopped inspect and use `docker rm --volumes ID`, then verify absence. No bulk pkill/prune/image prune/volume prune or name-prefix ownership inference. If unexpected anonymous volume appears, do not start; retain its exact name from owned-container inspection, remove the owned container and only that proven-created volume, verify absence, and fail. Base/final image VOLUME metadata alone is not an allocated volume and is retained, never advertised as removed.

## Task1A: Acquire a signed, frozen dependency closure

**Consumes:** independently approved adopted checkpoint, exact cached BASE, empty private directories and reviewed control scripts.
**Produces:** signed-index/package verification receipts, exact resolved APK closure/hashes and cleaned acquisition container; no installed runner or PostgreSQL process.

- [ ] Verify cache ID/RepoDigest/platform/rootfs metadata against the fixed identity, matching five-source hashes against54ab and no implementation diff. Save base signing-key hashes, repositories and `apk info -vv` baseline. Write the following fixed `control/acquire.sh` (no other payload), hash it and make its files0444:

```sh
#!/bin/sh
set -eu
umask 022
cmp /etc/apk/repositories /control/repositories
apk --version
apk --print-arch
apk info -vv
sha256sum /etc/apk/keys/*
apk update
find /var/cache/apk -type f -exec sha256sum {} \;
apk fetch --recursive --output /apks python3 gcc musl-dev binutils
apk verify /apks/*.apk
sha256sum /apks/*.apk
```

`control/repositories` contains exactly the two lines above. Neither shell script invokes PostgreSQL or a fetched package script. Require x86_64, successful signed index validation and successful verification of every downloaded APK against the image's unmodified trusted keys. No `--allow-untrusted`, key addition, TLS bypass, alternate repository, force flag or signature warning is accepted. If this exact APK version lacks `verify` or needs extra authority, stop; do not invent a fallback command. Signed packages are not yet an accepted compatible install closure.

- [ ] Create the acquisition container with exact future command (all shell variables are the validated fixed values defined above):

```sh
docker create --pull=never --name "autodata-pg17-acquire-$RUN_ID" \
  --cidfile "$PREP/evidence/acquire.cid" --label "autodata.pg17.gate=$GATE_SHA" \
  --network=bridge --read-only --user=0:0 --cap-drop=ALL --cap-add=DAC_OVERRIDE \
  --security-opt=no-new-privileges --pids-limit=128 --memory=512m --cpus=2 \
  --restart=no --no-healthcheck --stop-signal=SIGTERM --stop-timeout=10 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/log:rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/cache/apk:rw,noexec,nosuid,nodev,size=128m,uid=0,gid=0,mode=0700 \
  --mount "type=bind,src=$PREP/apks,dst=/apks" \
  --mount "type=bind,src=$PREP/control,dst=/control,readonly" \
  --entrypoint /bin/sh "$BASE" /control/acquire.sh
```

DAC_OVERRIDE is only for root to write the fresh uid1000 private output mount; no CHOWN/FOWNER/NET_ADMIN/SYS_ADMIN/NET_RAW/SETUID/SETGID capability. Exactly two binds are allowed: `/apks` writable, `/control` read-only; four bounded tmpfs targets; no source/evidence/secret/production bind. Inspect complete network/mount/capability/config before any start; cached image plus `--pull=never` must resolve or creation fails without registry access. Run only inspected ID, capture attach stdout/stderr and final zero exit, then stop/remove/verify as above. Host evidence is not mounted.

- [ ] Freeze APK files as read-only input: hashes, filenames/name/version/arch, signing-key hashes, signed repository index digests, exact repositories, baseline installed package versions and rootfs identity. Copy only acquisition receipts out before cleanup if needed via read-only `docker cp ID:/path DEST`; indices live in tmpfs and must be exported while the container is running only if already explicitly provided by fixed payload. Therefore the fixed payload must emit the signed-index hashes before exit; do not assume stopped tmpfs contents survive. Verify package SHA256 on host before/after install. No closure changes after freeze. Exact resolved versions become the immutable input manifest; this plan does not falsely invent versions before acquisition.

## Task1B: Offline install into one inspected container root layer

**Consumes:** frozen verified APK closure/control script hashes, exact cached BASE; no network.
**Produces:** stopped exited-zero installer, package/file delta and matching-toolchain receipts; no server/harness start.

- [ ] First write/hash `control/simulate.sh` containing only `set -eu`, `cmp /etc/apk/repositories /control/repositories`, `apk info -vv`, `apk verify /apks/*.apk` and `apk add --simulate --no-network /apks/*.apk`. Create a distinct simulation container using the complete installer create command below with only these three literal substitutions: name `autodata-pg17-simulate-$RUN_ID`, cidfile `simulate.cid`, final script `/control/simulate.sh`. All network/mount/capability/entrypoint/BASE/resource settings are identical; record complete resulting argv and inspect before start. Run under180s deadline, retain stopped zero exit, inspect and signed-package simulation output. Independent host review must account for every action as installation of a package absent from the baseline map; any upgrading, downgrading, replacement/reinstall, removal, unrecognized action, warning, unknown baseline version or signature error rejects before actual installation. Preserve simulation receipts and clean that exact container before creating the installer. Do not restart it or change its command. Only the already frozen identical APK bytes and identical BASE may be used by the installer; no resolver/index/network change occurs between stages. If compatibility cannot be proven, stop with the candidate APK closure uninstalled.

- [ ] Render `control/install.sh` with this fixed payload and hash it. Capture pre/post installed package maps and reject any changed or removed baseline package version, ownership/configuration or signing key. A separate stopped simulation container is reviewed before creating the actual installer; no package install is attempted when the frozen simulation proposes changing/removing/reinstalling any baseline package. Independent post-install maps additionally verify this invariant. Additional dependencies outside the signed frozen closure reject. Failure requires new plan review, not `apk upgrade` or relaxed comparisons.

```sh
#!/bin/sh
set -eu
umask 022
cmp /etc/apk/repositories /control/repositories
apk info -vv
sha256sum /etc/apk/keys/*
sha256sum /usr/local/bin/postgres /usr/local/bin/initdb /usr/local/bin/pg_ctl \
  /usr/local/bin/psql /usr/local/bin/pg_config \
  /usr/local/include/postgresql/server/pg_config.h /usr/local/include/postgresql/server/postgres.h
apk verify /apks/*.apk
apk add --no-network /apks/*.apk
addgroup -g 1000 probe
adduser -D -u 1000 -G probe probe
mkdir -p /source
chmod 0755 /source
apk info -vv
sha256sum /etc/apk/keys/*
sha256sum /usr/local/bin/postgres /usr/local/bin/initdb /usr/local/bin/pg_ctl \
  /usr/local/bin/psql /usr/local/bin/pg_config \
  /usr/local/include/postgresql/server/pg_config.h /usr/local/include/postgresql/server/postgres.h
```

- [ ] Create (but do not yet start) exact installer:

```sh
docker create --pull=never --name "autodata-pg17-install-$RUN_ID" \
  --cidfile "$PREP/evidence/install.cid" --label "autodata.pg17.gate=$GATE_SHA" \
  --network=none --user=0:0 --cap-drop=ALL \
  --cap-add=CHOWN --cap-add=FOWNER --cap-add=DAC_OVERRIDE \
  --security-opt=no-new-privileges --pids-limit=128 --memory=1g --cpus=2 \
  --restart=no --no-healthcheck --stop-signal=SIGTERM --stop-timeout=10 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=128m,uid=0,gid=0,mode=0700 \
  --tmpfs /var/log:rw,noexec,nosuid,nodev,size=4m,uid=0,gid=0,mode=0700 \
  --mount "type=bind,src=$PREP/apks,dst=/apks,readonly" \
  --mount "type=bind,src=$PREP/control,dst=/control,readonly" \
  --entrypoint /bin/sh "$BASE" /control/install.sh
```

The installer intentionally has one writable isolated container root layer; it has no writable host mount. CHOWN/FOWNER/DAC_OVERRIDE are fixture package-install capabilities only, dropped entirely in the final runner. No SYS_ADMIN/mount/SETUID/SETGID/network capability or privileged mode. A missing capability is a blocker; do not add caps. Exactly two read-only binds/three tmpfs; no default PGDATA volume. Inspect before start; execute only the full inspected ID under180s deadline. Do not commit until stopped state has exit0, `OOMKilled=false`, empty State.Error and unchanged source/input hashes.

- [ ] Retain `docker diff ID`, inspect, `/lib/apk/db/installed`, `/etc/apk/world`, user/group files and package file manifests via `docker cp` from the stopped container's root layer. Reject changes to `/usr/local` PG tools/headers/libraries/configuration, signing keys/repositories or any baseline installed package version; allow only newly added signed-package-manifest paths plus APK database/world and probe passwd/group/shadow/home/source changes. Transient installation locks/cache files must be absent before commit. Mounted `/apks`, `/control`, `/tmp` and PGDATA must contribute no committed bytes. No logs/manifests/APKs/repository source/customer secrets are written into the root layer. Unexpected changes or unverifiable path/owner ancestry blocks commit. No symlink/path-escape acceptance.

## Task1C: Commit the stopped exact installer and freeze image provenance

**Consumes:** exact installer ID, verified stopped exit0 state, reviewed package/file delta, base ID/layers and input hashes.
**Produces:** immutable local image ID, complete configuration/ancestry/toolchain receipts and cleaned temporary containers; no image push or Task2 execution.

- [ ] Record immutable inputs in a host JSON manifest (gate SHA, source54ab/archive hash, base image ID/RepoDigest/layer list, APK names/versions/hashes/key/index identities, control script hashes, install ID/create/inspect/diff hashes). Canonically serialize and hash it as `PROVENANCE_SHA256`. Commit without a mutable repository/tag, exactly once, from the stopped installer only:

```sh
docker commit --pause=true \
  --change 'USER 1000:1000' \
  --change 'WORKDIR /source' \
  --change 'ENTRYPOINT ["/usr/bin/python3"]' \
  --change 'CMD ["--version"]' \
  --change 'ENV PYTHONDONTWRITEBYTECODE=1' \
  --change 'STOPSIGNAL SIGTERM' \
  --change "LABEL autodata.pg17.gate=$GATE_SHA" \
  --change "LABEL autodata.pg17.provenance=$PROVENANCE_SHA256" \
  --change 'LABEL autodata.pg17.harness=54ab7dce19c36ce7ea3403259dd1ecc66bf323aa' \
  "$INSTALL_ID"
```

`INSTALL_ID` is the full captured/inspected exited-zero ID. Accept only returned `sha256:[0-9a-f]{64}` as `RUNNER_ID`. No mutable tag substitution, docker build/import/export reconstruction or restarting installer. Commit excludes mounted content by Docker semantics; independently inspect/save the resulting image to verify this rather than infer it from success. Commit must not mutate BASE; save/inspect BASE again. Retain exact commit argv/exit/stdout and resulting config/rootfs/history JSON. If commit fails/times out, preserve failure and identify only image IDs from this exact operation before any cleanup; no broad image deletion.

- [ ] Require final RootFS layers equal the exact ten BASE layers in order plus exactly one non-empty committed layer, no altered/replaced base layer. Inspect inherited volume declaration exactly `/var/lib/postgresql/data`; no added VOLUME, secret/proxy env, healthcheck or default postgres command. Require final User1000:1000, `/source`, Python entrypoint, `--version` CMD, SIGTERM and matching provenance labels. Inspect saved final added layer against the approved package/file delta: no APK archives, control/input/evidence/source contents, PGDATA/socket/log content or unexpected data. Docker config/history may contain the fixed scripts' argv but never private data; retain bounded metadata receipts. Layer/provenance consistency is required but is not actual harness correctness or publisher authentication.

- [ ] Only after those checks, write/hash `control/inspect.py` below. Mount only `/control` read-only and the verified exact54ab source snapshot read-only at `/harness`; this source is inspection input, never part of commit. Create exact non-root inspection container:

```sh
docker create --pull=never --name "autodata-pg17-inspect-$RUN_ID" \
  --cidfile "$PREP/evidence/inspect.cid" --label "autodata.pg17.gate=$GATE_SHA" \
  --network=none --read-only --user=1000:1000 --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit=128 --memory=512m --cpus=2 \
  --restart=no --no-healthcheck --stop-signal=SIGTERM --stop-timeout=10 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700 \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=128m,uid=1000,gid=1000,mode=0700 \
  --mount "type=bind,src=$PREP/control,dst=/control,readonly" \
  --mount "type=bind,src=$SOURCE_54AB,dst=/harness,readonly" \
  --entrypoint /usr/bin/python3 "$RUNNER_ID" -B /control/inspect.py
```

`SOURCE_54AB` is the previously verified private extraction of the frozen source archive; source file hashes must match the retained original index. Require exactly these two read-only binds/two tmpfs and full created-container inspection before start; run only that inspected ID under60s deadline. The payload is:

```python
import hashlib, json, os, pathlib, pwd, re, shlex, subprocess, sys
assert os.getuid() == 1000 and os.getgid() == 1000
assert pwd.getpwuid(1000).pw_name == 'probe' and sys.version_info.major == 3
fixed_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
def fixed_run(argv, timeout=2):
    value = subprocess.run(argv, env=fixed_env, cwd='/', stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    assert value.returncode == 0 and len(value.stdout) <= 65536 and len(value.stderr) <= 65536
    return value.stdout.decode('ascii')
versions = {}
hashes = {}
for name in ('postgres', 'initdb', 'pg_ctl', 'psql', 'pg_config'):
    path = pathlib.Path('/usr/local/bin') / name
    value = fixed_run([str(path), '--version'])
    match = re.search(r'17\.[0-9]+(?=\s|$)', value)
    assert match is not None
    versions[name] = match.group()
    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
assert len(set(versions.values())) == 1
include = pathlib.Path('/usr/local/include/postgresql/server')
assert fixed_run(['/usr/local/bin/pg_config', '--includedir-server']).strip() == str(include)
configure_args = shlex.split(fixed_run(['/usr/local/bin/pg_config', '--configure']), comments=False, posix=True)
assert configure_args.count('--with-icu') == 1 and '--without-icu' not in configure_args
assert re.search(r'^#define PG_VERSION_NUM 17[0-9]{4}$', (include / 'pg_config.h').read_text(), re.M)
for name in ('pg_config.h', 'postgres.h'):
    hashes[name] = hashlib.sha256((include / name).read_bytes()).hexdigest()
compiler = '/usr/bin/cc'
compiler_version = fixed_run([compiler, '--version']).splitlines()[0]
source = pathlib.Path('/harness/infra/deploy/gce/testdata/schema_probe_sentinel.c')
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'a4dd46d294c25181c3fd0258cf4e17359d718539804aceaa61ea7e01b2a61fd4'
module = pathlib.Path('/tmp/schema_probe_sentinel.so')
fixed_run([compiler, '-shared', '-fPIC', '-I' + str(include), '-o', str(module), str(source)], 30)
assert module.is_file() and module.stat().st_size > 0
hashes['sentinel_source'] = hashlib.sha256(source.read_bytes()).hexdigest()
hashes['sentinel_module'] = hashlib.sha256(module.read_bytes()).hexdigest()
print(json.dumps({'phase': 'preparation_inspection', 'versions': versions, 'hashes': hashes,
                  'compiler_version': compiler_version, 'runtime_verified': False,
                  'harness_executed': False, 'production_ready': False}, sort_keys=True))
```

No module load, database creation/server start or harness import/execution occurs. The compiled module is tmpfs-only, hash retained in stdout, and is destroyed with that inspection container. Source/tool/header hashes must equal the base/source manifests, not merely satisfy version patterns. Do not infer ICU runtime collation correctness from configure output; original Task2 still requires actual ICU fixture execution after separate authorization.
- [ ] Stop/remove/verify inspection and installer containers and every proven-owned temporary volume even on failure; preserve APK/manifest/commit/image receipts. Retain the frozen RUNNER_ID only as a review artifact; no image push/runtime dispatch. Before future acceptance, independent reviewer must inspect exact image, package/file delta, base-chain identities, all create/inspect/cleanup records and unchanged54ab source. Final image's inherited PGDATA VOLUME remains and every later launch must override it under the original tmpfs/mount contract.

## Concrete todo record

- [ ] Synchronize the inspected-create/offline-install/commit amendment, exact source/base pins, mount and cleanup contracts in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent plan review.
- [ ] After separate coordinator approval, create and inspect the exact cached-base acquisition container with bounded private PGDATA tmpfs, signed official APK-only networking and one private output mount; freeze the signed dependency closure and clean only its exact owned resources.
- [ ] Create and inspect a network-disabled offline installer with read-only frozen inputs, private PGDATA tmpfs and an isolated writable root layer; reject package upgrades, untrusted signatures, unexpected mounts or file changes before committing its stopped state.
- [ ] Commit only the reviewed exited-zero installer ID with explicit non-root image configuration and provenance labels; inspect exact base-layer ancestry, configuration, package/toolchain/source hashes and cleanup, then request independent frozen-image review.
- [ ] Keep actual PostgreSQL startup and harness Task2 unexecuted and unauthorized until separate exact-image/source dispatch; preserve all blocker/failure receipts and production runtime/grants/services/deployment/readiness denials.

## Scope, synchronization and adoption

This plan creates its dedicated task/record and updates the original route plan, canonical hosting/operations/architecture/orchestration docs, preparation evidence index and coordinator queue. All implementation paths remain outside scope. Preserve the builder-blocker receipts verbatim; no repair of evidence history. A new independently reviewed exact plan checkpoint, live Issue186/Project8 readback and pinned passing machine preflight precede a coordinator adoption/new Task1 preparation dispatch. No adoption/integration is performed by this planner. Original Task2 is not modified and remains blocked pending separate reviewed exact image/source authorization.

Run the existing preflight against the full committed checkpoint SHA and this dedicated record; retain an external-to-checkpoint pinned receipt in a later documentation commit. Remote readback hashes describe their exact timestamps; later checkpoint announcements get separate hashes. Do not rewrite records to imply an unexecuted route worked. If a required capability/provenance/signature/mount/cleanup/compatibility check cannot be established, preserve a blocking prerequisite receipt and stop before the dependent action.

Inspected-preparation amendment synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621173398 and Project8 readback at `2026-11-04T02:48:06.281627+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned inspected-preparation amendment checkpoint: `2cf545157ed299b8424bbebe1b01ce9c85ab3a3c`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621179539. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


Inspected PG17 preparation ICU review correction (plan-only): the fixed Python inspection script now parses pg_config --configure with `shlex.split(..., comments=False, posix=True)`, requires exactly one `--with-icu` argument and rejects `--without-icu`. A pure local fixture executes only that exact extracted AST fragment: quoted/unquoted ICU and quoted spaces pass; missing/disabled/contradictory/duplicate/substring/empty/malformed quoting reject (10 passed,0 failed). The prior whitespace split fails the quoted positive fixture. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-fixture.json` records inputs/results/fragment hash. No container, toolchain, download or harness execution is implied; independent corrected-checkpoint review/new preparation dispatch remain pending and original Task2 stays separately unauthorized.

Narrow ICU correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621225616 and Project8 readback at `2026-11-04T02:51:55.028338+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned ICU-corrected inspected-preparation checkpoint: `6d65a512172f28a9f7f0960ecf41409db78455c2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621229238. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 APK default-log correction: plan-only

Goal: Permit only an independently reviewed PG17 preparation retry with an explicit bounded private APK log tmpfs and pre-start guard, preserving the actual exit99 blocker, exact-owned cleanup, offline provenance and separate harness authority.

Correction plan `docs/superpowers/plans/2026-11-04-workshop-pg17-apk-log.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-apk-log.json`; record `docs/agents/records/2026-11-04-workshop-pg17-apk-log.json`. Preserved red: approved Task1A under6d65a5 exited99 at apk update with read-only log error,0 APKs; exact-owned container removed and volume inventory unchanged (base65772079). Read-only cached libapk3.0.8 identifies default `/var/log/apk.log`. Later approved APK acquisition/simulation/install creates add only private `/var/log` tmpfs4MiB (`rw,noexec,nosuid,nodev,uid=0,gid=0,mode=0700`) and exact pre-start guard; acquisition root stays read-only, no capability/command/repository/host-volume expansion, logs cannot enter committed added layer. Original full mount/cleanup/provenance/Task2 boundaries remain. Guard fixtures are synthetic/pure and not retry evidence. Independent review/new coordinator Task1A dispatch pending; this planner creates/starts/downloads/retries nothing.

Concrete todo:

- [ ] Synchronize the exact APK log-path diagnosis, retained red proof, bounded tmpfs guard and unchanged preparation/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent corrected-checkpoint review and a new coordinator Task1A dispatch only, create a fresh exact-base acquisition container with the additional private4MiB /var/log tmpfs and validate the complete original mount contract plus exact new log guard before start.
- [ ] Execute only the unchanged approved signed-APK acquisition payload after its inspected log guard passes; preserve the previous exit99 and every new failure, bounded attach/log metadata and exact-owned stop/removal/volume-absence evidence.
- [ ] Require the same private log tmpfs and guard for later approved offline simulation/install containers, with no log bytes entering the committed added layer; preserve no-upgrade/signature/package/file/layer/configuration and frozen-image review requirements.
- [ ] Keep image/toolchain/sentinel/harness outcomes unverified until actually observed under their separate approved steps; preserve original Task2 authority and every production/runtime/grant/service/deployment/readiness denial.

APK-log correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621303386 and Project8 readback at `2026-11-04T02:57:35.939965+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


APK-log correction adoption: independently approved checkpoint `bd59558a78a11448f89e35ef34f910bbb64cedbe` (receipt `9db69a7758228fb8997b7c1ca5f5d90c1cc7c32f`) adopted at `cc0945fb841459c68b7a6e4ced8dcb802640b979`, directly after retained failed evidence `6577207980f24e61c51ab0fcc8198ded18c0d1a4`. Five harness54ab files and raw blocker receipt remain unchanged. Live Issue186/Project8 synchronization https://github.com/lucronn/autodata/issues/186#issuecomment-6621339347 read back 2026-11-04T03:00:29.931234+00:00; exact hashes in dedicated APK-log record and predecessor Project index preserved verbatim in comment. Adoption only: no Docker/create/start/download/retry; full adopted-SHA preflight and root verification/new Task1A dispatch still required. Original Task2 and all runtime/production/readiness outcomes remain unauthorized/unverified.


## PG17 acquisition-only writable overlay successor: plan-only

Goal: Replace only the blocked read-only PG17 APK acquisition root with a disposable inspected writable overlay, require stopped overlay/baseline audits before accepting APK output, and preserve offline installation, separate harness authority and every production/readiness denial.

Successor plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-overlay.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-overlay.json`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-overlay.json`. Base226cb50f preserves both actual Task1A exit99/0APK/cleanup attempts. Only acquisition drops `--read-only` and requires explicit isolated writable root overlay; exact image, unchanged signed APK payload/official bridge scope/caps/resources/two binds/four private tmpfs remain. Require stopped complete docker diff with lock/baseline-only allowlist and unchanged package/keys/repos/PG hashes before any APK output acceptance; acquisition overlay/container is never committed, restarted, reused or passed to offline stages. Exact-owned cleanup/absence/volume inventory mandatory. Offline simulation/install/final-image/Task2 authority unchanged; independent exact-gate review/new Task1A dispatch required. No planning container/download/retry/image/harness action.

Concrete todo:

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
