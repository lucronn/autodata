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

### Mercury-2 output budget for canonical publication

Goal: let the existing canonical rewrite client use the exact Mercury-2 model
through an Inception-compatible endpoint without an unbounded provider credit
reservation. The official Inception endpoint and `mercury-2` model remain the
defaults. Each completion request declares `max_tokens=8192`; operators may
set `INCEPTION_MAX_TOKENS` to an integer from 1 through 32768. The model key and
optional alternate endpoint remain private runtime configuration, never source
control. This bounded request does not change source rights, transformation
ownership, validation, or atomic canonical publication.

Plan: `docs/superpowers/plans/2026-11-05-mercury2-output-budget.md`.
Tracking: https://github.com/lucronn/autodata/issues/327 in
https://github.com/users/lucronn/projects/8. Parent release issue:
https://github.com/lucronn/autodata/issues/186.

Concrete todo:

- [x] Commit the synchronized planning checkpoint and pass its exact-base preflight.
- [x] Add failing payload/invalid-setting tests, then implement the bounded request.
- [x] Verify and push the focused change.
- [ ] Review the exact implementation SHA and pass required CI.
- [ ] Verify a live bounded Mercury-2 TEST call and separately recover terminal
  model jobs before claiming any published canonical article.

Local Mercury-2 evidence: exact-base preflight at
`529af7a1db7fbbd384692d7ff5d17721fad07e5e` passed; the focused tests failed
before the client change and then passed (16 tests, 3 subtests). Full ingestion
worker verification passed (895 tests, 143 subtests, 239 skips) using the pinned
Stripe SDK in a temporary test environment; `git diff --check` passed. Live
provider acceptance remains pending.

### Dual-bank source media bindings

Goal: place declared source images at their actual article positions without
changing the provider's raw body, hash, revision, rights, or provenance. The
optional authenticated connector `asset_bindings` sidecar maps an exact decoded
HTML image URL to a declared opaque `resource_ref`. AutoData validates the
bounded mapping and binds only exact URL matches; malformed, conflicting, or
unknown mappings fail closed. Repeated occurrences of one URL keep their
original positions. No positional guess or detached duplicate gallery may
substitute for a valid source position. The existing source fallback remains
visible until canonical publication completes.

The consumer accepts at most 128 bindings with exactly `source_url` and
`resource_ref`, each a nonempty string of at most 2048 characters without control
characters. Source URLs are unique and refs must be declared in the same text
resource's `asset_resource_refs`. Matching uses HTMLParser's decoded attribute
value directly, without URL normalization or a second HTML entity decode.
Bindings remain in body provenance and nonempty bindings contribute to source
identity in source-URL order; the raw body hash remains unchanged. A changed
sidecar can therefore create a new transformation key and another rewrite under
the existing lifecycle. Canonical reuse or historical backfill needs separate
work; deployment canaries should use new or unpublished articles.

Plan: `docs/superpowers/plans/2026-11-05-source-media-bindings.md`.
Tracking: https://github.com/lucronn/autodata/issues/331 in
https://github.com/users/lucronn/projects/8; parent release issue #186.

Concrete todo:

- [x] Commit the synchronized planning checkpoint and pass exact-base preflight.
- [x] Test and implement the AutoData bounded, exact-URL consumer.
- [ ] Review and merge the consumer before deploying connector producers.
- [ ] Verify Bankone and Banktwo producer refs and Banktwo binary image route.
- [ ] Run bounded real dual-bank image-order and fallback canaries.


## Full article drafting with exact-hash content review

Planning checkpoint only. Issue https://github.com/lucronn/autodata/issues/333; parent https://github.com/lucronn/autodata/issues/186; prior bounded grammar https://github.com/lucronn/autodata/issues/300; Project https://github.com/users/lucronn/projects/8. Plan: `docs/superpowers/plans/2026-11-05-full-article-review.md`; record: `docs/agents/records/2026-11-05-full-article-review.json`.

**Goal:** Publish uniquely rewritten complete dual-bank articles once through full-prose drafting, exact-hash human content approval and durable review resume, serving source until publication.

The finite v2 operation selector cannot write general full prose. The retained authentic sample contains 20 articles per bank; the maintenance-XML replay adapted40, strict-valid24 and v2-eligible0, with16 document-invalid,16 unsupported and8 not-applicable. Its report SHA256 is `42f2ccc7245c1cb6657a56d64521a096e790e3ff72605a6386bbba2f09ee1f2b`. A separate offline media-fallback replay makes40 strict-valid by marking182 image occurrences unavailable; it does not prove genuine asset retrieval or durable source identity. This post-development sample is biased, and its alternating holdout is not a pre-tuning holdout. Historical v2 synthetic and initial absent-corpus evidence remains historical.

### Selected bounded design

Add immutable explicit `full-prose-review-v1`; retain v1/v2 definitions and defaults. A full-prose model drafts every ordinary prose leaf and exactly one concise source-bound introduction. The introduction supports table/specification articles without changing technical tables. The server constructs its stable block ID, evidence references and first-block position; the model supplies text only. Original blocks retain relative order, IDs, nesting and all protected members. Existing ordered-document rendering and same-origin media remain usable. No schema migration, new public endpoint, review UI, rewrite-on-read, bank joining or bulk refresh is part of this slice.

The response is `{"introduction":"...","replacements":[{"block_id":"...","path":"...","action":"rewrite|retain","text":"...","reason":"..."}]}`. Rows cover every paragraph/step/list-item text leaf in deterministic source order, once. Safety callouts, headings, tables/cells, title, media, links, evidence and unknown blocks remain byte-preserved. `retain` is for exact technical labels, safety/technical wording or nonprose and requires a concrete justification; the model's classification is a proposal for human review, never completeness authority. Skipped rows, empty/case/whitespace-only `rewrite` actions, changed `retain` text, unjustified retentions and model-supplied structure are rejected. Ordinary prose retained under a nonblank model justification still requires explicit human rejection or justified acceptance; the machine cannot establish its semantic classification. The independent reviewer must accept every rewrite, every retention and the introduction in full source context. An introduction alone does not earn complete-rewrite credit for an article that contains ordinary prose.

Deterministic checks enforce exact JSON shape/types, complete row coverage, source-bound skeleton/evidence/media/order, numeric/unit/identifier guards, nonblank text, meaningful changes and existing strict ordered validation. Introduction technical tokens must be source-supported. Freeze the conservative technical-token guard in profile tests: preserve per source leaf, in order, numeric strings (ASCII/Unicode digits, decimal/group separators, signs, comparators and range markers), immediately attached or whitespace-separated unit strings, mixed letter/digit identifiers, and source reference/link targets. No numeric conversion or technical-token relocation between leaves. In an introduction, each technical token must appear verbatim in the source document. Ambiguous tokenization takes literal leaf retention and mandatory human review; any later token-grammar change requires a new immutable profile. Ordinary words including component names can escape this guard and still require human review. These checks establish mechanical integrity only; they do not prove parts, modality, negation, conditions, attachment or meaning. No model judge or token score can approve content. Prompt<=200KiB and response<=1MiB remain unchanged.

### Draft, review and publication

Use existing attempts/revisions and immutable `canonical_article_reviews`; no new tables. After structural validation persist the unpublished candidate, set the existing job to `needs_review` with explicit `CONTENT_REVIEW_REQUIRED`, clear its lease and mark a versioned review checkpoint. Source remains reader-authoritative. Persisted model response and attempt metadata remain original evidence. Ordinary ensures and reads cannot revive the review wait or call a model.

One local database-operator CLI exports source/candidate/review manifests, then records approve/reject with expected article identity, source revision, job generation, profile, candidate revision and source/candidate hashes. Reviewer identity comes from an operator-controlled external allowlist and is separate from the model/drafting actor; this is a privileged local administrative boundary, not public authentication. Approval is a human action after independent full-document technical review. Automated fixtures may use clearly labelled synthetic reviewers and earn no real content credit. The CLI stores versioned JSON in the existing review `reason` containing exact bindings, content-completeness attestation, retained-path reasons and a nonblank human rationale. Production commands must not accept a synthetic reviewer or a model-produced approval.

An optional corrected replacements document may accompany review. Under job/article/candidate locks in the same order as `_lock_transform`, check the expected original candidate hash, reconstruct and structurally validate corrected prose with the same renderer, update only the unpublished candidate/projections/derived hashes and record original/final candidate hashes plus correction provenance in review metadata. Keep the original model attempt/response immutable. This permits a human to repair rejected drafts without changing source or inventing a new transformation identity. Historical decisions remain append-only. Any correction changes the candidate hash and invalidates all earlier approvals. Published candidates cannot be corrected by this command. Rejection leaves source selected and the same transformation budget; later explicit independent correction/review may resolve it.

Approval and pending-resume scheduling commit atomically. A distinct explicit review-resume claim obtains a new fenced lease for this existing job/candidate, without a model request, new rewrite attempt, retry-count reset or model-attempt increment; it works even when all three model delivery attempts were consumed. Exclude exact-bound saved review-resume candidates from the model-attempt exhaustion sweeper and model ambiguity marking on reclaim; revalidate approval on every lease recovery. Normal model retry/dead-letter semantics remain unchanged. Recovery after approval uses the persisted candidate. Recheck current generation/source/profile, structural report, raw model attempt and correction provenance, and the latest exact-bound approval under publication locks. Stale, rejected, missing, forged or other-article approvals block publication. Atomic pointer/job/outbox publication remains one event per transformation; its review status is APPROVED for this profile. v1/v2 retain their existing review and publication semantics.

### Measured completion boundary

Freeze a private acceptance manifest of all intended article identities/source hashes, including both banks and unsupported/table-only families, before tuning. Begin with retained40 without eligibility filtering; add separately disclosed authentic procedural articles if broader scope is needed. Every article in that frozen intended scope needs its own complete, materially rewritten and independently approved candidate; unique identities or introduction-only edits do not prove unique content. Independently check duplication of rewritten prose across the scope and resolve any copied/generic candidates. Record accepted/total and failures by bank/family. All introduced facts, action/condition/negation/modality, components/tools/values/units, references/applicability and media context require source comparison. Unavailable source media remains explicit and earns no recovered-media credit. No semantic completeness or purchased-dataset completion is claimed until every intended article passes. Source fallback is temporary availability.

A separately authorized bounded live Mercury test, externally provided credential and exact deployed worker configuration are prerequisites to real model/publication acceptance. This planning gate grants no provider calls, credentials changes, activation, deploy or release approval. A secure existing credential source has been verified separately; the running rewrite worker still lacks that configuration. Credential delivery to the intended runtime and live accepted rewrites remain unverified. No credential location or value belongs in this record.

Concrete todo:
- [ ] Freeze intended dual-bank source scope, hashes and retained40 baseline.
- [ ] Add immutable full-prose-review-v1 drafting and complete document integrity checks.
- [ ] Persist review waits; add exact-hash human approve/reject/correct and zero-redraft resume.
- [ ] Enforce approval at publication; test races, budgets, recovery and zero-call warm reads.
- [ ] Verify isolated lifecycle and every authentic final article; separately authorize live Mercury acceptance.


## Automatic permanent article rewriting

User requirement recorded on2026-11-06 supersedes mandatory manual article review for newly selected automatic work: Automatically publish one materially unique, consistent-format canonical rewrite per bank-scoped source article, retain the accepted revision permanently, and serve stored source until the rewrite is ready; no manual article review.

The additive immutable profile `full-prose-auto-v1` uses the existing source-first lifecycle and consistent ordered document. It rewrites ordinary paragraph, step and nested-list prose and adds one useful source-bound introduction, preserving original technical values, safety blocks, tables, headings, links, media, evidence and relative order. Invalid or incomplete candidates retain source availability. Mechanical validation and saved-response reconstruction gate automatic publication; they do not assert semantic proof or human approval. Metadata and publication review status remain truthful.

The accepted canonical revision is permanent and reused for subsequent customer reads without another bank or model request, expiry, rescheduling or rewrite-on-read. Concurrency and restarts join the existing durable transformation. New descriptor registration selects the automatic target explicitly. Existing records, stored sources and published revisions are preserved; a bounded explicit selection/expected-source refresh may opt existing articles into the new target. No bulk or automatic refresh follows from registration or reading.

Historical `full-prose-review-v1` continues to require its original exact-hash human approval when explicitly selected; its immutability does not impose review on the new automatic profile. The prior full-review plan and its open human acceptance work describe that historical lane. This automatic successor never fabricates approval records.

Tracking: https://github.com/lucronn/autodata/issues/186#issuecomment-6679826363; https://github.com/users/lucronn/projects/8. Plan: `docs/superpowers/plans/2026-11-06-automatic-permanent-article-rewrite.md`. Synchronized record: `docs/agents/records/2026-11-06-automatic-permanent-article-rewrite.json`. Inspected base: `4513c387c900add7138330555ccfca92f74b9894`.

Concrete todo:
- [ ] Add immutable full-prose-auto-v1 prompt/render/validation using complete prose leaves, source-bound introduction and existing ordered format.
- [ ] Publish valid automatic candidates through the existing durable fenced lifecycle without human review, preserving source fallback, saved-response integrity and once-per-transformation dedupe.
- [ ] Select automatic rewriting for newly captured articles and provide an explicit bounded refresh for existing stored sources; preserve all old profiles and published revisions.
- [ ] Prove both-bank automatic publication, integrity failures retaining source, concurrent/restart reuse, and zero provider/model/schedule calls on warm reads; start and verify the working local app.


### Automatic lifecycle recovery scope amendment

Issue186 amendment https://github.com/lucronn/autodata/issues/186#issuecomment-6679877079 and Project8 Release hotfix reference were synchronized/read back by the coordinator (field length990). This adds the following exact paths to the implementation allowlist:

- `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py`
- `workers/ingestion-python/tests/test_source_job_persistence.py`
- `workers/ingestion-python/tests/lifecycle_support.py`

Automatic-profile nonretryable mechanical failures enter `dead_letter` with source still readable, never a manual-review wait. A successfully saved automatic candidate may reclaim a fenced publication lease after its model-attempt budget is exhausted, without incrementing or resetting that budget, invoking the model, or reviving a failed/ambiguous result. Existing manual-review and legacy retry behavior remains intact. Tests must cover final-attempt restart/publication, failed candidate exclusion and stale leases.

New production descriptor registration defaults explicitly to the automatic profile. The shared test insertion helper explicitly requests historical `technical-prose-v1` unless a test selects another profile, preserving historical test coverage. The production upsert accepts an explicit profile only at its existing internal registration interface; HTTP clients cannot select a profile. These extra files may change only after this amendment is committed/pushed and exact-head preflight passes.


### Missing-model configuration and exact selected-job amendment

Base: `83b0b727736b36223e1859364bfeb49f67c3d93a`. Issue186 amendments https://github.com/lucronn/autodata/issues/186#issuecomment-6680123658 and https://github.com/lucronn/autodata/issues/186#issuecomment-6680125162 are synchronized with Project8 (coordinator readback length920, both comment IDs present).

Concrete todo:
- Park automatic work only after source and normalized input are durable when no model client exists; retain readable source and create no rewrite attempt.
- Exclude parked jobs from generic polling without configuration; when a client exists, resume only the same current article/job/source/generation/profile, without retry budget increment or reset.
- Recover existing `MODEL_NOT_CONFIGURED` dead letters only with zero rewrite attempts and exact ownership. Never revive failed or ambiguous model output. Historical profiles retain their behavior.
- Add optional exact `job_id` filtering to existing claim/worker functions, including recovery and exhausted-job sweep, so operators can capture/park/resume selected preview jobs without draining unrelated work. Verify repeated absent-key polling, configured restart, selection isolation and stale ownership using focused PostgreSQL tests.

Only already-allowed `article_lifecycle.py`, `source_job_persistence.py` and focused worker/job tests change. No schema/API/UI/credential/payment/deployment changes. Existing successful saved candidates may still publish without a model client. The model client is constructed at process startup, so configure the secret and restart before resuming. Commit/push this docs checkpoint and pass exact-head preflight before implementation.


### Historical commerce fixture scope amendment

Issue186 https://github.com/lucronn/autodata/issues/186#issuecomment-6680197528 and Project8 are synchronized (coordinator exact readback length951, link present), base `2c9ecd6bbd178e0d0b4912a3cf20d3097cbffc31`. Add only `workers/ingestion-python/tests/test_commerce_postgres.py` to the existing allowlist. Todo: (1) commit/push this docs-only checkpoint and pass exact-head preflight; (2) explicitly select historical `technical-prose-v1` in `seed_readable_source` descriptor registration to match its unchanged ensure; (3) run affected library case and focused recovery regression, no full-suite rerun; (4) push code and honest final evidence. No production implementation or commerce/payment behavior changes.
