# Workshop Backup and Isolated Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Coordinator review and exact-base dispatch precede implementation; no agent fan-out is required.

**Goal:** Implement the missing fixed Workshop backup lease/export and isolated restore helpers, with retained disposable local fixture proof.

**Architecture:** Keep the existing hosting/backup receipt contract. A small root-only module owns lease persistence, bounded local commands and isolated restore verification behind injected adapters; thin fixed shell entrypoints supply production paths. A separate opt-in disposable fixture runner exercises real PostgreSQL17 portable restore and cold SeaweedFS/NATS persistence without production configuration or cloud APIs.

**Tech Stack:** Python standard library/unittest, POSIX shell, existing host runtime/activation validators, PostgreSQL17 pg_dump/pg_restore, cached digest-bound Docker images, inert systemd definitions.

**Spec:** `docs/operations/workshop-backup-restore.md`.

Issue: https://github.com/lucronn/autodata/issues/308 (child of https://github.com/lucronn/autodata/issues/186).
Project: https://github.com/users/lucronn/projects/8 ; item `PVTI_lAHOCSJ8cc4BiQ2BzhGPueE`.
Record: `docs/agents/records/2026-11-05-workshop-backup-restore.json`.
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-backup-restore.json`.
Source baseline: `5d14c891e8efd14a297b07e482304ea2a6b9cd7f`.

## Global Constraints

- Public interfaces remain `backup-host.sh begin|status|export|resume <uuid>` and `restore.sh restore|validate <uuid>`; require UUID v4 and no additional arguments.
- Lease exactly1800seconds; recovery reserve300seconds; begin600seconds; resume300seconds; receipt65536bytes; export1073741824bytes; dump strictly smaller than export cap.
- The watchdog service and timer are inert files here: no systemctl/install/sudoers/real host invocation.
- Production adapters have fixed paths and sanitized environment; tests inject adapters in process, never a production CLI/environment path override.
- Existing `host_activation.py`, `host_install.py`, `deploy.sh`, `runtime-check.py`, `cloud-ops.py`, shared schemas/renderers and workflows are read-only dependencies. Scope conflict requires gate amendment.
- Backup and monitor workflows retain exit3. No cloud APIs, IAM/WIF, snapshots, remote SSH, production data/secrets, provider/payment calls, deployment, DNS or cutover.
- Local fixture uses cached exact image IDs, no pull, internal network/no published ports, unique owned resources, finite bounds, mandatory cleanup and retained failures.
- Local restore proof is portable PostgreSQL plus synthetic cold-state proof. It does not certify real cloud snapshots, production completeness, representative RPO/RTO, owner/privilege restoration or readiness.

---

## Concrete todo (synchronized with Issue/record/canonical document)

- [x] Add failing lease, lock, ordering, timeout, crash/watchdog, export-integrity and isolated-restore guard tests against the existing backup receipt/export contract.
- [x] Implement fixed local backup begin/status/export/resume helpers and bounded lease watchdog using installed release, disk, guard, secrets and shared operation locks.
- [x] Implement isolated restore/validate helpers that restore the portable dump into fresh disposable PostgreSQL, reject production targets and validate exact schema/data/object evidence without provider calls.
- [ ] Run retained disposable PostgreSQL/SeaweedFS/NATS fixture recovery proof, failure injection and cleanup verification; distinguish local portable proof from cloud snapshot and full restore-drill evidence.
- [x] Run affected host/cloud regressions, syntax/scope checks and exact-base preflight; commit/push coherent milestones and synchronize exact candidate evidence for independent review.

## File map and shared interfaces

| Path | Responsibility |
| --- | --- |
| `infra/deploy/gce/backup-host.sh` | Fixed isolated Python wrapper, binary export stdout discipline |
| `infra/deploy/gce/backup_restore.py` | State machine, fixed production adapter, durable lease and isolated restore guards |
| `infra/deploy/gce/restore.sh` | Fixed isolated restore wrapper |
| `infra/deploy/gce/autodata-backup-resume.service` | Root-only fixed watchdog invocation with330s timeout |
| `infra/deploy/gce/autodata-backup-resume.timer` | Thirty-second local watchdog schedule, no cloud identity |
| `infra/deploy/gce/test_backup_restore.py` | In-process fake adapters, temporary inodes and fault injection |
| `scripts/dev/workshop_backup_restore_fixture.py` | Opt-in real disposable restore proof and retained evidence |
| `scripts/dev/test_workshop_backup_restore_fixture.py` | Resource ownership, bounds, failed cleanup and receipt tests |

Only these eight implementation paths are allowlisted. Documentation/evidence may update this plan, canonical spec, this leaf's record/task and `docs/verification/2026-11-05-workshop-backup-restore.md`.

Keep module interfaces explicit and small:

```python
# CLI production entrypoints: arguments validated before any mutation.
def backup_cli(argv: list[str]) -> tuple[int, dict | None]: ...
def restore_cli(argv: list[str]) -> tuple[int, dict]: ...
def watchdog_cli() -> tuple[int, dict]: ...

# In-process adapter injection only; no CLI/env override.
def run_backup(verb: str, run_id: str, host, store, clock) -> tuple[int, dict | None]: ...
def run_restore(verb: str, run_id: str, target, store, clock) -> tuple[int, dict]: ...
```

`host` supplies fixed verified inputs/locks, maintenance, stop-writers, dump-to-exclusive-file, pg-restore-list, stop-stateful, sync, start-stateful, start-apps, no-work readiness and export streaming. `store` supplies pinned inode reads and atomic durable state transitions; `clock` supplies UTC, monotonic and boot ID. `target` supplies only validated plan/mount/inventory, exclusive owned resources and fixed restore/inspection operations. Tests record these calls, inject faults and assert real state transitions; do not duplicate the implementation as the oracle. Reuse validation and bounded child execution primitives from the read-only installed modules, adapting deadlines within the new module instead of widening shared code.

## Task 1: Fixed backup state machine and local watchdog

**Files:** create the first six paths in the file map.

**Consumes:** existing `host_activation.py` Pins/Lifecycle and `runtime-check.py` fixed installed-input, mount/guard/graph/no-work validators; `cloud-ops.py:_host`/`verify_export` remain the compatibility oracle.
**Produces:** fixed backup CLI and watchdog; success receipts and export bytes accepted by existing cloud definitions without claiming an actual snapshot.

- [ ] Read the canonical spec and the existing backup evaluator/host lifecycle; write test adapters with a call log, controllable clock, inode-backed store and injectable failure at each mutation.
- [ ] Add failing tests for malformed/extra args, environment injection, locks in wrong order/busy, UUID reuse, descriptor substitution, wrong mount/manifest/current selection, unknown/tenth container, missing secrets, low free space and dump/receipt/output bounds. Test failure before mutation never changes maintenance/services.
- [ ] Add ordering and red compatibility tests. The test must pass the generated receipts and real USTAR bytes to the existing unmodified `_host`/`verify_export`:

```python
code, begin = run_backup('begin', RUN_ID, host, store, clock)
self.assertEqual(code, 0)
self.assertEqual(host.calls, ['maintenance', 'stop_writers', 'dump',
                            'verify_dump', 'stop_stateful', 'sync', 'check_stopped'])
self.assertEqual(begin['state'], 'quiesced')
code, resumed = run_backup('resume', RUN_ID, host, store, clock)
self.assertEqual(code, 0)
self.assertTrue(resumed['writers_resumed'] and resumed['stateful_resumed'])
self.assertEqual(run_backup('resume', RUN_ID, host, store, clock)[0], 0)
# Export/status paths use existing cloud_ops.verify_export as the independent oracle.
```

- [ ] Run `python3 -m unittest discover -s infra/deploy/gce -p 'test_backup_restore.py' -v`; retain the failure attributable to missing helpers, then implement lease intent before mutations, begin/resume/status/export, bounded command process-group cleanup, generic redacted errors and wrapper stdout discipline as specified.
- [ ] Inject interruption after each intent/mutation and verify a resume attempt occurs; incomplete never becomes complete. Test recovery failure, expired lease, backwards wall clock, new boot ID, unreadable/corrupt lease, concurrent watchdog, changed selected release, wrong dump hash and wrong resumed graph. Missing secrets after reboot leave apps stopped/maintenance active.
- [ ] Implement fixed watchdog and inert unit definitions. Test30s timer/330s service bounds, root-only fixed executable/no environment, at most100 lease directories, serialization with operation locks, incomplete status and no cloud command.
- [ ] Run focused tests, `sh -n` wrappers, `python3 -m py_compile` module and tests, `git diff --check`; commit/push `feat: add fixed Workshop backup lease helpers` with red/green evidence. No installation or live helper invocation.

## Task 2: Isolated portable restore and evidence validation

**Files:** modify `backup_restore.py`, `test_backup_restore.py`; create `restore.sh`.

**Consumes:** verified three-file export; exact fixed restore plan and inventory contract from canonical spec.
**Produces:** isolated restore/validate interfaces and exact owned-resource receipts; no production service selection.

- [ ] Add failing plan/mount/archive tests: all required fields/types/hashes; unknown keys; same production UUID/device; non-mount/foreign mount; populated result; path/link race; duplicate/PAX/GNU/link/traversal members; wrong archive/manifest/dump hashes; wrong PG major/image; pre-existing resource/name; production Docker project and any live `/run/autodata` mount.
- [ ] Add a fake target which raises if production paths, provider URLs, payment/API/workers or caller SQL are requested; assert all failure paths preserve input bytes and remove only exact owned created resources.
- [ ] Implement strict input readers, raw USTAR validation, disposable target creation and `pg_restore --exit-on-error --no-owner --no-privileges` with finite child/output bounds. The plan cannot provide a command, connection string or arbitrary destination. Reuse fixed adapters in process; public wrapper paths stay fixed.
- [ ] Validate inventory through fixed SQL/protocol operations. Ledger must equal released migration filenames; use released migrations and actual relation constraints. Exact expected account/session/order/grant/article rows, referenced S3 bytes and JetStream state are compared against bounded inventory. Add negative oracles for wrong owner, missing session/grant, orphan article/object, byte corruption, wrong ledger and missing persisted message; each has its own failure result.
- [ ] Verify no configured commerce application starts and no network leaves the isolated fixture. Run focused tests and syntax/diff checks; commit/push `feat: add isolated Workshop restore validation`.

## Task 3: Actual disposable fixture proof and failure retention

**Files:** create `scripts/dev/workshop_backup_restore_fixture.py`, `scripts/dev/test_workshop_backup_restore_fixture.py`; modify only this leaf's tests if necessary.

**Consumes:** new production state-machine functions with explicit in-process adapters, released SQL inventory, actual cached PG17/SeaweedFS/NATS images.
**Produces:** exact-candidate external evidence with real dump/restore, object/message persistence and cleanup; no claimed real cloud snapshot.

- [ ] Build a resource-owning fixture adapter and fake-runner tests before daemon access. Default execution is inert. Actual execution requires `--execute-local-fixture --evidence-dir <new-absolute-dir>`; directory must be newly created/private and outside production paths. The runner resolves cached images to immutable IDs, verifies PG major17 and records IDs before use; missing cache is a failed prerequisite, never a pass/skip or pull. SeaweedFS must match the hosting plan digest. NATS/PG images must match the reviewed installed manifest fixture's exact image IDs; review and record actual cached IDs before the first real run.
- [ ] Resource names/labels derive from one fresh UUID. Use no ports/host networking/privileged containers or production bind mounts; an internal network and newly owned volumes only. Limit total fixture containers to6, total memory2GiB, PG512MiB, NATS/SeaweedFS256MiB each, at most1CPU per container, finite16MiB logs,900s overall/120s cleanup reserve,1GiB dump/export cap and1000 inventory entries. Reject daemon context mismatch and resource name collisions before creation.
- [ ] Apply the released SQL migrations to PG17, insert two synthetic accounts with distinct configuration/order/grant/session identities plus source/canonical article references using real current schema. Write exact source objects and a JetStream stream/message/consumer with synthetic credentials. Record expected hashes and row/sequence identities in canonical inventory; seed must itself query back and verify them. No provider/Stripe/Firebase configuration is read.
- [ ] Use the real `run_backup` state machine with fixture adapter to stop fixture writers, create and inspect a custom dump, stop PG/NATS/SeaweedFS, fsync and copy only the owned stopped volumes into separate newly owned volumes as a local cold-copy observation. Resume the source fixture, export and feed the archive through `run_restore` into fresh PG17. Use the restored cold storage only for synthetic object/message comparison. Do not label a local copy a GCE snapshot.
- [ ] Actual success requires all expected database rows/ownership/ledger, referenced object SHA and JetStream persisted sequence/consumer state. Run separate negative cases for corrupt dump, missing object, altered owner and missing message; a failure case is successful testing only when the expected restore validation rejects it and retains a failed receipt. No failed attempt is overwritten.
- [ ] Remove only UUID-labelled created containers, networks and volumes; inspect Docker for zero owned leftovers and collect OOM/exit status before removal. Retain script/source/image/archive/inventory/evidence hashes, exact redacted commands, individual assertions/timing and cleanup flags outside deleted volumes. Any cleanup failure makes the runner fail even if data validation passed.
- [ ] Run both fixture-runner unit tests and the actual local fixture command. Record precise evidence directory/hash and actual pass/failure in `docs/verification/2026-11-05-workshop-backup-restore.md`; missing prerequisites remain explicitly unverified. Commit/push `test: prove disposable Workshop backup restoration` only after real evidence is inspected.

## Final verification and handoff

- [ ] Run focused backup/fixture tests, existing `test_cloud_ops.py`, `test_host_activation.py`, `test_host_runtime.py`, `test_host_install.py`, `test_private_material.py` regressions, shell syntax, Python compilation and `git diff --check`. No tests may silently invoke production adapters.
- [ ] Compare `git diff --name-only <pinned-gate-sha> HEAD` to the eight implementation paths and this leaf's docs/evidence. Verify backup/monitor workflows and shared host files are byte-identical to the gate.
- [ ] Re-run the canonical preflight with the full pinned planning SHA, update Issue308 and its Project item with exact candidate/tests/evidence, and request independent review of that exact candidate. Review fixes outside the allowlist require an amended gate first.
- [ ] Leave live cloud snapshot/upload/WIF/monitoring, helper installation, actual restore drill, representative timings, owner choices and cutover to their separate reviewed gates. Do not advance last-verified-backup, mark parent186 Done, merge or deploy.

## Planning evidence

At source baseline, helpers/watchdog files are absent, `cloud-ops.py` is an offline simulation, and backup/monitor workflows explicitly exit3. Baseline `python3 -m unittest discover -s infra/deploy/gce -p 'test_cloud_ops.py' -q` passed57 tests. No implementation, Docker, provider or cloud operation was executed during planning.

The machine preflight is run after this document/record/spec are committed; the receipt pins the full gate SHA. Gate readiness is scope readiness only. Coordinator adoption and fresh implementation dispatch remain required.

## Implementation review checkpoint

Implementation is on `codex/workshop-backup-restore-build`, isolated from the gate checkout. See `docs/verification/2026-11-05-workshop-backup-restore.md` for exact code hashes, 396 passing local tests, retained historical recovery/negative evidence and final attempt8's fail-closed stop rejection. Complete current-source fixture proof remains blocked by cached SeaweedFS Mini shutdown Exit137; it is not a pass or skip. The fixture todo stays open. Detailed design checklists above retain their original acceptance requirements; the verification matrix records actual executed coverage rather than claiming every planned assertion was separately exercised. Issue308 records the final candidate SHA and Project Review status. Parent186 remains open.
