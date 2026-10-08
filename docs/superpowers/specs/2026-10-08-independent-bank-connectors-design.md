# Independent Bankone and Banktwo services

**Status:** Accepted for implementation planning
**Date:** 2026-10-08
**Scope:** Separate AutoData, Bankone, and Banktwo codebases and runtime ownership.

## Goal

Bankone and Banktwo must be independently understandable, buildable, testable, releasable, deployable, and operable without importing code, reading databases, sharing runtime secrets, or calling each other. AutoData consumes each bank over a stable, versioned HTTP contract and remains the application and system of record.

The initial boundary is three code repositories:

- `lucronn/autodata`: product API, application logic, source-neutral ingestion, canonical identity, normalization, provenance, review, storage, and persisted jobs.
- `lucronn/bankone`: Bankone-specific upstream access, authentication/session behavior, parsing, assets, and its read-only source API.
- `lucronn/banktwo`: Banktwo-specific upstream access, parsing, assets, and its read-only source API.

The canonical service origins are `https://bankone.cars.tk` and `https://banktwo.cars.tk`. Each subdomain points directly to its own bank project and serves its versioned API below `/v1`, with `/healthz` and `/readyz` probes. Neither bank routes traffic to the other, and no shared API gateway is required. The prior `cars.tk/bankone` and `cars.tk/banktwo` paths are retired after AutoData and approved consumers switch to the subdomains. Detach the `cars.tk` apex from the Banktwo project so domain ownership is not coupled to either bank. Do not retain a cross-domain credential-forwarding proxy.

## Current state established by repository inspection

Bankone and Banktwo GitHub repositories already exist. Bankone has a standalone Fastify/TypeScript service with upstream routing, authentication/session handling, HTML normalization, asset handling, tests, and a Vercel entrypoint. Its local clone is absent. Banktwo has a standalone TypeScript service in the `services/banktwo` Git checkout, with validated upstream transport, route dispatch, authentication, caching, retries, and tests. The local Banktwo checkout is dirty and behind its remote; the AutoData parent currently does not track `services/` or `.gitmodules` at HEAD.

AutoData still has substantial provider-specific implementation in `workers/ingestion-python/src/autodata_ingestion`: `bankone_connector.py`, `bankone_batch.py`, `bankone_job_persistence.py`, `banktwo_connector.py`, `banktwo_http_client.py`, `banktwo_catalog.py`, and `banktwo_guide.py`. Callers in `worker.py`, `knowledge_fallback_runtime.py`, `catalog_service.py`, `catalog_sync.py`, `catalog_years.py`, `chat_service.py`, `procedure_images.py`, `chat_intent.py`, `vehicle_identity_provider.py`, `procedure_normalize.py`, and `job_plan.py` also branch on provider routes, fields, IDs, hosts, and behavior. Go catalog and vehicle-sync code has some Banktwo-specific filtering and defaults.

AutoData Compose currently builds Banktwo in its application stack. The local Banktwo Vercel configuration currently rewrites `/bankone/*` through the Banktwo project; this route is removed when direct subdomain cutover completes. Bankone batch/job persistence writes the historical `autoapi_article_fetch_jobs` tables directly. These are real code, deployment, and data boundaries to migrate; file relocation alone will not complete the separation.

The working tree at design time contains extensive unrelated and in-progress changes, including a dirty nested Banktwo checkout. Extraction work must preserve them and use isolated worktrees or explicit file ownership. Do not infer a clean release from the current checkout.

## Ownership rules

### AutoData owns

- Public API, UI, authorization, product behavior, and user-facing job/chat orchestration.
- Canonical vehicle identity and provider-to-canonical mapping.
- Generic source-resource capture, normalization, source snapshots and hashes, evidence, review, object storage, normalized article data, and publication.
- Generic catalog synchronization checkpoints and source-fetch job lifecycle in AutoData-owned storage.
- Generic HTTP clients and conversion from the shared wire envelope into AutoData's existing `SourceResource` contract.

AutoData must not construct provider-specific paths, parse provider response schemas, apply provider-specific article ranking, fetch provider-hosted assets directly, or own either bank's upstream credentials/session state.

### Each bank owns

- Its provider authentication and sessions, route construction, provider response parsing, retries, caching, rate controls, source-specific vehicle resolution, catalog traversal, article search/selection, article/resource retrieval, and upstream asset handling.
- A public, read-only, independently versioned HTTP API, OpenAPI document, fixtures, contract tests, CI, image publication, deployment, secrets, health, metrics, and runbook.
- Opaque provider references and the provider metadata required to associate its responses with source evidence.

A bank does not import AutoData packages, access AutoData databases/object storage, return AutoData database identifiers, or invoke the other bank. The only shared runtime relationship between AutoData and each bank is HTTP using a versioned contract.

## Source Connector HTTP contract, version 1

The canonical contract is a provider-neutral OpenAPI document under `packages/contracts/source-connector/v1/` in AutoData. The two bank repositories implement it independently and run the same conformance fixtures; neither imports AutoData code at runtime. The contract has a separate major-version path and explicit compatibility rules.

Required capabilities:

- Catalog scope reads for years, makes, models, and configurations, with bounded pagination, stable opaque source references, source revision/watermark, and explicit completeness/continuation metadata.
- Vehicle resolution for an AutoData-supplied YMME/region/configuration. Return zero or more candidates with source labels, opaque references, and evidence/confidence metadata; never silently bind an ambiguous candidate.
- Vehicle-scoped article listing and query-aware article search. Search ranking and provider-specific categorization happen inside the bank. Responses include opaque resource references and source-visible title/category/component metadata.
- Retrieval of a selected article, labor record, or binary asset by opaque resource reference. Return original bytes/content, media type, content hash, source locator, and source version. Use bounded sizes and no arbitrary-origin proxy behavior.
- Capability discovery so AutoData can distinguish unsupported operations from empty results.

Wire `source.provider` is `bankone` or `banktwo`; the AutoData adapter maps it to the existing persisted lineage values (`autoapi` or `autoapitwo`) until a separate data migration is approved. All responses carry a request ID and source envelope (provider, source revision, fetched time, and relevant source URI/locator). List operations carry `complete`, `next_cursor`, and scope metadata. Errors use a shared stable shape and distinguish invalid input, not found, ambiguous resolution, unauthorized, rate limited/retryable, upstream unavailable, and invalid upstream response. No credentials, cookies, signed upstream URLs, or raw auth material appear in responses or logs. Banktwo may return only its own origin or opaque resource handles; it must not route Bankone traffic.

The banks can retain provider-specific internal API helpers. The public contract hides those helpers and does not require identical upstream features; unsupported capabilities are explicit.

## Runtime and routing topology

AutoData's local and deployed runtime calls independently configured `BANKONE_BASE_URL` and `BANKTWO_BASE_URL` services. AutoData Compose does not build a bank repository, mount its source tree, or make AutoData worker readiness depend on a bank container. Tests use contract fakes; local end-to-end development can start each bank from its own checkout and pass its URL as configuration.

The canonical origins are `https://bankone.cars.tk` and `https://banktwo.cars.tk`, attached directly to their respective bank deployments. Detach the `cars.tk` apex from Banktwo. Each serves its versioned API below `/v1`; probes are `/healthz` and `/readyz`. Banktwo runs at the origin root with `MOUNT_PATH` unset, and generated content links point to `https://banktwo.cars.tk`. Bankone signed asset references remain on `https://bankone.cars.tk`. The old shared path routes are removed after AutoData and approved consumers switch to the direct origins. No gateway or cross-domain credential-forwarding proxy remains.

Each bank has its own CI, image, deployment, domain origin (`bankone.cars.tk` or `banktwo.cars.tk`), secrets, health checks, and rollback. AutoData may pin a supported API major/minimum version in deployment configuration, but it does not pin or build a bank's source commit.

## Persistence compatibility and migration

AutoData remains the sole owner of stored source snapshots, normalized records, provider mappings, review, and catalog state. Banks are stateless with respect to AutoData data; their private cache/session state is isolated by bank.

Persisted identifiers are compatibility data, not source-code names. Preserve existing provider values and keys such as `autoapi`, `autoapitwo`, `autoapi_vehicle_id`, `autoapitwo_vehicle_id`, `autoapitwo-fleet-v1`, source locators, stable article IDs, and historical migrations. Do not bulk-rename provider IDs or immutable article/snapshot identities as part of extraction.

The generic provider catalog-sync/year state already belongs to AutoData. Bankone article-fetch jobs currently use `autoapi_article_fetch_jobs`/`autoapi_article_fetch_job_retries` and Bankone-specific SQL callers. Move the lifecycle logic behind a provider-neutral AutoData job store and add a generic table/schema additively. Preserve existing UUIDs and idempotency keys while dual-reading/dual-writing or transactionally copying and verifying outstanding rows. Keep legacy tables read-only through the rollback window; drop them only in a separate approved migration after no old worker can use them. No bank service receives database credentials.

Source hash, locator, selected vehicle mapping, article order, pagination completeness, labor association, image bytes, provenance, and retry/idempotency behavior must remain equivalent across cutover. A raw response hash can differ if envelope formatting changes; compare both raw-source identity and normalized semantic output explicitly.

## Migration sequence and acceptance

1. **Freeze contract:** finalize OpenAPI, error/pagination/version semantics, opaque resource rules, fixtures, conformance tests, and compatibility policy. Record current Bankone/Banktwo behavior for catalog, vehicle resolution, article selection, labor, and assets.
2. **Make each bank independently releasable:** update Bankone and Banktwo repos on their own branches. Move provider-specific parsing/search/catalog traversal behind their APIs. Add clean-checkout build/test/lint/security CI and independently configurable deployments. Remove cross-bank routes from Banktwo and establish independent routing ownership.
3. **Add AutoData's neutral adapter:** implement one generic contract client and a provider registry. Replace imports/calls from chat, catalog, vehicle resolution, article intake, image retrieval, knowledge fallback, and job planning. No application caller imports `bankone_*` or `banktwo_*` provider modules after cutover.
4. **Migrate durable jobs:** move Bankone article-fetch orchestration to the generic AutoData job store, preserve/reconcile in-flight legacy rows, and prove idempotent retry/replay without loss.
5. **Canary one bank at a time:** deploy Bankone then Banktwo independently to nonproduction. Compare selector candidates, catalog coverage/completeness, selected articles, labor, image bytes/hash, provenance, and consumer-visible procedures against the existing route for representative vehicles. Exercise no-result, ambiguity, timeout, retry, rate-limit, bad-response, unauthorized, and partial-page cases.
6. **Cut over and remove embedded adapters:** switch AutoData runtime URLs, verify both independent rollback paths and unchanged public behavior, then remove provider parsers, source-specific switches, Banktwo submodule/build dependency, and legacy runtime wiring. Preserve compatibility data and migration history.

Completion requires successful clean builds/tests and independent deployment for all three repositories; contract conformance for both banks; no provider-specific response parsing or direct upstream access in AutoData; no AutoData database credentials or dependencies in either bank; no Bankone route hosted by Banktwo; verified data/provenance parity and retry recovery; and a documented rollback window. Production rollout is not included until separately authorized by policy.

## Options considered

1. **Recommended — independent HTTP services on separate subdomains.** Gives each bank direct domain and deployment ownership, removes Banktwo routing to Bankone, and keeps AutoData dependent only on versioned HTTP contracts. Requires switching configured origins before retiring the old paths.
2. **Independent HTTP services plus a neutral shared-path router.** Preserves current public URLs but adds a fourth routing owner and a shared failure/configuration point. Not selected.
3. **Shared source SDK/package.** Reduces duplicate HTTP code but creates a versioned runtime dependency shared by AutoData and both banks, weakening independent releases. Do not start here; the contract plus conformance fixtures are enough.

## Review questions

- Does the three-repository ownership boundary and direct subdomain ownership match the requested separation?
- Are the provider-neutral operations and migration safeguards sufficient for the current catalog, chat, labor, and asset flows?


**Issue:** https://github.com/lucronn/autodata/issues/132
**Project:** https://github.com/users/lucronn/projects/8
