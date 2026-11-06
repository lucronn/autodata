# Draft: Catalog-Only Consumer Runtime Activation

Status: **UNSYNCHRONIZED DRAFT; NOT DISPATCHABLE**. Exact merge/CI and tracking are pending. No runtime action or operational script is authorized by this draft.

Goal: Activate the merged catalog-only consumer through a bounded initial proof of real index completion and two-bank browsing, without activating or modifying article rewriting.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Plan `docs/superpowers/plans/2026-11-06-catalog-index-runtime-activation.md`; canonical `docs/verification/2026-11-06-catalog-index-runtime-activation.md`; record `docs/agents/records/2026-11-06-catalog-index-runtime-activation.json`. Dedicated tracking field/comment **PENDING**.

## Concrete todo record

- [ ] Pin merged combined PR355 source/tree/archive/unit and successful required CI/review; synchronize exact tracking and machine preflight before runtime dispatch.
- [ ] Install the exact inert catalog unit and immutable merged source with a separate root-only14-name catalog environment; verify payload/import/configuration without live processing or secret output.
- [ ] After reviewed-script and coordinator dispatch, start the catalog-only service once and observe at most120 seconds, proving real current catalog_index job completion and two-bank browse results from a pinned authentic configuration.
- [ ] Record exact source/container/job/provider/index/readiness evidence and article non-interference; stop/disable on failure or uncertain proof, preserving checkpoints/history and leaving the separate article rollout untouched.

## Blocking pins and fixed installation

Combined PR355 https://github.com/lucronn/autodata/pull/355 head observed `b50948da68e2341a898b7137103e3aef208022c9`; required CI still running, merge SHA/tree/archive/unit hashes **PENDING**. Require strict merge of exact reviewed green head and no runtime source/unit drift. Exact committed synchronized gate/preflight, static script review/digest and coordinator dispatch **PENDING**.

Install only merged `infra/deploy/preview/autodata-catalog-index-worker.service` as `/etc/systemd/system/autodata-catalog-index-worker.service`; immutable root-owned source `/opt/autodata/catalog-index-worker/<MERGED_SHA>/source`; root0600 `/etc/autodata/catalog-index-worker.conf` containing only AUTODATA_CATALOG_INDEX_SOURCE; root0600 `/etc/autodata/catalog-index-runtime.env`; unique root0700 evidence directory (exact path **PENDING**). Fail on unexpected existing paths rather than overwrite. Reuse image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4, exact unit host-network/read-onlyroot+source/capdropALL/no-new-privileges/stop70/TimeoutStop80/Restartno/containername. No Install target: no boot enablement. No state mount or source substitution.

Privately select only14 names from the already corrected approved worker environment: DB AUTODATA_DB_ADDRESS/AUTODATA_POSTGRES_DB/AUTODATA_POSTGRES_USER/AUTODATA_POSTGRES_PASSWORD; S3 AUTODATA_S3_ENDPOINT/AUTODATA_S3_ACCESS_KEY/AUTODATA_S3_SECRET_KEY/AUTODATA_SOURCE_BUCKET; BANKONE_BASE_URL/AUTODATA_BANKONE_API_KEY/BANKTWO_BASE_URL/AUTODATA_BANKTWO_API_KEY; PYTHONDONTWRITEBYTECODE/PYTHONPATH. Preserve values; explicit valid S3 HTTP(S) URL; Python1 and fixed /app source/contracts path. Reject duplicates/extras/missing/newlines; validate private file modes and equality without printing values. No model/payment/internalHTTP/admin credentials, env change, source connector configuration repair, package install, migration or HTTP/API restart.

Before any processing, verify exact disabled/stopped new-article rollout with its two spent reservations and terminal jobs unchanged; snapshot article jobs/attempts/leases/checkpoints/revisions plus separate state bytes/hash. Verify canonical public readiness and purchase disabled using TLS verification/no redirects/User-Agent curl/8.0.0. Install inert unit/config/source/env, run systemd-analyze verify and only networknone --help/import proof with pinned image; daemon-reload permits discovery but does not start processing. No source/model/body call or catalog creation during this stage.

## Initial live proof and failure stop

Before dispatch pin one authentic user-selected configuration and both current Bankone/Banktwo catalog scope/job UUIDs, generation and baseline counts; exact identifiers **PENDING**. Existing user browsing/API catalog ensure may create the normal two catalog_index jobs only if explicitly included in the synchronized successor, with no fabricated reference, refresh/reset/page drain or manual descriptor insertion. Do not declare success from old populated descriptors: require a real current job transition to completed and corresponding new/verified persisted index-page/source binding, plus provider rows in normal authenticated `/v1/catalog/vehicles/<configuration>/articles` browse. Record safe IDs/counts/statuses, never opaque refs/source content/credentials.

After independently reviewed exact script, synchronized gate and explicit coordinator dispatch, start this service once; inspect exact source/image/unit/environment/security/singleton and no generic/article worker. It serially polls only eligible current catalog UUIDs and dispatches existing lifecycle with model_clientNone. Observe at most120s with bounded metadata/health reads; both-provider completion/browse population must be truthful (partial/no-match/provider failure are not two-bank success). Existing jobs may run1000pages/25srequests: observation timeout does not prove a per-job deadline. This catalog consumer can process other eligible catalog jobs during its initial window; it cannot call a model or claim article jobs.

Failure, unexpected payload/article mutation, provider errors or incomplete/uncertain proof requires systemctl stop within80s plus stopped/no-container verification<=15s, using an independent recovery budget and bounded hard request/process deadlines; verify no boot enablement. Preserve checkpoint/attempt history; no reset/retry/refresh/restore. On fully proved healthy initial acceptance the coordinator may retain this dedicated catalog service running under the same catalog-only scope; it still has Restartno/no boot target, and ongoing operation is reported explicitly. No article service enable/start/state/archive/config/quota operation is permitted.

## Synchronization boundary

Replace pending merged identities, proof scope/jobs, evidence paths and reviewed script bindings; append Issue186 and a dedicated Project8 field preserving prior fields/history; commit/push synchronized record and pass machine preflight at that exact SHA. Until then this is planning only. No new implementation or separate new-article proof state may be touched.
