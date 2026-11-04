# Integrated Workshop R3 fixture runtime Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans only after the separately committed gate passes and the coordinator dispatches the bounded runtime task. This draft authorizes documentation only.

**Goal:** Measure the integrated Workshop candidate with one fresh, isolated, bounded R3 fixture run: eight required provider/root outcomes and 42 SQL readiness tuples at one unchanged exact SHA.

**Architecture:** Reuse the unchanged candidate's Python bridge and four Go lifecycle roots for both synthetic providers. A reviewed external supervisor must mount a clean remote-free plain clone read-only, isolate PostgreSQL/NATS/SeaweedFS, freeze immutable image/cache/source identities and retain owned cleanup evidence. Historical leaf success is a blueprint, not acceptance of this integrated candidate.

**Tech Stack:** Docker Compose isolated internal network; PostgreSQL 17/pgvector; NATS JetStream; pinned SeaweedFS S3; existing Go 1.26/Python fixture bridge.

**Spec:** `docs/verification/2026-11-03-canonical-article-lifecycle.md`, “Separate integrated R3 runtime draft”; canonical gate `docs/agents/pre-implementation-gate.md`.

**Draft status:** BLOCKED. Documentation only, uncommitted, unsynchronized and unexecuted. The technical run contract below is fixed; unavailable prerequisites are explicit blockers, not executor discretion. No implementation, acquisition, Docker command, service/VM/cloud operation, GitHub write, commit or push is authorized by this draft.

## Gate, tracking and exact candidate

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-04-workshop-integrated-r3-runtime.json`
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-integrated-r3-runtime.json`
Source candidate: `4d82e413e04fb2401ac7bc28dc828375ac662180`. The coordinator reported independent exact-head integration review PASS at this SHA and draft PR217 creation; this is a coordinator handoff, not a fresh review performed by this planner. This is not the final runtime authorization base: the later committed synchronized documentation checkpoint must be pinned separately and pass machine preflight. Preserve source candidate identity even though its documentation descendant will have a different SHA. If integration review changes code, stop and revise this gate for the new full SHA; do not silently rebind or use a moving branch.

## Global constraints and scope

- Planning branch: `codex/workshop-integrated-r3-runtime-plan`; source base is the full SHA above. Agent preference: GPT-6.1 Sol, medium reasoning, Fast/priority when available.
- This draft modifies exactly the five documentation paths named in the record. Preserve every predecessor queue entry and unrelated field; no application, test, fixture, Dockerfile, Compose, workflow or runner source changes.
- This gate covers synthetic local R3 fixture measurement only. No real Bankone/Banktwo connector, provider credential, live model, payment, identity account or external endpoint may enter the runtime environment.
- Keep final180 separate: identity5 + catalog8 + commerce14 + paid12 + DTO120 + API21 = 180 logical cases needs its own synchronized exact-candidate runner/profile and runtime gate. Neither eight R3 results nor 42 readiness tuples replace any of those cases.
- Cloud/VM/staging bootstrap, production identity, release, merge, deployment, activation and cutover remain separately unverified and unauthorized. No existing leaf/runtime/integration gate grants these authorities.
- Runtime artifacts belong outside source under a fresh UUID-owned `/home/corp/autodata-evidence/` run root. No shared volumes, previous fixture databases, other checkouts or unrelated Docker resources may be mutated or pruned.

## Concrete todo

- [x] Retain the coordinator-reported independent exact-head integration review PASS at 4d82e413e04fb2401ac7bc28dc828375ac662180 with Issue186 comment6636079243 and builder handoff hash; any candidate change requires a fresh binding and review.
- [ ] Resolve immutable runner/service image availability, candidate compatibility, cache manifest and reviewed supervisor adaptation facts with read-only evidence; preserve the historical supervisor and leaf receipts.
- [ ] Independently review this docs-only blocked draft; have the serialized coordinator preserve Issue186/Project8 history and synchronize this exact goal, scope, references and todo only after blockers close; commit/push the checkpoint, pin its full SHA and pass canonical machine preflight before runtime dispatch.
- [ ] After a separate explicit runtime handoff, prepare a clean remote-free plain clone of the fixed candidate, new owned artifacts and services, immutable input/image/cache/host manifests and a fresh private /home SeaweedFS bind with at least 12 GiB free.
- [ ] Execute the unchanged required pytest bridge and eight exact Go roots under the 1320-second runner deadline; require zero skips, 42 expected/observed SQL tuple matches and every original lifecycle invariant.
- [ ] Preserve before/after provenance, all failed/successful commands and evidence, and bounded ownership-checked cleanup; obtain independent exact-run audit and synchronize measured completion without claiming final180, provider, payment, cloud or release acceptance.

## Evidence already inspected (historical only)

The leaf source candidate was `23a2f3b2e12c0b14b1d4989ab13a075cf1bee084`, not this integrated candidate. Its final green run is `/home/corp/autodata-evidence/index-readiness-green-68fd8e922a26/`:

- `supervisor.py` SHA-256 `e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9`.
- `artifacts/acceptance-result.json` SHA-256 `a677ebea4d8234d222c2d71065b0bf9337b2fbef0e51ed23f2b0eef5a967209a`.
- Independent leaf audit `/home/corp/autodata-evidence/index-readiness-green-independent-audit-68fd8e922a26.json`, SHA-256 `9e8bb8769123928682401fab64f899924b7d168775dd317d09031eb2843bd61b`.
- The leaf measured eight nonskipped Python cases/eight exact Go roots and 42 SQL tuples; retained cleanup and source receipts. It removed its owned build backend before fixtures and used a fresh Seaweed `/data` bind under `/home` with at least 12 GiB free after an earlier capacity failure.

Preserve those files byte-for-byte. Do not rewrite a leaf receipt, copy its candidate value into new results, or describe it as integrated-candidate success.

## Task 1: Close provenance and runner blockers before synchronization

**Files:** only this plan, its record/task, queue entry and canonical verification amendment. No runtime preparation occurs in this task.

**Chosen runtime strategy:** reuse the existing immutable acceptance image and service image IDs, only after read-only current availability and compatibility evidence. Do not perform a new build, pull, retag, package installation or download under this gate. If any image/cache is missing or incompatible, return BLOCKED and create a separately reviewed acquisition/build gate; do not fall back to mutable tags or online dependency resolution.

Historical IDs below are exact observations from retained inspect receipts, not current availability claims:

| Role | Historical immutable image ID | Reference inspected |
| --- | --- | --- |
| R3 runner/cleanup Python | `sha256:b43f27cfb2dc268b00baf0458bd50f411caccb8d23f037c2819d1d304463fc8c` | `artifacts/runner-before.json` |
| PostgreSQL/pgvector 17 | `sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e` | `artifacts/container-106d8e11ce069eb34338e1390c3cd0e9eb1629a822d92e4f2c2ab0d525d67c54.json` |
| NATS | `sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045` | `artifacts/container-fff1c7fa220d6ce537bc175c57c94e38eb68ec7e2b33e97739d6b42475518455.json` |
| SeaweedFS | `sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5` | `artifacts/container-3c112bb155cc7bbce2c3e9eb9748645bc2c82ff39d2425b74fa424ab1d3ca763.json` |

The Compose Seaweed registry reference is `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`. A registry manifest digest and a local image configuration ID are different identities; retain both and platform metadata rather than comparing them as equal.

- [x] Bind exact-head integration review PASS to the coordinator’s [Issue186 comment6636079243](https://github.com/lucronn/autodata/issues/186#issuecomment-6636079243), reported verified by full readback. Candidate tree is `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`. The builder handoff `/home/corp/autodata-evidence/final-leaves-builder/corrected/final-handoff.json` SHA-256 `de910ae65e80a4a94ff91dd886a030bafd3e695228f57d9d7c99b2b77e6668a4` was rehashed by this planner; it predates the reviewer and says review pending, so the later coordinator review receipt supplies PASS. This review gives no R3 or production approval.
- [ ] Have a separately authorized read-only provenance inspection establish current local image IDs/platforms, runner `/usr/local/bin/python` and Go/psql/pg_dump/git versions and executable hashes, installed Python/package versions and hashes, and immutable `/opt/go-module-cache` file manifest. Record before/after manifest hashes; runtime Go cache and temporary files use only fresh owned tmpfs.
- [ ] Compare candidate `apps/api-go/go.mod`, `go.sum`, `packages/contracts/go/go.mod`, both worker `pyproject.toml` files, fixture bridge/support files, Compose file and Dockerfile against the historical source manifest. Explicitly enumerate any difference and prove the reused runner has every required dependency with offline checks. Matching image ID alone does not establish candidate compatibility.
- [ ] Supply and independently review an exact external supervisor adaptation source/hash plus allowlist. It must implement immutable-image reuse, no build/pull/acquisition, required manifests, inherited evidence validation, and ownership cleanup. The current historical supervisor is not that adaptation: it always creates a builder and builds from mutable `golang:1.26`, `python:3.14-slim`, `moby/buildkit:buildx-stable-1`, apt/pip resolution and `go mod download`; its PG/NATS service tags are mutable. No such adaptation file exists in this draft. Any required runner implementation has its own gate before edits.
- [ ] The coordinator preserves full live Issue/Project history, appends this exact goal/refs/scope/todo, reads back hashes, updates canonical documentation and commits the synchronized checkpoint. Then pin its full SHA, pass `scripts/autonomy/pre_implementation.py` using the repository's canonical invocation and obtain independent committed-gate review/runtime dispatch. This draft intentionally fails the status boundary.

## Task 2: Fresh exact-input fixture setup after separate runtime handoff

**Consumes:** the fixed candidate, the later passing committed runtime gate and reviewed supervisor adaptation plus immutable local IDs/manifests. **Produces:** one new owned run root with complete source/host/image/cache/config identities before services start.

The baseline supervisor invocation, recorded here only to fix argument semantics, is:

```sh
python3 /home/corp/autodata-evidence/index-readiness-green-68fd8e922a26/supervisor.py \
  --source /home/corp/.codex/worktrees/workshop-final-leaves-build/autodata \
  --sha 4d82e413e04fb2401ac7bc28dc828375ac662180 --phase green
```

**Do not execute that baseline command:** its unconditional build contradicts Task 1's selected reuse strategy. The final executable command must name the reviewed adaptation's actual immutable path/hash with these same source/full-SHA/green arguments; absence of that exact command is a blocker. Do not invent a future filename or assume an override flag exists.

- [ ] Allocate a fresh 32-hex token, project `autodata-index-<first12>`, source clone, artifacts and private `seaweed-data` directory below a new `/home/corp/autodata-evidence/index-readiness-green-<first12>/`. Refuse existing paths/names, symlinks, resource labels and image name collisions. Persist token/path ownership marker before data writes.
- [ ] Preserve baseline clone commands exactly: `git clone --no-hardlinks --no-checkout <source> <new-checkout>`; `git -C <new-checkout> checkout --detach 4d82e413e04fb2401ac7bc28dc828375ac662180`; `git -C <new-checkout> remote remove origin`. Check exact HEAD, empty porcelain including untracked files, no remotes, ordinary `.git` directory (not a linked worktree), no tracked symlinks and no non-Git file outside the tracked manifest. Never run acceptance directly from the planning/integration worktree.
- [ ] Emit `inputs.sha256.json` over every tracked mode/path/file byte and `host-before.json` with candidate SHA, clean state, no remotes, plain-clone origin and manifest hash. Record source tree SHA and supervisor hash. Mount clone at `/workspace:ro`; `/artifacts` is the only persistent runner output mount; `/tmp:exec` is fresh tmpfs.
- [ ] Emit host manifest: UTC time, OS/kernel/architecture, Docker and Compose versions, daemon/root context identity, disk capacity, IDs of existing resources and exact owned token. Emit immutable image manifest for all four runtime IDs and runner executable/dependency/cache hashes. No secret environment dump; preserve only the explicit allowlist below.
- [ ] Resolve the canonical `infra/compose/compose.article-lifecycle-test.yaml` against `/dev/null` env. The reviewed private override may change only all runtime `image` fields to the accepted immutable IDs, set pull policy never/no-build for runtime services, and replace only minio `/data` volume with the fresh owned bind (`create_host_path=false`). Preserve baseline/config/delta hashes and verify no additional service environment, command, network, mount, port or build occurs. Do not invoke `test-runner` or a build section.
- [ ] Verify `seaweed-data` is empty, resolves directly below its owned `/home` run root, is not a symlink, and has `free_bytes >= 12 * 1024**3` immediately before service startup. Capture Docker capacity separately. Refuse instead of deleting other resources for space. Verify actual Seaweed inspect mount `/data` is this one writable bind. Ownership cleanup must remove only its contents after all mounts are absent.
- [ ] Start only fresh project-owned PostgreSQL, NATS and Seaweed on the new Compose internal network with fresh project volumes for PG/NATS, no published ports and no external network/provider route. Preserve labels, IDs, config, health and startup logs. Confirm PG major17, user `lifecycle_test`, NATS JetStream and S3 roundtrip in fixture receipts. Never import a previous database or bind.

## Task 3: Exact execution contract

The host allowlist is `PATH`, `HOME`, `USER`, `LOGNAME`, `LANG`, `LC_ALL`, `TZ`, plus exactly `AUTODATA_R3_TEST_IMAGE` (accepted immutable runner ID), `AUTODATA_R3_CANDIDATE_SHA=4d82e413e04fb2401ac7bc28dc828375ac662180` and `AUTODATA_LIFECYCLE_ARTIFACT_DIR` (new owned artifact path). Use `--env-file /dev/null`. Provider URL/key/payment/production credentials are absent.

The runner mode is fixed by the unchanged Compose environment:

```text
AUTODATA_LIFECYCLE_TEST=1
AUTODATA_CATALOG_INTEGRATION_REQUIRED=1
AUTODATA_CATALOG_TEST_CANDIDATE_SHA=4d82e413e04fb2401ac7bc28dc828375ac662180
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/workspace/workers/ingestion-python/src:/workspace/workers/enrichment-python/src:/workspace/packages/contracts/python:/workspace/workers/ingestion-python/tests
GOTOOLCHAIN=local
GOPROXY=off
GOFLAGS=-mod=readonly
CGO_ENABLED=0
GOMODCACHE=/opt/go-module-cache
GOCACHE=/tmp/go-cache
GOTMPDIR=/tmp/go-tmp
```

Use the frozen Compose prefix `docker compose --env-file /dev/null -p <owned-project> -f infra/compose/compose.article-lifecycle-test.yaml -f <reviewed-private-override>` from the plain clone. The final supervisor must pass the immutable image/config checks before this exact subprocess:

```sh
docker compose <frozen-prefix-options> run -d --pull never --no-deps \
  --name <owned-project>-go-test-runner go-test-runner \
  python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/index-readiness-r3.xml \
  workers/ingestion-python/tests/test_catalog_api_integration.py
```

Angle-bracket values above are the fresh UUID-owned paths/names deterministically defined in Task 2, not discretionary options. Retain final expanded argv and allowlisted environment before launch.

- [ ] Enforce 1320 seconds of monotonic elapsed time from detached runner launch, polling its owned immutable container ID; preserve Go 90-second timeout and bridge 120-second process timeout. At deadline stop the owned runner for 5 seconds, then kill if still running; classify timeout as failure and proceed to bounded owned cleanup. This is the runner deadline, not a claim that preparation plus cleanup totals 1320 seconds. Preserve startup wait150/command180, ordinary command30, inspect/log10 and cleanup30 bounds from the reviewed supervisor, without unbounded waits.
- [ ] The bridge owns eight new `lifecycle_test_<32hex>` databases and supplies each Go subprocess with only harness-generated fixture DSN, vehicle/article/other-article IDs, provider, loopback ensure/control URLs/token and case artifact path, plus fixed required-mode/candidate env. DSN is `postgres://lifecycle_test:lifecycle_test_only@postgres:5432/<fresh-db>?sslmode=disable`; no host/production DSN override. Go argv is exactly `go test -json -count=1 -timeout=90s -run ^<exact-root>$ .` in `/workspace/apps/api-go`.
- [ ] Require exactly the four roots below for bankone and banktwo, each exactly once: `TestPostgresCatalogLifecycleColdHTTPRaceOneJob`, `TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP`, `TestPostgresCatalogLifecycleAtomicPublication`, `TestPostgresCatalogLifecycleWarmReadsNoExternalCalls`. Exactly eight JUnit cases, eight Go root run/pass pairs, package pass, zero skipped/fail/error/subtest roots and eight unique databases are mandatory.
- [ ] Require the cold root's existing plain SQL helper to emit 21 uniquely named cases per provider in `go-measurement.json`: all 42 `passed=true`, expected equals observed full `(status, complete, retryable, processed, total, percent)` tuple, `total=2`, `percent=processed*50`. Preserve actual named cases from source/measurements rather than counting a summary or treating a skipped SQL path as acceptance.
- [ ] Retain original assertions: 20 real internal cold ensures/one durable job/no external cold work; source readable during captured model response hold with zero active-read ensure/provider/model delta; atomic source/canonical projection and one publication; 100 warm cycles with zero external work and unchanged immutable rows. Preserve provider-isolated descriptors and migrations001–040 fresh/empty/populated replay no-op evidence. No successful readiness matrix may excuse a failed lifecycle root.

## Task 4: Evidence, failure and bounded ownership cleanup

- [ ] Preserve expanded command logs/results, runner before/final/stopped inspect/log, all service inspect/logs, host before/after, runner input/git before/after, image/cache before/after manifests, eight case result/measured-runtime/go-measurement/event/stderr/command/migration files, JUnit and all referenced hashes. Require every candidate field to equal the exact fixed source SHA and every input-byte comparison to pass.
- [ ] Final host observation must equal the original tracked manifest and clean/remote-free identity. Image module/dependency manifests must equal their accepted values after the run; a new tmpfs Go compilation cache is expected ephemeral output, never evidence of a preexisting module cache.
- [ ] On success or failure, stop only the inspected runner ID with matching project/name/image; inventory only owned service IDs and preserve their logs before teardown. Refuse `--remove-orphans` if any unexpected ID carries the project label. Remove only owned Compose network/volumes/containers. Never run global prune, broad rm or delete another fixture's state.
- [ ] Verify no project container remains and no Docker container mounts the private Seaweed source before cleanup. Use only the accepted runner image's independently probed `/usr/local/bin/python`, explicit entrypoint, `--network none`, read-only rootfs and sole `/owned-data` bind after inspecting helper token/name/image/mounts. Bound wait30, stop5 then kill if required; retain helper inspect/log/exit. Remove only owned bind contents and directory; preserve ownership marker, override and receipts.
- [ ] Record acceptance status failed for any timeout, skip, missing assertion/artifact, provenance mismatch, unexpected resource or cleanup failure. Preserve original failure receipts and separate any recovery receipt; never overwrite an attempt as green. An unavailable prerequisite returns blocked without starting services.
- [ ] Independent audit must recompute source/artifact/command/cache/image identities, all eight exact roots and 42 tuples, original measured invariants, deadline and cleanup from immutable artifacts. Only then may the coordinator publish this gate's measured result and evidence hashes. Integration code review, final180, live providers/payments, cloud and release states remain separate.

## Explicit unresolved facts and disposition

- Historical image IDs exist in receipts, but current local availability, platform/entrypoint/tool versions, whole dependency/module cache manifests and candidate compatibility have not been established.
- The pinned historical supervisor always invokes an unpinned docker-container BuildKit build; it does not implement the selected immutable-image reuse path or immutable dependency/cache manifests. No adaptation source/hash has been supplied or reviewed.
- Fresh Issue186/Project8 synchronization, independent planning checkpoint review, committed checkpoint SHA, exact-base machine preflight and runtime handoff do not exist for this separate gate.

The draft is intentionally not dispatchable. Closing those facts requires reviewed evidence and a new synchronized committed checkpoint; natural-language approval alone cannot convert this record to a passing gate.


<!-- BEGIN 2026-11-04 independent R3 owned subprocess transport successor -->

## Independent R3 owned subprocess transport successor

This append-only successor preserves the integrated-runtime and fake-only histories. It plans the independent two-file process primitive and grants no execution or release authority. Real-child tests can run only under a later explicit two-file code dispatch after exact-checkpoint review.

## Canonical synchronized planning record

This is the dedicated successor checkpoint for the owned subprocess primitive. The parent fake-only collector spec is immutable historical policy, not execution authorization. The actual resulting checkpoint SHA must be sealed externally; no self-referential SHA is invented here. Independent exact-checkpoint review and explicit dispatch remain required after committed preflight.

```json
{
  "schema_version": 1,
  "goal": "Add a real Linux subprocess primitive that bounds retained output, accounts a nonrenewable shared budget and cancels/reaps only its owned local observation child/process group, providing the first enforcing building block for a later real R3 preparation adapter.",
  "plan_ref": "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
  "spec_ref": "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
  "record_ref": "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
  "task_ref": "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md"
  ],
  "todo": [
    "Freeze the e414e853 parent, real-child-only verification contract, exact two-file scope and false authorities; synchronize dedicated plan/spec/task/record, canonical index and Issue186/Project8; pass committed exact-base standalone/nested preflight and independent checkpoint review before dispatch.",
    "Implement and test exact admission, nonrenewable shared capture accounting and bounded binary stdout/stderr retention using only owned synthetic Python children.",
    "Implement and test monotonic cancellation/deadline handling, identity-safe owned group termination, direct-child reap and conservative cleanup_unconfirmed outcomes without host/tool/provider discovery.",
    "Run the focused real-child suite, memory syntax/static checks and exhaustive two-file/predecessor preservation checks; commit/push coherent validated milestones and obtain independent exact-code-head review and normal CI readback.",
    "Synchronize code-only measured receipts and explicit unresolved production containment/startup/file/owner/host/runtime/product/payment/final180/staging blockers; grant no runtime, promotion, merge, deployment or cutover authority."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-04T19:35:00.908451+00:00",
  "planning_status": "tracking_synchronized_pending_checkpoint_review",
  "planning_base_sha": "e414e8537c8a6f0bc99747f6db09782b7743a949",
  "implementation_base_sha": null,
  "execution_gate_sha": null,
  "scope": "owned_subprocess_transport_primitive_only",
  "allowed_gate_document_paths": [
    "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
    "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
    "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
    "docs/agents/tasks/2026-11-03-production-release/queue.json"
  ],
  "allowed_implementation_paths": [
    "scripts/r3_preparation/process_transport.py",
    "scripts/r3_preparation/test_process_transport.py"
  ],
  "source_document_sha256": {
    "/home/corp/autodata-evidence/next-release-gate-analysis/PLAN.md": "a80cb38985ed5b42d0f3020bd9903f10ce75371c289c633bac0980df59fdab30"
  },
  "external_plan_review_ref": "/home/corp/autodata-evidence/next-release-gate-review/verdict.json",
  "tracking_sync": {
    "accepted_case_credit": 0,
    "current_comment_count": 177,
    "future_implementation_paths": [
      "scripts/r3_preparation/process_transport.py",
      "scripts/r3_preparation/test_process_transport.py"
    ],
    "goal": "Add a real Linux subprocess primitive that bounds retained output, accounts a nonrenewable shared budget and cancels/reaps only its owned local observation child/process group, providing the first enforcing building block for a later real R3 preparation adapter.",
    "issue_after_sha256": "982000b290b2ebb0cb447620f1a3065a647898be8828f5f82dc2d05b2bf3c17b",
    "issue_before_sha256": "5a651a9cddf2e01ed3ab3b17c984914d44469cf69567877d0c734703baf7997b",
    "issue_body_unchanged": true,
    "issue_comment": "https://github.com/lucronn/autodata/issues/186#issuecomment-6640162652",
    "other_project_fields_unchanged": true,
    "planning_parent_sha": "e414e8537c8a6f0bc99747f6db09782b7743a949",
    "planning_paths": [
      "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
      "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
      "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
      "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
      "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
      "docs/agents/tasks/2026-11-03-production-release/queue.json"
    ],
    "previous_source_archived_verbatim": true,
    "prior_comment_count": 176,
    "prior_comments_preserved": true,
    "project_after_sha256": "bff82971b35007013586fd80d2012b1fd4cb34de6d9a8f485ede169183d2eddf",
    "project_before_sha256": "6c5b27b6a65662fa337c53168c7c0bbc6c255dc0157e1ee60080b47c45d23654",
    "status": "synchronized_live_readback",
    "todo": [
      "Freeze the e414e853 parent, real-child-only verification contract, exact two-file scope and false authorities; synchronize dedicated plan/spec/task/record, canonical index and Issue186/Project8; pass committed exact-base standalone/nested preflight and independent checkpoint review before dispatch.",
      "Implement and test exact admission, nonrenewable shared capture accounting and bounded binary stdout/stderr retention using only owned synthetic Python children.",
      "Implement and test monotonic cancellation/deadline handling, identity-safe owned group termination, direct-child reap and conservative cleanup_unconfirmed outcomes without host/tool/provider discovery.",
      "Run the focused real-child suite, memory syntax/static checks and exhaustive two-file/predecessor preservation checks; commit/push coherent validated milestones and obtain independent exact-code-head review and normal CI readback.",
      "Synchronize code-only measured receipts and explicit unresolved production containment/startup/file/owner/host/runtime/product/payment/final180/staging blockers; grant no runtime, promotion, merge, deployment or cutover authority."
    ],
    "receipt_ref": "/home/corp/autodata-evidence/r3-process-transport-planning-tracking/receipt.json",
    "receipt_sha256": "0318d50bcd8777658834495559b3820a0609a6b5faa508808d151b38754f9c76",
    "writer": "coordinator sole serialized writer"
  },
  "implementation_blockers": [
    "Commit/push the actual six-path checkpoint and externally pin its full SHA; pass standalone/nested canonical preflight at that SHA, independent exact-checkpoint review and explicit two-file dispatch before implementation."
  ],
  "execution_blockers": [
    "Production containment/startup supervision, descriptor-anchored FilePort/output I/O and bounded JSON remain separate.",
    "Named owner/reviewer/cancellation identities, approved host/tool/plugin/config/env/image/clone/output contracts and separately authorized preparation observations remain unresolved.",
    "Real CommandPort binding, compatible kernel supervision, runtime attempt/review, authenticated product/provider/payment/browser evidence, final180, profile promotion, staging, publisher/recovery and production/cars.tk cutover gates remain separate."
  ],
  "trusted": false,
  "runtime_accepted": false,
  "host_observed": false,
  "accepted_case_credit": 0,
  "profiles_enabled": false,
  "enabled_tiers": [],
  "runtime_lock": null,
  "run_record": null,
  "authority": false,
  "fixture_verified": false,
  "product_candidate_verified": false,
  "staging_verified": false,
  "deployment_authorized": false,
  "cutover_verified": false,
  "implementation_authorized": false,
  "runtime_execution_authorized": false,
  "profile_promotion_authorized": false,
  "merge_authorized": false,
  "authorities": {
    "fixture_verified": false,
    "product_candidate_verified": false,
    "staging_verified": false,
    "deployment_authorized": false,
    "cutover_verified": false,
    "implementation_authorized": false,
    "runtime_execution_authorized": false,
    "profile_promotion_authorized": false,
    "merge_authorized": false
  },
  "release_state": "unverified"
}
```

<!-- END 2026-11-04 independent R3 owned subprocess transport successor -->
