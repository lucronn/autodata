# New Article Automatic Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This checkpoint permits planning only; wait for exact-base preflight and coordinator dispatch before implementation.

**Goal:** Automatically process only newly created automatic article jobs through one bounded worker without retrying historical jobs or spending more than one model attempt per admitted article.

**Architecture:** Add a small worker wrapper around existing `run_article_worker_once(job_id=exact_uuid)`. Persist a database-clock activation cutoff, finite quota, disable flag and consumed reservations in one protected local state file; commit each selected pristine job's `max_attempts=1` before dispatch. Preserve the existing lifecycle, prompt-v2 validators, publication and source fallback.

**Tech Stack:** Python standard library, existing psycopg/PostgreSQL17 lifecycle repository, existing Docker runtime image and one systemd service.

**Spec:** `docs/operations/new-article-worker.md`; canonical gate `docs/agents/pre-implementation-gate.md`.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source base: `b3618fb6e68f1734ef029096748e30e655451a26`, tree `b686966c9bb4c01c7d35262c661f8645f9fb9f04` (merged PR350).
Record: `docs/agents/records/2026-11-06-new-article-worker.json`.

## Fixed scope and operator boundary

- Existing HTTP schedules durable jobs but runs no article worker. The separate HTTP source-refresh gate does not authorize a daemon. This successor supplies the missing small worker, not a new queue or scheduling framework.
- Only four implementation files: new `workers/ingestion-python/src/autodata_ingestion/new_article_worker.py`, new `workers/ingestion-python/tests/test_new_article_worker.py`, existing `workers/ingestion-python/tests/test_article_lifecycle_integration.py`, and new `infra/deploy/preview/autodata-new-article-worker.service`. This plan, record and canonical operator document may receive evidence updates. No database migration, API, generic claim, prompt, validator or existing worker behavior change.
- Retain exact pinned runtime image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`; new dependencies require a new decision. Keep current API/HTTP routing, checkout disabled, Stripe mode/keys/grants, source/canonical history and frozen canary identities unchanged.
- No provider, database-write, host-service or credential operation occurs during planning/implementation except isolated synthetic tests. Installing/arming the service is a later coordinator dispatch after exact-source review and verification; no historical generic worker may run concurrently.

## Small rollout contract

Fixed mounted directory `/var/lib/autodata/new-article-worker` contains mode0600 regular root-owned `rollout.json`, a single-process nonblocking `worker.lock`, and a short-held `state.lock`. Refuse symlinks, hardlinks, wrong ownership/mode and replaced directory/file identities. A parent-directory bind mount makes atomic JSON replacement visible. The service reads no caller-selected state path.

State schema1 contains `rollout_id` UUID, `source_sha` full approved code SHA, `cutoff` UTC timestamp obtained once from PostgreSQL `clock_timestamp()`, `expires_at=cutoff+24h`, `providers=["bankone","banktwo"]`, `max_jobs=10`, `enabled` boolean, and `reservations` array of `{job_id, reserved_at}`. Initialize once disabled; refuse overwrite/rearm of an existing rollout. Operators explicitly enable only the approved state. Restart preserves cutoff, expiry, quota and reservations. A new rollout or increased quota/provider scope requires a new recorded coordinator decision; never silently reset state.

One process and one job at a time; poll every2seconds. Under `state.lock`, stop admission when disabled, expired or10 reservations consumed. Disable is an atomic update under the same short lock, distinct from the lifetime `worker.lock`. Disable stops subsequent reservations; one already reserved/in-flight job may finish. SIGTERM stops polling and prevents another admission; provider delivery already in flight is never replayed. Service success exit at expiry/quota/disable is terminal, with no restart loop that rearms state.

For each candidate use existing PostgreSQL repository and one transaction with row locks on job and owning canonical article. Require ALL:

- Both article and job `created_at > cutoff`; provider is in the persisted allowlist and agrees across rows.
- Article `current_job_id` points exactly at this job, both request generations0, target/job normalization `ordered-article-v1`, profile `full-prose-auto-v1`, active membership and takedown, no current source or canonical revision.
- Job kind `article`, status `pending`, phase `queued`, retry_count0, lease_token0, no lease/heartbeat/next-attempt/error, empty checkpoint, no source revision/transformation key. Exclude catalog-index/legacy jobs and every failed/processing/refresh/review/park/recovery path.
- No previous job for this article, no source revision/observation, rewrite attempt, canonical candidate/publication or historical processing evidence for this identity. An old descriptor with a newly queued job is ineligible because the article creation cutoff also applies. Never re-key/reset an old identity.

Choose oldest eligible row with `FOR UPDATE SKIP LOCKED`; perform a locked eligibility recheck. While the row stays locked, consume and fsync a state reservation BEFORE changing the row. Then set `max_attempts=1` and add only `checkpoint.new_article_rollout={rollout_id,source_sha,cutoff,max_model_attempts:1}` and commit BEFORE calling the existing exact-job worker. If state persistence or SQL commit fails, do not dispatch; consumed quota remains spent conservatively. On restart any reserved UUID is excluded even when still pending, so crash cannot trigger automatic replay. Never reclaim a stale reservation or expired lease.

Dispatch exactly once with `run_article_worker_once(repo, worker_id=..., registry=..., object_store=..., model_client=..., job_id=reserved_uuid)`. Never invoke `article_worker_main`, call the helper without `job_id`, sweep the queue, refresh generations, resume failed jobs or raise attempt caps. The helper's internal resume/exhaustion SQL is already scoped by that exact UUID; its candidate is pristine at admission, not a historical job. Maintain the single-worker/no-other-dispatch prerequisite across cap-commit/claim. An unexpected owner/status change skips that reservation and consumes its quota; no fallback selection or retry for that UUID.

The unchanged claim increments retry_count to1, and the committed cap1 prevents another model attempt after failure/lease loss. Existing attempt-row uniqueness and dispatched transition prevent duplicate dispatch. Initialize model configuration before reserving any job; absent model credentials or an unexpected model stops admission. Preserve reviewed Mercury3 model,32768 output token/60second request limits, existing bounded source client behavior and strict publication checks. Any uncertain provider delivery consumes its reservation; no automatic client retries, tuning calls or second worker. A missing source/invalid rewrite stays truthful source fallback or explicit failure. Do not claim semantic certification or numeric originality.

## Task 1: Minimal worker and service

**Files/interfaces:** new module provides `run_new_article_worker()` and module CLI default run plus fixed `--initialize`, `--enable`, `--disable` control operations. Controls share fixed state paths; initialize captures DB time without enrolling jobs. The new service runs `python -m autodata_ingestion.new_article_worker` in the pinned existing image, immutable reviewed `/app` source mount, protected state-directory mount and approved private environment; one host-network container, read-only root, cap-drop ALL/no-new-privileges, no API/HTTP replacement.

- [ ] Write red unit tests proving cutoff/allowlist/quota/disable/restart fencing and exact UUID dispatch: frozen rows, missing model config and exhausted quota produce zero worker/provider calls; one eligible row calls the existing helper only once with `job_id` and cap1 already committed.
- [ ] Implement file locks, bounded strict state parsing/atomic fsynced updates, pristine SQL selection/cap transaction and the short wrapper loop. Test state-write/commit/crash boundaries; no generic claim API modifications.
- [ ] Add the service file with fixed state directory and command, `Restart=no`, one pinned image/source binding supplied by the reviewed root-only deployment configuration, and clean shutdown. Runtime installation/enablement remains coordinator-only, with no source/script repair at deploy time.
- [ ] Run focused unit tests and syntax/diff checks; commit and promptly push the coherent worker milestone.

## Task 2: PostgreSQL proof and handoff

**Files:** new unit tests and existing lifecycle integration fixture; operator document records exact results.

- [ ] Add real isolated PostgreSQL tests for two eligible new articles, pre-cutoff article/job, old article/new job, provider mismatch, generation1, failed/processing/expired/parked/recovery rows, retry/attempt/source/candidate history, owner-pointer drift and frozen canaries. Assert excluded rows/counters stay byte-identical.
- [ ] Prove cap1 committed before exact helper dispatch; worker restart after state reservation, SQL commit, uncertain model delivery and saved result never dispatches a second model request. A second worker fails the lifetime lock. Disable/expiry/quota prevent another admission; short state lock allows disable during a running job. Use fixture HTTP model counts, not row-count inference.
- [ ] Verify actual v2 automatic publication, readable source fallback on failure, and zero-call warm reuse through existing real lifecycle fixture. Run focused tests with real PostgreSQL (no skipped integration acceptance), existing automatic suites, syntax and diff checks. Push exact candidate for independent review and required CI.
- [ ] Coordinator later installs disabled service using exact reviewed source/image/environment, verifies no old/generic worker, persists database-clock cutoff and quota, and explicitly enables the finite rollout. Retain old HTTP/API/container state; disabling/stopping this service is rollback. Never restore/delete database rows or undo canonical results. Synchronize actual runtime counters/outcome separately; this planning checkpoint supplies no live-run authority.

## Concrete todo record

- [ ] Implement one small new-only worker around exact-job dispatch with persisted database-clock cutoff, provider allowlist,10-job/24hour quota, disable control and no historical resume or generic queue drain.
- [ ] Commit each pristine selected job's durable max_attempts1 before dispatch; preserve reservations across crashes/restarts and leave frozen/history-bearing jobs and all existing source/canonical records unchanged.
- [ ] Prove eligibility, cap/claim ordering, crash/disable/quota/concurrency behavior and actual automatic publication with focused unit and isolated PostgreSQL tests; add only the minimal worker service configuration.
- [ ] Push validated exact-source milestones for independent review/CI, record evidence in the operator document and tracking, and require separate coordinator service-install/enable dispatch with checkout disabled.

## Synchronized checkpoint and verification

Tracking uses an append-only Issue186 comment and dedicated Project8 `New article worker reference` text field; preserve Issue body/prior comments and every unrelated Project field. Commit/push the synchronized plan/record/operator document, then run the canonical preflight against its FULL committed SHA before any implementation dispatch:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-new-article-worker.json --base-sha FULL_CHECKPOINT_SHA
```

Implementation checks: focused `test_new_article_worker.py`, existing automatic rewrite unit suites, isolated lifecycle PostgreSQL `-k 'new_article_worker or automatic'`, Python syntax and `git diff --check`. Store exact commands and counts; unavailable/skipped PostgreSQL is an explicit acceptance gap. This plan neither enables a service nor spends a provider request.

Tracking synchronized through [Issue186 comment6695221432](https://github.com/lucronn/autodata/issues/186#issuecomment-6695221432) and dedicated Project8 text field `New article worker reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho439s`). Issue body, prior comments and unrelated Project fields remain intact. This docs-only checkpoint awaits exact-SHA machine preflight and coordinator implementation dispatch.
