# Initial public selector safety

Issue: https://github.com/lucronn/autodata/issues/436
Project: https://github.com/users/lucronn/projects/8 itemPVTI_lAHOCSJ8cc4BiQ2BzhI01Rs.
Protected source base272aeeaad8399c305468e5d486cc391d7340f6a4. Live-data lane confirms no worker-source overlap; preserve configuration429 class/log/watchdog contract and article behavior. No live provider/service/DB mutation or PR merge.

Goal: bound initial years/makes/models resolution, not only later deepening, and prevent anonymous cache misses from expanding into uncharged descendant work. Cached complete result remains zero-dispatch. Include cold-cache years even though live62years currently avoid ensure.

Decision: one process-global active initial job; normalizedscope singleflight;6s global cooldown after release and30s per-scope cooldown after incomplete/failure. Shared child control across all providers/cursors/nested Banktwo404 label repair:12actual dispatch maximum,20smonotonic attempt including child startup,6sminimum interdispatch floor,1MiB/response,4MiBtotal response bytes,5000total response rows including repair enumeration. Counts are transport observations, never deduplicated away. With6sfloor20s atmost4dispatches normally fit;12 is independent upper guard. No automatic descendant deepening from public initial selector reads; existing explicit/background deepening helper/config/article controls retain their own contracts but are no longer scheduled here.

Own subprocess resolves selector only, without persistence. Parent uses bounded nonblocking stdin/stdout/stderr and absolute deadline, terminate/kill/reap only owned process group on DNS/header/trickle/hang. Child receives normalized request/deadline, reconstructs configured source clients, applies resource/input/output bounds, returns bounded JSON result; never raw exception/provider content in errors/logs. Parent checks deadline before any persistence/coverage. On expired/budget/error retain existing durable partial rows, return incomplete/deferred with retry metadata, never persist false complete/empty proof. Successfully returned partial rows may persist only inside the live budget. No new DB schema; statement/lock/connect time bounds for selector persistence must avoid late blocking writes without changing config/article defaults. No provider or model/content/article dispatch in tests.

Red-first tests: cached scopes zero provider work including coldyears; dispatch/byte/row/deadline/429 shared across providers and hidden Banktwo enumeration+retry; global active same/different scopes and cooldown; local owned child stalls representing DNS/header/trickle plus concurrent callers, bounded termination/reap/no descendant leak/no late persistence; truthful partial/incomplete state and no automatic deepening. Existing connector/article/config/deepening tests verify default optional hooks preserve unrelated contracts. Use synthetic/local loopback only. First commit failing tests, then implementation/green evidence. Root reviews resulting PR/head; no serving activation.

Implementation owned paths: new selector job/control module+tests, catalog_service.py integration, source_connector_client.py optional per-read limits/accounting. HTTP worker/Go changes only if necessary for honest budget metadata; no HTML/JS. PR434 untouched.

Concrete todo:
- Synchronize Issue436 Project8 plan canonical docs record and pinned preflight
- Write red-first shared budget admission cooldown nested repair and owned slow-network tests
- Implement initial years makes models owned child shared12requests20s1MiBpage4MiBtotal5000rows and6sdispatchfloor
- Admit one global active initial job with6sglobal and30sscope cooldown; no public descendant deepening
- Prevent expired jobs from provider dispatch or persistence; preserve existing partial rows and truthful completion
- Run focused plus existing selector connector catalog configuration regressions and open review PR without live calls or merge


Owning-boundary refinement before HTTP implementation: `/v1/catalog/ensure` currently dispatches years to `catalog_years.ensure_catalog_years`, whose separate daemon manifest thread defaults Banktwo endpoints and bypasses initial admission. Public years must use the same owned selector path as makes/models; retain the explicit legacy helper for non-public callers, but remove its automatic HTTP dispatch. Persist successful bounded years as provider-backed selector projections in `vehicle_catalog_years` (existing nullable source_snapshot_id), with the exact provider/version/page URI and a documented normalized-projection SHA256; no S3/article evidence creation. Persist makes/models only in their scoped marker. Parent uses connect_timeout1s, statement_timeout<=1s, lock_timeout250ms and deadline checks/reservation before write/commit. Provider/IPC has an absolute20s hard deadline; DB cleanup is separately driver/server bounded, never claimed to be an owned-process hard deadline. Body-byte bounds exclude headers; subprocess memory/deadline also covers HTTP parser work. Add red-first actual HTTP boundary, successful owned local connector, fake-DB transaction/deadline/rollback checks.


Years schema refinement: Go reads durable years rows directly and does not use a years scope marker. The marker schema requires an actual model_year; public unfiltered years therefore writes only the provider-backed normalized years projection and creates no placeholder/false years marker. No S3 snapshot is invented. Successful makes/models keep normal scoped provenance/selector rows. Tests assert this exact marker distinction.

Years provenance: initial-only provider mappings carry the exact page provider/source URI/version into bounded years upsert. Retain those real source fields; response_hash is explicitly the normalized selected-year projection SHA256, not a supplier-body hash. source_snapshot_id remains null; no fake snapshot or S3 write. Reject missing row/page binding instead of fabricating provenance.
