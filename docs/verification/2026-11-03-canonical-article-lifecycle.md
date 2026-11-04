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
R2 is now verified below; the runner task is synchronized for its fresh
committed checkpoint and required preflight. This supersedes the initially considered
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

## Final R2 exact-candidate approval and integration

Candidate: `dba2d96170db5694052bd36dc7fca645fdf0a51d`.
Integration: `9fd3f9142ee22c47810765130cbc36d6284994a3`.
Independent review approves R2 scope with no remaining P1/P2 findings. The final
40-test review reruns the original late-COMMIT race and affected scheduling,
applicability and catalog-state tests; the earlier135-test review covers unchanged
behavior. PostgreSQL17 server transaction/idle deadlines roll back work even
when the client pauses after its last precommit check. Superseded failing
candidates remain retained and are not release evidence.

The builder and coordinator independently ran the exact committed candidate:
**762 tests plus25 subtests**, zero skips/failures/errors (232.90s and235.97s).
The same combined suite on the integration passed **762 tests plus25 subtests**
in 228.700 seconds, with zero skips/failures/errors. All37 R2 implementation,
test and contract files are byte-identical to the approved candidate; only the
verification document needed merge resolution, retaining both histories.
Go API/contract tests and15 migration utility tests also pass.

Mandatory fixture smoke at the exact candidate passed **267 tests in179.17s**,
zero skipped/error/failed cases, with **35 actual runtime records** and all
expected/measured invariants matching. Author evidence is retained under
`/tmp/autodata-r2-lifecycle-artifacts`, especially `r2-exact-dba2d96-run.json`,
`smoke-exact-dba2d96.json` and `smoke-exact-dba2d96-host.json`. Coordinator
candidate artifacts are under `/tmp/autodata-r2-independent-dba2d96`; integration
artifacts are under `/tmp/autodata-r2-integrated-9fd3f91`. Independent final review
is `/tmp/autodata-r2-review-core/dba2d96-deadline-review.xml`.

This completes R2 fixture implementation scope. The next shared migration-runner
repair is synchronized for committed-base preflight; it does not change historical
SQL. R3 public Go source fallback, R5 identity, R4 browser behavior and R6 live
acceptance/release gates remain outstanding. No production readiness or deployment
is claimed.

## Clean CI development discovery follow-up

[Run41625088678](https://github.com/lucronn/autodata/actions/runs/41625088678) at `31d1582d0b805f870e6fa42f9c812f7396d11c82` passed ingestion, then failed development unittest discovery importing `test_backfill_article_lifecycle`: `lifecycle_support` is absent from that command's import path. Actual failure log is `/tmp/autodata-ci-31d1582-failed.log`. The [one-file test discovery plan](../superpowers/plans/2026-11-03-dev-test-discovery.md) preserves all tests and workflow commands; its fresh gate precedes the import-path-only correction, clean Python3.12 reproduction, six real PG backfill cases and independent review. Migration replay remains a separate pending CI prerequisite.

## Migration replay and clean discovery integration

Migration candidate `e401a54342ec0f201728f95cdfc1ea32841d517c` passed independent
review with no findings and is integrated at
`f264dae2fb222b7a7c90e4ab79e2b04aa8589ccc`. The nine authorized files are
byte-identical after integration; all historical SQL001–038 remain unchanged.
The builder's exact candidate passed 760 ingestion tests plus 25 subtests,
31 focused migration tests, 123 developer tests plus 9 subtests and 23 utility
tests, with no skips. Independent review and the coordinator each passed
54 migration/schema/utility tests plus 7 subtests (26.07s and 25.731s).
All repository entrypoints applied 38 versions initially and none on repeat.
Evidence is retained in `/tmp/autodata-migration-builder/final-evidence.json`,
`/tmp/autodata-migration-review/review-summary.json` and
`/tmp/autodata-migration-independent-e401a54/verification.json`.

The one-file development discovery candidate
`c76f7a2afd786052121ed14d5ed51104cecea2c9` passed independent review with no
findings and is integrated unchanged at
`1d07ce28b5cc4cb7fb95ab41db8c178eff0d3c4d`. Clean Python 3.12 discovery
reproduced the base import failure, then passed 90 unittest cases without skips;
the removed failed-import placeholder explains the former count of 91.
Both builder and reviewer separately passed all six real PostgreSQL backfill
cases. Original test bodies, workflow commands and assertions are unchanged.
Evidence is `/tmp/autodata-dev-discovery-builder-evidence/provenance.json` and
`/tmp/autodata-dev-discovery-review/review-summary.json`.

Combined integration at `1d07ce28b5cc4cb7fb95ab41db8c178eff0d3c4d` passed
**809 tests plus 32 subtests in 242.13 seconds**, zero skips/failures/errors.
The clean candidate retained all ten approved repair files byte-for-byte.
Evidence is `/tmp/autodata-migration-integrated-1d07ce2/verification.json`;
the coordinator's private fixture project was removed after evidence retention.
Two invalid coordinator command preparations (a nonexistent path and an
unsupported Compose flag) ran no tests; their logs remain separate from the
successful invocation. No passing result is inferred from those failures.

Actual [GitHub run 41627289946](https://github.com/lucronn/autodata/actions/runs/41627289946)
**passed** at that integration, including ingestion, development discovery and
live Compose fast-lane smoke. Full workflow metadata/logs are retained at
`/tmp/autodata-ci-1d07ce2-result.json` and `/tmp/autodata-ci-1d07ce2-complete.log`.
This verifies the migration and discovery dependency. R3's independently
reviewed post-migration binding refinement is synchronized for a fresh committed
checkpoint and machine preflight. Its32-path scope is unchanged.

The runner prevents future replay damage but cannot repair an already corrupted
legacy031 constraint; that needs separately reviewed reconciliation. The
external Kubernetes migration image and production migration remain uncertified.


## Paid index readiness correction: historical planned verification (2026-11-04)

Plan: [workshop-index-readiness](../superpowers/plans/2026-11-04-workshop-index-readiness.md); record: `docs/agents/records/2026-11-04-workshop-index-readiness.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-index-readiness.json`. Issue186 / Project8 refs and concrete todo are in the plan. Inspected application candidate: `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. Status: **synchronized planning checkpoint pending committed-gate review**, with no implementation or test-pass claim for this correction.

Acceptance must bind the full implementation SHA to Node native workshop tests, Go API tests, catalog contract checks, scope/whitespace checks and required isolated PostgreSQL execution. The new current-job progress matrix must execute as a plain helper/table loop within the existing cold R3 Go root for both providers, without `t.Run` or additional Go run/pass events, preserving the unchanged Python eight-case inventory and restoring SQL fixture state. Retain the existing single-root Go JSON event contract and named case/full expected-observed tuple receipts in `go-measurement.json` and logs for both providers, plus non-skipped outcomes; ordinary Go suite skips cannot establish the SQL fix. HTTP tests must exercise real paid Handler grants, no-store descriptor responses and zero ingestion calls; browser tests must execute actual loadArticles with real readCollection and prove no early ready, bounded polling, partial links, desired article and navigation/abort behavior. A separate actual-status/DOM regression seeds ready text for vehicle A and proves loadArticles clears the completion live region immediately when vehicle B starts and keeps it clear for pending or terminal B; complete:false alone does not clear that region.

Use only the existing coordinator-owned R3 fixture runner, isolated fresh databases and synthetic HTTP services described by the plan. Record missing runtime/fixture execution as blocked. Preserve all earlier lifecycle/PG/provider/release evidence; this correction does not upgrade its status or authorize release/deployment/payment/provider traffic.


### Live planning synchronization receipt (2026-11-04)

The revised technical draft received independent PASS before synchronization. Fresh read-only API readback at `2026-11-04T15:02:40.245180+00:00` verified [Issue186 detail](https://github.com/lucronn/autodata/issues/186#issuecomment-6634018122) (body SHA-256 `c1597703501cec2abb5055e120c7d7bce37692bd4c95083045d810aff5d1931d`, 2794 bytes), the complete current Issue body (SHA-256 `927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25`) and all 136 comments. Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` has Source-or-dependency text length 957 / SHA-256 `51f2da943694be8f11e86e2463fe769f92f3a1f99b7151329f1eb175ba20b510` and Status `In Progress`; its full text matches the coordinator’s post-update readback. The existing source index and predecessor references are preserved; coordinator readback confirms other fields unchanged.

Full Issue/comments/Project readback and hashes are retained at `/home/corp/autodata-evidence/index-readiness-gate-checkpoint-20261104/`; before/after Project text is retained at `/home/corp/autodata-evidence/index-readiness-project-readback.json`. The canonical record/task are now synchronized against the exact matching goal, references and six todo items. No GitHub write was performed by this architect. The next implementation base is this docs-only checkpoint’s full committed SHA, verified by canonical preflight after commit; independent committed-gate review and fresh coordinator dispatch remain required. No implementation, runtime/provider/payment evidence, merge, activation or deployment is claimed.


## Reviewed code and isolated acceptance completion (2026-11-04; tracking synchronized)

Implementation is `23a2f3b2e12c0b14b1d4989ab13a075cf1bee084` in [draft PR211](https://github.com/lucronn/autodata/pull/211), based on synchronized gate `d60121c41a680d699da575d9883f9ecf45b0fb72`. Exact-base machine preflight and independent gate review passed before implementation. The diff touches exactly the six approved production/test paths; workers, schema, commerce, contracts, payment, deployment and `catalog.mjs` were unchanged. Current-job retryability and terminal aggregation, incomplete HTTP hydration, explicit complete-only ready copy and pre-await completion-live-region clearing are implemented. Paid GET remains read-only/descriptor-only; partial links, saved articles, bounded polling and navigation/abort behavior remain covered.

Exact-code local verification: `go test ./...` from `apps/api-go` passed 155 root tests with 12 ordinary fixture skips; `node --test apps/api-go/workshop-client.test.mjs` passed 62/62 with 0 skips; `python -m unittest discover -s scripts/contracts -p 'test_*.py'` passed 19/19; six-path scope and `git diff --check` passed. Raw exact-code receipt: `/home/corp/autodata-evidence/index-readiness-unit-evidence/verification-exact-23a2f3b.json`. Independent exact-code review **PASS** was provided by the coordinator; that code reviewer did **not** independently rerun Go.

The retained runtime sequence is deliberately separate:

- RED `402fbb2b348df54d9b7dbd55496f6dcf73e3c32f`, run `index-readiness-red-9ddd89c1ed01`: all 42 tuples executed, with 10 intended readiness mismatches per provider; two cold cases failed and six other lifecycle cases passed, with 0 skips/timeouts. The original failed receipt remains intact; the short/full-ID cleanup mismatch was recovered with a separate exact-owner receipt.
- First GREEN at the final code SHA, run `index-readiness-green-0407301b80b0`: six cases and all 42 tuples passed; two warm fixtures failed before Go on SeaweedFS disk capacity (2.15% free). This attempt remains **failed**, with its raw receipt and successful owned cleanup preserved.
- Final fresh GREEN at the same code SHA, run `index-readiness-green-68fd8e922a26`: **8/8 non-skipped Python/Go cases and 42/42 tuples passed** in 76.36s; supervisor exit 0/status passed/failures empty. The run used a clean remote-free clone, exact mounted-input hashes, eight isolated PostgreSQL databases, real fixture S3/NATS/HTTP probes, source/job/projection/counter measurements, and successful bounded owned cleanup. It retained backend-final inspect/log, removed only its build backend before fixtures, and used a private test-only Compose override binding only SeaweedFS `/data` to a fresh owned `/home` directory with at least 12 GiB headroom; the actual mount, config-only delta and cleanup interpreter were verified. No application source changed between GREEN attempts.

Final receipt: `/home/corp/autodata-evidence/index-readiness-green-68fd8e922a26/artifacts/acceptance-result.json`, SHA-256 `a677ebea4d8234d222c2d71065b0bf9337b2fbef0e51ed23f2b0eef5a967209a`. Independent raw-evidence audit **PASS**: `/home/corp/autodata-evidence/index-readiness-green-independent-audit-68fd8e922a26.json`, SHA-256 `9e8bb8769123928682401fab64f899924b7d168775dd317d09031eb2843bd61b`. Storage cleanup receipt SHA-256: `355598ffef4fcc101245fbe6bc72169a1e261b6e2db23dd1cf68d78a60fd9a44`. Final supervisor SHA-256: `e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9`.

Completion tracking is synchronized from the coordinator's serialized readback: [Issue186 completion detail](https://github.com/lucronn/autodata/issues/186#issuecomment-6634845885), body SHA-256 `9acb67f385d4f0c038afa12917c76d5799de7b9068e70cd4f869158bd548294b`; final Project8 Source SHA-256 `9c99e5508b2cf825dd8919a125962cb3a4c12df741df53722740de57f535e9b4` (476 bytes), with other Project fields unchanged. The exact predecessor Source SHA-256 `46b8e75e2a62481d106c77c1b6677dd8c1f865ef53b5377c0d31950280c68a7b`, its full text and all 138 predecessor comment hashes remain preserved in the linked detail and durable `/home/corp/autodata-evidence/index-readiness-completion-tracking-before.json` and `index-readiness-completion-tracking-readback.json`; the wording correction is retained in `index-readiness-completion-project-correction.json`. The earlier planning receipt remains historical evidence. No GitHub write was performed by this documentation agent. The full-SHA preflight receipt for this docs-only checkpoint is retained externally after commit; independent committed-checkpoint review remains required before integration. All release authorities remain false and `release_state` remains `unverified`; final180, stateful release-readiness review, live provider rehearsal/payment, PG/Stage1A/M2A/publisher/release, activation and deployment gates remain separate/open. The result establishes isolated fixture behavior only.


## Separate integrated R3 runtime draft (2026-11-04; blocked)

The separate plan `docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md` proposes one fresh isolated fixture measurement of integrated candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`: eight required provider/root outcomes and 42 current-job readiness SQL tuples with zero skips. Its record is `docs/agents/records/2026-11-04-workshop-integrated-r3-runtime.json` and task is `docs/agents/tasks/2026-11-03-production-release/workshop-integrated-r3-runtime.json`; the release queue indexes the same goal and concrete todo. This is a docs-only uncommitted draft, not a synchronized or machine-passing implementation/runtime gate. The coordinator reports independent exact-head integration review PASS at that SHA/tree `d9fb2a8f49beacd009374a76327d0736c1fc9b0a` and draft PR217; [Issue186 comment6636079243](https://github.com/lucronn/autodata/issues/186#issuecomment-6636079243) records the later review with verified readback. This supplies no R3/runtime or production approval.

The selected strategy reuses immutable local runner/PG17/NATS/Seaweed image IDs only after image/cache/source compatibility manifests and current availability are established; no build, pull, acquisition or service operation is authorized here. The historical leaf supervisor (`e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9`) is evidence only: it unconditionally builds and needs a separately gated, reviewed adaptation before the selected strategy has an executable command. The plan fixes a clean remote-free read-only plain clone, fresh owned services/databases, a fresh private `/home` Seaweed bind with at least 12 GiB free, 1320-second runner deadline, all existing lifecycle invariants, before/after immutable manifests and bounded ownership cleanup. Missing provenance and a final reviewed command keep execution blocked.

Historical index-leaf green/audit receipts do not establish this candidate's runtime result. Final180, real providers/payments, cloud/VM/staging, release/deployment/activation and cutover retain their separate gates and unverified states. No predecessor evidence or authority changes.


## R3 immutable supervisor implementation draft (2026-11-04; blocked)

`docs/superpowers/plans/2026-11-04-workshop-r3-immutable-supervisor.md` and `docs/agents/records/2026-11-04-workshop-r3-immutable-supervisor.json` define a separate adaptation-only draft for exact candidate `4d82e413e04fb2401ac7bc28dc828375ac662180` (tree `d9fb2a8f49beacd009374a76327d0736c1fc9b0a`), based on blocked R3 plan commit `d94543e6ec75e788b42421b0e4cfeca6f5cb3e9c`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-r3-immutable-supervisor.json`. The current read-only audit report hash is `b48449fb92e7541ee2f727dd0edba7a53f67bd36ef7d0a2b88f7c3a3046c96af`: all four immutable images remain local, while current tool/package/cache manifests and offline compatibility evidence remain absent. Historical evidence is preserved.

The release queue now indexes `workshop-r3-immutable-supervisor` as a separate blocked task with no execution dependencies, preserving all predecessor entries. Its parent runtime plan is context and consumes the adaptation; the adaptation does not depend on running that parent.

The proposed implementation allowlist contains only a new external supervisor, probe payload and focused offline tests under `/home/corp/autodata-evidence/r3-immutable-supervisor-4d82e413-implementation/`; it does not alter candidate source or the historical supervisor. The draft fixes immutable image/config admission, complete before/after manifests, no build/pull/acquisition, inherited eight-root/42-tuple validation, deadlines and bounded owned cleanup. Tests and source review may be authorized only by a later synchronized committed implementation gate and explicit external-path dispatch. Creating even a read-only/network-none probe container requires a separate execution gate; fixture services require accepted fresh probe manifests and the parent runtime gate.

Issue186/Project8 synchronization, committed gate/preflight and independent dispatch are pending. This draft grants no implementation, Docker/probe/runtime, provider/payment, cloud or release authority; final180 remains open and release unverified.
