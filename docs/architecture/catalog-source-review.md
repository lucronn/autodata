# Catalog source review

**Goal:** Provide a trustworthy comparison path from a normalized catalog article to the immutable provider snapshot stored during ingestion.

**Issue:** https://github.com/lucronn/autodata/issues/114

**Project:** https://github.com/users/lucronn/projects/8

## Contract

The article detail response may expose a `source_review` object containing:

- `available`: whether an immutable source snapshot exists;
- `snapshot_id`: the stored source snapshot identifier;
- `version`: the source adapter/version label;
- `content_sha256`: the stored content hash;
- `format`: `html` or `json`; and
- `url`: a same-origin AutoData URL for the stored source.

The response does not expose `source_original`, the recorded provider URI, object-storage keys, or credentials. It may contain same-origin opaque image URLs backed only by already-localized objects. The image endpoint never proxies/fetches a provider during display. The source URL reads the stored `catalog_articles.source_original` record and does not hydrate or refetch an external provider. Source images unavailable as local objects are omitted rather than fetched remotely.

`GET /v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source` has two representations:

- `Accept: application/json` returns the source metadata and sanitized source content for the Workshop comparison frame.
- Browser navigation (`Accept: text/html`) returns a CSP-protected review document containing the same sanitized content and stored-source metadata.

For stored AutoAPItwo HTML, source-relative `img` URLs resolve against the recorded snapshot URI and route through the opaque `/v1/catalog/images/{token}` endpoint. The sanitizer uses the configured image-reference key to generate authenticated randomized path tokens; it never emits the legacy `?src=` route or a provider URL in source-review content. Inline `data:image` sources and images that cannot be represented by valid opaque tokens are removed; image sources fail closed when the key is unavailable. Scripts, forms, frames, plugin elements, event-handler attributes, base tags, external links, and provider navigation are removed or neutralized. Source tables, headings, paragraphs, lists, and images remain in source order.

The Workshop loads source content only when the reviewer opens the source panel. Normalized document blocks that retain `evidence_ids` or `source_locator` receive a stable same-origin `Source` link to the source review URL with the relevant reference in its query string. The normalized article remains the main display and its order is unchanged.

## Todo

- [x] Add a provider-neutral catalog store source read and safe public metadata.
- [x] Add the same-origin sanitized source endpoint with JSON and browser representations.
- [x] Add on-demand Workshop source comparison and block-level source links.
- [x] Verify live Ram article source rendering, image proxying, and provider URL isolation.

## Boundaries

Source review is for comparison and traceability. It does not rewrite normalized content, reorder blocks, create a combined procedure, or make a new provider call.

## Container packaging

The API binary embeds both `dashboard/` and `workshop/` at compile time. The
API Docker build stage must copy both directories before `go build`; a clean
container build is the packaging check for this same-origin UI contract. The
source-review follow-up and its hosted-runner evidence are tracked in Issue
#114 and `docs/superpowers/plans/2026-10-03-source-review-container-assets.md`.

## Verification evidence

The implementation passed `go test ./...`, `go vet ./...`, `node --test workshop-client.test.mjs` (14 tests), and `git diff --check`. The local Compose API was rebuilt and restarted. A live authenticated Ram 1500 DS axle article request returned safe source metadata and a same-origin source URL; its on-demand source response rendered the stored HTML and image through AutoData routes, with scripts removed and CSP applied. The Workshop rendered the stored source copy beside the normalized article and exposed the evidence-bearing source reference.


## Opaque source-image follow-up

The source-review sanitizer must remain compatible with the opaque media contract in `docs/superpowers/plans/2026-10-03-opaque-source-media-paths.md`. Its follow-up is tracked in Issue #114 and Project #8, with the plan at `docs/superpowers/plans/2026-10-03-source-review-opaque-images.md`.

Follow-up goal: make source-image rendering compatible with opaque media tokens.
Track it on [Issue #114](https://github.com/lucronn/autodata/issues/114) and
[Project #8](https://github.com/users/lucronn/projects/8); see
`docs/superpowers/plans/2026-10-03-source-review-opaque-images.md`.

Follow-up todo:

- Generate opaque image path tokens for sanitized stored-source images.
- Fail closed when the configured image-reference key is unavailable.
- Test JSON and HTML source responses for provider-path leakage and verify that
  opaque tokens are accepted by the image endpoint.
- Run Go tests/vet and hosted Compose verification on PR #119 and descendants.
