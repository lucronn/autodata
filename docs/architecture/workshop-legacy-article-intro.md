# Legacy article introduction rendering

Goal: Preserve nonduplicated legacy article introduction/body text before usable structured steps while retaining authoritative-document precedence and safe text rendering.

Issue https://github.com/lucronn/autodata/issues/433; Project https://github.com/users/lucronn/projects/8.
Depends on PR #432 exact9f73f1426101f18020ef4d29969f05d29da5039a/tree4f3558278bb65cfa483c3c3ffc54d60580f2166a; parentc9913113078e21bacaf4ea506770ad9216592092.

Todo:
- Document retained source/projection shapes and exact duplicate/ambiguous legacy-body policy; keep authored M2A fixture unchanged.
- Add red-first client renderer regressions for intro plus steps, matched replay, unrelated/mismatched numbered lists, unnumbered replay, ambiguity, document precedence, partial/empty data, image/order preservation and inert markup.
- Implement the bounded presentation helper and render leading blocks before structured steps through existing safe DOM constructors.
- Run complete client/demo tests, syntax/diff checks and a bounded offline sandboxed-browser probe; commit/push and open dependent PR for root review without merge/deploy.

Plan docs/superpowers/plans/2026-11-15-workshop-legacy-article-intro.md; record docs/agents/records/2026-11-15-workshop-legacy-article-intro.json.

Status: numbered-body correction implemented; dependent PR435 awaits root review/integration. Legacy body content distinct from usable structured steps must remain visible as safe introductory text before steps. Ordered document blocks retain priority; numbered and exact full unnumbered step replays must not duplicate rendered steps. Unmatched/ambiguous text is preserved, without semantic guessing. See plan for exact projection, fallback and acceptance boundaries.

Implementation keeps only proven introductions before usable steps: numbered compatibility text contributes leading blocks only after complete count/order/ordinal/text replay identity is proved; otherwise preserve the whole body through leading-text parsing; unnumbered compatibility text loses only an exact whitespace-token suffix matching all displayed steps or all their instructions. Exact case/punctuation match is required, longest replay first. Distinct unmatched prefixes remain visible. A partial/near-match overlap is deliberately preserved, so the helper does not claim semantic deduplication. Authoritative document blocks and partially unusable-step/body fallback retain priority. Rendered introductory text uses the existing renderBlocks/element textContent constructors; no HTML parsing or data mutation.

Verification: twelve new client helper/actual-renderer regressions failed before implementation; all299 client/demo tests now pass, as do three syntax checks and diffcheck. Offline real sandboxed Chromium145 at1440/390 widths reproduces missing intro on source9f73 and shows the corrected intro before steps, exact replay deduplication, document precedence and inert HTML-like content with zero requests/console/page errors. This is authored native-DOM evidence, not application CSS/PG/S3/Firebase/payment or M2A runtime acceptance. See docs/verification/2026-11-15-workshop-legacy-article-intro.md.

The original M2A authored body and body-visible assertion remain intact. Its held package remains unstarted and unseeded until the protected source integration/gate/package review completes. No deployment, provider calls, Docker operations or M1/M2A mutations belong to this task.

Root review amendment: preserve unrelated numbered body ordinals and full text through legacyLeadBlocks rather than parts-only step blocks. Add actual-renderer regressions; earlier299 tests do not prove this guard.

Correction: amendment checkpoint8e2c187a passed exact preflight before correction. Five unrelated/mismatched numbered-list renderer tests failed before the guard; all305 client/demo tests now pass. Require full count/order/ordinal/text replay identity. Unmatched body uses legacyLeadBlocks, retaining literal ordinals/parts instead of incompatible parts-only step blocks. Native-DOM probes at1440/390 reproduce prior loss and confirm preservation, with zero requests/errors.
