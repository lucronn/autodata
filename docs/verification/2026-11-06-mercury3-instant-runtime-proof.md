# Draft: Mercury3 Instant One-Identity Runtime Proof

Status: **UNSYNCHRONIZED DRAFT — NOT DISPATCHABLE**. No runtime, implementation or operational script is authorized. Exact merged source, CI, tracking and script review are pending.

Goal: Prove the merged Mercury3 instant client on one fresh authentic Banktwo identity in a new finite rollout, preserving the retired rollout and spent jobs and always stopping after bounded observation.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Plan `docs/superpowers/plans/2026-11-06-mercury3-instant-runtime-proof.md`; canonical `docs/verification/2026-11-06-mercury3-instant-runtime-proof.md`; record `docs/agents/records/2026-11-06-mercury3-instant-runtime-proof.json`. Tracking field/comment: **PENDING**, no GitHub update by this draft.

## Concrete todo record

- [ ] Pin exact merged PR355 source/tree/archive and successful required CI/review; synchronize this draft before any runtime write.
- [ ] Verify old worker stopped/disabled and archive its exact state, two reservations/configuration and historical baselines; take a fresh identity-bound PostgreSQL17 backup and install the immutable new source with a new disabled rollout.
- [ ] After separate exact-script review and dispatch, atomically enroll only fresh Banktwo snapshot member2 through existing fenced persistence helpers, then enable/start the existing service once.
- [ ] Observe only the exact proof job for at most300 seconds, record truthful publication or source-fallback failure, and always disable+stop while preserving new reservation and old history; no retry/reset/replay.

## Blocking pins

- PR355 https://github.com/lucronn/autodata/pull/355: reviewed head observed `6296bccad8b19595db62317be788c5817ab16181`; exact merged source/tree/archive **PENDING**. Required successful CI/review URLs and final runtime diff **PENDING**. Do not substitute head for merge or assume CI completion.
- Gate checkpoint/record hash, dedicated Project8 field, Issue readback, exact-base synchronized preflight, independently reviewed static operational script SHA and explicit coordinator dispatch: **PENDING**. This draft's unsynchronized record intentionally blocks execution.
- Preserve existing image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`, unchanged service and exact corrected18-name private environment. Source-only configuration change to new immutable `/opt/autodata/new-article-worker/<MERGED_SHA>/source`; no provider/model/env tuning, package install, schema or HTTP/API deployment. Verify runtime diff against old39a90ef is the reviewed client change only.

## Fixed candidate; no discovery or source capture during preparation

Use only Banktwo persisted descriptor snapshot `2c3765ac-08ca-519c-97e9-a8984a504913`, SHA256 `8bfa14647b24f675698c9dfb647f0a3957b84a2320c9efdeb7e7e603c7f4a059`, zero-based member2. Opaque-ref SHA256 `b7a962535b91c1e4d71b7f44fc31dc479d12655f5feb77ec98e64bbf508b2ede`; deterministic article ID `f0e822b2-b03e-545b-aa7b-b541ef776888`; vehicle `d7344e42-c5f6-5ec1-b9e3-9352e6b41336`; configuration `cf544dfd-4570-589f-b3b4-23487d14e591`, exact configuration scope. Read-only preparation verified identity/provider-scope-ref absent and pending/processing article count0; recheck at dispatch. Existing resolution binding and exact snapshot member bytes must still agree. No alternate member, page drain, new snapshot, manufactured reference, external source/body/model request or identity creation during prep.

## Two bounded stages using reviewed controls

Stage A installs disabled only. Recheck canonical verified-TLS/no-redirect public readiness and purchase disabled with User-Agent curl/8.0.0, no generic/exact worker, no eligible pending work, and the old disabled rollout UUID `b4ac970f-684a-491e-8a52-5900cfcefc61` with exactly the two spent reservations. Preserve both terminal jobs, full current historical/frozen-anchor fingerprints and root-protected receipts. Under bounded exclusive state/worker locks, archive the old state directory and source configuration byte-for-byte to a unique root-only evidence path with fsync/readback/hashes; never alter its rollout, reservations, cutoff or expiry and never reinitialize it. Exact archive path is **PENDING** in the synchronized successor.

Take a fresh root0600 PG17 custom dump, bounded120s, with cluster system identifier + database OID equality between donor worker endpoint and backup endpoint; hash and PG17 restore-list<=15s. Keep the old backup and disposable restore proof as historical evidence, not permission to restore production. Seal exact merged archive root-owned/read-only with no extras, preserve unit/image/env/security, point only source configuration to the new pin, then create a NEW root0700 state directory at the service's existing bind path and initialize once disabled from database clock. New UUID/cutoff/expiry exactly+24h/max10/providers both; no old-state reset. Capture disabled-stage receipt and verify DB/history unchanged before handing off.

Stage B requires the reviewed disabled receipt plus synchronized gate and separate coordinator dispatch. Recheck unchanged source/state/env/service/public health, fresh zero-reservation state and all historical anchors. Read/hash only the existing internal S3 snapshot using the already protected pinned dependency bundle; no caller-owned Python dependencies. Lock source_fetch_jobs then canonical_articles before rechecking exact identity absence and baseline; use existing upsert_article_descriptor + ensure_article_job on ONE shared transaction for only this generation0/full-prose-auto-v1 descriptor/job. Record the exact returned job ID. Enqueue must follow new database cutoff and be the only eligible job at start.

Enable once and start the unchanged service once. Inspect exact source/image/environment/security/state binding. Observe the exact proof job for at most300s using bounded metadata-only reads; canonical success requires published current UNREVIEWED revision, passed validation, source/transformation/publication-event binding, zero human review and readable content. Preserve complete_rewrite flag semantics; no claim of semantic quality from mechanical validation. Failure/source fallback/timeout is truthful terminal evidence. No extra identity, direct model call, manual claim, attempt increase, retry or reset.

ALWAYS disable<=15s, stop<=80s and verify stopped<=15s after terminal outcome or deadline, using a separate recovery budget so forward timeout cannot prevent cleanup. Retain the new consumed reservation and all old history/evidence. Failure does not authorize another start. Never restore production DB or rewrite either spent job. The existing worker has fixed max10: this proof creates only one eligible identity, but concurrent ordinary application admissions could consume additional slots before stop. The synchronized gate must explicitly accept that bounded existing behavior or block dispatch; do not falsely claim a one-job worker cap.

## Draft boundary

No implementation or runtime write allowlist exists yet. No operational script is created by this draft. Exact source/CI, private evidence paths, old-state/config hashes, fresh baseline, script digest/review, tracking readback and committed synchronized preflight must replace all pending pins before a coordinator may authorize either stage.
