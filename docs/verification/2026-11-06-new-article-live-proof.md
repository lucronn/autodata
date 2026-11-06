# Live Automatic Article Proof: Two Authentic Persisted Descriptors

Status: synchronized planning boundary; no enrollment or article processing is claimed.

Goal: Permit one atomic enrollment of exactly two authentic unseen persisted-index descriptors, at most one Bankone and one Banktwo, for the existing finite worker to prove live automatic ingestion without replaying history or expanding its budget.

Canonical procedure: `docs/superpowers/plans/2026-11-06-new-article-live-proof.md`; record: `docs/agents/records/2026-11-06-new-article-live-proof.json`; operator: `docs/operations/new-article-worker.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8, dedicated `New article live proof reference` field.

## Exact two-member selection

Only the following already persisted partial-index members are eligible; there is no discovery, full-page drain, replacement member or synthetic/test reference:

| Provider | Existing descriptor snapshot | Snapshot SHA256 | Zero-based member | Opaque-ref SHA256 | New canonical article ID |
|---|---|---|---|---|---|
| bankone | `d1201595-d1e0-5b8b-a642-04dfc243ff80` | `29ea51838374f8f77faf89f524f982d9f2b9550f5949b084cb131e3bde543c70` | 2 | `b4cba926336fadac1e27ad6c9d7c41c97ee92823c81410c7488c88e3848ef634` | `bb7896e8-5647-518c-abe6-969384ecee8e` |
| banktwo | `2c3765ac-08ca-519c-97e9-a8984a504913` | `8bfa14647b24f675698c9dfb647f0a3957b84a2320c9efdeb7e7e603c7f4a059` | 1 | `7b5190d1626fef8846566df246b6ba934b6b1476d5116d940a16b41352b1c5a8` | `1cae3450-955a-5807-b72f-91010d396008` |

Bankone vehicle/configuration are `97d830df-987c-5db3-bcba-2d7b83fec4ac` / `c54c88f0-5d0a-5f45-979b-6804a08bad1f`; Banktwo are `d7344e42-c5f6-5ec1-b9e3-9352e6b41336` / `cf544dfd-4570-589f-b3b4-23487d14e591`. Scope is exactly `configuration:<configuration UUID>`. Reuse each existing matching provider/source-vehicle scope and nonnull `resolution_source_snapshot_id`; create or update no vehicle, configuration, scope or source snapshot. Verify snapshot DB metadata and existing object bytes agree, provider envelope matches, selected descriptor/ref hash matches and deterministic `article_id(ArticleKey(...))` equals the pinned ID. Preserve descriptor fields from that exact member, adding only normal `source_sort_order` equal to its index. No raw opaque reference, secret, body or model/source content is logged.

## Runtime boundary and acceptance

The existing worker remains source39a90ef, image5c8e79b, active container665da18f and original rolloutb4ac970f-684a-491e-8a52-5900cfcefc61 (cutoff2026-11-06T21:26:51.149443Z, expiry2026-11-07T21:26:51.149443Z, max10). Its successful idle receipt744d5322 proves zero reservations, not article publication. Recheck its exact active/source/security/healthy-checkout-disabled identity and zero reservations before enrollment; neither target may already exist. The two new identities consume original quota; no new budget/start/configuration is authorized.

The plan fixes the entire bounded procedure. Read only the two persisted internal S3 index objects; no external source/index/body/model call occurs in prep or enrollment. Root isolated Python may use only the plan's hash-verified Minio and required Crypto package extraction from the existing pinned image via its verified `/proc/<PID>/root/` (root-protected immutable private bundle), never user-site dependencies. No package install or new container is authorized.

After exact committed/pushed gate preflight and independent exact-driver/coordinator dispatch, create one exclusive consumed attempt journal, then use one transaction with source-job-first table fences, protected historical baseline and absence checks before existing descriptor/job helpers. Both authentic new descriptor/job pairs commit together, generation0/automatic; no existing identity/history/scope/source record is changed. Any uncertainty consumes the attempt and blocks repeat enrollment.

Read-only observation of those two returned job IDs lasts at most300seconds. The existing worker alone reserves original quota, commits cap1 and performs normal body/model/validation work. Success requires readable source, published UNREVIEWED canonical revision, valid publication binding and no review bypass; record truthful failure/source-only/timeout otherwise. Preserve original history/frozen rows. Detected unsafe behavior uses existing disable+stop with independent recovery budget. No replay, reset, retry, synthetic member, generic drain, third identity, expiry/cap change or new rollout follows. Preparation creates no identity/job and claims no end-to-end success.

## Concrete todo record

- [ ] Pin the two existing snapshot/page members and deterministic article IDs; recheck exact source/worker/rollout, zero reservations, absent identities, provider resolution bindings and unchanged historical baseline without external source/model calls.
- [ ] Independently review one bounded exact driver and dispatch; read and hash only the two existing internal S3 snapshots, then atomically insert the two new descriptors and generation0 jobs through existing persistence helpers after lock-before-absence checks.
- [ ] Observe only the existing finite worker and exact two job IDs; record truthful source/model/publication or failure evidence with one model attempt per job and UNREVIEWED publication, without direct claim/capture/model calls or manufactured work.
- [ ] Preserve consumed reservations, original ten-job/24-hour scope, historical rows and all receipts; disable+stop on detected unsafe behavior, with no enqueue retry, lease/attempt reset, replay, new rollout or source/unit/config change.

Tracking synchronized through [Issue186 comment6696570087](https://github.com/lucronn/autodata/issues/186#issuecomment-6696570087) and dedicated Project8 field `New article live proof reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho5KCg`), preserving prior history/fields. Exact committed pin and machine preflight precede any enrollment dispatch.

Exact Minio+Crypto dependency scope clarification: [Issue186 comment6696579424](https://github.com/lucronn/autodata/issues/186#issuecomment-6696579424).
