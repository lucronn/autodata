# Catalog Completion Cleanup Verification Boundary

Status: synchronized code-only planning boundary; no implementation performed by this checkpoint.

Goal: Clear stale catalog job error_code and next_attempt_at on successful fenced completion, preserving retry history and article isolation; make no production database or runtime changes.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Plan `docs/superpowers/plans/2026-11-06-catalog-completion-cleanup.md`; canonical `docs/verification/2026-11-06-catalog-completion-cleanup.md`; record `docs/agents/records/2026-11-06-catalog-completion-cleanup.json`.

## Concrete todo record

- [ ] Add a PG-backed regression exercising a retryable catalog failure followed by ordinary due reclaim and successful completion; demonstrate stale error and retry scheduling fail the expected clean completion assertions.
- [ ] Change only catalog_coverage._complete completed-job UPDATE to set error_code=NULL and next_attempt_at=NULL while preserving lease/generation fencing, retry count/checkpoints and existing successful scope semantics.
- [ ] Verify completed job status/phase, null error/schedule/leases, retryable=false, persisted bound page/descriptors and retained retry history; run focused catalog coverage and catalog-only worker tests including article non-interference.
- [ ] Commit/push the code and regression with validation evidence for review; preserve all live jobs, receipts and stopped services without deployment, database cleanup or new runtime authority.

## Exact scope and evidence

Product base6c1bd04fb419aad296f59a04f0eef256d37b2c73; planning branch includes append-only catalog runtime gates. Actual stopped retry produced matching Bankone4163 and Banktwo4112 bound descriptors with1 completed page each, but operator receipt was partial-failure/FORBIDDEN_ENV; authenticated paid browse UNVERIFIED and opposite-provider coverage incomplete. Runtime outcome and preserved safety evidence remain in docs/verification/2026-11-06-catalog-index-runtime-activation.md. Banktwo completed jobe9ef7353 retains UPSTREAM_UNAVAILABLE and next_attempt_at although phasecompleted and scopecomplete. Existing _complete UPDATE omits cleanup; no data migration is required for future completions.

Implementation allowlist ONLY workers/ingestion-python/src/autodata_ingestion/catalog_coverage.py and workers/ingestion-python/tests/test_catalog_coverage.py. Documentation may update only this plan/canonical/record and validation evidence. Keep the change to adding error_code=NULL,next_attempt_at=NULL in the existing lease-fenced successful job UPDATE. No schema, API, worker selection, retry limit, model, service or environment change. Scope code regression to actual retry->success using existing disposable PG fixture and connector fixtures: induce retryable source failure, preserve first retry count/error/schedule, make retry ordinarily due in fixture, reclaim exact catalog job, then successful page completion. Assert error/scheduleNULL and existing lease cleanup/retryablefalse, retry count retained and page/descriptors correct. Existing failure/needs_review branches must retain their diagnostic/scheduling behavior. Include successful empty/no-match completion cleanup if existing fixture path permits without expanding implementation.

Validation: focused test_catalog_coverage.py and test_catalog_index_worker.py with existing PG fixtures; retain article-job non-interference coverage. No provider/model/live requests. No live SQL UPDATE, repair of historic completed row, reset/replay, container/systemd control or deployment. Gate author edits documentation/tracking only; builder starts only after committed synchronized gate exact-base preflight and coordinator dispatch.

 Independent review further distinguishes4160 Bankone/4110 Banktwo descriptors bound to the new scope page from3/2 exact preexisting IDs retaining valid same-provider hashed historical snapshots through the existing equal-generation/equal-descriptor skip. Total active generation0 membership is4163/4112; do not claim every descriptor was newly rebound.
