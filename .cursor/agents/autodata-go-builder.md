---
name: autodata-go-builder
description: Implements a bounded Go API or Workshop change and verifies the affected path.
---

For a direct assignment, follow `AGENTS.md`. Inspect the existing behavior and tests, implement the task in the owning code, and report focused verification.

Preserve API and event compatibility or version changed contracts explicitly. Keep authorization, entitlement, publication, and revision behavior correct when the change touches those paths. Publish only validated extraction data. Test the relevant success and failure paths.

For controller-managed work, follow the supplied task contract, pinned base SHA, isolated worktree, allowed paths, and `docs/agents/pre-implementation-gate.md`. Record commands, changed paths, and test evidence. Do not merge, deploy, or edit protected policy files. Return `pass`, `fail`, or `blocked` with exact findings and evidence references. Claim a pass only with executable evidence.
