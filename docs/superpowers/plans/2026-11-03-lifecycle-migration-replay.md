# Lifecycle Migration Replay Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded task only after the repository pre-implementation gate passes at the committed checkpoint. This draft is not implementation authority.

**Goal:** Make every repository migration entrypoint skip committed versions under one PostgreSQL session lock, preserving historical SQL and lifecycle schema on restart.

**Architecture:** One POSIX-shell generator produces a self-contained psql driver with embedded SQL. One PostgreSQL session advisory lock serializes check/apply/record across the complete chain. Existing version markers determine skips; pending migrations execute transactionally, and markerless033 receives an explicit one-time replay and marker. Historical SQL remains unchanged.

**Tech Stack:** PostgreSQL17/pgvector, a supported psql client, POSIX shell, existing Python adapter and psycopg/pytest fixture tests.

**Spec:** Existing canonical lifecycle schema spec remains unchanged; this plan defines migration execution/adoption behavior.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8
**Inspected base:** `eaaedd1061dab1f28d5eee55f956903e150060a4`
**Status:** Coordinator-reviewed design, blocked for implementation until verified R2 integration, final tracking/checkpoint synchronization and passing exact-base preflight. The existing lifecycle fixture is a shared R2/R3 path; the migration writer starts after R2 and integrates before R3.

## Verified diagnosis and decision

Retained `/tmp/autodata-migration-repro/result.json` is `[0,3]`. The unchanged sorted Compose loop succeeds once, then fails at037 line2, `relation "vehicle_configuration_vehicle_owner_key" already exists`. Actual CI https://github.com/lucronn/autodata/actions/runs/41618670467 at `9e07beb286f6f67e5a5854c46ebc01cf82318a46` has the same reported second-execution failure after ingestion passes. These are distinct from the earlier fixed dependency failure.

Source inspection finds a version table, not a checksum ledger:001 creates `schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`. Production Compose, Base44 and `migrate.py` ignore it and rerun all files.037/038 have atomic BEGIN/body/marker/COMMIT but non-repeatable DDL. Their fixtures test upgrade and one extra036, not repeated037/038.

A narrow037/038 guard exception is insufficient.031 lines16–21 drops and re-adds `catalog_articles_content_status_check` allowing only `list_only` and `content_complete`;037 expands it to `content_partial`. Replaying031 after lifecycle installation can reject a valid partial row before reaching037. With no such row, guard-skipping037 would still leave a narrowed schema. A later039 cannot repair a failure at031/037. Therefore retain037/038 freeze and fix every operational migration entrypoint to skip already committed versions.

Audit of every filename/marker:001–032 and034–038 each insert exactly their filename stem;033 inserts NO version marker.033 creates hydration scope objects and re-applies reviewer rejection plus `updated_at=now()` for malformed Silverado/1500 identities.001–035 lack outer transactions;036–038 have an exact outer BEGIN/COMMIT. Do not describe the entire legacy chain as already atomic.

## Bounded adoption policy

Keep the existing marker-only provenance. A committed valid version is trusted and skipped; its original applied_at never changes. Do not fabricate historical checksum attestation, introduce a second ledger, or infer applied files from maximum version alone. This repair does not promise detection of someone modifying bytes of an already-applied historical file; repository immutability plus exact-SHA review remains the control.

For markerless033, do NOT infer completion merely because034/036 exists. On first adoption, execute the unchanged033 once inside a runner transaction and insert `033_catalog_scope_coverage` in that same transaction. This intentionally retains033's existing reviewer-state/timestamp effects on matching malformed rows. The coordinator accepts this explicit one-time replay for the implementation and isolated acceptance scope and records it in Issue/Project. It executes the existing pending033 semantics and records them atomically; it does not authorize applying migrations to production. A production adoption must account for the documented reviewer-state/timestamp effects through the deployment runbook. Later runs skip033 like every other version. If such one-time data effects are not acceptable for a target database, stop adoption and design a separately reviewed explicit schema/data attestation path; never silently stamp033.

Recognize legacy committed prefixes with the sole historical033 gap. Reject unknown version strings, duplicate file numbers, mismatched filename numbering/stems and any other ledger gap before application DDL. Reject a missing ledger with known application tables already present rather than guessing an untracked baseline. Empty database bootstrap is valid. A legacy partial001–035 migration with absent final marker is retried under its existing replay-oriented SQL, now in a transaction; its preexisting partial state is not retrospectively certified as atomic.

## Shared driver contract

Create `scripts/dev/migrate_sql.sh`. It must run under `/bin/sh` in `postgres:17-alpine` using only existing shell/core utilities and psql: no Python/runtime/package changes in the PostgreSQL image.

- Interface: `sh scripts/dev/migrate_sql.sh --emit` writes one complete psql driver to stdout and exits; it performs no DB calls. Default invocation generates that same driver into a private temporary file, invokes `psql -X --set ON_ERROR_STOP=1 --file <temp>`, and removes the file through a trap. Existing PG* environment determines target. Support `--migrations-dir <absolute-dir>` for fixture tests; default resolves repository db/migrations relative to the script. No eval or shell interpolation of SQL content.
- Fully validate filenames and manifest before emitting/executing SQL: exactly three decimal digits, underscore, lowercase alphanumeric/underscore stem, `.sql`; unique ascending numbers. Filenames produce SQL-safe expected version strings. Refuse symlink/ambiguous duplicate/unsupported names rather than interpolate unsafe names.
- Emit literal SQL bodies with `cat`, separated by an explicit newline. No `\i`/filesystem includes: the emitted driver must work when streamed to psql inside an existing postgres container that does not mount source. Reject psql metacommands in migration bodies; current files contain none.
- Driver uses `\set ON_ERROR_STOP on`, `SET default_transaction_isolation TO 'read committed'`, `SET lock_timeout TO '60s'`, then `SELECT pg_advisory_lock(186,3738);`. Reserve this lock pair for the migration session. A single psql process holds it across initial ledger validation and every file. Release on normal completion; connection close/disconnection also releases it. Do not split check/apply into different psql sessions.
- Check `to_regclass('schema_migrations')` before referencing the table. If absent on an empty DB, apply001 first inside runner BEGIN/COMMIT;001 itself creates/inserts ledger. Validate existing ledger shape with queries whose failure is fatal. Ledger table may legitimately not exist before001; SQL parsing must not reference it in a branch executed before creation.
- Once ledger exists, compare exact applied versions against the complete validated manifest and require a prefix except historical033. Reject unknown/higher versions instead of running an old checkout on a newer DB. Perform this before pending application DDL.
- For every expected version, use `SELECT EXISTS(...) AS autodata_skip \gset` and `\if :autodata_skip` to skip; otherwise execute that file. psql conditionals evaluate result variables, not migration text. The same session and lock cover the check plus execution.
- For001–035 (including033), emit runner BEGIN, original body verbatim, runner `INSERT INTO schema_migrations(version) VALUES ('<expected>') ON CONFLICT(version) DO NOTHING`, exact marker validation, COMMIT. Existing file inserts are harmless duplicates inside the same transaction. This supplies missing033 marker without editing historical SQL.
- For036–038 preserve their existing BEGIN/body/marker/COMMIT as one embedded block. Do not wrap them in another transaction, strip transaction delimiters, or parse nested PLpgSQL BEGINs. Validate exact expected marker after execution and fail if absent. Their existing bodies already guarantee DDL plus marker atomicity; audit tests must enforce these exact transaction/marker forms for this fixed manifest. Future transaction-bearing migrations require the same explicit audit before support. In particular R5 planned039 must re-pin its scope to include the shared driver/manifest tests if required; it cannot merely add an unsupported file and assume migration acceptance.
- After each actual apply emit machine-readable `AUTODATA_APPLIED <filename>`; skips emit `AUTODATA_SKIPPED <filename>`. `migrate.py` derives its returned completed list from applied lines, preserves stderr and nonzero exit, and never treats generated SQL as a completed application.
- A psql error exits, connection closes and active transaction rolls back; previous committed files remain. No broad duplicate-object catching, manual table dropping, marker deletion or blanket fallback.

Illustrative emitted per-file control, after ledger initialization:

```sql
SELECT EXISTS (
  SELECT 1 FROM schema_migrations
  WHERE version = '037_article_source_lifecycle'
) AS autodata_skip \gset
\if :autodata_skip
\echo AUTODATA_SKIPPED 037_article_source_lifecycle.sql
\else
-- Original complete037 BEGIN/body/marker/COMMIT is embedded verbatim here.
DO $driver_check$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM schema_migrations
                 WHERE version='037_article_source_lifecycle') THEN
    RAISE EXCEPTION 'expected migration marker missing';
  END IF;
END
$driver_check$;
\echo AUTODATA_APPLIED 037_article_source_lifecycle.sql
\endif
```

The body comment specifies byte-preserving embedding of an existing file, not new replacement DDL. Actual generator reads the original file, not this illustration.

## Entrypoint ownership and compatibility

Create `scripts/dev/migrate_sql.sh` and `workers/ingestion-python/tests/test_article_lifecycle_migrations.py`.

Modify `scripts/dev/migrate.py`: preserve address wait, CLI flags, PG credentials/environment, and `psql_command` native-vs-Docker choice. Generate driver once with shared script `--emit`; invoke existing native psql or `docker compose exec -T postgres psql` once with `-X --set ON_ERROR_STOP=1 --file -`, passing complete driver on stdin. Docker fallback requires no source mount or Python in postgres. Preserve public `apply_migrations(root,address=None)->list[str]` and meaningful failure propagation.

Modify `infra/compose/compose.yaml` migration-runner command to `['sh','scripts/dev/migrate_sql.sh']` in its existing `/workspace` bind mount. Modify `docker-compose.base44.yml` to the same command relative to its working directory. Retain image, PG environment, mounts, dependencies and service-completed gates. CI commands remain unchanged and exercise this same service.

Modify `workers/ingestion-python/tests/lifecycle_support.py`: `fresh_database(through=None)` applies an ordered fixture chain by generating a driver from the requested prefix into fixture-owned temporary files and running one psql session against the isolated database. Preserve repository safety guard and database name restriction. `apply_migration(repo,number)` can use a one-file fixture-only raw execution helper for intentional failure/original-file tests; label it as raw SQL testing, not the operational migration path. Do not make the normal fixture chain a separate duplicate version-skip implementation. The existing `infra/compose/article-lifecycle-test.Dockerfile` is `python:3.14-slim` and installs poppler/tesseract but no psql. Modify its existing apt-get line to add `postgresql-client`; preserve the base image and remaining dependencies. Include this exact path in the coordinator checkpoint and builder allowlist.

Modify `scripts/dev/test_migrations.py` for shell generation/marker manifest/safe argument and failure propagation regressions; source-level assertions alone are not DB acceptance.

Modify `infra/compose/article-lifecycle-test.Dockerfile` only to add the psql client package needed by shared-driver fixture execution.

Create `docs/operations/migration-runner.md`: describe version trust,033 one-time adoption, lock/key, private fixtures and recovery. Inventory Kubernetes `infra/k8s/base.yaml` external `ghcr.io/lucronn/autodata-migration-runner:dev` `/app/bin/migrate`: source/build is absent here. Do not change its image or certify behavior by guess. A Kubernetes release is BLOCKED until image provenance demonstrates delegation to this shared driver against the same migration artifact and passes the restart matrix. Repository repair itself requires no Kubernetes deployment/image publication.

No migration SQL, API, worker business behavior, policy, CI test command or schema contract changes are authorized.

## Concrete todo

- [ ] Synchronize Issue #186, Project #8, lifecycle/orchestration plans and verification record with the runner repair and explicit markerless-033 adoption policy; commit the checkpoint and pass exact-base preflight.
- [ ] Add real PostgreSQL regressions reproducing repeated037 failure and031 constraint regression, plus fresh/twice, populated036 upgrade, legacy033 adoption, unknown/gapped ledger rejection, concurrency and rollback.
- [ ] Implement one POSIX-shell/psql driver generator with one session advisory lock, version-aware conditional execution, transactional old migrations and exact marker verification; preserve SQL001–038 byte-for-byte.
- [ ] Delegate production Compose, Base44, native/container migrate.py and lifecycle fixture chain execution to the shared driver; document the external Kubernetes image certification boundary.
- [ ] Run focused and full ingestion/migration utility suites, exercise every repository entrypoint twice with private PostgreSQL fixtures and retain exact-SHA logs/schema/data comparisons.
- [ ] Obtain independent exact-SHA review, record the actual GitHub verification result, synchronize tracking and re-pin dependent release tasks before continuation.

## Implementation steps and evidence

- [ ] Coordinator reviews033 adoption effects, synchronizes external tracking and canonical docs, commits this plan/task, pins the new SHA and passes `scripts/autonomy/pre_implementation.py`. The inspected SHA is evidence, not the future authorization checkpoint.
- [ ] Write failing real PostgreSQL regressions: original full chain twice fails037; original chain replay after a `content_partial` catalog row fails031. Capture pre-repair output before implementation.
- [ ] Add driver generator/manifest tests and implement the fixed contract above. Run `sh -n scripts/dev/migrate_sql.sh` and verify default/emit drivers are identical.
- [ ] Wire all repository entrypoints and fixture chain to the generator. Add `postgresql-client` to the existing apt-get package list in `infra/compose/article-lifecycle-test.Dockerfile`. No new production runtime image.
- [ ] Run the matrix below in newly owned private PG17/pgvector projects; retain emitted driver, exact SHA, commands, exits, client/server versions and safe logs. Do not touch coordinator project `autodata-migration-repro`.
- [ ] Run focused schema/migration tests, then full ingestion and utility suites. Confirm historical SQL diff is empty, expanded constraint and read view definitions match before/after replay, and no existing row/version timestamp changes except approved first033 replay.
- [ ] Independent reviewer examines exact candidate SHA, reruns matrix, checks scope and legacy marker honesty. Only afterward integrate, run actual GitHub exact-head verification and update the verification record/Issue/Project. Re-pin dependent release tasks. No deployment.

## Required test matrix

| Case | Setup/action | Required result |
|---|---|---|
| Fresh/twice | Empty private DB; shared driver001–038 twice | Both exit0;38 markers including033; second run applies zero files; all timestamps and schema definitions identical |
| Populated lifecycle restart | Candidate schema with content_partial catalog row, descriptors, sources, jobs and published canonical record; full runner repeat | All skipped; content_partial constraint remains; complete immutable row values/pointers unchanged |
| Genuine036 upgrade | Original chain through036, legacy033 missing marker; seed legacy job statuses before036 import | Only033,037,038 pending; legacy UUID/idempotency/status/retry/snapshot invariants retained;033 effects explicitly match existing SQL |
| Original037/038 adoption | DB from original full chain; shared driver twice | Existing037/038 and031 skip; only first033 replays once; second run no-op |
| Markerless033 policy | Legacy table/data exists but033 marker absent; matching malformed review rows and control rows | Original033 executes once transactionally and only its documented rows change; marker inserted; next run changes nothing |
| Initial ledger absent | Truly empty DB vs known app table present without ledger | Empty bootstrap works; untracked application baseline fails closed |
| Bad manifest/ledger | Duplicate number, unsafe name, unknown version, same numeric version with wrong stem, missing032 below036 | Fail before pending DDL; missing033 alone is accepted by explicit adoption policy |
| Two full runners | Two independent shared drivers target same fresh DB and then same036 DB | One holds session lock; other waits; both succeed; each migration executes once; no duplicate objects |
|001–035 transaction rollback | Test-only migration fixture with two DDL statements then injected error before marker | Both DDL and marker absent after failure; prior commits intact; fixed fixture retry succeeds |
|036–038 rollback/retry | Test-only copied file with failure before existing marker; original files untouched | Existing BEGIN/body/marker atomicity retained; failed version objects absent; retry succeeds |
| Connection loss | Test-only migration pauses after DDL; terminate its fixture backend | Active transaction rolls back; advisory lock releases; second runner completes from last committed marker |
| Restart between files | Stop driver after committed037 before038, start normal driver |037 skipped;038 applied exactly once |
| Every repository path | Shared shell default, native migrate.py, Docker fallback migrate.py, production Compose, Base44, fixture driver | Same version skip behavior and private test target; no alternate unguarded loop |
| Exact actual CI | Workflow unchanged at integrated head | Ingestion and live Compose fast lane pass; isolated-DB skips never represented as DB acceptance |

Schema comparison must include columns, constraint/index/function/trigger definitions and `catalog_article_current` view, not merely object names/counts. Data comparison includes complete immutable records, old version applied_at and meaningful legacy invariants. Fresh and upgraded final schema definitions must match; data effects of033 are tracked separately as explicit adoption behavior.

Existing real PG fixture command (after adding postgresql-client in its existing image):

```sh
mkdir -p /tmp/autodata-migration-replay-verify
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-migration-replay-verify \
docker compose -p autodata-migration-replay-verify \
  -f infra/compose/compose.article-lifecycle-test.yaml up -d --wait postgres

AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-migration-replay-verify \
docker compose -p autodata-migration-replay-verify \
  -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner \
  python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/migration-replay-focused.xml \
  workers/ingestion-python/tests/test_article_lifecycle_migrations.py \
  workers/ingestion-python/tests/test_article_lifecycle_schema.py

python3 -m unittest discover -s scripts/dev -p test_migrations.py
```

Full ingestion uses the same isolated test runner with `workers/ingestion-python/tests`. Retain full logs and do not assert success from skipped PostgreSQL cases. Stop only newly owned fixture projects after retaining evidence.

## Gate and handoff

Coordinator checkpoint files: this plan at `docs/superpowers/plans/2026-11-03-lifecycle-migration-replay.md`; task at `docs/agents/tasks/2026-11-03-production-release/migration-replay.json`; updated canonical lifecycle plan, orchestration plan and verification record. Retain the existing037/038 freeze and add this runner prerequisite; do not replace it with a migration-edit exception.

The companion task deliberately has `status: blocked` until verified R2 integration because both lanes own lifecycle_support.py. R3 then waits for this repair and its required fixture command. Companion blocked JSON drafts deliberately have `status: blocked`. Machine preflight at inspected SHA must reject them for non-synchronized status and absent plan. Coordinator performs actual synchronization, commits the checkpoint, sets a fresh synchronized record and validates at that committed base before builder dispatch. No plan-only agent may silently do this status transition.

This repair does not supply retrospective checksum proof, Kubernetes image certification, R2/R3 completion or production release authority.
