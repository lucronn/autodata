# Release-receipt preservation verification

Status: synchronized planning checkpoint; selected snapshots not copied yet. Final PR/CI held for protected PR422 merge pin. No runtime or provider calls.

Goal: Preserve completed public API and private read_only ingestion release receipts on protected master with accurate historical chronology and unchanged acceptance limits.

Issue: https://github.com/lucronn/autodata/issues/423
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhI0Gfc`.
Plan: `docs/superpowers/plans/2026-11-15-release-receipts-preservation.md`. Canonical receipt: `docs/verification/2026-11-15-release-receipts-preservation.md`. Machine record: `docs/agents/records/2026-11-15-release-receipts-preservation.json`.
Related completed Issue410 and still-open Issue401 retain their original runtime scope/status. This task creates no runtime authority.

Initial protected base76fb21e8f7c080e93f6d38de93a2e1a22cd11f39/treec4b63d3635e7cc5b084f0d9df6154334e6dc36a3. The eight approved source paths are absent; exact source commits/blob IDs and allowed chronology changes are pinned in the plan. This new snapshot preserves historical checkpoint receipts without recreating their authorization.

Concrete todo:

- [ ] Pin protected base, verify all eight exact source blobs and path absence, and commit synchronized plan/Issue/Project/canonical documentation with passing exact-base preflight before snapshot edits.
- [ ] Copy only the eight approved Markdown/JSON snapshots, label pre-execution text historical, link public release chronology to the later private acceptance, preserve all partial-response/rollback-defect/acceptance limits and the unsynchronized diagnostic proposal.
- [ ] Validate exact path set, JSON, provenance, internal links, chronology, safe-content redaction and diff whitespace without runtime/provider calls.
- [ ] Hold final PR/CI until root supplies PR422 protected merge SHA/tree; integrate that exact base, recheck no overlap and source scope, then open a normal protected-master documentation PR for independent exact-head review and required CI.
