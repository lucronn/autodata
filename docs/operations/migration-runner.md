# PostgreSQL migration execution and adoption

Run `sh scripts/dev/migrate_sql.sh` with the target's existing PG environment.
Production Compose, Base44, native/container `migrate.py`, and normal lifecycle
fixture chains all delegate to this driver. Python retains its address wait,
CLI flags and native-psql/Docker fallback selection. Its completed list includes
only actual applications; generator and psql failures propagate with stderr.

`--emit` produces the complete embedded-SQL driver without DB access. Stream it
to `psql -X --set ON_ERROR_STOP=1 --file -` inside a container without source.
Default execution uses a private temporary driver file removed on exit. Use a
supported PostgreSQL client with psql conditionals. No Python is required by the
shell driver or the production PostgreSQL image.

The default manifest requires exactly the reviewed 001–039 filenames. Missing,
renamed, duplicate-numbered, additional, unsafe or symlinked files fail before
SQL output or DB access. The repository's empty `.gitkeep` is allowed.
`--migrations-dir /absolute/path` accepts only a contiguous canonical 001..N
prefix for private fixtures; it is not an adoption override. Backslashes are
rejected to prevent psql metacommands, including inline commands. SQL bodies are
embedded verbatim, without includes or interpolation. Future migrations require
reviewed manifest and transaction-contract updates; adding a file is insufficient.

One psql session holds reserved advisory lock `(186,3738)` across validation and
the complete chain, using read committed isolation and a 60-second lock timeout.
Cooperating runners serialize on this key. Ordinary application writers do not
automatically acquire the migration lock.

Before pending application DDL, the runner validates the entire existing ledger:
version primary key, timestamp shape/default, exact known versions and a committed
prefix with only the historical 033 gap allowed. Unknown versions fail, including
when a checkout predates its DB. Missing or empty ledgers permit bootstrap only
without known application tables. Untracked application databases need a
separately reviewed adoption path. A recorded 001 plus partial, unmarked next
legacy migration remains retryable using the original replay-oriented SQL.

Committed version markers are trusted and skipped, preserving `applied_at`.
This is marker-only provenance: it supplies no historical checksum attestation
and cannot detect edits to already-applied SQL. Historical 001–038 remain
immutable. Runner transactions wrap 001–035, verify the expected marker, and
commit. 033's missing marker is inserted in that transaction. 036–039 retain their
original complete BEGIN/body/marker/COMMIT blocks without nested transactions.
Output records `AUTODATA_APPLIED <filename>` or `AUTODATA_SKIPPED <filename>`.

Marker-based skipping prevents future replay; it does not repair schema drift
from an earlier failed old runner. In particular, the old full loop can commit 031's
narrower status constraint and then fail 037 while 037/038 markers remain. Such a
database requires a separately reviewed restore or schema-reconciliation path
before release acceptance. Do not treat intact markers as retrospective schema
attestation or claim that this runner repairs that prior damage.

## Explicit one-time 033 adoption

Legacy 033 creates hydration-scope objects without recording its version. On
first adoption, execute unchanged 033 once and atomically insert its marker.
Do not infer completion from 034/036 or silently stamp 033.

This replay rejects identity bases and linked configurations whose make/model
are Silverado/1500, case-insensitively, and updates their `updated_at` timestamps.
Those documented effects can occur even if an older runner executed 033 before.
Control rows and existing version timestamps remain unchanged. Later runs skip 033.
Coordinator acceptance covers implementation and isolated verification, not
production migration. Account for reviewer-state/timestamp effects in the
production deployment runbook. If unacceptable for a target DB, stop adoption
and design a separately reviewed explicit schema/data attestation path.

## Recovery and private verification

A SQL error stops the driver. Connection closure rolls back the active migration
and releases the session lock; previous commits remain. Correct the cause and
restart the reviewed driver. Never delete markers, drop application objects,
catch duplicate-object errors broadly, or fabricate historical markers to force
progress. Earlier partial legacy execution cannot be retrospectively certified
as atomic. Inspect the error, ledger and exact migration artifact before recovery.

Use a unique owned project with `infra/compose/compose.article-lifecycle-test.yaml`
and a private `AUTODATA_LIFECYCLE_ARTIFACT_DIR`. Its internal network has no host
ports and source is mounted read-only. Never mount `/run/base44/app.env`, use
live providers/credentials or reuse unrelated fixture projects. For example:

```sh
mkdir -p /tmp/autodata-migration-verify
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-migration-verify \
  docker compose -p autodata-migration-verify \
  -f infra/compose/compose.article-lifecycle-test.yaml up -d --wait postgres nats minio
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-migration-verify \
  docker compose -p autodata-migration-verify \
  -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner \
  python -m pytest -q -p no:cacheprovider \
  workers/ingestion-python/tests/test_article_lifecycle_migrations.py \
  workers/ingestion-python/tests/test_article_lifecycle_schema.py
```

Retain fresh/twice, populated lifecycle restart, genuine 036 upgrade,033 data
adoption, invalid manifest/ledger, concurrency, rollback, connection-loss and
restart evidence. Compare complete schema definitions and immutable records,
not just object names/counts. Test support's raw `apply_migration` intentionally
executes original SQL for upgrade/failure tests; normal fixture chains use this
shared operational driver.

## Kubernetes certification boundary

`infra/k8s/base.yaml` invokes `/app/bin/migrate` from external image
`ghcr.io/lucronn/autodata-migration-runner:dev`. Its source/build is absent here.
This repair does not certify it. Kubernetes release is blocked until image
provenance demonstrates delegation to this shared driver against the same
migration artifact and the image passes the restart matrix. No Kubernetes image
change, publication or deployment is authorized by this repair.


Migration 039 adds customer_accounts and auth_sessions. The same shared driver,
advisory lock and explicit self-contained transaction checks apply. Both tables
are known application tables: an absent/empty ledger cannot adopt them. The
project+UID account key and personal organization are durable; sessions persist
only 32-byte SHA256 token hashes, original Firebase authentication time, creation,
absolute expiry (at most 12 hours), and revocation. An038 database remains038 when
Firebase startup refuses it; startup never migrates. Apply the driver first.

Required private fixture coverage includes fresh039/twice, populated038→039 with
unchanged prior ledger timestamps/data, populated account/session restart,
039 rollback/retry and concurrent full runners. Historical 001–038 SQL remains
unchanged. The Kubernetes migration image is an external prerequisite: build and
verify an image carrying this exact 039 manifest before deployment; the manifest
alone does not certify that external image.
