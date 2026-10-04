# Plan: Complete the OpenAPI source and image contract

## Goal

Make Swagger accurately describe every public catalog, stored-source, and opaque-image route without documenting internal storage locators.

## Tracking

- **Issues:** https://github.com/lucronn/autodata/issues/113 and https://github.com/lucronn/autodata/issues/116
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-openapi-source-media-contract.md`
- **Canonical contracts:** `docs/architecture/provider-neutral-catalog-api.md`; `docs/architecture/opaque-source-media-paths.md`
- **Implementation PR:** #123 (stacked on #118 and #119)

## Evidence and decision

The public router registers stored source review and opaque image routes that the current OpenAPI spec does not list. The `Image` schema also exposes `storage_key`, an internal object-store locator, even though public Go JSON is being changed to omit it. Document both stored-source representations, the unauthenticated capability-token image path and its error responses, the rejected legacy route, and remove `storage_key` from both OpenAPI files.

## todo

1. Synchronize the plan and concrete work items to Issues #113 and #116 and Project #8.
2. Add complete OpenAPI paths/schemas for stored source JSON/HTML and opaque image binary responses; document legacy route rejection.
3. Remove the internal `storage_key` property from the public `Image` schema.
4. Add checks that route registrations and OpenAPI schemas stay aligned; validate JSON/YAML and run the full hosted fast lane on PR #123.

## Acceptance

- OpenAPI contains every `/v1/catalog` route registered by the API, including stored source and opaque images.
- Stored source documents the JSON and HTML representations and authentication behavior.
- Opaque image docs disclose no upstream URL parameter; legacy source-bearing requests are documented as rejected.
- Public image schema omits `storage_key` in both YAML and JSON.
