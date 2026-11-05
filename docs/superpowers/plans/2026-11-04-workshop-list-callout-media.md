# Workshop list and callout media Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task only after the canonical gate passes and explicit dispatch exists. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render retained ordered-list, unordered-list and callout block images in Workshop source, canonical and stored-source views through the existing authorized-media helper, preserving native list semantics, callout context, source evidence and rights fallback.

**Architecture:** Keep the existing resolver and authorized-media helper. Emit retained list figures as siblings after native lists, and group callout text and figures in the second grid child.

**Tech Stack:** Existing browser JavaScript and Node's native test runner; existing Go embedded assets. No dependencies.

**Spec:** `docs/superpowers/specs/2026-11-04-workshop-list-callout-media-design.md`

## Global constraints

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

## Task 1: Admit corrected source and synchronize the six-document checkpoint

- [x] Verify exact pinned K3b SHA/tree, retained exact-planning-review PASS and source-only Actions PASS; retain coordinator admission restricted to six-document planning checkpoint. Independently compare retained source-manifest bytes and queue49/root/prior task objects against K3b, preserving corrected task49 and prior48. Recheck current source/queue concurrency before materialization and rebuild if any history changed.
- [x] Verify Issue186/Project8 ownership and literal combined goal/todo/path contract readback; preserve Issue body/all 229 prior comments and other Project fields, and archive prior Project Source field verbatim. Retained before/after snapshots and independent checks support `status: synchronized` in the canonical core; no implementation authority is granted.
- [ ] Materialize exactly the six gate files after review, preserving all original queue root fields/prior objects/order. Commit and promptly push a coherent documentation milestone to the coordinator-assigned branch when authorized. Seal actual K4 SHA/tree externally after commit; no self-SHA rewrite.
- [ ] Extract committed standalone core, nested `pre_implementation` and policy from exact K4; run both canonical preflights with that external base SHA. Retain commands, exits, JSON and exact SHA. Require errors=[] plus independent exact-K4 review and explicit two-path code dispatch. Current record is expected blocked; do not run preflight as a claimed passing gate now.

## Task 2: Red tests, bounded rendering correction and verification

**Files:** Modify only `apps/api-go/workshop-client.test.mjs` and `apps/api-go/workshop/app.mjs` after Task 1.

**Interfaces:** Execute actual `element`, `assetID`, `imageMap`, `addImage`, `appendSource`, `renderBlocks`, `renderContent`, `renderArticle`, `reconcileImages`, `validSourceURL`, `loadSource`, `renewMedia`, `clearProtected` and `invalidate` from production through existing `appSection`/`runInNewContext`. Supply complete state and controlled requests; never stub renderer/helper/protected clearing.

- [ ] Add the `article block media` production-function DOM family described in the canonical spec. Observe both normalized list and callout missing-figure assertions fail against pinned unchanged M5/K3b bytes before implementation. Retain red SHA, command, exit and assertion logs; harness errors are not intended red.
- [ ] After `parent.append(list)` in the ordered/unordered branch, add only:

```javascript
for (const ref of block.images || [])
  addImage(parent, find(ref), ref.alt, g);
```

- [ ] Replace only callout content assembly with:

```javascript
const aside = element("aside", undefined, "article-callout");
const content = element("div");
content.append(element("span", block.text ?? ""));
for (const ref of block.images || [])
  addImage(content, find(ref), ref.alt, g);
aside.append(element("strong", block.label ?? "Note"), content);
parent.append(aside);
```

- [ ] Run focused/full Node, JS syntax, embedded Go and whitespace/scope checks below; inspect exact diff. Treat an out-of-scope production failure as a separate finding requiring revised gate. Commit and promptly push validated coherent test/fix milestones when authorized by the coordinator; retain red evidence before committing green results.

```sh
node --test --test-name-pattern='article block media' apps/api-go/workshop-client.test.mjs
node --test apps/api-go/workshop-client.test.mjs
node --check apps/api-go/workshop/app.mjs
```

Run `go test ./...` from `apps/api-go`, `git diff --check`, and compare `git diff --name-only "$GATE_SHA"` against exactly the six gate paths plus two implementation paths. GATE_SHA is externally sealed K4, never a later implementation HEAD. Record all ordinary skips and failures honestly.

## Task 3: Exact-code review and code-only closure

- [ ] Obtain independent exact-code review with source hashes and actual measured logs. Record browser/accessibility/product-acceptance limits and keep their work open.
- [ ] Reconcile Issue/Project/document evidence without claiming browser, native accessibility-tree, narrow-screen/print, server-entitlement or current-source acceptance from a test DOM. All operational/release authority remains false and accepted-case credit remains zero.

## Detailed test obligations


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
