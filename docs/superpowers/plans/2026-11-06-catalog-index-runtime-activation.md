# Draft: Catalog-Only Consumer Runtime Activation

Status: **UNSYNCHRONIZED DRAFT; NOT DISPATCHABLE**. Exact merge/CI and tracking are pending. No runtime action or operational script is authorized by this draft.

Goal: Activate the merged catalog-only consumer through a bounded initial proof of real index completion and two-bank browsing, without activating or modifying article rewriting.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Plan `docs/superpowers/plans/2026-11-06-catalog-index-runtime-activation.md`; canonical `docs/verification/2026-11-06-catalog-index-runtime-activation.md`; record `docs/agents/records/2026-11-06-catalog-index-runtime-activation.json`. Dedicated tracking field/comment **PENDING**.

## Concrete todo record

- [ ] Pin merged combined PR355 source/tree/archive/unit and successful required CI/review; synchronize exact tracking and machine preflight before runtime dispatch.
- [ ] Install the exact inert catalog unit and immutable merged source with a separate root-only14-name catalog environment; verify payload/import/configuration without live processing or secret output.
- [ ] After reviewed-script and coordinator dispatch, start the catalog-only service once and observe at most120 seconds, proving real current catalog_index job completion and two-bank browse results from the two pinned authentic configurations.
- [ ] Record exact source/container/job/provider/index/readiness evidence and article non-interference; stop/disable on failure or uncertain proof, preserving checkpoints/history and leaving the separate article rollout untouched.

## Blocking pins and fixed installation

Combined PR355 https://github.com/lucronn/autodata/pull/355 head observed `b50948da68e2341a898b7137103e3aef208022c9`; required CI still running, merge SHA/tree/archive/unit hashes **PENDING**. Require strict merge of exact reviewed green head and no runtime source/unit drift. Exact committed synchronized gate/preflight, static script review/digest and coordinator dispatch **PENDING**.

Install only merged `infra/deploy/preview/autodata-catalog-index-worker.service` as `/etc/systemd/system/autodata-catalog-index-worker.service`; immutable root-owned source `/opt/autodata/catalog-index-worker/<MERGED_SHA>/source`; root0600 `/etc/autodata/catalog-index-worker.conf` containing only AUTODATA_CATALOG_INDEX_SOURCE; root0600 `/etc/autodata/catalog-index-runtime.env`; unique root0700 evidence directory (exact path **PENDING**). Fail on unexpected existing paths rather than overwrite. Reuse image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4, exact unit host-network/read-onlyroot+source/capdropALL/no-new-privileges/stop70/TimeoutStop80/Restartno/containername. No Install target: no boot enablement. No state mount or source substitution.

Privately select only14 names from the already corrected approved worker environment: DB AUTODATA_DB_ADDRESS/AUTODATA_POSTGRES_DB/AUTODATA_POSTGRES_USER/AUTODATA_POSTGRES_PASSWORD; S3 AUTODATA_S3_ENDPOINT/AUTODATA_S3_ACCESS_KEY/AUTODATA_S3_SECRET_KEY/AUTODATA_SOURCE_BUCKET; BANKONE_BASE_URL/AUTODATA_BANKONE_API_KEY/BANKTWO_BASE_URL/AUTODATA_BANKTWO_API_KEY; PYTHONDONTWRITEBYTECODE/PYTHONPATH. Preserve values; explicit valid S3 HTTP(S) URL; Python1 and fixed /app source/contracts path. Reject duplicates/extras/missing/newlines; validate private file modes and equality without printing values. No model/payment/internalHTTP/admin credentials, env change, source connector configuration repair, package install, migration or HTTP/API restart.

Before any processing, verify exact disabled/stopped new-article rollout with its two spent reservations and terminal jobs unchanged; snapshot article jobs/attempts/leases/checkpoints/revisions plus separate state bytes/hash. Verify canonical public readiness and purchase disabled using TLS verification/no redirects/User-Agent curl/8.0.0. Install inert unit/config/source/env, run systemd-analyze verify and only networknone --help/import proof with pinned image; daemon-reload permits discovery but does not start processing. No source/model/body call or catalog creation during this stage.

## Initial live proof and failure stop

Before dispatch recheck the two pinned authentic configurations below, then record the at-most four current Bankone/Banktwo catalog scope/job UUIDs returned by the two explicitly authorized normal ensures, generation and baseline counts. No fabricated reference, refresh/reset/page drain or manual descriptor insertion is allowed. Do not declare success from old populated descriptors: require a real current job transition to completed and corresponding new/verified persisted index-page/source binding, plus provider rows in normal authenticated `/v1/catalog/vehicles/<configuration>/articles` browse. Record safe IDs/counts/statuses, never opaque refs/source content/credentials.

After independently reviewed exact script, synchronized gate and explicit coordinator dispatch, start this service once; inspect exact source/image/unit/environment/security/singleton and no generic/article worker. It serially polls only eligible current catalog UUIDs and dispatches existing lifecycle with model_clientNone. Observe at most120s with bounded metadata/health reads; both-provider completion/browse population must be truthful (partial/no-match/provider failure are not two-bank success). Existing jobs may run1000pages/25srequests: observation timeout does not prove a per-job deadline. This catalog consumer can process other eligible catalog jobs during its initial window; it cannot call a model or claim article jobs.

Failure, unexpected payload/article mutation, provider errors or incomplete/uncertain proof requires systemctl stop within80s plus stopped/no-container verification<=15s, using an independent recovery budget and bounded hard request/process deadlines; verify no boot enablement. Preserve checkpoint/attempt history; no reset/retry/refresh/restore. On fully proved healthy initial acceptance the coordinator may retain this dedicated catalog service running under the same catalog-only scope; it still has Restartno/no boot target, and ongoing operation is reported explicitly. No article service enable/start/state/archive/config/quota operation is permitted.

## Synchronization boundary

Replace pending merged identities, proof scope/jobs, evidence paths and reviewed script bindings; append Issue186 and a dedicated Project8 field preserving prior fields/history; commit/push synchronized record and pass machine preflight at that exact SHA. Until then this is planning only. No new implementation or separate new-article proof state may be touched.

## Read-only scheduling audit and exact ordinary requests

Audit2026-11-06T22:17:18Z found zero catalog_index jobs, both source /healthz endpoints200 without body/auth reads, pinned image present and all14 selected env names present in root0600 corrected18-name worker env. Old article rollout is disabled/reservations2, with no article/catalog worker container. Installation alone cannot prove catalog processing.

Configuration c54c88f0-5d0a-5f45-979b-6804a08bad1f (vehicle97d830df-987c-5db3-bcba-2d7b83fec4ac) has only stored Bankone partial scope58dc3a89-bc5b-49ca-a76f-db09a37cea0e, resolution10d897d6-4625-5d45-9f0c-6e3e3f01a39c/indexd1201595. Configuration cf544dfd-4570-589f-b3b4-23487d14e591 (vehicled7344e42-c5f6-5ec1-b9e3-9352e6b41336) has only Banktwo partial scope5d144da1-8887-4070-9bc5-cd7fbd2c501d, resolution35d577c2-085a-5b79-8870-04412bcf8b53/index2c3765ac. Both generation0/current_job_idNULL/row_count1; no verified car mapping proves shared-bank coverage. Use these two genuine configurations; do not invent a shared configuration.

After merged synchronization and explicit coordinator dispatch ONLY, authorize exactly one normal ensure per configuration, at most TWO HTTP requests and FOUR returned catalog job UUIDs total. Existing ensure_article_catalog_jobs always loops both providers; a provider field cannot narrow it. Requests use POST http://127.0.0.1:3031/v1/catalog/ensure, Content-Type application/json, Accept application/json, matching Idempotency-Key header and body key, and X-Autodata-Internal-Token read in-memory from the exact approved running HTTP service (38f3bc41...); token presence/address3031 verified without output. No owner/Firebase token is required by this internal scheduling boundary. Never persist/log that token, clone it into catalog env, call article scope, or manually insert/change jobs. Exact JSON bodies:

```json
{"idempotency_key":"catalog-hydration:ce2b2655338caa7adba056c3","scope":"articles","vehicle_id":"c54c88f0-5d0a-5f45-979b-6804a08bad1f"}
```

```json
{"idempotency_key":"catalog-hydration:7331b0c74ede374656132a8a","scope":"articles","vehicle_id":"cf544dfd-4570-589f-b3b4-23487d14e591"}
```

Bound each request to5s hard wall clock, no redirects or automatic retry; require202/200 and exactly one returned bankone UUID plus one banktwo UUID per request. Record all returned UUIDs and verify real catalog kind/current-scope/generation/configuration in DB before starting. Reuse current jobs if already scheduled; unexpected drift/cardinality/uncertain response stops the attempt rather than resending/resetting. The existing boundary performs durable SQL scheduling only, no source/body/model call.

Public authenticated GET /v1/catalog/vehicles/<configuration>/articles uses dataset_viewer auth when paid catalog mode is off and auto-schedules the same ensure if progressmissing/incomplete; paid mode does not auto-schedule. Root service auth can schedule directly; actual browse acceptance still uses existing authorized browser/API auth, never forged owner roles. Perform final browse GETs only after the four scope jobs are completed/coveragecomplete, so they do not cause an unplanned ensure. Expected known-bank descriptors must appear across the two genuine configurations; opposite-bank no-match is recorded honestly. Provider errors/timeout/incompletecoverage are partial failure, requiring stop, not a claimed two-bank success. This amendment is still unsynchronized planning; no request has been executed.
