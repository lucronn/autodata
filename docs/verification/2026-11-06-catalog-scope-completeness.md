# Sparse catalog selector verification — 2026-11-06

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8; PR https://github.com/lucronn/autodata/pull/363.

Planning gate: `5511b18f2082103243011598c840bfbad532a5e9`; implementation: `eb09122109fd1933cee8afea71be8495a77d69ac`. Independent read-only review of that exact implementation returned PASS with zero actionable findings. Connector client changes are outside this PR.

## Red/green evidence

Before implementation, all eight mixed-provider order/outcome regressions failed because `result.complete` was true despite a failed/incomplete provider. `TestCompleteEmptySelectorsDoNotHydrateAgain` failed with `complete:false, hydrating:true` and attempted ingestion. The upgrade test failed because migration042 did not exist.

After implementation:

- Host `python -m pytest workers/ingestion-python/tests/test_catalog_service.py workers/ingestion-python/tests/test_selector_deepening.py workers/ingestion-python/tests/test_catalog_selector_persistence.py -q`: **41 passed, 15 skipped**. Skips require the explicit isolated lifecycle fixture.
- Isolated PostgreSQL `pytest -q workers/ingestion-python/tests/test_catalog_selector_persistence.py`: **12 passed in31.07s**, including actual Go store/API checks, migration041->042, legacy marker recovery, partial selector retention, no synthetic identities, provider order failures, and20-second retry replay. After adding direct successful model/provenance assertions, rerun with `-k 'not go_sparse_selector_store'`: **11 passed, 1 deselected in1.58s**.
- Full Go API `go test ./...`, isolated runtime with network disabled: **ok github.com/lucronn/autodata/apps/api-go 8.741s**.
- Host `python -m pytest scripts/dev/test_migrations.py infra/deploy/gce/test_host_provision.py infra/deploy/gce/test_host_prepare_release.py -q`: **42 passed, 5 skipped, 17 subtests passed in4.17s**.
- Machine preflight at exact planning gate: **status synchronized, errors[]**; shell syntax and `git diff --check`: passed.

The dedicated container runtime was `autodata-source-projection-v2-test-runner:latest`, with a newly created isolated `pgvector/pgvector:pg17` container. No application database or live service was changed. The Go selector integration is invoked by the Python test with a fresh lifecycle_test_* database; unflagged ordinary runs skip it.

## Broader fixture limit

The expanded real migration chain and catalog service command used the explicit lifecycle flag, Python source path, private `/artifacts`, dedicated PostgreSQL and an ad-hoc SeaweedFS S3 container. Result: **57 passed, 2 setup errors in61.64s**. Both errors were `minio.error.S3Error`, code `InternalError`, during fixture `LifecycleRuntime` initialization while uploading a source resolution object, before either test body:

- `test_populated_publication_and_all_lifecycle_records_survive_restart`
- `test_total_catalog_deadline_rolls_back_first_bank_when_second_waits`

This does not constitute a passing full lifecycle run. Earlier ad-hoc attempts also lacked PYTHONPATH, `/artifacts` or an S3 endpoint; these fixture setup errors were corrected without changing application code. Ordinary migration/rollback/upgrade assertions passed after updating the exact42 migration expectations. Root coordinator accepted focused database/API checks, full Go checks and independent review as sufficient code-review evidence; required repository CI remains a release gate. No further broad rerun is authorized in this task.

## Operational boundary

Merge connector OSError fix first, apply migration042 using the canonical runner, restart ingestion HTTP and API to clear legacy process caches, then GET affected year/make scopes. Legacy markers remain preserved with version zero and cannot prevent those scoped reads. Successful complete reads store all source selectors atomically with version one; polling reuses existing single-flight and incomplete replay bounds. This repair does not start a fleet crawl, duplicate background jobs, deploy code, or restart production. Root owns release execution and live verification.
