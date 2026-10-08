# Independent Bankone and Banktwo Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Move all upstream-specific behavior into the independent Bankone and Banktwo repositories, and leave AutoData consuming them through stable HTTP APIs on separate subdomains.

**Architecture:** The banks expose a versioned provider-neutral source API and own parsing, upstream access, auth, caching, retries, assets, and their deployments. AutoData uses generic HTTP clients and keeps canonical identity, source snapshots, normalization, provenance, persistence, review, and product behavior. Each bank serves its own direct subdomain; neither bank calls or routes to the other. The public wire slugs `bankone` and `banktwo` map to persisted AutoData provider values `autoapi` and `autoapitwo` respectively.

**Tech Stack:** Go API, Python 3.12+ ingestion/enrichment workers, TypeScript/Fastify connector services, OpenAPI 3, PostgreSQL, NATS JetStream, MinIO, Docker, Vercel/Kubernetes deployment configuration.

**Spec:** `docs/superpowers/specs/2026-10-08-independent-bank-connectors-design.md`

**Issue:** https://github.com/lucronn/autodata/issues/132

**Project:** https://github.com/users/lucronn/projects/8

**Concrete todo:**
- Freeze and test the provider-neutral v1 HTTP contract.
- Move provider-specific API behavior into independently deployable Bankone and Banktwo repositories.
- Replace AutoData-specific adapters with generic HTTP clients and preserve stored identity/provenance.
- Migrate source fetch jobs additively and preserve in-flight work/idempotency.
- Deploy direct bank subdomains, remove cross-bank routing and AutoData build coupling, and canary both APIs.

## Global Constraints

- Canonical origins are `https://bankone.cars.tk` and `https://banktwo.cars.tk`; detach the apex `cars.tk` from Banktwo.
- Public `source.provider` values are `bankone` and `banktwo`; preserve stored `autoapi` and `autoapitwo` identifiers through an explicit AutoData mapping.
- Contract version is `/v1`; health and readiness routes are `/healthz` and `/readyz`.
- AutoData remains the only owner of canonical persistence, source provenance, normalized records, and public product APIs.
- Neither bank imports AutoData modules, accesses AutoData databases/object storage, or calls the other bank.
- Preserve legacy source identifiers, snapshot locators, article IDs, database migration history, and idempotency keys.
- Do not route production traffic until the independent service contracts and nonproduction canaries pass.
- Preserve all pre-existing dirty files in AutoData and Banktwo. Use isolated clean clones/worktrees and port only task-owned changes.

## Review Focus

- Ambiguous YMME resolves to explicit candidate choices; it never silently chooses a source vehicle.
- Partial catalog pages preserve `complete=false` and continuation tokens through retries and replay.
- Unauthorized, rate-limited, oversized, redirected, and malformed upstream responses never leak tokens or raw provider errors.
- Provider article ordering, labor links, HTML, image bytes, and hashes remain attributable to the selected opaque resource.
- Existing `autoapi*` provider keys and in-flight job rows stay readable during cutover and rollback.

---

### Task 1: Freeze the provider-neutral source contract

**Files:**
- Create: `packages/contracts/source-connector/v1/openapi.yaml`
- Create: `packages/contracts/source-connector/v1/fixtures/`
- Modify: `packages/contracts/contract.json`
- Test: `scripts/contracts/test_source_connector_contract.py`

**Interfaces:**
- Produces `SourceEnvelopeV1`: request ID; source provider/revision/fetched timestamp; scope; item list; page completeness and optional cursor.
- Produces common operations: capabilities, catalog scope read, vehicle resolution, article list/search, opaque resource read.
- Errors use stable codes for invalid input, not found, ambiguous, unauthorized, rate limited/retryable, unavailable, and invalid upstream response.

- [ ] Write fixture tests for complete and partial pages, ambiguous resolution, article/labor links, text resources, binary resources, and stable error envelopes.
- [ ] Run `python3 -m pytest scripts/contracts/test_source_connector_contract.py -q`; confirm missing/malformed schemas fail validation.
- [ ] Add the OpenAPI v1 schema and representative redacted fixtures; disallow provider credentials, raw cookies, and direct DB identifiers.
- [ ] Run the contract test and the existing cross-language contract suites.
- [ ] Commit the contract independently.

### Task 2: Make Bankone implement the contract and own its subdomain

**Files (Bankone repository):**
- Modify: `src/routes/api-routes.ts`, `src/openapi.ts`, `src/config.ts`, `src/server.ts`
- Modify/create: `src/source-contract/` for candidate/resource projection
- Test: `tests/integration/` and `tests/unit/`
- Modify: `.github/workflows/` and deployment configuration as required

**Interfaces:**
- `GET /v1/capabilities`
- `GET /v1/catalog/{scope}` with typed YMME filters, cursor, source revision, and completeness
- `POST /v1/vehicle-resolutions`
- `GET /v1/vehicles/{opaqueRef}/articles` and `POST /v1/vehicles/{opaqueRef}/article-search`
- `GET /v1/resources/{opaqueRef}` returning source envelope plus original text/binary payload and SHA-256
- `GET /healthz`, `GET /readyz`

- [ ] Add conformance tests importing the versioned schema/fixtures as test data only; verify ambiguity and pagination semantics.
- [ ] Implement Bankone projections using existing provider routes, auth, session manager, content normalization, and asset proxy. Keep all upstream access inside Bankone.
- [ ] Run `npm ci && npm test && npm run lint && npm run build` from a clean Bankone checkout.
- [ ] Configure direct `bankone.cars.tk` deployment and runtime-managed secrets; verify unauthenticated/authorized behavior and signed asset retrieval without exposing credentials.
- [ ] Commit and independently release a nonproduction Bankone API.

### Task 3: Make Banktwo implement the contract and own its subdomain

**Files (Banktwo repository):**
- Modify: `src/routes.ts`, `src/upstream-client.ts`, `src/public-links.ts`, `src/config.ts`, `src/server.ts`
- Test: `tests/service.test.ts`, `tests/config.test.ts`, new contract conformance tests
- Modify: `.github/workflows/`, `vercel.json`, deployment configuration as required

**Interfaces:** same Source Connector HTTP operations and health routes as Task 2.

- [ ] Start from a fresh Banktwo remote worktree/clone. Inventory and preserve its current dirty nested checkout; do not overwrite or copy its unreviewed changes without reconciliation.
- [ ] Add contract fixtures and tests for pagination, resolution ambiguity, selected articles, labor relationships, binary resources, errors, and output-size limits.
- [ ] Implement the contract over the existing bounded GET-only upstream client; remove `MOUNT_PATH=/banktwo` as a public deployment requirement and emit root-relative same-origin links.
- [ ] Remove `/bankone` rewrites and all Bankone project/domain references from the Banktwo deployment.
- [ ] Run `npm ci && npm test && npm run lint && npm run build` from the clean Banktwo checkout; publish and verify its independent nonproduction service at `banktwo.cars.tk`.
- [ ] Commit and independently release Banktwo without depending on Bankone.

### Task 4: Replace AutoData provider adapters with generic HTTP clients

**Files (AutoData):**
- Create: `workers/ingestion-python/src/autodata_ingestion/source_connector_client.py`
- Modify: `source_adapters.py`, `source_bundle.py`, `worker.py`, `knowledge_fallback_runtime.py`
- Modify: `catalog_service.py`, `catalog_sync.py`, `catalog_years.py`, `chat_service.py`, `procedure_images.py`
- Modify: `chat_intent.py`, `vehicle_identity_provider.py`, `procedure_normalize.py`, `job_plan.py`
- Modify Go: `apps/api-go/vehicle_identity_http.go`, `catalog_http.go`, `catalog_store.go`, `postgres_vehicle_identity.go`
- Test: matching ingestion and Go API tests

**Interfaces:**
- `SourceConnectorClient(base_url, token, timeout, max_bytes)` with `capabilities()`, `catalog(scope, selector, cursor)`, `resolve_vehicle(selector)`, `list_articles(source_vehicle_ref, cursor)`, `search_articles(source_vehicle_ref, query)`, `read_resource(resource_ref)`.
- Client methods return validated `SourceEnvelopeV1`; provider slugs are opaque metadata used only for persisted lineage/configuration.

- [ ] Write transport and call-site tests proving provider responses pass through the shared schema and source bytes/hash/locator survive conversion to `SourceResource`.
- [ ] Implement bounded HTTP(S), origin/path validation, no redirects, retry classification, response-size limits, bearer-token redaction, and typed errors.
- [ ] Replace all callers with a provider registry configured by `BANKONE_BASE_URL` and `BANKTWO_BASE_URL`; preserve user-facing selection/guide behavior and remove direct upstream URLs from AutoData runtime paths.
- [ ] Remove imports of `bankone_*` and `banktwo_*` modules after all call sites use the generic client; remove provider-specific Banktwo/Bankone parsing from Go and Python application layers.
- [ ] Run ingestion pytest suite, Go API tests, contract tests, and static checks.
- [ ] Commit AutoData client and call-site migration.

### Task 5: Move source-fetch persistence to provider-neutral AutoData jobs

**Files (AutoData):**
- Create: a forward-only migration adding generic source article-fetch jobs
- Modify: `workers/ingestion-python/src/autodata_ingestion/bankone_job_persistence.py` into a generic job-store module
- Modify: `bankone_batch.py` callers while migration is active
- Test: job persistence and migration tests

**Interfaces:**
- Generic job records contain provider slug, canonical vehicle reference, opaque source vehicle/article refs, idempotency key, status, retry count, and source snapshot IDs.
- Existing Bankone row UUIDs and idempotency keys map without regeneration.

- [ ] Add failing migration tests for fresh database, legacy in-flight rows, and duplicate replay.
- [ ] Add the generic table/indexes and an additive migration that copies/dual-reads legacy rows without dropping old tables.
- [ ] Move claim/success/failure/replay behavior behind the generic repository and preserve transaction locks.
- [ ] Run the migration, persistence, ingestion, and Go integration suites against fresh and upgraded databases.
- [ ] Commit the persistence migration independently; retain old tables for rollback.

### Task 6: Decouple local/deployed topology and cut over origins

**Files (AutoData):**
- Modify: `infra/compose/compose.yaml`, `infra/k8s/base.yaml`, `.env.example`, `README.md`
- Modify: Vercel domain assignments so `bankone.cars.tk` belongs to Bankone, `banktwo.cars.tk` belongs to Banktwo, and `cars.tk` is detached from Banktwo
- Modify: `services/banktwo` submodule/build references and `.gitmodules`
- Modify: connector/routing architecture docs and deployment config

**Interfaces:**
- AutoData runtime variables resolve directly to `https://bankone.cars.tk` and `https://banktwo.cars.tk` by default; deployments may set private service origins.
- Compose does not build, mount, or require either bank repository.

- [ ] Add Compose/config tests proving AutoData service definitions have no bank build context or startup dependency and each origin can be overridden independently.
- [ ] Remove Banktwo from the AutoData K8s workload and remove Banktwo image, credentials, submodule, and network alias from AutoData deployment config.
- [ ] Configure DNS/TLS/health checks and secrets separately for each subdomain; attach each subdomain directly to its own Vercel project and detach the apex `cars.tk` from Banktwo.
- [ ] Remove old shared path rewrites after all configured AutoData clients use subdomains; confirm no credential-forwarding proxy remains and old documented URLs are marked retired.
- [ ] Run Compose config, K8s schema/lint, and runtime readiness checks.
- [ ] Commit the topology cutover.

### Task 7: Canary each bank independently and remove old implementations

**Files:**
- Modify: `docs/architecture/source-connector-api-compatibility.md`, `docs/architecture/bankone-banktwo-domain-routing.md`, `README.md`
- Evidence: `docs/agents/evidence/`
- Tests: contract and semantic comparison harnesses

**Interfaces:** consume the independent v1 APIs and compare against the pre-cutover source fixtures.

- [ ] Run Bankone canary and compare vehicle candidates, catalog completeness, selected article/order, labor links, image bytes/hash, and provenance.
- [ ] Run Banktwo canary and compare the same behavior, including article ambiguity and composed guide output.
- [ ] Prove unauthorized, timeout, rate-limit, malformed response, partial pagination, replay, and rollback behavior for each service independently.
- [ ] Switch AutoData defaults, verify both domains and all affected product flows, then delete embedded provider parser/client modules and their imports.
- [ ] Run full worker, API, enrichment, contract, migration, service, and deployment-config checks. Record exact repository SHAs and evidence.
- [ ] Keep the legacy job table through the rollback window; schedule its removal as a later separately gated migration.
- [ ] Commit final docs/evidence and obtain independent contract, security, schema, reliability, and overall review.

## Delivery gate

Implementation starts only after this plan, spec, AutoData Issue/Project item, canonical document references, synchronized record, and machine preflight all point to the same base SHA. Each bank must be reviewed and released independently. No production rollout is authorized by this plan.


**Issue:** https://github.com/lucronn/autodata/issues/132
**Project:** https://github.com/users/lucronn/projects/8
