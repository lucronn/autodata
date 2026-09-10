# Natural-Language Multi-Component Job Composition Specification

**Status:** implementation-ready design
**Date:** 2026-09-10
**Scope:** vehicle-scoped job planning from natural language

## Goal

Accept a natural-language request such as:

> Replace the alternator and starter on my 1999 Chevrolet Silverado 1500 2WD with the 5.3L engine.

Resolve the request to one canonical vehicle, locate the best normalized single-component articles for every requested component, calculate a combined labor estimate that counts shared work once, and return a structured procedure assembled from those articles.

The result must be useful when the data is already indexed and must remain safe and auditable when the system needs to fetch, normalize, or ask for review. Any source data successfully accessed while satisfying this request is also a cache-warming ingestion opportunity: it is captured, normalized, deduplicated, vehicle-linked, provenance-linked, and indexed for future lookups.

## Product behavior

The request is processed in this order:

1. Parse the vehicle and requested components from the query, or combine the query with an explicit vehicle selector.
2. Resolve the vehicle against the canonical vehicle identity graph. A deterministic matcher is authoritative; Mercury-2 may adjudicate only among supplied candidates and only above the configured confidence threshold.
3. Search the vehicle-scoped normalized article index for one or more articles per requested component.
4. If a required component article is not present, invoke the existing source fallback boundary using the canonical vehicle identifier. Persist the accessed article list/index and any individual article resources needed for the request as source snapshots, then normalize, deduplicate, attach provenance, vehicle-link, and index every successfully accessed resource.
5. Extract or validate a component operation graph from each selected single-component article. Every operation has a duration when known, dependencies, component coverage, and an evidence reference.
6. Calculate combined labor deterministically from the union of operations. Shared access, setup, isolation, removal, inspection, and teardown operations count once. Dependency order and the initial single-technician labor-hour basis are explicit.
7. Compose a procedure from the selected source articles and the calculated operation plan. The LLM can consolidate, reorder, and explain sourced steps; it cannot create unsupported vehicle facts, labor values, safety instructions, torque values, or tool requirements.
8. Validate the composed result. Unsupported claims, conflicting instructions, missing evidence, ambiguous vehicle identity, missing required articles, or unknown overlap move the result to `needs_review` instead of being silently hidden.
9. Persist the request, selected articles, labor calculation, procedure result, source watermark, model/version metadata, evidence links, and validation outcome. A later identical request at the same source/model watermark is served from the warm path without another source fetch or LLM call.

## Access-triggered ingestion and materialization

The platform uses read-through materialization for source-backed knowledge. “Accessed” means a source resource was successfully retrieved or supplied to the normalization boundary while fulfilling a user query. The policy applies to AutoAPI and every future source connector, not only to a named provider.

Each accessed resource is handled as follows:

1. Capture the raw bytes or structured response as an immutable `source_snapshot` and `source_artifact`, including URI, adapter, source version, retrieval time, content hash, license/terms metadata, and takedown metadata.
2. Normalize recognized vehicle identities, article-list entries, article content, procedures, labor operations, and evidence into canonical tables or derived records.
3. Associate records to the canonical vehicle/configuration only when the deterministic identity policy authorizes the association. Ambiguous candidates are retained as review material, not silently attached.
4. Deduplicate exact content by content hash and canonical fingerprint. Detect near duplicates using the existing similarity/review policy; retain lineage to all source occurrences while selecting one canonical record for search.
5. Store source snapshot, extraction run, evidence locator, normalized record, and review state together so a future lookup can use the normalized record without refetching the source.
6. Index the normalized result for vehicle-scoped retrieval immediately after successful persistence. A later source watermark or correction creates a new record/revision and does not mutate the prior audit trail.

An article list is itself a persisted ingestion unit. The list can create searchable article metadata and source lineage without forcing the system to fetch every article body. When an individual article body is later accessed, that body is independently captured, normalized, deduplicated, vehicle-linked, evidence-linked, and indexed. The list entry and article body share lineage but are not treated as the same content.

## Composed procedures as durable derived articles

When the labor calculator and procedure validator produce a combined procedure for multiple components, the result is persisted as a first-class derived article with a new stable `article_id` and human-readable title, for example `combined:1999-chevrolet-silverado-1500:alternator+starter:v1`. The ID is derived from the canonical vehicle/configuration, normalized component set, source article fingerprints, labor-calculation version, procedure-contract version, and source watermark; it is not chosen by the LLM.

The derived article records:

- its own normalized content fingerprint and immutable result revision;
- `article_kind = composed` and `origin = derived_job_plan`;
- the canonical vehicle/configuration;
- the selected source article IDs and source snapshot watermarks;
- the labor operation graph and overlap calculation;
- every source evidence ID used by the procedure;
- model, prompt-contract, validator, and processing versions;
- warnings, conflicts, review state, and the request that created it.

The derived article is searchable and reusable on future lookups. A matching fingerprint returns the existing composed article; a changed source watermark, selected article, labor graph, or composition contract creates a new immutable derived revision linked to the prior one. The derived article never replaces or mutates the individual source articles, and it is not publishable as `ready` when the underlying procedure is `needs_review`.

## Initial labor model

The initial release uses standard labor hours for one technician. It does not claim to model two technicians working in parallel or a shop-specific productivity multiplier.

Each article contributes an operation graph. An operation contains:

- a stable operation key;
- a human-readable action;
- duration in labor hours, or an explicit unknown value;
- component keys covered by that operation;
- prerequisite operation keys;
- a resource or work-area group;
- evidence references and extraction confidence;
- whether it is source-stated, deterministically derived, or requires review.

The calculator forms a graph union by stable operation key and normalized semantic identity. A shared operation is included once and linked to every component it serves. The combined total is the duration of the ordered union for one technician, subject to dependencies. It reports:

```text
standalone_hours = sum of each selected article's labor hours
overlap_hours = standalone_hours - combined_union_hours
total_labor_hours = combined_union_hours
```

The reported number is not fabricated when the input is incomplete:

- A known shared operation is counted once.
- An operation with unknown duration makes the estimate a range or `needs_review`, according to the product policy for that article.
- Conflicting durations or incompatible dependencies are preserved as conflicts and require review.
- A source article's published labor value is never overwritten by an LLM estimate.
- The output includes the assumptions and operation-level contribution used to calculate the total.

## Procedure composition model

The composer receives only the following bounded context:

- canonical vehicle identity and source watermark;
- requested components and job intent;
- selected normalized article content;
- operation graph and deterministic labor result;
- source evidence excerpts and locators;
- safety and review constraints.

The composer returns structured JSON with:

- ordered steps;
- component keys addressed by each step;
- prerequisites, tools, warnings, and completion checks when sourced;
- source article IDs and evidence IDs for each factual step;
- an explicit `derived` marker for ordering or wording that is a deterministic composition rather than source text;
- conflicts, omissions, and `needs_review` flags;
- model name, prompt-contract version, and generation timestamp.

The composed procedure is a convenience projection, not a new source of truth. The original single-component articles remain independently addressable and auditable.

## Statuses

The job-plan resource uses:

- `processing`: parsing, retrieval, normalization, or composition is in progress;
- `ready`: the labor estimate and procedure passed validation;
- `needs_review`: the system returned the available structured material but a person must resolve an identity, source, labor, safety, or procedure conflict;
- `failed`: processing exhausted retry policy or encountered a permanent input/dependency error.

The underlying dataset and section states remain the existing platform states. A deep-lane failure cannot revoke a previously viewable dataset revision or a previously valid job plan.

## Example result shape

```json
{
  "job_plan_id": "uuid",
  "status": "ready",
  "vehicle": {
    "vehicle_id": "uuid",
    "year": 1999,
    "make": "Chevrolet",
    "model": "Silverado 1500",
    "body_style": "pickup",
    "drivetrain": "2WD",
    "engine": "5.3L"
  },
  "requested_components": ["alternator", "starter"],
  "source_watermark": "source-version-or-timestamp",
  "labor": {
    "basis": "one_technician_standard_hours",
    "standalone_hours": 4.5,
    "overlap_hours": 0.75,
    "total_labor_hours": 3.75,
    "confidence": 0.96,
    "assumptions": ["battery isolation is shared"],
    "operations": [
      {
        "operation_id": "op-battery-isolation",
        "action": "Disconnect and isolate the battery",
        "duration_hours": 0.25,
        "components": ["alternator", "starter"],
        "evidence_ids": ["uuid"]
      }
    ]
  },
  "procedure": {
    "title": "Replace alternator and starter",
    "steps": [
      {
        "sequence": 1,
        "action": "Disconnect and isolate the battery.",
        "components": ["alternator", "starter"],
        "source_article_ids": ["alternator-article", "starter-article"],
        "evidence_ids": ["uuid"],
        "origin": "shared_source_step",
        "requires_review": false
      }
    ],
    "warnings": [],
    "requires_review": false
  },
  "derived_article": {
    "article_id": "combined:1999-chevrolet-silverado-1500:alternator+starter:v1",
    "revision_id": "uuid",
    "title": "Replace alternator and starter",
    "status": "ready",
    "fingerprint": "sha256"
  },
  "provenance": {
    "article_ids": ["alternator-article", "starter-article"],
    "evidence_ids": ["uuid"],
    "model": "mercury-2",
    "contract_version": 1
  }
}
```

## Non-goals for this slice

- Estimating labor for an unrecognized vehicle without a reviewable identity match.
- Treating a generic article as vehicle-specific without provenance and compatibility evidence.
- Calling every individual source article when a source exposes an article list; list retrieval remains the default discovery operation.
- Replacing the canonical vehicle graph or existing article-ingestion pipeline.
- Allowing arbitrary LLM prose to become a publishable procedure.
- Introducing a separate search engine or multi-technician scheduling model.
- Treating source access as a transient read that is intentionally discarded.
- Treating a composed procedure as an ephemeral response only; valid composed procedures are durable derived articles.
- Storing API keys in source code, fixtures, documentation, or generated artifacts.
