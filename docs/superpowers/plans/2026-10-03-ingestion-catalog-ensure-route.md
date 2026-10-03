# Ingestion catalog ensure route contract

**Issue:** https://github.com/lucronn/autodata/issues/113
**Project:** https://github.com/users/lucronn/projects/8
**Canonical contract:** `docs/architecture/provider-neutral-catalog-api.md`

## Goal

Connect the Go catalog API's `POST /v1/catalog/ensure` call to the ingestion
worker's existing `ensure_catalog_hydration` service function. The current
worker HTTP adapter rejects that path, so catalog hydration requests never
reach the source connectors.

## Concrete todo

- [ ] Register `POST /v1/catalog/ensure` in the ingestion HTTP route contract.
- [ ] Dispatch the request to `ensure_catalog_hydration` with validated JSON
  and its idempotency key, returning the structured hydration result.
- [ ] Add HTTP dispatcher and handler regressions proving the Go request path
  reaches the catalog service and malformed requests fail safely.
- [ ] Verify catalog API/worker tests and run a clean isolated Compose catalog
  hydration smoke through a deterministic fake source.
- [ ] Record exact test and hosted verification evidence in Issue #113 and
  Project #8.

## Boundaries

- Preserve the existing `POST /v1/catalog/ensure` payload and response shape.
- Do not contact live providers in unit tests or the isolated fake-source
  smoke.
- Do not change catalog selection, normalization, persistence, or source API
  semantics as part of this route wiring.

## Acceptance

A catalog ensure request sent through the same internal HTTP boundary used by
the Go API invokes `ensure_catalog_hydration` exactly once and returns its
result. Unknown paths remain rejected; invalid JSON/request payloads return a
bounded client error. Worker/API tests and the isolated fake-source Compose
smoke pass.
