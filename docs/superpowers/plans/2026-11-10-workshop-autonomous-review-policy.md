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

- [ ] Synchronize this plan, verification document, Issue #385, Project #8, and exact-base pre-implementation record; run the machine preflight.
- [ ] Clarify the single-maintainer review decision in the operating model, Project settings checklist, and autonomous-development documentation without altering the eight-gate policy or CODEOWNERS mapping.
- [ ] Verify policy consistency, review the exact policy candidate independently, and merge only after required CI passes.
- [ ] Update the hourly Codex prompt to prioritize the next safe Workshop app task instead of repeating unchanged PR polls, while retaining exact-head AI review, CI, and no-production limits.
- [ ] Recheck the current Workshop app and closure PRs at their exact heads, refresh strict branch checks after the policy merge, integrate when gates pass, and reconcile Issue #385/#388 and Project #8 without claiming production readiness.

## Task 1: Synchronized checkpoint

**Files:** This plan, `docs/verification/2026-11-10-workshop-autonomous-review-policy.md`, and `docs/agents/records/2026-11-10-workshop-autonomous-review-policy.json`.

- [ ] Record the five concrete todos in Issue #385 and the Project #8 item's source/dependency field; read both back.
- [ ] Commit the plan, verification document, and synchronized record as a planning-only checkpoint.
- [ ] Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-10-workshop-autonomous-review-policy.json --base-sha <checkpoint-sha>` and require `status: synchronized`, `errors: []`.

## Task 2: Repair the review-rule mismatch

**Files:** `docs/github/operating-model.md`, `docs/github/project-bootstrap.md`, `docs/agents/autonomous-development-system.md`, and the verification document.

- [ ] Replace the unconditional CODEOWNERS-approval wording with a rule for independent exact-head AI review when there is no distinct eligible CODEOWNER, and make clear that live branch protection still controls any required GitHub approval.
- [ ] Clarify that CODEOWNERS is retained for ownership/routing, not self-approval; the autonomous release controller's separate role/evidence gates remain unchanged.
- [ ] Run `python3 -m unittest scripts.dev.test_repository_governance -q`, `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -q`, and `git diff --check`.

## Task 3: Integration and automation

**Files:** The same verification document and the existing Codex heartbeat automation; no Workshop app source file is in scope for the policy change.

- [ ] Commit and push the policy candidate, obtain a separate read-only exact-head review, create a PR, and verify its required CI and live protection state before merge. User authorization supplies the one-time policy-transition decision; no GitHub approval is fabricated.
- [ ] Update the existing hourly automation prompt through the app tool, preserving its schedule and quiet-notification preference.
- [ ] Refresh PR #387 and PR #389 against the new `master`, rerun exact-head checks and review as needed, then merge only if the current policy and branch protection permit. Update Issue/Project/documentation with exact outcomes.
