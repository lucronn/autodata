# Plan: Keep image storage keys out of public article payloads

## Goal

Prevent normalized catalog responses from exposing internal object-storage keys while retaining the key for AutoData's internal image handling.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/116
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-public-image-storage-key.md`
- **Canonical contract:** `docs/architecture/opaque-source-media-paths.md`
- **Follow-up PR:** #118

## Evidence and decision

`CatalogImage.StorageKey` currently serializes as `storage_key` in public article JSON and is declared in OpenAPI. This reveals an internal storage locator and couples public clients to the backing store. Keep it available to internal Go code but exclude it from JSON serialization and the public schema. Preserve public `url` as the opaque same-origin image path.

## todo

1. Synchronize this plan and the work item to Issue #116 and Project #8.
2. Exclude `storage_key` from public image serialization and OpenAPI.
3. Add an endpoint regression with a populated internal storage key proving it is absent from responses.
4. Run Go tests/vet, developer contract tests, and hosted CI on PR #118 and descendants.

## Acceptance

- Public article/index JSON contains no `storage_key` or internal object key.
- Internal storage-key fields remain available to private server-side code.
- The OpenAPI `Image` schema documents only public fields.
