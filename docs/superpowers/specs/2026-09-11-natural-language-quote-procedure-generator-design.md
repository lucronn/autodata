# Natural-Language Quote and Procedure Generator Design

**Status:** approved design; ready for implementation
**Tracking:** [Issue #87](https://github.com/lucronn/autodata/issues/87) and [AutoData Portfolio Project #8](https://github.com/users/lucronn/projects/8)
**Scope:** chat-first vehicle repair requests, normalized source retrieval, labor/parts quoting, composed procedures, source-diagram vectorization, and correlated worker progress

## Product goal

AutoData accepts one natural-language request and returns the fastest useful
answer available for the identified vehicle. A request such as:

> 97 Toyota RAV4 brake line replacement procedure, and quote

must produce a complete procedure when enough information is available, infer
the supporting work required by the requested operation, calculate labor with
shared work counted once, include source/catalog parts prices with their pricing
dates and no markup, and continue improving the same answer as background
normalization and enrichment finish.

The primary interaction is a chatbot. Vehicle year, make, model, engine, and
drivetrain are extracted from the same natural-language message rather than
entered into separate form fields. If the text maps to multiple canonical
vehicles, the response first presents the available numbered and clickable
options, displays any information already available, and asks one concise
clarification in the same chat. Clicking or typing an option immediately
executes the pending request.

## Non-goals

- No labor-dollar calculation, shop rate, tax, fee, or parts markup in this
  version.
- No blocking the user response on AutoAPI, normalization, price refresh,
  procedure composition, or visual processing.
- No fabricated vehicle facts, labor values, prices, source evidence, or
  technical diagrams.
- No separate vehicle-selection form as the primary interaction.
- No source call for every article when the request needs only a subset.
- No mutable overwrite of a published article, quote, procedure, price
  snapshot, or evidence record.
- No public display of raw credentials or worker secrets.

## Design principles

1. **Cache first.** Search normalized vehicle-scoped content and reusable
   derived procedures before invoking a model or a source connector.
2. **Display what exists.** Available normalized or source-backed data is
   returned immediately with an explicit state; background work never hides
   usable information.
3. **Application-owned source calls.** Mercury-2 may interpret intent, but
   only the allowlisted connector boundary constructs AutoAPI requests.
4. **Deterministic arithmetic.** Labor totals, overlap deductions, parts
   subtotals, freshness, and idempotency are computed by application code.
5. **Evidence follows facts.** Every displayed fact, operation, price, step,
   and derived visual links to a source snapshot and evidence locator.
6. **Immutable revisions.** New normalization, price, procedure, or visual
   output creates a new revision; earlier output remains auditable.
7. **Progressive publication.** Each background stage publishes independently
   and updates the same correlated chatbot answer.

## Architecture

```text
Chat client
    |
    v
Go API: chat query and selection boundary
    |
    +--> Request interpreter
    |      - deterministic aliases and parser first
    |      - Mercury-2 fallback for structured intent
    |
    +--> Vehicle resolver
    |      - canonical identity lookup
    |      - candidate options and confidence
    |
    +--> Normalized retrieval and derived-article cache
    |      - PostgreSQL records and pgvector retrieval
    |      - price snapshots and visual artifact pointers
    |
    +--> Immediate answer
    |      - normalized data, or source_unnormalized data
    |      - procedure, labor, parts, warnings, evidence
    |      - clickable options when clarification is required
    |
    +--> Provider-neutral source connector on cache miss
    |      - AutoAPI vehicle-scoped article-list/detail/price calls
    |      - deterministic fake connector in local development
    |
    +--> NATS JetStream correlated work
           |
           +--> normalize and deduplicate source articles
           +--> refresh 30-day price snapshots
           +--> calculate labor and overlap
           +--> compose procedure with Mercury-2
           +--> redraw existing source visuals into vectors
           +--> persist evidence and immutable revisions
           +--> publish answer updates and worker progress events
```

The existing Go API, Python ingestion/enrichment workers, PostgreSQL, NATS,
MinIO, and `/job-plans` compatibility endpoint remain the implementation
foundation. The chatbot contract is a user-facing orchestration over those
boundaries, not a new table-shaped public API.

## Request lifecycle

### Initial message

The client sends one natural-language message with an idempotency key:

```http
POST /chat/queries
Authorization: Bearer ...
Idempotency-Key: chat-query-unique-key
Content-Type: application/json
```

```json
{
  "conversation_id": "uuid",
  "message": "97 Toyota RAV4 brake line replacement procedure, and quote"
}
```

The API creates a durable query record and returns the best immediately
available answer. It does not wait for source retrieval or normalization.

### Vehicle resolution

Vehicle parsing uses canonical aliases, known year/make/model catalogs, and
the constrained Mercury-2 intent adapter only where deterministic parsing is
insufficient. A resolved vehicle must include the canonical vehicle ID and
the identity fields used to scope every downstream lookup.

When more than one safe vehicle match remains, the response contains both a
numbered representation and clickable options. The response may include a
provisional procedure or source result before asking the question. A selection
is sent through the same conversation and executes immediately.

The API must not silently select an engine, drivetrain, region, or vehicle
configuration when that choice can change labor, parts, safety, or procedure
content. A high-confidence unambiguous match can execute without a question;
the response still records the resolved identity and confidence.

### Intent and supporting operations

The interpreter produces structured requested operations and supporting
operations. Supporting operations are classified as `required` or
`recommended`.

- `required` means the source procedure or a trusted domain rule establishes
  that the operation is needed to complete the requested work safely or
  correctly.
- `recommended` means the source or rule suggests useful supporting work, but
  it is not a prerequisite for completing the requested operation.

Both categories contribute to the displayed labor total, but each has a
separate subtotal and list. The output must never hide that an operation was
derived rather than directly requested.

The initial implementation supports deterministic aliases and structured
Mercury-2 output validation. The LLM may suggest a component or supporting
operation, but publication requires a matching normalized article, trusted
rule, or review-needed state. Unsupported suggestions remain visible as
unresolved recommendations and cannot become verified procedure steps.

### Retrieval and read-through ingestion

The retrieval order is:

```text
derived procedure cache
  -> normalized vehicle-scoped articles
  -> normalized price snapshots
  -> normalized vector artifacts
  -> source article list
  -> only requested source article details and price resources
```

Every source payload accessed by the request is persisted for later
normalization, even when it is returned provisionally. Source retrieval is
idempotent by source snapshot, canonical vehicle, resource identity, query,
and processing version. The full catalog warm-up remains article-list-first;
it does not fetch every article detail.

The immediate response identifies each result with one of:

- `normalized` — persisted normalized data is being returned;
- `source_unnormalized` — source data is available but normalization is still
  processing;
- `stale` — the cached value is returned while a refresh is queued;
- `processing` — no usable value is currently available for that item;
- `unavailable` — the source or cache has no usable value; or
- `needs_review` — the data exists but cannot be treated as verified.

The response is useful whenever any requested part of the result is available.
Missing fields are represented as missing or unavailable rather than blocking
the entire quote or procedure.

## Quote model

### Labor

Labor operations are normalized into stable operation identities with source
article references, base hours, required/recommended category, and prerequisite
relationships. The calculator computes:

```json
{
  "required_hours": 2.6,
  "recommended_hours": 0.8,
  "total_hours": 3.4,
  "overlap_hours_removed": 0.8,
  "overlap_operations": [
    {
      "operation_id": "brake-wheel-removal",
      "counted_once_for": [
        "brake-line-replacement",
        "brake-system-inspection"
      ]
    }
  ]
}
```

An operation is counted once when its stable identity and shared-work scope
match. The result includes the contributing article IDs, evidence IDs, raw
hours, deductions, and final hours. Mercury-2 cannot change the arithmetic.

### Parts and pricing

Parts are canonicalized by source part number, normalized name, vehicle
compatibility, and source identity. A price is an immutable snapshot:

```json
{
  "part_id": "canonical-part-id",
  "source_part_number": "source-number",
  "name": "Brake fluid",
  "quantity": 1,
  "amount": 18.99,
  "currency": "USD",
  "priced_at": "2026-08-01T12:00:00Z",
  "freshness": "stale",
  "source": "autoapi",
  "refresh_status": "queued",
  "markup_applied": false
}
```

Prices younger than 30 days are returned from the normalized cache. At 30
days, a cached price is stale but remains immediately displayable with its
`priced_at` date. A background refresh creates a new snapshot. If refresh
fails, the stale price remains visible and the response includes the refresh
failure state. The previous snapshot is never overwritten.

The quote contains source-price subtotal only. No markup, labor-dollar total,
tax, fee, or customer-invoice calculation is performed.

## Procedure generation

The procedure generator receives normalized source articles, supporting
operations, labor relationships, source watermarks, and evidence references.
Mercury-2 produces a structured procedure draft with ordered steps, warnings,
required/recommended annotations, source article IDs, and evidence IDs.

The application validates that:

- every executable step maps to at least one source article or trusted rule;
- every safety warning has evidence or is marked for review;
- every labor operation in the quote is represented or explicitly excluded;
- every source reference belongs to the resolved vehicle;
- no generated step introduces an unsupported part, value, or vehicle fact; and
- the final JSON conforms to the versioned contract.

The accepted composition is persisted as a reusable derived article with an
immutable revision. Its identity includes the canonical vehicle ID, normalized
requested operation set, required/recommended supporting set, source
watermarks, and composition version. A repeated request can return the
derived article without another AutoAPI or Mercury-2 call.

The first chatbot response includes the procedure whenever enough source data
exists. A later normalized or enriched procedure revision updates the same
answer and remains linked to the earlier provisional response.

## Visual processing

Vector processing is limited to source images or diagrams that actually exist.
No technical visual is fabricated from text when the source contains no visual.

For an eligible source visual, the visual worker:

1. stores the original source object and attribution metadata;
2. produces a vector artifact using a versioned image-to-vector processor;
3. validates that the artifact is renderable and linked to the source object;
4. marks it `AI-enhanced / UNREVIEWED` until human review; and
5. publishes the vector artifact as a new immutable derived visual revision.

The chatbot shows the vector redraw as the primary visual and exposes a link
to the original source image. Reviewers can inspect both, while ordinary
procedure output is not forced to display the original image inline.

## Worker progress and answer updates

Each chat query has a `query_id` and `correlation_id`. The Go API exposes a
request-specific event stream:

```http
GET /chat/queries/{query_id}/events
Accept: text/event-stream
```

The Workers terminal subscribes to the same correlated events and displays
source retrieval, normalization, price refresh, labor calculation, procedure
composition, visual processing, retries, dead letters, and publication. It is
an observability surface, not a prerequisite for displaying the answer.

Events use the existing versioned envelope and add query-specific payloads:

```json
{
  "event_id": "uuid",
  "event_type": "chat.answer.updated",
  "event_version": 1,
  "occurred_at": "timestamp",
  "producer": "normalization-worker",
  "request_id": "uuid",
  "projection_id": "uuid",
  "revision_id": "uuid",
  "correlation_id": "uuid",
  "idempotency_key": "stable-key",
  "payload": {
    "query_id": "uuid",
    "stage": "article_normalization",
    "status": "completed",
    "data_state": "normalized",
    "message": "Brake-line article revision published"
  }
}
```

Required event behavior:

- duplicate events are ignored by idempotency key;
- transient source, model, or storage failures retry with bounded backoff;
- exhausted failures publish a dead-letter event and degrade only the affected
  result or section;
- a retry cannot create a second article, price snapshot, procedure revision,
  visual artifact, or answer update;
- event history remains readable after completion; and
- source takedown or entitlement revocation prevents new access while
  retaining prior revisions and audit evidence.

## Persistence boundaries

The feature extends the existing persistence model with focused records rather
than embedding transient state in one large JSON document:

- **Chat queries:** conversation ID, message, idempotency key, resolved
  vehicle/candidates, current answer revision, status, and correlation ID.
- **Job plans:** requested operations, supporting operations, classification,
  parser/composition versions, and review state.
- **Quote revisions:** required/recommended operations, overlap calculations,
  parts snapshots, source watermarks, and evidence IDs.
- **Price snapshots:** canonical part, source part, amount, currency, priced
  date, source snapshot, freshness, and refresh state.
- **Derived article revisions:** deterministic identity, source article IDs,
  procedure steps, labor references, visual references, and changelog.
- **Visual artifacts:** original source object, derived vector object,
  processor version, render validation, and review state.
- **Worker events:** event envelope, stage, retry count, terminal outcome,
  correlation ID, and payload reference.

Existing `catalog_articles`, `normalized_source_bundles`, `dataset_revisions`,
`extraction_evidence`, `publication_events`, and `ingestion_jobs` remain
authoritative where their current contracts already cover the data. New
migrations must preserve forward-only behavior, immutable revisions, source
watermarks, and idempotency constraints.

## Error and review behavior

- **Unauthenticated:** return the existing authentication error contract;
  do not create a query.
- **Ambiguous vehicle:** show options and available provisional data, then ask
  the clarification in chat.
- **No matching component:** return a structured review-needed response and
  explain what was not understood.
- **AutoAPI unavailable:** return cached or source data already available;
  otherwise return a retryable source-unavailable state without fabrication.
- **Normalization failure:** retain source data, mark the item
  `source_unnormalized` or `needs_review`, and continue unrelated stages.
- **Price refresh failure:** retain the stale price with its pricing date and
  retry state.
- **Procedure composition failure:** return the available single-component
  procedures and labor information; do not publish an unsupported combined
  procedure.
- **Visual failure:** publish the procedure without the vector, retain the
  original source pointer, and mark visual processing failed.
- **Invalid evidence:** do not publish the affected fact or step; expose the
  review-needed state and evidence error.
- **Human review pending:** show `UNREVIEWED — human review pending`; this is
  a label, not an implicit approval or mutation of review records.

## Security and source rights

All source records retain URI, attribution, terms/license metadata, content
hash, source version, retention status, and takedown state. A takedown blocks
new retrieval and publication while prior revisions remain auditable according
to the retention policy.

The chatbot never receives provider credentials. AutoAPI credentials, model
credentials, database credentials, and object-storage credentials stay behind
environment or secret-manager interfaces. Worker events redact secrets and
avoid embedding raw authorization headers or sensitive source payloads.

## Verification requirements

The implementation is not complete until tests cover the full vertical slice:

1. Parse a single natural-language vehicle/job/quote request.
2. Return numbered and clickable vehicle options for an ambiguous vehicle.
3. Execute immediately after a typed or clicked selection.
4. Return a complete procedure in the initial response when source data is
   available.
5. Derive required and recommended supporting operations.
6. Calculate separate labor subtotals and a combined overlap-aware total.
7. Return parts prices, pricing dates, and `markup_applied=false`.
8. Return a 30-day stale price immediately while enqueueing refresh.
9. Return raw/source data while normalization is processing.
10. Persist every accessed source article and prevent duplicate ingestion.
11. Reuse a persisted derived procedure on a warm request.
12. Publish correlated worker events and update the same answer.
13. Redraw an existing source diagram into a vector artifact and link the
    original; do not create a vector when no source image exists.
14. Preserve evidence, source watermarks, revision history, retry state, and
    review labels.
15. Exercise AutoAPI miss behavior and all local fake-source/fake-payment
    paths in the Compose smoke environment.

Performance is measured separately for warm normalized retrieval and cold
source fulfillment. The warm path must not invoke AutoAPI or Mercury-2 when a
valid reusable answer exists. The cold path may be slower, but it must return
available data without waiting for background normalization.

## Delivery boundary

This design is implemented through the existing mandatory
[pre-implementation planning and tracking gate](../../agents/pre-implementation-gate.md).
The design and implementation plan must be recorded in the repository,
synchronized to Issue #87 and Project #8, and pinned to the implementation
base SHA before any worker changes implementation files.
