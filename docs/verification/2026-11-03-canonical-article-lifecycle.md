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

## R2 implementation and fixture verification

Authorized base: `262d180dec9b0411fa914393f4d8900ce23e466b`. Implementation is
isolated on `codex/r2-rewrite-lifecycle`; migrations 037/038 remain unchanged.
R2 adds ordered conservative rewrites, persisted attempts/results/validation,
atomic publication/outbox, the dedicated worker, SQL-only ensure scheduling,
reviewed offline legacy mapping and generated catalog contracts. Independent
exact-commit review and coordinator integration remain required.

The isolated project is `autodata-r2-lifecycle`; artifacts are retained under
`/tmp/autodata-r2-lifecycle-artifacts`. It uses private PostgreSQL, S3 and NATS
volumes, an internal network, no host ports, read-only code and fixture-only
credentials. Connector/model HTTP servers bind loopback inside the test runner.
No real model/bank requests or `/run/base44/app.env` are used.

Process acceptance launches two actual `scripts/dev/article_worker.py` CLI
processes. Injected local test barriers cover death before source commit, after
source commit/dispatch/result, before/inside publication and after a real NATS
acknowledgment. A separate death after an actual model HTTP request proves
ambiguity and bounded redelivery. SQL backend termination proves publication
rollback. Tests also cover twenty competing ensures, provider separation,
changed and unchanged-source refresh, three exhausted attempts with unchanged
owner/key/budget, warm 100-read/ensure restart, real SDK failure/5-second timeout,
optional unavailable image placement, broker outage and final delivery expiry.
Deterministic expiry-boundary tests change database expiry immediately before
actual reclaim/final sweep and prove renewed leases survive.

The smoke command runs mandatory schema/source/job/transform/publication/runtime
and integration acceptance. It fails on skipped tests or unavailable fixture
services. JUnit records exact test IDs; runtime JSON records contain measured
call counts, durable jobs/attempts/revisions/event keys and expected/measured
zero duplicate-event/unvalidated-publication invariants. The JSON manifest
records command argv, timestamps, status, candidate provenance and artifact
SHA-256 values. The read-only runner has no usable worktree Git metadata, so
pass the host's exact SHA explicitly; the manifest labels this provenance.

```sh
export AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-r2-lifecycle-artifacts
candidate_sha=$(git rev-parse HEAD)
docker compose -p autodata-r2-lifecycle \
  -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner \
  python scripts/dev/article_lifecycle_smoke.py --mode fixture \
  --candidate-sha "$candidate_sha" --output /artifacts/lifecycle-smoke.json
```

Runtime handoff: `article_lifecycle.run_article_worker_once` and
`run_article_job`; `worker.ArticleRepository` / `ArticleObjectStore`;
`catalog_service._ensure_lifecycle_catalog`; fixture
`lifecycle_support.LifecycleRuntime` (`ensure`, `read_current`, `refresh`,
`start_workers`, `pause`, `kill_worker`, `expire_lease`, `counters`). R3 owns
public Go integration and its combined Go/Python fixture harness. R6 owns
production worker/relay deployment and authenticated canaries. Fixture success does not establish production readiness.

Builder verification before the final exact-SHA acceptance run: full ingestion,
backfill/smoke utilities, enrichment outbox and contract tests passed **732 tests
and 25 subtests** in 191.73 seconds (`r2-final.xml`, `r2-final.log`). Subsequent
focused checks passed 20 runtime/HTTP/legacy tests, 14 publication/read-contract
tests, 10 contract tests and all 15 migration utility tests. The final candidate
is recorded by the smoke manifest; these earlier logs are retained separately
and are not substituted for exact-candidate verification. Scope and whitespace
checks pass. Generated bindings match source and Go contract tests pass.

The `9769105` checkpoint was superseded after independent review found missing
year/configuration applicability facts, misleading aggregate catalog completion
and a cumulative scheduling deadline defect. Its exact builder run passed 742
tests plus 25 subtests (716 ingestion, 6 backfill, 3 smoke utilities, 7 outbox,
10 contracts), but those passing results did not cover the findings. New real
worker/DB regressions failed before the repair: 13 applicability/aggregation
failures and 2 deadline failures. Corrections load normalized year and actual
configuration facts, preserve partial/terminal provider outcomes, and fence
connections/statements/commit under one total budget. The two-bank lock test
also verifies rollback of the first bank's newly inserted job; a delayed-connect
test verifies no scheduling after expiry. Final smoke acceptance includes these
catalog/HTTP regressions and the bounded document/Mercury/backfill/contract suites.

The builder's repaired runtime/catalog/HTTP/publication/worker focused suite
passed **89 tests** in 134.76 seconds (`review-repairs-focused.xml` and log).
The final exact-candidate full run and smoke manifest remain the authoritative
acceptance records; independent review must verify the repaired commit.

The `8be01c9` checkpoint passed 761 tests plus 25 subtests in 234.29
seconds with a clean immutable checkout, but independent review demonstrated a
late-COMMIT race after the last client deadline check. The retained barrier
regression failed with two jobs committed after HTTP 503 (`late-commit-red.xml`).
Scheduling now sets PostgreSQL 17 transaction and idle-transaction deadlines
from the remaining total budget, so server rollback survives a client pause
between the pre-commit check and COMMIT. Query cancellation remains a prompt
cleanup aid; the server deadline revokes commit authority. Final acceptance
records must name the subsequent corrected candidate.
