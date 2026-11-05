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

Catalog display URLs are opaque references to these already-local objects.
The API may read the configured object store to serve an image, but must never
fetch an image from a provider during article or source-review display. Object
keys remain internal and are omitted from public JSON and OpenAPI. An asset
that could not be localized remains unavailable; it does not fall back to a
remote URL.

The exact source response is stored in `source_original` and linked to the
source snapshot. The normalized document is versioned. A new source snapshot or
normalization version creates a new revision of the same canonical article
identity; it does not create an unrelated list-only/detail article pair.

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

## Durable ordered rewrite (November 2026)

The lifecycle keeps immutable `source_document`, body, steps, images and resource
provenance before any rewrite. Normalization preserves existing ordered blocks,
including string-valued list items and table cells. The model receives only
bounded editable prose slots addressed by block ID and path, and returns each
slot exactly once in order. Tables, warnings, images, nested structure, evidence
and the noneditable parts of text remain protected.

The current `technical-prose-v1` validator is deliberately conservative: it
allows a small set of equivalent opening verbs while requiring the remainder
of the instruction to match. It rejects altered numbers/units, negation,
applicability, tools, parts, safety text, block order, table cells and asset
positions. Nested images require persisted local content identity or an
explicit unavailable reason at their original position. Provider URLs cannot
become renderable images. An unchanged or invalid model response remains
source/review content; no success is fabricated.

Every attempt records prompt/input hashes and dispatch ownership; bounded raw
results and candidate documents persist before validation/publication. Reports
bind source, candidate, protected projection, skeleton, evidence and changed
slots. Publication recomputes these bindings and projections under the live
job/article locks. The revision, pointer, completed job and outbox commit
atomically. Saved results resume without another model request. A new source or
explicit normalization/profile version uses a new transformation key; an
unchanged-source refresh retains the original completed or exhausted owner and
its budget. Human `review_status=UNREVIEWED` remains distinct from automated
validation.

The shared catalog contract is generated from `packages/contracts/contract.json`
by `scripts/contracts/generate.py` into Python/Go bindings. It adds lifecycle
states and publication events without changing existing dataset envelopes.

## Public lifecycle projection

Source fallback and published canonical content share `schema_version:1` and
`normalization_version:ordered-article-v1`. Source is `content_partial`, even
when structurally complete. Canonical completion additionally requires a
published revision, matching source revision and nonempty document. Retained
unknown block text, ordered steps, warnings, tables, evidence IDs and image
positions remain visible.

Public nullable identity/revision fields accompany `content_origin`,
`availability`, `view_revision`, stored `review_status` and durable `processing`.
States are queued, fetching_source, normalizing, rewriting, validating,
publishing, completed, failed and needs_review. The display revision hashes
immutable selected content and policy; random media tokens and processing-only
updates do not change it. A new source is selected until its matching canonical
publication; an older canonical cannot claim to rewrite the new source.

The catalog JSON Schema and matching OpenAPI JSON/YAML bind additive fields and
compatibility body/steps/media. Fixtures reject title-only completion, invented
states, private object metadata and mismatched source/canonical metadata.

Compatibility steps preserve the actual R2 projection. Canonical steps expose
`action`, the ordered following `instructions`, ordered `evidence_ids`, and
`images` when that field was supplied, including an explicit empty array. A
canonical action is not copied into instructions. Source steps retain `text`
and their explicit positive `number`; the legacy instructions array may be
derived from source text when absent or empty. An absent canonical number stays
absent. The ordered document remains authoritative for display order. Step
images use the same safe public metadata and local-reference transformation as
article images; storage keys and provider URLs are not exposed, and rotating
media URLs do not change the view revision.


## Retained list and callout block images — proposed consumer contract

Status: synchronized tracking contract in external package; exact-source K3b Actions PASS, full external Vercel rollup failure. Exact K3b source admitted by coordinator for this six-document planning checkpoint only; awaiting committed K4, exact-base preflights and independent review. No implementation or product-acceptance claim.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Goal: Render retained ordered-list, unordered-list and callout block images in Workshop source, canonical and stored-source views through the existing authorized-media helper, preserving native list semantics, callout context, source evidence and rights fallback.
Status: synchronized tracking contract (external package awaiting committed checkpoint). Issue186 comment `https://github.com/lucronn/autodata/issues/186#issuecomment-6646734485` and Project8 Source pointer were read back at `2026-11-05T01:06:29Z`. Selected planning base K3b `a788f110e57de13b1b876df0e148df4705db591e` (tree `9a3d2e449c42085a384950118e9c7c7a28bbb873`), exact planning-checkpoint review PASS; exact-source Actions audit PASS. Full check rollup remains failure due to external Vercel. K4 SHA/tree unknown; implementation/preflight/operational/release authorities remain false; accepted-case credit 0.

Concrete todo:
1. Preserve current Issue186/Project8 history; synchronize the combined goal, six gate-document paths, two implementation paths, list sibling/callout content-container DOM contract, exact helper fallback, todo and all false authorities; retain fresh readback and independent committed-gate review.
2. Add production-function DOM tests for normalized ordered/unordered string-item lists and callouts with direct/item-flattened retained block images; observe intended missing-figure failures on frozen M5 application bytes and retain exact red logs.
3. Add only list block-image emission and callout second-grid-child content grouping/image emission through the existing resolver/addImage helper; preserve item images, text/label count, source links and unavailable-media behavior.
4. Verify mixed-document placement, source/canonical actual renderArticle and stored-source actual loadSource entry paths, ID aliases, safe/missing media, exact alt/caption, empty media and object-item compatibility; add explicitly new bounded actual renewMedia/reconcile/invalidation coverage and run focused/full Node, syntax, embedded Go and diff/scope checks with exact-SHA logs.
5. Record exact-code independent review, source hashes, measured test results and unresolved browser/accessibility/product-acceptance limits; commit and promptly push validated coherent milestones only to the coordinator-assigned branch when separately authorized; keep every runtime/release/provider/payment/acceptance authority false.

Six prospective gate paths:
- `docs/superpowers/plans/2026-11-04-workshop-list-callout-media.md`
- `docs/superpowers/specs/2026-11-04-workshop-list-callout-media-design.md`
- `docs/agents/records/2026-11-04-workshop-list-callout-media.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-list-callout-media.json`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/architecture/normalized-article-document.md`

Two prospective implementation paths:
- `apps/api-go/workshop/app.mjs`
- `apps/api-go/workshop-client.test.mjs`

Current implementation allowlist: []. All authorities false. Accepted-case credit: 0.

Normalized ordered/unordered lists retain string items and block-level image references. Render `ol`/`ul` with only `li` element children and unchanged item count; emit block figures immediately after the list in retained reference order. Preserve object-item images inside their existing `li`. Item associations flattened by normalization cannot be reconstructed from the global image pool; do not invent placement or deduplicate across contexts.

Callouts retain `aside.article-callout > strong + div`; the content div contains one text span followed by retained figures, so figures stay in the second grid column and within callout context. Keep figures outside the span; empty image lists preserve the two grid children and original label/text. CSS changes are outside this gate.

Use the existing ID-alias resolver and `addImage` only. Nonempty reference alt produces image alt and caption; absent/empty reference alt uses resolved-image alt or `Article illustration` without a caption. Missing or unsafe authorized media produces the existing `Illustration unavailable.` figure text without img/caption. Inline/provider URLs never act as a fallback. Preserve existing renewal limits, revision reconciliation, invalidation and rights suppression.

The same contract applies to source/canonical `renderArticle` and actual stored-source `loadSource`, retaining source/processing labels and Source links. Future production-function DOM tests cover lists/callouts/mixed placements, ID aliases, safe/missing media, alt/caption, object/empty compatibility, renewal/reconcile and 401/403/410 clearing/stale generations. Native accessibility-tree, diagram interpretation/order, narrow-screen grid, print layout and stored-source visual observations remain separately authorized browser work. Historical evidence elsewhere in this document remains historical.


## K4 tracking and CI checkpoint evidence

Status: synchronized tracking contract (external package awaiting committed checkpoint). Issue186 comment `https://github.com/lucronn/autodata/issues/186#issuecomment-6646734485` and Project8 Source pointer were read back at `2026-11-05T01:06:29Z`. Selected planning base K3b `a788f110e57de13b1b876df0e148df4705db591e` (tree `9a3d2e449c42085a384950118e9c7c7a28bbb873`), exact planning-checkpoint review PASS; exact-source Actions audit PASS. Full check rollup remains failure due to external Vercel. K4 SHA/tree unknown; implementation/preflight/operational/release authorities remain false; accepted-case credit 0.

Canonical core status is `synchronized` for the literal goal, five todos and path contract. The external package does not constitute committed K4 or a passing implementation gate. All 48 authority booleans stay false; factual tracking readback and source-only CI observations do not grant new action authority. The coordinator explicitly admitted exact K3b as source for the six-document K4 planning checkpoint only; code/runtime/acceptance/release authority remains false.

Tracking before snapshot: `/home/corp/autodata-evidence/article-media-k4-before-tracking.json`, SHA-256 `dcae6d1cff722fe1fc42a2065b2e1bc5c605f2a150d2398efa93a8df88929295`. Tracking after snapshot: `/home/corp/autodata-evidence/article-media-k4-after-tracking.json`, SHA-256 `e326e6f387ec8b8dd9b4a236511e7d470b700476ba1feef83b5bf58ac2261229`. Exact added Issue comment SHA-256: `4103436ee9185599ab5d71ce93f9aa2bf08d7ff9304cd5db87dd8ca2fabeb286`. Project Source pointer SHA-256: `411f7b8cb52202960f155ad2df89829f593c5921183e4d7e0195009bd9de3421`. Independent retained-snapshot verification: `/home/corp/autodata-evidence/article-media-k4-ci-rebind/tracking-readback-verification.json`, SHA-256 `6f2330c2a6b15998c3fe8954482d670c0310d12153a1342708baed3899cc62f6`. Issue body, all 229 prior comments and other Project fields were preserved; the prior Project Source field is archived verbatim in the before snapshot. Historical proposed/unverified wording in the additive comment describes preparation time and is superseded for factual readback only by these receipts.

Source-only Actions receipt: `/home/corp/autodata-evidence/api21-k3b-ci-final/receipt.json`, SHA-256 `ef2689c464617b84a6ad0a671bc3c2932d345a81714774b58eaf517475cdbfe6`. Push run https://github.com/lucronn/autodata/actions/runs/41943766277 checked out exact K3b `a788f110e57de13b1b876df0e148df4705db591e`. PR run https://github.com/lucronn/autodata/actions/runs/41943811298 checked out `0e7e6050a0588d19870dd95c2410c343ef591f5a`; its parents are `046b141f80dbb0a28bfeb3e0ab7f9635f4ab349c` and K3b. Both runs completed successfully; the source and merge trees equal `9a3d2e449c42085a384950118e9c7c7a28bbb873`. The full check rollup remains failure because external Vercel reports `Deployment rate limited — retry in 24 hours.`; the cause is not independently established. Cursor Bugbot is neutral. No wholly green rollup, media CI authority, acceptance or release credit is claimed.

K4 SHA/tree, implementation base, execution gate and branch assignment remain null. Preflights have not run. The coordinator must recheck source/queue concurrency, preserve the coordinator admission limited to six-file planning materialization, commit and externally seal actual K4, pass standalone and nested canonical preflights at exact K4, obtain independent exact-K4 review and issue explicit two-path implementation dispatch. No code or runtime work is authorized by this external package. The prior K3b package PASS covers its original six hashes only; new synchronized bytes require independent exact-K4 review.
