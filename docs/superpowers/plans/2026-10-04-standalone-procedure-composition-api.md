# Standalone multi-component procedure composition API

**Issue:** https://github.com/lucronn/autodata/issues/110  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/mercury2-procedure-composition.md`

## Goal

Expose vehicle-matched multi-component procedure composition through AutoData's
standalone catalog/job-plan API, with no chatbot UI, route, worker, or runtime
dependency. Preserve individual source articles and their provenance; return
the unified composition only in the synchronous response.

## Decisions and invariants

- Composition is a standalone catalog API capability, not chatbot work.
- Verify three newly sampled, distinct vehicle/procedure requests. The user
  approved any three random cases and approved the available source material for
  ingestion, storage, normalization, and consumer display.
- Each case must pass a cold request and a warm replay. Cold requires complete,
  readable, source-backed instructions for each requested component, correctly
  vehicle-matched sources, safe local image references, and no labor or false
  completeness. Warm must reuse the persisted individual source articles with
  no provider detail calls and no new article/composition writes.
- The combined procedure is ephemeral. Chat-specific persistence, cache, review,
  and event paths are not used.
- Keep Vercel Deployment Protection enabled. Use only a supported, least-
  privilege worker identity or an internal connector deployment; never put
  secrets in source, logs, issue comments, or test reports.

## Concrete todo

- [x] Trace the existing `/job-plans` public route, Go proxy, worker handler,
  and compose path; document whether it already meets the standalone contract.
- [x] Add `POST /v1/catalog/vehicles/{vehicle_id}/compositions`, resolve the
  canonical vehicle through the catalog store, reject conflicting vehicle
  fields in the body, proxy through the existing Go-to-worker boundary, and
  document it in OpenAPI JSON/YAML without chat-specific dependencies.
- [x] Add API/worker contract tests for validation, auth, cold hydration,
  provider-qualified identities, truthful failure, and ephemeral composition.
- [ ] Configure approved AutoDBone access for the actual worker runtime while
  preserving Deployment Protection; verify a real worker-originated request.
- [ ] Run three newly randomized, distinct YMME + procedure cold/warm pairs.
  Record redacted request IDs, source article identities/hashes, readable-step
  checks, image checks, provider detail-call counts, and persistence deltas.
- [ ] Run focused and hosted checks on the exact candidate SHA, independent
  contract/data-quality/security review, and the required release manifest.
- [ ] Close #110 only when every acceptance check passes.

## Acceptance

The documented standalone API returns a source-backed multi-component
procedure for three newly sampled distinct vehicle/procedure cases. Each cold
and warm result satisfies the invariants above; unavailable sources produce an
explicit incomplete/error response, never an empty or falsely complete result.
The worker can reach AutoDBone through the approved protected/internal path.
Exact-SHA hosted and independent gates pass. No chatbot capability is required.

## Implementation sequence

1. Synchronize this plan, Issue #110, Project #8, and the canonical contract at
   a planning checkpoint; pin the implementation base and pass preflight.
2. Implement only missing standalone API/worker contract pieces with tests.
3. Establish least-privilege protected worker access without disabling Vercel
   Deployment Protection.
4. Exercise three new random cold/warm vehicle-procedure pairs; repair every
   semantic failure before recording acceptance.
5. Run exact-SHA hosted and independent gates, then update issue/project/report.
