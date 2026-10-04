# Catalog release acceptance report

**Candidate:** `98928cc492ba51a4c9f142d056bbb66b4db883a8`
**PR:** https://github.com/lucronn/autodata/pull/125 (draft)
**Project:** https://github.com/users/lucronn/projects/8
**Decision:** blocked; keep the PR draft and Issues #110–#116 open.

## Implemented

- #110/#115: provider-qualified article identity, truthful per-provider failures, worker source headers, and no completeness for empty instructions.
- #111: content-complete articles require resolvable evidence on every retained content block; unknown blocks remain incomplete.
- #112/#116: article images use opaque references to AutoData object storage; provider URL image fetches are disabled; storage keys are excluded from public projections and schemas. SVG and other active image formats are rejected.
- #113: normal API startup uses verified expiring service keys; unsigned local identity is explicit development mode; local Compose API is loopback-bound; Kubernetes service keys and image-reader credentials are API-only Secret references.
- #114: recursive stored-source redaction and local-image-only HTML projection; OpenAPI JSON/YAML describe the source and image routes.

## Verification

- Hosted Autonomous Verification passed on `d3f7ff06d21e9ef13f3cd750e112ec786bc9f5ef` and `d891fb82be2fb7169337927d931363e377d7e4ed`; verification for final candidate `98928cc` is running.
- Go API: `go test ./... -count=1` and `go vet ./...` passed after the raster-only media checks.
- Ingestion worker: `566 passed, 3 skipped, 27 subtests passed`.
- Focused catalog image tests: `14 passed`; Kubernetes manifest tests: `5 passed`.
- Compose config validation passed with synthetic local-only values.
- Isolated Compose candidate `autodata-release-candidate` started; `/healthz`, `/readyz`, `/openapi.json`, `/openapi.yaml`, `/swagger`, and `/workshop` returned HTTP 200. The running API code matches the candidate; the later commits only tightened Kubernetes secret/TLS configuration and added acceptance notes.
- All seven synchronized pre-implementation records passed the machine validator against their pinned checkpoints.
- Five cold catalog attempts for the same oil-pump + water-pump request (2013 Honda Crosstour, 2018 Dodge Charger AWD, 1997 Toyota RAV4, 2012 Ram 1500 DS, 2013 Honda Accord Coupe) each returned HTTP 200 with `complete=false`, `hydrating=true`, and zero configurations. A direct RAV4 hydration recorded an AutoDBone authentication failure (`source rejected authentication`); AutoDBtwo returned selector provenance but no persistable configuration rows. No distinct procedure article was retrieved. Passing vehicle/procedure acceptance: **0/5**.
- The previous release-manifest draft was rejected by `scripts/autonomy/validate_run.py`: required gate decisions/reports, evidence completeness, provenance coverage, and valid base SHA were missing. No passing run manifest is claimed.

## Remaining blockers

1. #110 has no active non-chat composition route. The retired `/chat/queries` endpoint returns 404. The product path depends on whether multi-component composition should be a standalone catalog API or be canceled with chatbot work.
2. #115 needs approved protected AutoDBone worker access or an internal connector deployment. Authenticated Vercel CLI access is not worker-runtime proof; no bypass credential or protection setting was changed.
3. #110/#111/#112/#115 need real source-backed cold/warm article tests with diverse vehicles and procedures, readable ordered instructions, evidence, and working local images.
4. The final PR SHA `98928cc` still requires hosted checks and independent review. Source-rights and provenance release gates are not complete.

## Actions before release

- Resolve the Issue #110 product path.
- Provide approved worker-side access to the protected source, then run fresh cold and warm acceptance against the final SHA.
- Complete source-rights/provenance, schema, reliability, security, and independent-review reports in a validator-passing run manifest.
- Merge only after every required gate passes with zero critical/high findings.
