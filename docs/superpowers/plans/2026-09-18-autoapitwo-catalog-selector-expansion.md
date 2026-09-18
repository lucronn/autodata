# AutoAPItwo Catalog Selector Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the normalized AutoAPItwo make, model, and engine/base catalog into the dashboard progressively after the year manifest, without blocking the first selector response.

**Architecture:** Keep the existing two-lane catalog design. The ingestion worker continues a durable, idempotent AutoAPItwo fleet traversal and persists normalized vehicle identity/configuration rows; the Go API reads those rows and reports sync status; the minimal dashboard renders the available hierarchy and polls while the deep catalog is still warming. The selector never calls AutoAPItwo directly.

**Tech Stack:** Go HTTP API, Python ingestion worker, PostgreSQL/pgvector, AutoAPItwo fleet JSON endpoints, static HTML/CSS/JavaScript dashboard, Docker Compose.

**Spec:** `docs/architecture/vehicle-catalog-ingestion.md`

**Issue:** https://github.com/lucronn/autodata/issues/107

**Project:** https://github.com/users/lucronn/projects/8

## Concrete todo

- Propagate durable catalog readiness and row counts through the selector API.
- Render model and engine/base configuration choices from normalized records.
- Replace the active selector row in place after each choice to minimize cursor movement.
- Verify AutoAPItwo traversal, persistence, local Compose behavior, browser interaction, and CI.
- Synchronize the exact implementation SHA, Issue #107, Project #8, and CI evidence.

## Global Constraints

- The selector response remains cache-first and non-blocking.
- AutoAPItwo is accessed only through the bounded provider connector and documented `/api/v1/fleet/*` endpoints.
- Normalized records remain linked to immutable source snapshots and provider mappings.
- Repeated selector loads and worker retries must be idempotent.
- The dashboard must preserve the existing decade -> year -> make-letter -> make flow.
- The primary selector row must replace its contents in place after each selection: decade buttons become years, year buttons become makes, and downstream choices reveal models and engine/base configurations with minimal pointer travel.
- Existing untracked `output/`, `sample data/`, and `tmp/` directories are user-owned and must not be staged.

---

### Task 1: Define the selector hierarchy contract

**Files:**
- Modify: `docs/architecture/vehicle-catalog-ingestion.md`
- Create: `docs/superpowers/plans/2026-09-18-autoapitwo-catalog-selector-expansion.md`
- Test: `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: existing `VehicleIdentitySelectors` and `VehicleIdentityRecord.Configurations` JSON fields.
- Produces: documented selector hierarchy and readiness behavior for makes, models, and engine/base configurations.

- [x] **Step 1: Write the failing dashboard contract assertions**

  Extend the dashboard route tests so the served HTML contains `model-step`, `model-list`, `configuration-step`, and `configuration-list`, and the JavaScript contains `renderModels`, `renderConfigurations`, and `catalog_sync` polling.

- [x] **Step 2: Run the dashboard test to verify it fails**

  Run `go test ./...` from `apps/api-go`.
  Expected: FAIL because the new hierarchy controls and render functions do not exist.

- [x] **Step 3: Record the selector contract in the canonical architecture document**

  Document that models are derived from normalized vehicle identity records for the selected year/make, and engine/base choices are derived from the matching configuration records. A configuration label must remain honest when displacement is unavailable: show `Base configuration` plus known drivetrain/trim rather than inventing an engine.

- [x] **Step 4: Commit the planning checkpoint**

  Commit only the plan, canonical document, synchronized record, and tracking updates after the gate preflight is complete.

### Task 2: Expose durable catalog readiness

**Files:**
- Modify: `apps/api-go/vehicle_identity.go`
- Modify: `apps/api-go/vehicle_identity_http.go`
- Modify: `apps/api-go/postgres_vehicle_identity.go`
- Test: `apps/api-go/vehicle_catalog_sync_test.go`
- Test: `apps/api-go/vehicle_identity_test.go`

**Interfaces:**
- Consumes: `vehicle_catalog_syncs` and `vehicle_configurations` PostgreSQL rows.
- Produces: `VehicleIdentitySelectors.CatalogSync` with provider, source version, status, and row count; selector years remain available during all sync states.

- [x] **Step 1: Write the failing readiness test**

  Update the ingestion-client capture test to assert that selector reads still schedule idempotent catalog warm-up and add a pure selector test asserting that a catalog status of `completed` is not overwritten with `warming` by the HTTP handler.

- [x] **Step 2: Run the focused Go tests to verify failure**

  Run `go test ./...` from `apps/api-go`.
  Expected: FAIL because the selector status currently always reports `warming` whenever an ingestion client exists.

- [x] **Step 3: Implement minimal durable status propagation**

  Add `row_count` to `CatalogSyncStatus`, read the `fleet-vocabulary-v1` sync row in the PostgreSQL selector store, preserve an existing durable status in the HTTP response, and continue calling the idempotent ensure route so stale/failed runs can be retried by the existing claim logic.

- [x] **Step 4: Run the focused Go tests to verify success**

  Run `go test ./...` from `apps/api-go`.
  Expected: PASS with the new status assertions and existing selector tests.

### Task 3: Render models and engine/base configurations in the dashboard

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/app.js`
- Modify: `apps/api-go/dashboard/styles.css`
- Test: `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: selector JSON containing `years`, `vehicles`, `model`, and `configurations`.
- Produces: interactive decade -> year -> make initial -> make -> model -> engine/base selection with no direct provider calls.

- [x] **Step 1: Add the failing UI contract assertions**

  Assert the dashboard HTML contains the model and configuration steps, and assert JavaScript markers for model/configuration state, data attributes, polling, and the configuration label formatter.

- [x] **Step 2: Run the dashboard tests to verify failure**

  Run `go test ./...` from `apps/api-go`.
  Expected: FAIL because the new steps and functions are absent.

- [x] **Step 3: Implement the minimal hierarchy**

  Replace the active choice row in place after each selection: decade buttons become individual years, the year row becomes make letters/makes, then models, then engine/base configurations. Keep only the currently relevant row visible and preserve a compact breadcrumb/selection label so pointer movement remains minimal. Filter records by selected year, make, and model. Group configurations deterministically by `configuration_key`; render a label from known engine displacement, drivetrain, and trim, using `Base configuration` when no displacement is present. Reset downstream selections whenever an upstream choice changes. Extend the selected label and continue button to include model and configuration.

- [x] **Step 4: Add non-blocking refresh while catalog sync is active**

  Store `catalog_sync` from the response. While its status is `pending`, `running`, `partial`, `failed`, or `warming`, refresh selectors at a bounded interval; stop after `completed`, `dead_letter`, or the configured refresh deadline. Preserve the current user selection when refreshed records still contain it.

- [x] **Step 5: Run the dashboard tests to verify success**

  Run `go test ./...` from `apps/api-go`.
  Expected: PASS with all static dashboard markers present.

### Task 4: Verify provider-backed ingestion and browser behavior

**Files:**
- Modify: `docs/superpowers/plans/2026-09-18-autoapitwo-catalog-selector-expansion.md`
- Modify: `docs/agents/records/2026-09-18-autoapitwo-catalog-selector-expansion.json`

**Interfaces:**
- Consumes: live Compose services, AutoAPItwo fleet endpoints, dashboard, and GitHub CI.
- Produces: exact SHA, test evidence, persisted catalog counts, browser evidence, and synchronized Issue/Project state.

- [x] **Step 1: Run deterministic local checks**

  Run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests -q`, `go test ./...` from `apps/api-go`, `python3 scripts/dev/test_migrations.py`, and `git diff --check`.

- [x] **Step 2: Apply migrations and rebuild the local services**

  Run the existing Compose migration runner, rebuild `ingestion-http` and `api`, and call `GET /vehicle-identities/selectors` with the local viewer token. Verify that the response includes years, makes/models/configurations as rows arrive and that the catalog sync status changes to `completed` without duplicate provider work.

- [x] **Step 3: Verify the browser hierarchy**

Reload `http://127.0.0.1:8080/dashboard/` in the browser. Confirm decade controls appear immediately, then choose a decade/year/make/make-letter and verify model and engine/base controls are populated from the normalized response.

Browser verification passed on `http://127.0.0.1:8080/dashboard/`: 1990s ->
1999 -> C -> Chevrolet -> Silverado 1500 -> `5.3L engine · 2WD`. The
selected-vehicle summary and Continue control were rendered.

- [x] **Step 4: Synchronize delivery records**

Update this plan, the canonical architecture document, the machine record, Issue #107, and its Project #8 item with the exact implementation SHA and successful CI URL. Push all intentional changes; preserve unrelated untracked directories.

Implementation checkpoint: `5c6026ee9676699ea5d85a4e696a96cda6d8c12a`.
CI: `https://github.com/lucronn/autodata/actions/runs/35397024629` (passed).
Issue #107 and Project #8 are synchronized to this checkpoint; the item is
ready to close after the documentation CI for this final record update passes.
