# Source Connector API Compatibility Plan

**Goal:** Keep AutoData's source adapters and runtime configuration compatible
with the current AutoDBone and AutoDBtwo connector APIs.

**Issue:** https://github.com/lucronn/autodata/issues/115

**Project:** https://github.com/users/lucronn/projects/8

**Canonical contract:** `docs/architecture/source-connector-api-compatibility.md`

**Todo:**

- [ ] Map AutoData's AutoAPI source vocabulary to AutoDBone's neutral catalog
  aliases and route family, preserving existing response parsing and provenance.
- [ ] Set the documented AutoDBone endpoint as the local default and make the
  endpoint explicit in deployment configuration without changing secret
  handling.
- [ ] Fetch AutoDBone's signed `/v1/assets/reference/...` figures through the
  configured AutoDBone origin and persist them in AutoData object storage;
  never send these URLs to AutoDBtwo or expose them in normalized responses.
- [ ] Verify AutoDBtwo remains pinned to its latest standalone connector
  revision and that catalog/article/image requests use only its HTTP boundary.
- [ ] Add focused route, alias, signed-asset, unsupported-source, safe-error,
  and runtime-configuration tests; run relevant worker and deployment checks.
- [ ] Verify live health/catalog behavior against the reachable connector
  endpoints, and record any provider/authentication limitation separately.

## Current observed mismatch

AutoDBone's latest public facade registers `/v1/api/catalog/:catalog/...`
routes and accepts neutral aliases (`gm`, `toyota`, and `catalog`). AutoData's
`AutoAPIConnector` still builds legacy `/v1/api/source/{provider}/...` paths,
including vehicle, article, labor, parts, and resource reads. The local Compose
default also points at the previous `autoapi-sigma.vercel.app` deployment.
AutoDBtwo's latest source revision is `a54541d1397c0aec8a684ee0cec720138c0bfb86`;
the current AutoData worktree already has that submodule revision, which must
be preserved during this change. AutoDBone now rewrites embedded images into
signed `/v1/assets/reference/...` URLs; AutoData's image fetch path currently
sends all provider images to AutoDBtwo, which rejects AutoDBone URLs and causes
the figures to be omitted.

## Decisions and boundaries

- AutoData remains the public normalized API and system of record.
- AutoDBone is the connector for the existing AutoAPI source. Translate only
  the connector's route and catalog alias at the HTTP boundary; do not leak the
  upstream provider vocabulary in new public AutoData routes.
- Map `GeneralMotors` to `gm`, `Toyota` to `toyota`, and `Motor` to `catalog`.
  Reject unmapped provider names rather than silently routing them to another
  catalog.
- Preserve source response bodies, parsing, normalization, source hashes,
  provenance, and persistence semantics.
- Validate signed AutoDBone asset URLs against the configured connector origin
  and exact asset route before fetching. Bound response bytes, reject redirects
  and non-image media types, and store accepted bytes in AutoData object storage
  so normalized article output contains no signed source URL.
- Keep Vercel Deployment Protection enabled. Authenticated live checks may use
  the existing Vercel CLI context; runtime access must use approved deployment
  configuration or an internal connector deployment. Never commit bypass
  credentials.
- AutoDBtwo remains a separately deployed read-only service configured through
  `AUTODATA_AUTODBTWO_BASE_URL`; its upstream host is set only in that service.
- No database schema, normalized-data API contract, source credential, or
  production deployment change is in scope.
- Tests must prove AutoData emits the current connector routes and handles
  unavailable/unauthorized upstream responses safely. Unit/contract tests do
  not substitute for live connector evidence.

## Acceptance criteria

- Every AutoData AutoAPI read used for catalog, vehicle identity, articles,
  article details, optional labor, parts, and binary/resource content maps to a
  current AutoDBone route and supported neutral alias.
- The AutoData local runtime defaults to the current AutoDBone service URL;
  deployment config has an explicit override and no embedded credential.
- AutoDBtwo is pinned to the latest agreed connector commit and remains the
  sole AutoAPItwo network boundary in the worker path.
- Focused adapter tests and relevant worker tests pass; Compose/Kubernetes
  configuration validates.
- Live connector results are reported with status and response semantics, or
  the exact external blocker is recorded without claiming live verification.
