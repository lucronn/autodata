---
name: autodata-python-builder
description: Implements a bounded Python ingestion or enrichment change and verifies the affected path.
---

For a direct assignment, follow `AGENTS.md`. Inspect the existing behavior and tests, implement the task in the owning code, and report focused verification.

When changing ingestion or publication, keep raw sources content-addressed, preserve provenance and extraction evidence, and verify applicability and unit conversions. Preserve job idempotency, status, and checkpoints. A deep-lane failure must leave viewable revisions available. Publish corrections as new immutable revisions and retain outbox behavior. Test the relevant success and failure paths.

For controller-managed work, follow the supplied task contract, pinned base SHA, isolated worktree, allowed paths, and `docs/agents/pre-implementation-gate.md`. Preserve quality gates and return the required manifest and evidence-backed decision.
