# Release-receipt preservation plan

Status: synchronized documentation-only task; final PR/CI held until coordinator supplies protected PR422 merge SHA/tree.

Goal: Preserve completed public API and private read_only ingestion release receipts on protected master with accurate historical chronology and unchanged acceptance limits.

Issue: https://github.com/lucronn/autodata/issues/423
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhI0Gfc`.
Plan: `docs/superpowers/plans/2026-11-15-release-receipts-preservation.md`. Canonical receipt: `docs/verification/2026-11-15-release-receipts-preservation.md`. Machine record: `docs/agents/records/2026-11-15-release-receipts-preservation.json`.
Related completed Issue410 and still-open Issue401 retain their original runtime scope/status. This task creates no runtime authority.

## Pinned base and source selection

Initial protected base `76fb21e8f7c080e93f6d38de93a2e1a22cd11f39`, tree `c4b63d3635e7cc5b084f0d9df6154334e6dc36a3` (PR415 protected merge). All eight selected paths are absent at that base. Planning checkpoint must be committed/pushed and pass canonical machine preflight before copying snapshots. Preserve published milestone history; after root supplies exact PR422 protected merge/tree, merge that exact commit into this isolated branch, recheck path absence at that protected base, and verify docs-only final triple-dot scope. Do not open PR or trigger its CI until this dependency is satisfied. Root owns independent review and merge.

Private audit `/home/corp/autodata-evidence/release-docs-protection-audit-20261115/DRAFT-HANDOFF.md` and adjacent exact-docs-manifest.json identify these approved snapshots. That historical read-only audit is task input; current coordinator instruction authorizes this separately gated docs preservation. Do not cherry-pick whole stale branches or import unrelated diagnostic/recovery proposals. Copy exactly these eight files with the small chronological edits below:

- `docs/agents/records/2026-11-14-workshop-preview-read-only-rollout.json` from `b517b1e7576e8055b4c644a3e06aae54b817548e` Git blob `c44bf889dbb61bc0056fc7fd6debf1f033126b28`.
- `docs/superpowers/plans/2026-11-14-workshop-preview-read-only-rollout.md` from `b517b1e7576e8055b4c644a3e06aae54b817548e` Git blob `29601e64597b53befdb84d76849869144de3b724`.
- `docs/verification/2026-11-14-workshop-preview-read-only-rollout.md` from `b517b1e7576e8055b4c644a3e06aae54b817548e` Git blob `e2b9a53a3d75177bd9a114f0a754de115987e9f4`.
- `docs/agents/records/2026-11-15-private-read-only-runtime.json` from `60c3df486455bef32dd36a9f420c145948575c55` Git blob `01e9c95c89746981404137872c5e812957748125`.
- `docs/architecture/workshop-private-read-only-runtime.md` from `60c3df486455bef32dd36a9f420c145948575c55` Git blob `7f5c3bf190e01c7aaffa64aea8da158d4ae95934`.
- `docs/superpowers/plans/2026-11-14-private-read-only-runtime-rollout.md` from `60c3df486455bef32dd36a9f420c145948575c55` Git blob `a3bc8cdd575d6fd3e47cdc648312ff5e4f06d7c6`.
- `docs/verification/2026-11-14-private-read-only-runtime-rollout.md` from `60c3df486455bef32dd36a9f420c145948575c55` Git blob `33411e4886897dbb827018d8150fd5e8fa99fa29`.
- `docs/superpowers/plans/2026-11-15-configuration-hydration-diagnostics.md` from `60c3df486455bef32dd36a9f420c145948575c55` Git blob `e9779be60bfb9d572057d437180e2f308d145bce`.

The two copied rollout JSON records remain byte-identical archival records. Their original status/checkpoint timestamps evidence the completed historical gates, not this preservation gate or permission to rerun one-attempt helpers. Only this task's new423 machine record applies to current documentation work.

## Chronology and safe publication

Public source3a18d9c7/binary0b17821c API-only read_only accepted00:59Z and apex307 readback01:03Z are bounded historical receipts. Clarify that unchanged private7ce6 applies only to that API release window; link later private runtime receipt superseding it with92d81a1/6fcc910d. Mark public plan preparation, old-runtime pins, future installation wording and instruction/helper sections historical, explicitly non-replayable. Preserve actual accepted source/config/assets/browser receipts and unexercised real rollback disclosure.

Private acceptance is source92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a/image5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4/container6fcc910d46d5740b556c2fc0d0ac527a9e180cf0f27c1a60e5d8815ca84ef9a4, with7ce6 stopped predecessor. Put accepted status first; label premerge/source-only/pending/activation-unexecuted sections and retained handoff instructions historical. Mark preparation/handoff todos completed only where executed receipt demonstrates it. Do not erase initial partial makes/models responses or Created-state rollback defect/regression evidence.

Keep distinct: runtime read_only/disabled purchase/protected27 acceptance; durable dual-bank makes/models60/10-row completion; incomplete/unproved Integra configuration collection despite one usable cached item. No provider/storage cause is established, item.complete does not prove enumeration/rights, and Issue401 stays open. The eighth file stays a historical PROPOSED unsynchronized diagnostics snapshot solely to preserve the original internal reference; no later diagnostics design is imported.

Provider-entry browser acceptance stopped before credentials. Do not claim completed Firebase session, TEST settlement, scoped grant, licensed reader/media/supplier rights, cold-boot durability or repaired live SVG from historical memory-only tests/future422 source. Native renderer dependencies remain absent from the deployed5c image receipt; future image/runtime activation needs its own gate. Preserve underlying limitations exactly. Exclude executable helpers, private configs/inspect/env, credentials/dumps/table rows and licensed source/media bytes; publish only existing safe metadata/hashes/counts and private evidence pointers. No serving or provider GET is performed.

## Allowed edits and verification

This three-file423 plan/record/verification set plus exactly eight paths above is the entire allowlist. No implementation, image, workflow, schema or runtime file changes; no PR422/418 path changes. Validate original eight source Git blob IDs before copy; retain a private before/after blob/line-diff manifest. Parse all three JSON records, verify referenced repository plan/document paths and Markdown links exist on final base, inspect imported text for secrets/raw licensed data and chronological overclaims, check exact changed path set and `git diff --check`. Run current-base autonomy preflight and suitable repository-governance/document checks without creating new tests for this documentation-only preservation. No runtime helpers are executed. Required PR CI runs only after protected422 dependency is integrated and final candidate is ready.

Concrete todo:

- [ ] Pin protected base, verify all eight exact source blobs and path absence, and commit synchronized plan/Issue/Project/canonical documentation with passing exact-base preflight before snapshot edits.
- [ ] Copy only the eight approved Markdown/JSON snapshots, label pre-execution text historical, link public release chronology to the later private acceptance, preserve all partial-response/rollback-defect/acceptance limits and the unsynchronized diagnostic proposal.
- [ ] Validate exact path set, JSON, provenance, internal links, chronology, safe-content redaction and diff whitespace without runtime/provider calls.
- [ ] Hold final PR/CI until root supplies PR422 protected merge SHA/tree; integrate that exact base, recheck no overlap and source scope, then open a normal protected-master documentation PR for independent exact-head review and required CI.
