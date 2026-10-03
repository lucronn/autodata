# Normalized article document contract

**Tracking:** [Issue #111](https://github.com/lucronn/autodata/issues/111) in
[AutoData Portfolio Project #8](https://github.com/users/lucronn/projects/8).  
**Implementation plan:**
`docs/superpowers/plans/2026-09-30-ordered-article-document-normalization.md`

## Purpose

AutoData receives repair articles in different provider formats. The source
response must be captured unchanged, then converted into one ordered document
shape that the API and Workshop can render without provider-specific logic.

The document is an ordered stream. Each block has a stable block ID, source
order, evidence references, and one display type. The stream is authoritative;
`body`, compatibility `steps`, and the top-level image list are projections.

## Document shape

```json
{
  "schema_version": 1,
  "normalization_version": "ordered-article-v1",
  "blocks": [
    {
      "block_id": "article:block:0001",
      "source_order": 1,
      "type": "heading",
      "level": 2,
      "text": "REMOVAL",
      "evidence_ids": ["evidence-1"]
    },
    {
      "block_id": "article:block:0002",
      "source_order": 2,
      "type": "table",
      "label": "Special Tools",
      "columns": ["Tool", "Description"],
      "rows": [["8498", "Receiver, Axle Shaft Seal"]],
      "evidence_ids": ["evidence-2"]
    },
    {
      "block_id": "article:block:0003",
      "source_order": 3,
      "type": "image",
      "asset_id": "asset-1",
      "alt": "Axle seal tool illustration",
      "evidence_ids": ["evidence-3"]
    },
    {
      "block_id": "article:block:0004",
      "source_order": 4,
      "type": "paragraph",
      "text": "Remove the axle seal.",
      "evidence_ids": ["evidence-4"]
    }
  ]
}
```

Supported types are `heading`, `paragraph`, `ordered_list`, `unordered_list`,
`step`, `table`, `callout`, `image`, `link`, `break`, and `unknown`. Unknown
blocks retain their sanitized text or raw-source locator and receive a review
reason. They do not disappear from the document.

## Processing boundaries

The source adapter parses HTML, JSON, PDF, or other supported media into the
ordered block stream. Table cells remain structured cells. Local document
anchors are ignored as navigation metadata. Invalid external links do not make
an otherwise readable article fail. Images are represented as media blocks at
their source position.

Normalization classifies blocks and derives optional sections and compatibility
steps. Headings and explicit ordered-list boundaries may create steps. Plain
paragraphs remain paragraphs. The normalizer must not create a numbered step
merely because content exists.

Image materialization fetches source bytes once, stores them in object storage
using a content hash, and gives the document an internal asset ID. Public API
responses expose only same-origin asset URLs. A failed image fetch creates an
unavailable asset state with a reason and source evidence.

The exact source response is stored in `source_original` and linked to the
source snapshot. The normalized document is versioned. A new source snapshot or
normalization version creates a new revision of the same canonical article
identity; it does not create an unrelated list-only/detail article pair.

### Repairing legacy empty documents

Some legacy rows may be marked `content_complete` while the ordered document
has no blocks, even though an immutable `source_original` and compatibility
`body`/`steps` are present. Such a row is not complete under this contract.
Selected-article reads must repair it from the stored source snapshot before
falling back to an upstream provider. The repair reuses the existing provider
parser, preserves the original snapshot and evidence, and updates the existing
canonical article row idempotently. It must not fetch source content or invoke
an LLM. It must not call a source catalog or article-detail endpoint.

A repair must retain image blocks at their parsed source positions and reuse
already-localized assets. If an image asset is missing, only that image may be
fetched once through the existing allowlisted image adapter and persisted
locally; subsequent reads reuse it. If that media read fails, the document
keeps an unavailable image block at the same source position instead of
moving it to a detached gallery. If the stored source cannot produce a valid
readable ordered document, the row is `content_partial` and the API reports the
repair failure. Existing valid, non-empty ordered documents remain authoritative
and are not rebuilt on normal reads. See the
[legacy repair plan](../superpowers/plans/2026-10-03-repair-legacy-ordered-article-documents.md).

## Completeness and errors

`list_only` means the catalog descriptor is available but detail has not been
retrieved. `content_partial` means detail was retrieved but one or more
required blocks, media assets, or validations failed. `content_complete` means
the ordered document validates, readable content is present, every image is
resolved or explicitly unavailable, and all retained blocks have source
evidence.

The API must not return a malformed article as a successful complete response.
For selected-article hydration, it returns the durable hydration state and
source failure detail when the canonical content is not ready.

## Consumer rendering

The Workshop renders blocks in array order. It uses semantic tables for tables,
headings for headings, callouts for safety notes, paragraphs for prose, ordered
lists for ordered source steps, and the same-origin asset URL for image blocks.
There is no detached image gallery fallback for an image that has a valid source
position. An unavailable image is rendered at that position with its review
state.

## Verification contract

Tests must prove source-order preservation, deterministic repeated normalization,
source-original retention, image placement, no provider URL leakage, valid
table/callout rendering, stable canonical identity on repeated hydration, and
honest partial/completed status across both providers.

## Implementation evidence (2026-09-30)

The live Ram 1500 DS axle article now returns 15 ordered blocks, including its
tool table and interleaved illustrations, with no literal table-pipe artifacts.
Its eight image references are served through the same-origin image endpoint;
the first SVG proxy read returned HTTP 200. Re-reading the legacy list-row URL
returned the cached complete detail without adding another detail row. A cold
five-vehicle article sweep returned five HTTP 200 responses with readable
content and non-empty ordered documents.

Automated verification passed: 557 Python tests with 3 skips, Go tests, 13
Workshop JavaScript tests, 13 migration tests, and `git diff --check`.
