# R3 immutable supervisor adaptation Implementation Plan

> **For agentic workers:** Implement only after a later synchronized committed checkpoint and explicit implementation dispatch. Use executing-plans task by task; this synchronized checkpoint authorizes code-only editing only after exact-base preflight, independent committed-gate review and explicit external-path dispatch.

**Goal:** Prepare reviewed offline external supervisor, probe payload and fake unit tests for exact candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; no Docker or probe/runtime execution.

**Architecture:** Preserve the historical validator and fixture semantics in a new external supervisor. Separate pure admission/command construction, network-none compatibility-probe payload, and focused offline tests. A later execution gate admits fresh manifests and probe evidence before services; historical success cannot supply fresh candidate acceptance.

**Tech Stack:** Python standard library/unittest; Docker/Compose argv generation only during this implementation scope.

**Spec:** `docs/verification/2026-11-03-canonical-article-lifecycle.md`, “R3 immutable supervisor implementation draft”; parent runtime plan `docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md`; canonical gate `docs/agents/pre-implementation-gate.md`.

## Status, binding and authority

Tracking synchronized; independent docs-only correction review PASS. Code-only implementation remains pending exact committed-gate review and dispatch. Correction base: `aafaaf93089b009baae3d68011cd74365b8de18e`; predecessor planning base: `d94543e6ec75e788b42421b0e4cfeca6f5cb3e9c`; branch `codex/workshop-r3-immutable-supervisor-gate`. Source candidate/tree remain `4d82e413e04fb2401ac7bc28dc828375ac662180` / `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`. The committed planning checkpoint full SHA is an external invocation input; do not self-reference it in this document. Any candidate change stops this task and requires a revised binding.

Issue reference: https://github.com/lucronn/autodata/issues/186
Project reference: https://github.com/users/lucronn/projects/8
Live coordinator tracking was synchronized and read back at https://github.com/lucronn/autodata/issues/186#issuecomment-6636602964; the predecessor Project Source is archived verbatim there. Record: `docs/agents/records/2026-11-04-workshop-r3-immutable-supervisor.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-r3-immutable-supervisor.json`. The coordinator completed the tracking write; implementation and Docker mutation still require their separately stated gates. This checkpoint does not authorize a Docker command.

This synchronized gate permits only the named external code and offline mocked tests after exact-base preflight, independent committed-gate review and explicit dispatch. Creating/starting even a network-none, read-only compatibility container is Docker mutation and belongs to a separate explicit execution gate. No build, pull, retag, import/export, package install, download, service startup, cloud, provider/payment, merge, deployment or production authority follows from implementation completion. Keep final180 open and release unverified.

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

This gate checkpoint changes exactly five documentation paths: docs/superpowers/plans/2026-11-04-workshop-r3-immutable-supervisor.md, docs/agents/records/2026-11-04-workshop-r3-immutable-supervisor.json, docs/agents/tasks/2026-11-03-production-release/workshop-r3-immutable-supervisor.json, docs/agents/tasks/2026-11-03-production-release/queue.json and docs/verification/2026-11-03-canonical-article-lifecycle.md. The queue indexes this separate adaptation task; preserve every predecessor entry and all other queue fields; preserve every predecessor entry and all other queue fields. The parent runtime plan is contextual and consumes the completed adaptation; this adaptation has no dependency on parent runtime execution.

After explicit code-only dispatch, implementation may create exactly:

- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/supervisor.py`: adapted bounded runner, admission and command construction, inherited validator, owned cleanup.
- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/offline_probe.py`: deterministic image-filesystem manifests and offline compatibility checks; no acquisition code.
- `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test_supervisor.py`: standard-library unittest with fake command executor, temporary fixtures and historical artifact copies in memory.

All offline temporary fixtures, copied historical receipt fixtures, red/green logs, syntax-check bytecode and output receipts must live only under `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test-artifacts/`; they are test evidence/fixtures, not an additional executable source allowlist. TemporaryDirectory and similar helpers must receive an owned directory below test-artifacts; do not use default host temporary directories. Imports allocate no files. No package install or host-side real tool/import/Go probe is allowed; verification may run Python standard-library tests/syntax checks and read-only source/hash/allowlist checks. No repository implementation file is allowlisted. No changes to candidate tests, Go/JS/worker source, Compose, Dockerfile, migrations, autonomy tooling or historical artifacts. The implementation gate must explicitly authorize absolute external paths as well as its repository checkpoint; repository machine preflight alone is not external filesystem authorization. If tooling cannot represent that boundary, stop for coordinator resolution rather than modifying gate tooling.

## Concrete todo
- [ ] Independently review this docs-only correction; coordinator synchronizes Issue186/Project8, canonical document and this concrete todo, commits the checkpoint, pins its full SHA and passes canonical preflight before explicit external-code implementation dispatch.
- [ ] Create only the three named external Python sources and test-artifacts; preserve historical evidence byte-for-byte and use synthetic observations, temporary fixtures and fake executor calls only, with no Docker invocation.
- [ ] Implement distinct synthetic, initial-probe and fixture admission interfaces, deterministic manifests and immutable command generation; retain eight-root/42-tuple semantics and add only the explicitly frozen 24-name artifact completeness check.
- [ ] Run failing-first then green standard-library tests for admission, manifests, validator and bounded owned cleanup; retain offline receipts/source hashes and obtain independent exact-source review.
- [ ] Handoff reviewed source and offline-test evidence only; keep current image/tool/package/cache/Compose/probe facts as execution blockers under separate later gates, all runtime/release authorities false and release unverified.

## Manifest and admission contract

`fixture-admission.json` (a future execution-owner reviewed input, not manufactured as trusted by the implementer) binds schema version1, candidate SHA/tree, committed implementation gate SHA, supervisor/probe source SHA-256, historical supervisor hash, audit report hash, all four image IDs/platforms/config/RootFS fingerprints, resolved Compose canonical hash/delta, executable/package/cache expected manifest digests, accepted probe receipt hash and literal command policy. Missing/null/duplicate/extra roles, stale candidate/source hash or changed config fails closed before fixture resources exist. Admission records carry provenance/origin and distinguish historical observations from current measurements; a newly computed manifest cannot self-authorize its own acceptance.

### Frozen admission stages and offline completion

The code-only milestone produces source, synthetic/fake-test receipts and exact source hashes. It does not produce accepted current manifests, compatibility success or R3 acceptance. No current executable/distribution/cache measurement is required to implement these pure interfaces; those facts continue to block execution. No real Docker command, including inspect/config/help, runs during this slice.

- `simulate(stage, admission, observation, fake_executor)` accepts only `stage` equal to `initial_probe` or `fixture` and inputs marked `origin: synthetic_code_only`; it returns `mode: synthetic_code_only`, `trusted: false`, generated argv and fake results. Tests use in-memory inputs or owned test-artifacts fixtures. Simulation runs the same stage-specific binding/content/command-policy checks in an explicitly synthetic validation mode, returning a non-executable test context and fake receipts; the real admission wrappers still reject synthetic origins. Simulation never issues an executable dispatch/context, trusted manifest or current PASS receipt.
- `admit_probe(admission, observation)` is pure and returns an immutable `stage: initial_probe` context or raises. The later independently reviewed `probe-admission.json` binds schema version1, candidate SHA/tree, committed probe execution-gate SHA, supervisor/probe/historical/audit hashes, four immutable image/platform/config/RootFS identities, exact planned probe argv/mount/env/deadline policy and observation origin. Its purpose is initial measurement, so it requires neither accepted package/cache/tool digests nor a probe receipt that has not yet been produced. It rejects synthetic origins, missing bindings, unauthorized operations and identity mismatches. The later execution owner must supply that separate gate and fresh image/CLI observations before any Docker mutation.
- `admit_fixture(admission, observation)` is pure and returns an immutable `stage: fixture` context or raises. It requires all fixture-admission fields above, fresh independently accepted tool/package/cache digests and probe receipt hash, exact effective Compose delta, and the separately committed parent runtime gate. Probe-collected observations cannot self-approve; historical or synthetic observations cannot satisfy fixture admission.
- `commands_for(context)` returns argv arrays and finite command budgets only; it performs no execution/allocation. `execute(context, dispatch, executor)` refuses before allocation or executor call unless a separately supplied execution-owner reviewed dispatch binds the matching stage, committed execution-gate SHA, candidate/tree, exact supervisor/probe hashes and literal allowed operations. No default dispatch or fake/synthetic input may reach the real executor. During code-only tests every executor is fake, including cleanup/failure paths; real execution is outside this implementation authorization.

No circular admission: initial probe collects unaccepted manifests; the execution owner reviews their bytes/digests and receipt under the later gate; fixture admission then consumes that independent acceptance. Initial-probe context cannot start fixture services. The code-only review tests these stages with synthetic data and makes no statement that a later owner has supplied or accepted real input.

Every manifest uses sorted unique POSIX paths and canonical JSON UTF-8 serialization (`sort_keys=True`, separators comma/colon, terminal newline), SHA-256 of raw bytes, schema version, candidate/source/image IDs and phase. Record symlink path/target, verified resolved path, file kind/mode/size/hash; reject escaping symlinks, unreadable paths, duplicate paths, incomplete enumeration or missing expected roots. Do not include mtime in equality. Preserve individual entries and aggregate digest, no secret env dump.

- Image manifest: full inspect receipt plus stable `Id`, `Os`, `Architecture`, `Variant`, `RootFS.Type/Layers` and `Config` digest for all roles, Docker daemon/context/platform identity and separate RepoDigests. Compare stable fields before/after, not inspect timestamps. Require linux/amd64 daemon compatibility; a missing image fails without acquisition.
- Tool manifest: resolve/hash `/usr/local/bin/python`, Go, psql, pg_dump and git through symlinks, capture explicit argv/version/stdout/exit/timeout and executable target bytes. Expect Python3.14.10, Go1.26.10, psql/pg_dump17.11, git2.47.3 as historical comparison; divergent current evidence blocks owner admission, never silent fallback.
- Python manifest: enumerate every installed distribution name/version, dist-info metadata and actual distribution files with hashes, including editable/direct-url provenance. Record missing RECORD hashes rather than skipping file hashing; reject unreadable/missing files. Use metadata discovery plus filesystem hashing, validate unchanged worker dependency constraints, and import bridge/support/required worker modules with bytecode disabled. Record module origin paths so a host/source shadow cannot satisfy an image dependency check.
- Go cache manifest: enumerate every entry (including zip/mod/info/sumdb and extracted module files) below `/opt/go-module-cache`, canonical path/kind/mode/hash and symlinks. Keep it read-only; only GOCACHE/GOTMPDIR use new owned tmpfs. Before/after file manifest equality is required across probe and eventual acceptance; missing module reports incompatibility without download.
- Config/input manifest: hash all tracked candidate file modes/bytes, clean detached HEAD/tree, no remotes, plain clone and no extra files; record baseline and effective Compose plus exact structural delta. Permit only four runtime image IDs, `pull_policy: never`, removal of `go-test-runner.build`, omission of unused `test-runner`, and fresh minio `/data` bind (`create_host_path=false`). Retain source config hash; deny other environment/command/mount/network/port changes. New provenance probe mounts are separate from fixture config.

## Task 1: Failing-first admission and immutable command tests

**Files:** future external `test_supervisor.py`, then `supervisor.py`. Interfaces are the frozen `simulate`, `admit_probe`, `admit_fixture`, `commands_for` and guarded `execute` boundaries above; injected executor is the only subprocess boundary, always fake for this milestone. Importing either code file performs no command, path allocation or Docker operation.

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

**Files:** external supervisor/tests only. Keep original `validate()` checks except mechanically moving pure validation for offline testability and the one explicitly authorized fail-closed artifact completeness assertion below. No other changed acceptance rule is authorized by this correction.

### Frozen per-case artifact inventory

Read-only inspection of all eight retained `index-readiness-green-68fd8e922a26/artifacts/r3/<provider>/<GoRoot>/result.json` receipts found exactly the same 24 `artifact_sha256` keys. The historical validator hashes only entries present in that mapping; this correction explicitly permits one stronger completeness assertion: require its exact key set to equal the following inventory, require each value to be a lowercase 64-hex SHA-256, and verify every named regular artifact file's bytes. Reject missing/extra keys, missing referenced files and hash mismatches. Preserve all other historical acceptance semantics. Historical receipt values/PASS remain historical test fixtures only.

```text
go-command.json
go-events.jsonl
go-measurement.json
go-stderr.log
measured-runtime.json
migration-driver.sql
migration-driver.stderr
migration-fresh.json
migration-fresh.rows.json
migration-fresh.schema.sql
migration-fresh.stderr
migration-fresh.stdout
migration-replay-empty.json
migration-replay-empty.rows.json
migration-replay-empty.schema.sql
migration-replay-empty.stderr
migration-replay-empty.stdout
migration-replay-populated.json
migration-replay-populated.rows.json
migration-replay-populated.schema.sql
migration-replay-populated.stderr
migration-replay-populated.stdout
populated-before.rows.json
populated-before.schema.sql
```

- [ ] Add failing-first negative tests by mutating copied historical receipt structures: missing/extra/skipped Go/JUnit root, changed candidate, missing artifact hash, duplicate database, one false readiness tuple, bad counters/projection/migration/source identity. Require rejection before calling any cleanup command in these pure tests.
- [ ] Preserve exactly four roots for both bankone/banktwo, eight unique DBs, zero skips/fail/errors, 42 full expected/observed readiness tuples, 20 cold ensures/one job/no external cold work, held model/source readability, atomic publication and 100 warm cycles/unchanged rows. Keep migrations001–040 and input/git equality, original per-case artifacts and failure receipts. Never copy historical PASS into a current receipt.
- [ ] Preserve 1320s monotonic runner deadline from launch, Go90s/bridge120s, startup150s/command180s, ordinary30s, inspect/log10s and cleanup30s bounds. Record timeout separately and always retain failed attempt evidence. Probe compile180s is separately bounded and cannot extend runner acceptance.
- [ ] Test cleanup with fake inspect records: full immutable container IDs, UUID owner token, exact name/image/project/service labels and allowed mounts must all match immediately before stop/kill/remove. Unknown/colliding resources fail closed. Cleanup container explicitly uses `/usr/local/bin/python`, immutable runner ID, network none/read-only root, and sole writable mount `/owned-data` from the fresh owned Seaweed path.
- [ ] Before fixture data deletion require owner marker exact token/path, resolved non-symlink path directly below run root, project containers absent and no container mounting the data path; never follow symlinks. Preserve at least12GiB capacity check before fixture startup. Remove only recorded owned container IDs/volumes/network; do not use global prune or remove-orphans. Verify each volume/network name/project label and actual attachments before removal. Preserve all cleanup receipts; failure keeps overall result failed and reports remaining resource identities, no blind broad fallback.
- [ ] Run focused tests, `python3 -X pycache_prefix=/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test-artifacts/pycache -m py_compile /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/supervisor.py /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/offline_probe.py /home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/test_supervisor.py`, source SHA-256 and allowlist diff checks; independently review exact adaptation/probe/tests. Later coordinator may commit/push validated repository documentation milestones under its authorized cadence; external source is bound by retained bytes/hashes, not assumed present in Git. External source is not committed to this repository by the code-only task; the coordinator commits/pushes this gate checkpoint separately.
- [ ] Handoff reviewed immutable source paths/hashes, offline red/green results, exact planned expanded-argv schema and remaining blockers. Before any real probe, require a separately synchronized committed execution gate with explicit Docker mutation ownership/bounds. Before fixture services, require fixture admission with independently accepted current probe manifests plus the parent runtime gate's exact reviewed supervisor command/hash and independent review/preflight.

## Synchronized implementation gate and deliverables

1. Draft correction review and Issue186/Project8 synchronization passed. The committed checkpoint/full SHA, canonical preflight, independent exact-gate review and explicit absolute external-path code-only dispatch are required before external source edits.
2. External adaptation/probe/tests, offline red/green receipts, source hashes and independent exact-source review are deliverables of the later code-only slice, not claims of current completion.

## Unresolved execution facts (not code-only prerequisites)

1. Fresh executable/distribution/cache manifests, independently accepted manifest digests and current offline import/compile/cleanup-interpreter probe evidence remain absent; code-only work cannot close these facts.
2. Installed Docker/Compose CLI support and actual resolved Compose compatibility remain unmeasured for this adaptation; no image availability/config observation substitutes for the later pre-mutation check.
3. Separately synchronized committed probe gate/dispatch is required for any container; fixture execution additionally requires independently accepted fresh probe evidence and the parent runtime gate with reviewed exact source hashes/command.
4. Direct host layer reads were denied. Collecting fresh image-filesystem manifests therefore requires a separately authorized container probe, never widened privileges, image export, build/pull or package acquisition under this code-only slice.
5. The effective Compose model must prove removal of inherited build fields and unused service with the installed Compose version. Offline tests check intended structure only; later read-only compose-config compatibility must be retained before create/start. Unsupported behavior blocks execution and cannot authorize candidate Compose edits.
