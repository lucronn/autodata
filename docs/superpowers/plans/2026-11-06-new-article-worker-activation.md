# First New Article Worker Runtime Activation Plan

> **For agentic workers:** Use superpowers:executing-plans for this fixed runtime handoff. This checkpoint is planning only; no deployment, initialization, enablement or worker start occurs without a later coordinator dispatch at its exact passing pin.

**Goal:** Permit one corrected enable/start retry of the same disabled ten-job/24-hour new-article rollout after verified zero-reservation rollback, preserving its original state, budget and historical jobs.

**Architecture:** Reuse the installed unchanged PR352 service, immutable reviewed source, pinned image,18-name private environment and already initialized disabled state. Correct only the external effective-environment inspection guard, then permit one separately reviewed/dispatched enable/start retry of the same rollout. Existing exact-job dispatch commits cap1 before claim and never revisits a reserved UUID.

**Tech Stack:** Existing Docker image, systemd, Python worker controls, PostgreSQL17 read-only preflight/backup and bounded observation. No new implementation or deployment framework.

**Spec:** `docs/operations/new-article-worker.md`; canonical gate `docs/agents/pre-implementation-gate.md`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-06-new-article-worker-activation.json`.

## Exact identities and prerequisites

- Worker code is **only** `39a90ef58225aabeef242c63f231c220a47ccee7` (PR352), full tree `ff59de0d1372725bd79180f61001b48520c3d53e`. Deterministic `git archive --format=tar` SHA256 is `fd9dd41408a252c556607f4086bbd7422b56404da94e74fc6b2fe2b750e8dced`; worker module SHA256 `f9c057351be15b8c15b4de69e9e7c474755e50f33f6672cc5f216b0d0f2dad26`; service SHA256 `c1d1882dbfd2b7a18759762a1212a17e1031db04b6ccb11006a00af74dc0e257`. No source substitution, source repair or new dependency.
- Before any runtime write, require PR352 merged to master, independent review approved at that head, all required CI successful, and no changes to runtime source/contracts/service between the reviewed head and merge. Record the actual merge SHA and CI URLs; a changed runtime diff requires another reviewed gate. The implementation preflight was at `2a8525b36c990babffe4c83e9e4288a9f0c0137c`; this separate runtime record must also pass at its own committed/pushed pin.
- HTTP refresh succeeded by coordinator report and read-only inspect: `autodata-ingestion-prompt-v2-http-b3618fb6-r3`, ID `38f3bc41eb2433096fe469c6b4dd4d368d52a28b43ba678c395b48ba7c478e22`, source `/home/corp/autodata-candidate/prompt-v2-http/b3618fb6e68f1734ef029096748e30e655451a26/source` read-only at `/app`; port3031; source SHA `b3618fb6e68f1734ef029096748e30e655451a26`. Original `3cefb07d948ae5bbee3d1cde52a8f41e5dcf837ccbdb8143f67284ff3f90dcfe` is retained stopped for its own rollback. HTTP outcome is independently receipt-verified at [Issue186 comment6695577548](https://github.com/lucronn/autodata/issues/186#issuecomment-6695577548), docs PR353 head `3da82f415c91958211277485f72fafd80f2a142c`. Validate the private `third-final-result.json` SHA256 `a623cf5bbc778057e243021cfeca7404d8e50bfe22c320806b280202875dc84e`, local3031 and canonical public readiness/purchase proof (200, enabledfalse), and unchanged DB receipt `17a932` before worker installation. Any HTTP identity drift blocks; do not recreate API/HTTP as part of this task.
- Runtime image is `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`, default UID0. Local tests: focused28, unit200, existing automatic/new runtime20, plus final shutdown regression1 passed. No production job/model call is needed to establish installation readiness.

## Fixed runtime write allowlist

Only create the immutable source `/opt/autodata/new-article-worker/39a90ef58225aabeef242c63f231c220a47ccee7/source`, exact unit `/etc/systemd/system/autodata-new-article-worker.service`, configuration `/etc/autodata/new-article-worker.conf`, private environment `/etc/autodata/new-article-runtime.env`, state directory `/var/lib/autodata/new-article-worker`, and private evidence/backup directory `/var/lib/autodata/new-article-worker-evidence/first-rollout-39a90ef`. Fail rather than overwrite any existing rollout/state/container/service/configuration; an existing matching source may be read-verified and reused, never patched. Parent directories/config/state are root-owned; source directories0555/files0444 (retaining execute bits only where the archive has them), private directories0700/files0600. No caller-owned0700 mount: UID0 with all capabilities dropped requires root ownership.

Source comes from the exact verified archive with no `.git`/untracked files, extracted once and sealed root-owned/read-only. Service is byte-identical to the pinned file. Config is exactly:

```ini
AUTODATA_NEW_ARTICLE_SOURCE=/opt/autodata/new-article-worker/39a90ef58225aabeef242c63f231c220a47ccee7/source
AUTODATA_NEW_ARTICLE_SOURCE_SHA=39a90ef58225aabeef242c63f231c220a47ccee7
```

Build private runtime.env inside a root-only process by selecting **only these16 donor names** from the successful fixed HTTP container; never clone its full environment or print secret values:

```text
AUTODATA_DB_ADDRESS
AUTODATA_POSTGRES_DB
AUTODATA_POSTGRES_USER
AUTODATA_POSTGRES_PASSWORD
AUTODATA_S3_ENDPOINT
AUTODATA_S3_ACCESS_KEY
AUTODATA_S3_SECRET_KEY
AUTODATA_SOURCE_BUCKET
BANKONE_BASE_URL
AUTODATA_BANKONE_API_KEY
BANKTWO_BASE_URL
AUTODATA_BANKTWO_API_KEY
INCEPTION_API_KEY
INCEPTION_MODEL
PYTHONDONTWRITEBYTECODE
PYTHONPATH
```

Require each selected name exactly once and preserve its value. Add **only** `INCEPTION_MAX_TOKENS=32768` and `INCEPTION_API_TIMEOUT_SECONDS=60`, yielding **18 exact env-file names**. Require `INCEPTION_MODEL=mercury-3`, `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python`. Reject missing/duplicate/extra names, newline/NUL values, donor mismatch or unexpected tuning. The unchanged unit adds `AUTODATA_NEW_ARTICLE_SOURCE_SHA` and repeats the two Python settings with identical values, yielding **19 approved application names**, not19 total container environment entries: pinned image defaults such as PATH/LANG/PYTHON_VERSION/PYTHON_SHA256 remain from that exact image. Compare application names/values and pinned-image defaults separately. Do not copy commerce/webhook keys, internal HTTP token, image signing key, NATS or MinIO admin credentials. Do not alter HTTP settings; record only names/counts, permissions, equality verdicts and private file digests.

The unchanged unit uses fixed container name `autodata-new-article-worker`, host network, read-only root/source, cap-drop ALL, no-new-privileges, whole state-directory read-write bind, no extra ports/mounts, `Restart=no`, stop timeout70seconds and systemd stop timeout80seconds. There is no Install target: do not enable it at boot. Root-only command payload inspection must confirm the source/env/state/image/command before execution; no Compose up, generic worker entrypoint, provider install, host bootstrap, migration or grant change is in scope.

## Task 1: Freeze, backup and install disabled

- [ ] Recheck exact gate/preflight, merge/CI/review and successful HTTP receipt. Record root-only absence/ownership checks for the fixed paths, unit and worker container; verify no generic article worker/other exact dispatch runs and no pending/processing article jobs exist. If that baseline changed, stop for a narrow coordinator decision; never drain it.
- [ ] With existing approved private DB credentials and bounded connections, capture database clock and historical job/attempt/source/publication fingerprints, frozen Bankone job `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d`, frozen Banktwo `64888ce4-429e-4e22-9892-48d1fb4b82eb`, and completed canary `2967d7f9-09ad-4a24-9e96-9f2e20479ff5`. Verify required table SELECT/INSERT/UPDATE and `has_column_privilege(current_user,'source_fetch_jobs','max_attempts','UPDATE')`/checkpoint permissions with read-only catalog queries; no grant repairs.
- [ ] Capture a consistent private PostgreSQL17 custom-format `pg_dump` using the existing approved backup path/runtime, bounded to120seconds. Require exit0, root0600 nonempty artifact, SHA256, and successful PostgreSQL17 `pg_restore --list` within15seconds; preserve the existing verified restore-drill reference. Backup is evidence, never permission to restore or remove rows during rollback. Do not put connection strings/passwords in argv or output.
- [ ] Seal archive/source, exact unit and two config files; record private allowlist/value equality (18 env-file names) and public source/unit/image hashes. Verify root permissions, read-only mount/UID0 compatibility and `systemd-analyze verify` without starting anything. Run only `python -m autodata_ingestion.new_article_worker --help` in the fixed pinned image with networknone for import proof. `systemctl daemon-reload` is allowed only after the exact unit is installed; no enable/start yet.
- [ ] Using the same fixed image/source/env/state payload below, invoke only `--initialize` once. It queries database clock and writes disabled state; no enrollment or model/source request. Require schema1, exact source SHA, fresh UUID, cutoff from DB time, expiry exactly+24h, providers bankone/banktwo, max_jobs10, enabledfalse and empty reservations. State and lock files root0600, directory root0700; initialization cannot overwrite an existing rollout. Snapshot scope privately and verify DB fingerprints unchanged. Hand the disabled installation evidence to the coordinator before enable/start.

The approved root-only Docker control argv is the service payload without a worker daemon/name and with exactly one control argument. For `--initialize`, `--enable` and rollback `--disable`, use:

```sh
docker run --rm --network host --read-only --cap-drop ALL --security-opt no-new-privileges \
  --env-file /etc/autodata/new-article-runtime.env \
  --env AUTODATA_NEW_ARTICLE_SOURCE_SHA=39a90ef58225aabeef242c63f231c220a47ccee7 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python \
  --mount type=bind,src=/opt/autodata/new-article-worker/39a90ef58225aabeef242c63f231c220a47ccee7/source,dst=/app,readonly \
  --mount type=bind,src=/var/lib/autodata/new-article-worker,dst=/var/lib/autodata/new-article-worker \
  --workdir /app/workers/ingestion-python \
  sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4 \
  python -m autodata_ingestion.new_article_worker --initialize
```

Replace only the final `--initialize` with `--enable` or `--disable` at their explicitly authorized stage; no empty/default control invocation. Bound each control process to15seconds; on uncertain initialization, inspect existing state and stop rather than retry/reinitialize.

## Task 2: Explicit first rollout, bounded observation and rollback

- [ ] After disabled evidence is accepted and coordinator explicitly dispatches enable/start at the pinned runtime gate, recheck the unchanged HTTP health/purchase state, worker absence, private permissions, remaining24h window and zero reservations. Run `--enable` once, verify enabledtrue with unchanged scope, then `systemctl start autodata-new-article-worker.service` once. Inspect fixed container's exact source/image/args,19 approved application names plus unchanged pinned-image defaults, UID0/security and mounts. Any mismatch means disable+stop, not repair/recreate/retry.
- [ ] Observe at most120seconds initially (eight samples15seconds apart, each read bounded5seconds), without manufacturing articles, calling ensure, warming provider routes or doing model tuning. Confirm service/process singleton, HTTP health and checkout disabled, state cutoff/expiry/quota unchanged, reservations monotonic<=10; each newly admitted job is automatic generation0, post-cutoff, `max_attempts=1`, retry_count<=1 and has at most one model-attempt row/dispatch evidence. Match every admitted UUID to state and rollout checkpoint. Historical/frozen job counters/checkpoints and immutable source/publication fingerprints must remain unchanged. Record only identifiers/status/counters/hashes; never credentials or source/model content.
- [ ] Successful natural new work must publish through unchanged validators as `UNREVIEWED`; failure must retain truthful readable source/failure state. During initial observation the operator disables+stops upon detecting a terminal job failure, ambiguous delivery, historical mutation, second attempt, scope/quota drift, unexpected process/health failure or purchase-enabled state. The existing worker does not automatically stop on a failed dispatch: detection latency can permit further admissions, bounded by the same10 reservations. No retry/reset/rearm, cap increase or generic sweep. An idle120second observation is valid idle evidence, not a publication success claim.
- [ ] On healthy completion of the initial observation, leave only this same process authorized until first10 reservations or persisted24h expiry, with a recorded coordinator handoff of cutoff/expiry/count and the finite-risk statement below. The handoff explicitly accepts the bounded worst case of up to10 jobs, each with at most one model attempt, even when a failure occurs between polls or after initial observation; truthful source fallback remains. Later read-only checks are optional diagnostics, not a prerequisite for leaving the finite worker running. No periodic observer, new monitor/service or enforced fail-stop deadline is required: an unseen failure can consume remaining slots up to10. No first-failure-stop or unattended fail-stop guarantee exists. Disable+stop on any failure detected during the initial120second observation; after healthy initial observation, leave the same worker running only until its persisted cap/expiry. No additional rollout, automatic restart or continuing budget is implied. Later read-only checks may inspect actual natural work; they do not enqueue it. At quota/expiry the worker exits; record final counters and retain state even if fewer than10 complete.
- [ ] Rollback invokes the fixed `--disable` control (15second bound), then `systemctl stop autodata-new-article-worker.service` (80second bound), and verifies enabledfalse, no running named worker/container, preserved reservations and unchanged HTTP/API/checkout. If disable fails, stop immediately anyway; keep failed state/attempt evidence and diagnose read-only. Never restart, reset leases/attempts, delete state, change canonical/source rows or restore the backup. One already running claim may finish or be killed by the existing stop timeout; a spent reservation cannot be replayed.
- [ ] Synchronize exact source/service/environment hashes, actual merge/CI references, rollout UUID/cutoff/expiry, backup/observation/rollback receipts and truthful outcome in the canonical operator doc and append-only Issue186/dedicated activation field. No new implementation file is authorized by this runtime plan; a required code/payload change needs an amended synchronized checkpoint.

## One corrected enable/start retry amendment

This section supersedes the first-start/no-retry instructions **only for one corrected retry of the already initialized rollout**. Task1 is historical completed work, not authority to install or initialize again. The first attempt failed `WORKER_EFFECTIVE_ENV_DRIFT` and was rolled back with disabled/stopped verified true and zero reservations. Retain successful installed-disabled receipt SHA256 `2a9a3067f87643829eaae1305c0ae0a799e64444bf237501e8af8ddff622df78`, baseline SHA256 `88063c1537c0f1313813120e1518c0cf479a9c7b546376c17c2f32a6e728f7ad`, failure receipt SHA256 `1b34a77af48667c36e98ee47814b4cfc51a070048567f58688f552f6bf76b454`, stage1 helper SHA256 `6495ac99507d7bbba4227630a1f22f72da03487bda136ec58d74cc30f375bf9c` and the existing verified private backup. The failed stage2 script SHA256 was `d1062baadfdde67ba88d550a0b69a5ef83d7b686a611b220ccf7ddffe47f6da3`; it is evidence, not the retry payload.

The same rollout must remain UUID `b4ac970f-684a-491e-8a52-5900cfcefc61`, cutoff `2026-11-06T21:26:51.149443+00:00`, expiry `2026-11-07T21:26:51.149443+00:00`, providers bankone/banktwo and max_jobs10. No reinitialize, reset, new rollout/cutoff, expiry extension, cap increase, source/model work, environment-file edit or service/source/config replacement is authorized. Existing installed source/image/unit/environment/security/mount checks remain mandatory. Fresh bounded preflight immediately before retry must verify disabled state, zero reservations, stopped service/no running worker container, remaining original time window, singleton, unchanged historical/frozen fingerprints and public readiness/purchase200 with purchase disabled. Any mismatch blocks the retry.

Docker CLI28.5.2 appends repeated user environment entries and the daemon preserves them. The unchanged unit repeats two settings already present in the exact18-name env-file. The revised effective-environment guard may accept **exactly two occurrences each** of `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python`, with both occurrences equal to their pinned values. Every other approved application name must occur exactly once; reject any other duplicate, missing/extra application name or unequal value. Preserve the pinned image defaults and validate them separately. The env-file itself must still have exactly18 unique approved names; this is solely an effective-container inspection correction, not permission to relax env-file validation or expose additional credentials.

Before runtime dispatch, independently statically review the complete revised retry script at its exact SHA256 against this committed/pushed gate, including the two-name exception and all original bounds/rollback checks. Record that digest and review approval in the private retry evidence. Use fresh retry-specific receipt paths; never overwrite the retained stage1/baseline/failure evidence. A coordinator then separately authorizes **one** `--enable` control and **one** `systemctl start` of the same installed service, using the original15second control and120second initial-observation bounds. No automatic or manual second retry is implied; any failure or uncertain execution consumes this authorization and requires disable+stop plus a new synchronized decision before another start. During initial observation any detected failure triggers disable+stop; rollback retains the same UUID/cutoff/expiry and all reservations.

After healthy initial observation, the unchanged truthful finite contract applies: the same worker may remain until its original ten reservations or original expiry; an unseen failure may consume remaining slots, each with at most one model attempt. No automatic first-failure stop, unattended fail-stop or ongoing monitor prerequisite is promised. Later read-only checks remain optional diagnostics. This amendment performs no runtime operation and changes no implementation file.

## Concrete todo record

- [ ] Retain verified stage1 installation, backup and failure receipts; verify the same rollout UUID/cutoff/expiry, disabled state, zero reservations, stopped worker, unchanged installed payload and healthy public readiness with purchase disabled.
- [ ] Independently review the exact revised retry script and its digest; accept only the two equal-value Python duplicates in Docker effective environment while retaining exactly18 unique env-file names and all other pinned checks.
- [ ] After exact checkpoint preflight and explicit coordinator dispatch, run one enable and one service start for the same rollout; observe120seconds and disable+stop on any detected failure without another retry.
- [ ] After healthy initial observation retain only the original finite ten-job/24-hour authorization; preserve consumed state and evidence with no reinitialization, reset, source/model change, cap increase or expiry extension.

## Synchronization

Use a new dedicated Project8 `New article worker activation reference` text field and append-only Issue186 comments. Preserve the body, prior comments, implementation-worker field, HTTP field and historical source/dependency reference. Commit/push only this plan, its record and the canonical operator document on `codex/new-article-runtime-gate`, then run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-new-article-worker-activation.json --base-sha FULL_COMMITTED_CHECKPOINT_SHA`. This machine success verifies the planning boundary; merge/CI and explicit runtime dispatch are additional blocking prerequisites.

Tracking is synchronized through [Issue186 comment6695599756](https://github.com/lucronn/autodata/issues/186#issuecomment-6695599756) and Project8 dedicated `New article worker activation reference` field `PVTF_lAHOCSJ8cc4BiQ2Bzho49NY`; all prior Issue/body/Project fields were preserved. Exact committed/pushed pin and machine preflight precede any later runtime dispatch. HTTP successful outcome is [comment6695577548](https://github.com/lucronn/autodata/issues/186#issuecomment-6695577548).

This amendment supersedes checkpoint `e06efc2966946754491d923db938aa3dca8c9d82` solely for the minimal environment and truthful operator-observation contract. It does not change worker code, source/image/service pins, ten-job/24-hour budget or deferred runtime authority.

Amended environment and finite-continuation tracking: [Issue186 comment6695699309](https://github.com/lucronn/autodata/issues/186#issuecomment-6695699309), clarified by [comment6695712232](https://github.com/lucronn/autodata/issues/186#issuecomment-6695712232), and the same dedicated activation field. The coordinator independently instantiated configured model, connector registry and S3 client from the16 selected donor names plus two limits, and completed a DB SELECT1; no provider/model/S3 call or runtime write was needed. Later checks are optional; the first10/24h bounded risk is accepted after healthy initial observation.

One-retry amendment tracking: [Issue186 comment6696148312](https://github.com/lucronn/autodata/issues/186#issuecomment-6696148312) and unchanged dedicated activation field `PVTF_lAHOCSJ8cc4BiQ2Bzho49NY`. The prior stage1/failure evidence remains retained; this checkpoint changes only the exact same-rollout retry boundary. Runtime controls remain deferred to independently reviewed exact-script coordinator dispatch.
