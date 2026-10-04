# Catalog Source Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let a reviewer open the exact stored provider snapshot alongside a normalized article, with stable source references and no live provider navigation.

**Architecture:** The catalog store will expose an internal source-content read for an already stored article. The Go API will add safe source metadata to the normal article response and a same-origin source endpoint that returns sanitized/renderable HTML or JSON from `source_original`; it will never refetch a provider. The Workshop will show an on-demand stored-source panel and attach source links to normalized blocks that carry evidence or a source locator.

**Tech Stack:** Go 1.26, `pgx/v5`, `golang.org/x/net/html`, embedded vanilla HTML/CSS/ES modules, Go and Node test suites.

**Spec:** `docs/architecture/catalog-source-review.md`

**Issue:** https://github.com/lucronn/autodata/issues/114

**Project:** https://github.com/users/lucronn/projects/8

## To-do

- [x] Read only the immutable source snapshot and publish safe metadata.
- [x] Sanitize stored source HTML/JSON and localize source image references.
- [x] Add an on-demand Workshop comparison panel and block-level source links.
- [ ] Verify the source comparison against a freshly rebuilt local stack and current browser data.

## Global Constraints

- Raw provider snapshots remain server-side; the public article response exposes only stable source metadata and same-origin URLs. Public image URLs use randomized opaque tokens and never expose source paths.
- Source review reads `catalog_articles.source_original` and must never call AutoAPI or AutoAPItwo.
- Normalized block order, normalized wording, local illustration URLs, and existing catalog hydration behavior remain unchanged.
- Source HTML is sanitized, provider image URLs are rewritten through the opaque same-origin image route, and scripts/forms/external navigation are disabled.
- Source review is loaded on demand so opening an article does not add a second large source payload to the article request.

## Review Focus

- A complete article with HTML in `source_original` returns a rendered source copy and stable metadata; a missing raw snapshot returns an explicit unavailable response.
- A catalog-row alias and a hydrated provider article resolve the same stored source without triggering hydration or an upstream request.
- Relative provider image URLs in source HTML resolve to opaque same-origin image paths; original provider URLs do not appear in the rendered page or normal article JSON.
- Dangerous HTML elements, event attributes, external links, and base tags are removed or neutralized while tables, headings, paragraphs, and images remain readable.
- A source endpoint requested by a browser renders review HTML, while the Workshop JSON fetch receives the same content and can display it in a sandboxed frame.

### Task 1: Add the source-review contract and store boundary

**Files:**
- Create: `docs/architecture/catalog-source-review.md`
- Modify: `apps/api-go/catalog_store.go`
- Test: `apps/api-go/catalog_test.go`

**Interfaces:**
- Produces `CatalogSourceReview`, `CatalogSourceContent`, and `CatalogStore.ArticleSource(context.Context, Principal, string, string)` for the API handler.
- Keeps raw source bytes on the internal result only; public article JSON receives metadata through `CatalogSourceReview`.

- [x] Write tests for memory-store source lookup, alias lookup, missing-source behavior, and safe metadata on article detail.
- [x] Run the focused Go catalog tests against the implemented store contract.
- [x] Add source metadata fields to the internal article record, implement `ArticleSource` for memory and PostgreSQL stores, and populate snapshot ID/version/hash/URI from the joined `source_snapshots` row.
- [x] Add the new source-review architecture contract and exact issue/project references.
- [x] Run the focused Go tests and verify the store contract passes.

### Task 2: Serve sanitized stored source content through the API

**Files:**
- Create: `apps/api-go/catalog_source.go`
- Modify: `apps/api-go/catalog_http.go`
- Modify: `apps/api-go/main.go`
- Test: `apps/api-go/catalog_test.go`
- Modify: `apps/api-go/go.mod`
- Modify: `apps/api-go/go.sum`

**Interfaces:**
- Adds `GET /v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source` under `dataset_viewer`.
- Returns JSON for `Accept: application/json` and review HTML for browser navigation; both are derived only from the stored snapshot.

- [x] Add failing tests for HTML extraction, relative-image proxying, dangerous-element removal, JSON response shape, browser HTML response, and no upstream calls.
- [x] Run the focused Go tests against the implemented source renderer.
- [x] Implement `renderStoredCatalogSource` with `golang.org/x/net/html`, preserving readable source structure, removing executable/navigation elements, and rewriting provider-host images to same-origin proxy URLs.
- [x] Register the route and add source metadata/link construction to `getCatalogArticle`.
- [x] Run focused Go tests, `go vet`, and API build checks.

### Task 3: Render source review and block references in Workshop

**Files:**
- Modify: `apps/api-go/workshop/index.html`
- Modify: `apps/api-go/workshop/app.mjs`
- Modify: `apps/api-go/workshop/styles.css`
- Test: `apps/api-go/workshop-client.test.mjs`
- Test: `apps/api-go/workshop_test.go`

**Interfaces:**
- Uses `article.source_review.url` as the only source link.
- Fetches that URL with JSON accept headers only when the reviewer expands the source panel; displays returned HTML in a sandboxed iframe.

- [x] Add client tests for source-reference URL construction and block evidence link eligibility.
- [x] Run Node client tests against the implemented source-reference helpers.
- [x] Add an on-demand stored-source panel with metadata, a same-origin open link, and a sandboxed comparison frame; add compact `Source` links to evidence-bearing normalized blocks.
- [x] Add accessible styling for source metadata, frame, and block reference links without changing document order or article content.
- [x] Run Node and Go Workshop tests and verify the embedded assets contain the new controls.

### Task 4: Verify live stored-source review

**Files:**
- Modify: `docs/superpowers/plans/2026-09-30-catalog-source-review.md`
- Modify: `docs/architecture/catalog-source-review.md`

- [x] Rebuild/restart the local API using the existing Compose workflow.
- [x] Request the live Ram 1500 DS axle article and confirm the article response contains only safe source metadata plus a same-origin source URL.
- [ ] Request the source URL with JSON and browser HTML accepts; confirm the stored source renders, source images use opaque `/v1/catalog/images/{token}` paths, and no provider URL or script is exposed.
- [ ] Open the Workshop article in the browser and confirm the source panel and block reference links work.
- [x] Record test and live evidence in the plan and architecture document.

## Verification evidence

- `go test ./...` passed in `apps/api-go`.
- `node --test workshop-client.test.mjs` passed: 14 tests.
- `go vet ./...` passed in `apps/api-go`; `git diff --check` passed.
- Local Compose API rebuilt and restarted; authenticated `GET /readyz` remained ready.
- Authenticated live article request for the Ram 1500 DS axle article returned `source_review.available=true`, snapshot `4ee4818c-bd55-5ade-af9e-802e7e687dd6`, format `html`, and a same-origin source URL. The public article JSON did not contain `source_original` or `source_uri`.
- Previous local runtime evidence is recorded above for the stored article source endpoint; re-run after the dependent catalog and opaque-media changes are integrated.
