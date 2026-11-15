# Live Automatic Article Proof: Two Authentic Persisted Descriptors

Status: exact two-identity enrollment completed; partial automatic-processing outcome verified: Bankone published UNREVIEWED, Banktwo failed once with source fallback. Two-bank publication and full-rewrite quality are not established.

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

## Dispatched enrollment outcome

At approximately 2026-11-06T21:49:39Z, the independently reviewed exact driver exited 0 with `TWO_NEW_IDENTITIES_ENQUEUED`, under gate `c1a1fcbed6788c58f4e89e0e86da8e1c03d9af37` and its synchronized exact-base preflight. The sealed result reports `status: enqueued`, source `39a90ef58225aabeef242c63f231c220a47ccee7`, zero direct provider calls and zero direct model calls. It returned exactly:

| Provider | Article ID | Generation0 job ID | Persisted descriptor member |
|---|---|---|---|
| bankone | `bb7896e8-5647-518c-abe6-969384ecee8e` | `80d311b0-30cb-440d-831f-f1d6f06336f3` | `d1201595-d1e0-5b8b-a642-04dfc243ff80`, index2 |
| banktwo | `1cae3450-955a-5807-b72f-91010d396008` | `e536239d-4425-4c24-a8cf-43d5bd34af5b` | `2c3765ac-08ca-519c-97e9-a8984a504913`, index1 |

Private root-protected evidence is under `/var/lib/autodata/new-article-worker-evidence/two-bank-enqueue-review/`:

| Evidence | SHA256 |
|---|---|
| Exact reviewed `enqueue_two_new_identities.py` | `fbf9442b8fe9db756752fd0eb7c2d63ccc1e708fa460bd90cc01b266113eef79` |
| `pre-dispatch-health.json` | `546b087fcbeac548b8b3ca09eb0505f100dbf16428ad4884f6f5810512db51d7` |
| `dispatch-approved.json` | `17faf1015d8dff4d7ce834b184634f008c81382a9f3e98b548d15902c260c661` |
| `exact-gate-preflight.json` | `2d4ef9e7ed460c6f2b3b19445c9637f3cf5f1402a2e198c48fc99e1cb877ecae` |
| Consumed `attempt.json` | `038508cd0959d9204378e43c2072b5dfbbf983cf5a58753932b29fd6724bb57b` |
| `enqueue-result.json` | `2fb097bc39e42ef668bab3db5aa121628738d1ef24bbe1b21822ff5ad94cfd4a` |

The committed planning record remains the original authorization boundary. This receipt proves enrollment, with no additional enqueue, retry, reset or new budget authorized. Existing-worker processing and end-to-end publication require independent read-only evidence; none is inferred from the enqueue result.

Independent read-only DB observation `monitor-01.json` at `2026-11-06T21:50:14.036398Z` (SHA256 `3e217be76a010770291e231c27f43477ec14b5a550f4c9c22a00fede731d4870`) confirmed both exact article/provider/job bindings, created at `2026-11-06T21:49:40.294617Z` after the original cutoff, request/job generation0, retry_count1 and max_attempts1. The original rollout had exactly two reservations, matching only these two jobs, and unchanged cutoff/expiry/max10/source. All seven protected historical prestate counts/digests remained unchanged.

At that observation Bankone was `completed`, canonical/available with published=true and one succeeded rewrite attempt; Banktwo was `processing/rewriting`, source/available with one dispatched attempt. These are metadata observations, not a complete end-to-end acceptance claim: Banktwo terminal outcome and canonical revision validation/UNREVIEWED/publication-event/no-review binding still require independent proof. No additional work or retry follows from this outcome record.

Independent terminal DB receipt `monitor-02.json` at `2026-11-06T21:51:01.273022Z` has SHA256 `d3a5088ff16f6375f87d53f19211883c1cd5e46023e0f6dcab1a841bd749346d`:

- Bankone completed automatically with exactly one succeeded Mercury-3 rewrite attempt (`full-prose-auto-v1`). Current canonical revision `1f70613e-f5e2-47f0-a625-8eed88ff425a` was published at `2026-11-06T21:50:03.332078Z`, with nonempty canonical/source bodies, validation passed, `UNREVIEWED`, matching source/transformation/current-publication-event bindings and zero human reviews. Its recorded `complete_rewrite` is `false`; publication does not establish full-rewrite quality.
- Banktwo reached `dead_letter` / `REWRITE_RESPONSE_INVALID` after exactly one failed Mercury-3 attempt completed at `2026-11-06T21:50:31.497295Z`. It has no canonical revision/publication and retains an available nonempty source fallback. No retry or reset is authorized.
- Both reservations remain consumed within the original ten-job cap, and all seven historical prestate counts/digests are unchanged. The observer alerted the coordinator to the failure/stop boundary; this documentation task performs no runtime control.

This is one verified automatic UNREVIEWED publication and one bounded failed rewrite with readable source fallback. It is not a two-bank publication success, a quality acceptance, or permission for another identity/attempt.

The coordinator then performed the gate-required single disable+stop. Private `failure-stop.json` SHA256 `cb595dfc9f53373fa6d803fc5e1b3efed93e4c5ddfe2601cf4b907b0da0022e9` reports verified=true, original reservations2 retained and no worker container. No rerun followed.

Metadata-only `banktwo-failure-diagnostics.json` SHA256 `8480327ac277fd701b13e493bec28fabd47eda82d8f72d5b2591b57f1ecdcc08` narrows the failure to `MERCURY_OUTPUT_TRUNCATED`, stage `finish`, `finish_reason=length`, max_output_tokens32768, retryable=false and no next attempt. No source/model content is recorded here. The worker is stopped with the two consumed reservations; further work requires separate authorization.
