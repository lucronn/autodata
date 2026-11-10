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

**Files:** `apps/api-go/catalog_access_test.go`, `apps/api-go/postgres_catalog_access_test.go`, `apps/api-go/catalog_http.go`, `apps/api-go/catalog_access.go`, `apps/api-go/catalog_lifecycle.go` (only if a helper belongs there), and `apps/api-go/main.go` only if route wiring requires it.

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

- [ ] Run focused and full relevant Go/Node suites, `git diff --check`, and any repository policy checks; record exact head, skips, and limitations in the spec.
- [ ] Obtain a separate read-only AI review of the exact head; resolve Critical/Important findings. This is a repository review decision, never a GitHub approval.
- [ ] Push a PR linked to #393, wait for current required CI and live protection, then squash merge if all gates permit. Update Project #8 and close #393 only after the actual Workshop interaction is delivered; do not claim live paid-access acceptance while #391 remains blocked.

The `modern-web-guidance` forms and accessibility guides were checked before this UI plan. Their applicable requirements are to keep a visible label and a polite, debounced result announcement; no new framework or browser API is needed.
