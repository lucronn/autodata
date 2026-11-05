# Staging First-Install Application Private-Material Implementation Plan

> **For agentic workers:** This is tracking-synchronized planning material. After a committed checkpoint, passing full-SHA preflight, independent exact-checkpoint review and fresh root dispatch, use the repository implementation workflow task by task. Do not execute this plan before those gates.

**Goal:** Add a root-only staging local first-install helper for one manifest-bound normal application private-file set on a prepared pre-daemon host, without executing workloads.

**Architecture:** A standalone helper uses hash-bound inert-installer filesystem/mount primitives and pure runtime schema validation over descriptor-pinned bytes. One invocation atomically installs one of four fixed application private-file maps; it never invokes runtime.validate_manifest or connects to deployment, cloud or workload execution.

**Tech Stack:** Python 3 standard library, Linux dirfds/no-follow descriptors, flock, renameat2(RENAME_NOREPLACE), fsync and fixed intercepted findmnt probes; unittest temporary inode fixtures. No dependency addition.

**Spec:** `docs/agents/specs/2026-11-04-workshop-staging-private-material.md`. Every exact CLI/input/identity/map/journal/receipt/transaction rule there is normative for all tasks below.

## Planning state and references

Status: `planning_synchronized_pending_checkpoint`. [Issue186](https://github.com/lucronn/autodata/issues/186) and [Project8](https://github.com/users/lucronn/projects/8) were synchronized and read back at https://github.com/lucronn/autodata/issues/186#issuecomment-6637585359; a committed checkpoint, full-SHA preflight, independent review and dispatch remain pending. Record `docs/agents/records/2026-11-04-workshop-staging-private-material.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-private-material.json`, evidence `docs/agents/records/2026-11-04-workshop-staging-private-material-evidence.json`. The coordinator exclusively owns GitHub writes, final checkpoint and dispatch.

The accepted application/source integration base is `4d82e413e04fb2401ac7bc28dc828375ac662180` on `codex/workshop-gce-private-material-gate`. It is not this successor's implementation gate. `implementation_base_sha` remains null until the new planning checkpoint exists. External revision2 report SHA256 `692cf04e2a586f50cb10483f3f296232fedf0e5287d969726e3c15b4ae9f3ad8` has coordinator-relayed independent PASS. The separate exact committed checkpoint review remains pending. Retained external status fields are historical; they are not silently relabeled.

## Global constraints and exact file structure

- Create only `infra/deploy/gce/private_material.py`: fixed root-only staging CLI, pinned first-install validation, private pipe parser, transaction, redacted journal/receipt.
- Create only `infra/deploy/gce/test_private_material.py`: synthetic input/identity/mount/transaction/fault/redaction/denial/parity tests.
- No existing implementation path changes, helper installation, secret access, Docker/cloud/network/VM/provider/runtime action, integration, merge or deployment.
- First install only, one service, absent fixed target, prepared pre-daemon host, no rotation; outcome is `one_service_private_material_installed`, never `secrets_ready`.
- Forward work budget 270 seconds plus 30 seconds best-effort cleanup reserve is cooperative. Kernel I/O/reap/return has no hard bound; durable `operation_status` is always `unconfirmed`.
- Treat publisher/pre-daemon owner acceptance as an explicit trust prerequisite, never as native observed quiescence or authenticated remote secret provenance.
- All prior Stage0/Stage1A/PG/JS/staging statuses, detailed history, indexes and pins retain their own scope and authority.

## Concrete todo (same record/task/tracking work queue)

- [ ] Accept the exact first-install pre-daemon sub-slice and two-file implementation boundary; record coordinator branch/base ownership and independent design review.
- [ ] Synchronize proposed Issue186/Project8/canonical plan/task/record/docs/todo with retained live readbacks and preserved existing histories; commit/push an exact planning checkpoint.
- [ ] Pin the checkpoint full SHA, run machine preflight, obtain independent exact-checkpoint review and fresh implementation dispatch before editing either implementation path.
- [ ] Add offline failing pinned-schema/path-swap/parity, concrete host-record identity/freshness, strict-input/mount/lock/cooperative-budget/non-success-journal/no-replace/fault/redaction/replay tests using fake probe process/selector/clock objects; implement only the new helper and test module.
- [ ] Run focused and existing host/cloud/bootstrap/publisher/contract regression checks offline and scope/diff/syntax checks; commit/push validated coherent milestones on the assigned feature branch.
- [ ] Independently review exact implementation SHA and retained red/green/fault/scope evidence; keep integration and every operational/readiness authority false pending separate explicit gates.

## Task 1: Gate acceptance and trusted-input parser

**Files:** Create only the two allowlisted files after dispatch.
**Interfaces:** Fixed CLI `install <40-lowercase-hex-source-sha> <service>`; `validate_pinned_first_manifest(manifest, config, schema_bytes, runtime) -> str` follows the exact five-step pure sequence in the spec.

- [ ] Coordinator preserves then-current Issue body, all predecessor comments and full Project index verbatim with hashes, synchronizes exact goal/allowlist/todo/references, commits/pushes checkpoint, pins its full SHA, runs preflight and obtains independent exact-checkpoint review and fresh dispatch.
- [ ] Write failing tests for strict CLI/production denial before stdin, exact four service maps, duplicate/unknown/placeholder JSON, boolean-as-int, approval/version/hash/expiry binding and private FIFO/pipe-only framing. Cover 1MiB frame, 1..16384-byte values, canonical strict base64/UTF8 and NUL/CR/LF/marker denial, bounded EOF and zero secret reads/material writes before prerequisites.
- [ ] Write pinned-schema path-swap/no runtime.Path.read_bytes tests plus parity tests against exact candidate first-install fixtures and semantic mutations. Supply original-validator schema reads only exact candidate fixture bytes. Write concrete pre-daemon record freshness/machine/boot/authorization/assertion/byte-drift tests.
- [ ] Run `python3 -m unittest discover -s infra/deploy/gce -p test_private_material.py`; retain the expected failing red output and cause before implementation. Implement the fixed parser and pinned validation boundaries only; rerun to green and retain evidence. Commit/push the coherent validated milestone only after coordinator dispatch.

## Task 2: First-install transaction and fault behavior

**Files:** Modify only the two newly created allowlisted files.
**Interfaces:** Exact mount/identity/lock inputs and redacted durable/public outputs defined by the spec; no generic caller-selected paths or exec interface.

- [ ] Add failing tests for ownership/mode/single-link/parent drift, exact data UUID mount and required tmpfs flags; current/socket/final/temp/journal residue; lock conflict/path replacement and no-replace promotion. Fake probe Popen/selector/killpg/wait/clock objects only.
- [ ] Add failure injection at every create/write/chown/chmod/fsync/close/revalidate/rename/journal boundary, including short write/ENOSPC, mount/lock/target swaps, expiry, signal simulation, identity-unsafe cleanup and denied replay. Advance fake clocks across 270/300 seconds during fsync/close/rename and require timeout/incomplete with no durable passed status. Retain red output.
- [ ] Implement root-private intent-before-material, exact map/metadata/byte checks, shared pinned lock, no-replace directory promotion, final descriptor/mount/approval/pre-daemon rechecks, identity-safe cleanup and non-success journal. Do not change existing primitives to satisfy the scope.
- [ ] Test success for each service and post-promotion failures: close secret FDs before material_verified journal; final stdout may pass only after resource closure, durable fsync and final observed budget check. Global authority fields remain false. Rerun focused tests to green and commit/push validated milestone.

## Task 3: Redaction, regression and exact-candidate handoff

**Files:** Only the two allowlisted files; retained logs are external evidence, with no secret values.

- [ ] Add distinct synthetic sentinels and scan captured stdout/stderr/env/argv/persistent files for values, base64, content hashes and stream hashes. Confirm fixed redacted failure codes, bounded receipts, no traceback/raw child output, and no durable success certificate.
- [ ] Verify reboot boundary only as absence of persistence/units/boot hooks and refusal for missing tmpfs/material. No actual reboot or lost-tmpfs restart-protection claim.
- [ ] Run the offline commands below within the fixed local-fixture boundary. If a suite requires prohibited execution, report it blocked. Retain exact command/exit/stdout/stderr/log hashes and implementation SHA; do not broaden allowlist to repair regressions.
- [ ] Compare exact checkpoint-to-candidate diff to exactly the two new paths and confirm all other implementation blobs unchanged. Commit/push validated candidate and obtain independent exact-SHA review of red/green, timeout/fault/descriptor/redaction evidence before any separate integration decision.

## Verification boundary

All tests run as an unprivileged developer using temporary inode trees, patched ownership/chown observations and intercepted host/cloud operations. In the new test_private_material.py suite, all probe Popen/selector/killpg/wait calls are fake objects with a fake monotonic clock; only isolated local Python CLI-denial subprocesses may run. Slow-probe, descendant-held-pipe, kill/reap-error and deadline tests therefore verify call ordering and fail-closed state logic, not actual OS process-group termination. Existing unchanged regression suites additionally execute their existing local Python and /bin/sh fixture processes and read-only local wrapper utilities. In particular test_host_install.ProbeAndLauncherTests deliberately executes temporary Python probes and a copied launcher; that is permitted offline fixture activity. No suite is permitted root execution, a real findmnt/Docker/gcloud/systemctl command, real mount, Docker socket, network, secret access, cloud or workload operation. If a regression cannot satisfy this local-fixture boundary, report the test as blocked instead of running it or weakening the restriction. Synthetic distinct sentinel strings represent values; inspect all persistent files and captured stdout/stderr/env/argv for any sentinel or its base64/hash representation.


Prospective offline verification commands from a clean implementation worktree (not executed by this drafting task):

```sh
python3 -m unittest discover -s infra/deploy/gce -p test_private_material.py
python3 -m unittest discover -s infra/deploy/gce -p test_host_install.py
python3 -m unittest discover -s infra/deploy/gce -p test_host_runtime.py
python3 -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py
python3 -m unittest discover -s infra/deploy/gce -p test_staging_bootstrap.py
python3 -m unittest discover -s infra/deploy/gce -p test_release_workshop_contract.py
python3 -m unittest discover -s infra/deploy/gce -p test_publisher_adapters.py
node --test infra/deploy/gce/test_publisher_artifact.mjs infra/deploy/gce/test_publisher_identity.mjs infra/deploy/gce/test_publisher_policy.mjs
python3 -c 'import ast,pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ("infra/deploy/gce/private_material.py","infra/deploy/gce/test_private_material.py")]'
git diff --check
```

Run machine gate preflight with the accepted record path and exact committed planning base via `scripts/autonomy/pre_implementation.py --record <canonical-record> --base-sha <full-checkpoint-sha> --repo-root <implementation-worktree>`; the coordinator must resolve and record those concrete arguments. Separately compare `git diff --name-only <full-checkpoint-sha>...<implementation-sha>` with exactly the two implementation paths, and verify the checkpoint's canonical docs and source bindings. This draft cannot supply a future commit SHA or an authorized working tree and does not turn command examples into dispatch.


## Completion limits and unresolved successors

Local code success completes only this two-file code slice. Authenticated publisher/finalize/readback and Secret Manager numeric-version fetch/IAP transport; trusted package/helper install; disk/mount preparation; effective guards, hung-I/O supervision/recovery and reboot-start protection; rendered Compose/Caddy/NATS/S3 and stateful/bootstrap/migrator/metrics secrets; image pull, lifecycle/current selection; schema/roles/passive runtime/no-work evidence; backup/watchdog/restore; activation collection and production dispatch remain separate gates. Real owner identities/versions/evidence are required only for later live use and never justify secret values in chat/repository.

## Code-only implementation receipt (2026-11-04)

The synchronized, independently reviewed planning checkpoint was committed at `b9208fb5967aeafc5e1048a4073beeffd5867e28`; standalone and nested preflight returned `status: synchronized`, `errors: []` before implementation dispatch. The builder made three coherent pushed commits on `codex/workshop-gce-private-material-build`. Exact implementation head `b46217747f103f08a144f9474047a7f2a857f73f` changes only the two new helper/test files named above and is draft [PR #227](https://github.com/lucronn/autodata/pull/227).

The independent read-only exact-head review reported **PASS with no actionable findings**. It reran seven offline Python suites: 38 focused, 40 host-install, 81 host-runtime, 57 cloud-ops, 33 staging-bootstrap, 5 Workshop contract and 45 publisher-adapter tests, totaling 299 passed. Syntax and committed diff checks passed; the reviewer verified the preflight, exact two-path scope, selected source parity and all 27 external evidence hashes. The optional Node publisher suite is explicitly **not passing**: 124 passed, 18 failed on the existing `loadOfficialToolkit` `missing_dependency` descriptor fixture. No dependency install or scope expansion was attempted. The builder's sealed handoff is `/home/corp/autodata-evidence/gce-private-material-builder/handoff.json`, and its SHA-256 manifest is `/home/corp/autodata-evidence/gce-private-material-builder/hashes.json` (manifest SHA-256 `436cf8c8f2a1826d83481158ee46170c44b1db6008e85dd541681b1ea4f05efc`).

This receipt supersedes this plan's historical pending-code-work wording only for the two-file offline slice. It does not change the authorizing checkpoint or its record, and it grants no integration, host, cloud, secret, Docker, runtime, provider, payment, staging-readiness, merge or deployment authority. A local transaction can return only its bounded redacted receipt; the durable journal remains `unconfirmed`. The live-use successors above remain open.
