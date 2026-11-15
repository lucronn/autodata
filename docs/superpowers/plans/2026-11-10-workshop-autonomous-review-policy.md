# Workshop autonomous review policy implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the single-maintainer Workshop PR workflow use an independent exact-head AI review without waiting for an impossible self-authored GitHub CODEOWNERS approval, while preserving CI and all other release gates.

**Architecture:** CODEOWNERS continues to identify domain ownership and request eligible GitHub reviewers. The repository operating model distinguishes that routing from the independent review decision: an AI reviewer separate from the implementer can supply a retained exact-head verdict when no distinct eligible CODEOWNER exists. GitHub-required approvals, required checks, blocking threads, the eight-gate autonomous release controller, and production-deployment prohibition remain authoritative. The hourly Codex task keeps moving to the next safe Workshop app task when one PR is waiting.

**Tech Stack:** Repository Markdown policy, GitHub Project #8, GitHub pull requests, and Codex heartbeat automation.

**Spec:** `docs/verification/2026-11-10-workshop-autonomous-review-policy.md`

## Global constraints

- Do not forge a GitHub approval or claim that an AI review is a GitHub CODEOWNERS review.
- Do not disable a required branch-protection check, remove CODEOWNERS ownership, or bypass a failed review/CI gate.
- Do not deploy production, charge a customer, or claim live paid-access acceptance.
- Track the change in [Issue #385](https://github.com/lucronn/autodata/issues/385) and [Project #8](https://github.com/users/lucronn/projects/8); the existing Workshop app fix is [PR #389](https://github.com/lucronn/autodata/pull/389).

## Concrete todo

- [x] Synchronize this plan, verification document, Issue #385, Project #8, and exact-base pre-implementation record; run the machine preflight.
- [x] Clarify the single-maintainer review decision in the operating model, Project settings checklist, and autonomous-development documentation without altering the eight-gate policy or CODEOWNERS mapping.
- [x] Verify policy consistency, review the exact policy candidate independently, and integrate its exact tree on protected `master` only after required CI passes. The squash request advanced `master` but returned 502 before GitHub marked PR #390 merged; its duplicate PR record was closed with exact-tree evidence.
- [x] Update the hourly Codex prompt to prioritize the next safe Workshop app task instead of repeating unchanged PR polls, while retaining exact-head AI review, CI, and no-production limits.
- [x] Recheck and integrate Workshop app PR #389 at its exact head after refreshing strict branch checks; it merged as `2a1ef1cda802c7fbcddbfd6bcec0dccf302e272c` without claiming production readiness.
- [ ] Recheck and integrate documentation closure PR #387 at its exact head; reconcile Issue #385/#388 and Project #8 with confirmed outcomes.

## Task 1: Synchronized checkpoint

**Files:** This plan, `docs/verification/2026-11-10-workshop-autonomous-review-policy.md`, and `docs/agents/records/2026-11-10-workshop-autonomous-review-policy.json`.

- [x] Record the five concrete todos in Issue #385 and the Project #8 item's source/dependency field; read both back ([Issue comment](https://github.com/lucronn/autodata/issues/385#issuecomment-6764439766)).
- [x] Commit the plan, verification document, and synchronized record as planning-only checkpoint `cd7b0ffa187a1f570a9df03ab2c5fc23a3215025`.
- [x] Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-10-workshop-autonomous-review-policy.json --base-sha cd7b0ffa187a1f570a9df03ab2c5fc23a3215025`; exit 0, `status: synchronized`, `errors: []`.

## Task 2: Repair the review-rule mismatch

**Files:** `docs/github/operating-model.md`, `docs/github/project-bootstrap.md`, `docs/agents/autonomous-development-system.md`, and the verification document.

- [x] Replace the unconditional CODEOWNERS-approval wording with a rule for independent exact-head AI review when there is no distinct eligible CODEOWNER, and make clear that live branch protection still controls any required GitHub approval.
- [x] Clarify that CODEOWNERS is retained for ownership/routing, not self-approval; the autonomous release controller's separate role/evidence gates remain unchanged.
- [x] Run `python3 -m unittest scripts.dev.test_repository_governance -q` (10 passed), `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -q` (146 passed), and `git diff --check` (clean).

## Task 3: Integration and automation

**Files:** The same verification document and the existing Codex heartbeat automation; no Workshop app source file is in scope for the policy change.

- [x] Commit and push policy head `a442cfb`, obtain a separate read-only exact-head review (no findings), create PR #390, and verify required CI run 42796020557 and live protection. Its protected-master squash commit `fd1a877` is tree-identical to that reviewed head; GitHub returned 502 before marking the PR merged, so the duplicate PR record was closed. No GitHub approval was fabricated.
- [x] Update the existing hourly automation prompt through the app tool, preserving its hourly schedule and quiet-notification preference; read back the saved automation configuration.
- [x] Refresh PR #389 against the policy base, rerun exact-head local tests and independent review, and merge only after all three jobs in CI run 42798577653 passed and live protection allowed it.
- [ ] Refresh PR #387 against the app-integrated `master`, rerun current review and CI, then reconcile Issue/Project/documentation with exact outcomes.
