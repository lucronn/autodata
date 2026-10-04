# Ordered article document normalization implementation plan

**Issue:** https://github.com/lucronn/autodata/issues/111  
**Project:** https://github.com/users/lucronn/projects/8  
**Canonical contract:** `docs/architecture/normalized-article-document.md`  
**Related contracts:** `docs/architecture/contracts.md`, `docs/architecture/article-catalog-list-only-hydration.md`

## Goal

Make every selected source article safe to ingest, store, and display without
losing source order, headings, tables, callouts, paragraphs, lists, or image
positions. Preserve the exact original source for audit and keep the normalized
ordered document as the only consumer-facing article representation.

The existing `body`/`steps`/top-level `images` projection remains a backward-
compatible read projection during migration. The ordered document becomes the
authoritative representation for new and rehydrated content.

## Concrete todo

- [ ] Add the provider-neutral ordered article document contract and schema
  validation for headings, paragraphs, lists, tables, callouts, steps, images,
  links, unknown blocks, source order, and evidence references.
- [ ] Refactor source adapters to emit ordered blocks without flattening table
  cells, document anchors, HTML structure, or interleaved images.
- [ ] Persist immutable original source, canonical article identity, ordered
  document blocks, materialized image assets, normalization version, and a
  compatibility projection without creating duplicate list-only/detail rows.
- [ ] Materialize provider images into local object storage and expose only
  same-origin AutoData asset URLs; retain explicit unavailable-image blocks for
  failed media reads.
- [ ] Make normalization deterministic and order-preserving. Infer steps only
  from explicit source boundaries; retain unstructured content as ordered
  blocks instead of fabricating numbered steps.
- [ ] Update the article API and Workshop renderer to render the ordered block
  stream, including tables, callouts, headings, and images at their source
  positions.
- [ ] Strengthen `content_complete` validation and return explicit hydration or
  source failure states instead of serving malformed content as complete.
- [ ] Add fixture, property, round-trip, API, image, duplicate-identity, and
  browser regression coverage across arbitrary article shapes and both source
  adapters.
- [ ] Rehydrate representative existing articles, verify the Ram axle article
  and additional random articles live, run the full applicable suites, rebuild
  Compose, and synchronize Issue #111 and Project #8 evidence.

## Design constraints

- Original source bytes and source metadata remain immutable and available for
  later review.
- Normalization never reorders source content or removes repeated source text
  unless the source explicitly marks it as presentation-only.
- Structural normalization is deterministic. Optional phrase rewriting is a
  separate transformation that must preserve block IDs, count, and order.
- Catalog hydration remains list-only. Article detail and image reads happen
  only after a user selects an article.
- A valid unknown source shape is retained as an ordered `unknown` block and
  marked for review; it is never silently dropped or guessed into a procedure.
- Existing uncommitted workspace artifacts remain untouched and unstaged.

## Acceptance

- The Ram `Axle Drive Shaft Seal - Removal` article renders its tool table,
  removal text, and each illustration in the source order without literal pipe
  separators.
- An article with no reliable numbered steps remains readable without a fake
  `1.` wrapper.
- A table-heavy article, callout-heavy article, paragraph-only article,
  numbered article, malformed-link article, image-free article, and partial
  article each have an honest status and readable rendering.
- Every public image URL is same-origin and resolves to a stored asset or an
  explicit unavailable-image state.
- Repeated selected-article requests reuse the canonical article identity and
  do not create a second list-only/detail row for the same provider article.
- The original source remains retrievable by source snapshot and evidence ID.

