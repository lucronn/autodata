# AutoData agent instructions

Before any implementation work, read the canonical [pre-implementation planning and tracking gate](docs/agents/pre-implementation-gate.md).

No implementation agent may modify implementation files until the required plan, GitHub Issue/Project update, canonical repository-document update, concrete `todo` list, and machine-checked `status: synchronized` record exist at the pinned base SHA. This file is only a discovery pointer; the canonical rule and record shape live under `docs/agents/`.

## Base44 sandbox environment

The Base44 preview runs the stack through `docker-compose.base44.yml` (development
topology: repository bind-mounted, live reload, local infrastructure only). The
repository's own `infra/compose/compose.yaml` builds production images and is not
used here.

- Bring up: `docker compose -f docker-compose.base44.yml up -d --build`.
  Web entry point is host port `3000` -> Go API `:8080`. The API process serves
  `/dashboard/`, `/workshop/`, `/swagger/`, `/healthz` and `/v1/...`; there is no
  separate frontend server.
- `db/migrations/*.sql` are applied by the `migration-runner` one-shot service
  before any app service starts. Re-running it is safe (forward-only, idempotent
  files); do not delete the `postgres-data` volume to "fix" migrations.
- MinIO images are no longer publicly distributable, so `object-storage` is
  LocalStack S3 (`localstack/localstack:4`, endpoint `object-storage:4566`).
  The application enables bucket versioning, so a plain static S3 stub is not
  enough; LocalStack's S3 implementation is required.
- External source connectors `https://bankone.cars.tk` and
  `https://banktwo.cars.tk` answer `401` without an API key. The catalog the
  Workshop browses is hydrated from Banktwo, so `AUTODATA_BANKTWO_API_KEY`
  (delivered via `/run/base44/app.env`, never committed) must be present before
  `/v1/catalog/years` returns anything. Failed hydration attempts are recorded in
  `vehicle_catalog_syncs`; after `BANKTWO_CATALOG_MAX_ATTEMPTS` (default 3)
  failures the sync dead-letters and stops retrying — reset that row when a key
  is added.
- Auth is the local header convention `Authorization: Bearer local:<org>:<roles>`
  (e.g. `local:demo:dataset_viewer`). The Workshop defaults to
  `local:demo:dataset_viewer` and needs no sign-in.
- Live reload: the API runs under `air` with polling enabled (bind mounts). The
  Workshop/dashboard/Swagger assets are `go:embed`, so an asset edit rebuilds the
  binary — allow a few seconds. Python services run from the mounted source with
  no restart needed for code edits (long-running loops pick changes up on restart
  of the process, i.e. `docker compose ... restart <service>`).
- Tests: `docker compose -f docker-compose.base44.yml exec -T api go test ./...`,
  `... exec -T ingestion-worker python -m pytest tests`,
  `... exec -T enrichment-worker python -m pytest tests`.
