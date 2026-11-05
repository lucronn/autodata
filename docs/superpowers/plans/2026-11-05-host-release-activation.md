# Host Release Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate an already provisioned AutoData host using immutable local releases, maintenance-first lifecycle operations, actual PostgreSQL/service/dependency readiness, and schema-compatible rollback.

**Architecture:** Keep the environment-cleared fixed-path shell launcher. Add one host lifecycle module that collects real bounded observations and controls the existing immutable Compose graph. Strengthen the runtime helper with a real transactional schema collector and dependency-only readiness observations; retain existing pure validators and fail-closed prerequisite checks.

**Tech Stack:** Python standard library, POSIX shell, fixed installed Docker/Compose, PostgreSQL17 psql, Caddy admin socket, existing Go GET /readyz.

**Spec:** This plan and the executable boundary in `docs/operations/workshop-gcp.md`; previous hosting design `docs/superpowers/plans/2026-11-03-workshop-hosting.md` remains historical for earlier milestones. This successor explicitly authorizes the lifecycle and locked-schema implementation previously excluded there.

Issue: https://github.com/lucronn/autodata/issues/299
Parent launch issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source base: `38b53eca633eee94f045fc33d9c90bb36da7618d`
Record: `docs/agents/records/2026-11-05-host-release-activation.json`
Task: `docs/agents/tasks/2026-11-03-production-release/host-release-activation.json`

## Global constraints and boundaries

- This is executable on-host code for an already provisioned host, not an offline simulation wrapper. Implemented lifecycle verbs must invoke the real bounded local executor by default when called from the installed CLI. Test injection cannot be a substitute for this production connection.
- CLI remains exactly `deploy.sh check|install|start|stop|maintenance|resume <40-lowercase-hex-source-sha>`. `install` retains its existing inert-install boundary. No arbitrary paths, extra flags, custom executors, environment overrides, commands, URLs or secret values are accepted through the CLI.
- Production commands use fixed `/usr/bin/docker`, `/usr/bin/findmnt`, installed `/opt/autodata/bin` helpers and the existing project `autodata-production`, with sanitized environment, cwd `/`, no shell command evaluation, redacted error receipts and bounded capture. Invocation as non-root fails.
- No code changes outside the eight-path allowlist below. No cloud resource/registry/provider action or production credential access during development. Disposable PG17 tests use synthetic data and explicit isolated test connection settings, never host production configuration.
- Host prerequisites are explicit: reviewed accepted release already installed; immutable image cache; expected persistent disk and tmpfs; deployed runtime helper/schema/Compose template; metadata/storage guards; provisioned PG17 database and least-privilege socket identity/auth; current schema migrated; private service files and pre-existing service data directories. Startup validates these and fails without them. It does not migrate, initialize PostgreSQL, mount/format disks, fetch images, provision roles, publish artifacts or deliver secrets.
- New `runtime-grants.sql` documents the exact bootstrap-time probe grants; it is never invoked by activation. No superuser/admin fallback, role membership, BYPASSRLS, database/schema ownership, CREATE/TEMP/MAINTAIN grant or alternate password discovery. ACCESS SHARE needs only existing SELECT rights; missing lock permission blocks rather than broadens the role.
- `no_work` means the checker only observes fixed local readiness, not that the application queue is empty. Worker startup is a real activation and can process existing work in later authorized production use. Checks never submit orders, jobs, payments, model requests or bank calls. A local passed receipt cannot certify external legal/payment/account/provider configuration or full product launch.

## Exact implementation allowlist

- `infra/deploy/gce/deploy.sh`
- `infra/deploy/gce/runtime-check.py`
- `infra/deploy/gce/host_activation.py`
- `infra/deploy/gce/runtime-grants.sql`
- `infra/deploy/gce/test_host_runtime.py`
- `infra/deploy/gce/test_host_activation.py`
- `infra/deploy/gce/test_host_schema_pg17.py`
- `docs/operations/workshop-gcp.md`

`host_activation.py` owns file materialization, operation locking, fixed process supervision, maintenance control, release selection and recovery. `runtime-check.py` owns actual schema/service/readiness evidence and existing input validators. The shell routes installed modules. Tests own adversarial execution and PG protocol proof. Runbook updates record real behavior and remaining prerequisites. No Compose template, application or workflow change is authorized by this milestone; if required, stop and synchronize a scope amendment before edits.

## Lifecycle and evidence contract

All lifecycle operations serialize on one no-follow root-owned private `/var/lib/autodata/operations/activation.lock` with nonblocking flock. The parent is created only after the verified data disk prerequisite passes, never on the boot disk. Preserve existing private-material/install operation-lock exclusion too: acquire the existing `/run/autodata/state/operation.lock` before the activation lock in a fixed order so private-file delivery cannot race service startup. Revalidate pinned input inode/hash identities and mounts before mutation and before committing success. Concurrent calls fail with a redacted operation_failed receipt.

Materialize `compose.production.yaml` and `Caddyfile` only from `render_bundle` of validated manifest/configuration. Create absent regular root-owned mode0600 files with O_EXCL/no-follow inside the already verified release directory; never overwrite different bytes or accept caller-authored extra runtime configuration. Existing exact files are idempotent. Bound file sizes, recheck directory identities and require final bytes match before any Compose call. NATS/S3 private configuration remains supplied through its existing fixed private-file contract. Reject unresolved template tokens. Compose always uses fixed `--project-name autodata-production --project-directory <release> --file <release>/compose.production.yaml`, `--env-file /dev/null`, `--pull never`, and explicit service lists: never build, pull, remove volumes or execute arbitrary profiles.

Maintenance uses only `/run/autodata/caddy/maintenance.caddy`: private validated root-owned directory, atomic same-directory replacement of a regular mode0444 file containing exactly `respond "Maintenance" 503\n` or empty bytes. Rename the import file in its mounted directory so Caddy sees replacement. Reload using the existing Caddy container's fixed `caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile --address unix//run/caddy/admin.sock`. If the edge is absent, maintenance file creation precedes edge startup. Record success only after reload succeeds for a running edge. If reload fails, stop the edge before further activation changes and retain maintenance; never leave an unverified open edge.

- `check SHA`: verify installed manifest/configuration/migration bytes, mounts, guards, private material, cached images, locked schema, actual desired service graph and fixed local readiness. No mutation. All required true observations yield exit0/status passed; previously hardcoded schema/services/runtime_evidence false become actual observations. Missing/invalid state remains failure.
- `start SHA`: capture validated current selection; validate target/prior rollback compatibility before mutation; install maintenance first; verify pre-existing initialized data directories; `up -d --no-deps --pull never postgres nats minio`; verify locked schema; `up -d --no-deps --pull never api ingestion-http article-worker payment-reconciler caddy`; verify services and bounded GET /readyz; atomically select SHA; remove maintenance and reload edge only after all checks pass; recheck inputs and return success. Do not start migration/bootstrap/metrics-probe profiles.
- `maintenance SHA`: require SHA is current and owned graph matches; atomically enable maintenance, reload existing edge, return observed maintenance success. Never claim full runtime readiness from this verb alone.
- `resume SHA`: require current SHA; run full schema/service/dependency prerequisites while maintenance stays enabled; clear maintenance and reload only after success. A failed readiness probe leaves maintenance enabled.
- `stop SHA`: require SHA is current or the selected verified target in failed activation recovery; enable maintenance; stop edge first if maintenance cannot be confirmed; stop application services then edge then postgres/nats/minio using explicit bounded Compose stop lists. Never `down -v` or remove data. Service absence is idempotent only after ownership inspection. Return actual stopped-state evidence, with runtime_evidence false because stopped is not ready.

`/opt/autodata/current` is an atomic root-owned symlink pointing exactly to `/opt/autodata/releases/<SHA>`; reject all other target forms and untrusted parent metadata. Construct a unique temporary symlink in `/opt/autodata`, verify the selected prior link identity, then atomic rename and parent fsync. Publish it only after successful readiness. Existing target release bytes are never edited to select another version.

Rollback is bounded once: when target start fails after mutation, preserve maintenance and stop the failed target's application services; restore only `target.rollback_source_sha` if it equals the captured current release and `validate_manifest(target, config, previous)` proves identical migration inventory and configuration. Revalidate cached images/prerequisites and start/probe that exact prior graph; atomically restore previous current link only after successful recovery. Recovery remains in maintenance until explicit resume. On first activation with no previous release, leave current absent and application/edge stopped. Any failed/timeout recovery returns exit6/recovery_incomplete; successful recovery still returns a failed activation receipt, never passed. No automatic SQL rollback or arbitrary historical release selection.

Every command has a finite timeout and bounded stdout/stderr: maximum 1MiB retained JSON/output, 5s inspect/probe, 30s Compose/reload/stop, 120s whole lifecycle with reserved final 30s for one recovery attempt. Kill/reap the process group on timeout, bound drain/cleanup, and distinguish timeout exit5 from recovery_incomplete exit6. Never print subprocess stderr, private bytes, inspect environment values or token-bearing requests. Receipts use the existing version1 schema/failure codes and report observations separately from operation outcome.

## Task 1: Real stable schema observation

**Files:** `runtime-check.py`, `runtime-grants.sql`, `test_host_runtime.py`, `test_host_schema_pg17.py`.
**Interface:** `collect_postgres_schema(manifest) -> dict` returns the strictly validated `{version: int, migrations: list[str]}` only after a real fixed PG17 transaction succeeds. Existing `collect_postgres_catalog` stays catalog-only and cannot set schema true. The new collector owns the complete single-session lock/catalog/ledger protocol.

- [ ] Add a failing pure executor test proving that catalog-only observations cannot set schema true and malformed/missing grants never trigger fallback.

```python
def test_schema_cannot_be_inferred_from_catalog(self):
    with patch.object(self.rt, 'collect_postgres_catalog', return_value={}):
        with self.assertRaises(self.rt.ContractError):
            self.rt.collect_postgres_schema(self.manifest)
```

- [ ] Add real disposable PG17 tests with synthetic public.schema_migrations and the explicit least-privilege probe role. Prove a correct ledger succeeds, missing/extra/duplicate or out-of-order inventory fails, revoked SELECT/CONNECT fails, owner/superuser/BYPASSRLS/extra grants fail, missing table/view/foreign/RLS/custom type/custom AM/expression-index mutations fail, and concurrent rename/replacement/ALTER cannot swap the relation between validation and read. A second session's DDL must block or time out while the first holds its lock. Record a real PostgreSQL17 run, not fake transcript success; tests must fail clearly if explicitly requested without PG17.
- [ ] Implement a fixed psql script in one bounded `docker exec -i` session as the existing metrics socket identity (no TTY, no password, no psqlrc, fixed PGOPTIONS/search_path, ON_ERROR_STOP). The script starts READ ONLY transaction, takes `LOCK TABLE ONLY public.schema_migrations IN ACCESS SHARE MODE`, then inspects built-in catalogs under that held lock. Use psql conditionals to prevent the ledger SELECT from ever being submitted when catalog/role facts fail. Catalog checks enforce the current safe ordinary-heap ledger contract and exact supported primitive types; recheck identity/auth/privilege facts and the locked relation OID. Use no application functions/custom operators/casts. The lock-before-catalog sequence is deliberate; unsafe relation kinds may be locked but their content is never selected. Keep the lock through bounded ledger read/validation and transaction completion; re-inspect the same Postgres container after completion. Bound rows by approved inventory plus one and bound text/output before retaining it. No interactive caller input is forwarded.
- [ ] Ship a reviewed grants script containing only explicit CONNECT on autodata, USAGE on public and SELECT on public.schema_migrations for existing autodata_metrics, plus required revocations consistent with safe-role validation. It is a provisioning input, not an activation side effect. Tests prove exact required rights suffice and broader administrative rights are rejected.
- [ ] Run red/green pure tests and actual PG17 tests, then commit/push `feat(deploy): verify live schema under a stable PG17 lock`.

## Task 2: Actual readiness and fixed host lifecycle

**Files:** `runtime-check.py`, `deploy.sh`, new `host_activation.py`, `test_host_runtime.py`, new `test_host_activation.py`.
**Interfaces:** `host_activation.activation_cli(argv) -> (int, dict)` is the real default lifecycle path; `runtime-check.deploy_cli(argv)` remains the check path; `runtime-check.collect_runtime_readiness(manifest, config) -> dict[str, bool]` collects schema/services/postgres/nats/s3/no_work evidence. Tests inject the module's bounded executor, not a caller-controlled CLI switch.

- [ ] Add failing tests that installed shell verbs start/stop/maintenance/resume load the fixed activation module, normal calls invoke the real bounded executor and wrong inputs fail before mutation.

```python
def test_start_stays_in_maintenance_when_readiness_fails(self):
    host = self.fixture(readiness_status=503)
    code, receipt = host.start()
    self.assertNotEqual(code, 0)
    self.assertTrue(host.maintenance_enabled())
    self.assertFalse(host.current_points_to_target())
    self.assertNotIn('provider_request', host.events)
```

- [ ] Implement one bounded executor shared by real checks and lifecycle operations, using process-group kill/reap, monotonic deadline, fixed argv/env and streaming capture. Test timeout, oversize stdout/stderr, pipe-drain failure and cancellation, retaining redacted receipts.
- [ ] Inspect all eight NORMAL_SERVICES using fixed field projections only, never complete Config.Env. Require exact Compose project/service labels, one running nonpaused/nonrestarting/nondead container per role, manifest image ID, expected command/user/read-only/security/mount/network graph, and exact rendered config consistency. Fail on duplicate/extra role containers or restart/identity drift between observations. Reuse PostgreSQL's stricter existing inspector.
- [ ] Issue only fixed host-local `GET http://172.30.10.10:8080/readyz` using http.client, no proxy, no redirects, 5s total bound and <=16KiB JSON. Require HTTP200 and exactly `database`, `nats`, `object_storage`, each equal to `ready`; any additional `paid_catalog: unavailable` is failure. Never accept `{}` or missing dependencies. The existing handler checks actual TCP connectivity to those three dependencies and local paid-catalog configuration; report that limited fact honestly. PostgreSQL schema is separately established by the transaction collector. These checks do not prove NATS/S3 authenticated operations or external paid-product configuration. No caller URL or customer identity. Set no_work only because this fixed request cannot enqueue provider/payment/model work; tests guard all other paths/methods and assert a bodyless GET. Require fresh pre/post container identities. Map each receipt boolean from corresponding observation; runtime_evidence requires every prerequisite and live readiness check.
- [ ] Implement no-follow idempotent materialization, host locking, validated data prerequisites, maintenance operations and explicit Compose service sequences defined above. Verify actual stored rendered files before execution; never accept a fake callback result as readiness in the production CLI.
- [ ] Update previous offline assertions only where this successor intentionally introduces actual capability; preserve tests that prohibit accidental network/mutation in pure validators. Add lock contention, private-delivery lock contention, pre-existing wrong bundle, symlink/hardlink/owner/mode, directory replacement, missing disk/guard/secret, stale current, immutable image mismatch, readiness redaction and stop-idempotence tests.
- [ ] Run all focused host regression tests and commit/push `feat(deploy): activate verified local releases with maintenance controls`.

## Task 3: Immutable selection, compatible recovery and operator contract

**Files:** `host_activation.py`, `test_host_activation.py`, `docs/operations/workshop-gcp.md`.
**Interface:** successful `start` selects target only after readiness; failed activation uses the manifest-designated compatible prior release once and stays in maintenance, with explicit failure/recovery receipts.

- [ ] Add failing tests for compatible rollback, incompatible migration/configuration denial before mutation, wrong prior SHA, missing prior cache, target failure before/after selection, rename/fsync failure and recovery timeout/failure. Assert no SQL or secret/version rollback.
- [ ] Implement atomic current selection and bounded recovery exactly as the lifecycle contract. Reinspect pinned release files/mounts before link mutation. Preserve prior manifest/selection and never recursively search older releases. Assert receipts cannot claim passed after recovery.
- [ ] Update runbook's current boundary to explain the new executable verbs, exact prerequisites, GET-only evidence semantics, failure codes, stop/start/resume behavior, manual schema/bootstrap prerequisite, compatible rollback and remaining external launch acceptance. Retain historical offline sections as historical, clearly superseded only for this milestone's lifecycle scope.
- [ ] Execute verification below, commit/push `feat(deploy): restore compatible releases after failed activation`, and hand off exact SHA plus evidence for independent review. No merge or deployment is authorized by this plan.

## Verification and acceptance

Run from repository root:

```sh
python3 -m unittest discover -s infra/deploy/gce -p 'test_*.py'
python3 -m py_compile infra/deploy/gce/runtime-check.py infra/deploy/gce/host_activation.py
sh -n infra/deploy/gce/deploy.sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-host-release-activation.json --base-sha <FULL_COMMITTED_CHECKPOINT_SHA>
git diff --check
```

The real PG17 tests may use a disposable isolated cached PG17 test image or local PG17 binaries, with synthetic credentials and a dedicated temporary database/cluster. They must execute the production fixed SQL protocol against PostgreSQL17, exercise a separate concurrent DDL connection, and destroy their own resources. A missing real PG17 environment is an explicit unverified acceptance item and blocks the final schema success claim; it must not be replaced with fixtures or silently skipped as passed. No use of production host configuration/secrets is permitted. Test harness settings remain isolated to test code and cannot alter production collector configuration.

## Concrete todo record

- [ ] Implement a fixed bounded PG17 single-transaction collector: lock before catalog validation, reject unsafe ledger/catalog/role facts before reading ledger rows, compare exact migration inventory, and prove the protocol with real disposable PostgreSQL17 adversarial tests.
- [ ] Implement real fixed-path host lifecycle execution with one host operation lock, verified immutable local Compose/Caddy material, cached images only, validated mounts/guards/secrets, and maintenance-first start/stop/maintenance/resume operations.
- [ ] Collect actual service/container/image/configuration and local GET /readyz evidence without scheduling provider/payment/model work; set schema/services/postgres/nats/s3/no_work/runtime_evidence only from their corresponding successful observations.
- [ ] Atomically select a successfully verified release and restore only the manifest-designated prior release with identical schema/configuration on activation failure; prove failure, timeout, concurrent invocation and recovery behavior with bounded executor tests.
- [ ] Run focused host regressions, real disposable PG17 protocol tests, shell/Python syntax, exact-base preflight and diff checks; commit/push coherent milestones and independently review the exact candidate before integration. Update the runbook with actual executable prerequisites and remaining launch blockers.

## Synchronized implementation boundary

The committed checkpoint must include this plan, matching record/task, Issue299/Project8 references and canonical runbook/architecture update. Run the machine preflight against that exact full checkpoint SHA, push it, and hand off the SHA/tree and tracking readback before any implementation edit. Parent Issue186's accumulated history remains intact; Issue299 is its linked sub-issue with a separate Project item. Historical planning gates remain historical and do not prohibit the separately synchronized code scope here. Future cloud/live activation or missing bootstrap prerequisites require their own reviewed operational authorization.
