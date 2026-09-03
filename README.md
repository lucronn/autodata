# AutoData

AutoData is a cloud-neutral, containerized automotive data platform. It turns
heterogeneous source resources into evidence-backed, vehicle-specific dataset
projections that can be published quickly and enriched incrementally.

The repository is a modular monorepo:

- `apps/api-go` — authenticated API, RBAC, entitlement-aware reads, feedback,
  and reviewer commands.
- `workers/ingestion-python` — provider-neutral source intake, normalization,
  provenance, fast-lane publication, and payment reconciliation.
- `workers/enrichment-python` — deep-lane section enrichment, the initial
  evidence-backed search index, embeddings, immutable revisions, and
  publication outbox handling.
- `packages/contracts` — versioned API, event, and payment contracts.
- `db/migrations` — forward-only PostgreSQL and pgvector schema migrations.
- `infra/compose` and `infra/k8s` — local and Kubernetes-compatible topology.
- `docs/architecture` — canonical system, lifecycle, contract, and operations
  documentation.
- `docs/github` — repository and Project operating model.

## Start the local stack

The deterministic local path uses PostgreSQL with pgvector, NATS JetStream,
MinIO, fake source data, and a fake payment provider. It does not require cloud
credentials:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml up -d \
  postgres nats minio migration-runner

AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm ingestion-smoke
```

The smoke command verifies the deterministic purchase, entitlement, viewable
revision, PostgreSQL records, MinIO source object, and `dataset.viewable`
JetStream event. The full developer workflows and recovery checks are in
[`docs/architecture/infrastructure-and-dev.md`](docs/architecture/infrastructure-and-dev.md).

## Validate a heterogeneous source drop

The source normalizer accepts mixed JSON/API envelopes, XML, CSV, HTML, plain
text, PDF, SVG, and unsupported media without relying on filenames. It retains
raw bytes and provenance, emits typed candidates where the shape is recognized,
extracts literal HTML/plain text into reviewable evidence, and routes ambiguous
or unknown material to review. New source media types can register an adapter
without changing the connector or event contract; unconfigured binary types
remain content-addressed raw artifacts.

For a local-only source directory:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/normalize_source_directory.py "sample data" --region US
```

The `sample data/` directory is intentionally not part of the public
repository. Do not stage or publish source payloads unless their redistribution
terms have been explicitly approved. The Compose-mounted persistence form and
its review semantics are documented in the infrastructure guide.

The same pipeline can run through the ingestion worker boundary instead of the
developer script:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -v "$PWD/sample data:/sample-data:ro" \
  -e AUTODATA_SOURCE_DIRECTORY=/sample-data \
  -e AUTODATA_SOURCE_VERSION=local-sample-v1 \
  -e AUTODATA_SOURCE_REGION=US \
  -e AUTODATA_SOURCE_PERSIST=0 \
  -e AUTODATA_WORKER_ONCE=1 \
  ingestion-worker python -m autodata_ingestion.worker
```

Set `AUTODATA_SOURCE_PERSIST=1` only when the local PostgreSQL and MinIO
connection variables are also provided. The worker reports bundle readiness and
quality/review status separately.

For one HTTP(S) source resource, set `AUTODATA_SOURCE_URI` instead of
`AUTODATA_SOURCE_DIRECTORY`. The connector captures the response status,
non-secret response headers, redirect target, and raw bytes before the same
content-first classification and normalization path. Source authentication, if
required, belongs in secret-managed `AUTODATA_SOURCE_REQUEST_HEADERS_JSON`; do
not commit header values or credentials to the repository.

## Run tests

```sh
(cd apps/api-go && go test ./...)
(cd packages/contracts/go && go test ./...)
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests -q
PYTHONPATH=workers/enrichment-python/src python3 -m pytest workers/enrichment-python/tests -q
PYTHONPATH=workers/ingestion-python/src python3 -m pytest scripts/dev/test_*.py -q
python3 scripts/contracts/test_contracts.py
python3 scripts/dev/test_k8s_manifests.py
```

Architecture and delivery decisions are maintained in the linked canonical
documents rather than duplicated in this index.
