# AutoData

> Turn scattered repair data into a vehicle-specific procedure, quote, and
> evidence-backed answer.

![AutoData turns scattered repair data into a vehicle-specific procedure, quote, and evidence-backed workspace](docs/assets/autodata-platform-overview.png)

Finding the right repair answer is fragmented across manuals, generic search,
diagnostic data, parts catalogs, and wiring diagrams. AutoData brings those
sources together for one vehicle, preserves where the answer came from, and
turns a plain-language request into a usable repair workflow.

The result is a vehicle-specific workspace with the relevant procedure,
labor-and-parts quote, supporting source evidence, and clear review status. A
fast lane makes the first useful answer available quickly; a deep lane keeps
enriching it in the background.

[Architecture](docs/architecture/domain-model.md) ·
[Local quick start](#start-the-local-stack) ·
[Wiki](https://github.com/lucronn/autodata/wiki) ·
[Project #8](https://github.com/users/lucronn/projects/8)

## At a glance

- **Vehicle-scoped:** identity, configuration, procedures, specifications,
  diagnostics, evidence, and feedback stay attached to the requested vehicle
  projection.
- **Fast to useful:** the fast lane normalizes core facts and publishes an
  immutable, viewable revision without waiting for every enrichment section.
- **Built to deepen:** the deep lane adds documents, images, diagrams, search,
  embeddings, and quality review independently of the first viewable result.
- **Safe by default:** provenance, evidence, review status, entitlements, and
  source-rights boundaries are part of the platform contract.

The current verified local path is deterministic and uses PostgreSQL with
pgvector, NATS JetStream, MinIO, fake source data, and a fake payment provider.
It does not require cloud credentials. Generated procedures and source-derived
results remain explicitly `UNREVIEWED` until an authorized human review changes
their status.

The repository is a modular monorepo:

- `apps/api-go` — authenticated API, RBAC, entitlement-aware reads, feedback,
  and reviewer commands.
- `workers/ingestion-python` — provider-neutral source intake, normalization,
  provenance, fast-lane publication, and payment reconciliation.
- `workers/enrichment-python` — deep-lane section enrichment, evidence-backed
  search and quality processors, embeddings, immutable revisions, and
  publication outbox handling.
- `packages/contracts` — versioned API, event, and payment contracts.
- `db/migrations` — forward-only PostgreSQL and pgvector schema migrations.
- `infra/compose` and `infra/k8s` — local and Kubernetes-compatible topology.
- `docs/architecture` — canonical system, lifecycle, contract, and operations
  documentation.
- `docs/github` — repository and Project operating model.
- `docs/agents/pre-implementation-gate.md` — mandatory, agent-agnostic planning
  and GitHub/repository synchronization gate for implementation work.

For a guided introduction, start with the [GitHub Wiki](https://github.com/lucronn/autodata/wiki).
For the authoritative technical details, use the linked documents under
[`docs/`](docs/).

## Current development slice

The current development slice is tracked in [Issue #85](https://github.com/lucronn/autodata/issues/85) and [Project #8](https://github.com/users/lucronn/projects/8). The verified local path currently supports:

- natural-language component intent translation into an allowlisted vehicle-scoped query;
- query-aware normalized-article lookup with exact and near-duplicate protection;
- deterministic single-technician labor calculation with shared-operation overlap counted once;
- Mercury-2 composition of an evidence-linked multi-component procedure;
- persistence of the composed procedure as a reusable derived article;
- warm replay from PostgreSQL without repeating the source or model call; and
- dashboard rendering of every generated step with an explicit `UNREVIEWED` label.

The RAV4 examples are automated `ready` results, not technician approval. Source evidence remains pending human review, and a genuinely uncached source request still depends on the local AutoAPI service being available. Those are tracked separately from the completed cache, composition, and dashboard behavior.

The next planned product slice is the [chat-first natural-language quote and
procedure generator](https://github.com/lucronn/autodata/issues/87), tracked in
[Project #8](https://github.com/users/lucronn/projects/8). Its target
interaction is a single request such as `97 Toyota RAV4 brake line replacement
procedure, and quote`; it will return the full procedure, required and
recommended supporting work, overlap-aware labor hours, source parts prices
with pricing dates and no markup, and live worker progress. The design is being
completed before implementation, and the repository [pre-implementation gate](docs/agents/pre-implementation-gate.md)
remains mandatory.

The approved [design spec](docs/superpowers/specs/2026-09-11-natural-language-quote-procedure-generator-design.md)
and [implementation plan](docs/superpowers/plans/2026-09-11-natural-language-quote-procedure-generator.md)
are the canonical technical records for this slice.

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

Open the local chatbot dashboard at [http://127.0.0.1:8080/dashboard/](http://127.0.0.1:8080/dashboard/)
after the API container is running. It loads normalized vehicle selectors,
accepts a plain-language question, and submits it to `POST /job-plans`. The
response includes structured labor, a combined procedure, source status,
evidence, original image URLs present in the ingested article, and an explicit
`UNREVIEWED — human review pending` label until a reviewer approves the result.
On a local cache miss, the ingestion service uses the configured source
connector and materializes the returned source data for future lookups.

The dashboard uses the local development identity format
`Bearer local:demo:dataset_viewer` by default. A production identity adapter
must replace that local header boundary; provider credentials do not belong in
the browser bundle.

For a direct smoke test of the chatbot endpoint, provide a deterministic
vehicle-scoped catalog in the request. This exercises combined labor,
procedure composition, image propagation, and derived-article persistence
without making provider calls:

```sh
curl -sS -X POST http://127.0.0.1:8080/job-plans \
  -H 'Authorization: Bearer local:demo:dataset_viewer' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: local-job-plan-001' \
  -d '{"vehicle":{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"2WD","engine_displacement_l":5.3},"query":"replace the alternator and starter"}'
```

Omit the request's `catalog` after a successful persisted request to exercise
the warm derived-article path. A cache miss uses
`AUTODATA_AUTOAPI_BASE_URL` only after the indexed local lookup is empty.
The fallback first reads the vehicle's article list, selects only the articles
relevant to the natural-language request, then fetches those articles' detail
and labor resources. It persists the normalized article body, source images,
labor operations, and evidence, so the next lookup uses PostgreSQL instead of
repeating provider calls. The full catalog warm-up remains list-only; it does
not fetch every individual article detail. The
AutoAPI traversal command hydrates the complete available year/make/model/
vehicle configuration and article-list catalog when the connector session is
authorized:

```sh
AUTODATA_POSTGRES_PASSWORD=local-dev-only \
AUTODATA_MINIO_ROOT_USER=localadmin \
AUTODATA_MINIO_ROOT_PASSWORD=local-dev-password \
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/ingest_autoapi_service.py \
  --base-url http://127.0.0.1:3000 --persist
```

Mercury-2 is an advisory wording layer for selected, evidence-backed source
steps. It may translate natural-language intent into allowlisted component
keys and compose a procedure from normalized source articles, but it cannot
invent vehicle facts, labor values, safety instructions, tools, or evidence.
Set `INCEPTION_API_KEY` and `INCEPTION_API_BASE_URL` through the local
environment or a deployment secret interface; the repository and browser
bundle never contain those values. If the adapter is unavailable, the API
returns the validated deterministic procedure and marks the LLM layer as
unavailable rather than fabricating content.

## Validate a heterogeneous source drop

The source normalizer accepts mixed JSON/API envelopes, XML, CSV, HTML, plain
text, PDF, SVG, and unsupported media without relying on filenames. It retains
raw bytes and provenance, emits typed candidates where the shape is recognized,
extracts literal HTML/plain text, page-level text from text-based PDFs, and
literal SVG labels into reviewable evidence. Configured raster images can use
the worker's Tesseract OCR boundary to emit confidence-aware region evidence.
Mixed or scanned PDFs rasterize only pages without native text and send those
pages through the same OCR/evidence boundary. JSON envelopes can also carry
explicit embedded `html` or base64 `pdf` resources; these are adapted through
the same document/PDF path with locators such as `body.html:{document_id}` and
`body.pdf:{document_id}:page:{n}` while the outer JSON remains the source
content address. Ambiguous or unknown material is routed to review. New source
media types can register an adapter without changing the connector or event
contract; if an optional embedded-resource, PDF rasterizer, or OCR capability
is unavailable, the original outer payload remains content-addressed with
review metadata.

For a local-only source directory:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/normalize_source_directory.py "sample data" --region US
```

The `sample data/` directory is intentionally not part of the public
repository. Do not stage or publish source payloads unless their redistribution
terms have been explicitly approved. The Compose-mounted persistence form and
its review semantics are documented in the infrastructure guide.

The normalizer also emits a `source_report` array with one payload-free record
per resource. It includes the source URI/version, media type, content hash,
artifact kind, candidate counts and kinds, extraction status, and stable review
reasons. When persistence is enabled, conflicts and quarantine reasons are also
written as idempotent `source_review_items` records linked to source snapshots
and extraction evidence. Similar-article quarantine entries are coalesced with
their article-similarity conflict so the review queue does not duplicate one
ambiguity. Embedded-resource summaries include their locator and content hash
but never copy raw source contents or credentials.

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

Normalize a vehicle list into stable selection JSON without starting the
container stack:

```sh
AUTODATA_WORKER_ONCE=1 \
AUTODATA_VEHICLE_LIST_JSON='[{"model_year":"99","make":"Chevy","model":"Silverado 1500","region":"US","drivetrain":"2wd"},{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"2WD","engine_displacement_l":5.3}]' \
PYTHONPATH=workers/ingestion-python/src \
python3 -m autodata_ingestion.worker
```

Set `AUTODATA_SOURCE_PERSIST=1` when the PostgreSQL and MinIO variables are
available to persist the list as an immutable source snapshot. Each row is
stored with evidence and an identity observation; richer rows add a
configuration beneath the existing `vehicle_id` instead of creating another
vehicle family. `AUTODATA_VEHICLE_LIST_SOURCE_URI` and
`AUTODATA_SOURCE_VERSION` identify the list source for replay and audit.

For a complete local AutoAPI export, use the batch runner. It discovers a
vehicle bundle from each directory containing `name.json`, derives selector
configurations from the split `name.json` and `motorvehicles.json` responses,
and processes every other file in that directory through the universal source
adapter. A source root containing `name.json` is treated as one vehicle; a
catalog root containing child bundles is processed one vehicle at a time. If
multiple discovered bundles normalize to the same vehicle family, they are
merged into one batch and all source directories are normalized together, so
article deduplication and provenance cover the complete drop set. A selector
export may also arrive first, without article bundles. Pass it with
`--selector-json`; nested `models` and `engines` are flattened into
configuration observations, and every selector vehicle is retained as
`pending_source` until its article bundle arrives. A selector vehicle without
a matching source bundle is never silently skipped:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/ingest_autoapi_batch.py "sample data" \
  --region US \
  --source-version autoapi-local-v1
```

Selector-only catalog import (identity/configuration stage):

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/ingest_autoapi_batch.py "autoapi-export" \
  --selector-json "autoapi-export/vehicles.json" \
  --region US \
  --source-version autoapi-selector-v1
```

When the corresponding per-vehicle directories are added beneath the same
source root, rerunning the command merges the selector observations with the
bundle-derived trims and engines, then normalizes and persists each available
article independently. Replays use the stable vehicle, source, article, and
locator identities; near-duplicate articles remain linked to their canonical
record for review rather than being published twice. The batch result is
`completed` only when every planned vehicle was processed without a review or
failure condition; `pending_source`, `needs_review`, and `failed` remain
explicit per-vehicle and aggregate outcomes.

Add `--persist` only when PostgreSQL and MinIO are available through the local
environment. This persists the derived selector rows and each vehicle's
source snapshots, evidence, normalized articles, duplicate links, and review
items. The command continues across vehicle bundles and reports per-vehicle
failure or review status. A remote AutoAPI connector must provide the same
immutable bundle shape; this local runner does not guess undocumented remote
endpoint paths.

The companion AutoAPI repository in `/Users/dull/Documents/ChatGPT/autoapi`
provides the verified read-only `/v1/api` connector surface. When that local
service is running, the service-backed catalog runner traverses every exposed
year, make, model, and vehicle ID, fetches each vehicle's name and engine
metadata, fetches the complete article list, and passes the list response through
the same normalizer and persistence path with bounded vehicle-level concurrency:

```sh
PYTHONPATH=workers/ingestion-python/src \
python3 scripts/dev/ingest_autoapi_service.py \
  --base-url http://127.0.0.1:3000 \
  --content-source GeneralMotors \
  --source-version autoapi-http-v1 \
  --vehicle-concurrency 4 \
  --retry-attempts 3 \
  --retry-backoff-seconds 0.25
```

Add `--persist` only with the local PostgreSQL and MinIO environment configured.
The command exits nonzero when the AutoAPI catalog traversal or any article
list fetch is incomplete; its JSON report includes the years traversed and
vehicle/article-list counts. The AutoAPI service's own
runtime credentials remain in its secret-managed environment and are never
copied into AutoData or logged by this runner.
Vehicle bundles default to four concurrent fetches; lower that limit when the
upstream session or local network needs a gentler request rate. The runner
fetches the AutoAPI article list for each vehicle but intentionally does not
request individual article-detail endpoints. Idempotent GETs retry
transient 408, 425, 429, 500, 502, 503, and 504 responses with bounded
exponential backoff; persistent authentication failures remain visible and
fail the run.

Each processed result includes `article_coverage`: raw candidate count, raw
unique article IDs, normalized unique IDs, review/quarantine IDs, and an
`unaccounted_unique_ids` list. A valid complete bundle has an empty
`unaccounted_unique_ids` list; near-duplicate records are accounted for in the
review set rather than silently dropped.

For one target article, set `AUTODATA_ARTICLE_URI` and provide the target
vehicle as JSON. The worker returns the normalized article records together
with their source evidence; source credentials, if required, remain in the
secret-managed request-header variable:

```sh
AUTODATA_WORKER_ONCE=1 \
AUTODATA_ARTICLE_URI=https://example.test/article \
AUTODATA_ARTICLE_VEHICLE_JSON='{"year":1999,"make":"Chevrolet","model":"Silverado 1500","region":"US","drivetrain":"2WD"}' \
PYTHONPATH=workers/ingestion-python/src \
python3 -m autodata_ingestion.worker
```

The same worker boundary is available through the local Go API when the
Compose stack is running. `POST /article-intakes` accepts
`{"source_uri":"https://...","vehicle":{...}}` with an `Idempotency-Key`
and returns the normalized article, vehicle association, and evidence JSON.
It requires the `ingestion_operator` role. `POST /knowledge-queries` accepts
the vehicle/query request shape below with an `Idempotency-Key`; it requires
the `dataset_viewer` role and returns `cache_hit` when the indexed catalog
matches, or `fetched` after one bounded source fallback and normal intake.
The API service forwards these calls only to the internal `ingestion-http`
service. Set `AUTODATA_INGESTION_INTERNAL_TOKEN` through the environment or a
secret manager when the internal network is not otherwise trusted; never put
that token, source headers, or provider keys in the repository.

For vehicle-scoped keyword lookup, provide a normalized catalog in the
request. A catalog hit is returned immediately without a source request:

```sh
AUTODATA_WORKER_ONCE=1 \
AUTODATA_KNOWLEDGE_REQUEST_JSON='{"vehicle":{"year":1999,"make":"Chevy","model":"Silverado 1500","region":"US"},"query":"brake connector","catalog":[{"vehicle_key":"chevrolet-silverado-1500-1999-us","kind":"article","article":{"article_id":"TSB-42","title":"Brake connector bulletin"},"evidence":[]}]}' \
PYTHONPATH=workers/ingestion-python/src \
python3 -m autodata_ingestion.worker
```

On a catalog miss, set `source_uri_template` in the request or
`AUTODATA_KNOWLEDGE_SOURCE_URI_TEMPLATE` in the environment. The HTTP source
template may use `{vehicle_key}`, `{year}`, `{make}`, `{model}`, `{region}`,
`{body_style}`, `{trim}`, `{drivetrain}`, `{engine_displacement_l}`, `{query}`,
and `{keywords}`. The worker URL-escapes those values, fetches one
bounded source resource, verifies the returned vehicle, and returns the
normalized article with evidence. Source responses are never treated as a
match unless the requested vehicle and query both pass the intake boundary.

When `catalog` is omitted from a knowledge request, the worker first performs
an indexed PostgreSQL lookup by canonical `vehicle_key` and ranks the
normalized records locally. Component job-plan queries add bounded title
filters before applying the result limit, so a requested oil- or water-pump
article is not missed merely because it sorts beyond the first page of a large
catalog. Unfiltered reads exclude linked duplicates; all reads exclude
records without persisted evidence and source snapshots marked for takedown.
Only when the database lookup has no matching result does it resolve and fetch
the configured source. Supplying `catalog: []` deliberately bypasses the
database lookup and is useful for controlled fallback tests.

Mercury-2 is optional and advisory. It can adjudicate ambiguous vehicle
identity matches and, when explicitly enabled, extract typed candidates from
otherwise-unrecognized structured source shapes. Deterministic normalization,
provenance, evidence, and review gates remain authoritative; the model cannot
publish directly to canonical tables. Enable it only through secret-managed
environment variables; never place the API key in Compose files, source files,
README examples, or Git history:

```sh
export INCEPTION_API_KEY='<set-locally-or-through-a-secret-manager>'
export INCEPTION_API_BASE_URL='<provider-endpoint>'
export AUTODATA_MERCURY2_EXTRACTION_ENABLED=1
```

The source extractor is called only for structured artifacts that have no
deterministic typed candidates. It is bounded by
`AUTODATA_MERCURY2_EXTRACTION_MAX_INPUT_BYTES` and
`AUTODATA_MERCURY2_EXTRACTION_MAX_CANDIDATES`; a missing configuration,
timeout, invalid response, or empty proposal leaves the raw source and marks
the artifact `needs_review` for replay.

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
