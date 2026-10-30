# AutoData agent instructions

Before any implementation work, read the canonical [pre-implementation planning and tracking gate](docs/agents/pre-implementation-gate.md).

No implementation agent may modify implementation files until the required plan, GitHub Issue/Project update, canonical repository-document update, concrete `todo` list, and machine-checked `status: synchronized` record exist at the pinned base SHA. This file is only a discovery pointer; the canonical rule and record shape live under `docs/agents/`.

## Base44 sandbox environment

`docker-compose.base44.yml` is the sandbox-only development stack; it does not
replace `infra/compose/compose.yaml`.

- Start: `docker compose -f docker-compose.base44.yml up -d --build`.
- The Go API is the only application process. It serves the dashboard,
  workshop, Swagger UI, `/openapi.json` and `/v1/catalog/*`, and is mapped to
  host port 3000 (`/healthz` liveness, `/readyz` checks DB, NATS and S3).
- Application processes run from the bind-mounted checkout (`go run .`, Python
  modules) on plain runtime images; `.base44/ingestion-dev.Dockerfile` installs
  only the ingestion dependencies and copies no source.
- The API embeds its static assets (`//go:embed`), so editing
  `apps/api-go/{dashboard,workshop,swagger-*}` requires
  `docker compose -f docker-compose.base44.yml restart api`. Go code changes
  likewise need a restart; there is no Go file watcher.
- `minio` runs SeaweedFS with the repository's pinned CI image because the MinIO
  image is no longer publicly pullable; the API and workers still address S3 as
  `minio:9000`.
- No external credentials are required. `scripts/dev/ingestion_smoke.py` and
  `autodata_ingestion.ingest_fixture` are available under
  `--profile smoke`. Tests run inside the containers, e.g.
  `docker compose -f docker-compose.base44.yml exec -T api go test ./...`.
- The workshop catalog is populated by the external Bankone/Banktwo Source
  Connector services (`BANKONE_BASE_URL` / `BANKTWO_BASE_URL`). Without a
  reachable connector `/v1/catalog/years` correctly returns `{"items":[]}`, so
  the vehicle cascade stays empty even though the API is healthy.
