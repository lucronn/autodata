# AutoData API, Event, and Persistence Contracts

## Platform spine tables

| Table | Responsibility | Key invariants |
| --- | --- | --- |
| `dataset_products` | Sellable vehicle selector and section contract | Product version is immutable once purchased |
| `dataset_requests` | One requested make/model/year/region dataset | Duplicate request keys resolve to the same active request |
| `dataset_projections` | Entitlement-scoped materialized dataset | Projection points to canonical IDs and published revisions |
| `dataset_revisions` | Immutable purchaser-facing snapshots | Revision has source watermark, schema version, readiness, and changelog |
| `dataset_section_status` | Independent section readiness | One failed section does not hide another successful section |
| `entitlements` | Access grant for a purchaser/org | Provider event ID and request are idempotent |
| `source_snapshots` | Content-addressed source capture | Hash and retrieval metadata are retained |
| `source_artifacts` | Format-classified raw source resources | Raw object, media type, hash, and extraction status are retained |
| `vehicle_models` | Provider model variants for a canonical vehicle | Source/evidence locator and provider ID are retained |
| `powertrains` | Engine or powertrain variants for a model | Powertrain identity remains linked to its model and source |
| `inventory_parts` | Normalized parts and price observations | Ambiguous prices remain `needs_review` rather than being guessed |
| `catalog_articles` | Source article index for procedures, diagnostics, TSBs, and specifications | Article IDs, classification, source, and evidence are retained |
| `ingestion_jobs` | Lane-specific work and retries | Lane, processing version, and stable idempotency key are explicit |
| `extraction_runs` | OCR/LLM/embedding execution metadata | Model/provider/version and confidence are retained |
| `extraction_evidence` | Fact-to-source/page/region traceability | Evidence references an immutable source artifact |
| `publication_events` | Outbox and publication audit | Event identity is unique and replay-safe; delivery attempts are observable |
| `feedback_items` | Human issue, review, and correction workflow | Approved changes link to a new revision |
| `payment_events` | Verified provider webhook record | Provider event ID is unique; payload is not trusted before verification |

## Universal source-resource contract

The ingestion boundary is intentionally broader than any one provider or file schema. Connectors return a sequence of source resources with this logical contract:

```json
{
  "source_uri": "provider://resource/identifier",
  "source_version": "provider-version-or-retrieval-watermark",
  "media_type": "application/json",
  "payload": "raw bytes",
  "locator": "provider/page/path/when-available",
  "metadata": {
    "attribution": "source-specific terms and attribution"
  }
}
```

The intake layer computes `content_sha256`, stores the raw resource before extraction, and classifies it as structured data, a document, a diagram, or quarantined unsupported media. JSON API headers and bodies are retained together; unknown fields remain in the raw payload. Extractors produce typed candidates with stable keys and locators, but a candidate is not canonical data until normalization, provenance, evidence, confidence, and quality gates pass. A valid but unrecognized shape is retained with `needs_review`; it is never silently dropped or guessed into a domain table.

One dataset request may combine resources from different protocols and media types. The request correlation ID joins them, while each resource retains its own hash, source version, object key, extraction run, and evidence path. Duplicate payloads deduplicate by content hash, and distinct versions remain auditable.

When two or more source resources provide incompatible candidates for the same canonical field, normalization emits a conflict record containing the field, every candidate value, source URI/version, and evidence IDs. The affected fact is not selected by arrival order or filename; it remains unresolved until a reviewer records a decision. Conflict records are part of the normalized bundle and quality report, so a later implementation can persist and resolve them without changing the universal resource contract.

## Public API

The API is projection-oriented. Clients do not depend on table names or internal canonical joins.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/dataset-requests` | Create or reuse a purchased dataset request after entitlement authorization |
| `GET` | `/dataset-requests/{id}` | Read request, lane, fulfillment, and error status |
| `GET` | `/datasets/{id}` | Read the latest entitled projection revision |
| `GET` | `/datasets/{id}/sections` | Read section-level readiness and revision pointers |
| `GET` | `/datasets/{id}/revisions` | List entitled immutable revisions and changelogs |
| `GET` | `/datasets/{id}/evidence/{evidence_id}` | Resolve page/region evidence for a published fact |
| `GET` | `/datasets/{id}/search?q={query}&limit={n}` | Search approved evidence within the entitled projection |
| `POST` | `/datasets/{id}/feedback` | Submit a correction or quality issue |
| `POST` | `/datasets/{id}/feedback/{feedback_id}/review` | Resolve or reject a feedback item as a reviewer |
| `POST` | `/datasets/{id}/evidence/{evidence_id}/review` | Approve or reject pending evidence as a reviewer |

Dataset responses include:

```json
{
  "dataset_id": "uuid",
  "revision_id": "uuid",
  "availability": "viewable",
  "source_watermark": "timestamp-or-source-version",
  "sections": [
    {
      "name": "diagnostics",
      "status": "enriching",
      "last_published_revision": "uuid",
      "updated_at": "timestamp"
    }
  ]
}
```

The response may include a `data` object for published sections and a `warnings` array for incomplete, low-confidence, stale, or review-gated content. A client must be able to render the dataset from status and revision metadata without guessing whether missing fields are unavailable, not applicable, or still processing.

Feedback submission accepts `correction`, `missing`, `quality`, or `safety` categories and a bounded body, with optional `revision_id` and `evidence_id` references. The caller must hold the dataset entitlement. The API validates that a referenced revision belongs to the projection and that a referenced evidence record is approved, published, and linked to the same projection; otherwise it returns `REVISION_NOT_FOUND`, `INVALID_EVIDENCE`, or `REVIEW_REQUIRED` without creating a record. Valid feedback is inserted into `feedback_items` with status `open`. Reviewers resolve feedback by creating a new immutable revision when a correction is accepted; no published revision is mutated in place.

Feedback review is restricted to the `data_reviewer` role. The request accepts `{ "decision": "resolve" | "reject", "reason": "...", "applied_revision_id": "uuid" }`. `resolve` requires an existing published replacement revision in the same projection; `reject` must not include an applied revision. The review stores the reviewer, timestamp, reason, and replacement revision on the feedback item. Repeating the same terminal decision is idempotent; attempting the opposite terminal decision returns a non-retryable conflict. Published revisions remain immutable and auditable through their changelog, source watermark, provenance, and evidence links.

Evidence review is restricted to the `data_reviewer` role and accepts `{ "decision": "approve" | "reject", "reason": "..." }`. Only pending evidence that is not already linked to a published revision may transition. The decision records the reviewer principal, timestamp, and reason in the evidence metadata. Repeating the same decision is idempotent; changing an existing decision or reviewing already-published evidence returns a non-retryable conflict. Approval makes the evidence eligible for a later enrichment publication; it does not expose an unlinked fact to purchaser reads or mutate an existing revision.

## Authentication and authorization

The initial organization has these roles:

- `platform_admin`: configuration, policy, and lifecycle control.
- `ingestion_operator`: source adapters and job operations.
- `data_reviewer`: evidence review and publication approval.
- `support_billing_operator`: payment reconciliation and entitlement support.
- `dataset_viewer`: entitled dataset reads and feedback submission.

Every dataset read checks the caller's organization and active entitlement. A request with no entitlement returns `403`. A revoked dataset or revision returns `410` or a documented policy-specific error class. Internal worker endpoints require service identity and do not reuse end-user bearer tokens.

## Error contract

Errors use a stable shape:

```json
{
  "error": {
    "code": "DATASET_NOT_VIEWABLE",
    "message": "The dataset is still in fast-lane processing.",
    "request_id": "uuid",
    "retryable": true,
    "details": {}
  }
}
```

Required error classes include:

| Code | HTTP | Retryable | Meaning |
| --- | ---: | :---: | --- |
| `UNAUTHENTICATED` | 401 | no | Credentials are absent or invalid |
| `ENTITLEMENT_REQUIRED` | 403 | no | Caller lacks access to the requested dataset |
| `FORBIDDEN` | 403 | no | Caller is authenticated but lacks the required role |
| `ENTITLEMENT_REVOKED` | 410 | no | Access was withdrawn |
| `DATASET_NOT_VIEWABLE` | 409 | yes | Fast-lane minimum contract is not published |
| `SECTION_FAILED` | 200/207 | yes | Dataset is readable but one section has failed |
| `REVISION_NOT_FOUND` | 404 | no | Revision is not visible to this caller |
| `DUPLICATE_REQUEST` | 200/202 | no | Existing request is returned or processing is reused |
| `INVALID_EVIDENCE` | 422 | no | Evidence reference does not resolve to a published artifact |
| `REVIEW_REQUIRED` | 409 | yes | Publication is blocked pending review |
| `INVALID_REQUEST` | 422 | no | Request body or required idempotency input is invalid |

## Event envelope

All NATS messages use this versioned envelope:

```json
{
  "event_id": "uuid",
  "event_type": "dataset.section.published",
  "event_version": 1,
  "occurred_at": "timestamp",
  "producer": "enrichment-worker",
  "request_id": "uuid",
  "projection_id": "uuid",
  "revision_id": "uuid",
  "correlation_id": "uuid",
  "idempotency_key": "stable-key",
  "payload": {}
}
```

Subjects are versioned by event type and schema version at the contract package boundary:

```text
dataset.fast.requested
dataset.viewable
dataset.deep.requested
dataset.section.published
dataset.enrichment.failed
dataset.review.requested
dataset.revision.revoked
```

Consumers must tolerate redelivery, reject unsupported event versions explicitly, and record the envelope before applying a side effect. Publication events are written through an outbox so database state and emitted events can be reconciled.

The publication outbox adds `producer`, `delivery_status`, `delivery_attempts`, `last_delivery_error`, and `delivered_at` to the audit row. A relay claims the oldest `pending` or retryable `failed` row with `FOR UPDATE SKIP LOCKED`, commits the claim, publishes the stored envelope to its allow-listed subject, and then records success. A crash between the database commit and NATS publish can produce a duplicate; this is intentional at-least-once delivery. The relay sends the event idempotency key as the NATS `Nats-Msg-Id`, and every consumer must deduplicate by `idempotency_key`. Delivery failures are retried up to the configured attempt limit and then remain auditable as `dead_letter` for operator replay or correction.

## Payment adapter

The internal payment boundary is provider-neutral:

```text
create_checkout_session(product_id, purchaser_id) -> CheckoutSession
verify_webhook(headers, body) -> VerifiedPaymentEvent
record_payment_event(event) -> PaymentEvent
create_entitlement(payment_event) -> Entitlement
revoke_entitlement(entitlement_id, reason) -> Revocation
```

Stripe is the reference production adapter. The local fake provider emits deterministic event IDs and signed fixtures. Webhook handling verifies the signature before parsing trusted fields, records the provider event exactly once, and reconciles delayed fulfillment from the outbox.

Verified checkout events may carry `dataset_request_id` as the provider checkout metadata reference. Reconciliation records the event before fulfillment and tracks `fulfillment_status` (`pending`, `fulfilled`, or `failed`), `fulfillment_attempts`, `last_fulfillment_error`, and `fulfilled_at`. If the request is not present when the webhook arrives, the event remains pending; the payment reconciler retries it after the request is created. A successful retry creates or reuses one entitlement and one dataset projection, transitions a `purchased` request to `fast_lane_processing`, and is safe to repeat. A reused provider event with a different payload is rejected as a payment conflict. Revoked requests or entitlements are never reactivated by replay.

## Revision and evidence rules

Every published fact must resolve to a source snapshot and, for extracted document content, an extraction run and evidence record. Evidence includes source document, page number, bounding box or region when available, extracted string, confidence, model version, reviewer state, and timestamps.

Approved evidence may be indexed in the `extraction_evidence.embedding` `vector(1536)` column. Embedding generation is behind the provider-neutral worker boundary and records its provider/version in the revision changelog; the local deterministic adapter is only a reproducible development implementation. Pending or rejected evidence is never embedded for purchaser-facing retrieval, and a missing vector does not alter the already-published dataset revision.

A stale revision may be requested only when the caller is entitled to that revision. The default dataset read returns the latest permitted revision. A revision is never updated in place; corrections, enrichment, unit conversion changes, and source replacement produce a new revision with a changelog.

Evidence search is projection-scoped and returns only approved evidence linked to a published revision in the caller's entitled projection:

```json
{
  "dataset_id": "uuid",
  "results": [
    {
      "evidence_id": "uuid",
      "revision_id": "uuid",
      "locator": "page=9",
      "extracted_text": "P0300 misfire diagnostic procedure",
      "confidence": 0.99,
      "score": 0.81
    }
  ]
}
```

The initial local API uses the same deterministic embedding algorithm as the local enrichment adapter to turn `q` into a 1536-dimensional query vector. A production embedding service can replace that adapter without changing the projection or evidence contract. Empty or invalid limits return `422`; missing/revoked entitlements use the same authorization errors as dataset reads.
