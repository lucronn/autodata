# Plan: Restore hosted Compose verification with a pullable S3 image

## Goal

Remove the shared GitHub Actions blocker preventing the open catalog/procedure
pull requests from reaching their application checks. Use an actively published,
publicly pullable S3-compatible image for the CI fast lane while preserving the
existing local MinIO service, its disk format, and developer data.

## Tracking

- **Issue:** https://github.com/lucronn/autodata/issues/111
- **Project:** https://github.com/users/lucronn/projects/8
- **Plan:** `docs/superpowers/plans/2026-10-03-ci-s3-image-access.md`
- **Canonical documentation:** `docs/architecture/infrastructure-and-dev.md`
- **Planning base SHA:** `81685a5debe64aaaa50ecd4b2f490b586de010cf`
- **Implementation branch:** `phobos/provider-neutral-catalog-workshop` (PR #117)

## Evidence and decision

The live GitHub Actions failure occurs before application tests: pulling
`quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z` returns `unauthorized`.
The old Compose image plan points at unrelated, already-closed Issue #88 and
its old registry-access assumption is no longer valid.

Keep the default local MinIO service unchanged. Use a CI-only Compose override
with the public SeaweedFS single-process S3 service, pinned to the verified
multi-platform image index
`docker.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`.
Its upstream documents the single-process S3 endpoint, environment-based
credentials and bucket creation. The image was pulled successfully, its S3
endpoint became healthy, and the existing Python MinIO SDK successfully listed
the bucket, uploaded, downloaded, and deleted an object using the configured
credentials. This is a development/CI implementation of the existing S3
contract; the override uses a distinct temporary volume and does not read,
replace, or delete the local MinIO volume. The local developer and production
object-store configurations remain unchanged.

## todo

1. Synchronize this plan and its concrete work items to Issue #111 and Project #8.
2. Add a CI-only Compose override using the pinned SeaweedFS image, compatible
   credentials, matching internal S3 port, health check, and an isolated volume.
3. Update the CI startup command, regression tests, and canonical docs; leave
   the local MinIO service, application defaults, developer scripts, and its
   persistent volume unchanged.
4. Run merged Compose config validation and the complete CI-shaped S3-backed
   ingestion smoke using the override.
5. Push the base-PR update, rerun the exact GitHub verification checks for all
   seven stacked PRs, and synchronize evidence to Issue #111 and Project #8.

## Acceptance

- The pinned image manifest is publicly pullable without registry credentials.
- The existing MinIO Python SDK and Go S3 client can write and read objects.
- The CI override's health check waits for the S3 service before application tests.
- The existing ingestion fast-lane smoke passes against a clean data volume.
- GitHub Actions passes on the exact current heads of PRs #117-#123.
- Local MinIO configuration, format, data volume, and production storage remain unchanged.
