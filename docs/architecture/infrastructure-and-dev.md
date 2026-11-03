# AutoData Infrastructure and Developer Environment

## Local topology

The local environment is deterministic and containerized. Docker Compose provides service parity without requiring a cloud account.

```text
                    +-------------------+
                    |      Go API        |
                    +---------+---------+
                              |
                    +---------v---------+
                    | Internal ingestion |
                    | HTTP gateway       |
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
- Internal ingestion HTTP gateway for bounded API-to-worker requests. It is reachable only through the cluster/private Compose network and forwards URL article intake and cache-first knowledge queries to the Python ingestion boundary.
- Python ingestion worker for source adapters, fast-lane normalization, OCR, and extraction.
- Python enrichment worker for deep sections, embeddings, cross-record validation, and publication.
- Publication outbox relay for at-least-once delivery from PostgreSQL to NATS JetStream.
- Migration runner for applying schema changes from a clean database.
- Deterministic fake source connector that can emit core data, document pages, diagrams, failures, and source drift.
- Deterministic fake payment/webhook service for purchase, duplicate webhook, refund, and delayed fulfillment scenarios.
- Payment reconciler that polls pending verified events and safely retries delayed entitlement fulfillment.
- Optional Mailpit and OpenTelemetry-compatible services behind a development profile.

### Container image provenance

Local Compose continues to use its existing MinIO service and persistent volume.
GitHub Actions adds a CI-only Compose override for a publicly pullable SeaweedFS
S3 service from GitHub Container Registry, pinned by multi-platform manifest
digest. GHCR avoids unauthenticated Docker Hub pull quotas on shared runners.
The override maps the existing CI credentials to SeaweedFS, pre-creates the
test bucket, uses a separate disposable data volume, and exposes the same
internal S3 port expected by the application. It never mounts or migrates the local MinIO volume. The
reason for the CI-only override and its verification are tracked in Issue #111
and `docs/superpowers/plans/2026-10-03-ci-s3-image-access.md`.

The Go API uses the same PostgreSQL connection pool for purchaser-facing
projection reads and dataset-request status when `AUTODATA_PROJECTION_STORE`
is set to `postgres`. In that mode, request creation stores the product,
vehicle, region, lifecycle status, processing lane, organization owner,
correlation identity, processing version, and unique idempotency key in
`dataset_requests`. A replay reads the existing row inside a transaction and
cannot cross organization boundaries. Before a projection exists, request
section readiness is derived from the product's immutable `minimum_sections`
contract as `pending`; after projection materialization, the API reads the
durable `dataset_section_status` rows. The default non-PostgreSQL mode keeps
the in-memory stores for API-only tests and local handler development.

## Universal source intake

Source connectors do not write directly to canonical tables. Every connector returns one or more immutable `SourceResource` envelopes containing the source URI, source version, connector media type when available, raw bytes, optional locator, attribution/terms metadata, and retrieval metadata. The intake boundary computes a SHA-256 content address before interpretation and stores the raw resource in object storage.

The format layer is provider-neutral:

| Input | Intake result | Downstream capability |
| --- | --- | --- |
| JSON or JSON API envelope | Structured artifact with preserved headers and body | Typed record extractor and schema validation |
| XML, CSV, or other structured text | Structured artifact retaining original bytes | Format-specific record extractor |
| HTML or plain text | Document artifact | Text extraction, OCR fallback, and evidence locators |
| PDF | Document artifact | Native page extraction; optional rasterization/OCR and page/region evidence |
| SVG or other diagram media | Diagram artifact | Diagram metadata, rendering, and diagram evidence |
| Unknown or unsupported media | Quarantined artifact | Operator review or a newly registered capability |

Extractors are selected by declared capabilities and observed content, not by a hard-coded filename convention. Generic connector media types such as `application/octet-stream` and `text/plain` are content-sniffed for recognizable JSON, HTML, XML, SVG, PDF, and conservative delimited-text signatures; a filename is never the sole parser. A source may emit multiple resource types in one request: for example, a vehicle identity response, a parts collection, an article index, an HTML procedure, a PDF, and an SVG diagram. JSON envelopes may additionally declare an embedded HTML document or base64 PDF in `body.html` or `body.pdf`; the adapter treats the outer JSON as the persisted source artifact, records the embedded content hash, and reuses the normal document/PDF/OCR path under an explicit `body.html:{document_id}` or `body.pdf:{document_id}:...` locator. Each top-level resource receives its own content hash, object key, extraction run, and evidence path, while the request correlation ID joins them into one dataset projection.

For an otherwise-unrecognized JSON shape, the ingestion worker has an explicit opt-in Mercury-2 advisory path (`AUTODATA_MERCURY2_EXTRACTION_ENABLED=1`). The bounded extractor receives the source URI, media type, and parsed document and may return only typed candidates with source locators; it must not infer absent facts. The normalizer, provenance/evidence builder, confidence checks, duplicate/conflict gates, and human review state remain authoritative. The raw source is retained regardless of model success. Missing credentials, provider errors, invalid JSON output, input-size limits, candidate-count limits, or an empty proposal leave the artifact `needs_review` and retryable without blocking unrelated resources or revoking an already-viewable revision. The model is never called for a resource that already has deterministic candidates.

The reference `HttpSourceConnector` provides a protocol-neutral HTTP(S) capture for sources that expose one resource per request. It rejects non-HTTP(S) URIs and embedded URL credentials, applies a bounded timeout and maximum payload size, records the response status and non-request response headers, and retains the final URI when a source redirects. A request or deployment may provide an explicit source version; otherwise the connector uses the configured version, ETag, Last-Modified value, or a content-hash version. Authentication headers are supplied only through secret-managed runtime configuration (`AUTODATA_SOURCE_REQUEST_HEADERS_JSON`) and are never placed in source fixtures, logs, or committed examples. Multi-resource provider APIs can implement the same `SourceConnector` contract and return one `SourceResource` per response/page/file.

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

### Local Workspace Service Configuration and Smoke Probes

The local development environment accommodates both containerized Compose stacks and direct host execution:

- **API Ports:** Docker Compose defaults to port `:8080`, while the host systemd service (`autodata-api.service`) defaults to port `:18080` (configured via `AUTODATA_API_ADDR=:18080` and `AUTODATA_API_BASE_URL=http://127.0.0.1:18080` in `.env.example`).
- **Migration Runner Resilience:** `scripts/dev/migrate.py` automatically resolves the PostgreSQL address. When `AUTODATA_DB_ADDRESS` is not explicitly exported, it probes `127.0.0.1:5432` for host execution and falls back to `postgres:5432` when operating inside a Docker network.
- **Unified Smoke Probing:** `scripts/dev/smoke_local_stack.py` and `scripts/dev/api_runtime_smoke.py` accept `--base-url`, respect `AUTODATA_API_BASE_URL` and `AUTODATA_API_ADDR`, and probe port `18080` as an automatic fallback if port `8080` is not active on `127.0.0.1`.
- **Fast-Lane Fixture Seeding:** `autodata_ingestion.ingest_fixture` defaults `AUTODATA_FAKE_PAYMENT_SIGNING_SECRET` to `"local-fixture-signing-key"` and handles optional NATS event broadcasting gracefully during standalone or offline local database seeding.
- **Payment Reconciliation & Worker Resilience:** `scripts/dev/reconcile_payments.py` automatically probes `127.0.0.1:5432`, defaults credentials to `"local-dev-only"`, supports `--address`/`--database-url` overrides, and accepts `--once`, `--batch-size`, and `--poll-seconds` CLI flags for flexible one-shot or continuous reconciliation. Worker modules (`publisher`, `outbox`, and ingestion persistence adapters) safely fallback to default credentials rather than raising `KeyError`.
- **Developer Operations Scripts:** `scripts/dev/operational_metrics.py`, `scripts/dev/payment_reconciliation_smoke.py`, `scripts/dev/replay_outbox.py`, and `scripts/dev/backup_restore_smoke.py` default to `"local-dev-only"` password, support `--address`/`--database-url` options, and automatically probe local database and S3 ports, supporting immediate execution on host developer workstations.
- **Deep-Lane Smoke Auto-Discovery & Database Overrides:** `scripts/dev/deep_lane_smoke.py` supports `--address`/`--database-url`, `--projection-id`, `--section`, and automatic database projection discovery when no projection ID is supplied, using a valid approved evidence fixture default.
- **Ingestion Smoke Hardening & CLI Ergonomics:** `scripts/dev/ingestion_smoke.py` includes contract and worker package path resolution, automatic `127.0.0.1` database and S3 endpoint probing, non-blocking NATS broker probing, silent error callback handling for offline brokers without stderr tracebacks, and supports `--address`, `--s3-endpoint`, and `--nats-url` CLI arguments for targeted endpoint testing.
- **Connector Prefix Routing & Figure Localization:** `procedure_images._read_asset_resource` dynamically inspects registered connectors from `source_connector_registry(include_defaults=True)`, resolves connector prefixes (such as `bankone:asset/...` and `banktwo:asset/...`), and provides structured error handling when a connector is unconfigured.
- **Document Block Image Hydration & Figure Localization:** `_collect_image_records`, `_rewrite_document_images`, and `hydrate_article_image_urls` in `procedure_images` recursively traverse `normalized_document` blocks to collect, rewrite, and hydrate direct `images` lists on arbitrary blocks (callouts, steps, sections) as well as nested child elements under `children`. Both default `artifact://{image_id}` URIs and offline `embed_data_uri` data URIs are consistently applied.
- **Step Normalization, List Hygiene & Block Figure Preservation:** `article_document._step_block` normalizes procedure step and instruction blocks, extracting action/instruction text (including joined strings from mapping elements in `instructions`), resolving step numbers, preserving step metadata, normalizing direct figure lists via `_normalize_cell_image`, and aggregating/deduplicating attached item-level images from dictionary instructions. `document_from_steps` and `_blocks_from_steps` unpack dictionary instruction items safely, extracting clean text without serializing Python dictionary reprs, and support step title, name, and text fallback extraction for legacy procedures. `_list_block` extracts clean text from dictionary items having `text`, `value`, `label`, `content`, `body`, or `message` keys, preserves author-defined `label`, `title`, and `heading` attributes, and normalizes and preserves direct `images` lists and item-level images via `_normalize_cell_image`. `_callout_block` preserves custom author titles/headings (`title`, `heading`), synthesizes composite text from bullet `items` when text is omitted, and normalizes and aggregates direct and item-level images from `items` without duplicate figures. `_table_block` preserves direct attached `images` lists via `_normalize_cell_image`, aggregates row-level images from dictionary rows (`row.get("images")`), deduplicates table figures using `_image_identities`, and supports `title`/`heading` label extraction, while `_table_cell` normalizes `content`, `body`, and `label` in direct and nested cell blocks. `_image_block` supports `description`, `legend`, and `title` fallbacks for caption and alt text and retains `content_sha256`, with `_normalize_cell_image` supporting `title` fallback for captions. Numbered step blocks and paragraph blocks normalize and preserve direct `images` lists and deduplicate figures via `_image_identities`, with paragraph and heading text resolving `content` and `body` fallbacks. `_evidence_ids` resolves both singular (`evidence_id`) and plural (`evidence_ids`) references on raw blocks and articles. Pre-scan image deduplication in `build_ordered_document` captures attached figures across all source blocks, list items, `uri`/`path` identifiers, and `asset_resource_ref` references into `seen_image_keys`, preventing duplicate trailing figure insertions.
- **Outbox Relay, Migration & Replay CLI Ergonomics:** `scripts/dev/outbox_relay.py`, `scripts/dev/replay_outbox.py`, and `scripts/dev/migrate.py` resolve worker virtual environments, support `--address`/`--database-url` and `--nats-url`/`--url` CLI options, and provide safe connection fallbacks for local and containerized stacks, forwarding address and broker parameters directly to `autodata_enrichment.outbox.relay_pending_events`. `scripts/dev/nats_health.py` supports `--address` and `--nats-address` alongside `--url` and `--nats-url` with automatic `nats://` scheme normalization, `scripts/dev/object_storage_health.py` supports `--address` and `--s3-address` alongside `--endpoint` and `--s3-endpoint`, and `scripts/dev/ingestion_smoke.py` supports `--endpoint`, `--s3-address`, and `--url` aliases. `scripts/dev/knowledge_warm_path_benchmark.py` supports `-q` as a shorthand for `--query`.
- **Ingestion Persistence Endpoint Resilience & Service CLI Uniformity:** `autodata_ingestion.bundle_persistence`, `vehicle_selection_persistence`, `derived_article_persistence`, `bankone_job_persistence`, `procedure_images`, `catalog_sync`, `knowledge_catalog`, `catalog_service`, `chat_durable_runtime`, `knowledge_fallback_runtime`, and `ingest_fixture` automatically probe `127.0.0.1:5432` and `127.0.0.1:9000` when running directly on the host, eliminating connection failures when container DNS names are unexported. `persist_source_bundle`, `persist_vehicle_selection_list`, `persist_derived_article`, `persist_catalog_years`, `persist_fast_lane`, `catalog_sync._conninfo`, and `persist_bankone_article_fetch_jobs` support explicit `address` parameter overrides passed to `_resolve_database_address`, with `execute_bank_batch` and `scripts/dev/ingest_bankone_batch.py` propagating address overrides directly. `scripts/dev/ingest_bankone_service.py`, `scripts/dev/ingest_banktwo_service.py`, `scripts/dev/normalize_source_directory.py`, and `scripts/dev/backup_restore_smoke.py` support `--address` and `--database-url` CLI arguments to route persistence and database commands dynamically.
- **PDF Figure Extraction, Table Figure Preservation, Document Hydration & Inline Image Localization:** Ingestion adapters extract browser-safe figures embedded in PDF source documents, deduplicate repeating logos/headers across pages, merge images across multi-page document records, align figure captions with ordered document blocks, preserve direct and nested table cell images and attributes during document normalization, validate list block item sequences, sanitize unsafe link protocols in `_safe_link`, normalize image blocks with `asset_resource_ref` to retain attributes and compute availability consistently, hydrate images and table cell figures recursively in `normalized_document` via `hydrate_article_image_urls`, recursively collect images from `normalized_document` blocks and table/grid cells in `procedure_images._collect_image_records` to localize document-only and cell-level figures, prevent duplicate figure insertions, preserve unresolved asset references and non-empty attributes during bundle normalization, support multi-key image matching (`id`, `artifact_key`, `asset_resource_ref`, `source_url`, `src`, `href`, `uri`, `path`, `content_sha256`, `storage_key`) and table cell figure localization in `procedure_images`, and persist inline `data:image/` figures into MinIO object storage (`procedure-images/<sha256>`) resolved to `artifact://<image_id>` references.
- **Provider-Neutral Bank Batch Ingestion:** `autodata_ingestion.bankone_batch` exports canonical provider-neutral aliases `BankBatch`, `execute_bank_batch`, and `build_bank_batch_plan`, enabling `scripts/dev/ingest_bankone_batch.py`, `scripts/dev/ingest_bankone_service.py`, `scripts/dev/ingest_banktwo_service.py`, and future multi-bank connectors to ingest catalog batches neutrally with `--limit` CLI slicing, `--address` parameter propagation, and worker virtual environment auto-discovery.
- **Universal Developer Scripts Ergonomics:** All developer and smoke tools (`scripts/dev/normalize_source_directory.py`, `scripts/dev/reconcile_payments.py`, `scripts/dev/ingest_bankone_service.py`, `scripts/dev/ingest_banktwo_service.py`, `scripts/dev/deep_lane_smoke.py`, `scripts/dev/smoke_local_stack.py`, `scripts/dev/replay_outbox.py`, `scripts/dev/fake_integrations_smoke.py`, `scripts/dev/ingest_bankone_batch.py`, `scripts/dev/api_runtime_smoke.py`, `scripts/dev/backup_restore_smoke.py`, `scripts/dev/operational_metrics.py`, `scripts/dev/payment_reconciliation_smoke.py`, `scripts/dev/universal_article_smoke.py`, `scripts/dev/knowledge_warm_path_benchmark.py`, `scripts/dev/migrate.py`, `scripts/dev/migration_plan.py`, `scripts/dev/consumer_agent.py`, `scripts/dev/nats_health.py`, `scripts/dev/object_storage_health.py`, and `scripts/dev/ingestion_smoke.py`) auto-discover worker virtual environment site-packages in `sys.path` and support programmatic `main(argv=None)` invocation with flexible CLI parameter handling, including `--url`, `--api-url`, and `--base-url` aliases across API and smoke probes (`universal_article_smoke.py`, `smoke_local_stack.py`, `api_runtime_smoke.py`, `fake_integrations_smoke.py`, `consumer_agent.py`) and `--database-url` aliases across persistence tools. `scripts/dev/smoke_local_stack.py` wraps network probes with formatted diagnostic error exits without unhandled tracebacks.
- **Contract Verification & Check Mode:** `scripts/contracts/generate.py` supports programmatic `main(argv=None)` and `--check` CLI mode to verify that generated Go and Python bindings match canonical specifications without modifying files on disk, enabling automated CI contract drift detection.
- **Pre-Implementation Preflight CLI Validation:** `scripts/autonomy/pre_implementation.py` supports programmatic `main(argv=None)` and CLI invocation with `--record`, `--base-sha`, `--repo-root`, and `--policy` options, returning structured JSON outputs and exit codes (0 for valid, 1 for errors), enabling automated gate validation by developers, automation tools, and CI pipelines.
- **Directory Normalization Filtering:** `scripts/dev/normalize_source_directory.py` supports `--limit` to bound source resource adaptation and extraction during quick local exploratory inspections.

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

The active product UI is the provider-neutral Workshop at `/workshop/`. The `/dashboard/` page is a small landing page; there is no chat worker or chat smoke service in the default stack.

For a local source drop containing mixed JSON, HTML, PDF, SVG, XML, or CSV resources, inspect the normalized bundle without uploading the raw files:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/normalize_source_directory.py "sample data" --region US
```

The command reports the normalized vehicle, typed candidate counts, evidence count, and quarantine reasons. It exits non-zero for missing directories or invalid source payloads. Raw sample files remain local fixtures unless their redistribution terms are explicitly approved.

The same provider-neutral path can run once through the ingestion worker boundary. This is useful for a local source drop and exercises connector discovery, content-first media detection, normalization, and quality evaluation without requiring a provider-specific adapter:

```sh
AUTODATA_SOURCE_DIRECTORY=/sample-data \
AUTODATA_SOURCE_VERSION=local-sample-v1 \
AUTODATA_SOURCE_REGION=US \
AUTODATA_SOURCE_PERSIST=0 \
AUTODATA_WORKER_ONCE=1 \
docker compose -f infra/compose/compose.yaml run --rm --no-deps \
  -v "$PWD/sample data:/sample-data:ro" \
  ingestion-worker python -m autodata_ingestion.worker
```

The worker emits a deterministic JSON summary with bundle readiness, quality/review status, source artifact count, evidence count, and quarantine reasons. The local directory normalizer additionally emits a payload-free `source_report` array: each record contains source URI/version, media type, content hash, object key, artifact kind, candidate counts and kinds, extraction status, a review flag, and stable review reason codes. Persisted source conflicts and quarantine reasons also create idempotent `source_review_items` rows, linked to source snapshot and extraction-evidence UUIDs. Similar-article quarantine records are coalesced with their article-similarity conflict, so reviewers receive one queue item per ambiguity. Replays update the same pending item. Embedded-resource records include only their locator, media type, embedded hash, candidate count, and extraction status; raw payloads and credentials are never copied into the report. The intake registry is open to source-specific media adapters without changing the event envelope or connector contract. The built-in document path extracts visible HTML text, UTF-8 plain text, and page-level text from text-based PDFs through the pinned `pypdf` dependency into reviewable evidence. Explicit `body.html` and base64 `body.pdf` fields in JSON envelopes reuse that path and retain outer/embedded hashes in metadata and evidence. Raster image sources use the optional `pytesseract`/Tesseract OCR runtime and emit confidence-aware region evidence; the ingestion image installs the open-source Tesseract binary. Mixed or scanned PDFs rasterize only pages without native text through pinned `pdf2image` and the Poppler `pdftoppm` runtime, then send the resulting PNG bytes through the same OCR boundary. The original PDF hash remains the evidence content address, and locators include the rendered page number and OCR region. SVG diagrams contribute only literal labels; their geometry remains raw. If an embedded-resource adapter, PDF rasterization, or OCR capability is unavailable, the outer source remains raw with review metadata and can be replayed after the worker image capability is deployed. Set `AUTODATA_SOURCE_PERSIST=1` only when the local PostgreSQL and MinIO connection variables are configured; this remains an explicit local execution path, not the production NATS dispatcher.

Vehicle selector lists use the same persistence boundary. `AUTODATA_VEHICLE_LIST_JSON` accepts coarse and rich rows, while `AUTODATA_VEHICLE_LIST_SOURCE_URI` and `AUTODATA_SOURCE_VERSION` identify the immutable list snapshot. With `AUTODATA_SOURCE_PERSIST=1`, the worker stores the raw list in object storage, records one evidence locator per row, and upserts the canonical vehicle base/configuration graph. A later `99 Silverado 1500 2WD 5.3LT` observation therefore resolves to the existing `chevrolet-silverado-1500-1999-us` base and its `...-engine-5-3l` configuration. Rows without a region require `AUTODATA_SOURCE_REGION`; conflicting known dimensions are retained as reviewable identity observations rather than merged.

The AutoAPI batch path additionally persists one `autoapi_article_fetch_jobs` row per planned vehicle when selector persistence is enabled. The row is keyed by adapter, source version, vehicle family, and source location. A selector-only vehicle is `pending` until its bundle arrives; a worker claim moves pending or retryable work to `processing`; a processed bundle is `completed` or `needs_review`; and an exception is `failed` with its checkpoint and error metadata. After the configured claim limit, a failure becomes `dead_letter` and requires explicit operator replay. Terminal states are not reopened by duplicate success or failure calls. Replaying the same source updates the existing row and does not create another fan-out job. The job table is an ingestion work ledger, not a substitute for the immutable source snapshots, normalized article records, or source-review queue.

Knowledge requests use a cache-first path. If the request omits `catalog`, the worker performs a bounded indexed read of active `catalog_articles` for the canonical vehicle key and ranks the normalized results locally. Component job-plan queries add bounded title filters for the requested normalized components before applying `AUTODATA_KNOWLEDGE_CACHE_MAX_RECORDS` (default `200`, clamped to `1..1000`), so an oil- or water-pump article is not missed merely because it sorts beyond the first page of a large vehicle catalog. Unfiltered reads exclude linked duplicates; component-scoped reads use the requested title filters and `DISTINCT ON article_id` so stale duplicate-link metadata cannot hide a valid requested article. Both paths exclude taken-down snapshots and rows without persisted evidence. The worker only calls the configured universal source resolver after the indexed lookup produces no matching article or procedure. An explicit empty `catalog` is reserved for deterministic fallback tests. The database reader includes stored configuration dimensions, the persisted extraction-evidence UUID, artifact key, extracted text, review state, and source watermark metadata. It resolves evidence by source snapshot plus locator so every cache hit remains traceable to the ingestion and review boundary.

To capture one HTTP(S) source resource through the same worker, replace the directory variables with `AUTODATA_SOURCE_URI=https://source.example/resource`. If authentication is required, inject `AUTODATA_SOURCE_REQUEST_HEADERS_JSON` from the deployment secret interface; keep its value out of shell history, documentation, and logs. The HTTP connector enforces `AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS` and `AUTODATA_SOURCE_MAX_BYTES` limits, defaulting to 30 seconds and 50 MiB.

The running Compose stack also exposes the supported application path through the Go API. `POST /article-intakes` requires the `ingestion_operator` role and accepts a JSON object containing `source_uri` and a vehicle mapping; it forwards the request to the private `ingestion-http` service. `POST /knowledge-queries` requires `dataset_viewer` and performs the indexed cache lookup before invoking the configured source resolver. Both requests require a caller-supplied `Idempotency-Key`, and the API returns the worker's structured JSON response without exposing the internal service to the host network:

```sh
curl -sS -X POST http://127.0.0.1:8080/knowledge-queries \
  -H 'Content-Type: application/json' \
  -H 'X-Roles: dataset_viewer' \
  -H 'Idempotency-Key: local-knowledge-query-001' \
  -d '{"vehicle":{"year":1999,"make":"Chevrolet","model":"Silverado 1500","drive_type":"2WD","engine":"5.3L"},"query":"brake procedure"}'

curl -sS -X POST http://127.0.0.1:8080/article-intakes \
  -H 'Content-Type: application/json' \
  -H 'X-Roles: ingestion_operator' \
  -H 'Idempotency-Key: local-article-intake-001' \
  -d '{"source_uri":"https://source.example/article","vehicle":{"year":1999,"make":"Chevrolet","model":"Silverado 1500","drive_type":"2WD","engine":"5.3L"}}'
```

These are future-execution examples: use a permitted source URI and the deployment's real authentication middleware when the API is exposed outside local development. The internal gateway accepts only HTTP(S) source URIs, applies the same source size/time limits as the worker, and returns `422` for invalid request shapes or `502`/`503` for unavailable downstream processing. Its optional `AUTODATA_INGESTION_INTERNAL_TOKEN` is supplied through a secret interface; it is blank only for the isolated local Compose network.

The ingestion worker also contains a durable pull-consumer boundary for version-one `dataset.fast.requested` events. The consumer is wired to the transactional fast-lane projection publisher but remains disabled by default as a deployment safety gate. Enable it only with `AUTODATA_FAST_CONSUMER_ENABLED=1` and `AUTODATA_SOURCE_PERSIST=1`, after database and object-storage credentials are available through the environment or secret interface. Use `AUTODATA_FAST_CONSUMER_DURABLE` for the stable consumer name and `AUTODATA_FAST_CONSUMER_MAX_DELIVERIES` for the bounded delivery limit. The consumer acknowledges only successful handler completion, applies exponential `nak` delays to retryable failures, immediately dead-letters malformed or incorrectly configured requests, and publishes exhausted work to `dataset.fast.dead_letter` with a stable NATS message ID. It never receives source credentials from an event.

The ingestion worker also contains the vehicle-scoped knowledge fallback
consumer. Enable it with `AUTODATA_KNOWLEDGE_CONSUMER_ENABLED=1`,
`AUTODATA_SOURCE_PERSIST=1`, and either an explicit source hint in the event
or `AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE` with `{make}`, `{model}`,
`{year}`, `{region}`, `{vehicle_key}`, `{query}`, and `{keywords}`
placeholders. The handler loads the latest normalized revision for a warm
lookup, resolves and fetches only on a miss, persists source/evidence data,
appends an immutable article revision, and emits `dataset.section.published`.
Use `AUTODATA_KNOWLEDGE_CONSUMER_DURABLE` and
`AUTODATA_KNOWLEDGE_CONSUMER_MAX_DELIVERIES` for durable delivery settings.
Retryable source failures use bounded exponential NAK delays; invalid events,
vehicle mismatches, and unresolved source configuration are dead-lettered.
The URL template and request headers are configuration only and must not
contain credentials committed to the repository.

The enrichment worker has a separate durable `dataset.viewable` consumer for deep-lane fan-out. Enable it with `AUTODATA_VIEWABLE_CONSUMER_ENABLED=1` after the fast-lane consumer is enabled. It validates the event, selects the default independent sections (`diagnostics`, `procedures`, `electrical`, `inventory`, `maintenance`, `search`, and `quality`) unless the event supplies an explicit list, and calls the idempotent deep scheduler. A duplicate viewable event reuses the existing job and event idempotency keys. Invalid events are dead-lettered immediately; transient scheduling failures use bounded exponential retry. Deep section execution remains independent, so a failed section does not withdraw a viewable revision.

The same enrichment deployment can consume `dataset.deep.requested` events when `AUTODATA_DEEP_CONSUMER_ENABLED=1`. That consumer validates the source snapshot, projection, section, processing version, and idempotency identity before invoking the registered section processor. The reference image registers conservative `diagnostics`, `procedures`, `electrical`, `inventory`, `maintenance`, `search`, and `quality` processors. Diagnostics selects only approved evidence containing an explicit DTC code or diagnostic term; the procedures, electrical, inventory, and maintenance processors select approved evidence with explicit section signals; search indexes approved source evidence with its original locator and artifact key; and quality summarizes approved evidence counts, artifacts, and confidence buckets. All processors delegate publication to the immutable section publisher, which creates embeddings and the next revision, and none turns unreviewed text into canonical facts or claims that a heuristic match is a canonical domain fact. Section processors remain the extension point for richer OCR, document extraction, normalization, evidence approval, and domain-specific validation; an unregistered section is dead-lettered as an explicit configuration failure rather than acknowledged. Processor failures are retried with bounded backoff, and successful processors must invoke the immutable section publication contract.

Persistence is opt-in and local-only for source-drop commands. When database and object-storage variables are configured, append `--persist` to write content-addressed artifacts and normalized records to the Compose stack. A durable fast-lane event additionally supplies the request/projection identity and publishes only after the entitlement, minimum-section contract, provenance, and evidence-review gates pass. A bundle with review items is still stored for audit, and each conflict or quarantine reason is queryable through `source_review_items`, but it cannot be treated as fully publishable until its quarantine or review items are resolved.

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

# Or directly on host with CLI flags:
python3 scripts/dev/outbox_relay.py --once --limit 50
```

`docker compose up` also starts `outbox-relay` as a continuously polling local service. Use `AUTODATA_OUTBOX_POLL_SECONDS` (or `--poll-seconds`) to change its interval. The command above sets `AUTODATA_OUTBOX_ONCE=1` (or `--once`) for a bounded smoke run. Use `AUTODATA_OUTBOX_MAX_ATTEMPTS` (or `--max-attempts`) to bound delivery retries. A failed event is retried on a later invocation until that limit is reached, then is marked `dead_letter` with its last error preserved. Outbox claiming and NATS publication are separate commits, so operational monitoring must treat duplicate delivery as normal and inspect `delivery_attempts`, `delivery_status`, and `delivered_at` when reconciling the database with JetStream.

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
| Internal ingestion gateway | `AUTODATA_INGESTION_URL`, `AUTODATA_INGESTION_HTTP_ADDR`, request timeout | internal token is secret |
| Payments | adapter mode, webhook path, provider IDs, Stripe price-ID mapping, checkout return URLs | signing secret and provider API key are secret |
| Authentication | issuer, audience, role claim, key-set URL | private keys are secret |
| Observability | service name, exporter endpoint, sampling rate | tokens may be secret |
| Workers | concurrency, timeout, batch size, model/provider version, embedding mode | provider keys are secret |

Examples use names and local fake values only. No real token, API key, private key, webhook secret, or credential may appear in documentation, fixtures, logs, or committed configuration.

## Deployment posture

The repository retains a provider-neutral, Kubernetes-compatible reference design for general deployments. The paid Workshop hosting choice is the standalone VM lane described below; these reference resources do not establish its deployed topology:

- Stateless Go API replicas behind a provider-neutral ingress/load balancer.
- Independently scaled fast and deep Python workers.
- PostgreSQL with automated backups, restore verification, connection pooling, and migration gates.
- NATS JetStream with durable streams, explicit retention, consumer limits, and dead-letter subjects.
- S3-compatible object storage with versioning, content hashes, lifecycle policies, and source-specific retention.
- Kubernetes readiness/liveness checks, resource requests/limits, rolling updates, disruption budgets, and one-shot migration jobs.
- Secret-manager interface for database, provider, authentication, and object-storage credentials.
- OpenTelemetry-compatible traces and metrics with request/correlation IDs propagated through API, database, NATS, and workers.

The platform keeps cloud-specific adapters behind interfaces for ingress, secrets, object storage, managed PostgreSQL, and observability. Docker Compose remains the contract for local development. Kubernetes manifests are a reference contract for a separately selected cluster deployment; paid Workshop uses its standalone production Compose definition.

The generic Kubernetes reference baseline is `infra/k8s/base.yaml`. It contains the API Service and two-replica rolling Deployment, a private `autodata-ingestion-http` Service and independently scalable gateway Deployment, independently scalable ingestion, enrichment, and payment-reconciler Deployments, a one-shot migration Job, and an API PodDisruptionBudget. The manifest references the externally managed `autodata-runtime-secrets` Secret and deliberately does not define or embed secret values. The `autodata-config` endpoint values and image references are provider-neutral defaults that must be replaced by an environment overlay before a cluster apply. Migration images are built and published as release artifacts; the migration Job is run and verified before API rollout. The API communicates with the gateway through the cluster DNS name `http://autodata-ingestion-http:8081`; no gateway port is exposed through a load balancer or ingress.

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


## Explicit customer authentication runtime

The API requires AUTODATA_ENV, AUTODATA_AUTH_MODE and AUTODATA_PUBLIC_ORIGIN.
Compose/Base44 select development/local explicitly; CI selects test/local.
These headless fixtures retain existing header authentication but expose no
browser login or demo account. HTTPS localhost origins are configuration values;
local stacks do not gain a TLS listener from this setting. Only test mode permits
an HTTP loopback origin. Staging/production require firebase mode; production
origin is exactly https://cars.tk.

Firebase mode additionally requires AUTODATA_FIREBASE_PROJECT_ID,
AUTODATA_FIREBASE_WEB_API_KEY, AUTODATA_FIREBASE_WEB_APP_ID and
AUTODATA_FIREBASE_AUTH_DOMAIN. Kubernetes references these public app values
from externally managed ConfigMap autodata-firebase-config. Its absence fails
startup instead of selecting local mode. Do not put service-account JSON into
that ConfigMap or the checkout. Provision the runtime's approved ADC/workload
identity and Firebase Auth user-read permission separately; the provider-neutral
manifest does not invent a cloud service account or binding. Firebase mode
rejects FIREBASE_AUTH_EMULATOR_HOST, in-memory persistence, unavailable PostgreSQL
and schema before 039. Run the shared migration driver before starting replicas.

All replicas use the same durable project+UID accounts and SHA256 session hashes.
Absolute sessions expire after 12 hours without sliding renewal. Every protected
request checks current database status and live Firebase user revocation against
original auth_time; outages fail503 without stale acceptance. Requests carrying
Authorization headers cannot fall back to customer cookies. Only dataset_viewer
is assigned; existing organization-owned reads retain their predicates.

See docs/verification/production-access-runbook.md for deterministic acceptance
and the separate live staging prerequisites. This identity change does not
certify commerce or paid catalog/media access.


## Paid Workshop standalone VM hosting lane (offline gate)

The selected cars.tk topology is one GCE VM with a separate persistent data disk, standalone [production Compose](../../infra/compose/compose.production.yaml) and Caddy. The [canonical thirty-path plan](../superpowers/plans/2026-11-03-workshop-hosting.md), [task](../agents/tasks/2026-11-03-production-release/workshop-hosting.json), [synchronized record](../agents/records/2026-11-03-workshop-hosting.json), [Issue186](https://github.com/lucronn/autodata/issues/186) and [Project8](https://github.com/users/lucronn/projects/8) govern this offline implementation scope. The [operations runbook](../operations/workshop-gcp.md) records exact definition interfaces and later rollout/recovery requirements. Local, CI and Base44 Compose keep their existing roles.

The steady service graph is Caddy, Go API, private ingestion HTTP, one article worker, payment reconciler, PostgreSQL, NATS JetStream and the pinned SeaweedFS S3 service under the existing `minio` service name. Migration, bootstrap and passive metrics are explicit one-shot operations. The paid lane uses PostgreSQL article/index jobs; the generic enrichment/outbox/demo/fixture lanes are outside this initial production graph. Only Caddy publishes 80/443 and serves the same-origin Workshop/API boundary. PostgreSQL, NATS, S3 and application/metrics listeners stay private. Released images must be immutable digests on the reviewed platform, with exact source/migration/configuration/secret-version bindings; a source checkout or build on the VM is outside the topology.

The proposed e2-standard-4 VM, 200 GiB balanced data disk, nightly maintenance and RPO24h/RTO4h remain owner decisions and measured-recovery targets. Project/billing/region, VPC, package/boot-image pins, provider authorization, alert destination and staging hostname remain prerequisites. No VM, persistent disk, firewall, static address, registry, bucket or DNS state is established by this document. Vercel remains in place until a separately approved final-origin cutover.

### Runtime and external identity boundaries

The sole proposed attached VM identity is `autodata-api-firebase@HOST_PROJECT_ID.iam.gserviceaccount.com`, with exactly `firebaseauth.users.get` on the selected Firebase project. Its explicit access-scope ceiling is cloud-platform, userinfo.email and identitytoolkit; IAM remains the permission boundary. That permission permits account read/list behavior and cannot be restricted to a requested UID. It grants no secret, registry, storage, snapshot, monitoring, logging, impersonation or IAM-administration authority. Real Firebase SDK refresh/GetUser/revocation behavior remains staging evidence.

The metadata design permits only the API's designated container address, with an explicit trusted UID0 host-platform exception. Other containers and unprivileged host users must be denied on IPv4, IPv6 and the metadata hostname. A separate storage guard permits application access only to S3 TCP 9000 at the fixed storage address, including both bridged and routed traffic. Root-owned fixed helpers, data-mount identity and guard-before-Docker dependencies are required. Rendering rules does not prove actual namespace isolation, OS Login/guest-agent behavior or reboot safety.

Four separate external GitHub OIDC/WIF principals are required: publish writes the named registry; deploy reads exact images/numeric secret versions and is a trusted host administrator; backup uses fixed non-admin host helpers plus reviewed snapshot/object-create authority; monitor uses only a fixed aggregate helper and external metricWriter. Backup and monitor receive no secret/deploy/Docker authority, and routine backup receives no delete permission. Restore and prune authority require separate approval. WIF trust must bind numeric repository/owner identity, exact approved workflow/ref and protected environment. These are reviewed authority definitions, not active IAM bindings.

External deploy delivery must stream only manifest-bound secret versions into service-specific tmpfs files, with no bearer token on the VM or containers. Entrypoints load only fixed service secret names immediately before exec; secret values must never be persisted as Compose environment metadata. The API has no credential-file/developer-home mount or emulator. The attached VM account cannot fetch secrets or registry credentials. Loss of tmpfs secrets after reboot must block startup until separately authorized external redelivery.

### Workflow and verification state

The [release](../../.github/workflows/release-workshop.yml), [backup](../../.github/workflows/backup-workshop.yml) and [monitor](../../.github/workflows/monitor-workshop.yml) workflows are guarded offline definitions. Each operation has its own enable variable and production environment, requires the exact master workflow ref and numeric repository/owner tuple, and validates four distinct configured service accounts. Release publish and deploy are separate manual choices; backup defines a 03:17 UTC daily/manual trigger, and monitor defines a five-minute/manual trigger. Job budgets are 45/30/30/1 minutes respectively. The runbook specifies all variable names and immutable dispatch fields.

Absent enable variables skip jobs. Enabled valid jobs still fail with exit 3 `missing_dependency`: no workflow has a WIF authentication, build/publish, artifact fetch/provenance, host-operation or metrics adapter. Permissions are only `contents: read`, with no OIDC-token request or action invocation. Deploy's run/artifact/digest fields receive syntax checks only. Neither a protected-environment name nor a matching configuration string proves environment protection, cloud identity or provenance. `cloud-bootstrap.sh` renders a nonexecuting plan; `cloud-ops.py` has fail-closed CLI entrypoints and an explicitly simulated fake backup evaluator.

Pure schema/render/fake-transcript tests provide offline contract evidence. They cannot certify actual IAM/network/metadata/storage denial, Firebase or Stripe behavior, licensed bank/model access, no-work readiness, package installation, startup/reboot/secret redelivery, backup cutoff/immutable generations, isolated restore/RPO/RTO, alert delivery or final-origin TLS. Monitoring requires native Compute metrics, external HTTPS uptime and a separately authenticated aggregate exporter; missing heartbeat must alert independently. No Ops Agent or VM-ADC monitoring path is proposed, and GitHub's coarse schedule does not promise a one-minute SLO.

Before staging, pin the final independently reviewed integrated release and resolve owner configuration/toolchain inputs under a separate authorization. Retain exact-SHA denial, runtime, recovery and notification evidence in Issue186/Project8 and canonical documentation. Final DNS/TLS/Firebase-domain and cars.tk cutover require another explicit gate. The current definitions do not establish an active cloud deployment or production readiness.


### Passive PostgreSQL schema observation: draft checkpoint

The [hosting plan's approved v3 passive-schema contract](../superpowers/plans/2026-11-03-workshop-hosting.md#passive-schema-observation-synchronized-plan-only-checkpoint) and [runbook prerequisites](../operations/workshop-gcp.md#passive-postgresql-schema-collector-draft-prerequisites) define the next bounded A milestone at planning base `bc62f86eac54eb81b61e4013f0e910f264556f6c`. Task/record are `synchronized` after coordinator live Issue186/Project8 readback; commit/push, exact-SHA preflight, coordinator integration/re-pin and independent checkpoint review remain required. Only runtime-check.py and test_host_runtime.py may change after that gate; original30-path ownership remains unchanged.

The proposed definition binds an existing local PostgreSQL17 container and dedicated socket-auth-only autodata_metrics role to fixed read-only SQL and a bounded exact ledger/rights protocol. It requires explicit nonownership, PUBLIC/column/MAINTAIN privilege checks, ordinary permanent non-RLS text-key relation checks, row/value bounds before aggregation and streaming capture limits. Future administration must provision role/HBA/ident; missing prerequisites remain unavailable. A Docker data mount is not an attestation of effective PostgreSQL configuration; the probe never reads superuser-only data_directory or gains broad monitoring privileges. No new secrets/mounts or real execution are included.

Concrete todo is canonical in the task/record and hosting plan: synchronize tracking/documents, independently approve the new pinned gate, implement only the two fake-exec-tested A paths, validate and independently review the exact candidate. Services/readiness/runtime evidence and mutation/deploy verbs stay blocked; real provisioning and runtime/staging proofs remain separately authorized.


Tracking synchronization read back: [Issue186 comment6617024444](https://github.com/lucronn/autodata/issues/186#issuecomment-6617024444) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, at `2026-11-03T22:27:57.522560+00:00`. The comment records the same v3 goal, five concrete todos, exact two-path implementation scope and offline limits; the project note indexes it. This is a plan-only synchronization checkpoint, not implementation dispatch or runtime/deployment authorization.
