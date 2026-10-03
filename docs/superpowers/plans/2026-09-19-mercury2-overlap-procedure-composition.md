# Ephemeral Mercury-2 Multi-Component Composition Plan

**Goal:** Produce one useful unified response from persisted, normalized individual vehicle procedures without storing the combined result.

**Issue:** https://github.com/lucronn/autodata/issues/110  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/mercury2-procedure-composition.md`

## Scope and invariants

- Persist and reuse only individual source-backed articles and their normalized forms.
- Resolve from the normalized database first. Retrieve/ingest a missing individual article once, then compose from the newly persisted normalized record.
- Generate the multi-component procedure per request through the API/worker path. Never persist, review, or cache the composed output as an article or revision.
- Preserve original source content, normalized step order, source/evidence lineage, and locally stored images.
- Mercury-2 may unify equivalent overlapping work only when source operations support it; keep per-article order and expose conflicts/uncertainty rather than guessing.
- Provide deterministic non-empty fallback from available articles when the model is unavailable or invalid.
- Labor is outside this issue and must not participate in acceptance or block procedure delivery.

## Concrete todo

- [ ] Trace public composition request from API through worker, including normalized-article lookup, missing-article ingestion, and all persistence/cache calls.
- [ ] Remove combined-procedure storage, derived-article caching, and chat-specific dependencies from the active composition path.
- [ ] Compose from stored individual normalized article records; keep source order and validate source/evidence/image references and vehicle scope.
- [ ] Ensure a missing individual article follows the existing one-time source ingestion path and is reusable on a subsequent request.
- [ ] Return deterministic source-backed output on Mercury-2 failure/invalid output; return explicit errors only when required individual source data is unavailable.
- [ ] Add focused tests for cache-first reuse, one-time missing article ingestion, ephemeral output (no writes/cache), fallback, lineage, image references, and single/multi-article API behavior.
- [ ] Run worker/API/contract suites and a local public-API smoke where available; document exact results and any external dependency limitation.

## Execution tasks

### Task 1 — Trace and lock the active-path boundaries

Inspect the job-plan handler, catalog/article service, worker dispatch, Mercury composition, cache helpers, and persistence helpers. Add tests before implementation that demonstrate which active code writes a composed result or triggers repeat source calls.

### Task 2 — Keep composition ephemeral and source-first

Remove active-path reads/writes for cached or persisted derived procedures. Resolve selected normalized articles from the database; route only missing individual article detail through existing ingestion and commit that individual record before composition. Do not change catalog-list hydration into article-detail fan-out.

### Task 3 — Compose and fail safely

Pass only same-vehicle normalized source articles to Mercury-2. Validate output references against the supplied article/evidence/image records, preserve each source article's internal step order, and use deterministic source-backed composition on model failure. Do not add labor logic.

### Task 4 — Verify public behavior

Run focused tests, all ingestion worker tests, relevant Go API/contract tests, and a local API smoke if the configured stack is available. Verify that a repeated request makes no upstream detail call for already ingested records and that neither request creates a composed article/cache entry. Record test counts and blockers; update Issue #110 and Project #8 with evidence.

## Exclusions

Persistent combined articles/revisions; combined-result review; combined-result caching; dashboard chatbot delivery; labor/quote handling; changing the normalized individual article order; bulk fetching every catalog article's full content.
