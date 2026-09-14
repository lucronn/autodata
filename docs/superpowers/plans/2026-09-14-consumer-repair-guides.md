# Illustrated consumer repair guides

## Goal and accepted product decisions

Chat must produce polished DIY repair guides and matching PDFs, combining existing AutoAPI content with AutoAPI Two. Replacement guides include prerequisite access, removal, installation, timing, fluids and final checks. Shared operations occur once in a valid dependency order. Incomplete results are previews; PDF download is withheld until essential instructions and figures are resolved. Consumer text contains no source or generation commentary; evidence remains attached internally. Existing review status is separate from completeness.

## Implementation

1. Add a bounded, read-only AutoAPI Two connector using fleet search, vehicle-scoped content search and returned article/media links. Keep provider vehicle IDs separate. Resolve engine, body and drivetrain before mixing sources. Never infer identity from shared model names. Reject off-origin or cross-vehicle content links; do not invoke account/session-management/cache mutation endpoints. Preserve raw article HTML, normalized ordered text, figure associations, hashes and provenance. Cache successful reads and coalesce concurrent identical requests; honor retry-after and bound timeouts, fan-out and dependency expansion.
2. Expand requested procedures through explicit supporting operations and linked component content. Retrieve removal and installation together, including specifications and mandatory timing, sealing and refill instructions. Avoid irrelevant search hits (engine teardown is not a pump prerequisite). Preserve unresolved dependencies and conflicts as explicit completeness gaps. Do not invent missing values or declare completeness solely from headings.
3. Compose a single structured guide with applicability, preparation, tools/consumables, numbered phases/steps, step-specific images, torque references and final checks. Preserve internal source/evidence IDs, required work and optional work. Consolidate equivalent shared operations only when their preconditions and resulting mechanical state agree. Keep numerical specifications and warnings intact; detect incompatible values and unit mismatches. Use the existing model boundary for wording and ordering with validation against retrieved steps. No source prose in consumer output.
4. Extend the existing chat answer additively with guide content, revision, completeness/gaps and PDF readiness. Persist it in the existing durable answer snapshot. Render guide sections and images in the existing dashboard, show useful previews and plain-language progress, and preserve vehicle selection and current quote behavior. The legacy procedure contract remains readable.
5. Generate PDFs from the same immutable guide revision and verified image bytes, using a deterministic layout. Serve through the authorized chat query boundary with owner/organization checks; never expose source credentials or arbitrary URL fetching. Keep partial and stale revisions from appearing as final downloads. Cache artifacts by revision and recover safely after restart.

## Verification

Unit and integration coverage: identity ambiguity, provider mismatch, hostile links/HTML, dependency cycles and budgets, missing installation/specification/figure, conflicting torque values, shared-work deduplication, preserved warnings and numbers, consumer-copy cleanliness, cache/coalescing/retry behavior, PDF authorization and revision parity. Render PDFs and inspect every page for clipping and unreadable diagrams. Exercise the browser on a narrow screen and desktop; verify images and download behavior.

Live acceptance: submit a 1997 RAV4 oil-pump plus water-pump request, choose the exact variant, retrieve both providers, resolve timing-belt and installation dependencies, display one coherent illustrated guide, download and inspect its matching PDF, then replay the request to verify reuse. A second vehicle/job and missing-content scenario must prove this is not a RAV4-only template. No completion claim based on fixtures alone.

## Delivery and todo

Tracking: https://github.com/lucronn/autodata/issues/89 and https://github.com/users/lucronn/projects/8. Canonical contract: docs/architecture/consumer-repair-guides.md. Establish a synchronized machine record and validate the pinned planning commit before implementation. Preserve sample data/, output/ and tmp/ as local artifacts, not repository sources.

- [x] Connect and validate the additional source.
- [x] Retrieve and compose complete repair dependencies with images.
- [x] Render consumer guides and revision-matched PDF downloads.
- [x] Verify tests, live chat, images, PDF and warm replay; synchronize delivery evidence.
