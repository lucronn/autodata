# AutoData Platform Architecture Blueprint

## Purpose

AutoData is an automotive repair-data platform that turns public automotive sources into traceable, searchable, vehicle-specific datasets. A purchaser should be able to request a make/model/year/region dataset, see useful core information quickly, and receive deeper TSB, procedure, wiring, diagram, image, and evidence-backed enrichment as it is processed.

This document is the decision record for the initial architecture package. It describes boundaries and contracts for a later implementation; it does not itself create application code, cloud resources, GitHub resources, or a remote repository.

## Goals

- Deliver a viewable vehicle-specific dataset quickly after a successful one-time purchase.
- Continue deep enrichment asynchronously without blocking the initial viewable projection.
- Represent ICE, hybrid, EV, electrical, diagnostic, repair, inventory, maintenance, and feedback data without flattening meaningful domain distinctions.
- Preserve provenance from every published fact to a source snapshot, document version, page or region, extraction run, and review decision where available.
- Make revisions immutable, auditable, and safe to consume while new enrichment is published.
- Give operators explicit quality, review, takedown, and entitlement controls.
- Provide local developer parity using containers and deterministic fake source/payment services.
- Make delivery work visible through a parameterized GitHub Project and a protected-main workflow.

## Non-goals for the first implementation slice

- Building the end-user web application.
- Supporting multiple organizations with hard tenant isolation on day one.
- Introducing a separate search cluster before PostgreSQL/pgvector scale requires it.
- Guaranteeing that arbitrary public web material may be republished; source rights, attribution, retention, and takedown policy remain mandatory.
- Automating GitHub or cloud mutations from this documentation package.

## Approved architecture

The repository is a modular monorepo with a small number of deployables. Go owns the synchronous API, authorization, entitlement-aware reads, and review commands. Python owns source adapters, OCR, document extraction, normalization, validation, embeddings, and enrichment. PostgreSQL with pgvector is the system of record; NATS JetStream carries durable jobs and events; S3-compatible storage holds raw and derived artifacts.

```text
Clients / internal tools
          |
       Go API
  auth, RBAC, entitlement checks,
  dataset reads, review, feedback
          |
   PostgreSQL + pgvector
   canonical records, projections,
   revisions, provenance, audit
          ^
          |
 NATS JetStream event backbone
   durable jobs, retries, DLQs, events
          |
 Python workers
  fast source ingest, deep enrichment,
  OCR, extraction, validation, embeddings
          |
 Object storage
  source docs, page images, OCR,
  diagrams, meshes, evidence artifacts
```

### Repository boundaries

```text
/apps/api-go                 Synchronous API and authorization boundary
/workers/ingestion-python    Fast/deep source ingestion and document processing
/workers/enrichment-python   Enrichment, embeddings, quality, and publication jobs
/packages/contracts          Versioned API/event schemas and generated clients
/db/migrations                Relational schema and controlled migration history
/infra/compose                Local development topology
/infra/k8s                    Provider-neutral deployment templates
/docs/architecture           System, domain, lifecycle, and operations documentation
/docs/github                 Repository and GitHub Project operating model
```

### Bounded contexts

The canonical model follows the domain design supplied for AutoData and is grouped into the logical contexts in [domain-model.md](../../architecture/domain-model.md). The API exposes projections and lifecycle status instead of mirroring every table. Workers may create candidates and evidence, but only a publication transition makes data available as canonical or purchaser-facing content.

### Core invariants

1. No AI extraction is published without a source reference and extraction metadata.
2. A viewable projection is never made unavailable merely because a deep section failed.
3. Published revisions are immutable; enrichment creates a new revision and changelog.
4. Every asynchronous handler is idempotent and has bounded retries plus dead-letter handling.
5. Entitlement checks happen at the API boundary and again before sensitive fulfillment work.
6. Payment webhooks are signature-verified and replay-safe.
7. Source takedown and entitlement revocation stop access without erasing audit history.

## Quality and governance

Public-source aggregation requires source URL or identity, publisher, retrieval time, license/terms metadata, attribution requirements, content hash, retention state, and takedown state. Raw material is quarantined before parsing. Candidate facts retain page/region evidence, model/provider version, confidence, extraction timestamp, and human-review history.

The initial organization uses these roles: platform admin, ingestion operator, data reviewer, support/billing operator, and dataset viewer. The data model keeps organization ownership explicit so future tenant isolation does not require rewriting the projection and entitlement contracts.

## Delivery decisions

- Runtime: Go API plus Python workers.
- Persistence: PostgreSQL with pgvector.
- Jobs/events: NATS JetStream.
- Artifacts: S3-compatible storage, MinIO locally.
- Local orchestration: Docker Compose.
- Deployment posture: Kubernetes-compatible and cloud-neutral.
- Commercial model: one-time entitlement for a vehicle-specific dataset product.
- Payment reference: Stripe adapter with deterministic local fake provider.
- Git workflow: trunk-based development with protected `main`.
- Planning: one parameterized GitHub Portfolio Project.

## Related documents

- [Domain model](../../architecture/domain-model.md)
- [Dataset lifecycle](../../architecture/dataset-lifecycle.md)
- [API and event contracts](../../architecture/contracts.md)
- [Infrastructure and developer environment](../../architecture/infrastructure-and-dev.md)
- [GitHub operating model](../../github/operating-model.md)
- [GitHub Project bootstrap](../../github/project-bootstrap.md)

