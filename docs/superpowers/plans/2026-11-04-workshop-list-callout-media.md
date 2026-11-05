# Workshop list and callout media K4a Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans only after the canonical gate and explicit coordinator dispatch pass. Steps use checkbox syntax.

**Goal:** Render retained ordered-list, unordered-list and callout block images in Workshop source, canonical and stored-source views through the existing authorized-media helper, preserving native list semantics, callout context, source evidence and rights fallback.

**Architecture:** Preserve existing list sibling figures and callout strong+div(span+figures) layout. Guard missing reference IDs at only the two newly added block-image consumers before invoking the unchanged resolver and helper.

**Tech Stack:** Existing JavaScript, native Node test runner and Go embedded assets; no dependencies.

**Spec:** `docs/superpowers/specs/2026-11-04-workshop-list-callout-media-design.md`

## Global constraints

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


This supersedes K4's exact unguarded two-loop snippets prospectively for the P2 correction only. Original K4 documents and source identity are retained externally in source-k4; historical M5 missing-figure work is already present in cd64 and must not be replayed as new implementation work.

## Task 1: Synchronize and seal K4a

- [ ] Independently review the six proposed files and source/hash manifest; verify cd64 ancestry, exact two-file code head and report identity. Preserve queue root fields, task count/order, task49 and all prior49 objects. If another checkpoint is selected, rebuild and re-review rather than silently rebasing this package.
- [ ] Post the literal Issue/Project tracking payload only under coordinator authority, archive fresh before/after snapshots and prior Project Source verbatim, read back exact goal/six todos/guard rule/paths, and independently verify synchronization.
- [ ] Update active core, nested core and task50 status to synchronized with actual readback metadata; preserve previous K4 records as historical evidence. Materialize exactly six gate files on the coordinator-assigned branch rooted at cd64, commit and promptly push after document checks; externally seal actual K4a SHA/tree.
- [ ] Extract exact committed standalone/nested core and policy and invoke canonical `scripts.autonomy.pre_implementation.validate_record` for each at the sealed SHA. Require errors=[] and retain commands/exits/JSON; obtain independent exact-checkpoint review and explicit assigned-branch/two-path code dispatch. No earlier preflight substitutes.

## Task 2: Reproduce and fix the P2 within two files

**Modify:** `apps/api-go/workshop-client.test.mjs`, `apps/api-go/workshop/app.mjs` only after Task 1.

- [ ] Add the concrete regression cases below and strengthen the existing absent-ID fixture. Run against unchanged frozen cd64 app bytes; retain intended no-img/missing-figure assertion failures. Existing 94-case passing review and prior M5 missing-figure failures do not replace this red. ReferenceError, incomplete harness or extraction failure is not intended red.

```javascript
for (const type of ['ordered_list', 'unordered_list', 'callout']) {
  test(`article block media ${type} rejects missing IDs with a valid unrelated pool`, () => {
    const h = articleMediaHarness();
    const article = mediaArticle([{ type, items: ['Check'], text: 'Note',
      images: [{ status: 'unavailable', unavailable_reason: 'source image reference is missing' }] }],
      [{ id: 'unrelated', url: mediaURL('unrelated') }]);
    const parent = h.content(article);
    assert.equal(mediaDescendants(parent, 'img').length, 0);
    const figures = mediaDescendants(parent, 'figure');
    assert.equal(figures.length, 1);
    assert.deepEqual(mediaTags(figures[0]), ['p']);
    assert.equal(figures[0].textContent, 'Illustration unavailable.');
    assert.equal(figures[0].children[0].className, 'image-missing');
    assert.equal(mediaDescendants(parent, 'figcaption').length, 0);
  });
  for (const content_origin of ['source', 'canonical']) {
    test(`article block media ${type} rejects missing IDs in ${content_origin} article`, () => {
      const h = articleMediaHarness();
      const parent = h.render(mediaArticle([{ type, items: ['Check'], text: 'Note',
        images: [{ status: 'unavailable', unavailable_reason: 'source image reference is missing' }] }],
        [{ id: 'unrelated', url: mediaURL('unrelated') }], { content_origin }));
      assert.equal(mediaDescendants(parent, 'img').length, 0);
      const figures = mediaDescendants(parent, 'figure');
      assert.equal(figures.length, 1);
      assert.deepEqual(mediaTags(figures[0]), ['p']);
      assert.equal(figures[0].textContent, 'Illustration unavailable.');
      assert.equal(mediaDescendants(parent, 'figcaption').length, 0);
    });
  }
}
```

Use the existing exact-head `articleMediaHarness`, real production function extraction, `mediaArticle`, `mediaURL`, `mediaDescendants` and `mediaTags`; do not copy the renderer or stub addImage/find. Also replace the existing `absent ID` unavailable fixture's pool `[{ url: mediaURL('safe') }]` with `[{ id: 'unrelated', url: mediaURL('safe') }]`. Keep its inline ref URL so inline fallback remains tested. Cover explicit empty asset_id/image_id values as an additional missing-key case; all no-key and empty-key cases must yield one missing figure, no img and no caption. Existing alias tests must continue proving valid asset_id/image_id refs resolve through id/image_id/asset_id pools.


- [ ] Apply exactly the missing-ID conditional in the existing list loop and callout loop. For each ref in the new list and callout block.images loops, evaluate ref?.asset_id || ref?.image_id before find(ref). If neither is truthy, do not call find; pass undefined to existing addImage for Illustration unavailable. Keep the shared find, assetID, addImage, localImageURL, rights, renewal and other consumers unchanged.

List loop after `parent.append(list)`:

```javascript
for (const ref of block.images || [])
  addImage(parent, (ref?.asset_id || ref?.image_id) ? find(ref) : undefined, ref.alt, g);
```

Callout loop (content remains the existing second grid child):

```javascript
for (const ref of block.images || [])
  addImage(content, (ref?.asset_id || ref?.image_id) ? find(ref) : undefined, ref.alt, g);
```


The conditional is evaluated before find. Whitespace/formatter wrapping is permitted within these two calls. No shared helper, resolver, other consumer, rights, renewMedia, source handler, CSS, schema, dependency or generated asset edit is allowed. ID-bearing lookup keeps the established truthy alias semantics; no new identifier validation or fallback is introduced.

- [ ] Run focused/full checks and inspect the exact two-file diff, retaining logs and source identity.

```sh
node --test --test-name-pattern='article block media' apps/api-go/workshop-client.test.mjs
node --test apps/api-go/workshop-client.test.mjs
node --check apps/api-go/workshop/app.mjs
```

Run `/home/corp/go-sdk/bin/go test ./...` from `apps/api-go` (or a verified available Go SDK), `git diff --check`, and inspect `git diff --name-only "$K4A_GATE_SHA"` for the two implementation paths only. Retain actual counts, exits and ordinary integration skips. `K4A_GATE_SHA` is the externally sealed committed planning checkpoint that descends exact cd64, never historical K4 or a later code HEAD. Compare checkpoint-versus-cd64 diff against exactly the six gate paths. Record hashes of both exact implementation files. No tests were executed by this planning package; historical 94 focused/166 full/336 Go passing checks are prior review facts, not K4a results. Full prior tests continue to cover DOM placement, source links, safe media, alt/caption, stored source, bounded renewal, reconciliation, current rights clearing and stale generations. Do not weaken them or broaden production scope to make them pass.


- [ ] Commit and promptly push one coherent regression/fix milestone after checks and only on the assigned branch. Retain red evidence externally before green commit.

## Task 3: Independent exact-code review and bounded closure

- [ ] Obtain independent review at exact new code SHA, verify the no-key/empty-key cases and valid aliases, source/canonical actual renderArticle, original callout/list DOM and unchanged resolver/helper source hashes. Any broader defect requires separate revised scope.
- [ ] Retain fresh exact-candidate CI and update Issue/Project with measured code-only evidence. Do not call old code or plan review PASS a new result. Keep browser/native accessibility/narrow-screen/print/current-source product acceptance open, all operational/release authorities false, accepted-case credit zero.
