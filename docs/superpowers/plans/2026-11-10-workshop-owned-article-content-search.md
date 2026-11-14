# Workshop Owned-Article Content Search Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the consumer Workshop search box find terms inside readable articles after the current selected-configuration grant check, without placing article content in the paid index response.

**Implementation boundary:** Extend the existing protected article-index GET route with an optional `q` parameter. Keep its current response envelope and metadata-only item contract. For paid mode, select current eligible projections for the exact configuration in one streamed store query; compare bounded query words against article metadata and rendered document text, falling back to body/steps only where there is no rendered document. Return descriptors, not content. Use a separate abortable, debounced search request in the Workshop screen; preserve the existing unfiltered index polling and article-opening flow. No schema, entitlement, or payment changes.

**Tech stack:** Go API and catalog store, browser ES modules, Node Workshop client tests, existing Postgres fixture tests.

**Spec:** `docs/verification/2026-11-10-workshop-owned-article-content-search.md`.

**Project:** https://github.com/users/lucronn/projects/8

## Concrete todo

- [x] Prove the paid API access/content boundary with red-first tests and implement bounded server-side search (isolated Postgres fixture execution remains a CI gate).
- [x] Wire the real Workshop search interaction with abortable, debounced requests and test stale/incomplete states.
- [ ] Run exact-head verification, independent review, current CI, and branch protection before integration.
- [ ] Align the guarded paid-access fixture's exact assertion and HTTP-observation inventories with the new search probes; offline parser tests pass, but the guarded twelve-case runtime must still confirm the actual receipts.
- [x] Keep JSON/YAML OpenAPI variants in sync and test their semantic equivalence.
- [x] Resolve the content-search visible-text fallback discrepancy found in exact-head review with a red-first Go regression test.

## Constraints

- Issue [#393](https://github.com/lucronn/autodata/issues/393) and Project #8 are the canonical tracking scope; the public origin 502 is separate Issue #391.
- No content-bearing field is added to the unfiltered or searched paid descriptor response. No client-side fetch-all of paid article details.
- Use `catalogProtected` so the same exact configuration grant check runs before any content query. Preserve current lifecycle and source-rights predicates from `PaidArticleDescriptors`.
- Query validation: trim, maximum 120 Unicode code points, maximum eight whitespace-separated words; reject invalid nonempty query with 422. Match all words case-insensitively across visible fields. Search results are not ranked in this slice and preserve index order.
- A nonempty document's rendered blocks are authoritative over compatibility body/steps. Search the fields rendered by `renderBlocks`; do not index IDs, locators, hidden labels, image URLs, or source metadata. Use body/steps only when no document blocks are available.
- Keep `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff` on paid responses. Do not log queries or return snippets.
- Limit in-flight browser requests with a 300 ms debounce and a separate `NavigationGeneration`; clear search state on protected-state reset and selected-vehicle change. Pending search is visibly distinct from zero matches; stale or aborted responses cannot replace current results.
- Keep exact-head preflight, red-green tests, independent read-only review, current required CI, and live branch protection as integration gates. No production deployment.

## Tasks

### Task 1: Prove the API access and content boundary

**Files:** `apps/api-go/catalog_access_test.go`, `apps/api-go/postgres_catalog_access_test.go`, `apps/api-go/catalog_http.go`, `apps/api-go/catalog_access.go`, `apps/api-go/catalog_search.go`, `apps/api-go/catalog_search_test.go`, `apps/api-go/openapi.json`, and `scripts/contracts/test_catalog_lifecycle_contract.py`. No route rewiring or schema change is needed.

- [x] Add failing tests to the existing protected article-index handler for `q` matching content-only text after a valid grant, preserving metadata-only output, and denying wrong-configuration/unpurchased/revoked access.
- [x] Add store/fixture tests for current source/canonical revision selection and lifecycle exclusion; ensure a hidden document label alone cannot match. The isolated Postgres fixture cannot run in this local checkout and remains required CI evidence.
- [x] Implement bounded `q` parsing and a paid-store search method that streams current eligible projection rows for the selected configuration, searches only visible fields, and emits existing descriptor shape.
- [x] Run focused and full local Go tests. Do not expand the grant or checkout contract.

### Task 2: Wire actual Workshop search interaction

**Files:** `apps/api-go/workshop/app.mjs`, `apps/api-go/workshop-client.test.mjs`, and `apps/api-go/workshop/catalog.mjs` only if a pure helper is needed.

- [x] Add red-first actual-flow tests: content-only term makes one protected search request and displays the server match; a later query suppresses stale results; incomplete index does not claim a definitive no-match. The request also guards selected-vehicle changes.
- [x] On nonempty search, debounce a request to the existing index route with `q`; abort superseded requests without aborting the article-index polling generation. Keep metadata-only local filtering only for the empty-query case and preserve article links.
- [x] Announce the settled result count/status politely without per-keystroke live-region noise. Retain the visible label, keyboard operation, and existing error boundary.
- [x] Run Workshop Node tests. The live Workshop origin is 502 (Issue #391), so browser acceptance waits for a healthy origin.

### Task 3: Verify and integrate

- [x] First repair the exact paid fixture evidence contract. The search probes add three named assertions and four HTTP observations to the six-root/two-provider fixture. Failing inventory tests preceded updates to `scripts/dev/workshop_paid_access_smoke.py`, `scripts/dev/release_acceptance.py`, and their focused tests. `workers/ingestion-python/tests/test_paid_catalog_api_integration.py` consumes the smoke collector's literal map; no duplicate map is needed. The release parser retains its independent literal inventory and strict paths, status/counter sequences, positional body checks, and totals. The isolated guarded runtime remains the next gate.
- [x] Keep both embedded API descriptions equivalent by adding the bounded `q` query and grant/metadata-only description to `apps/api-go/openapi.yaml`; the contract test rejects JSON/YAML drift.
- [x] Resolve the renderer/search fallback mismatch: when there is no rendered document but usable steps exist, match the rendered steps rather than hidden compatibility body. The red-first case passed after retaining body fallback only where it is displayed.
- [ ] Run the guarded twelve-case isolated Postgres fixture on the exact candidate if the authorized runtime is available; otherwise explicitly retain this as a merge blocker. Ordinary CI and Go unit tests do not substitute for it.
- [ ] Run focused and full relevant Go/Node suites, `git diff --check`, and any repository policy checks; record exact head, skips, and limitations in the spec.
- [ ] Obtain a separate read-only AI review of the exact head; resolve Critical/Important findings. This is a repository review decision, never a GitHub approval.
- [ ] Push a PR linked to #393, wait for current required CI and live protection, then squash merge if all gates permit. Update Project #8 and close #393 only after the actual Workshop interaction is delivered; do not claim live paid-access acceptance while #391 remains blocked.

The `modern-web-guidance` forms and accessibility guides were checked before this UI plan. Their applicable requirements are to keep a visible label and a polite, debounced result announcement; no new framework or browser API is needed.
