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

- [ ] Trace object-store configuration and permissions; implement API read access to the existing bucket using the repository's established S3-compatible configuration.
- [ ] Change the opaque token payload from provider URL to a validated local object key; preserve randomized authentication and key rotation/configuration behavior.
- [ ] Keep internal storage keys available after catalog persistence/decode while excluding them from public JSON and source-review output.
- [ ] Rewrite article and sanitized stored-source image URLs to opaque object-backed paths; remove provider-fetch fallback and legacy query path.
- [ ] Align JSON/YAML OpenAPI schemas, routes, security, errors, and examples with runtime behavior; remove `storage_key`.
- [ ] Add regression tests for localized reads, missing objects/configuration, token tampering, provider-request non-occurrence, public-key/source-path redaction, and source-review HTML/JSON behavior.
- [ ] Run focused Go and Python tests, full relevant suites, compose/config checks, and a cold/warm local integration using representative articles; record exact results and commit SHA.

## Acceptance

An authenticated article response has usable opaque image URLs and no provider URL or `storage_key`; fetching an image reads its already-local object and causes zero provider requests. Stored-source HTML follows the same rule. Missing or invalid local assets fail closed without leaking paths. Tests and API schema validation pass, and GitHub Issues #112/#116 and Project #8 point to this plan and the same todo.
