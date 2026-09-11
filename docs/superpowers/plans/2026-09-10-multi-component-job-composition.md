# Natural-Language Multi-Component Job Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a vehicle-scoped natural-language job planner that selects normalized single-component articles, calculates combined one-technician labor hours with shared-operation overlap counted once, and returns an evidence-backed LLM-composed procedure.

**Architecture:** Keep the Go API as the authenticated boundary and make the Python ingestion/enrichment side responsible for intent resolution, article acquisition, operation extraction, deterministic labor calculation, and constrained procedure composition. Every source resource successfully accessed for a request is read-through materialized into the existing source snapshot/normalization/evidence pipeline. The LLM is advisory and schema-constrained. PostgreSQL stores durable job requests/results, operation graphs, and composed derived articles; existing source snapshots and extraction evidence remain the provenance authority; NATS JetStream carries retryable asynchronous work; the warm path serves a previously validated plan at the same source/model watermark without invoking the LLM or refetching the source.

**Tech Stack:** Existing Go HTTP API, Python workers, PostgreSQL/pgvector, NATS JetStream, MinIO/S3-compatible evidence storage, generated bindings from `packages/contracts/contract.json`, pytest/unittest, Go tests, Docker Compose integration fixtures, Mercury-2 through the existing environment-only `Mercury2Client` boundary.

**Spec:** `docs/superpowers/specs/2026-09-10-multi-component-job-composition.md`

> **Current status (2026-09-11):** The implementation slice described by this plan is on the pushed `automation/knowledge-fallback-runtime` branch and is tracked by [Issue #85](https://github.com/lucronn/autodata/issues/85) and [Project #8](https://github.com/users/lucronn/projects/8). The canonical specification records verified behavior. Remaining follow-ups are human review of source evidence and live AutoAPI verification for genuinely uncached source hydration; the checkboxes below are the historical execution checklist, not an indication that the slice is unstarted.

## Global Constraints

- This plan is for the existing AutoData repository at `/Users/dull/Documents/ChatGPT/autodata`.
- Do not modify or stage the user-provided untracked `sample data/` directory unless a later implementation task explicitly requires a narrowly named fixture copied from it.
- Do not print, commit, or embed any API credential. Mercury-2 credentials are supplied only through the existing secret-managed environment variables used by `Mercury2Client`.
- Do not make an LLM response authoritative for vehicle identity, labor values, safety facts, compatibility, or evidence.
- The initial labor basis is one technician using standard labor hours. Requests that ask for parallel multi-technician scheduling are rejected as unsupported rather than approximated.
- Every factual operation and procedure step must retain an evidence path to a source snapshot and locator, or be marked as derived and subject to the validation policy.
- A missing, ambiguous, conflicting, or low-confidence input must yield `needs_review` with structured reasons; it must not be silently converted to a confident result.
- Existing cache-first knowledge search and source fallback behavior remains backward compatible.
- Any successfully accessed AutoAPI or other connector resource is persisted and indexed for future lookups; source access is never intentionally discarded after producing a response.
- Article lists and article bodies are separate ingestion units with shared lineage. Fetching a list does not require fetching every article body, but every body that is later accessed is normalized and persisted.
- A validated multi-component procedure is persisted as a new `catalog_articles` derived record with a deterministic ID/fingerprint and lineage to all contributing articles and evidence.
- Derived articles never mutate source articles. A changed source watermark, source selection, labor graph, or composition contract creates a new derived revision.
- Published data and job-plan results are immutable. Corrections create a new revision/result and preserve the prior audit trail.
- Every asynchronous handler must define an idempotency key, retry classification, maximum retry behavior, and dead-letter subject.
- Each completed task below is committed separately with a focused commit message after its tests pass. Never use `git add -A`; stage only the paths listed in that task.

---

## Task 1: Establish the domain contract and acceptance fixtures

**Files:**

- Create `docs/superpowers/specs/2026-09-10-multi-component-job-composition.md` using the specification in this plan.
- Create `workers/ingestion-python/tests/fixtures/job_plan_articles.json` with two deterministic articles for a 1999 Chevrolet Silverado 1500 2WD 5.3L: alternator and starter. Include a shared battery-isolation operation, component-specific operations, durations, dependencies, and evidence locators.
- Create `workers/ingestion-python/tests/fixtures/job_plan_queries.json` with successful, ambiguous, missing-component, unsupported-parallelism, and conflicting-labor queries.
- Extend `scripts/contracts/test_contracts.py` only with fixture-independent checks that the job-plan contract names and event subjects are present once the canonical contract is added in Task 2.

**Steps:**

- [ ] Write the canonical vehicle/job examples and explicitly state the single-technician labor basis.
- [ ] Add fixture records where every labor operation has a stable key and evidence locator.
- [ ] Add fixture assertions for the expected union total: standalone hours 4.5, shared overlap 0.75, combined total 3.75.
- [ ] Run the focused fixture/schema tests and observe the expected failure because the job-plan contract and calculator do not yet exist.
- [ ] Commit only the specification and fixture paths with `docs: specify multi-component job composition`.

**Verification:**

```bash
python3 -m unittest workers/ingestion-python/tests/test_job_plan_fixtures.py
```

The first run is expected to fail with the missing test/module error; the tests become executable after Task 2 and Task 5 add the contract and calculator.

## Task 2: Add canonical API and event contracts

**Files:**

- Modify `packages/contracts/contract.json`.
- Regenerate `packages/contracts/go/contracts.go` and `packages/contracts/python/autodata_contracts/contracts.py` using `python3 scripts/contracts/generate.py`.
- Modify `packages/contracts/python/autodata_contracts/__init__.py` only if the generated job-plan classes require explicit exports.
- Update `packages/contracts/go/contracts_test.go` and `scripts/contracts/test_contracts.py`.

**Contract decisions:**

- Add `job_plan_status`: `processing`, `ready`, `needs_review`, `failed`.
- Add `job_plan_origin`: `source_step`, `shared_source_step`, `derived_ordering`, `llm_wording`.
- Add event subjects: `job.plan.requested`, `job.plan.completed`, `job.plan.failed`, `job.plan.review.requested`.
- Add `job_plan_request` with required `job_plan_id`, `vehicle`, `query`, and `status`; allow optional `options` and `idempotency_key` only where transport already supplies the header.
- Add `job_plan_response` with required `job_plan_id`, `status`, `vehicle`, `requested_components`, `source_watermark`, `labor`, `procedure`, and `provenance`.
- Add `job_plan_labor` with required `basis`, `standalone_hours`, `overlap_hours`, `total_labor_hours`, `confidence`, `assumptions`, and `operations`.
- Add `job_plan_operation` with required `operation_id`, `action`, `duration_hours`, `components`, `evidence_ids`, and `origin`; permit nullable duration for a review-required estimate.
- Add `job_plan_procedure` with required `title`, `steps`, `warnings`, and `requires_review`.
- Add `job_plan_step` with required `sequence`, `action`, `components`, `source_article_ids`, `evidence_ids`, `origin`, and `requires_review`.
- Add `job_plan_provenance` with required `article_ids`, `evidence_ids`, `model`, and `contract_version`.
- Add `job_plan_derived_article` with required `article_id`, `revision_id`, `title`, `status`, and `fingerprint`; allow normalized body and steps in the job-plan response.
- Add error codes `JOB_PLAN_NOT_FOUND`, `JOB_PLAN_REVIEW_REQUIRED`, `JOB_PLAN_UNSUPPORTED`, and `JOB_PLAN_CONFLICT`.

**Steps:**

- [ ] Add the enums and object definitions to the canonical JSON source without adding new required fields to existing contracts.
- [ ] Add the new subjects and required-field lists.
- [ ] Regenerate both language bindings with the repository generator; never edit generated files by hand.
- [ ] Add tests for enum membership, required-field membership, backward-compatible existing contracts, and Go/Python generated parity.
- [ ] Run `python3 scripts/contracts/test_contracts.py` and `go test ./packages/contracts/go`.
- [ ] Commit only contract source, generated bindings, and contract tests with `feat: define job plan contracts`.

## Task 3: Define the Python domain types and strict validators

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/job_plan_models.py`.
- Create `workers/ingestion-python/src/autodata_ingestion/job_plan_validation.py`.
- Create `workers/ingestion-python/tests/test_job_plan_models.py`.
- Create `workers/ingestion-python/tests/test_job_plan_validation.py`.

**Implementation details:**

- Use frozen dataclasses or equivalent immutable value objects for `JobIntent`, `ComponentArticle`, `LaborOperation`, `LaborPlan`, `ProcedureStep`, `ProcedureDraft`, and `JobPlanResult`.
- Normalize component keys using lowercase, whitespace normalization, and a finite alias map for common automotive terms. Preserve the original phrase separately for auditability.
- Reject empty queries, empty component lists, invalid hours, negative durations, duplicate operation IDs, missing dependencies, cycles, malformed evidence references, and unsupported technician counts.
- Accept evidence IDs and locators only as references supplied by the retrieval/persistence layer; validators must not manufacture evidence.
- Validate that an operation’s components are a subset of the requested components.
- Validate that every non-derived procedure step has at least one source article and evidence reference.
- Validate that a `ready` procedure has no unresolved conflict, unsupported operation, or safety omission.
- Ensure serialized output is stable: sorted IDs where order is not semantic, ordered steps where order is semantic, and no secrets or raw prompts.

**Steps:**

- [ ] Write failing tests for valid alternator/starter models, malformed operations, dependency cycles, invalid evidence, unsupported parallelism, and stable JSON serialization.
- [ ] Run the focused tests and capture the expected missing-model failure.
- [ ] Implement immutable models and validators with explicit error codes.
- [ ] Re-run the focused tests until they pass.
- [ ] Commit only model/validator files with `feat: add job plan domain validation`.

## Task 4: Build constrained natural-language intent resolution

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/job_intent.py`.
- Create `workers/ingestion-python/tests/test_job_intent.py`.
- Modify `workers/ingestion-python/src/autodata_ingestion/mercury2.py` only to add a narrowly scoped structured job-intent adapter that reuses `Mercury2Client` and environment-only configuration.
- Extend `workers/ingestion-python/tests/test_mercury2.py` with the adapter response-validation cases.

**Implementation details:**

- First use deterministic parsing for explicit vehicle fields, common year/make/model/engine patterns, and component aliases.
- If the deterministic parser is incomplete or ambiguous, send Mercury-2 a bounded JSON prompt containing the query and any explicit vehicle selector. Request only `{vehicle_observation, components, operation_kind, confidence, unresolved_terms}`.
- Mercury-2 may propose component names and candidate vehicle fields, but the canonical vehicle matcher must re-score and authorize the candidate. The adapter must reject fields outside the allowed schema, unknown components, confidence outside 0..1, and invented candidate IDs.
- Set temperature to zero through the existing client behavior. Include the model name and prompt-contract version in the request fingerprint.
- Do not pass whole source documents to intent resolution; pass only the natural-language query and known selector context.
- If Mercury-2 is unavailable, return deterministic `needs_review` or use already-resolved explicit fields; never make the API unavailable for a warm-path lookup.

**Steps:**

- [ ] Add failing tests for explicit parsing, aliases such as `alt`, natural-language component lists, ambiguous vehicle text, invalid LLM JSON, candidate outside the deterministic set, and provider failure.
- [ ] Run `python3 -m pytest workers/ingestion-python/tests/test_job_intent.py workers/ingestion-python/tests/test_mercury2.py` and observe the missing adapter failure.
- [ ] Implement deterministic parsing and the constrained Mercury-2 adapter.
- [ ] Validate all model output before it can reach retrieval or persistence.
- [ ] Re-run the focused tests and commit with `feat: resolve natural language job intent`.

## Task 5: Add vehicle-scoped component article selection

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/job_article_selector.py`.
- Create `workers/ingestion-python/src/autodata_ingestion/source_access_materializer.py`.
- Modify `workers/ingestion-python/src/autodata_ingestion/vehicle_article_query.py` only to expose reusable vehicle-key normalization and ranking primitives without changing existing response behavior.
- Modify `workers/enrichment-python/src/autodata_enrichment/search_processor.py` only where needed to index component aliases and operation metadata while preserving current article/procedure search.
- Create `workers/ingestion-python/tests/test_job_article_selector.py`.
- Create `workers/enrichment-python/tests/test_job_search_index.py` cases for component filtering and evidence preservation.

**Implementation details:**

- Search by canonical vehicle ID/configuration before title/body similarity. Do not return an article attached only to a nearby vehicle configuration without a review flag.
- Rank by exact component identity, vehicle configuration specificity, operation kind, article quality/reviewer state, lexical/embedding score, and evidence completeness.
- Require one selected article per requested component for a `ready` result. If several articles are materially similar, select one canonical article and retain the alternatives in the audit record.
- Reuse the existing cache-first fallback path. A cache miss may request the source article list/content for the canonical vehicle; source connectors must not enumerate every individual article when the source list is sufficient for selection.
- Every successfully accessed source resource becomes a materialization record before the lookup is considered fulfilled. Article-list metadata and article bodies are independently captured; the materializer calls the existing source snapshot, artifact, normalization, evidence, and persistence boundaries and is idempotent by source URI, source version, content hash, and locator.
- A source response containing multiple recognized records materializes every record present in that response, not only the record selected for the current query, subject to source terms, size limits, and review/quarantine policy. This is the cache-warming rule for future lookups.
- Exact duplicate content collapses to one normalized record. Near-duplicate content retains every source occurrence as lineage and goes through the existing similarity/review policy; no provenance occurrence is discarded.
- Define an explicit `article_selection_fingerprint` from canonical vehicle ID, normalized component keys, query intent, source watermark, and selector version.
- Return selection reasons and rejected candidates for diagnostics, but do not expose hidden source material to a purchaser without entitlement.

**Steps:**

- [ ] Add failing tests for exact vehicle matches, engine/configuration disambiguation, similar-article deduplication, missing component, stale article, and evidence-less article rejection.
- [ ] Add failing materializer tests for article-list capture, individual article capture, multi-record response materialization, exact replay idempotency, content-hash deduplication, near-duplicate review, and source-term quarantine.
- [ ] Run the focused selector/materializer/index tests and observe the expected missing selector/materializer behavior.
- [ ] Implement selection, ranking, cache-miss delegation, and universal source read-through materialization.
- [ ] Re-run the focused tests and commit with `feat: select and materialize vehicle job articles`.

## Task 6: Implement the deterministic overlap-aware labor calculator

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/labor_calculator.py`.
- Create `workers/ingestion-python/tests/test_labor_calculator.py`.
- Add migration design inputs to `docs/architecture` only if needed for the operation schema; schema implementation is Task 8.

**Implementation details:**

- Accept the validated operation graphs from the selected articles; do not accept a free-form LLM labor estimate.
- Normalize operation identity from a source stable key plus a deterministic semantic key built from action class, normalized work area, and required resource. Preserve source keys for audit.
- Merge exact/shared operations once and union their component links and evidence links.
- Topologically order dependencies and calculate the one-technician union duration. Reject cycles and impossible dependencies.
- Calculate and return `standalone_hours`, `overlap_hours`, and `total_labor_hours` with decimal-safe arithmetic. The sum must satisfy `standalone_hours = overlap_hours + total_labor_hours` within the declared precision.
- Treat unknown duration, conflicting duration, missing prerequisite, and inferred overlap as explicit review conditions. Return a range only when lower and upper bounds can be derived from known durations; otherwise return a nullable total and `needs_review`.
- Preserve component contribution rows so the API can explain exactly why shared work was counted once.
- Keep the algorithm independent of Mercury-2 and any network service.

**Required test matrix:**

- Alternator plus starter with one shared battery-isolation operation: 4.5 standalone, 0.75 overlap, 3.75 total.
- Two components with no shared work: total equals standalone.
- Three components sharing setup and teardown: each shared operation counted once.
- Dependency order where article order differs from execution order.
- Duplicate operation keys with different evidence: merged once, evidence unioned.
- Unknown duration: no false precise total.
- Conflicting durations: `needs_review`, conflict details retained.
- Cycle: permanent validation error.
- Technician count other than one: unsupported error.

**Steps:**

- [ ] Write the failing test matrix before implementation.
- [ ] Run `python3 -m pytest workers/ingestion-python/tests/test_labor_calculator.py` and observe the expected missing module failure.
- [ ] Implement operation normalization, graph union, topological ordering, decimal arithmetic, and review conditions.
- [ ] Re-run tests and assert all operation-level evidence survives serialization.
- [ ] Commit with `feat: calculate overlap-aware job labor`.

## Task 7: Implement evidence-bounded procedure composition

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/procedure_composer.py`.
- Create `workers/ingestion-python/tests/test_procedure_composer.py`.
- Extend `workers/ingestion-python/tests/test_mercury2.py` for structured procedure response handling.

**Implementation details:**

- Build the composer input from selected article steps, labor operations, vehicle identity, evidence excerpts/locators, and explicit safety/review rules.
- Ask Mercury-2 for structured procedure JSON only. The prompt must say that source articles are authoritative, unsupported facts are prohibited, and unresolved conflicts must be surfaced.
- Require each generated step to contain a sequence, action, component keys, source article IDs, evidence IDs, origin, and review flag.
- Run the deterministic validator after the LLM response. A step referring to an article/evidence not present in the input is invalid. A step that adds an unsupported torque, fluid, tool, hazard, or vehicle fact is rejected or marked for review.
- Use deterministic fallback composition when Mercury-2 is unavailable: merge source steps by operation dependency and deduplicate shared steps, returning `needs_review` if natural-language consolidation is required.
- Never replace or mutate source article text. Store the composed procedure as a new durable derived article with a deterministic article ID and content fingerprint, a model/prompt contract fingerprint, and lineage to every contributing article and evidence record.
- Use `article_kind = composed` and `origin = derived_job_plan`. The LLM never chooses the article ID. The ID is derived from canonical vehicle/configuration, normalized component set, source article fingerprints, labor-calculation version, procedure-contract version, and source watermark.
- Make a composed article searchable after its result revision is persisted. A later identical request reuses the composed article; any source, labor, or contract change creates a new immutable derived revision linked to the previous revision.
- Do not publish a composed article as `ready` when its labor plan or procedure is `needs_review`; retain the structured draft and review reasons for operators.

**Steps:**

- [ ] Write failing tests for a valid combined procedure, shared-step deduplication, source evidence propagation, hallucinated evidence IDs, unsupported torque/tool claims, contradictory source steps, and LLM outage fallback.
- [ ] Run the focused tests and observe the expected missing composer failure.
- [ ] Implement bounded prompt construction, response parsing, deterministic validation, and safe fallback.
- [ ] Re-run tests and commit with `feat: compose evidence-backed job procedures`.

## Task 8: Persist job plans and operation provenance

**Files:**

- Create `db/migrations/022_job_plans.sql`.
- Modify `workers/ingestion-python/src/autodata_ingestion/bundle_persistence.py` or add `workers/ingestion-python/src/autodata_ingestion/job_plan_persistence.py` for the smallest isolated persistence boundary.
- Create `workers/ingestion-python/tests/test_job_plan_persistence.py`.
- Extend `scripts/dev/test_migrations.py` with the new migration and invariant checks.

**Schema decisions:**

- `job_plans`: request ID, organization ID, canonical vehicle ID/configuration, original query, normalized intent JSON, status, source watermark, selector version, model/prompt contract version, idempotency key, created/updated timestamps, failure/review details.
- `job_plan_articles`: job plan ID, article ID, component key, selection score/reason, source snapshot ID, revision ID, selected/rejected marker.
- `job_plan_operations`: job plan ID, stable operation ID, normalized semantic key, action, duration, components JSONB, dependencies JSONB, resource group, origin, evidence IDs JSONB, confidence, review state.
- `job_plan_results`: job plan ID, immutable result revision, labor JSONB, procedure JSONB, provenance JSONB, validation status, published timestamp, and result fingerprint.
- `source_access_records`: job plan ID, source snapshot ID, resource kind (`article_list`, `article`, `procedure`, `evidence`, or `other`), source URI/locator, normalization status, normalization version, and idempotency key. This is the durable audit that every successfully accessed source resource was processed by the ingestion boundary.
- `derived_articles`: a durable composed-article identity, generated article ID, canonical vehicle/configuration, title, current status, current fingerprint, and the creating job plan. It is separate from `catalog_articles` so a derived article never masquerades as an externally sourced article.
- `derived_article_revisions`: derived article ID, revision number, normalized body/steps, labor plan, procedure, source watermark, model/prompt/validator versions, immutable fingerprint, publication status, and published timestamp.
- `derived_article_lineage`: derived article revision ID, contributing catalog article ID, source snapshot ID, extraction evidence ID, lineage role, and source locator. Every composed article must be able to navigate back to all individual articles and evidence used to make it.
- Unique constraints prevent duplicate job plans for the same organization/idempotency key and duplicate result revisions for the same calculation fingerprint.
- Unique constraints prevent duplicate source-access records for the same plan, source snapshot, and locator, and duplicate derived revisions for the same derived article/fingerprint.
- Foreign keys link source-access, lineage, articles, and evidence to existing source/extraction records wherever identifiers are available. JSONB is used for structured derived content and plan snapshots, not to replace canonical article/provenance tables.

**Steps:**

- [ ] Add failing migration tests for table presence, enum/check constraints, unique idempotency key, result immutability, evidence linkage, and cascade behavior that preserves audit history.
- [ ] Add migration tests proving a source list and later article body are separately auditable, an exact replay does not create another normalized article, and a composed article has a new ID plus lineage to each source article/evidence record.
- [ ] Run the migration tests and observe the expected missing migration failure.
- [ ] Implement the migration with forward-only, idempotent statements matching repository migration conventions.
- [ ] Implement insert/read/replay persistence methods with transaction boundaries around source materialization, plan creation, derived-article revision creation, and result publication.
- [ ] Re-run migration and persistence tests; commit with `feat: persist multi-component job plans`.

## Task 9: Add the internal worker job-plan request path

**Files:**

- Modify `workers/ingestion-python/src/autodata_ingestion/http_service.py` to add `POST /v1/job-plans` and `GET /v1/job-plans/{id}` dispatch behavior.
- Modify `workers/ingestion-python/src/autodata_ingestion/worker.py` to orchestrate intent, vehicle resolution, selection, fallback, labor calculation, composition, validation, and persistence.
- Create `workers/ingestion-python/src/autodata_ingestion/job_plan_runtime.py` if orchestration would otherwise enlarge `worker.py` beyond its current boundaries.
- Create `workers/ingestion-python/tests/test_job_plan_http_service.py`.
- Create `workers/ingestion-python/tests/test_job_plan_runtime.py`.

**Implementation details:**

- `POST /v1/job-plans` requires an internal idempotency key and a vehicle selector or query that contains sufficient vehicle identity. It returns an existing result on an idempotency hit.
- The internal request handler accepts only bounded JSON and rejects unknown top-level fields, oversized input, unsupported technician count, and missing query.
- The runtime first checks the warm path using the plan fingerprint and source/model watermark. It invokes Mercury-2 only on a cold or invalidated path.
- Cache miss behavior reuses existing source fallback and article intake persistence, then materializes every source resource returned by the connector before selecting the component articles. It must not create duplicate source snapshots or duplicate normalized articles.
- When a component article body is accessed, persist that body even if another article is ultimately selected. When the source returns an article list, persist all list records in that response so future component searches are warm.
- After labor and procedure validation, persist the combined result as a new derived article/revision and add it to the searchable normalized index in the same publication transaction.
- Retryable network/provider errors raise a retryable worker error. Invalid user input, invalid model output after one bounded repair attempt, identity ambiguity, and evidence mismatch are permanent review outcomes.
- Publish result and status transition atomically with the outbox/event record. A duplicate delivery must be safe.

**Steps:**

- [ ] Write failing HTTP and runtime tests for validation, idempotency, warm hit, cold miss, source fallback, review outcome, retryable error, and duplicate delivery.
- [ ] Run the focused tests and observe the expected missing route/orchestrator failure.
- [ ] Implement dispatch and orchestration behind injected interfaces for source resolver, article selector, LLM client, calculator, composer, and persistence.
- [ ] Re-run tests and commit with `feat: orchestrate job plan fulfillment`.

## Task 10: Add Go API endpoints and authorization behavior

**Files:**

- Modify `apps/api-go/main.go` to register `POST /job-plans` and `GET /job-plans/{id}`.
- Create `apps/api-go/job_plans.go`.
- Modify `apps/api-go/ingestion_http.go` only to proxy the internal job-plan request path.
- Create or extend `apps/api-go/job_plans_test.go`.
- Update API contract/openapi documentation if the repository maintains a generated API description.

**Public API behavior:**

```text
POST /job-plans
GET  /job-plans/{id}
```

`POST /job-plans` accepts:

```json
{
  "query": "replace the alternator and starter",
  "vehicle": {
    "year": 1999,
    "make": "Chevrolet",
    "model": "Silverado 1500",
    "drivetrain": "2WD",
    "engine": "5.3L"
  },
  "options": {
    "technician_count": 1,
    "allow_source_fallback": true
  }
}
```

The response is `202` for processing, `200` for a warm ready/review result, and the existing structured error format for authentication, entitlement, invalid input, or unavailable ingestion. The API requires `dataset_viewer`, applies the same organization/entitlement boundary as dataset knowledge reads, and never exposes source content outside the purchaser’s permitted projection.

`GET /job-plans/{id}` returns section-level result status, labor calculation, procedure, source watermark, evidence references, review reasons, and result revision. A plan tied to a revoked entitlement returns `ENTITLEMENT_REVOKED` while preserving the internal audit record.

**Steps:**

- [ ] Add failing tests for unauthenticated, forbidden, missing/revoked entitlement, malformed body, missing idempotency key, warm `200`, cold `202`, `needs_review`, `failed`, and duplicate requests.
- [ ] Run `go test ./apps/api-go` and observe the expected missing handler/interface failures.
- [ ] Implement the handler, request validation, proxying, status mapping, and response-size bounds using current API conventions.
- [ ] Re-run Go tests and commit with `feat: expose job plan API`.

## Task 11: Add NATS subjects, retry, and dead-letter delivery

**Files:**

- Modify `packages/contracts/contract.json` and regenerate bindings only if Task 2 did not include all subjects.
- Create `workers/ingestion-python/src/autodata_ingestion/job_plan_consumer.py`.
- Create `workers/ingestion-python/tests/test_job_plan_consumer.py`.
- Modify `workers/enrichment-python/src/autodata_enrichment/outbox.py` if the existing allow-list must include job-plan event types.
- Add the job-plan stream/consumer configuration to `infra/compose/compose.yaml` and environment documentation, without placing credentials in files.

**Delivery rules:**

- Use `job.plan.requested` v1 for work requests, `job.plan.completed` v1 for validated results, `job.plan.failed` v1 for exhausted failures, and `job.plan.review.requested` v1 for durable review outcomes.
- Use an idempotency key derived from organization, canonical vehicle/configuration ID, normalized component set, query intent, source watermark, selector version, and model/prompt version.
- A successful or review-complete message is acknowledged only after the result/outbox transaction commits.
- Retry transient source, database, NATS, object-storage, and model transport failures with bounded exponential backoff.
- Dead-letter after the configured maximum delivery count with original event ID, plan ID, idempotency key, error class, and last attempt timestamp. Do not include secrets or full source documents in the dead-letter payload.
- Permanent validation/review outcomes are not retried indefinitely; they publish the review event once and acknowledge the original message.

**Steps:**

- [ ] Write failing tests for exact event envelope, idempotent duplicate, retryable error, permanent review, max delivery count, and secret-free dead-letter payload.
- [ ] Run the consumer tests and observe the expected missing consumer failure.
- [ ] Implement the JetStream consumer and dead-letter publisher using existing knowledge-fallback delivery patterns.
- [ ] Re-run tests and commit with `feat: add durable job plan delivery`.

## Task 12: Add the warm-path performance and consistency layer

**Files:**

- Create `workers/ingestion-python/src/autodata_ingestion/job_plan_cache.py` or keep the cache query inside the persistence boundary if no separate module is justified.
- Create `scripts/dev/job_plan_warm_path_benchmark.py`.
- Create `scripts/dev/test_job_plan_warm_path.py`.
- Extend `infra/compose/compose.yaml` only with configuration required to run the benchmark locally.

**Performance contract:**

- A warm request with the same canonical vehicle, normalized component set, source watermark, selector version, and model/prompt contract version must not call Mercury-2, refetch source content, or recalculate embeddings.
- The warm path may deterministically revalidate the persisted result and must return the stored result revision, derived article ID, and evidence IDs unchanged.
- A new source watermark invalidates only the affected selection/result fingerprint and creates a new result revision; prior revisions remain readable internally.
- The benchmark must count materialization writes, source-resource cache hits, derived-article cache hits, and duplicate-suppression decisions in addition to request, LLM, source-fetch, result-hit, and error counts.
- Measure p50/p95 from API request to structured JSON for warm and cold paths separately. The benchmark must report request count, LLM call count, source fetch count, result cache hit count, and error count.
- Use a deterministic fake Mercury-2 client and fake source connector in tests; live provider tests remain opt-in and require environment configuration.

**Steps:**

- [ ] Write failing tests that execute the same request twice and assert one cold calculation, zero second-call LLM/source calls, identical result/evidence, and a faster second response.
- [ ] Run the benchmark test and observe the expected missing cache/benchmark failure.
- [ ] Implement fingerprint lookup and warm-path short-circuiting.
- [ ] Re-run tests and commit with `perf: add job plan warm path`.

## Task 13: Add end-to-end local fixtures and operational documentation

**Files:**

- Create `scripts/dev/job_plan_smoke_test.py`.
- Create `workers/ingestion-python/tests/test_job_plan_end_to_end.py`.
- Modify `docs/architecture/contracts.md` or the appropriate current architecture document to link the new job-plan contracts and state transitions.
- Create `docs/architecture/job-planning.md` with the request sequence, labor formula, LLM safety boundary, review behavior, and troubleshooting commands.
- Modify `docs/github/operating-model.md` only if the repository’s current CI contract needs a job-plan-specific check.

**Smoke scenario:**

1. Load the deterministic Silverado article fixtures and source evidence into PostgreSQL/MinIO.
2. Resolve the natural-language query to the canonical vehicle and two components.
3. Select the alternator and starter articles without selecting duplicates.
4. Calculate 4.5 standalone hours, 0.75 overlap hours, and 3.75 total labor hours.
5. Compose a structured procedure whose shared battery step appears once and whose component-specific steps retain article/evidence links.
6. Assert that the article list and both accessed article bodies have durable source-access/materialization records, normalized article records, and evidence links.
7. Assert that the combined procedure has a new derived article ID, a searchable revision, and lineage to both source articles and all procedure evidence.
8. Repeat the same request and assert a warm result with no fake LLM/source calls and no duplicate normalized or derived article.
9. Inject a source timeout, retry it, then force the max delivery count and verify a secret-free dead-letter event.
10. Change one source watermark and verify a new immutable result revision and derived article revision while the prior result remains auditable.
11. Revoke entitlement and verify access is denied without deleting the internal job-plan/audit record.

**Steps:**

- [ ] Add the deterministic fake source, fake payment/entitlement setup, fake Mercury-2 response, and database/NATS/MinIO harness wiring.
- [ ] Run the smoke test against the local Compose stack and capture HTTP status, result JSON, operation totals, evidence IDs, retry count, dead-letter count, and warm-path call counts.
- [ ] Run all Go tests, all ingestion tests, all enrichment tests, migration validation, and contract generation checks.
- [ ] Commit the smoke harness and documentation with `test: verify multi-component job planning flow`.

## Task 14: Final review and delivery checks

**Files:**

- No new implementation files; review the changed paths from Tasks 1–13.

**Checks:**

- [ ] Run `git status --short` and confirm the user-provided `sample data/` directory remains unstaged and all other changes are intentional.
- [ ] Perform a placeholder-marker and internal-artifact-name scan over the changed documentation and implementation paths; remove any unresolved planning placeholders or accidental internal artifact names.
- [ ] Verify every job-plan status is defined in the canonical contract and used consistently by Go, Python, persistence, and documentation.
- [ ] Verify the fast/warm path never waits on deep-lane enrichment and a deep-lane failure cannot revoke a valid viewable revision.
- [ ] Verify every operation and procedure fact has evidence or an explicit derived/review marker.
- [ ] Verify all handlers have idempotency, retry, and dead-letter tests.
- [ ] Verify API section/readiness output includes job-plan status, labor result status, procedure status, source watermark, and review reasons.
- [ ] Verify entitlement, refund/revocation, source takedown, correction, and prior-revision audit behavior.
- [ ] Verify no secret appears in source, fixtures, logs, generated artifacts, commits, or dead-letter payloads.
- [ ] Run the complete local test matrix and record exact command output and exit codes.
- [ ] Review `git diff --stat` and `git diff --check`.
- [ ] Stage only intentional task paths, inspect `git diff --cached --name-only`, commit, push the completed implementation branch, and verify the remote SHA if the user authorizes implementation execution.

## Expected implementation outcome

The finished feature will let a caller submit one natural-language vehicle job, receive a deterministic and explainable combined labor estimate, and receive a structured procedure assembled from the best vehicle-specific single-component articles. It will be fast on repeated queries, safe when the source/model is uncertain, and auditable down to the source snapshot and evidence locator without turning the LLM into an unverified data authority.
