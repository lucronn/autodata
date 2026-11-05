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


## Retained list and callout block images — K4a correction contract

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Goal: Render retained ordered-list, unordered-list and callout block images in Workshop source, canonical and stored-source views through the existing authorized-media helper, preserving native list semantics, callout context, source evidence and rights fallback.

Exact correction source cd64 `cd64be80867fd223cf05d2ca94f90ce6b48d47de`, tree `4964e26bfd9b83b8ac7e75970b5db5231ce3e9f0`; direct parent K4 `d012fb74f2f9a5d5fc728d76796b1c83723f1780`. All six gate-document blobs at cd64 equal K4. This K4a amendment is based on cd64, not the separate K3c task49 amendment. Independent exact-code review reports FAIL/P2; source is admitted here only for prospective correction planning, never as passing code.

Status: synchronized literal K4a tracking contract; implementation remains blocked. Issue186 comment `https://github.com/lucronn/autodata/issues/186#issuecomment-6646946325` and Project8 Source were read back at `2026-11-05T01:19:56Z`. Issue body, all 232 prior comments and other Project fields are preserved; previous Project Source is archived verbatim in the before snapshot. Project Source indexes K4a and separate task49 K3c. This factual synchronization grants no implementation authority. The earlier K4 preflight/dispatch covers only the earlier contract. Commit this six-file checkpoint on exact cd64, seal actual K4a SHA/tree externally, pass both exact-base preflights and independent exact-checkpoint review, then obtain separate branch/two-path dispatch. Never guess or self-embed the future SHA.

Tracking evidence: before snapshot SHA-256 `1a286ff981b3d3cb932a7af45f87816cee426963732e5c2823815f113f99a4ce`; after snapshot SHA-256 `018511fb8530d7b98f705cf593d3798299e923bc461457723b8a6e743561aa53`; exact added comment SHA-256 `814c0ba7cc20c3d2276774e0ff25bb4158d8fcd5c2dd393ef6f0fac2b738c34e`; Project Source SHA-256 `af0b3c9dc93b78a9edb503ab475f10d0b2343c3189732c4282ada970e7889c19`. Retained-snapshot verification: `/home/corp/autodata-evidence/article-media-k4a-plan/tracking-readback-verification.json`, SHA-256 `8332ac022dc65decd93f0b4967e02afa939d3f1dd96353fa3548a21c6e085d5c`. External draft review PASS40/40: `/home/corp/autodata-evidence/article-media-k4a-package-review/report.md`, SHA-256 `709b1be924d6e8a048777a7c15fe5be60e085380e3354fa6328d890d1da2adca`; it covers the archived original draft hashes only, not these newly synchronized bytes. Independent exact synchronized-checkpoint review remains required. Exact source cd64 is still FAIL/P2; P2 remains open until the two-file correction and independent exact-code review. All authorities remain false, credit0; no preflight is claimed.

Concrete todo:
1. Preserve Issue186/Project8 history and queue root/prior49 task objects; independently review and synchronize this K4a missing-ID correction, six gate documents, two implementation paths, concrete todo and all false authorities; retain fresh literal readback, then commit the six-document checkpoint on exact cd64 source and seal its actual SHA/tree externally.
2. At the committed K4a checkpoint, extract standalone and nested pre_implementation records and exact policy; require both canonical machine preflights errors=[], independent exact-checkpoint review and explicit coordinator branch/two-path dispatch before implementation edits.
3. In workshop-client.test.mjs, use actual production renderContent and renderArticle to reproduce missing-ID wrong-image rendering for ordered_list, unordered_list and callout with a valid unrelated ID-bearing image pool; retain intended red assertions on frozen cd64 bytes and strengthen the existing absent-ID fixture.
4. In only the new callout and list block.images consumers in app.mjs, guard on ref?.asset_id || ref?.image_id before find(ref); pass undefined to existing addImage when missing and preserve ref alt, helper fallback, DOM placement and every existing resolver/helper/rights behavior.
5. Run focused/full Node, JS syntax, embedded Go and diff/scope checks; retain exact-SHA/hash commands, counts and skips, prove missing-ID references yield one unavailable figure and no unrelated img through renderContent and source/canonical renderArticle, and retain all existing media/renewal/source regressions.
6. Commit and promptly push the validated coherent two-file correction only after dispatch, obtain independent exact-code review and fresh exact-candidate CI/tracking readback; keep browser/accessibility/product acceptance, runtime/release authorities false and accepted-case credit zero.

Six gate-document paths:
- `docs/superpowers/plans/2026-11-04-workshop-list-callout-media.md`
- `docs/superpowers/specs/2026-11-04-workshop-list-callout-media-design.md`
- `docs/agents/records/2026-11-04-workshop-list-callout-media.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-list-callout-media.json`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/architecture/normalized-article-document.md`

Two future implementation paths:
- `apps/api-go/workshop/app.mjs`
- `apps/api-go/workshop-client.test.mjs`

Current implementation allowlist: []. Every authority remains false; accepted-case credit: 0. No merge, release, runtime, browser, provider, payment or acceptance authority is granted.


For each ref in the new list and callout block.images loops, evaluate ref?.asset_id || ref?.image_id before find(ref). If neither is truthy, do not call find; pass undefined to existing addImage for Illustration unavailable. Keep the shared find, assetID, addImage, localImageURL, rights, renewal and other consumers unchanged.

Native ol/ul contain only li children; block figures remain list siblings. Callout is aside > strong + div, with span then retained figures in the div. Missing-ID refs must never display an unrelated pool asset: use existing unavailable figure text through addImage. Existing authorized URL, alt/caption, source evidence, aliases, renewal, reconciliation and rights clearing remain unchanged. Actual renderContent and source/canonical renderArticle regressions require valid unrelated ID-bearing pool assets; existing stored-source/renewal tests remain required. Keep browser/accessibility/narrow-screen/print/current-source product acceptance open.

This K4a section supersedes only the earlier K4 unguarded snippets prospectively. Historical K4 source/tracking evidence is retained in the canonical record's k4_history and the external source-k4 snapshot. K4a source cd64 is not task49's separate K3c amendment; queue root/prior49/history/order remain unchanged.


## Meaningful article rewrite v2 — planned, not released

Issue: https://github.com/lucronn/autodata/issues/300 (parent https://github.com/lucronn/autodata/issues/186). Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGN8dM`.
Plan: `docs/superpowers/plans/2026-11-05-article-rewrite-v2.md`.
Record: `docs/agents/records/2026-11-05-article-rewrite-v2.json`.

Improve meaningful source-bound article rewriting through immutable technical-prose-v2, preserving complete technical instructions, consistent ordered-document display, and readable source fallback.

The existing technical-prose-v1 opening-verb substitutions do not establish meaningful full-article coverage. Planned technical-prose-v2 uses a finite full-clause grammar, source-bound operation IDs and server-rendered complete procedural directives. The server recomputes the full candidate and all source/protected/technical/evidence bindings. Arbitrary generated prose, model-judge shortcuts and numeric-token-only safety checks are excluded. Exact clause examples and parser limits live in the plan. Existing ordered-document formatting, source fallback, atomic publication, warm-read reuse and provider-scoped identity remain the contract. v1 remains immutable; v2 requires explicit profile refresh and a new transformation key, without rewriting on read.

Unsupported ordinary prose remains source-readable with a reason and a tracked remediation owner; it does not receive full canonical-rewrite credit. An independently reviewed corpus of complete retained source documents must measure both-bank article/clause coverage and every changed technical context. The immediate bounded implementation may improve coverage, but the user outcome remains open until the entire intended purchased-dataset scope has unique consistent-format accepted rewrites. Remaining prose needs reviewed grammar extensions or a separately designed expert rewrite/approval path. Source fallback provides availability while that requirement is unresolved. Cross-bank combination is pending user clarification and not authorized here. No universal rewrite, production activation or readiness is claimed.

Concrete todo:

- [ ] Freeze representative full-document corpus and baseline coverage, with provenance and unsupported cases.
- [ ] Implement source-bound complete-clause operations and server rendering with exact technical span preservation and fail-closed validation.
- [ ] Route immutable v1/v2 profiles through durable attempts, validation, publication and explicit refresh.
- [ ] Verify corpus meaning, source fallback, dual-bank isolation, concurrency, restart and zero-call warm reads; publish exact coverage and independent review.

This is a docs-only planning checkpoint. Its committed full SHA/tree and canonical preflight result are pinned externally after commit; the coordinator owns subsequent implementation dispatch.

### v2 development implementation status (not release acceptance)

The synchronized base `694ba2af0946710ae39ef4b0f7a867766c4dceb0` passed the
canonical preflight before implementation. Development uses source-hash/path/span/
grammar-bound operation identifiers and deterministic complete directive rendering.
The initial vocabulary is finite and exercised only on synthetic regressions;
unknown components or ordinary clauses make the whole article ineligible.
Intentionally verbatim prose also uses a finite full-match safety/conditional
grammar; a marker or punctuation rule cannot exempt unparsed ordinary prose.
Unrecognized safety/conditional prose takes whole-source fallback.
All other block members, evidence and media remain immutable. v2 is explicitly
routed by the lease profile; the v1 default and validator behavior remain unchanged.
Result storage, validation and publication bind the saved v2 selector operations
back to the complete source-derived candidate under the existing locks.

No authentic retained capture package is available in this checkout. The 14-document
fixture corpus is synthetic development evidence, with no bank attribution or
realistic acceptance credit. Authentic per-bank baseline, held-out coverage, all-ten-
verb presence and independent content review remain unmeasured. The purchased-
dataset outcome and production activation remain blocked on that evidence and
unsupported-family remediation. See `docs/verification/2026-11-05-article-rewrite-v2.md`.


## Source projection v2 — development implementation, not activated

Issue: https://github.com/lucronn/autodata/issues/325. Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGUxxM`.
Plan: `docs/superpowers/plans/2026-11-05-source-projection-v2.md`.
Record: `docs/agents/records/2026-11-05-source-projection-v2.json`.

Version corrected source projections and support bounded source-only offline reprojection from retained body bytes without provider/model calls.

This is a prospective amendment to the original source-projection-v1 contract in
`docs/superpowers/specs/2026-11-03-canonical-article-lifecycle-design.md`.
The historical v1 spec and rows remain immutable. A parser fix can change readable
projection while provider bytes remain identical; raw fingerprint alone therefore
cannot identify a projection revision. Migration 041 permits v1 and v2 and keys
source revisions by `(canonical_article_id, source_fingerprint, projection_version)`.
Raw fingerprint calculation, resource content hashes and raw snapshot identities
are preserved. New capture explicitly selects source-projection-v2; historical
captures/readback expose their stored version. Same-version recapture dedupes the
source row and appends the existing immutable observation for each new capture job.

Legacy v1 transformation keys keep the exact existing four-field digest payload.
For v2, the payload additionally carries `projection_version: source-projection-v2`
and `domain: autodata:article-transformation:v2`; unknown versions reject. No stored
key is recomputed. New v2 work cannot reuse published or terminal v1 transformations.
Source persistence, observation, transformation ownership and source/canonical
pointer transition stay atomic under existing lease/generation locks. A v2 source
clears stale v1 canonical publication from the current pointer while retaining all
historical rows; readable source is available before any model work. Only matching
v2 publication/reuse may populate the canonical pointer.

The store rejects v1 capture when the locked article currently points to v2; a
database pointer guard also rejects direct v2-to-v1 downgrade. Separately authorized
rollout must drain all old workers before migration, migrate, replace every worker,
then resume. Removing the old unique pair makes old two-column ON CONFLICT SQL fail
closed. Mixed binaries and schema/binary rollback against v2 state are unsupported;
retain history and forward-fix. No read-time reprojection, automatic refresh or bulk
recapture is introduced. Existing API/current-source view remains the reader contract.

Concrete todo:

- [x] Add migration 041 allowing v1/v2, three-column source uniqueness and database-enforced prevention of v2-to-v1 current-source downgrade; extend the migration driver and its tests through 041, then verify populated upgrade and migration-driver rerun.
- [x] Carry explicit projection identity through captured/stored sources and version-aware dedupe; preserve raw fingerprint/snapshot hashes and immutable history.
- [x] Keep legacy v1 transformation-key bytes stable, domain-separate v2 keys, and atomically switch current source with stale canonical cleared.
- [x] Prove identical-byte v1-to-v2 append, repeat-v2 reuse, historical reads, terminal/published v1 isolation, readable fallback before model and stale-worker rejection; run focused and isolated PostgreSQL regressions.
- [x] Add bounded body-only offline preview/apply from verified retained bytes, with atomic exact-job source-only storage, NULL transformation key, no provider/model calls and fail-closed reconstruction tests.
- [x] Commit/push validated milestones, obtain independent exact-SHA review and synchronize verification evidence in plan, canonical doc, Issue and Project.


- [x] Repair PR #326 required CI by changing only the current GCE bundle and SQL-ledger migration-count assertions from 40 to 41 in host_provision.py, test_host_provision.py and test_host_prepare_release.py; run focused and full GCE tests plus driver/diff checks and obtain exact-SHA repair review. Track fresh final-head required CI separately as pending.

The bounded offline projector supports exactly one saved body resource (max 1 MiB,
30-second deadline), complete immutable observation context/provenance and matching
manifest/snapshot/content-addressed SHA. Reconstruct the saved SourceEnvelopeV1 and
reuse current capture through an exact-ref OfflineClient and verify-only object
sink. Preserve fingerprint, body snapshot, manifest, provenance, evidence and original
captured_at. Missing/extra/optional resources, discovered images/assets, identity or
hash drift fail closed; no real connector/model or object write is permitted.
Preview is default and reports hashes/counts/IDs only. Apply binds explicit article,
expected revision and preview hashes; actor/reason are required. In one transaction,
lock/check current source and inactive prior job, increment generation, create/mark
and exact-claim a source-only job, append v2/observation and switch pointers. Generic
queue claim/sweeps exclude source-only jobs. Finish needs_review with nonretryable
SOURCE_ONLY_REPROJECTION, no lease and NULL transformation_key; normal future v2
refresh can still own a canonical transformation. Repeat exact apply is idempotent;
races/failures roll back the complete transaction. Historical rows remain unchanged.

Read-only stage audit proved feasibility for the retained 3853-byte Banktwo body:
current capture replay produced 29 blocks/no images with identical raw identity and
saved provenance, no provider call, S3 put or database mutation. This is not a
repaired stage article. Implementation tests, review, explicit stage apply and
browser acceptance are still required. CANARY_REQUEST_LIMIT blocks reliance on
provider refetch; offline apply does not need it.

This checkpoint authorizes bounded source/schema/tests and offline projector/CLI
implementation after committed preflight and coordinator dispatch. No live
provider/model call, stage mutation, deployment, UI/auth/payment/rewrite-model
change is authorized. Exact checkpoint SHA/preflight are pinned externally after
this docs-only commit; runtime apply requires separate authorization after review.

### Source projection v2 migration-driver scope amendment

The driver currently pins its expected migration chain through 040. The v2 plan
prospectively adds only `scripts/dev/migrate_sql.sh` and `scripts/dev/test_migrations.py`
to recognize 041 and verify ordered apply/restart behavior. Preserve ledger checks,
ordering, locking, transaction and failure semantics. All prior source identity,
offline-only implementation and separate stage-activation boundaries remain binding.

Development candidate `e45541ca2058e9fa25b70b6eace329922ee96ca5` implements the
versioned source/store and bounded offline source-only path. Local isolated
schema/migration/integration tests passed 113 cases before the final added cases;
the exact committed-candidate focused selection passed 33 cases with 45 deselected
and no skips (21.07 s). The coordinator confirmed independent exact-SHA review with
zero actionable findings; reviewer migration-driver unittests passed 25. All six
development work items are complete; fresh CI/runtime acceptance remain open. See
`docs/verification/2026-11-05-source-projection-v2.md` for run bindings and limitations.
This does not establish stage application or authenticated browser acceptance.

### Required-CI bundle-count repair gate

PR https://github.com/lucronn/autodata/pull/326 required CI failed at
https://github.com/lucronn/autodata/actions/runs/42065098477 because current GCE
bundle validation and its test expect 40 migrations while migration 041 makes 41.
Only `infra/deploy/gce/host_provision.py` and
`infra/deploy/gce/test_host_provision.py` are added to the source-projection scope
(18 total historical/current implementation paths; the active repair allowlist is
these two). Change only the two current count assertions from 40 to 41; preserve
all bundle integrity checks and historical frozen receipt collectors. The first
six development items retain prior evidence; the new CI-repair item is pending
committed checkpoint/preflight, coordinator dispatch, focused tests, exact-SHA
review and fresh required CI. This gate grants no runtime or merge authority.

### Second required-CI repair amendment — current SQL-ledger test

The first two count assertions were repaired at
`7aa196122953b3ba150f434dd10decfb5ce79a1d`. Broader GCE verification ran 559
tests with one failure/seven skips: the current real SQL-ledger test in
`infra/deploy/gce/test_host_prepare_release.py:89` still expects 40 rows, actual41;
ledger contents already matched the exact sorted manifest. Add only this test path
(three active repair paths, 19 total historical/current paths), permitting only
that current count40→41 assertion after committed preflight and coordinator
dispatch. Preserve all role/grant/ledger/refusal checks and historical receipts.
Focused/full GCE tests, review and fresh required CI remain pending; no runtime
or merge authority is added.

### Post-CI-repair evidence

Candidate `66efbf55ac3658e7a86d3adb2341b512453bb047` repairs exactly three current
GCE migration-count assertions40→41 in the gated two commits; source lifecycle
behavior and historical frozen receipts are unchanged. Failed required CI run
42065098477 traced to stale current bundle validation; broader local tests found
the same stale count in current real SQL-ledger verification. Final focused real-DB
regression passed1/no skips; full GCE559 tests OK with7 root/environment skips;
driver25 tests OK before the final test-only line. Original lifecycle113 earlier
isolated cases, exact-source-candidate33 focused/no skips and independent review
remain separately bound evidence. The coordinator confirmed independent exact-SHA repair review of `66efbf55ac3658e7a86d3adb2341b512453bb047` with zero actionable findings. Seventh local repair/review todo is complete; fresh final-head required CI, stage apply and browser acceptance remain open.
See `docs/verification/2026-11-05-source-projection-v2.md` for exact SHAs and limits.
