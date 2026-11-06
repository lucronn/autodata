# Catalog-Only Index Consumer

Goal: Restore durable production catalog browsing with a catalog-only consumer that polls existing eligible index jobs and dispatches only their exact UUIDs without consuming article work or model quota.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8, dedicated `Catalog index consumer reference` field. Plan `docs/superpowers/plans/2026-11-06-catalog-index-consumer.md`; canonical `docs/operations/catalog-index-worker.md`; record `docs/agents/records/2026-11-06-catalog-index-consumer.json`. Planning base is merged master `29c90d9ab5c6d008231f8e94f063d7aea7df1ee0`; PR355 remains independent.

## Concrete todo record

- [ ] Implement catalog-only eligible UUID selection and serial exact-job dispatch to the existing lifecycle worker with model_client=None, two-second idle polling, --once and SIGTERM stop between jobs; never dispatch an unfiltered job.
- [ ] Prove selection, due/expired/exhausted handling, exact fencing and article/model non-interference with focused unit and real PostgreSQL17 catalog tests; run relevant existing checks and required CI.
- [ ] Add an initially inert preview service template and minimal operator documentation using the existing pinned image, immutable source, least-privilege DB/S3/source environment and existing catalog persistence/lease behavior.
- [ ] Commit and independently review exact code/test/unit evidence, synchronize Issue186/Project8 and operator outcome; require a separate exact-source runtime gate before install/start or live catalog enumeration.

## Fixed implementation

Add only `workers/ingestion-python/src/autodata_ingestion/catalog_index_worker.py`, `workers/ingestion-python/tests/test_catalog_index_worker.py`, focused additions to `workers/ingestion-python/tests/test_catalog_coverage.py`, and `infra/deploy/preview/autodata-catalog-index-worker.service`; evidence updates to this plan/record/operator doc are allowed. Do not modify lifecycle/claim/persistence/schema/connectors/article worker/API/UI/compose or PR355 files.

The new wrapper selects at most one UUID by joining source_fetch_jobs j to catalog_article_provider_scopes s on j.catalog_provider_scope_id=s.catalog_provider_scope_id: j.job_kind=catalog_index, provider bankone/banktwo, s.current_job_id=j.source_fetch_job_id, s.generation=j.request_generation and matching provider/scope binding. Eligible jobs are due pending/failed with retry_count<max_attempts, or expired processing (including exhausted processing requiring existing cleanup). Exclude completed/dead_letter/needs_review and future retries; order oldest created_at then UUID. Use DB clock and existing lease/attempt rules; selection is read-only, closes its transaction before any connector/S3 I/O. Call existing run_article_worker_once(repo,worker_id=...,registry=...,object_store=...,model_client=None,job_id=EXACT_UUID). No candidate means no dispatch; never job_id=None or a generic drain. Existing atomic claim/lease fencing handles races and heartbeat. Do not claim in a separate custom path, change retries or reset a job.

Loop serially, waiting2s when idle/no claim, with --once for at most one selected dispatch and SIGTERM/SIGINT stop before the next selection/dispatch. Build only existing DB/S3/source clients; no model client/import/secret required. Validate explicit HTTP(S) S3 URL consistently with the reviewed runtime client; missing/invalid prerequisites fail closed with content-free diagnostics. Preserve existing catalog resolution/page/checkpoint/descriptor/membership behavior. Enumeration can take up to1000 pages and connector calls can take25s each; signal requests stop between jobs and does not promise a per-job wall deadline. Operator stop is bounded by service timeout/termination and existing leases recover abandoned work; do not add pager/cancellation architecture here.

The preview unit is an uninstalled template, no Install target/boot enablement, Restart=no; separate service/container name, unchanged image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4, host network, root/source read-only, cap-dropALL, no-new-privileges, explicit stop timeout70/systemd80. Root-only source config binds an immutable reviewed source path; separate root-only catalog env supplies only DB4, S3endpoint/access/secret/sourcebucket4, Bankone/Banktwo URLs/APIkeys4 and the two Python settings (14 names), never Inception/payment/admin/internal HTTP credentials. No article-worker state/quota mount or generic worker command. Installing/configuring/starting it is outside this implementation gate.

## Meaningful verification and release boundary

Focused tests must prove exact serialized/parameterized eligibility, no UUID-less fallback, no dispatch when empty, --once/serial/stop behavior and no model construction. Real PG17 tests must include an earlier pending article, expired/exhausted article, due/future catalog retries, terminal/stale scope generation/current_job bindings and competing claims. Only the exact eligible catalog UUID may be claimed/cleaned up; article job/attempt/checkpoint/lease rows, article model quota and stopped finite rollout remain unchanged. Exercise existing catalog processing with fake connector/S3 on both providers, proving descriptor/index-page persistence and normal checkpoint/completion without body/resource capture or model invocation. Existing catalog tests plus focused wrapper tests and required CI must pass; record exact source and review evidence.

This checkpoint permits implementation only after committed/pushed synchronized tracking and exact-base preflight plus coordinator dispatch. It does not install a service, touch secrets/runtime state, call live sources/model, create/refresh/drain catalog jobs, retry spent article work or alter finite article reservations. Live catalog browsing acceptance needs a separate synchronized runtime gate pinned to merged reviewed source/CI, explicit install/start/stop and honest provider/index results.

Tracking scope synchronized: https://github.com/lucronn/autodata/issues/186#issuecomment-6697016638; dedicated Project8 `Catalog index consumer reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho5QE4`). Exact committed pin/preflight precedes implementation dispatch.

## Preview runtime contract

`infra/deploy/preview/autodata-catalog-index-worker.service` is an inert template.
Do not install or start it under this implementation checkpoint. A separately
synchronized runtime gate must pin the merged reviewed source, passing CI, and
explicit operator install/start/stop scope before any live catalog work.

At that boundary, `/etc/autodata/catalog-index-worker.conf` must be root-owned
mode 0600 and contain only `AUTODATA_CATALOG_INDEX_SOURCE`, an absolute immutable
checkout path at the approved full commit. Verify the checkout's commit and
cleanliness before starting; the worker does not attest that path itself.
The unit bind-mounts that source read-only using the existing pinned runtime
image. It has no writable article rollout/quota mount, boot target or restart.

The separate root-owned mode 0600 `/etc/autodata/catalog-index-runtime.env` has
exactly these 14 variable names, populated from managed runtime configuration:

```
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
PYTHONDONTWRITEBYTECODE
PYTHONPATH
```

Set `PYTHONDONTWRITEBYTECODE=1` and
`PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python`.
Use an explicit HTTP(S) origin for `AUTODATA_S3_ENDPOINT` (an optional trailing
slash is accepted; userinfo, query, fragment and other paths are rejected).
Both provider URL/canonical key pairs are required by this dedicated runtime.
This intentionally stricter admission does not accept legacy `BANKONE_API_TOKEN`
or `BANKTWO_API_TOKEN` aliases; operators map existing managed credentials to the
canonical names above. Do not add model, payment, admin, internal HTTP or finite
article-worker state credentials to this file. Diagnostics contain only
`CATALOG_INDEX_WORKER_BLOCKED` and exit 1 when configuration or execution fails.

For a separately gated bounded dispatch, append `--once` to the Python command;
it attempts at most one selected UUID and exits 0 for an empty queue or lost
claim. Continuous operation polls serially and waits 2s after an empty selection
or lost claim. It never creates catalog jobs or dispatches without an exact UUID.

SIGTERM/SIGINT requests stop before the next selection/dispatch. An already
running catalog job continues its existing heartbeat and may enumerate 1000
pages with 25s connector calls, so there is no per-job wall deadline. The unit's
`docker stop --time 70` terminates a still-running container after its grace
period; systemd allows 80s for stop. Existing 90s leases recover abandoned jobs;
expired jobs with exhausted attempts are cleaned up through the existing exact
claim path. Operators must inspect provider coverage and errors after recovery;
a successful process exit does not prove complete live catalog browsing.
