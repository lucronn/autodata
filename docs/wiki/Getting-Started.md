# Getting Started

The supported local path is deterministic and credential-free. It runs the
PostgreSQL/pgvector, NATS JetStream, MinIO, migration, API, and worker
boundaries from Docker Compose with fake source and payment adapters.

## Start the foundation services

From the repository root:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml up -d \
  postgres nats minio migration-runner
```

Run the deterministic ingestion smoke:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm ingestion-smoke
```

The smoke verifies the purchase, entitlement, viewable revision, PostgreSQL
records, MinIO source object, and `dataset.viewable` JetStream event. With the
API container running, open the local dashboard at
<http://127.0.0.1:8080/dashboard/>.

## Try an illustrated repair guide

Configure the ingestion service with
`AUTODATA_AUTOAPITWO_BASE_URL=https://autoapitwo.vercel.app`, then enter a
request such as:

```text
1997 Toyota RAV4 2-door 2WD 2.0L oil pump and water pump replacement
```

Choose the exact vehicle match when prompted. The guide keeps removal and
installation together, includes timing-belt access and final fluid/leak
checks when required by the returned procedure, and shows each available
figure beside its step. The HTML download appears first only after the required
procedure coverage and figures are complete; it contains the prepared figures
inline. The PDF link remains available as a compatibility fallback for the same
revision. The full local configuration and source
boundary are documented in the [repository README](https://github.com/lucronn/autodata#illustrated-diy-repair-guides).

## Read the full workflow

The root [README](https://github.com/lucronn/autodata#start-the-local-stack)
contains the chatbot request example, source-drop normalization commands,
AutoAPI connector boundary, and complete test commands. The canonical
[infrastructure and developer guide](https://github.com/lucronn/autodata/blob/master/docs/architecture/infrastructure-and-dev.md)
contains recovery checks, persistence details, and secret-handling rules.

Do not add the user-owned `sample data/` directory or any restricted source
payloads to commits. Provider credentials belong in a secret-managed local or
deployment environment, never in the Wiki, README, browser bundle, or Git
history.
