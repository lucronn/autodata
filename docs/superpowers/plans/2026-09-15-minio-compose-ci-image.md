# Plan: Restore the CI Compose MinIO image

## Goal

Make the required GitHub Compose verification runnable again after the
Docker Hub `minio/minio:latest` reference began returning a repository access
failure, without changing the application storage contract or committing any
credentials.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/88
- **Project:** https://github.com/users/lucronn/projects/8
- **Base SHA:** `c6e1145f4fd7f2d4227b790826963e9e6511c750`
- **Implementation scope:** `infra/compose/compose.yaml`, the Compose image
  regression test, and the canonical infrastructure documentation.

## Decision

Keep `AUTODATA_MINIO_IMAGE` as the deployment override, but change its local
and CI default to the verified stable MinIO release image hosted by Quay:
`quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z`. A release tag is used
instead of `latest` so a future registry change cannot silently alter the
development stack. The override remains available for provider-neutral
deployments and private registries.

The storage API, bucket names, health check, ports, credentials, and service
dependencies remain unchanged. No source data, output artifacts, or secret
values enter the commit.

## todo

1. Record the CI failure and this plan in Issue #88 and its Project #8 item.
2. Add the synchronized pre-implementation record at the pinned base SHA.
3. Add a regression test that rejects the unavailable Docker Hub default and
   requires the verified Quay release default while preserving the override.
4. Change only the Compose MinIO default and document the registry/tag
   decision in `docs/architecture/infrastructure-and-dev.md`.
5. Run the Compose config check, focused regression, local applicable suites,
   and the required GitHub verification workflow.
6. Reconcile Issue #88 and Project #8 only after the remote README branch is
   merged and the Wiki/readme state is verified again.

## Verification gates

- `docker compose ... config --quiet` succeeds with CI-safe environment
  values.
- The Compose image regression passes and confirms `AUTODATA_MINIO_IMAGE`
  still overrides the default.
- The existing local unit, contract, and runtime checks remain green.
- The required GitHub check passes on the exact PR head.
- The default `master` branch contains the refreshed README and canonical
  docs after merge; the four Wiki pages remain readable.

## Boundaries

This plan does not change MinIO data semantics, source ingestion behavior,
Kubernetes image policy, application code, credentials, or user-owned
untracked directories. It does not close Issue #85, whose remaining
acceptance is human technician review.
