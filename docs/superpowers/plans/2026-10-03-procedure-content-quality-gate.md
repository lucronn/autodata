# Reject incomplete cached repair procedures

**Issue:** https://github.com/lucronn/autodata/issues/110  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/mercury2-procedure-composition.md`

## Goal

Never report a multi-component procedure as ready when its selected source
articles contain only headings, metadata, or other non-instructional text. A
cached row must satisfy the same procedure-content contract as a newly fetched
article. If its saved original source can repair it, repair and persist that
individual article; otherwise fetch only the selected source article or return
an explicit unavailable/incomplete result. Public images must use the opaque,
server-local media route.

## Evidence

At PR #123 HEAD `289603639dfe5bf330dde06905a86f9c6d8ade32`, an isolated warm
candidate request for 2012 Dodge/Ram Ram 3500 6.7L, “alternator and oil pump
replacement,” returned `status=ready` and `source.mode=normalized_cache`, but
the selected instructions were only “7L DIESEL” and “REMOVAL.” Both rows had
`content_status=content_complete`. The returned image references still used
the legacy `/v1/catalog/images?src=...` form. This disproves the earlier weak
non-empty/cache acceptance signal.

## Invariants

- “Ready” requires meaningful, source-authored procedure instructions for each
  requested component; headings, section labels, metadata, and empty lists do
  not count.
- Apply the same content validator to fresh ingestion, normalized persistence,
  cache reads, composition selection, and public article rendering.
- Invalid legacy rows are not usable cache hits. Rebuild them from the immutable
  retained source snapshot when possible, otherwise refetch only the selected
  individual article. Persist repaired individual articles idempotently; never
  persist the combined result.
- Preserve the original source and source lineage. Do not invent missing repair
  steps or silently label partial source data complete.
- Public image references use opaque same-origin paths; reject legacy `?src=`
  references at the external response boundary.
- Labor remains out of the retrieval and readiness decision.

## Concrete todo

- [ ] Add a shared procedure-content quality predicate and regression fixtures
  for headings-only, metadata-only, empty, malformed, and valid source steps.
- [ ] Make cache reads and composition reject rows that fail that predicate,
  independent of a stale `content_status` value.
- [ ] Repair rejected legacy rows from their immutable original snapshot, or
  fetch only the selected article; persist individual repairs with source
  lineage and locally stored/opaque images.
- [ ] Return an explicit incomplete/source failure when meaningful content is
  still unavailable; do not emit a `ready` procedure from placeholder text.
- [ ] Add response tests proving images are opaque and no provider URL or
  `?src=` survives the public projection.
- [ ] Run the worker, Go API, contract, and Compose checks; repeat five newly
  sampled cold and warm multi-component requests across distinct YMME vehicles.
  Require meaningful source-backed instructions for both components in every
  result, correct image references, no labor, no combined persistence, and no
  database growth on warm replay.
- [ ] Publish exact-SHA evidence to Issue #110 and Project #8; obtain the
  independent release gates before closing or merging the stacked PRs.

## Acceptance

The five distinct-YMME cold/warm pairs either return usable source-backed
procedures with meaningful instructions for every requested component or
honestly report that the missing source content could not be obtained. A
heading-only or metadata-only response must never be `ready`. Warm valid rows
make no provider detail calls or database writes; combined procedures remain
ephemeral.
