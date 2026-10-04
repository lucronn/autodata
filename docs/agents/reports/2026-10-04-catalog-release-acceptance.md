# Catalog release acceptance report

**Candidate:** `34d1b129f9f8e4e619b23ddce18761bdc61ee4d9` on `phobos/complete-catalog-release`.
**PR:** https://github.com/lucronn/autodata/pull/125 (draft)
**Project:** https://github.com/users/lucronn/projects/8
**Decision:** do not merge or close Issues #110–#116; procedure/runtime and hosted release gates remain incomplete.

## Completed in this candidate

- Added authenticated `POST /v1/catalog/vehicles/{vehicle_id}/compositions`; the path vehicle is canonical, body accepts only a non-empty query, and `Idempotency-Key` is required.
- Routed through the existing Go-to-ingestion job-plan boundary and documented the operation in OpenAPI JSON/YAML.
- Added response projection that strips provider URLs, object keys, source snapshots, and internal visual metadata; localized image storage keys become opaque same-origin image paths.
- Added provider-host-scoped Vercel protection-bypass header configuration for the ingestion worker, with Compose/Kubernetes secret references. Vercel Deployment Protection was not disabled.

## Verification

- Go API: `go test ./... -count=1` and `go vet ./...` passed.
- Ingestion worker: `568 passed, 3 skipped, 27 subtests passed`.
- Kubernetes manifest and Compose image contracts: 9 tests passed; Compose config validation passed with synthetic local-only values.
- `git diff --check` passed.
- In the isolated ingestion container, an authenticated request to the current protected AutoDBone deployment's `/v1/api/years` returned HTTP 200. The worker's configured default hostname was stale; this probe used the currently live deployment hostname. No production runtime secret was installed.
- Three distinct cold/warm worker cases were attempted: 2005 Toyota Camry starter, 1997 Toyota RAV4 oil/water pumps, and 2002 Honda Civic front caliper. None passes acceptance:
  - Camry: `needs_review`, zero steps on cold and warm; one selected source ID (fingerprint `c6e07e6d0d4b`).
  - RAV4: cold and warm both raised `RuntimeError` because no usable vehicle-matched source procedure was available.
  - Civic: `needs_review`, two steps on both passes (fingerprint `64a408bb9c15`); no torque/check terms and zero returned images.
- No passing cold/warm sample, complete DIY procedure, or localized composition image has been demonstrated. These are failures, not accepted tests.
- No Kubernetes context is configured, so the actual deployment's runtime secret store could not be updated or verified. Hosted checks and independent release review have not run for this implementation candidate.

## Remaining blockers

1. Configure the protected-source credential and current AutoDBone origin in the actual AutoData worker runtime; verify from that runtime without weakening Vercel Deployment Protection.
2. Repair provider identity/catalog selection and procedure completeness until three newly randomized, distinct vehicle/procedure cold/warm pairs provide complete source-backed instructions, stable warm reuse, and working localized images.
3. Prove no composition/derived-article writes or cache entries on those exact cold/warm runs.
4. Run hosted checks on the exact final candidate and obtain independent contract, data-quality, and security review plus a validator-passing release manifest.

Issue #110 remains open. Do not merge PR #125 or close Issues #110–#116 based on this report.
