# Legacy article introduction rendering

Goal: Preserve nonduplicated legacy article introduction/body text before usable structured steps while retaining authoritative-document precedence and safe text rendering.

Issue https://github.com/lucronn/autodata/issues/433; Project https://github.com/users/lucronn/projects/8.
Depends on PR #432 exact9f73f1426101f18020ef4d29969f05d29da5039a/tree4f3558278bb65cfa483c3c3ffc54d60580f2166a; parentc9913113078e21bacaf4ea506770ad9216592092.

Todo:
- Document retained source/projection shapes and exact duplicate/ambiguous legacy-body policy; keep authored M2A fixture unchanged.
- Add red-first client renderer regressions for intro plus steps, numbered and unnumbered replay, ambiguity, document precedence, partial/empty data, image/order preservation and inert markup.
- Implement the bounded presentation helper and render leading blocks before structured steps through existing safe DOM constructors.
- Run complete client/demo tests, syntax/diff checks and a bounded offline sandboxed-browser probe; commit/push and open dependent PR for root review without merge/deploy.

Plan docs/superpowers/plans/2026-11-15-workshop-legacy-article-intro.md; record docs/agents/records/2026-11-15-workshop-legacy-article-intro.json.

Status: synchronized planning, implementation pending. Legacy body content distinct from usable structured steps must remain visible as safe introductory text before steps. Ordered document blocks retain priority; numbered and exact full unnumbered step replays must not duplicate rendered steps. Unmatched/ambiguous text is preserved, without semantic guessing. See plan for exact projection, fallback and acceptance boundaries.
