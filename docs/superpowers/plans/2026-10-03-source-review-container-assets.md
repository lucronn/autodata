# Plan: Package Workshop assets in the source-review API image

## Goal

Make the source-review API Docker image build in a clean hosted runner by
including the Workshop files embedded by the Go API binary.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/114
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-source-review-container-assets.md`
- **Canonical contract:** `docs/architecture/catalog-source-review.md`
- **Implementation PR:** #119
- **Planning base SHA:** `50d2feaf03ada1c5d1659d2c9c1340389835564d`

## Evidence and decision

The source-review API added `//go:embed dashboard/* workshop/*` to
`apps/api-go/main.go`, but `apps/api-go/Dockerfile` copies only `dashboard/`
into its build stage. A clean GitHub Compose run fails at Go compilation with
`pattern workshop/*: no matching files found`. Local cached build layers hid
the packaging error. Copy the Workshop directory beside the dashboard in the
builder stage; keep the final image and runtime contract unchanged.

## todo

1. Synchronize this plan and the work item to Issue #114 and Project #8.
2. Copy `apps/api-go/workshop/` into the Go Docker build stage.
3. Build the API image with a clean cache and run Go tests/vet.
4. Re-run the complete GitHub Compose fast lane for PR #119 and the stacked
   descendants, then record exact-SHA evidence.

## Acceptance

- A clean `docker build --no-cache -f apps/api-go/Dockerfile .` succeeds.
- Go tests and `go vet` pass.
- Hosted Compose smoke reaches its semantic checks on the current PR head.
- The fix stays in the source-review PR that introduced the embedded Workshop
  asset reference.
