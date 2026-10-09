# AutoData agent instructions

Before any implementation work, read the canonical [pre-implementation planning and tracking gate](docs/agents/pre-implementation-gate.md).

No implementation agent may modify implementation files until the required plan, GitHub Issue/Project update, canonical repository-document update, concrete `todo` list, and machine-checked `status: synchronized` record exist at the pinned base SHA. This file is only a discovery pointer; the canonical rule and record shape live under `docs/agents/`.

## Base44 sandbox (local development environment)

Everything runs from the cloned source through `docker-compose.base44.yml`; the
repo's own `infra/compose/compose.yaml` builds released images and must not be
used for sandbox work.

```
docker compose -f docker-compose.base44.yml up -d --build
```

Non-obvious things worth knowing:

- **Single entry point.** nginx (`proxy`) owns host port 3000 and fronts the Go
  API: `/workshop/` is the vehicle workshop UI, `/dashboard` is the operator
  dashboard, and API calls go to `/v1/...` on the same origin. `GET /` answers a
  302 to `/workshop/`, so probe `/workshop/` for a 200.
- **Live reload.** `api` runs `air` from a bind mount (`.base44/air.toml`), so Go
  changes and the go:embed'ed `dashboard/` + `workshop/` assets rebuild on save.
  Its build output lives in `apps/api-go/tmp/`, which is git-ignored. Every
  long-running Python service runs through `.base44/reload-python.sh`, which
  re-execs the service command (1s mtime poll) when a file under its watched
  `src/` changes, so a save is enough — without that wrapper a running
  interpreter kept the code it imported at startup and an edit silently had no
  effect until a manual restart (no rebuild is needed either way). A dependency
  change still needs `up -d --build`.
- **One-shot jobs exit 0 by design.** `migration-runner` applies the schema (via
  `.base44/migrate.sh`, which records applied files in `base44_schema_migrations`
  so a repeated `up` is safe) and `ingest-fixture` writes the deterministic
  fast-lane fixture (`ON CONFLICT DO NOTHING`). Seeing them as `Exited (0)` in
  `docker compose ps -a` is success, not a failure. Both are declared as
  completed prerequisites of the long-running services that consume them —
  `ingest-fixture` is in `api`'s `depends_on` with
  `condition: service_completed_successfully` — so a finished one-shot is never
  mistaken for a crashed application service, and `api` never serves an unseeded
  store.
- **Selector hydration persists durable manifests.** Years, makes, and models
  are flat provider indexes with no full vehicle identity, so hydration writes
  them to `vehicle_catalog_years`, `vehicle_catalog_makes` and
  `vehicle_catalog_models` (migration `037_catalog_selector_manifests.sql`)
  through `catalog_manifests.persist_selector_manifest`; the API's selector
  reads union those manifests with the seeded identity rows. A new migration
  file only reaches the database through the one-shot `migration-runner`, so
  after adding one run `docker compose -f docker-compose.base44.yml up -d`
  (it re-runs the recorded-files wrapper and exits 0).
- **The `years` scope writes no hydration-scope marker.** `vehicle_catalog_hydration_scopes.model_year`
  requires a real year (`CHECK (model_year >= 1886 ...)`), but the years index is
  not year-scoped, so `catalog_service._persist_hydration_scope` returns
  `not_applicable` for `scope == "years"` instead of inserting a synthetic `0`
  row (which used to violate the check constraint). `vehicle_catalog_years` is
  populated through the canonical selection store instead, and the API's
  `Years` read unions it with `vehicles.model_year`, so the picker's first
  dropdown is never empty once the fixture has run.
- **The catalog picker needs the external connectors.** Vehicle years/makes/
  models are hydrated from the independent Source Connector v1 origins
  `BANKONE_BASE_URL` / `BANKTWO_BASE_URL` (defaults `https://bankone.cars.tk`,
  `https://banktwo.cars.tk`). Both origins require bearer authentication: with no
  credential the hydration request fails (`401` upstream, surfaced by the API as
  `catalog hydration returned status 422`) and the picker stays empty. Supply the
  real `BANKONE_API_TOKEN` / `BANKTWO_API_TOKEN` through the Base44 dashboard
  (delivered via `/run/base44/app.env`, listed last in every `env_file`); never
  commit them. Local-only, non-credential settings live in
  `.env.base44-defaults`.
- **Checking a running stack:** `docker compose -f docker-compose.base44.yml ps`
  for service state, `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/workshop/`
  for the UI, and `docker compose -f docker-compose.base44.yml logs --since=10m api`
  for hydration failures. Service logs carry benign noise: SeaweedFS (`minio`)
  prints gRPC/lock-ring startup chatter and the migrations print `NOTICE ...
  constraint ... does not exist, skipping` for idempotent DDL.
