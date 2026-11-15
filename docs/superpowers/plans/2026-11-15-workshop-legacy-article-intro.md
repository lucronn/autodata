# Preserve legacy article introduction before structured steps

Goal: Preserve nonduplicated legacy article introduction/body text before usable structured steps while retaining authoritative-document precedence and safe text rendering.

Issue https://github.com/lucronn/autodata/issues/433; Project https://github.com/users/lucronn/projects/8.
Depends on PR #432 exact9f73f1426101f18020ef4d29969f05d29da5039a/tree4f3558278bb65cfa483c3c3ffc54d60580f2166a; parentc9913113078e21bacaf4ea506770ad9216592092.

Todo:
- Document retained source/projection shapes and exact duplicate/ambiguous legacy-body policy; keep authored M2A fixture unchanged.
- Add red-first client renderer regressions for intro plus steps, matched replay, unrelated/mismatched numbered lists, unnumbered replay, ambiguity, document precedence, partial/empty data, image/order preservation and inert markup.
- Implement the bounded presentation helper and render leading blocks before structured steps through existing safe DOM constructors.
- Run complete client/demo tests, syntax/diff checks and a bounded offline sandboxed-browser probe; commit/push and open dependent PR for root review without merge/deploy.

## Evidence and source constraints

Read-only inspection of actual articlePresentation/renderContent on9f73 shows two usable steps, no document blocks, a nonempty authored body and no rendered body. Both headings/instructions remain visible. The omitted M2A body identifies a fictional/no-real-vehicle fixture and is not repeated by its steps; retain it and the original body-visible browser assertion. No M2A files, immutable pins, fixtures, stores or runtime may be changed by this task.

Owning source/projection inspection, without reading licensed provider content: procedure_normalize._body_from_steps generates numbered action/instruction body; article_document.project_ordered_document can produce unnumbered joined text alongside structured steps. Ordered documents already supersede these compatibility fields. Existing legacyArticleBlocks segments numbered bodies into leading headings/paragraphs/callouts and numbered step blocks. Current partly unusable steps deliberately fall back to the body. All retained source examples/tests used here are authored repository fixtures; no provider fetch/capture or licensed content is needed.

## Decision

Add a small pure presentation helper used only for usable structured steps with no authoritative document blocks. If legacyArticleBlocks recognizes numbered steps, suppress that replay only when the complete numbered sequence matches actual structured steps in count, order, ordinal and exact whitespace-normalized displayed text (action-or-heading plus instructions, or instructions-only). Retain only its leading blocks before the first matched step. If any numbered item differs, preserve the entire body through legacyLeadBlocks; never pass legacy parts-only step blocks to the structured renderer. This reuses existing number/decimal handling. For an unnumbered body, remove only a complete exact whitespace-token suffix replay of the displayed structured sequence, checking both action-or-heading plus instructions and instructions-only. Match case and punctuation exactly; choose the longest matching sequence. Return the unchanged preceding body through existing legacy block parsing. A body equal to the replay yields no introduction. A distinct unmatched body is retained; never guess near matches, use fuzzy deletion, reinterpret HTML, mutate article objects or rewrite stored/provenance content.

Ambiguity: an unnumbered body with partial, interleaved, differently punctuated or reordered overlap cannot be safely reconciled by this bounded projection rule. Preserve unmatched text even if some words repeat; an authoritative ordered document is the durable representation for exact interleaving. Unrelated, differently numbered, reordered, partial or conflicting numbered bodies remain intact as body text. The helper cannot infer that a numbered warranty/storage list is a procedure replay. Test and document these limits rather than claiming semantic deduplication.

Render introductory blocks with existing renderBlocks/element textContent constructors before the existing structured-step loop. Preserve authoritative document precedence, usable-step/image behavior, body-only and partially unusable-step fallbacks, origin/completion/authentication policy. No innerHTML or new DOM sink, dependency, schema/API contract, credential/service, CSS or backend change.

## Red-first acceptance

Add client helper and actual renderContent harness tests before implementation: distinct body plus two steps retains intro once before ordered headings/instructions; numbered body retains leading heading/callout/paragraph and renders steps once; unnumbered body equal to complete step replay is omitted; intro plus exact replay retains intro only; action+instruction and instructions-only shapes, whitespace normalization, punctuation/case ambiguity retained, decimals/unrelated numbers, empty body, partial-step body fallback, document dominance, no input mutation, image IDs/order retained, HTML-like intro/callout stays inert. Run whole client/demo suite, node syntax checks and diffcheck. Use a bounded offline real Chromium sandbox probe with authored data/actual functions and no service/provider requests as supplementary DOM evidence; it is not PG/S3/M2A acceptance.

## Exact implementation allowlist

- apps/api-go/workshop/catalog.mjs
- apps/api-go/workshop/app.mjs
- apps/api-go/workshop-client.test.mjs
- docs/architecture/workshop-legacy-article-intro.md
- docs/verification/2026-11-15-workshop-legacy-article-intro.md

Plan and synchronized record are docs-only gate files. Create/push the checkpoint and run exact pre_implementation.py before editing the above implementation files. Keep a separate branch/worktree on the named UI head, then open a dependent PR for root review. No merge/deploy; integration/rebase only after coordinator supplies the protected #432 base. No Docker startup/build/cache pruning or M1/M2A mutation.

## Root review amendment before correction

Root found that treating every numbered body as replay could discard an unrelated numbered list, and parts-only legacy steps are incompatible with renderBlocks step fields. Exact numbered matching and actual-renderer preservation tests are required. Synchronize this docs-only checkpoint and rerun exact preflight before correction. Earlier299-test/browser receipts are historical and do not prove this new guard.
