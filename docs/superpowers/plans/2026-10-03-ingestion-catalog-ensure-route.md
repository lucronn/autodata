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

- [x] Register `POST /v1/catalog/ensure` in the ingestion HTTP route contract.
- [x] Dispatch the request to `ensure_catalog_hydration` with validated JSON
  and its idempotency key, returning the structured hydration result.
- [x] Add HTTP dispatcher and handler regressions proving the Go request path
  reaches the catalog service and malformed requests fail safely.
- [x] Verify catalog API/worker tests and run an isolated Compose container
  route smoke with a deterministic fake hydration service.
- [x] Record exact local test and smoke evidence in Issue #113 and Project #8.
- [ ] Pass hosted verification on the current PR stack head.

## Local verification so far

- Worker HTTP route tests pass, including a real local HTTP request to the
  dispatcher with one hydration-service invocation.
- Ingestion worker suite: 367 passed, 3 skipped.
- Go API tests and `go vet ./...` pass.
- Python compileall and `git diff --check` pass.
- The container smoke used a fake hydration result and made no provider calls;
  hosted verification remains outstanding.

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
