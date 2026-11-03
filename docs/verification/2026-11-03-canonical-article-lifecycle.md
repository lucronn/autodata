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
