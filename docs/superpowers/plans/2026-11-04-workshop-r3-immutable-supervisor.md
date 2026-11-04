# R3 immutable supervisor adaptation Implementation Plan

> **For agentic workers:** Implement only after a later synchronized committed checkpoint and explicit implementation dispatch. Use executing-plans task by task; this draft authorizes documentation only.

**Goal:** Adapt the historical external R3 supervisor to immutable local-image reuse and offline provenance for exact candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`, without changing candidate source or executing Docker.

**Architecture:** Preserve the historical validator and fixture semantics in a new external supervisor. Separate pure admission/command construction, network-none compatibility-probe payload, and focused offline tests. A later execution gate admits fresh manifests and probe evidence before services; historical success cannot supply fresh candidate acceptance.

**Tech Stack:** Python standard library/unittest; Docker/Compose argv generation only during this implementation scope.

**Spec:** `docs/verification/2026-11-03-canonical-article-lifecycle.md`, “R3 immutable supervisor implementation draft”; parent runtime plan `docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md`; canonical gate `docs/agents/pre-implementation-gate.md`.

## Status, binding and authority

BLOCKED / pending independent review and synchronization. Planning base: `d94543e6ec75e788b42421b0e4cfeca6f5cb3e9c`; branch `codex/workshop-r3-immutable-supervisor-gate`. Source candidate/tree remain `4d82e413e04fb2401ac7bc28dc828375ac662180` / `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`. The future committed planning checkpoint is a separate SHA and is not yet available. Any candidate change stops this task and requires a revised binding.

Issue reference: https://github.com/lucronn/autodata/issues/186
Project reference: https://github.com/users/lucronn/projects/8
These are intended existing tracking references, not a claim of live synchronization for this adaptation. Record: `docs/agents/records/2026-11-04-workshop-r3-immutable-supervisor.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-r3-immutable-supervisor.json`. No GitHub write, commit, push, implementation or Docker mutation is authorized in this draft.

The later implementation gate may authorize external code editing and offline mocked tests only. Creating/starting even a network-none, read-only compatibility container is Docker mutation and belongs to a separate explicit execution gate. No build, pull, retag, import/export, package install, download, service startup, cloud, provider/payment, merge, deployment or production authority follows from implementation completion. Keep final180 open and release unverified.

## Inspected evidence and fixed identities

Historical supervisor `/home/corp/autodata-evidence/index-readiness-green-68fd8e922a26/supervisor.py`, SHA-256 `e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9`, unconditionally creates/bootstraps BuildKit and builds. Preserve it and all leaf evidence byte-for-byte; copy only into the new allowlisted file after implementation authorization.

Read-only audit `/home/corp/autodata-evidence/r3-readonly-provenance-4d82e413-20261104/report.md`, SHA-256 `b48449fb92e7541ee2f727dd0edba7a53f67bd36ef7d0a2b88f7c3a3046c96af`, plus adjacent `audit-result.json`, `source-comparison.json` and image snapshots, records local linux/amd64 image availability and unchanged before/after config/RootFS identities. Historical versions support compatibility; executable/package/cache manifests and fresh offline probes remain absent. Host overlay reads were denied. This draft does not reinterpret these observations as probe success.

| Role | Exact local image configuration ID |
| --- | --- |
| runner/probe/cleanup | `sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c` |
| PostgreSQL17 | `sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e` |
| NATS | `sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045` |
| SeaweedFS | `sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5` |

Retain RepoDigests separately, particularly Seaweed `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`; registry manifest and local configuration ID are different identities. Runner entrypoint is null/default command `python3`; all probe/cleanup invocations explicitly select `/usr/local/bin/python`.

The audit compared candidate/leaf Go modules, worker pyprojects, Dockerfile, Compose, bridge, lifecycle support and migration runner. No Go/worker/contracts/migration/Compose input changed. Two Workshop JavaScript files are embedded in Go, so candidate compilation remains necessary. The two release acceptance Python changes do not authorize altering the R3 fixture. Retain fresh complete candidate tracked-file manifest, not only the dependency comparison.

## Exact file allowlist

Current draft may change exactly five documentation paths: docs/superpowers/plans/2026-11-04-workshop-r3-immutable-supervisor.md, docs/agents/records/2026-11-04-workshop-r3-immutable-supervisor.json, docs/agents/tasks/2026-11-03-production-release/workshop-r3-immutable-supervisor.json, docs/agents/tasks/2026-11-03-production-release/queue.json and docs/verification/2026-11-03-canonical-article-lifecycle.md. Append only this separate blocked adaptation task to the queue; preserve every predecessor entry and all other queue fields. The parent runtime plan is contextual and consumes the completed adaptation; this adaptation has no dependency on parent runtime execution.

Future implementation may create exactly:

- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/supervisor.py`: adapted bounded runner, admission and command construction, inherited validator, owned cleanup.
- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/offline_probe.py`: deterministic image-filesystem manifests and offline compatibility checks; no acquisition code.
- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test_supervisor.py`: standard-library unittest with fake command executor, temporary fixtures and historical artifact copies in memory.

External output receipts from offline tests may live only under `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test-artifacts/`; they are evidence, not executable source. No repository implementation file is allowlisted. No changes to candidate tests, Go/JS/worker source, Compose, Dockerfile, migrations, autonomy tooling or historical artifacts. The implementation gate must explicitly authorize absolute external paths as well as its repository checkpoint; repository machine preflight alone is not external filesystem authorization. If tooling cannot represent that boundary, stop for coordinator resolution rather than modifying gate tooling.

## Concrete todo
- [ ] Independently review this blocked implementation draft; coordinator synchronizes Issue186/Project8, canonical document and concrete todo, commits the checkpoint, pins its full SHA and passes canonical machine preflight before implementation dispatch.
- [ ] Create only the named external supervisor, offline probe and focused standard-library tests; preserve historical supervisor byte-for-byte and demonstrate failing-first admission, manifest, command and cleanup tests without Docker.
- [ ] Implement immutable image/config admission, deterministic executable/package/cache manifests and network-none compatibility probe command generation; retain original eight-root/42-tuple validator and bounded cleanup.
- [ ] Run focused offline tests and source/allowlist checks; independently review exact adaptation source hashes and provide a non-executable handoff for a separate probe/runtime gate.
- [ ] Keep probe execution, service startup, acquisition/build/pull and all release authorities false; record unresolved current provenance facts for the execution owner.

## Manifest and admission contract

`admission.json` (a future execution-owner reviewed input, not manufactured as trusted by the implementer) binds schema version1, candidate SHA/tree, committed implementation gate SHA, supervisor/probe source SHA-256, historical supervisor hash, audit report hash, all four image IDs/platforms/config/RootFS fingerprints, resolved Compose canonical hash/delta, executable/package/cache expected manifest digests, accepted probe receipt hash and literal command policy. Missing/null/duplicate/extra roles, stale candidate/source hash or changed config fails closed before fixture resources exist. Admission records carry provenance/origin and distinguish historical observations from current measurements; a newly computed manifest cannot self-authorize its own acceptance.

Every manifest uses sorted unique POSIX paths and canonical JSON UTF-8 serialization (`sort_keys=True`, separators comma/colon, terminal newline), SHA-256 of raw bytes, schema version, candidate/source/image IDs and phase. Record symlink path/target, verified resolved path, file kind/mode/size/hash; reject escaping symlinks, unreadable paths, duplicate paths, incomplete enumeration or missing expected roots. Do not include mtime in equality. Preserve individual entries and aggregate digest, no secret env dump.

- Image manifest: full inspect receipt plus stable `Id`, `Os`, `Architecture`, `Variant`, `RootFS.Type/Layers` and `Config` digest for all roles, Docker daemon/context/platform identity and separate RepoDigests. Compare stable fields before/after, not inspect timestamps. Require linux/amd64 daemon compatibility; a missing image fails without acquisition.
- Tool manifest: resolve/hash `/usr/local/bin/python`, Go, psql, pg_dump and git through symlinks, capture explicit argv/version/stdout/exit/timeout and executable target bytes. Expect Python3.14.10, Go1.26.10, psql/pg_dump17.11, git2.47.3 as historical comparison; divergent current evidence blocks owner admission, never silent fallback.
- Python manifest: enumerate every installed distribution name/version, dist-info metadata and actual distribution files with hashes, including editable/direct-url provenance. Record missing RECORD hashes rather than skipping file hashing; reject unreadable/missing files. Use metadata discovery plus filesystem hashing, validate unchanged worker dependency constraints, and import bridge/support/required worker modules with bytecode disabled. Record module origin paths so a host/source shadow cannot satisfy an image dependency check.
- Go cache manifest: enumerate every entry (including zip/mod/info/sumdb and extracted module files) below `/opt/go-module-cache`, canonical path/kind/mode/hash and symlinks. Keep it read-only; only GOCACHE/GOTMPDIR use new owned tmpfs. Before/after file manifest equality is required across probe and eventual acceptance; missing module reports incompatibility without download.
- Config/input manifest: hash all tracked candidate file modes/bytes, clean detached HEAD/tree, no remotes, plain clone and no extra files; record baseline and effective Compose plus exact structural delta. Permit only four runtime image IDs, `pull_policy: never`, removal of `go-test-runner.build`, omission of unused `test-runner`, and fresh minio `/data` bind (`create_host_path=false`). Retain source config hash; deny other environment/command/mount/network/port changes. New provenance probe mounts are separate from fixture config.

## Task 1: Failing-first admission and immutable command tests

**Files:** future external `test_supervisor.py`, then `supervisor.py`. Interface: pure `admit(admission, observation)` raises on mismatch; `commands_for(admitted_context)` returns argv lists without execution; injected executor is the only subprocess boundary. Importing either code file performs no command, path allocation or Docker operation.

- [ ] Write unittest cases for missing/wrong image, platform mismatch, changed Config/RootFS, registry/config-ID confusion, mutable tag, stale candidate/supervisor/probe hash, absent/untrusted manifest, extra service and config delta. Tests call pure functions and prove no executor call on rejection.
- [ ] Run `python3 -B -m unittest discover -s /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation -p test_supervisor.py -v`; retain the failing output before implementation. The expected failure is missing adaptation API, not a Docker failure.
- [ ] Copy historical supervisor to the exact new file; refactor only enough for a main guard, injected executor and admission boundary. Remove builder/image-name allocation and every buildx/build/pull/retag/acquisition path, including finally cleanup. Hard-code candidate binding and exact four-ID contract; no mutable image fallback.
- [ ] Require generated service startup `up -d --no-build --pull never --wait --wait-timeout 150 postgres nats minio` under the frozen Compose prefix. Runner uses `run -d --pull never --no-deps --name <owned-runner> go-test-runner /usr/local/bin/python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/index-readiness-r3.xml workers/ingestion-python/tests/test_catalog_api_integration.py`. Effective go-test-runner has no build field; unused test-runner cannot be selected. All image create/run argv use exact IDs and explicit `--pull never`, including compatibility and cleanup `docker create`. Check installed CLI support before mutation and block if unsupported; prior inspect alone does not close a missing-image race. No implicit pull is permitted.
- [ ] Add fake-executor assertions for exact startup/runner argv, absence of build/acquisition commands in success/failure/cleanup, and refusal to execute without a separate runtime dispatch input. Run focused tests green and inspect diff before the milestone handoff.

## Task 2: Failing-first manifests and read-only compatibility probe

**Files:** future `offline_probe.py`, focused tests, supervisor invocation generation. Interface: probe emits raw canonical manifest/probe JSON to stdout; host executor retains byte/hash/argv/exit receipts. An independent execution owner admits its digest later.

- [ ] First test deterministic ordering, full symlink resolution, changed bytes, omitted file, extra distribution, missing module-cache entry, unreadable path, import error, nonzero/version mismatch, timeout and malformed/truncated output. Prove each fails admission and that no network/install command is generated.
- [ ] Implement the manifest contract and network-none probe command plan only. Under a later probe execution gate create an owned container with immutable runner ID, `--network none --read-only --cap-drop ALL --security-opt no-new-privileges`, clean candidate `/workspace:ro`, probe script mounted read-only, fresh executable `/tmp` tmpfs, explicit `/usr/local/bin/python -B`, no Docker socket, host network, service mounts, provider env or secrets. Capture stdout through Docker logs rather than allowing arbitrary writable host mounts.
- [ ] Fix offline Go env to `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOFLAGS=-mod=readonly CGO_ENABLED=0 GOMODCACHE=/opt/go-module-cache GOCACHE=/tmp/go-cache GOTMPDIR=/tmp/go-tmp`. Probe imports required Python modules without initializing fixtures/services, validates worker dependency constraints and runs `go test -c -o /tmp/r3-compat.test .` in `/workspace/apps/api-go` to compile exact candidate tests/embeds without executing test roots. Network none enforces offline operation. Record exact command and 180-second compile bound; failure never starts services. Import-time unexpected service access fails this probe rather than widening access.
- [ ] Snapshot tool/distribution/module-cache manifests before and after this probe. Require equality; only tmpfs outputs may change. Probe is compatibility evidence only, not eight-root acceptance. The fixed cleanup-interpreter probe also verifies `/usr/local/bin/python` and `shutil.rmtree`, with network none/read-only root and no mounts.
- [ ] Run the same offline unittest command green. Preserve red/green logs and source hashes. No real probe or Docker command is executed by this implementation milestone.

## Task 3: Preserve validator, deadlines and cleanup; review handoff

**Files:** external supervisor/tests only. Keep original `validate()` checks except mechanically moving pure validation for offline testability; any changed acceptance rule requires a revised gate.

- [ ] Add failing-first negative tests by mutating copied historical receipt structures: missing/extra/skipped Go/JUnit root, changed candidate, missing artifact hash, duplicate database, one false readiness tuple, bad counters/projection/migration/source identity. Require rejection before calling any cleanup command in these pure tests.
- [ ] Preserve exactly four roots for both bankone/banktwo, eight unique DBs, zero skips/fail/errors, 42 full expected/observed readiness tuples, 20 cold ensures/one job/no external cold work, held model/source readability, atomic publication and 100 warm cycles/unchanged rows. Keep migrations001–040 and input/git equality, original per-case artifacts and failure receipts. Never copy historical PASS into a current receipt.
- [ ] Preserve 1320s monotonic runner deadline from launch, Go90s/bridge120s, startup150s/command180s, ordinary30s, inspect/log10s and cleanup30s bounds. Record timeout separately and always retain failed attempt evidence. Probe compile180s is separately bounded and cannot extend runner acceptance.
- [ ] Test cleanup with fake inspect records: full immutable container IDs, UUID owner token, exact name/image/project/service labels and allowed mounts must all match immediately before stop/kill/remove. Unknown/colliding resources fail closed. Cleanup container explicitly uses `/usr/local/bin/python`, immutable runner ID, network none/read-only root, and sole writable mount `/owned-data` from the fresh owned Seaweed path.
- [ ] Before fixture data deletion require owner marker exact token/path, resolved non-symlink path directly below run root, project containers absent and no container mounting the data path; never follow symlinks. Preserve at least12GiB capacity check before fixture startup. Remove only recorded owned container IDs/volumes/network; do not use global prune or remove-orphans. Verify each volume/network name/project label and actual attachments before removal. Preserve all cleanup receipts; failure keeps overall result failed and reports remaining resource identities, no blind broad fallback.
- [ ] Run focused tests, `python3 -X pycache_prefix=/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test-artifacts/pycache -m py_compile /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/supervisor.py /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/offline_probe.py /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test_supervisor.py`, source SHA-256 and allowlist diff checks; independently review exact adaptation/probe/tests. Later coordinator may commit/push validated repository documentation milestones under its authorized cadence; external source is bound by retained bytes/hashes, not assumed present in Git. No commit or push in this draft task.
- [ ] Handoff reviewed immutable source paths/hashes, offline red/green results, exact planned expanded-argv schema and remaining blockers. Before any real probe, require a separately synchronized committed execution gate with explicit Docker mutation ownership/bounds. Before fixture services, require admitted current probe manifests plus the parent runtime gate's exact reviewed supervisor command/hash and independent review/preflight.

## Unresolved owner/execution facts

1. Current executable/file-level package/cache manifest and fresh import/compile probe evidence do not exist. Generating them requires separately authorized container execution because direct layer reads are denied. No code review or offline mock test closes this fact.
2. The execution owner must review/accept expected manifest digests and exact probe receipt, then populate admission; implementation cannot trust self-generated observations automatically. Missing dependency/image requires a separate acquisition gate, never a build/pull fallback.
3. Fresh Issue186/Project8 readback, serialized tracking update, checkpoint commit/full SHA, machine preflight and independent implementation dispatch are absent. Future external-code authorization must be explicit. Runtime/probe dispatch remains a distinct later gate, even after adaptation tests pass.
4. The effective Compose model must prove removal of inherited build fields and unused service with the host's installed Compose version. Offline unit tests can check the intended model; actual `compose config` compatibility must be recorded read-only under the later gate before create/start. Unsupported merge behavior returns blocked, never edits candidate Compose.
