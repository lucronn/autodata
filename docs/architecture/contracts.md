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
| `ingestion_jobs` | Lane-specific work and retries | Lane, processing version, and stable idempotency key are explicit |
| `extraction_runs` | OCR/LLM/embedding execution metadata | Model/provider/version and confidence are retained |
| `extraction_evidence` | Fact-to-source/page/region traceability | Evidence references an immutable source artifact |
| `publication_events` | Outbox and publication audit | Event identity is unique and replay-safe |
| `feedback_items` | Human issue, review, and correction workflow | Approved changes link to a new revision |
| `payment_events` | Verified provider webhook record | Provider event ID is unique; payload is not trusted before verification |

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
| `POST` | `/datasets/{id}/feedback` | Submit a correction or quality issue |

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

## Revision and evidence rules

Every published fact must resolve to a source snapshot and, for extracted document content, an extraction run and evidence record. Evidence includes source document, page number, bounding box or region when available, extracted string, confidence, model version, reviewer state, and timestamps.

A stale revision may be requested only when the caller is entitled to that revision. The default dataset read returns the latest permitted revision. A revision is never updated in place; corrections, enrichment, unit conversion changes, and source replacement produce a new revision with a changelog.
