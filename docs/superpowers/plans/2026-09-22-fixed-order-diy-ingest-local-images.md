# Fixed-order procedure ingest with DIY rewrite and local images

Issue: https://github.com/lucronn/autodata/issues/112
Project: https://github.com/users/lucronn/projects/8
Canonical repository documents:
- `docs/architecture/contracts.md`
- `docs/architecture/dashboard-agent-workspace.md`
- `docs/agents/pre-implementation-gate.md`

## Goal

Ingest each provider article in source order, keep an immutable original copy,
LLM-rewrite only step phrasing for DIY uniqueness, fetch and store images
locally so display never depends on AutoAPItwo URLs, and remove all step
rearranging.

## Architecture

1. Store `source_original` (provider blocks/body/image URLs) on each catalog
   article for audit.
2. Normalize into ordered consumer steps without rearranging or verb-based
   phase flips that later shuffle steps.
3. Mercury-2 rewrites only `action` / `instructions` text with the same step
   count and order; failure keeps normalized wording and records
   `rewrite_status`.
4. Fetch figures into MinIO at ingest; served `images` use local storage keys /
   data URIs, never live provider hosts.
5. Compose concatenates articles in fixed component order only — no global
   phase sort.

## Concrete todo

- [ ] Remove compose phase sort and ingest verb phase-flips; preserve source
  order.
- [ ] Add `source_original` (+ `rewrite_status`) migration and persist/load
  round-trip.
- [ ] Fetch provider images to MinIO at ingest; store local keys on
  step/article images.
- [ ] Mercury phrase-only rewriter with fixed-order validation; wire into
  persist path.
- [ ] Unit + warm oil-pump smoke: order stable, originals stored, no provider
  image hosts.

## Acceptance

- Published step order matches source block order within each article.
- Multi-component answers concatenate articles without phase reshuffle.
- `source_original` is present on `content_complete` rows.
- Served image URLs are not AutoAPItwo hosts.
- DIY rewrite changes phrasing only or is marked skipped/failed without
  changing order.
