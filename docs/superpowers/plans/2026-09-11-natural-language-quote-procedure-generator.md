# Natural-Language Quote and Procedure Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a chat-first AutoData flow that accepts one natural-language vehicle repair request and returns the fastest available procedure, overlap-aware labor quote, source parts prices, and progressive worker updates.

## Current delivery checkpoint — 2026-09-11

This plan remains the canonical implementation record for Issue #87 and
Project #8. The integrated implementation is complete at the delivery
checkpoint `c10b09fd2e05efabb19732094ac5323efdb0650e` on
`automation/knowledge-fallback-runtime`; the remote branch resolves to the
same SHA. It includes the durable chat runtime, AutoAPI fallback, immediate
source visibility, normalization/composition, overlap-aware labor, prices and
refresh, source/evidence/revision persistence, worker progress, Go routes,
dashboard, Compose wiring, and CI/smoke coverage. The user-owned untracked
`sample data/` directory remains outside every commit.

The deployed connector at `https://autoapi-sigma.vercel.app` passed its health,
readiness, year, make, and model checks. A cold public query for a 2004 Toyota
Corolla alternator and starter replacement reached that connector, exposed
source data while normalizing, then published a normalized answer with two
distinct source articles, two procedure steps, 1.4 labor hours, and the
explicit `UNREVIEWED — human review pending` label. Final status remains
`Review` until the fresh read-only review of the pushed range completes; the
exact evidence is recorded in the SDD ledger.

**Architecture:** Keep Go as the authenticated public boundary and Python as the source/normalization/composition runtime. Search the normalized PostgreSQL cache first, read through to the provider-neutral AutoAPI connector only for missing data, return source data immediately when normalization is pending, and publish correlated background updates through NATS JetStream. Mercury-2 is constrained to structured intent suggestions, supporting-operation classification, procedure composition, and faithful source-diagram vectorization; application code owns vehicle scope, source calls, arithmetic, persistence, and publication validation.

**Tech Stack:** Go 1.26 `net/http`, Python 3 with the existing ingestion/enrichment packages, PostgreSQL with pgvector, NATS JetStream, MinIO/S3-compatible storage, versioned JSON contracts, Docker Compose, and the repository’s existing pytest, Go, contract, and runtime-smoke tooling.

**Spec:** `docs/superpowers/specs/2026-09-11-natural-language-quote-procedure-generator-design.md`

## Global Constraints

- The user enters one natural-language message; year, make, model, engine, drivetrain, operation, procedure intent, and quote intent are extracted from that message.
- Ambiguous vehicle matches are returned as both numbered and clickable options before the clarification question; selecting or typing an option immediately executes the pending request.
- The initial answer includes the procedure whenever sufficient source data exists and never waits for ingestion, normalization, price refresh, procedure composition, or visual processing.
- Normalized cache data is preferred; every accessed source payload is retained for normalization and future lookup.
- AutoAPI calls are provider-neutral, vehicle-scoped, allowlisted, idempotent, and article-list-first; a warm request must not invoke AutoAPI or Mercury-2.
- Required and recommended supporting operations are separate labor categories, both contribute to the displayed labor total, and shared operations are counted once with deductions explained.
- Parts prices are source/catalog prices only, with no markup, labor dollars, taxes, fees, or invoice calculation. Prices are stale at 30 days but are returned immediately with `priced_at` while refresh runs asynchronously.
- Raw/source data may be displayed as `source_unnormalized` while normalization is processing. It must never be presented as normalized or approved.
- Combined procedures are immutable derived articles with source/evidence links, deterministic identities, and reusable revisions.
- Vector redraws are generated only from existing source diagrams/images. The vector is primary in the user view, the original is linked, and the artifact is `AI-enhanced / UNREVIEWED` until reviewed.
- Worker events are correlated to the chat query, retryable with bounded attempts, idempotent, dead-lettered after exhaustion, and must degrade only the affected result.
- No credentials, secrets, or user-provided `sample data/` files may be committed. All local tests use deterministic fake source/payment/model/vector adapters.
- All implementation work must pass the repository’s pre-implementation planning gate before an implementation agent changes code.

## Pre-Implementation Tracking

```json
{
  "goal": "Deliver a chat-first natural-language quote and procedure generator",
  "plan_ref": "docs/superpowers/plans/2026-09-11-natural-language-quote-procedure-generator.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/87",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/superpowers/specs/2026-09-11-natural-language-quote-procedure-generator-design.md",
    "docs/agents/pre-implementation-gate.md"
  ],
  "todo": [
    "Implement versioned chat, quote, price, procedure, visual, and worker-event contracts",
    "Implement natural-language vehicle and operation interpretation",
    "Implement normalized read-through retrieval and 30-day price snapshots",
    "Implement overlap-aware quote and immutable composed-procedure publication",
    "Implement the chat API, clickable vehicle options, answer updates, and Workers terminal",
    "Verify the complete cold and warm paths in local Compose and protected CI"
  ],
  "status": "synchronized",
  "updated_at": "2026-09-11T15:47:33Z"
}
```

The plan checkpoint must be committed and pushed before implementation workers
start. After that push, update Issue #87 and Project #8 with the exact plan
SHA, then pass the machine preflight against the implementation base SHA.

## File ownership map

- **Contracts and persistence:** `packages/contracts/contract.json`, generated
  Go/Python bindings, `db/migrations/025_chat_quote_procedure.sql`, and their
  tests.
- **Intent and vehicle planning:** new
  `workers/ingestion-python/src/autodata_ingestion/chat_intent.py` and its
  focused tests. Existing job-plan calculation remains owned by the quote
  worker.
- **Source retrieval and price snapshots:** existing
  `knowledge_fallback_runtime.py`, `autoapi_connector.py`, plus new
  `pricing.py` and focused tests.
- **Quote, procedure, and visuals:** existing `job_plan.py`, `mercury2.py`,
  `derived_article_persistence.py`, plus new `visual_vectorization.py` and
  focused tests.
- **Python chat service and progress:** new `chat_service.py` and
  `progress_events.py`, existing `http_service.py` and worker entry points,
  with service tests.
- **Go public API:** new `chat.go` and `chat_events.go`, existing `main.go` and
  `ingestion_http.go`, with Go API tests.
- **Dashboard:** `apps/api-go/dashboard/index.html`, `app.js`, and
  `styles.css`, with static asset tests in `dashboard_test.go`.
- **Integration and delivery:** new or modified `scripts/dev/chat_smoke.py`,
  its tests, Compose service configuration, and the protected verification
  workflow only where required to run the smoke.

---

### Task 1: Add versioned chat, quote, price, procedure, visual, and progress contracts

**Files:**
- Modify: `packages/contracts/contract.json`
- Modify: `packages/contracts/go/contracts.go` through `scripts/contracts/generate.py`
- Modify: `packages/contracts/python/autodata_contracts/contracts.py` through `scripts/contracts/generate.py`
- Create: `db/migrations/025_chat_quote_procedure.sql`
- Create: `db/migrations/026_chat_quote_operation_categories.sql` for upgrade-safe adoption of the Task 1 quote-category columns
- Create: `scripts/contracts/test_chat_quote_contract.py`
- Modify: `scripts/dev/test_migrations.py`
- Modify: `packages/contracts/go/contracts_test.go`

**Interfaces:**
- `chat_query`: `query_id`, `conversation_id`, `message`, `idempotency_key`, `status`, `vehicle_options`, `answer`, and `correlation_id`.
- `chat_selection`: `query_id`, `selection_type`, `option_number`, and optional `vehicle_id`.
- `chat_answer`: `answer_status`, `data_state`, `vehicle`, `procedure`, `quote`, `warnings`, `updated_at`, and `worker_stream`.
- `chat_quote`: `required_hours`, `recommended_hours`, `total_hours`, `overlap_hours_removed`, `overlap_operations`, `parts`, and evidence references.
- `price_snapshot`: canonical part identity, source part number, amount, currency, `priced_at`, freshness, source snapshot, and refresh status.
- `worker_progress_event`: the existing event envelope plus `query_id`, `stage`, `status`, `data_state`, and a redacted message.

- [ ] **Step 1: Write failing contract tests**

Add assertions that the generated bindings expose these exact fields and enum
values:

```python
def test_chat_answer_exposes_procedure_quote_and_progress() -> None:
    contract = load_contract()
    answer = contract["chat_answer"]
    assert {"answer_status", "data_state", "procedure", "quote", "worker_stream"} <= set(answer["properties"])
    assert "source_unnormalized" in contract["data_state"]

def test_quote_separates_required_and_recommended_labor() -> None:
    quote = load_contract()["chat_quote"]
    assert {"required_hours", "recommended_hours", "total_hours", "overlap_hours_removed"} <= set(quote["properties"])

def test_price_snapshot_has_priced_at_and_no_markup_contract() -> None:
    price = load_contract()["price_snapshot"]
    assert {"amount", "currency", "priced_at", "freshness", "refresh_status"} <= set(price["properties"])
```

Run:

```bash
python3 -m pytest scripts/contracts/test_chat_quote_contract.py -q
```

Expected: FAIL because the new contract definitions do not exist.

- [ ] **Step 2: Add the canonical JSON definitions**

Add `data_state`, `answer_status`, `quote`, `price_snapshot`, `procedure_step`,
`visual_artifact`, `chat_answer`, `chat_query`, `chat_selection`, and
`worker_progress_event` to `packages/contracts/contract.json`. Keep UUID,
timestamp, nullable, and enum conventions identical to the existing contract.
Add `chat.answer.updated`, `chat.vehicle.options`, `chat.worker.progress`,
`chat.price.refresh.requested`, `chat.procedure.published`, and
`chat.visual.published` to the versioned event subject list.

- [ ] **Step 3: Add persistence constraints**

Create `025_chat_quote_procedure.sql` with forward-only tables and constraints
for `chat_queries`, `chat_query_options`, `chat_job_plans`,
`chat_quote_revisions`, `parts_price_snapshots`, `chat_visual_artifacts`, and
`chat_worker_events`. Include unique keys for query idempotency, deterministic
derived-article identity, `(canonical_part_id, source_snapshot_id, priced_at)`,
and `(query_id, event_id)`. Store raw answer snapshots and source watermarks as
JSONB/text only where needed for audit; keep immutable published revisions
protected from update/delete.

- [ ] **Step 4: Regenerate bindings and make the tests pass**

Run:

```bash
python3 scripts/contracts/generate.py
python3 -m pytest scripts/contracts/test_chat_quote_contract.py -q
(cd packages/contracts/go && go test ./...)
```

Expected: PASS, with generated Go/Python bindings matching the canonical JSON.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/contract.json packages/contracts/go/contracts.go packages/contracts/go/contracts_test.go packages/contracts/python/autodata_contracts/contracts.py db/migrations/025_chat_quote_procedure.sql scripts/contracts/test_chat_quote_contract.py
git commit -m "feat: add chat quote and procedure contracts"
```

### Task 2: Implement natural-language vehicle and operation interpretation

**Files:**
- Create: `workers/ingestion-python/src/autodata_ingestion/chat_intent.py`
- Create: `workers/ingestion-python/tests/test_chat_intent.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/vehicle_identity.py`
- Modify: `workers/ingestion-python/tests/test_vehicle_identity.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ChatIntent:
    vehicle_observation: dict[str, Any]
    requested_operations: tuple[dict[str, Any], ...]
    quote_requested: bool
    procedure_requested: bool
    clarification: str | None

def interpret_chat_message(
    message: str,
    vehicle_candidates: tuple[Mapping[str, Any], ...],
    *,
    mercury_client: Mercury2Client | None = None,
) -> ChatIntent: ...

def derive_supporting_operations(
    requested_operations: tuple[Mapping[str, Any], ...],
    articles: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]: ...
```

- [ ] **Step 1: Write failing parser tests**

Cover `97 Toyota RAV4 brake line replacement procedure, and quote`, spelling
variants, multiple components, quote-only requests, procedure-only requests,
and a message with no identifiable component. Assert that vehicle details and
requested operations are structured rather than copied as free text.

- [ ] **Step 2: Write failing candidate/clarification tests**

Provide two candidate vehicles and assert that the result exposes both in
stable order, preserves confidence, and produces one clarification question.
Provide one unambiguous candidate and assert that `clarification is None`.

- [ ] **Step 3: Implement deterministic extraction**

Use the existing canonicalization and alias patterns as the first pass. Extract
year, make, model, engine, drivetrain, operation verbs, component aliases, and
`quote`/`procedure` intent. Return `ChatIntent` with normalized values and
stable option ordering.

- [ ] **Step 4: Implement constrained Mercury-2 fallback**

When deterministic extraction leaves an operation or vehicle field unresolved,
call the existing `Mercury2Client` with a JSON-only schema. Validate that the
model can choose only among supplied vehicle candidates and allowlisted
components. Keep the model response advisory; unknown values become
`needs_review` instead of being treated as facts.

- [ ] **Step 5: Implement supporting-operation classification**

Read source article metadata and trusted rule metadata. Emit explicit
`required` and `recommended` categories with a basis and source article IDs.
Do not promote a model-only suggestion to `required` without source/rule
support.

- [ ] **Step 6: Run tests and commit**

```bash
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_chat_intent.py workers/ingestion-python/tests/test_vehicle_identity.py -q
git add workers/ingestion-python/src/autodata_ingestion/chat_intent.py workers/ingestion-python/src/autodata_ingestion/vehicle_identity.py workers/ingestion-python/tests/test_chat_intent.py workers/ingestion-python/tests/test_vehicle_identity.py
git commit -m "feat: interpret natural language chat repair requests"
```

### Task 3: Add read-through source retrieval and 30-day price snapshots

**Files:**
- Create: `workers/ingestion-python/src/autodata_ingestion/pricing.py`
- Create: `workers/ingestion-python/tests/test_pricing.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/knowledge_fallback_runtime.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/autoapi_connector.py`
- Modify: `workers/ingestion-python/tests/test_knowledge_fallback_runtime.py`
- Modify: `workers/ingestion-python/tests/test_autoapi_connector.py`

**Interfaces:**

```python
def price_freshness(priced_at: datetime, now: datetime) -> str: ...

def read_cached_price_or_queue_refresh(
    part: Mapping[str, Any],
    *,
    now: datetime,
    refresh: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]: ...

def fetch_required_source_resources(
    vehicle: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]],
    connector: AutoAPIConnector,
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing price freshness tests**

Assert that a price at 29 days is `fresh`, a price at exactly 30 days is
`stale`, and a stale price is returned immediately with its original
`priced_at`, `refresh_status=queued`, and a refresh request identity.

- [ ] **Step 2: Write failing source-selection tests**

Use the existing fake AutoAPI response and assert that a cache miss reads the
article list first and fetches only requested article details, labor resources,
and part-price resources. Assert that repeated requests use the normalized
cache and make zero connector calls.

- [ ] **Step 3: Implement the price snapshot module**

Use UTC timestamps and a fixed 30-day freshness boundary. Return immutable
snapshot dictionaries with source part number, amount, currency, `priced_at`,
source snapshot ID, freshness, refresh status, and `markup_applied=False`.

- [ ] **Step 4: Extend source fulfillment**

Update `fulfill_once` and its resolver to persist every fetched payload before
normalization, return a `source_unnormalized` result when a normalized record is
not ready, and emit a durable refresh job for stale prices. Reuse the existing
AutoAPI article-list-first traversal and idempotency conventions.

- [ ] **Step 5: Add persistence and failure behavior**

Write price snapshots and source states through the migration’s unique keys.
When refresh fails, retain the stale snapshot, record retry metadata, and
return it without blocking the response. Exhausted refresh retries publish a
dead-letter event without deleting the snapshot.

- [ ] **Step 6: Run tests and commit**

```bash
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_pricing.py workers/ingestion-python/tests/test_knowledge_fallback_runtime.py workers/ingestion-python/tests/test_autoapi_connector.py -q
git add workers/ingestion-python/src/autodata_ingestion/pricing.py workers/ingestion-python/src/autodata_ingestion/knowledge_fallback_runtime.py workers/ingestion-python/src/autodata_ingestion/autoapi_connector.py workers/ingestion-python/tests/test_pricing.py workers/ingestion-python/tests/test_knowledge_fallback_runtime.py workers/ingestion-python/tests/test_autoapi_connector.py
git commit -m "feat: add cached source prices and read-through refresh"
```

### Task 4: Implement overlap-aware quotes, reusable procedures, and source-diagram vectorization

**Files:**
- Create: `workers/ingestion-python/src/autodata_ingestion/visual_vectorization.py`
- Create: `workers/ingestion-python/tests/test_visual_vectorization.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/job_plan.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/mercury2.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py`
- Modify: `workers/ingestion-python/tests/test_job_plan.py`
- Modify: `workers/ingestion-python/tests/test_mercury2.py`
- Modify: `workers/ingestion-python/tests/test_derived_article_persistence.py`

**Interfaces:**

```python
def build_quote_and_procedure(
    query: str,
    vehicle: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
    *,
    mercury_client: Mercury2Client | None = None,
) -> dict[str, Any]: ...

class SourceDiagramVectorizer(Protocol):
    def redraw(self, source_bytes: bytes, *, source_uri: str) -> dict[str, Any]: ...

def compose_procedure_revision(
    quote: Mapping[str, Any],
    articles: Iterable[Mapping[str, Any]],
    *,
    mercury_client: Mercury2Client | None = None,
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing labor tests**

Add a fixture containing brake-line replacement, brake bleeding, and inspection
operations. Assert separate required/recommended subtotals, total hours, the
shared operation counted once, and a detailed overlap deduction.

- [ ] **Step 2: Write failing procedure tests**

Assert that the composed procedure includes every requested and required
supporting step, source article IDs, evidence IDs, safety warnings, and an
explicit unreviewed state. Assert that a Mercury-2 response with an unsupported
step is rejected rather than published.

- [ ] **Step 3: Implement deterministic quote calculation**

Refactor the existing `_calculate_labor` and `_stable_operation_id` path into
the public quote function. Deduplicate by stable operation identity and shared
work scope. Keep arithmetic outside the model and include both raw and
deducted hours in the response.

- [ ] **Step 4: Implement constrained procedure composition**

Extend the existing Mercury-2 composition path with a strict JSON schema. Feed
it normalized articles and the validated quote only. Validate every generated
step against article/evidence IDs, vehicle identity, and required/recommended
classification before calling `persist_derived_article`.

- [ ] **Step 5: Implement vector redraw boundary**

Add a provider-neutral vectorizer interface with a deterministic local fake
that returns a renderable SVG fixture for tests and Compose. The production
adapter accepts only an existing source image, writes the original and derived
objects to object storage, records processor/version metadata, and marks the
derived artifact `AI-enhanced / UNREVIEWED`. Reject text-only requests without
a source visual.

- [ ] **Step 6: Persist a reusable immutable revision**

Extend `derived_article_identity` and `persist_derived_article` to include the
canonical vehicle, operation categories, source watermarks, quote identity,
procedure revision, and visual artifact references. Replays return the same
derived article without a new model or source call.

- [ ] **Step 7: Run tests and commit**

```bash
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_job_plan.py workers/ingestion-python/tests/test_mercury2.py workers/ingestion-python/tests/test_derived_article_persistence.py workers/ingestion-python/tests/test_visual_vectorization.py -q
git add workers/ingestion-python/src/autodata_ingestion/job_plan.py workers/ingestion-python/src/autodata_ingestion/mercury2.py workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py workers/ingestion-python/src/autodata_ingestion/visual_vectorization.py workers/ingestion-python/tests/test_job_plan.py workers/ingestion-python/tests/test_mercury2.py workers/ingestion-python/tests/test_derived_article_persistence.py workers/ingestion-python/tests/test_visual_vectorization.py
git commit -m "feat: compose overlap-aware quotes and vector procedures"
```

### Task 5: Add the Python chat service, answer updates, and worker progress events

**Files:**
- Create: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Create: `workers/ingestion-python/src/autodata_ingestion/progress_events.py`
- Create: `workers/ingestion-python/tests/test_chat_service.py`
- Create: `workers/ingestion-python/tests/test_progress_events.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/http_service.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/worker.py`

**Interfaces:**

```python
def create_chat_query(message: str, *, idempotency_key: str, principal: Mapping[str, Any]) -> dict[str, Any]: ...

def select_chat_vehicle(query_id: str, selection: Mapping[str, Any]) -> dict[str, Any]: ...

def get_chat_query(query_id: str) -> dict[str, Any]: ...

def iter_chat_events(query_id: str, *, last_event_id: str | None = None) -> Iterator[dict[str, Any]]: ...

def publish_chat_progress(query_id: str, stage: str, status: str, *, data_state: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing service tests**

Test idempotent query creation, candidate option output, immediate typed/click
selection, normalized cache hit, source-unormalized response, and same-answer
updates after a background publication.

- [ ] **Step 2: Write failing event tests**

Assert deterministic event IDs/idempotency keys, query correlation, redaction
of credential-like values, replay from `last_event_id`, bounded retry state,
and dead-letter publication after the configured attempt limit.

- [ ] **Step 3: Implement the service state machine**

Create the durable query and job-plan records. Run the following stages in
order: interpret, resolve vehicle, lookup derived article, lookup normalized
articles/prices, return immediate answer, enqueue missing source work, and
publish later answer revisions. Keep each stage independently retryable.

- [ ] **Step 4: Implement source and model fan-out**

Use the existing ingestion runtime and NATS/event abstractions. Emit progress
events for every stage. A source or model failure updates only the affected
item and leaves any answer already available.

- [ ] **Step 5: Add HTTP service routes**

Expose Python service routes for `POST /v1/chat/queries`,
`POST /v1/chat/queries/{id}/selections`, `GET /v1/chat/queries/{id}`, and
`GET /v1/chat/queries/{id}/events`. Return JSON immediately for query/selection
calls and SSE-compatible frames for event delivery.

- [ ] **Step 6: Run tests and commit**

```bash
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_progress_events.py -q
git add workers/ingestion-python/src/autodata_ingestion/chat_service.py workers/ingestion-python/src/autodata_ingestion/progress_events.py workers/ingestion-python/src/autodata_ingestion/http_service.py workers/ingestion-python/src/autodata_ingestion/worker.py workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_progress_events.py
git commit -m "feat: orchestrate chat answers and worker progress"
```

### Task 6: Expose the chat and Workers terminal through the Go API

**Files:**
- Create: `apps/api-go/chat.go`
- Create: `apps/api-go/chat_events.go`
- Create: `apps/api-go/chat_test.go`
- Create: `apps/api-go/chat_events_test.go`
- Modify: `apps/api-go/main.go`
- Modify: `apps/api-go/ingestion_http.go`
- Modify: `apps/api-go/go.mod` only if an existing streaming dependency is required; prefer the standard library.

**Interfaces:**

```go
type ChatClient interface {
	Create(context.Context, *http.Request, []byte, string) (int, []byte, error)
	Select(context.Context, *http.Request, string, []byte, string) (int, []byte, error)
	Get(context.Context, *http.Request, string) (int, []byte, error)
	Events(context.Context, *http.Request, string, string) (io.ReadCloser, error)
}
```

- [ ] **Step 1: Write failing route/auth tests**

Assert that unauthenticated requests are rejected, authenticated
`dataset_viewer` requests proxy JSON bodies with idempotency keys, and the
event route preserves `Last-Event-ID` and `text/event-stream`.

- [ ] **Step 2: Write failing duplicate/error tests**

Assert that duplicate idempotency keys return the original query, missing
selection options return a structured `INVALID_REQUEST`, and upstream
unavailability returns `INGESTION_UNAVAILABLE` without exposing internal
headers or body secrets.

- [ ] **Step 3: Implement the Go client boundary**

Extend the internal ingestion client with bounded GET/stream operations. Keep
the existing `/job-plans` behavior unchanged for compatibility. Add routes:

```go
mux.Handle("POST /chat/queries", s.requireRole("dataset_viewer", s.createChatQuery))
mux.Handle("GET /chat/queries/{id}", s.requireRole("dataset_viewer", s.getChatQuery))
mux.Handle("POST /chat/queries/{id}/selections", s.requireRole("dataset_viewer", s.selectChatVehicle))
mux.Handle("GET /chat/queries/{id}/events", s.requireRole("dataset_viewer", s.streamChatEvents))
```

- [ ] **Step 4: Implement streaming safeguards**

Limit event frame size, flush each frame, stop on client cancellation, preserve
request/correlation IDs, and redact authorization values from logs. Do not
buffer an unbounded event stream.

- [ ] **Step 5: Run tests and commit**

```bash
(cd apps/api-go && gofmt -w chat.go chat_events.go chat_test.go chat_events_test.go ingestion_http.go main.go && go test ./...)
git add apps/api-go/chat.go apps/api-go/chat_events.go apps/api-go/chat_test.go apps/api-go/chat_events_test.go apps/api-go/ingestion_http.go apps/api-go/main.go apps/api-go/go.mod apps/api-go/go.sum
git commit -m "feat: expose chat query and worker event APIs"
```

### Task 7: Replace the form-first dashboard with the natural-language chat experience

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/app.js`
- Modify: `apps/api-go/dashboard/styles.css`
- Modify: `apps/api-go/dashboard_test.go`

**Interfaces:**

The dashboard calls the Go routes from Task 6 and renders these response
properties without inventing client-side data: `vehicle_options`,
`procedure`, `quote`, `warnings`, `data_state`, and `worker_stream`.

- [ ] **Step 1: Write failing static dashboard tests**

Assert that the HTML includes a natural-language message input, answer panel,
procedure panel, quote panel, clickable vehicle-option container, and Workers
terminal. Assert that there are no required year/make/model/engine/drivetrain
inputs.

- [ ] **Step 2: Write failing behavior markers**

Assert that the JavaScript contains the chat query route, selection route,
event stream route, numbered option rendering, click handler, stale price
label, `source_unnormalized` label, required/recommended labor display, and
`UNREVIEWED` label.

- [ ] **Step 3: Implement the chat-first shell**

Replace vehicle selectors and mandatory fields with one message composer. Add
conversation messages, structured JSON output, procedure steps, required and
recommended labor sections, parts pricing dates, warnings, and source links.

- [ ] **Step 4: Implement numbered/clickable options**

Render stable buttons whose visible labels begin with the option number. Support
typed numeric selection in the chat input. Both paths call the selection route
and immediately rerender the pending result.

- [ ] **Step 5: Implement progressive answer updates**

Open the request-specific event stream after query creation. Merge answer
updates by revision ID, retain visible provisional data, show stale prices
with their dates, and never clear a usable result when a background stage
fails.

- [ ] **Step 6: Implement the Workers terminal**

Render correlated progress events with timestamp, stage, status, retry count,
and a safe message. Keep operational errors separate from the customer-facing
procedure but link both by query ID.

- [ ] **Step 7: Run tests and commit**

```bash
(cd apps/api-go && gofmt -w dashboard_test.go && go test ./...)
git add apps/api-go/dashboard/index.html apps/api-go/dashboard/app.js apps/api-go/dashboard/styles.css apps/api-go/dashboard_test.go
git commit -m "feat: add natural-language quote chatbot dashboard"
```

### Task 8: Add deterministic cold/warm end-to-end verification and Compose wiring

**Files:**
- Create: `scripts/dev/chat_smoke.py`
- Create: `scripts/dev/test_chat_smoke.py`
- Modify: `infra/compose/compose.yaml`
- Modify: `infra/compose/.env.example` only if the file exists and contains no secrets
- Modify: `.github/workflows/autonomous-verification.yml`
- Modify: `README.md`
- Modify: `docs/architecture/infrastructure-and-dev.md`

**Interfaces:**

The smoke accepts the deterministic fake adapters and asserts the complete
request lifecycle for:

```text
97 Toyota RAV4 brake line replacement procedure, and quote
```

- [ ] **Step 1: Write failing smoke assertions**

Assert:

```python
assert response["procedure"]["status"] in {"available_provisional", "ready"}
assert response["quote"]["parts"]["markup_applied"] is False
assert response["quote"]["labor"]["required_hours"] >= 0
assert response["quote"]["labor"]["recommended_hours"] >= 0
assert response["quote"]["labor"]["overlap_hours_removed"] >= 0
assert response["workers"]["events"]
assert any(item["data_state"] == "source_unnormalized" for item in response["updates"])
```

Also assert that a second identical request makes zero source/model calls,
that a stale price is returned immediately with `priced_at`, and that an
existing source diagram yields a vector artifact linked to its original.

- [ ] **Step 2: Implement the fake cold path**

Wire the existing fake source, fake payment, fake Mercury-2, fake vectorizer,
PostgreSQL, NATS, and MinIO services. Make the first response include
available source data and the final event include normalized procedure, quote,
price, and visual revisions.

- [ ] **Step 3: Implement the warm path assertion**

Replay the same idempotency key and a semantically identical query. Assert that
the derived article and price snapshot are reused and that no AutoAPI or
Mercury-2 call is made.

- [ ] **Step 4: Wire Compose services and health checks**

Expose the Python chat service and its worker entry points through the existing
Compose network. Add only non-secret environment names for event stream,
price TTL, fake adapters, and object-storage buckets. Keep startup ordering,
health checks, retry limits, and cleanup deterministic.

- [ ] **Step 5: Add protected CI execution**

Run the chat smoke after migrations, fake integrations, and API readiness. Keep
the existing live Compose smoke and add the new smoke’s output to the job
summary. The workflow must report source/model skips explicitly rather than
calling fixtures a live provider verification.

- [ ] **Step 6: Update developer documentation**

Document the single-message local test, the clickable selection behavior, the
Workers terminal, the provisional-source state, the 30-day price policy, and
the warm replay command. Do not add credentials or sample data.

- [ ] **Step 7: Run the complete verification suite and commit**

```bash
(cd apps/api-go && go test ./...)
(cd packages/contracts/go && go test ./...)
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests -q
PYTHONPATH=workers/enrichment-python/src python3 -m pytest workers/enrichment-python/tests -q
PYTHONPATH=workers/ingestion-python/src python3 -m pytest scripts/dev/test_*.py -q
python3 -m pytest scripts/contracts -q
python3 scripts/dev/chat_smoke.py
python3 -m json.tool .autodata-autonomy-policy.json >/dev/null
git diff --check
git add scripts/dev/chat_smoke.py scripts/dev/test_chat_smoke.py infra/compose/compose.yaml .github/workflows/autonomous-verification.yml README.md docs/architecture/infrastructure-and-dev.md
git commit -m "test: verify chat quote and procedure lifecycle"
```

## Integration and review order

1. Complete Task 1 and commit the shared contracts/migration.
2. Dispatch Tasks 2, 3, and 4 in parallel because their write sets are
   disjoint.
3. Review and integrate Tasks 2–4; run all Python tests.
4. Dispatch Tasks 5, 6, and 7 in parallel because their write sets are
   disjoint and their external contracts are fixed by Tasks 1–4.
5. Review and integrate Tasks 5–7; run Go and Python tests together.
6. Run Task 8 as the integration owner; fix only cross-task contract defects
   with an explicit follow-up commit.
7. Run the complete verification suite, inspect the final diff, update Issue
   #87 and Project #8 with exact SHAs and CI results, and push the branch.

## Acceptance evidence

The feature is complete only when the final evidence proves all of the
following:

- A single natural-language message resolves the vehicle and requested job.
- Ambiguous vehicles produce numbered/clickable options, and selection
  executes immediately.
- The initial answer includes the procedure whenever source data exists.
- Required and recommended supporting operations are separate and both affect
  the total.
- Shared labor is counted once and the overlap deduction is visible.
- Source parts prices include `priced_at` and no markup.
- A 30-day-old price is returned immediately while refresh runs in background.
- Raw source data is visible while normalization is running.
- Every accessed source is persisted and repeated requests avoid source/model
  calls.
- The combined procedure is persisted as an immutable reusable revision.
- Existing source visuals can produce linked vector artifacts; text-only
  requests do not fabricate diagrams.
- The same answer updates as worker events publish.
- The Workers terminal streams correlated progress and dead-letter outcomes.
- Source, evidence, review, revision, and idempotency links remain intact.
- Local fake adapters and protected Compose CI verify cold and warm paths.
