# AutoAPItwo Year Manifest Bootstrap Plan

> Follow `docs/agents/pre-implementation-gate.md` before modifying
> implementation files. This plan is the complete scope for this change.

**Goal:** Fetch and persist AutoAPItwo's year manifest once, then make every
year from 1966 through 2027 available in the selector response on the first
page load without waiting for the full make/model/engine catalog traversal.

**Issue:** https://github.com/lucronn/autodata/issues/106

**Project:** https://github.com/users/lucronn/projects/8

**Canonical contract:** `docs/architecture/vehicle-catalog-ingestion.md`

**Base SHA:** `9ee98bee135800e62989199a382e3fcffb11e539`

**Implementation SHA:** `70bb071f584adfdd08ef6bfbeeaafbf8020dbfef`

**CI:** [Autonomous Verification run 35387843397](https://github.com/lucronn/autodata/actions/runs/35387843397) — passed

## Decisions

- AutoAPItwo's `/api/v1/fleet/years` response is the source of truth; the
  configured local development range is 1966–2027 and must be visible before
  deep catalog enrichment completes.
- A durable `vehicle_catalog_years` table stores the normalized year,
  provider, source version, source endpoint, response hash, and fetched time.
- The selector remains cache-first and non-blocking. If the year manifest is
  absent, the API returns the configured 1966–2027 range immediately and
  schedules a single lightweight manifest fetch through ingestion HTTP.
- Deep catalog traversal remains separate. Its existing source/version claim
  prevents duplicate full-catalog work, while the year manifest claim prevents
  repeated `/fleet/years` calls.
- Provider years outside the configured range are retained in the durable
  cache but are not hidden from the API when AutoAPItwo supplies them.

## Concrete todo

- Add the durable year-manifest table and migration validation.
- Add a bounded AutoAPItwo year-list fetch and idempotent persistence path.
- Add an internal `catalog-years/ensure` route and selector scheduling.
- Return 1966–2027 on initial selector load while preserving cached/provider
  years and never waiting for deep traversal.
- Add deterministic adapter, HTTP, Go selector, migration, and browser tests.
- Update the canonical contract, Issue #106, Project #8, and this record with
  the exact implementation SHA and CI evidence.

## Acceptance checks

- A cold selector request lists every year from 1966 through 2027.
- The first cold request schedules at most one year-manifest fetch.
- A completed manifest makes zero repeated `/api/v1/fleet/years` calls.
- Existing cached vehicle rows remain available while the manifest or deep
  catalog is being synchronized.
- The year-manifest path never calls article, procedure, image, or content
  endpoints.
- Browser verification confirms all decade controls are visible after load; selecting a decade uses the 1966–2027 provider-backed year manifest.

**todo:** complete — implemented and verified the non-blocking year-manifest bootstrap.

## Verification record

- `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests -q`: 420 passed, 3 skipped, 12 subtests passed.
- `go test ./...` from `apps/api-go`: passed.
- `python3 scripts/dev/test_migrations.py`: 13 passed.
- Live Compose migration applied `030_vehicle_catalog_years.sql`; the provider manifest completed with 62 rows and source-snapshot links.
- Live `GET /vehicle-identities/selectors` returned 62 years with minimum 1966 and maximum 2027 while catalog traversal remained asynchronous.
- Browser load at `http://127.0.0.1:8080/dashboard/` showed all seven decade controls from `1960s` through `2020s` on initial load.
- The completed manifest claim returned without another provider fetch on the subsequent ensure request.
