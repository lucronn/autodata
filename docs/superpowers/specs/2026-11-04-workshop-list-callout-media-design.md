# Workshop retained list and callout block images — provisional design

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

## Reviewed source contract

Exact K3b application/DTO/normalizer bytes and existing producer implementation files match reviewed M5; the prospective new producer observability test remains absent. All source line citations below remain M5 citations and are verified unchanged at K3b. The exact K3b planning review and retained exact-source Actions audit passed; full rollup remains failure due to external Vercel. This static equivalence is not media source admission.

## 1. Exact source finding

| Layer | Exact M5 path and lines | Finding |
| --- | --- | --- |
| Normalization | `workers/ingestion-python/src/autodata_ingestion/article_document.py:697-748` | `_list_block` converts list items to strings (701, 718-719), gathers direct images and item images (713-726), deduplicates known identities (729-738), and returns `items=clean_items` plus block-level `images` (742-748). Item-specific positioning is already flattened at this boundary. |
| Capture/rewrite coverage | `workers/ingestion-python/tests/test_source_article_capture.py:478-529` | Real normalized fixture shape includes an ordered-list item image (482), checks one captured nested image (503-508), strict validation (510), evidence provenance (511-514), and the identical image after rewrite (525-529). These are test definitions inspected, not runs credited here. |
| Public DTO | `apps/api-go/catalog_store.go:98-122` | `CatalogDocumentBlock.Images` is `[]CatalogImage` (105); `Items` is `[]string` (117). The frontend cannot expect item objects for the canonical normalized list shape. |
| Public projection | `apps/api-go/catalog_lifecycle.go:402-458` | The recursive public projection explicitly retains `items` and `images` (427), sanitizes media IDs (429-443), then decodes the same DTO (454-458). |
| Actual omission | `apps/api-go/workshop/app.mjs:487-498` | The list branch appends string/object item text and `item.images` only. It never visits `block.images`. |
| No gallery escape | `apps/api-go/workshop/app.mjs:546-584`; `workshop/catalog.mjs:151-164` | A document with blocks selects `renderBlocks`, ahead of legacy projections. Top-level images are a lookup pool, not a fallback gallery. |
| Shared affected surfaces | `apps/api-go/workshop/app.mjs:549-556,598-620,731-732` | Source and canonical documents share the article renderer. The stored-source panel also calls the same `renderBlocks`. |
| Existing contract | `docs/architecture/normalized-article-document.md:14-16,79-89,109-123` | Ordered document is authoritative; remote image fallback is forbidden; source-position illustrations must render there; verification includes image placement and provider URL leakage. |

The minimum failing input is a normalized `{type: "ordered_list", items: ["Check the pump."], images: [{asset_id: "figure-1", alt: "Pump orientation"}]}` together with top-level `images: [{id: "figure-1", url: "/v1/catalog/images/v2.figure1"}]`. The current list branch emits only `ol > li`; it silently omits the attached figure even though the authorized asset is available. `unordered_list` uses the same branch and is affected too. This is a static source conclusion, not a browser reproduction.

The dual-bank source audit independently records the same defect in `/home/corp/autodata-evidence/dual-bank-release-audit/report.md`, section “Concrete launch blockers and code boundaries”, finding 0. The current retained manifest does not contain this external audit's read-time hash; this reference is historical and not independently endorsed. Exact pinned normalization, DTO and renderer bytes independently establish the omissions. No historical fixture, API21, DTO120 or release acceptance is reclassified by this proposal.

## 2. Minimal behavior and scope

List change: immediately after `parent.append(list)` inside the ordered/unordered-list branch, iterate `block.images || []` and call the existing helper with the same resolver and alt behavior as step/list-item images:

```javascript
for (const ref of block.images || [])
  addImage(parent, find(ref), ref.alt, g);
```

Callout change: keep `aside.article-callout` and its strong label as the first grid child. Make a normal-flow `div` the second grid child, append the existing text span followed by figures to that div, then append the aside. Proposed branch body:

```javascript
const aside = element("aside", undefined, "article-callout");
const content = element("div");
content.append(element("span", block.text ?? ""));
for (const ref of block.images || [])
  addImage(content, find(ref), ref.alt, g);
aside.append(element("strong", block.label ?? "Note"), content);
parent.append(aside);
```

These snippets are proposal text only; neither has been applied. They do not introduce a generic block-media walker or a gallery. M5 `apps/api-go/workshop/styles.css:747-756` uses `grid-template-columns: max-content 1fr`; a third direct aside child could land in the label column. The chosen content div keeps all illustrations in the second column and within the safety context. A figure must not be nested inside the text span. CSS stays outside the implementation allowlist. Native browser narrow-screen/print layout remains a future observation, not a result established by this DOM design.

Required DOM order for a list between two paragraphs is `p(before), ol|ul, figure(block-image-1), figure(block-image-2), [existing source link], p(after)`. The list has only `li` element children. Block-level figures are siblings after the list, in retained `block.images` order, because the current normalizer no longer stores an item association. Do not invent an item position, add a fake list item for each figure, or reconstruct ordering from global asset order. Preserve existing object-item images inside their `li`; normalized string items remain unchanged. Duplicate references intentionally appearing in different contexts remain distinct placements; do not deduplicate globally or alter normalizer behavior.

For callouts, exact order is `p(before), aside.article-callout(strong(label), div(span(text), figure(ref-1), figure(ref-2))), [existing source link], p(after)`. Text and label render once. Missing/empty images still use the same two grid children with the unchanged label and text content; no image wrapper is added per figure.

Each referenced block-level illustration in either shape gets exactly one helper invocation, not one per global asset. Resolve through the existing `find` alias handling (`asset_id`/`image_id` against `id`/`image_id`/`asset_id`, app.mjs:448-456). An inline ref URL must never become a fallback: the resolver uses the corresponding top-level/step image pool, as existing image/step/list-item rendering does.

Accessibility: preserve native `ol`/`ul` and `li` semantics and item count. Reuse `figure`, informative `img.alt`, `figcaption` and missing-image text from `addImage` (app.mjs:417-435). A nonempty ref alt supplies both `img.alt` and a figcaption. With absent/empty ref alt, `img.alt` uses the resolved image alt or the established “Article illustration” fallback, and no figcaption is created. Missing/unsafe image rendering produces the existing missing-image paragraph inside a figure, without an img or figcaption. No new ARIA role, tabindex, focus jump or live-region announcement is needed. This bounded fix must not fabricate a complex-diagram description or assert whole-reader accessibility conformance. Validate any supplied diagram text/figure order in a later local browser observation.

Rights and security: keep `addImage`, `localImageURL`, `renewMedia`, source validation and server authorization unchanged. `localImageURL` accepts only same-origin opaque `/v1/catalog/images/v2.*` routes with no credentials/query/fragment (catalog.mjs:167-173). Missing asset mapping, missing/invalid authorized URL, unavailable assets without a URL, provider/JavaScript/data URLs, and absent IDs must use “Illustration unavailable.” with no unsafe `img` source. An image error continues through the existing bounded renewal and 401/403/410 invalidation paths (app.mjs:417-435,746-827); do not add direct fetches or retries. Server token authorization binds account/configuration/region/provider/source and canonical revisions (catalog_media_access.go:100-124). A DOM test proves helper routing and clearing behavior, not server entitlement correctness.

Source fallback: source while preparing or after failed/review-needed rewrite must render both retained shapes, keep its current origin/processing label, and preserve the Source link when available. Canonical selection, complete state, revision changes, stable-revision URL reconciliation, print availability and stored-source loading must keep their current policies. Rights/withdrawal denial may leave no readable content; this correction must not reconstruct suppressed images or source bytes.

**Exact future implementation allowlist:**

- `apps/api-go/workshop/app.mjs` — only list branch block-image emission and callout content grouping/block-image emission through the current resolver/helper.
- `apps/api-go/workshop-client.test.mjs` — production-function DOM regression harness and cases, following its existing `appSection`/`runInNewContext` technique at lines 536-544.

No CSS, new module/export, package/dependency, generated Firebase bundle, Go DTO/API, schema, capture/normalizer, provider client, rewrite/profile, identity/commerce, acceptance manifest, workflow, runtime harness, Docker/deployment or release script change is needed. Any discovered need outside those two implementation paths requires a revised gate before edits.

## 3. Combined defect coverage and limits

At M5 `_callout_block` collects direct and flattened item images into `block.images` (`article_document.py:752-811`), while the callout renderer emits only label and text (`app.mjs:467-474`). This second omission shares the list defect's image pool, resolver, helper, entry points and two implementation paths. Both are explicitly included in this revision's single prospective gate. Revision 1 did not authorize callouts; this revision still authorizes no implementation until actual combined goal/spec/todo/tracking synchronization, committed checkpoint, exact-base preflight and independent gate handoff exist.

Step-level images already have an explicit loop (app.mjs:484-485), table-cell images have one (521-522), and standalone image blocks use `addImage` (474-475). The proposed mixed-document regression protects these supported placements. No item-to-image position already flattened by normalization is reconstructed. No generic recursive media feature, other block-type correction or overall media-fidelity acceptance is inferred from fixing these two consumers.


## Required future verification

Use one test-only DOM model within `workshop-client.test.mjs`, following its production-boundary extraction at lines 536-544. Execute actual `assetID`/`imageMap`/`addImage`/`appendSource`/`renderBlocks`/`renderContent` source through `appSection('const assetID =', 'function reconcileImages(')` plus production `element` (app.mjs:54-59). Supply real imported `articlePresentation`, `localImageURL`, `sourceReferenceURL`, safe location.origin and a current generation. Do not stub `addImage`, copy a second renderer, or assert source-string presence as the regression.

The test DOM must model append with multiple arguments, document fragments transferring their children, parent/child links, sibling order, textContent, replaceChildren/replaceWith, querySelectorAll for asset images, isConnected, attributes, captured event handlers, disabled/hidden/open and dataset properties. Compare extracted primitive observations or normalized arrays to avoid VM cross-realm strict-equality traps. No fetch/image network requests occur in this model.

Use the focused family name **`article block media`** across list/callout/entry-point/renewal tests. Required cases:

| Case | Production entry and input | Required observations |
| --- | --- | --- |
| Ordered and unordered list | `renderContent`; normalized string items, two block refs, surrounding text and unrelated out-of-order global asset | Current M5 fails expected missing-figure assertions (intended red). Green preserves exact `p,ol-or-ul,figure,figure,p` order; only li list children; unchanged item count; ref order/IDs/URLs; no unrelated global image. |
| Callout, both retained origins | `renderContent`; warning/note label and text with two refs representing direct and item-flattened normalized media | Current M5 fails missing-figure assertion. Green has exactly `aside > strong + div`, with `div > span + figure + figure`; one label/text; figures stay inside aside in retained order; source link follows complete aside, then next block. No figure inside span or as a third aside grid child. |
| Mixed article | List, callout, step, table-cell and standalone image blocks, reversed pool order, same asset intentionally referenced in two contexts | Each retained placement renders once; pool order does not reorder content; repeated contextual reference appears twice; existing supported shapes remain. |
| Source/canonical and UI policy | Actual `renderArticle`, source origin with fetching/failed/needs_review processing and canonical origin with fresh revisions, both normalized shapes, conflicting legacy steps/body | Document branch renders both shapes without legacy/gallery duplication. Check real article-kind/note/print state using real `processingArticle`/`readableArticle`; do not claim that `renderContent` alone proves UI origin, note or completion policy. Fixture complete/origin fields are never changed by renderers. |
| Stored source | Actual `loadSource`, matching source revision and both shapes in response document | Source frame becomes visible with exact list/callout order and metadata. Reject changed returned source revision without replacing existing frame; invalid source URL causes no request/frame update. |
| Pool/resolver and unsafe URLs | Parameterize list and callout placements: ref asset_id/image_id, pool id/image_id/asset_id aliases; missing entry/ID/URL; unavailable image without URL; provider/javascript/data/invalid same-origin routes; credentials/query/fragment | Safe mapped asset wins; inline reference URL is ignored. Every unrenderable referenced placement uses existing missing-image text inside figure with no unsafe img src. No direct fetch fallback. |
| Exact alt/caption | Nonempty ref alt; absent/empty ref alt plus resolved image alt; neither alt; unavailable image | Ref alt becomes both img.alt and figcaption. Without nonempty ref alt, img.alt is resolved alt or `Article illustration`, and there is no figcaption. Unavailable image has only existing missing-image paragraph. Text resembling HTML remains inert textContent. |
| Compatibility/empty | Object list item with its own image plus distinct block image; absent/empty block images; callout without media | Existing item image stays within li once; block image is sibling once. Native list count/children unchanged. Empty callout preserves label/text once in exactly two grid children; no invented media/gallery. |
| Source evidence / handler | Valid review+locator/evidence on each shape | Source link follows all figures/whole aside and precedes next block; actual existing handler calls source loading only for current generation. |
| New image error linkage | Trigger actual new img's captured error listener with current/stale generation and a renewal spy | Current generation calls renewal; obsolete generation does not. This is linkage-only and does not prove actual renewal, rights clearing, server entitlement or bounded retry. |
| New actual renewal coverage | Separately execute actual `renewMedia`, `renderArticle`, `reconcileImages`, `validSourceURL` and invalidation boundary with bounded controlled request promises | Prove bounded shared renewal, stable-revision URL reconciliation including source frame, current 401/403/410 clearing, stale failure isolation and existing failure text. Exact setup below. |

For actual article UI assertions, extract `appSection('const assetID =', 'async function loadArticle(')` so the real `renderArticle` and `reconcileImages` run, along with real imported `readableArticle` and `processingArticle`. Supply document.title/body.dataset, complete reader/source-frame/print nodes, quote/vehicle.region, renderedRevision/currentArticle/sourceData, renewalUsed, and safe source review fixtures. Use distinct view_revision values when expecting replacement; use the same value when testing URL reconciliation. State observations are prospective tests, not measured product acceptance.

For stored-source tests, additionally execute `appSection('function validSourceURL(', 'function handleSourceError(')`. Supply currentArticle.id, articlePath, real uuid, requestJSON, sourceRevision/sourceData/sourceURL and source frame/reference nodes. A usable isolated-model fixture is `/v1/catalog/vehicles/v/articles/a/source?source_revision_id=11111111-1111-4111-8111-111111111111` on `https://cars.example` with matching `articlePath`; returned source.url must retain that revision. These are matching stub paths, not claims of valid live API entity IDs. Verify actual source rejection behavior and retained frame, not only two differently named renderBlocks calls.

**Renewal correction:** M5 has no existing renewMedia regression harness in workshop-client.test.mjs. Its lines 581-624 cover source-review errors, not media renewal. This revision requires a new bounded actual-function harness in the same test file; no existing renewal coverage is claimed. Extract `appSection('async function renewMedia(', 'async function library(')` in addition to actual renderArticle/reconcile/validSourceURL above. Supply renewalUsed, renewal, renewalFailures Set, renderedRevision, currentArticle, sourceData/sourceURL, navigation generations, requestArticleJSON/requestJSON, $, element, and actual `clearProtected`/`invalidate` extracted with `appSection('function clearProtected(', 'async function operation(')`. Initialize every state field reset by clearProtected and all its target nodes; actual invalidate calls navigation.clear. Supply show/status spies solely to observe those UI calls, not to simulate protected-content clearing.

Bounded renewal scenarios: (1) defer one requestArticleJSON; dispatch two current image errors and assert one shared article request; resolve same revision with replacement authorized URLs and assert actual renderArticle/reconcile marks replacements and updates both images; third error after completed renewal makes no second article request and uses existing retry text; (2) provide sourceData/sourceURL plus matching source revision, assert one controlled source request and actual source-frame URL reconciliation; changed returned source revision leaves failed image unavailable; (3) reject the current article renewal with each 401/403/410 and assert actual invalidate empties protected article/source nodes and navigation generation, with welcome/error calls; (4) invalidate/advance generation before resolving or rejecting request, assert stale completion/error leaves the newly selected content untouched and does not issue source fetch or clear the new view. Use fresh harness state per scenario. This demonstrates current client policy only, not server rights authorization. Do not modify production renewal behavior to make the harness simpler.

Future commands (not executed):

```sh
node --test --test-name-pattern='article block media' apps/api-go/workshop-client.test.mjs
node --test apps/api-go/workshop-client.test.mjs
node --check apps/api-go/workshop/app.mjs
```

Then `go test ./...` from `apps/api-go` verifies embedded asset/build and existing Go boundaries; record any ordinary skipped fixture roots honestly. Run `git diff --check` and compare `git diff --name-only "$GATE_SHA"` against the two implementation paths plus six authorized gate paths; no CSS/package-lock/generated asset or unrelated changes. Do not run providers, Compose, paid fixtures, API21/DTO120/final180 profiles or application runtime for this unit-scoped change. Required broader repository checks discovered during execution remain required, but cannot authorize live work.

Retain red exact SHA, command/exit and missing-figure assertions for both list and callout against frozen M5 production bytes. A harness failure is not intended red. Then record green exact SHA, focused/full counts/skips, syntax/build/diff results and independent source review. One coherent test/fix milestone can include both consumers after red evidence is retained; commit/push cadence follows AGENTS and separate coordinator authorization. Completion tracking stays code-only, with accepted-case credit zero.

A real browser observation of native accessibility-tree list item count, callout second-column/narrow-screen grouping, diagram order, print layout and stored-source appearance remains separately authorized work. A toy DOM cannot establish those results or full assistive-technology usability. Keep product acceptance items requiring them open. This report grants no runtime/browser authority.



## K4 tracking and CI checkpoint evidence

Status: synchronized tracking contract (external package awaiting committed checkpoint). Issue186 comment `https://github.com/lucronn/autodata/issues/186#issuecomment-6646734485` and Project8 Source pointer were read back at `2026-11-05T01:06:29Z`. Selected planning base K3b `a788f110e57de13b1b876df0e148df4705db591e` (tree `9a3d2e449c42085a384950118e9c7c7a28bbb873`), exact planning-checkpoint review PASS; exact-source Actions audit PASS. Full check rollup remains failure due to external Vercel. K4 SHA/tree unknown; implementation/preflight/operational/release authorities remain false; accepted-case credit 0.

Canonical core status is `synchronized` for the literal goal, five todos and path contract. The external package does not constitute committed K4 or a passing implementation gate. All 48 authority booleans stay false; factual tracking readback and source-only CI observations do not grant new action authority. The coordinator explicitly admitted exact K3b as source for the six-document K4 planning checkpoint only; code/runtime/acceptance/release authority remains false.

Tracking before snapshot: `/home/corp/autodata-evidence/article-media-k4-before-tracking.json`, SHA-256 `dcae6d1cff722fe1fc42a2065b2e1bc5c605f2a150d2398efa93a8df88929295`. Tracking after snapshot: `/home/corp/autodata-evidence/article-media-k4-after-tracking.json`, SHA-256 `e326e6f387ec8b8dd9b4a236511e7d470b700476ba1feef83b5bf58ac2261229`. Exact added Issue comment SHA-256: `4103436ee9185599ab5d71ce93f9aa2bf08d7ff9304cd5db87dd8ca2fabeb286`. Project Source pointer SHA-256: `411f7b8cb52202960f155ad2df89829f593c5921183e4d7e0195009bd9de3421`. Independent retained-snapshot verification: `/home/corp/autodata-evidence/article-media-k4-ci-rebind/tracking-readback-verification.json`, SHA-256 `6f2330c2a6b15998c3fe8954482d670c0310d12153a1342708baed3899cc62f6`. Issue body, all 229 prior comments and other Project fields were preserved; the prior Project Source field is archived verbatim in the before snapshot. Historical proposed/unverified wording in the additive comment describes preparation time and is superseded for factual readback only by these receipts.

Source-only Actions receipt: `/home/corp/autodata-evidence/api21-k3b-ci-final/receipt.json`, SHA-256 `ef2689c464617b84a6ad0a671bc3c2932d345a81714774b58eaf517475cdbfe6`. Push run https://github.com/lucronn/autodata/actions/runs/41943766277 checked out exact K3b `a788f110e57de13b1b876df0e148df4705db591e`. PR run https://github.com/lucronn/autodata/actions/runs/41943811298 checked out `0e7e6050a0588d19870dd95c2410c343ef591f5a`; its parents are `046b141f80dbb0a28bfeb3e0ab7f9635f4ab349c` and K3b. Both runs completed successfully; the source and merge trees equal `9a3d2e449c42085a384950118e9c7c7a28bbb873`. The full check rollup remains failure because external Vercel reports `Deployment rate limited — retry in 24 hours.`; the cause is not independently established. Cursor Bugbot is neutral. No wholly green rollup, media CI authority, acceptance or release credit is claimed.

K4 SHA/tree, implementation base, execution gate and branch assignment remain null. Preflights have not run. The coordinator must recheck source/queue concurrency, preserve the coordinator admission limited to six-file planning materialization, commit and externally seal actual K4, pass standalone and nested canonical preflights at exact K4, obtain independent exact-K4 review and issue explicit two-path implementation dispatch. No code or runtime work is authorized by this external package. The prior K3b package PASS covers its original six hashes only; new synchronized bytes require independent exact-K4 review.
