# Workshop final180 Inventory and Runner Implementation Plan

> **For agentic workers:** Implementation of the proposed runner requires a separate synchronized gate. Use superpowers:executing-plans only after that gate passes; this pending plan authorizes no implementation.

**Goal:** Freeze a planning-only final180 literal inventory and propose a separately gated fixture runner; preserve disabled profiles and false authority.

**Architecture:** The first checkpoint is documentation and immutable source inspection only. A separate runner slice would collect actual fixture evidence in isolated owned infrastructure; later reviewed profile promotion and final acceptance remain independent gates.

**Tech Stack:** Repository Markdown/JSON planning records; proposed Python unittest/subprocess fixture supervisor and Docker isolation.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-inventory.md` and adjacent literal JSON inventory.

## Global constraints

- Inspection base `df52326b2a12fd17db39d9368f66a28a366f38ad`; no final source tuple is selected.
- Issue: https://github.com/lucronn/autodata/issues/186
- Project: https://github.com/users/lucronn/projects/8 ; existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
- Record/task status `pending`; no GitHub write, commit, push or implementation authorized by this draft.
- Literal180 = 5+8+14+12+120+21; support evidence adds zero cases.
- Every profile/tier remains disabled and every verification/deployment/cutover authority false.
- Execution preference gpt-6.1-sol / medium / Fast when exposed; no silent fallback.

## First checkpoint: inventory/profile planning only

Files: create this plan, the spec Markdown/literal JSON, task `docs/agents/tasks/2026-11-03-production-release/workshop-final180-inventory.json`, record `docs/agents/records/2026-11-04-workshop-final180-inventory.json`; update only the pending queue entry and canonical assembler plan pointer. Application, scripts, tests, profiles, policy, workflow, Compose and runtime evidence remain outside this checkpoint.

Consumes the exact pinned Git objects and the parent assembler plan. Produces explicit source-observed literal IDs, hashes, raw/support requirements, proposed argv/deadline/env contract, missing-fact inventory and a pending handoff. It does not produce a profile that the assembler can select.

- [ ] Select and record the integrated source tuple; regenerate literal IDs and source hashes only from the selected immutable Git objects.
- [ ] Review complete raw/support inventories, source hashes, argv, phase/global deadlines, environment, storage and trust identities; preserve every explicit missing fact.
- [ ] Synchronize Issue186, Project8, this plan/spec/inventory/task/record/queue and canonical assembler plan; commit the docs checkpoint and obtain exact-base preflight plus independent gate review.
- [ ] Separately approve and synchronize a literal runner implementation allowlist and failing-test contract; no runner implementation follows from this pending planning task.
- [ ] After reviewed runner integration, freeze a new final candidate and execute fresh180/support/CI/security/image/raw-review evidence under its own exact-base gate; enable no assembler profile here.

The five items above are the canonical todo copied identically to task and record. Coordinator tracking must preserve all predecessor Source/dependency text and hashes, update the existing Issue/Project item, read back complete matching text/status, and attach capture receipts. Never mark Done or release-ready. Commit/push only after coordinator selects source tuple and authorizes synchronization. The new checkpoint SHA is an external invocation input, never embedded as its own hash.

For committed checkpoint B, independently confirm task/record equality and all references exist at B, then run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-final180-inventory.json --base-sha B --repo-root <owned-checkout> --policy <policy-at-B>`. Require exit0/status synchronized/errors empty plus independent real tracking/scope review. The present `pending` record intentionally fails; machine validation is not a substitute for real tracking freshness or missing evidence resolution. A passing documentation checkpoint still cannot authorize the separately scoped runner without its own synchronized record and concrete allowlist.

## Proposed separate runner slice, not authorized

Only proposed paths: `scripts/dev/workshop_final180_runner.py`, `scripts/dev/test_workshop_final180_runner.py`, `docs/verification/workshop-final180-runbook.md`. Coordinator must create a dedicated runner task/record, complete exact runtime/image/raw/environment/cleanup decisions in the spec, synchronize Issue/Project and commit a fresh checkpoint before any file is created. No autonomy runner, assembler, producer test, workflow, Compose, application or SQL edit is included.

Before that runner checkpoint, freeze the phase-specific environment: common fixed values plus only the current phase's fixed selector. DTO must omit paid/API integration selectors and prove its nested Go fixture reports `ready.kind=dto-fixture`; the nested launcher's argv, environment, ownership, readiness and stop behavior remain unresolved. Account for its existing 4400-second timer inside browser 4440 seconds and DTO phase 4560 seconds, including startup and cleanup. These are planning requirements, not a claim that the runner or acceptance is executable.

The 4400-second Go timer starts after readiness, so the browser's 4440-second ceiling alone does not ensure the fixture remains alive for its full run. The successor runner gate should choose a shorter browser subprocess cap and explicit startup/stop reserves, validated against cold-start evidence; 4320 seconds for browser, 120 seconds for startup and 80 seconds for stop are proposals, not frozen authority. DTO failure traces may be 16MiB, above the current assembler's 8MiB per-artifact limit; retain them in private raw storage and decide transport/validator bounds in a separate reviewed gate.

The runner gate must require independently meaningful red/green tests for: wrong/dirty candidate; unsafe/symlink input or artifact path; extra/missing/copied source; shell/argv/env override; each missing/duplicate/extra/skipped/failed logical ID despite a correct count; DTO substituted for API; mixed candidate; child timeout/nonzero masked by outer pass; deadline exhausted during cleanup; unowned process/container/volume deletion; interruption and retained failed attempt; zero authority and no evaluator/profile mutation. Use inline fake command/clock/owned-resource adapters; synthetic tests prove supervisor behavior only.

Implementation milestones, each with focused tests and a small validated commit/push after its gate: (1) strict selected-candidate/source/inventory/argv/environment and ownership admission; (2) bounded serial phase supervision and cleanup with private raw receipts; (3) exact observed ID/outcome/support reconciliation and honest failed/unavailable output; (4) runbook, complete local suite, independent exact-SHA code review. Run `python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v`, developer/autonomy discovery appropriate to the new import path, AST syntax and diff/allowlist checks. Broader actual Docker/browser180 execution is separately dispatched at the final integrated candidate after runner review; do not run acceptance during parser/supervisor unit tests.

## Review and freeze conditions

Reject inventory approval if literal arrays disagree with source, a source hash/command is inferred from a later checkout, known raw files are omitted, source-local and supervisor budgets are conflated, total-only evidence substitutes for IDs, a missing trust field is silently filled, or pending tracking is presented as synchronized. The exact missing dependencies are materialized in the JSON inventory and queue. Full raw/member bounds remain unfrozen; profiles stay unavailable until resolved. Preserve historical passing/failed receipts without using them as final-head evidence.
