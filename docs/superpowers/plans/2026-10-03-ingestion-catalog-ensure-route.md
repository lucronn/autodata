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
- [x] Pass hosted verification on implementation commit
  `95381f4d6ffeb5d69e7ab8bf0feb192bd030462c`.

## Local verification so far

- Worker HTTP route tests pass, including a real local HTTP request to the
  dispatcher with one hydration-service invocation.
- Ingestion worker suite: 367 passed, 3 skipped.
- Go API tests and `go vet ./...` pass.
- Python compileall and `git diff --check` pass.
- The container smoke used a fake hydration result and made no provider calls;
  it did not read/write a database or call live sources.
- Both hosted Autonomous Verification runs passed on the implementation commit:
  [37108159899](https://github.com/lucronn/autodata/actions/runs/37108159899)
  and [37108163117](https://github.com/lucronn/autodata/actions/runs/37108163117).

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
