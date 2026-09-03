# AutoData Infrastructure and Developer Environment

## Local topology

The local environment is deterministic and containerized. Docker Compose provides service parity without requiring a cloud account.

```text
                    +-------------------+
                    |      Go API        |
                    +---------+---------+
                              |
        +---------------------+---------------------+
        |                     |                     |
 +------v------+       +------v------+       +------v------+
 | PostgreSQL  |       | NATS        |       | MinIO       |
 | + pgvector  |       | JetStream   |       | S3 API      |
 +-------------+       +------+------+       +-------------+
                              |
                 +------------+------------+
                 |                         |
          +------v------+           +------v------+
          | Fast worker |           | Deep worker |
          | Python      |           | Python      |
          +------+------+           +------+------+
                 |                         |
          +------v------+           +------v------+
          | Fake source|           | Fake payment|
          | connector  |           | + webhooks  |
          +------------+           +-------------+
```

Services:

- PostgreSQL with the pgvector extension for canonical data, projections, revisions, audit records, and semantic vectors.
- NATS JetStream for durable jobs, event delivery, retries, and dead-letter streams.
- MinIO for raw sources, documents, page images, OCR output, diagrams, meshes, and evidence artifacts.
- Go API for authenticated reads, entitlement checks, dataset status, reviewer commands, and feedback.
- Python ingestion worker for source adapters, fast-lane normalization, OCR, and extraction.
- Python enrichment worker for deep sections, embeddings, cross-record validation, and publication.
- Publication outbox relay for at-least-once delivery from PostgreSQL to NATS JetStream.
- Migration runner for applying schema changes from a clean database.
- Deterministic fake source connector that can emit core data, document pages, diagrams, failures, and source drift.
- Deterministic fake payment/webhook service for purchase, duplicate webhook, refund, and delayed fulfillment scenarios.
- Payment reconciler that polls pending verified events and safely retries delayed entitlement fulfillment.
- Optional Mailpit and OpenTelemetry-compatible services behind a development profile.

## Universal source intake

Source connectors do not write directly to canonical tables. Every connector returns one or more immutable `SourceResource` envelopes containing the source URI, source version, connector media type when available, raw bytes, optional locator, attribution/terms metadata, and retrieval metadata. The intake boundary computes a SHA-256 content address before interpretation and stores the raw resource in object storage.

The format layer is provider-neutral:

| Input | Intake result | Downstream capability |
| --- | --- | --- |
| JSON or JSON API envelope | Structured artifact with preserved headers and body | Typed record extractor and schema validation |
| XML, CSV, or other structured text | Structured artifact retaining original bytes | Format-specific record extractor |
| HTML or plain text | Document artifact | Text extraction, OCR fallback, and evidence locators |
| PDF | Document artifact | Page extraction, OCR, and page/region evidence |
| SVG or other diagram media | Diagram artifact | Diagram metadata, rendering, and diagram evidence |
| Unknown or unsupported media | Quarantined artifact | Operator review or a newly registered capability |

Extractors are selected by declared capabilities and observed content, not by a hard-coded filename convention. A source may emit multiple resource types in one request: for example, a vehicle identity response, a parts collection, an article index, an HTML procedure, a PDF, and an SVG diagram. Each resource receives its own content hash, object key, extraction run, and evidence path, while the request correlation ID joins them into one dataset projection.

The intake invariants are:

- Raw bytes are retained even when extraction fails or the shape is unfamiliar.
- A recognized format does not imply trusted domain facts; canonical publication still requires normalization, provenance, evidence, confidence, and quality gates.
- Unknown fields are preserved in the raw artifact and candidate payload rather than silently discarded.
- Duplicate payloads deduplicate by content hash; distinct source versions remain separately auditable.
- Conflicting candidates are emitted as evidence-linked conflict records and held for review; normalization never chooses a canonical value solely because it arrived first.
- Unsupported or ambiguous resources become `needs_review`/quarantined work and cannot block publication of an already-viewable revision.
- Source-specific adapters may understand a provider’s envelope or identifiers, but they must return the common resource/candidate contract before persistence.

## Developer workflows

The eventual repository should expose a small task interface, whether through `make`, `just`, or an equivalent task runner. The canonical workflows are:

```text
dev up                  Start Compose infrastructure and application services
dev down                Stop local services without deleting volumes
db migrate              Apply migrations
db reset                Recreate only the local development database
fixtures load           Load deterministic vehicle/source fixtures
purchase simulate      Emit a signed fake payment event
dataset fast            Trigger or replay fast-lane processing
dataset deep            Trigger deep enrichment fan-out
dataset inspect         Show request, entitlement, section, and revision status
evidence inspect        Resolve a fact to source/page/region evidence
jobs replay             Replay a selected dead-letter job
events relay            Deliver pending publication outbox events to NATS
test unit               Run Go and Python unit suites
test integration        Run service integration tests
test smoke              Run purchase -> viewable -> deep enrichment flow
```

`db reset` is local-only and must require an explicit destructive confirmation. It must never target a shared or production database.

The first-success developer path is:

1. Start Compose.
2. Apply migrations.
3. Load the deterministic source/product fixtures.
4. Simulate a payment webhook.
5. If the dataset request is delayed, run the payment reconciler and verify the event moves from `pending` to `fulfilled` with exactly one entitlement and projection.
6. Poll the request until `viewable`.
7. Read the dataset and section statuses.
8. Wait for or trigger deep enrichment.
9. Verify a new revision and evidence link.
10. Inject a deep failure, confirm the core dataset remains viewable, replay the dead-letter job, and verify section recovery.

The implemented foundation smoke path can be run with the local fake values below:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml up -d postgres nats minio migration-runner

AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm ingestion-smoke
```

`ingestion-smoke` runs the deterministic `ingest-fixture` dependency first. It fails with a non-zero exit and an actionable message when the migration, payment/entitlement, normalized vehicle, source object, or `dataset.viewable` event contract is not satisfied. It is safe to rerun: the fixture uses stable identifiers and idempotency keys, while published revisions remain immutable.

For a local source drop containing mixed JSON, HTML, PDF, SVG, XML, or CSV resources, inspect the normalized bundle without uploading the raw files:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/normalize_source_directory.py "sample data" --region US
```

The command reports the normalized vehicle, typed candidate counts, evidence count, and quarantine reasons. It exits non-zero for missing directories or invalid source payloads. Raw sample files remain local fixtures unless their redistribution terms are explicitly approved.

Persistence is opt-in and local-only. When database and object-storage variables are configured, append `--persist` to write content-addressed artifacts and normalized records to the Compose stack. A bundle with review items is still stored for audit, but it cannot be treated as fully publishable until its quarantine items are resolved.

To persist a local directory through the same container image used by the ingestion worker, mount the directory read-only and provide only local development values:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -v "$PWD/sample data:/sample-data:ro" \
  -e AUTODATA_DB_ADDRESS=postgres:5432 \
  -e AUTODATA_POSTGRES_DB=autodata \
  -e AUTODATA_POSTGRES_USER=autodata \
  -e AUTODATA_POSTGRES_PASSWORD=local-dev-only \
  -e AUTODATA_S3_ENDPOINT=minio:9000 \
  -e AUTODATA_S3_ACCESS_KEY=localadmin \
  -e AUTODATA_S3_SECRET_KEY=local-dev-password \
  -e AUTODATA_SOURCE_BUCKET=autodata-sources \
  ingestion-worker python /app/scripts/normalize_source_directory.py \
  /sample-data --region US --source-version local-sample-v1 --persist
```

This command is a local verification path only. It does not publish the source directory to GitHub or an external provider. Repeating it with the same source version is idempotent for normalized records; raw resources remain content-addressed and auditable.

The deep-lane publisher can be exercised against a viewable fixture projection after the local environment variables are exported. Scheduling creates one pending job and one durable `dataset.deep.requested` outbox event per section; publishing a section requires approved evidence and creates a new immutable revision:

```sh
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -e AUTODATA_DEEP_PROJECTION_ID=<viewable-projection-id> \
  -e AUTODATA_DEEP_SCHEDULE_SECTIONS=diagnostics,procedures,electrical,embeddings,quality \
  enrichment-worker python /app/scripts/deep_lane_smoke.py

docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -e AUTODATA_DEEP_PROJECTION_ID=<viewable-projection-id> \
  -e AUTODATA_DEEP_SECTION=diagnostics \
  -e AUTODATA_DEEP_CONTENT='{"code":"P0300","description":"example"}' \
  -e AUTODATA_DEEP_EVIDENCE='[{"evidence_id":"source-locator-1","locator":"page=4","extracted_text":"P0300","confidence":0.99,"reviewer_state":"approved"}]' \
  enrichment-worker python /app/scripts/deep_lane_smoke.py
```

The API also exposes a dependency-free `/metrics` endpoint for in-process access-denied counters. It is intended to be network-restricted to the observability plane in deployed environments. Every API response carries an `X-Request-ID`; the API preserves a valid W3C `traceparent` when one is supplied and generates a safe request ID when it is absent or malformed. This makes an ID available to logs, error bodies, and downstream event-envelope correlation without requiring an observability vendor SDK. The operational metrics snapshot reads durable request, job, outbox, evidence, review, payment, revision, and source state and emits Prometheus-compatible text for a local scrape or a scheduled exporter:

```sh
curl http://127.0.0.1:8080/metrics

AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  payment-reconciler python /app/scripts/operational_metrics.py
```

The required local recovery check creates only `autodata_restore_check_<process-id>`, restores a custom-format PostgreSQL backup into it, verifies the migration ledger, and drops that exact temporary database in a `finally` path. It does not reset the development database or delete published revisions:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
python scripts/dev/backup_restore_smoke.py
```

The same section job is safe to replay. A failed section is recorded in `ingestion_jobs` and `dataset_section_status`, can be retried up to its configured limit, and moves to `dead_letter` without changing the last published revision for other sections. The placeholder projection ID and evidence above are future execution parameters, not committed credentials or source payloads.

Publication events are delivered from PostgreSQL through the outbox relay. The relay is a bounded, one-shot developer command; it claims pending or retryable events, publishes the immutable envelope to NATS JetStream, and records delivery state. It is safe to rerun because the event idempotency key is used as the NATS message ID and consumers must deduplicate redelivery:

```sh
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -e AUTODATA_OUTBOX_BATCH_SIZE=50 \
  -e AUTODATA_OUTBOX_ONCE=1 \
  enrichment-worker python /app/scripts/outbox_relay.py
```

`docker compose up` also starts `outbox-relay` as a continuously polling local service. Use `AUTODATA_OUTBOX_POLL_SECONDS` to change its interval. The command above sets `AUTODATA_OUTBOX_ONCE=1` for a bounded smoke run. Use `AUTODATA_OUTBOX_MAX_ATTEMPTS` to bound delivery retries. A failed event is retried on a later invocation until that limit is reached, then is marked `dead_letter` with its last error preserved. Outbox claiming and NATS publication are separate commits, so operational monitoring must treat duplicate delivery as normal and inspect `delivery_attempts`, `delivery_status`, and `delivered_at` when reconciling the database with JetStream.

The asynchronous and object-storage probes are bounded operational commands. The NATS probe is read-only and reports the configured JetStream stream; the object-storage probe creates missing configured buckets and upgrades them to versioning, which is required before source artifacts are accepted:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  payment-reconciler python /app/scripts/nats_health.py

AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -e AUTODATA_S3_ENDPOINT=minio:9000 \
  -e AUTODATA_S3_ACCESS_KEY=localadmin \
  -e AUTODATA_S3_SECRET_KEY=local-dev-password \
  payment-reconciler python /app/scripts/object_storage_health.py
```

Dead-letter replay is explicitly targeted and cannot accept both target types. After correcting the failure cause, replay one event or job; the command preserves the original idempotency key and nests the prior attempt/error metadata before returning it to `pending`:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  payment-reconciler python /app/scripts/replay_outbox.py --event-id <dead-letter-publication-event-id>
```

The replay command refuses a missing, non-dead-lettered, or already replayed target. It does not create a replacement event, rewrite a published revision, or bulk-reset a queue.

## Configuration contract

Configuration is grouped by subsystem and supplied through environment variables or a secret manager:

| Category | Examples | Secret? |
| --- | --- | :---: |
| Database | host, port, database, pool limits, migration mode | credentials are secret |
| NATS | URL, stream names, consumer names, retry limits, outbox batch/attempt limits | usually no; auth may be secret |
| Object storage | endpoint, region, bucket names, path style | credentials are secret |
| Source adapters | adapter name, fixture mode, request limits, source policy | tokens are secret |
| Payments | adapter mode, webhook path, provider IDs, Stripe price-ID mapping, checkout return URLs | signing secret and provider API key are secret |
| Authentication | issuer, audience, role claim, key-set URL | private keys are secret |
| Observability | service name, exporter endpoint, sampling rate | tokens may be secret |
| Workers | concurrency, timeout, batch size, model/provider version, embedding mode | provider keys are secret |

Examples use names and local fake values only. No real token, API key, private key, webhook secret, or credential may appear in documentation, fixtures, logs, or committed configuration.

## Deployment posture

The deployment design is provider-neutral and Kubernetes-compatible:

- Stateless Go API replicas behind a provider-neutral ingress/load balancer.
- Independently scaled fast and deep Python workers.
- PostgreSQL with automated backups, restore verification, connection pooling, and migration gates.
- NATS JetStream with durable streams, explicit retention, consumer limits, and dead-letter subjects.
- S3-compatible object storage with versioning, content hashes, lifecycle policies, and source-specific retention.
- Kubernetes readiness/liveness checks, resource requests/limits, rolling updates, disruption budgets, and one-shot migration jobs.
- Secret-manager interface for database, provider, authentication, and object-storage credentials.
- OpenTelemetry-compatible traces and metrics with request/correlation IDs propagated through API, database, NATS, and workers.

The platform keeps cloud-specific adapters behind interfaces for ingress, secrets, object storage, managed PostgreSQL, and observability. Docker Compose remains the contract for local parity; Kubernetes manifests are the contract for deployable topology, not a requirement to operate Kubernetes during development.

The initial deployable baseline is `infra/k8s/base.yaml`. It contains the API Service and two-replica rolling Deployment, independently scalable ingestion, enrichment, and payment-reconciler Deployments, a one-shot migration Job, and an API PodDisruptionBudget. The manifest references the externally managed `autodata-runtime-secrets` Secret and deliberately does not define or embed secret values. The `autodata-config` endpoint values and image references are provider-neutral defaults that must be replaced by an environment overlay before a cluster apply. Migration images are built and published as release artifacts; the migration Job is run and verified before API rollout.

Validate the manifest structure locally with `python scripts/dev/test_k8s_manifests.py`. A cluster-specific deployment pipeline may additionally run `kubectl apply --dry-run=server` against the target cluster and then apply the same reviewed manifest plus its environment overlay. The repository does not assume a Kubernetes context is available on a developer workstation.

## Reliability behavior

- Database writes and publication events use an outbox record so a committed revision cannot silently lose its event.
- Consumers persist an inbox/deduplication key before applying side effects.
- Transient worker failures retry with bounded exponential backoff.
- Exhausted jobs move to a dead-letter stream and mark only the affected request/section as failed.
- Source checkpoints allow page/range resume rather than restarting a large document set.
- A viewable revision is retained while deep work is retried.
- Payment events are reconciled when webhook acknowledgment and fulfillment scheduling are separated by a transient failure.
- Backups are useful only after restore verification; the operational runbook must test restoration into an isolated environment.
- PostgreSQL recovery uses `scripts/dev/backup_restore_smoke.py`; a failed restore blocks promotion and leaves the source database untouched.
- NATS JetStream recovery starts from durable stream state and the PostgreSQL publication outbox: inspect consumer lag, stop duplicate consumers if needed, replay pending/dead-letter outbox events with their original idempotency keys, and verify downstream deduplication before resuming normal traffic.
- MinIO recovery preserves content-addressed source objects and derived evidence artifacts; lifecycle rules may expire only artifacts past their documented retention watermark, never the source/evidence objects required by a published revision.
- Dead-letter replay is bounded and targeted: replay only the selected job/event after its failure cause is corrected, preserve the original idempotency key, and confirm the affected section returns to `processing`/`complete` without changing an earlier published revision.

## Required operational metrics

The first dashboards and alerts must cover:

- Payment confirmation to `viewable` latency.
- Fast-lane success, failure, retry, and review rates.
- Deep-lane completion by data section.
- Queue depth and oldest message age by stream/consumer.
- Retry and dead-letter counts.
- Extraction confidence distribution and low-confidence publication blocks.
- Human-review backlog and age.
- Revision publication rate and source watermark lag.
- Entitlement fulfillment lag and reconciliation failures.
- Source takedown, revision revocation, and access-denied counts.

The checked-in baseline alert policy is [`infra/observability/prometheus-alerts.yaml`](../../infra/observability/prometheus-alerts.yaml). It uses only the provider-neutral metric names above, separates page-level availability/billing failures from warning-level freshness/review signals, and links each alert to a repository runbook. A deployment may translate these rules into its observability provider, but it must preserve the thresholds, severity intent, and runbook links or record an explicit reviewed policy change.
