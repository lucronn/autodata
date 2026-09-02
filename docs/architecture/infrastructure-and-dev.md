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
- Migration runner for applying schema changes from a clean database.
- Deterministic fake source connector that can emit core data, document pages, diagrams, failures, and source drift.
- Deterministic fake payment/webhook service for purchase, duplicate webhook, refund, and delayed fulfillment scenarios.
- Optional Mailpit and OpenTelemetry-compatible services behind a development profile.

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
5. Poll the request until `viewable`.
6. Read the dataset and section statuses.
7. Wait for or trigger deep enrichment.
8. Verify a new revision and evidence link.
9. Inject a deep failure, confirm the core dataset remains viewable, replay the dead-letter job, and verify section recovery.

## Configuration contract

Configuration is grouped by subsystem and supplied through environment variables or a secret manager:

| Category | Examples | Secret? |
| --- | --- | :---: |
| Database | host, port, database, pool limits, migration mode | credentials are secret |
| NATS | URL, stream names, consumer names, retry limits | usually no; auth may be secret |
| Object storage | endpoint, region, bucket names, path style | credentials are secret |
| Source adapters | adapter name, fixture mode, request limits, source policy | tokens are secret |
| Payments | adapter mode, webhook path, provider IDs | signing secret is secret |
| Authentication | issuer, audience, role claim, key-set URL | private keys are secret |
| Observability | service name, exporter endpoint, sampling rate | tokens may be secret |
| Workers | concurrency, timeout, batch size, model/provider version | provider keys are secret |

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

## Reliability behavior

- Database writes and publication events use an outbox record so a committed revision cannot silently lose its event.
- Consumers persist an inbox/deduplication key before applying side effects.
- Transient worker failures retry with bounded exponential backoff.
- Exhausted jobs move to a dead-letter stream and mark only the affected request/section as failed.
- Source checkpoints allow page/range resume rather than restarting a large document set.
- A viewable revision is retained while deep work is retried.
- Payment events are reconciled when webhook acknowledgment and fulfillment scheduling are separated by a transient failure.
- Backups are useful only after restore verification; the operational runbook must test restoration into an isolated environment.

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
