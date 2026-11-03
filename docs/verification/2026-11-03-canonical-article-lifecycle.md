# Canonical article lifecycle verification

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8  
Plan: [canonical article lifecycle](../superpowers/plans/2026-11-03-canonical-article-lifecycle.md)

## R1 intake foundation: independently verified

Authorized implementation base: `4a8a0d24a8555911b567b8691e6ba3f4a0477fa8`.
Final builder candidate: `330c29c0a1b2b7d43745dd9b2ba93cf1f9055e09`.
Integration commit: `c3b7a46d1233a1af8c0f0cba19a2f169d5a9a4b4`.

Independent exact-SHA schema/source/reliability review approved tasks 1–4 with
no remaining P1/P2 findings. The 23-file allowed scope and whitespace checks
passed. Migrations 037/038 are the only new schema changes; historical migrations
remain unchanged. The isolated real PostgreSQL checks cover clean and upgrade
migration, legacy row preservation, immutable source ownership, concurrent
ensures/claims, fencing, expiry and exhausted-transform reuse.

The coordinator ran the full ingestion suite in a separate clean verification
worktree at the candidate, then on the integrated branch:

```sh
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-r1-independent-2755244 \
docker compose -p autodata-r1-verify \
  -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner \
  python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/r1-pytest-integrated-c3b7.xml workers/ingestion-python/tests
```

Results: **644 tests and 25 subtests passed** at the candidate (83.21 seconds)
and integration (83.66 seconds). The migration utility suite passed all 15 tests
at the earlier schema candidate; those migration and utility bytes are unchanged.
Final independent capture review also passed 48 focused capture tests and the
real PostgreSQL legacy-snapshot-reference regression.

Evidence is retained under `/tmp/autodata-r1-independent-2755244`: final candidate
`r1-pytest-provenance-remediation.xml` / `pytest-provenance-remediation.log`, and
integration `r1-pytest-integrated-c3b7.xml` / `pytest-integrated-c3b7.log`.
Earlier failing/corrected candidates remain separate retained records. The
Compose project has an internal network, private fixture volumes, no host ports,
read-only code, and no production or source-bank credentials.

Both banks retain independent opaque identities and evidence. Capture preserves
ordered tables and media, marks unavailable assets honestly, handles real SDK
storage exceptions, and maps reused source bytes to actual persisted snapshot
UUIDs. Source/configuration selectors do not widen ambiguous scope.

## Remaining lifecycle and release work

R2 tasks 5–8 are pending: model-attempt accounting and validation, worker/runtime
integration, atomic canonical publication/outbox, and full process/S3/NATS
recovery acceptance. The real S3 adapter must set connect/read timeouts and
zero automatic retries; bounded caller waits alone do not stop upload threads.
Warm-read, source-to-canonical API/browser behavior and authenticated real-bank
staging acceptance are later workstreams. This record certifies the R1 fixture
scope only and does not claim production readiness.

## CI dependency setup follow-up

GitHub runs [41617122268](https://github.com/lucronn/autodata/actions/runs/41617122268)
and [41617440987](https://github.com/lucronn/autodata/actions/runs/41617440987)
failed ingestion collection because their pytest-only setup omitted declared
runtime dependencies. A clean Python 3.12 reproduction retained under
`/tmp/autodata-ci-dependency-repro` confirms exit 2 before dependency setup and
**594 passed, 50 skipped, 25 subtests passed** in 35.13 seconds after installing
the unchanged pyproject dependencies. Those 50 cases require the separately
verified isolated PostgreSQL runner; skips are not database acceptance.
The [reviewed one-file CI repair](../superpowers/plans/2026-11-03-ingestion-ci-dependencies.md)
preserves all test commands and release gates. Actual GitHub verification
remains failing until that repair and a successful exact-head run are recorded.

The one-file dependency setup repair passed independent exact-SHA review and a
fresh exact-step Python3.12 replay at `9e07beb286f6f67e5a5854c46ebc01cf82318a46`
(594 passed, 50 isolated-DB skips, 25 subtests). It is integrated unchanged.
Builder replay artifacts are `/tmp/autodata-ci-dependency-builder/`.
Actual [CI run41618670467](https://github.com/lucronn/autodata/actions/runs/41618670467)
passed ingestion tests and then failed live Compose smoke. A second execution
of the repository migration loop fails on migration037 because its unique index
already exists. The coordinator reproduced the exact loop against a fresh
isolated PostgreSQL database: first run exit0, second run exit3. Logs are retained
at `/tmp/autodata-migration-repro/{run1.log,run2.log,result.json}`. This is a
separate restart defect in the two new unreleased migrations; the reviewed
dependency repair worked. A separately reviewed replay plan and fresh gate are
required before changing those frozen migrations. CI and release remain failing.

Further inspection found031 replays a constraint that predates content_partial,
and033 has no ledger marker. The [runner repair plan](../superpowers/plans/2026-11-03-lifecycle-migration-replay.md)
therefore keeps all migration SQL immutable and centralizes applied-version
checks and locking. The documented one-time033 adoption is explicitly accepted
for isolated implementation acceptance; no production database is targeted.
The task remains dependency-blocked until verified R2 integration and a fresh
committed synchronized record. This supersedes the initially considered
037/038-only replay guard, which would not fix the031 regression.
