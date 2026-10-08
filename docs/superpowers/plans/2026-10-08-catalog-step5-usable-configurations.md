# Catalog Step 5 Usable Configurations Plan

Issue: https://github.com/lucronn/autodata/issues/134
Project: https://github.com/users/lucronn/projects/8
Canonical contract: [dashboard-selector.md](../../architecture/dashboard-selector.md)

## Goal

Dashboard Step 5 (Engine / base) must show usable complete configurations as
soon as they exist in the catalog store. The UI must not stay empty for the
full hydration poll window when configuration rows are already complete but
the `vehicle_catalog_hydration_scopes` marker is missing.

## Problem

`GET /v1/catalog/.../configurations` sets `hydrating: true` whenever
`CatalogScopeComplete` is false, even when every returned item is already
`complete: true`. The dashboard `getReadyCatalogScope` helper clears the list
and waits until `hydrating !== true` (up to ~90s). Ensure hydration often
returns `coverage: not_complete` / `no_persistable_rows` and never writes the
scope marker, so Step 5 appears broken.

## Todo

- [x] Treat usable complete configuration items as ready in the Go
      configurations response (`hydrating: false` when items are usable).
- [x] Persist the configurations hydration-scope marker when ensure reports a
      complete scoped read, including empty-but-complete provider responses.
- [x] Update the dashboard poller so Step 5 renders the latest usable items
      instead of staying blank while background hydration continues.
- [x] Add Go and dashboard regression coverage for the ready/hydrating decision.
- [x] Verify in the Cursor browser that 2026 Dodge Charger R/T 4 Door Step 5
      shows Base Powertrain promptly.

## Acceptance

- Usable complete configuration items are visible without waiting on a missing
  hydration-scope row.
- Ensure/persist writes the configurations scope marker when the provider
  reports a complete scoped read.
- Browser Step 5 no longer shows a long empty “Loading…” / no-options state
  when Base Powertrain (or equivalent) already exists.
- Existing catalog cascade steps 1–4 remain unchanged.

## Out of scope

- Article list empty counts after selection (separate catalog/content issue).
- Bank connector rename / domain routing beyond what ensure needs to persist.
