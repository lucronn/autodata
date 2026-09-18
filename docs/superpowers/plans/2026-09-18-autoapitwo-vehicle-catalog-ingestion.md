# AutoAPItwo Vehicle Catalog Ingestion Plan

> **For agentic workers:** follow the canonical pre-implementation gate in
> `docs/agents/pre-implementation-gate.md` before modifying implementation
> files. This plan is the single implementation scope for this feature.

**Goal:** Ingest AutoAPItwo's vehicle vocabulary once as the application is
used—years, makes, models, engines, and the provider vehicle identity needed
for later lookups—then serve the selector and natural-language vehicle linking
from AutoData's durable database without repeating upstream catalog calls.

**Architecture:** Add a durable, resumable catalog-sync job behind the existing
Go selector endpoint. The endpoint returns already persisted data immediately
and schedules one idempotent sync when the catalog is empty or its configured
source version has not completed. The Python ingestion worker walks only
AutoAPItwo fleet vocabulary and summary vehicle endpoints; it does not fetch
repair articles, PDFs, images, or procedures during this catalog warm-up.

**Issue:** https://github.com/lucronn/autodata/issues/106

**Implementation:** `59d36bc9aef6080b584e01808140270d7a782aa4`

**CI:** [Autonomous Verification run 35385479339](https://github.com/lucronn/autodata/actions/runs/35385479339) passed.

**Project:** https://github.com/users/lucronn/projects/8

**Canonical contract:** `docs/architecture/vehicle-catalog-ingestion.md`

## Decisions

- The source is the configured `AUTODATA_AUTOAPITWO_BASE_URL`, defaulting to
  `https://autoapitwo.vercel.app`.
- The traversal uses AutoAPItwo's documented fleet surface:
  `/api/v1/fleet/years`, `/years/{year}/makes`,
  `/years/{year}/makes/{make}/models`,
  `/years/{year}/makes/{make}/models/{model}/engines`, and the YMME `car`
  endpoint with `scope=summary` when a provider vehicle identity is required.
- The sync stores source/provider IDs and raw response evidence, then maps
  normalized observations into the existing vehicle identity base,
  configuration, alias, and provider-mapping tables. AutoAPItwo identifiers
  are external keys, not replacements for AutoData's own stable vehicle IDs.
- The sync is catalog-only. Article/content endpoints are not called by this
  job; article ingestion remains a separate request-driven path.
- A source-version and traversal-version watermark makes a completed catalog
  idempotent. Duplicate delivery upserts the same base/configuration/provider
  mapping and never creates duplicate vehicles.
- API reads never wait for the sync. An empty or partial catalog is returned
  with readiness metadata while the worker continues in the background.
- Upstream failures are retried with bounded backoff, checkpointed by scope,
  and eventually dead-lettered for explicit replay. A partial catalog remains
  usable and is never deleted because one branch failed.

## Implementation tasks

### Task 1: Add the durable catalog-sync contract

**Files:** a new migration under `db/migrations/`, Go persistence and API
tests, and the canonical contract document.

- [x] Add a `vehicle_catalog_syncs` job/state table keyed by provider,
  source-version, and traversal-version, with status, checkpoint, counts,
  attempts, error, and timestamps.
- [x] Add a per-scope checkpoint table or JSON checkpoint with unique scope
  keys for year, make, model, engine, and summary-car resolution.
- [x] Add the minimum provider/source fields needed for deterministic upserts
  and expose selector readiness without exposing upstream credentials.
- [x] Define status values `pending`, `running`, `completed`, `partial`,
  `failed`, and `dead_letter`; document retry and replay rules.

### Task 2: Implement the AutoAPItwo catalog adapter

**Files:** `workers/ingestion-python/src/autodata_ingestion/`, focused worker
tests, and configuration documentation.

- [x] Add typed traversal methods for years, year makes, year/make models,
  model engines, and summary YMME car resolution.
- [x] Validate same-origin HTTPS responses, redirects, response size, schema
  shape, retry limits, and provider rate limits before persistence.
- [x] Persist a source snapshot/evidence path for the catalog batch
  and retain the response hash, endpoint, parameters, source version, and
  fetched timestamp.
- [x] Normalize provider labels and engines through the existing vehicle
  identity normalizer; retain raw labels and AutoAPItwo IDs for audit and
  future natural-language alias matching.

### Task 3: Connect on-demand scheduling to selector reads

**Files:** Go selector/API boundary, ingestion HTTP/worker boundary, tests,
and Compose environment configuration.

- [x] Make `GET /vehicle-identities/selectors` return persisted years, makes,
  models, engines, provider mappings, and a catalog readiness object.
- [x] When the configured catalog source is not complete, enqueue exactly one
  idempotent sync for the source/version and return immediately with current
  data plus `sync_status`.
- [x] Ensure concurrent selector requests coalesce to the same sync job and
  that a completed source/version does not call AutoAPItwo again.
- [x] Preserve the existing memory-store behavior in unit tests and provide
  deterministic fake AutoAPItwo responses for local integration tests.

### Task 4: Make the dashboard consume the durable catalog

**Files:** dashboard selector contract/tests and minimal UI only where needed.

- [x] Keep the current decade → year → make-letter → make flow.
- [ ] Add model and engine selection only after the selected make, using the
  already returned persisted catalog rather than per-click upstream calls.
- [ ] Show a small, non-blocking catalog status message when the worker is
  warming the catalog; never hide available persisted options while syncing.

### Task 5: Verify one-time behavior and delivery tracking

- [x] Test cold selector access schedules one sync and returns without waiting.
- [x] Test duplicate/concurrent selector access creates one job at the database
  claim boundary.
- [ ] Test a second access after completion makes zero AutoAPItwo calls.
- [ ] Test resume after a failed year/make/model branch and dead-letter replay.
- [x] Test duplicate provider rows converge to one canonical base/configuration
  while retaining source evidence and provider mappings.
- [x] Exercise the browser against the local Compose stack and verify years,
  makes, models, and engines remain available after the upstream is disabled.
- [x] Record the verified implementation SHA, browser evidence, CI run, Issue,
  and Project item here and in the canonical document.

## Non-goals

- Do not ingest every individual repair article, procedure, PDF, image, or
  diagram during catalog warm-up.
- Do not replace AutoData vehicle IDs with ACES or AutoAPItwo IDs.
- Do not make the dashboard block on upstream traversal.
- Do not add an LLM to deterministic catalog traversal or vehicle identity
  persistence.

## Self-review checklist

**todo:** implement and verify the durable, catalog-only AutoAPItwo warm-up.

- [x] No duplicate catalog sync jobs for the same source/version.
- [x] No duplicate canonical vehicles or configurations after replay.
- [x] Every persisted provider fact has source snapshot and evidence metadata.
- [x] The selector returns usable cached data while synchronization runs.
- [ ] A completed sync makes no repeated AutoAPItwo catalog calls.
- [x] Article/content endpoints are not called by catalog warm-up.

## Current verification boundary

The first local warm-up was observed as `running` with two attempts while the
dashboard remained usable. The implementation intentionally does not claim
that the complete remote fleet traversal has finished until the durable sync
row reaches `completed`. Model/engine selection controls and post-completion
zero-call verification remain follow-up work. The current implementation
persists bounded batches and scope rows as traversal progresses, so partial
catalog data is available before the full remote fleet completes.
