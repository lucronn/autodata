# Source projection v2 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after exact-base preflight and coordinator dispatch. Keep milestones small and push after validation.

**Goal:** Version corrected source projections and support bounded source-only offline reprojection from retained body bytes without provider/model calls.

**Architecture:** Preserve raw fingerprint and snapshot identities; key immutable source rows by article, raw fingerprint and projection version. Explicit v2 capture selects a domain-separated transformation identity while v1 keys retain their exact historical bytes. Existing source/current-canonical pointers remain the read contract.

**Tech Stack:** Python dataclasses/pytest, PostgreSQL migrations and isolated lifecycle fixtures.

**Spec:** `docs/architecture/normalized-article-document.md`, Source projection v2 (prospective amendment to the original v1 lifecycle spec).

Issue: https://github.com/lucronn/autodata/issues/325
Project: https://github.com/users/lucronn/projects/8
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGUxxM
Record: `docs/agents/records/2026-11-05-source-projection-v2.json`.
Inspected source: `140fdf132afb9d6efad0164e5c67d7e4a836200d`; branch `codex/source-projection-v2`.

## Global constraints

Source capture/store/schema/types, a bounded offline body-only projector/CLI and tests only. Preserve raw bytes, raw fingerprint algorithm, snapshots, article identity, immutable source revisions, observations and published/terminal v1 results. No provider/model calls, stage mutation, UI/auth/payment/model changes, deployment or runtime activation. Use synthetic/offline fixtures only. Preserve historical v1 spec as history; this contract prospectively permits v2. No automatic recapture/read-time reprocessing or bulk refresh. Stage apply requires separate coordinator authorization after exact-SHA review.

## Concrete todo

- [x] Add migration 041 allowing v1/v2, three-column source uniqueness and database-enforced prevention of v2-to-v1 current-source downgrade; extend the migration driver and its tests through 041, then verify populated upgrade and migration-driver rerun.
- [x] Carry explicit projection identity through captured/stored sources and version-aware dedupe; preserve raw fingerprint/snapshot hashes and immutable history.
- [x] Keep legacy v1 transformation-key bytes stable, domain-separate v2 keys, and atomically switch current source with stale canonical cleared.
- [x] Prove identical-byte v1-to-v2 append, repeat-v2 reuse, historical reads, terminal/published v1 isolation, readable fallback before model and stale-worker rejection; run focused and isolated PostgreSQL regressions.
- [x] Add bounded body-only offline preview/apply from verified retained bytes, with atomic exact-job source-only storage, NULL transformation key, no provider/model calls and fail-closed reconstruction tests.
- [x] Commit/push validated milestones, obtain independent exact-SHA review and synchronize verification evidence in plan, canonical doc, Issue and Project.


## Exact implementation allowlist

- `db/migrations/041_article_source_projection_v2.sql` (new schema migration)
- `workers/ingestion-python/src/autodata_ingestion/source_article_capture.py` (explicit v2 capture)
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_types.py` (projection metadata/key routing)
- `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py` (version-aware storage/readback/pointers)
- `workers/ingestion-python/tests/test_source_article_capture.py`
- `workers/ingestion-python/tests/test_article_lifecycle_types.py`
- `workers/ingestion-python/tests/test_article_lifecycle_schema.py`
- `workers/ingestion-python/tests/test_article_lifecycle_migrations.py`
- `workers/ingestion-python/tests/test_article_lifecycle_integration.py`
- `workers/ingestion-python/src/autodata_ingestion/source_revision_reprojection.py` (new bounded offline reconstruction and atomic source-only apply)
- `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py` (exact-ID source-only claim and generic queue exclusion)
- `workers/ingestion-python/src/autodata_ingestion/worker.py` (ArticleObjectStore bounded read method only)
- `workers/ingestion-python/tests/test_source_revision_reprojection.py` (new projector/CLI/transaction tests)
- `scripts/dev/reproject_article_source.py` (new preview-by-default single-article CLI)
- `scripts/dev/migrate_sql.sh` (extend pinned migration chain through 041 only)
- `scripts/dev/test_migrations.py` (migration-driver 041 chain/restart regressions)

Gate/evidence documents: this plan, its JSON record, `docs/architecture/normalized-article-document.md`, and new `docs/verification/2026-11-05-source-projection-v2.md`. No API/view/worker-runner/normalizer/adapter behavior changes are required; worker.py is limited to the object-store read helper. If a new implementation path is necessary, amend and revalidate the gate first.

## Task 1: versioned schema and identities

- [ ] Add failing types/schema/migration regressions before changing behavior. Freeze an explicit expected v1 key digest for a fixed article UUID/fingerprint/profile tuple; require omitted selector and explicit v1 to match that exact digest. Require v2 key to differ and unknown versions to reject. On populated schema through 040, seed a v1 revision and immutable observation/publication; apply 041, compare old rows byte-for-byte, append same-article/same-fingerprint v2, reject duplicate same-version rows and unknown versions, and assert immutable update/delete protections still hold.
- [ ] Add 041 only; do not edit 037/038. Replace v1-only projection CHECK with allowlist `source-projection-v1`, `source-projection-v2`; replace two-column UNIQUE with `(canonical_article_id, source_fingerprint, projection_version)`. Keep v1 default for historical fixture compatibility; production capture always supplies v2 explicitly. Add a `canonical_articles` pointer-update trigger rejecting a move from v2 to v1 (SQLSTATE 23514); do not disable existing identity or immutable triggers. Null pointer resets are not a supported rollback path.
- [ ] Add `CapturedSource.projection_version` at the end with v1 compatibility default; capture returns explicit `source-projection-v2`. Add `transformation_key(..., *, projection_version="source-projection-v1")`: v1 keeps the exact existing four-field digest payload, v2 adds `projection_version: source-projection-v2` and `domain: autodata:article-transformation:v2` to that payload, unknown versions raise ValueError. Never recompute stored job/revision keys.
- [ ] Extend scripts/dev/migrate_sql.sh expected pinned migration list through 041 without changing ledger validation, ordering, lock/transaction handling or failure behavior. Add scripts/dev/test_migrations.py regressions that 041 is accepted/applied in order and skipped on restart; run `python3 -m unittest discover -s scripts/dev -p test_migrations.py`. Verify migration driver restart skips 041 and preserves populated rows/schema; update only migration-count/latest-chain expectations in the allowlisted migration test. Run focused unit tests and required PostgreSQL checks below; commit/push the validated schema/types milestone.

## Task 2: atomic source transition and regressions

- [ ] Add failing capture/store/integration regressions using existing runtime fixtures and `dataclasses.replace(captured, projection_version="source-projection-v1")` for historical seeds. Identical raw body/media/manifest must yield equal raw fingerprint, raw SHA and snapshot IDs across v1/v2; source revision IDs and transformation keys differ. Include a historical escaped-XML v1 projection and corrected ordered v2 projection of the same retained synthetic raw bytes; assert readable v2 text/structure rather than metadata alone. Verify all v1 rows remain unchanged after transition and v1/v2 explicit revision reads return their own version/document.
- [ ] Insert projection_version explicitly; use the three-column conflict target and all three columns in the fallback SELECT. Add StoredSource projection_version and load it from the immutable row. Validate supported capture version before persistence and reject v1 capture under the locked article when current source is v2, before any observation/pointer/key writes. Preserve existing lease/generation fences and rollback the entire transaction on failure.
- [ ] Pass captured projection_version to transformation_key. Keep source insertion, immutable observation, transformation ownership, and current pointer update in the existing transaction. A first v2 source clears a stale v1 canonical pointer; existing published/terminal v1 jobs cannot satisfy a v2 key. Repeat v2 observation dedupes the source and reuses only a matching v2 transformation. Published/terminal v1 records, observations, retry budgets and events remain untouched.
- [ ] Prove source fallback is visible after source commit before model work using the existing after_source_commit barrier; old canonical is absent until matching v2 publication. Test both published and terminal v1 isolation, repeat-v2 dedupe/observation creation, historical reads, stale lease/generation rejection, same-binary v1 downgrade rejection, and direct SQL v2-to-v1 pointer rejection. Old-binary two-column ON CONFLICT must fail closed after migration with no partial writes.
- [ ] Run full focused tests, isolated PostgreSQL suite and diff checks below. Commit/push the validated store/tests milestone; independent reviewer checks exact SHA, migration and raw identity invariants. Record commands/counts/skips and review in the verification doc, plan, canonical doc and Issue/Project. Runtime recapture and rollout remain separate authorization.

## Verification commands

```sh
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_source_article_capture.py workers/ingestion-python/tests/test_article_lifecycle_types.py workers/ingestion-python/tests/test_source_revision_reprojection.py -q
git diff --check
```

For the real PostgreSQL tests, use the existing isolated lifecycle runner (never application/stage databases), e.g. with dedicated artifacts and Compose project:

```sh
mkdir -p /tmp/source-projection-v2-artifacts
export AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/source-projection-v2-artifacts
export AUTODATA_R3_TEST_IMAGE=autodata-source-projection-v2-tests
export AUTODATA_R3_CANDIDATE_SHA=$(git rev-parse HEAD)
docker compose -p autodata-source-projection-v2 -f infra/compose/compose.article-lifecycle-test.yaml up -d postgres nats minio
docker compose -p autodata-source-projection-v2 -f infra/compose/compose.article-lifecycle-test.yaml run --rm --build test-runner python3 -m pytest workers/ingestion-python/tests/test_article_lifecycle_schema.py workers/ingestion-python/tests/test_article_lifecycle_migrations.py workers/ingestion-python/tests/test_article_lifecycle_integration.py workers/ingestion-python/tests/test_source_revision_reprojection.py -q
```

Required: PostgreSQL tests execute with no skips; all pass. Fixture bank/model servers are local synthetic services, not live providers/models. Remove the dedicated Compose project and its volumes after evidence capture. Existing API/current-source view is exercised through runtime.read_current; no API implementation change is allowed.

## Task 3: bounded offline source-only reprojection

Interfaces: `reproject_stored_source(repo, source_revision_id, *, object_store, deadline_seconds=30) -> CapturedSource`; `apply_source_reprojection(repo, canonical_article_id, expected_source_revision_id, captured, *, actor, reason) -> dict`; `ArticleObjectStore.get_object(key, *, max_bytes) -> bytes`. Keep source_revision_reprojection independent of live connector registries/model clients.

- [ ] Add red tests for body-only HAL/maintenance-XML replay: saved v1 escaped XML becomes readable ordered v2 with equal raw fingerprint, body snapshot, full manifest/provenance/evidence and original captured_at. Require exactly one successful body manifest entry and matching immutable observation context/provenance/snapshot; reject optional/extra/failed resource entries, descriptor asset/labor refs, parsed asset refs/images, missing blob, unsupported version, identity drift, hash/media/object-key mismatch, oversized body and deadline expiry. Assert zero provider/model calls and zero S3 puts. Preview leaves every database table unchanged.
- [ ] Read only the saved body object (max 1 MiB, total deadline 30 seconds) after binding manifest/provenance/snapshot SHA and content-addressed key. Reconstruct SourceEnvelopeV1 using the immutable observation request_id/provider/source_revision/fetched_at/locator and exact bytes, kind article/media/SHA. Feed current capture_source_article through an OfflineClient that permits exactly the saved provider/body ref and a verify-only put sink. It must never construct a real connector. The saved manifest is authoritative because optional body envelope refs were not persisted; fail closed if replay discovers any asset/labor/image need. Restore captured_at and assert exact fingerprint/snapshot/manifest/provenance/evidence equality before returning explicit v2.
- [ ] Preview is default CLI mode; require `--article-id` and `--source-revision-id` UUIDs, with optional `--dry-run`. `--apply` additionally requires actor/reason and preview-bound expected fingerprint/body SHA. Print IDs, versions, hashes, counts, lengths and status only; never licensed text, raw resource refs or secrets. Reuse ArticleRepository/ArticleObjectStore environment configuration without loading connector registry or model client. Limit worker.py edits to get_object: bounded read, size rejection and response close/release with existing SDK timeouts/no retries.
- [ ] Apply opens one database transaction, locks the exact article, validates current source equals expected revision and immutable raw bindings still match preview, rejects active normal jobs, and increments generation without profile changes. Create a source-only job with checkpoint `source_only_reprojection=true`, original source revision ID, actor and reason; exact-ID claim it in that same transaction. Refactor store internals to accept the existing cursor so insertion, claim, source/observation append and pointer switch all commit or roll back together. Generic claim and exhausted-lease sweeps exclude the source-only marker; targeted claim requires that marker and exact job/article IDs. No broad queue claim is allowed.
- [ ] Source-only storage appends v2 and a new immutable observation, clears stale canonical and updates current job/source under normal fences. It finishes the new job as terminal `needs_review`, nonretryable, `error_code=SOURCE_ONLY_REPROJECTION`, clears lease fields and keeps transformation_key NULL. Do not consult/reuse/reserve a canonical transform key in this branch; a later separately authorized normal v2 refresh must be able to own the v2 key. Old source, observation, published/terminal job and retry records remain unchanged. Repeating an already-applied exact request returns already_applied without new rows; a concurrent different pointer/generation fails closed.
- [ ] Real PostgreSQL tests inject failure between job creation/source insertion/pointer update and prove complete rollback, zero queue stealing of unrelated jobs, source-only generic-claim exclusion, expected-pointer race rejection, idempotent repeated apply, historical v1 readability, current v2 source fallback and NULL transform key. Then explicitly refresh in the fixture and prove a normal v2 worker can own its transformation (fixture provider/model only). CLI tests exercise default preview, apply argument binding and safe output. Commit/push the validated offline milestone and obtain independent exact-SHA review before any runtime use.

## Stage outcome boundary

Read-only audit of the existing stage Banktwo article found one HAL+JSON body resource, complete immutable observation context/provenance and a 3853-byte S3 blob matching the manifest SHA. Offline replay through current capture yielded 29 blocks and no images with identical raw identity and saved provenance; no provider call, S3 write or database mutation occurred. This establishes feasibility only. The implementation must reproduce the invariant under tests; actual stage apply and authenticated browser acceptance remain separate coordinator actions after review. Normal refresh would re-fetch and may hit CANARY_REQUEST_LIMIT; no provider refetch is needed or authorized for this source-only path.

## Rollout and rollback contract

Separate operator work must stop/drain all old workers before migration, apply 041, replace every worker with the v2 binary and then resume. Dropping the old unique pair deliberately causes old `ON CONFLICT(canonical_article_id,source_fingerprint)` writes to fail closed; mixed binaries are unsupported. Both new store and database prevent direct v2-to-v1 current-source downgrade. Do not down-migrate or start old binaries against v2 state; retain immutable records and use a forward fix. This checkpoint authorizes none of those runtime actions.

## Gate handoff

Commit/push these three planning documents, pin the resulting full checkpoint SHA externally, then run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-source-projection-v2.json --base-sha CHECKPOINT_SHA
```

Required result: `{"status": "synchronized", "errors": []}`. Live Issue body, Project Source field and Ready status must be read back before commit; their hashes are in the record. Coordinator owns builder dispatch; this checkpoint contains no implementation.

## Migration-driver scope amendment

Amends checkpoint `dff1a1cda2c8e48433edec1d38a1d61816746391`: the driver hardcodes the chain through 040, so 041 cannot run without adding its exact expected name. Only `scripts/dev/migrate_sql.sh` and `scripts/dev/test_migrations.py` are added to implementation scope; all prior invariants and runtime restrictions remain binding. This docs-only amendment must be committed, pushed and pass exact-SHA preflight before editing those paths.

## Development implementation evidence

Candidate `e45541ca2058e9fa25b70b6eace329922ee96ca5` implements the first five concrete work items. See `docs/verification/2026-11-05-source-projection-v2.md` for separately bound earlier broad and final focused test runs, fixture limitations and the exact-candidate review status. The detailed task checklists above are retained as original execution instructions, rather than additional release acceptance. The coordinator confirmed independent exact-SHA review with zero actionable findings. The exact committed-candidate focused run passed 33 tests, 45 deselected and zero skips (21.07 s); independent migration-driver unittests passed 25. All six development work items are complete. Stage application, fresh CI and browser acceptance remain open and receive no acceptance credit here.
