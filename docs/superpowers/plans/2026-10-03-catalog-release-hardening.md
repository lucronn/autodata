# Catalog release hardening

**Issues:** https://github.com/lucronn/autodata/issues/112, https://github.com/lucronn/autodata/issues/113, https://github.com/lucronn/autodata/issues/114, https://github.com/lucronn/autodata/issues/116  
**Project:** https://github.com/users/lucronn/projects/8  
**Candidate base:** `d7bf5db7ad2a11d14a5cec2d25ace7fa8460c7a3`  
**Canonical contracts:** `docs/architecture/provider-neutral-catalog-api.md`, `docs/architecture/catalog-source-review.md`, `docs/architecture/opaque-source-media-paths.md`

## Goal

Complete the existing catalog issue stack without a development-only identity boundary, unsafe stored-source JSON projection, or provider-dependent article illustrations. Keep the provider-neutral catalog, Workshop, source review, and fixed-order procedure behavior.

## Decisions

1. The normal API process uses a verified service-key authenticator. It reads a secret-managed set of SHA-256 key digests, subjects, organization IDs, roles, and expiration timestamps. It compares a presented bearer key in constant time and rejects unknown, expired, or malformed identities. The unsigned `local:` authenticator is permitted only in an explicitly selected local-development mode. Normal startup fails closed when service authentication is unconfigured. The local Compose API port binds to loopback.
2. Catalog articles are global normalized records; the authenticated catalog role controls reads. This task does not change the catalog's global ownership model. Public image links remain opaque bearer capabilities as documented by Issue #116; no provider path or internal object key appears in a public payload.
3. Ingested article images are served from AutoData object storage. The public image token names a locally stored asset, not a provider URL. The API resolves the asset through its own storage boundary. Missing objects are explicit unavailable images; they are not fetched from AutoAPItwo while rendering. Source-review images use the same localized asset mapping or are omitted when no safe local asset exists.
4. Stored-source JSON is a review projection. It preserves safe content but removes credentials, request headers, signed references, and navigation to external providers recursively. The immutable original stays server-side. HTML and JSON responses share the same source-image and redaction rules.
5. OpenAPI JSON and YAML describe the actual authenticated routes and use a syntactically valid opaque-token example. Both formats must agree with endpoint behavior.

## Concrete todo

- [ ] For Issue #113, add verified service-key authentication for the normal Go API startup, explicitly confine `local:` tokens to local development, configure secret delivery, and cover forged/expired/missing-key negative cases.
- [ ] For Issue #112, read stored article images from AutoData object storage through opaque references and eliminate provider network fetches from the public image path; verify stored-source images and warm replay.
- [ ] For Issue #114, redact unsafe stored-source JSON fields and signed URLs, preserve immutable originals, and add synthetic-secret and source-image regressions.
- [ ] For Issue #116, align OpenAPI JSON/YAML with image and source behavior, omit storage keys and invalid image examples, and verify public responses reveal no provider paths.
- [ ] Build the clean API image, run focused Go/Python/Workshop checks and the hosted verification workflow on the final implementation SHA.
- [ ] Run a fresh-stack browser/API acceptance matrix for representative source-backed vehicles, including image HTTP 200 responses and negative cases; record exact SHA and review evidence before release.

## Implementation boundaries

- Go API identity and startup: `apps/api-go/requests.go`, `apps/api-go/main.go`, startup tests, Compose/Kubernetes configuration.
- Localized media: image persistence/projection and `apps/api-go/catalog_http.go`, catalog store/object-storage interfaces, plus focused image tests.
- Stored source: `apps/api-go/catalog_source.go` and source-review tests.
- Contract: `apps/api-go/openapi.json`, `apps/api-go/openapi.yaml`, and their validation tests.

All implementation agents must run `scripts/autonomy/pre_implementation.py` against the synchronized record and pinned planning checkpoint before editing implementation files. Independent security and data-quality review, required runtime acceptance, and the release controller's exact-SHA gates remain necessary before merge.
