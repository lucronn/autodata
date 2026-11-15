# Two Authentic Persisted Article Descriptors Live Proof Plan

> **For agentic workers:** Use superpowers:executing-plans for the fixed handoff. This checkpoint plans only; no enrollment occurs before exact committed preflight, independent driver review and coordinator dispatch.

**Goal:** Permit one atomic enrollment of exactly two authentic unseen persisted-index descriptors, at most one Bankone and one Banktwo, for the existing finite worker to prove live automatic ingestion without replaying history or expanding its budget.

**Architecture:** Reuse exact existing index snapshot members and current persistence helpers in one fenced transaction, then let the already running finite worker process the two new identities. No new code, external index fetch, generic drain or direct model dispatch.

**Tech Stack:** Existing Python ingestion source, PostgreSQL17, internal S3 snapshots and existing finite worker.

**Spec:** `docs/verification/2026-11-06-new-article-live-proof.md`; operator: `docs/operations/new-article-worker.md`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-06-new-article-live-proof.json`.

## Exact two-member selection

Only the following already persisted partial-index members are eligible; there is no discovery, full-page drain, replacement member or synthetic/test reference:

| Provider | Existing descriptor snapshot | Snapshot SHA256 | Zero-based member | Opaque-ref SHA256 | New canonical article ID |
|---|---|---|---|---|---|
| bankone | `d1201595-d1e0-5b8b-a642-04dfc243ff80` | `29ea51838374f8f77faf89f524f982d9f2b9550f5949b084cb131e3bde543c70` | 2 | `b4cba926336fadac1e27ad6c9d7c41c97ee92823c81410c7488c88e3848ef634` | `bb7896e8-5647-518c-abe6-969384ecee8e` |
| banktwo | `2c3765ac-08ca-519c-97e9-a8984a504913` | `8bfa14647b24f675698c9dfb647f0a3957b84a2320c9efdeb7e7e603c7f4a059` | 1 | `7b5190d1626fef8846566df246b6ba934b6b1476d5116d940a16b41352b1c5a8` | `1cae3450-955a-5807-b72f-91010d396008` |

Bankone vehicle/configuration are `97d830df-987c-5db3-bcba-2d7b83fec4ac` / `c54c88f0-5d0a-5f45-979b-6804a08bad1f`; Banktwo are `d7344e42-c5f6-5ec1-b9e3-9352e6b41336` / `cf544dfd-4570-589f-b3b4-23487d14e591`. Scope is exactly `configuration:<configuration UUID>`. Reuse each existing matching provider/source-vehicle scope and nonnull `resolution_source_snapshot_id`; create or update no vehicle, configuration, scope or source snapshot. Verify snapshot DB metadata and existing object bytes agree, provider envelope matches, selected descriptor/ref hash matches and deterministic `article_id(ArticleKey(...))` equals the pinned ID. Preserve descriptor fields from that exact member, adding only normal `source_sort_order` equal to its index. No raw opaque reference, secret, body or model/source content is logged.

## Existing authority and readiness

Runtime source remains `39a90ef58225aabeef242c63f231c220a47ccee7`, image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`, exact reviewed service/source/config unchanged. The active worker's prior successful idle receipt is SHA256 `744d5322d599014288c62438a0df4a2d0cec7e23ea16c85d2df060ac556119e6`, container `665da18f7ba3c953eaa8a961509beaf70868b1ed74ccd7143c87667bd2e01bdf`, under activation gate `2dca9672ee570ddce5f55756f6300014c6f6962b` and docs PR354. This new gate enrolls authentic unseen work; it does not restart or replace the worker.

Require original rollout UUID `b4ac970f-684a-491e-8a52-5900cfcefc61`, cutoff `2026-11-06T21:26:51.149443+00:00`, expiry `2026-11-07T21:26:51.149443+00:00`, enabledtrue, providers bankone/banktwo, max_jobs10, zero reservations, remaining original window by DB clock and active exact singleton worker. Neither target descriptor nor any prior job/source/revision/attempt/publication identity may exist. A mismatch blocks both enrollments; do not select substitutes or drain pending work. Existing HTTP/canonical readiness200 and purchase disabled remain prerequisites. The two selected jobs consume the original finite ten-job budget; there is no separate allowance or guarantee that all remaining slots are unused forever.

## Bounded one-shot persistence boundary

Preparation is read-only and makes no external connector, article body, provider or model call. A separately dispatched driver may read **only the two existing internal S3 index objects**, maximum4MiB each, with a hard whole-read budget15seconds and no unbounded SDK retries. Set `sys.dont_write_bytecode=True` before immutable-source imports. Use existing approved DB/S3 credentials privately; no credential copying into argv/logs or runtime configuration edit. Driver/evidence files are root0600 under `/var/lib/autodata/new-article-worker-evidence/two-bank-enqueue-review/`; no implementation/source file is modified.

Host execution must use root isolated Python (`/usr/bin/python3 -I`), never corp/user-site packages or a caller-supplied `PYTHONPATH`. Before enrollment, permit read-only extraction of **only** the running pinned worker image's `/usr/local/lib/python3.14/site-packages/minio` and its required `/usr/local/lib/python3.14/site-packages/Crypto` package directories through `/proc/<verified worker PID>/root/`, bounded30seconds, into root-owned `two-bank-enqueue-review/pinned-deps/`. Before and after copying, bind PID/start identity to the exact running worker/container and pinned image; require its root filesystem read-only and the package outside all bind mounts. Create a complete relative-path/SHA256 manifest from that protected source and require extracted file set and every byte hash to match, rejecting links/traversal/extras. The root system already supplies other required dependencies; no additional package directory may be copied. Seal package directories0500/files0400 under private root0700 evidence; preserve manifest/archive hashes privately. No package installation, image pull, external network or new worker/container is authorized. Add only this protected package parent and the already sealed root-owned ingestion/contracts source to isolated `sys.path`; validate imported dependencies originate in protected root-owned system paths or the verified bundle. No user-writable dependency may be imported by the root driver. A missing dependency or mismatch blocks; do not install/fallback. This private preparation creates no canonical/source/job record.

Independent review must pin the complete driver SHA256, exact gate SHA, target IDs and a protected machine-preflight receipt bound to that exact base SHA. Require explicit coordinator execution dispatch after this record passes at its committed/pushed pin. Create an exclusive, fsynced one-shot attempt journal before mutation; any failed or uncertain attempt consumes authorization. Do not rerun the driver or infer rollback from a missing result receipt.

Within one existing `ArticleRepository.connect()` transaction, acquire `LOCK TABLE source_fetch_jobs,canonical_articles IN SHARE ROW EXCLUSIVE MODE` in that order **before** checking historical baseline and exact identity absence. Use existing bounded role/connection settings (`lock_timeout=1500ms`, `statement_timeout=1800ms`) and an independent hard transaction budget15seconds; no admin/grant fallback. Recheck original rollout and seven protected baseline tables under the fence. Holding this fence prevents existing `ON CONFLICT DO UPDATE` helpers from racing a concurrent enrollment into historical mutation. Any existing row, changed baseline, timeout or error aborts both new pairs.

Pass a caller-owned same-transaction repository wrapper to the existing `upsert_article_descriptor(repo,key,descriptor,UUID(snapshot),0,rewrite_profile_version="full-prose-auto-v1")` and `ensure_article_job(repo,article_id,normalization_version="ordered-article-v1",rewrite_profile_version="full-prose-auto-v1")`. Both helper `connect()` contexts must yield the same outer connection and must not commit independently. Require returned exact article ID, `created=true`, pending article job, generation0, retry0, no source/attempt/history and exact current owner. Both pairs commit together only after all checks; expected writes are exactly two new canonical descriptors, two new article jobs and their current-job pointers. No direct source/body capture, exact-job dispatch, model construction, catalog/index job, scope generation/retirement, history update or publication write occurs in this driver.

Retain the diagnosis's exact seven-table prestate (counts/digests) in the private reviewed driver/manifest and compare it under the transaction fence. Evidence records hashes/IDs/counters only. Preserve all frozen/history-bearing rows and original backup/failure receipts. Insertion makes these two genuinely new post-cutoff identities eligible for the **already authorized finite worker**, which independently reserves quota and commits cap1 before claim. Do not set worker reservations, max_attempts or checkpoints manually.

## Observation, truthful acceptance and recovery

After commit, record the returned two exact job IDs and observe read-only for at most300seconds with individually bounded reads. Do not call ensure again, run an alternate worker, retry failed body/model calls, manufacture more identities or bypass validators to produce success. Match each admitted ID to the same persisted rollout reservation, generation0, exact ownership/provider/snapshot and original cutoff; require durable max_attempts1, retry_count<=1 and at most one model attempt. Existing source/model calls made by the finite worker remain inside its original one-attempt/ten-job/24-hour authority.

A successful end-to-end claim requires persisted readable source, normal validator success, current canonical revision published/UNREVIEWED, a matching publication event and no approval-review bypass. Record source/model/publication IDs/hashes/statuses only. A truthful source-only/failed/ambiguous outcome or observation timeout is recorded as such, never called successful automatic publication. Idle service readiness alone remains insufficient. On detected history/scope drift, second attempt, unsafe health/checkout state or terminal/ambiguous failure, use the existing bounded disable15s + stop80s recovery without deleting/resetting work or restoring the DB. Keep an independent recovery budget and preserve spent reservations even if a current claim finishes or is killed. No enqueue retry, third identity, new rollout, worker restart, budget increase or expiry extension follows from this gate. After successful bounded proof, only the original finite worker authority remains; unseen-failure risk and optional later read-only diagnostics are unchanged.

## Concrete todo record

- [ ] Pin the two existing snapshot/page members and deterministic article IDs; recheck exact source/worker/rollout, zero reservations, absent identities, provider resolution bindings and unchanged historical baseline without external source/model calls.
- [ ] Independently review one bounded exact driver and dispatch; read and hash only the two existing internal S3 snapshots, then atomically insert the two new descriptors and generation0 jobs through existing persistence helpers after lock-before-absence checks.
- [ ] Observe only the existing finite worker and exact two job IDs; record truthful source/model/publication or failure evidence with one model attempt per job and UNREVIEWED publication, without direct claim/capture/model calls or manufactured work.
- [ ] Preserve consumed reservations, original ten-job/24-hour scope, historical rows and all receipts; disable+stop on detected unsafe behavior, with no enqueue retry, lease/attempt reset, replay, new rollout or source/unit/config change.

## Synchronization

Append only Issue186 and dedicated Project8 `New article live proof reference` field `PVTF_lAHOCSJ8cc4BiQ2Bzho5KCg`; preserve activation/HTTP/implementation fields and all history. Commit/push this plan, record and canonical verification document; machine-check the record at that exact committed SHA before any enrollment dispatch.

Tracking synchronized through [Issue186 comment6696570087](https://github.com/lucronn/autodata/issues/186#issuecomment-6696570087) and dedicated Project8 field `New article live proof reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho5KCg`), preserving prior history/fields. Exact committed pin and machine preflight precede any enrollment dispatch.

Exact Minio+Crypto dependency scope clarification: [Issue186 comment6696579424](https://github.com/lucronn/autodata/issues/186#issuecomment-6696579424).
