# Localized Opaque Catalog Images

**Issues:** [#112](https://github.com/lucronn/autodata/issues/112), [#116](https://github.com/lucronn/autodata/issues/116)  
**Project:** [AutoData Portfolio Project #8](https://github.com/users/lucronn/projects/8)  
**Canonical contracts:** `docs/architecture/normalized-article-document.md`, `docs/architecture/opaque-source-media-paths.md`, `docs/architecture/catalog-source-review.md`

## Goal

Serve catalog and stored-source images only from AutoData-controlled object storage. Public responses use opaque same-origin URLs and never expose provider URLs or object keys. Image display must not make provider requests. Preserve source order and image placement; images that cannot be localized are represented as unavailable rather than fetched later from their source.

## Design decisions

- Ingestion owns provider fetching and writes validated image bytes to the configured object store.
- The normalized image record retains its object key internally. Public `CatalogImage` JSON contains only safe descriptive metadata and an opaque URL.
- The opaque token is authenticated and randomized, and resolves only to a validated local object key; it never contains or resolves to an upstream URL.
- The API image handler reads the configured object store and fails closed when configuration, token, object, or media validation fails. It does not issue HTTP requests to providers.
- Stored-source HTML uses the same opaque local-asset route. If a source image was not materialized locally, source review omits it rather than proxying it.
- OpenAPI JSON and YAML describe the actual article, stored-source, and image routes, with no `storage_key` property and valid examples.

## Concrete todo

- [x] Trace object-store configuration and permissions; implement API read access to the existing bucket using the repository's established S3-compatible configuration.
- [x] Change the opaque token payload from provider URL to a validated local object key; preserve randomized authentication and key rotation/configuration behavior.
- [x] Keep internal storage keys available after catalog persistence/decode while excluding them from public JSON and source-review output.
- [x] Rewrite article and sanitized stored-source image URLs to opaque object-backed paths; remove provider-fetch fallback and legacy query path.
- [x] Align JSON/YAML OpenAPI schemas, routes, security, errors, and examples with runtime behavior; remove `storage_key`.
- [x] Add regression tests for localized reads, token tampering, provider-request non-occurrence, public-key/source-path redaction, and source-review HTML/JSON behavior.
- [x] Run focused Go and Python tests, Compose/Kubernetes config checks, and a cold/warm image API integration against a locally signed S3-compatible test server.
- [ ] Verify the running release-candidate catalog stack with its stable image-reference key configured and a representative stored image; this environment currently has no stable key configured and correctly omits unusable image URLs.

## Verification evidence (2026-10-04)

- `go test ./...` and `go vet ./...` in `apps/api-go`: passed.
- `PYTHONPATH=src python3 -m pytest -q tests/test_procedure_images.py tests/test_object_storage.py`: 14 passed.
- `python3 scripts/dev/test_k8s_manifests.py` and `python3 scripts/dev/test_compose_images.py`: 8 passed.
- `docker build -f apps/api-go/Dockerfile -t autodata-api-112-116:verify .`: passed.
- OpenAPI YAML and JSON parse to identical documents; `git diff --check`: passed.
- Go integration test exercised a signed MinIO-S3-compatible object read plus cold/warm API requests; the fake object store observed no external provider requests.
- Live release-candidate stack does not configure `AUTODATA_IMAGE_URL_KEY` (nor an image-reference fallback), so a live stored-object URL fetch is not yet verifiable there; URLs fail closed rather than exposing provider paths.

## Acceptance

An authenticated article response has usable opaque image URLs and no provider URL or `storage_key`; fetching an image reads its already-local object and causes zero provider requests. Stored-source HTML follows the same rule. Missing or invalid local assets fail closed without leaking paths. Tests and API schema validation pass, and GitHub Issues #112/#116 and Project #8 point to this plan and the same todo.
