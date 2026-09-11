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
