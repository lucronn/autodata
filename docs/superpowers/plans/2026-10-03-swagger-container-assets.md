# Plan: Package OpenAPI and Swagger assets in the API image

## Goal

Make the provider-neutral API Docker image build from a clean context with the
embedded Swagger contract and UI assets introduced by PR #123.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/113
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-swagger-container-assets.md`
- **Canonical contract:** `docs/architecture/provider-neutral-catalog-api.md`
- **Implementation PR:** #123
- **Planning base SHA:** `9c697ed662df84987c2c127499761d1ed31ce9dc`

## Evidence and decision

PR #123 changes `main.go` to embed `dashboard/*`, `workshop/*`,
`openapi.yaml`, `openapi.json`, `swagger.html`, and `swagger-ui/*`. The current
API Dockerfile copies only `dashboard/` and `workshop/`, so a clean hosted
build fails with `pattern openapi.json: no matching files found`. Copy the
OpenAPI files, Swagger HTML, and Swagger UI directory into the Go build stage.

## todo

1. Synchronize this plan and work item to Issue #113 and Project #8.
2. Copy all root OpenAPI/Swagger embed assets into the API Docker build stage.
3. Add a regression assertion for every embedded asset and build the image
   with a clean cache.
4. Run Go tests/vet and pass the hosted Compose fast lane on PR #123.

## Acceptance

- No `go:embed` pattern used by `main.go` is missing from the API Docker build
  context.
- A clean no-cache image build and Go tests/vet pass.
- Hosted Compose verification passes on the exact current PR #123 head.
