# Source projection v2 development verification

Status: development implementation verified locally; coordinator confirmed independent exact-candidate review with zero actionable findings. No stage activation or browser acceptance is claimed.

Candidate: `e45541ca2058e9fa25b70b6eace329922ee96ca5` on `codex/source-projection-v2`.
Issue: https://github.com/lucronn/autodata/issues/325.
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGUxxM`.
Planning checkpoints: `dff1a1cda2c8e48433edec1d38a1d61816746391`, amended by `6f0fb9f5a1ab6f6f520f1722831db9c080b98eb4` before migration-driver edits. Exact amended-checkpoint machine preflight returned `{"status": "synchronized", "errors": []}`.
Implementation milestones: schema/types `6130e0c`, atomic versioned store `9383648`, bounded offline source-only reprojection `e45541c` (full candidate above).

## Verified behavior

Migration 041 permits immutable v1/v2 source rows with three-column uniqueness and a database guard against current-source downgrade. The migration driver recognizes 041 and preserves existing ledger/locking/transaction behavior. Capture writes explicit v2; historical v1 reads and source identities remain stable. The v1 transformation-key payload retains its frozen historical digest; v2 adds an explicit projection version and domain. Published or terminal v1 work cannot satisfy v2 work.

Source capture/store regressions cover identical-byte v1-to-v2 append, repeated-v2 reuse, immutable historical reads, existing lease/generation fences, and current source fallback before canonical/model work. Source/canonical pointer changes remain atomic.

The offline path supports exactly one verified retained body resource, max 1 MiB and 30 seconds, using immutable saved context/provenance and content-addressed bytes. Preview is default. Optional resources, missing bodies, hash/identity drift, discovered images and expired deadlines fail closed. CLI output reports IDs/hashes/counts only. No live connector/model is constructed; replay performs no S3 puts.

Source-only apply binds the expected article/revision and preview hashes. One transaction creates/marks/exact-claims its job, appends v2 and observation, clears stale canonical and switches current source. The terminal job is nonretryable `needs_review` with `SOURCE_ONLY_REPROJECTION` and NULL transformation_key. Generic claim/sweeps exclude source-only jobs. Tests prove rollback at job/source/pointer boundaries, unrelated-job isolation, active-job/pointer-race rejection, repeated-apply idempotency and later normal v2 transformation-key ownership.

## Local test evidence

The builder reported these distinct runs; counts are not combined. Earlier broad runs preceded the final added regressions and idempotency fix, so they are not represented as a complete final-candidate rerun.

| Run | Result | Binding |
| --- | --- | --- |
| Host capture/types/offline suite | 165 passed, 6 skipped; 116.35 s | Earlier working tree; PostgreSQL-only skips expected outside isolated fixture |
| Isolated schema/migration/integration/offline suite | 113 passed, zero skips; 197.22 s | Working tree before final two unit cases, repeated-v2 apply regression and fix |
| Updated isolated offline/source-projection selection | 33 passed, 45 deselected, zero skips; 23.88 s | Final working tree before commit |
| Exact committed candidate focused selection | 33 passed, 45 deselected, zero skips; 21.07 s | `e45541ca2058e9fa25b70b6eace329922ee96ca5` |
| Independent migration-driver unittest | 25 passed | Reviewer at exact candidate; coordinator-confirmed |

Host command:

```sh
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_source_article_capture.py workers/ingestion-python/tests/test_article_lifecycle_types.py workers/ingestion-python/tests/test_source_revision_reprojection.py -q
```

The broad isolated run used Compose project `autodata-source-projection-v2`, `infra/compose/compose.article-lifecycle-test.yaml`, `test-runner` and this pytest command:

```sh
python3 -m pytest workers/ingestion-python/tests/test_article_lifecycle_schema.py workers/ingestion-python/tests/test_article_lifecycle_migrations.py workers/ingestion-python/tests/test_article_lifecycle_integration.py workers/ingestion-python/tests/test_source_revision_reprojection.py -q -p no:cacheprovider
```

The exact committed-candidate rerun used this full command:

```sh
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/source-projection-v2-artifacts AUTODATA_R3_TEST_IMAGE=autodata-source-projection-v2-tests AUTODATA_R3_CANDIDATE_SHA=e45541ca2058e9fa25b70b6eace329922ee96ca5 docker compose -p autodata-source-projection-v2-final -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner python3 -m pytest workers/ingestion-python/tests/test_source_revision_reprojection.py workers/ingestion-python/tests/test_article_lifecycle_integration.py -k 'reprojection or projection_v2 or unknown_projection' -q -p no:cacheprovider
```

The fixture requires `AUTODATA_LIFECYCLE_TEST=1`, restricts database access to generated `lifecycle_test_*` databases, and runs synthetic connector/model servers on its internal network. Synthetic runtime/worker artifacts are retained under `/tmp/source-projection-v2-artifacts`; test counts came from tool transcripts rather than a separately saved pytest log.

Additional parallel attempts against a shared SeaweedFS fixture encountered three setup `InternalError` failures (`No writable volumes and no free volumes left`). Those runs did not establish passing evidence; the dedicated fresh fixture resolved the setup issue. No application assertion failure is attributed to those setup attempts.

The reviewer ran `python3 -m unittest discover -s scripts/dev -p test_migrations.py`: 25 tests passed. `git diff 6f0fb9f e45541c --check` passed. The implementation diff contains exactly the 16 allowlisted implementation paths.

## Independent review and cleanup

The coordinator confirmed independent exact-SHA review of `e45541ca2058e9fa25b70b6eace329922ee96ca5` with zero actionable findings. Review covered atomic apply, repeated-v2 idempotency, NULL source-only transformation key, queue exclusion, offline SHA/provenance preservation and migration behavior. The reviewer also passed the 25 migration-driver unittests and diff checks.

The builder removed both owned Compose projects (`autodata-source-projection-v2` and `autodata-source-projection-v2-final`) using `down -v --remove-orphans`, removing their networks and six volumes. Container and volume label queries returned empty for both projects. The synthetic artifact directory remains retained.

## Remaining boundaries

Fresh CI status and any runtime activation remain open. No PR or merge is authorized by this record.

The prior read-only stage feasibility audit found a 3853-byte Banktwo body and replayed it to 29 blocks with no images while preserving raw identity/provenance. That audit is not an apply of this implementation. No migration, stage database mutation, provider/model call, provider refetch, deployment or authenticated browser acceptance occurred in this development verification. Drain old workers before a separately authorized migration/activation; mixed binaries and rollback against v2 state remain unsupported. Actual stage offline apply, readable fallback and browser acceptance remain open.
