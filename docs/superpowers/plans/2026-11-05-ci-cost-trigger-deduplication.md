# CI Cost Trigger Deduplication Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this single task after the exact planning checkpoint passes preflight and the coordinator dispatches implementation.

**Goal:** Avoid duplicate Autonomous Verification suites for feature-branch pushes while retaining pull_request verification and push verification on master.

**Architecture:** Add a branches filter containing only master under the existing push event. Preserve pull_request path filters, workflow_dispatch, all jobs, steps, required check names, permissions, timeouts and existing push path filters.

**Tech Stack:** GitHub Actions YAML; existing Python stdlib repository governance checks.

**Spec:** Narrow CI cost correction described in this plan and docs/github/operating-model.md.

## Global Constraints

- Planning source: `2e5c483e40bd6fa930382319dfaea1c8bbfdedce` on origin/master.
- This checkpoint changes documentation only. No workflow implementation, PR, merge or deployment.
- Future implementation scope: `.github/workflows/autonomous-verification.yml`, focused regression coverage in `scripts/dev/test_repository_governance.py`, and only `product_evidence.ci_profile.workflow_sha256` in `docs/agents/tasks/2026-11-03-production-release/r6-release.json`. No other implementation paths are authorized.
- Existing jobs and required checks must remain unchanged. Do not add pull_request branch filters or alter path filters.

## Task 1: Limit push verification to master

- [ ] Re-run the committed JSON record preflight at the exact checkpoint SHA before implementation.
- [ ] Add focused governance regression coverage for the event matrix: matching feature push does not schedule; matching master push schedules; matching pull_request schedules; manual dispatch remains available. Confirm current unrestricted push configuration fails the new assertion.
- [ ] Under the existing `push:` key, before `paths:`, add exactly `branches:` followed by the YAML list item `- master`; preserve every other workflow byte. Keep all jobs and required check names.
- [ ] Rebind the single disabled R6 workflow digest exactly as specified below. Preserve all other R6 bytes and every disabled/release-authority semantic.
- [ ] Run `python -m unittest discover -s scripts/dev -p 'test_repository_governance.py' -v`, the existing workflow binding checks found during source inspection, and `git diff --check`. Compare the jobs subtree and all path lists byte-for-byte to the pinned checkpoint. Run `PYTHONPATH=scripts/dev python -m unittest test_workshop_browser_smoke.DTOWorkflowBindingTests test_release_acceptance.TrustedBoundaryTests -v` on the final committed source. The trusted loader reads workflow bytes at its pinned git base, so verify the final commit rather than only working-tree bytes. No changes to the binding consumer tests or release_acceptance.py are authorized.
- [ ] Commit and promptly push the small validated implementation milestone on the assigned feature branch; obtain independent review and actual pull_request Actions receipts for every existing required job. After merge by an authorized coordinator, inspect master push receipt and absence of duplicate feature-push runs. No merge authority comes from this plan.
- [ ] Synchronize Issue/Project and canonical documentation with the exact source SHA, local/hosted evidence and any remaining blockers. Do not claim future master evidence before it exists.

## Acceptance

The workflow event matrix is feature push=no, master push=yes (existing paths apply), pull_request=yes (existing paths apply), workflow_dispatch=yes. Existing full-suite jobs and required checks are identical. Local structural tests prove the trigger change and hosted PR evidence proves checks remain present. Planning-only validation does not claim implementation or CI success.

## Mandatory one-field R6 binding correction

The current full-workflow binding is intentional. `scripts/dev/test_workshop_browser_smoke.py:1259` checks current workflow bytes; `scripts/dev/release_acceptance.py:3658` checks committed workflow bytes at the trusted base. Keep both consumers and their enforcement unchanged.

Change only `product_evidence.ci_profile.workflow_sha256` in `docs/agents/tasks/2026-11-03-production-release/r6-release.json` from `3c54e7ba0613d1cd3a78819eede4915b1d268ffd904df83b2c034d914dca10e6` to `de53b6f0552165d4ce07549d07e5cb38999995befe9369e0d030fe7d6beb543d`. The latter is independently computed from the exact two-line push trigger addition. If the actual workflow differs, stop and revise this gate; do not adopt an unreviewed digest.

The original R6 is 8727 bytes, SHA256 `05b43e5a775e685d76bd44f0b05675cbd286476547c17e7e2cb9dade03a4e32d`. Expected one-field result remains 8727 bytes, SHA256 `136619978274a7b541651ac7e9ed4cac58bc10cf826358d6f658c0c2f813cb78`, Git blob `e9f2d5c4784212d9d922628fc84c4873d89dce99`. Require exact byte equality to the original with that sole literal replacement. Preserve `ci_profile.enabled=false`, `dto_upload_required=true`, `enabled_tiers=[]`, every disabled slot/supervisor/bindings/report profile and all release authority/credit limits. This rebind grants no promotion, browser evidence, acceptance or release authority.

Regression evidence at the original checkpoint: planner independently ran `PYTHONPATH=scripts/dev python -m unittest test_workshop_browser_smoke.DTOWorkflowBindingTests test_release_acceptance.TrustedBoundaryTests -v`: 8 tests PASS. Builder reports governance baseline 9/9 PASS and a readonly temporary-tree trigger injection producing the expected one-test digest AssertionError before rebind; this is red source evidence, not implementation or hosted CI success. Final source must pass both the existing binding/trusted-boundary tests and new trigger regression tests with unchanged binding consumers, and retain exact workflow/R6 byte proofs.

## Synchronized tracking and todo record

Issue: https://github.com/lucronn/autodata/issues/315

Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGR-0Q`.

```json
{
  "goal": "Avoid duplicate Autonomous Verification suites for feature-branch pushes while retaining pull_request verification and push verification on master.",
  "plan_ref": "docs/superpowers/plans/2026-11-05-ci-cost-trigger-deduplication.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/315",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/github/operating-model.md",
    "docs/agents/pre-implementation-gate.md"
  ],
  "todo": [
    "Re-run the exact-checkpoint planning preflight before implementation.",
    "Add focused governance regression coverage for feature push, master push, pull_request and manual dispatch.",
    "Limit push to master while preserving all existing paths, jobs and required checks.",
    "Rebind only product_evidence.ci_profile.workflow_sha256 in the disabled R6 task to the exact master-only-push workflow digest; preserve every other byte and all disabled authorities.",
    "Run structural/workflow-binding checks, inspect unchanged job definitions and push a validated implementation milestone for independent review and actual PR CI evidence.",
    "Synchronize exact-source evidence and remaining blockers in canonical docs and GitHub; retain master-push verification as pending until available."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T13:32:24.447085Z",
  "project_item_id": "PVTI_lAHOCSJ8cc4BiQ2BzhGR-0Q",
  "planning_source_sha": "2e5c483e40bd6fa930382319dfaea1c8bbfdedce",
  "implementation_paths": [
    ".github/workflows/autonomous-verification.yml",
    "scripts/dev/test_repository_governance.py",
    "docs/agents/tasks/2026-11-03-production-release/r6-release.json"
  ],
  "workflow_binding": {
    "task_ref": "docs/agents/tasks/2026-11-03-production-release/r6-release.json",
    "field": "product_evidence.ci_profile.workflow_sha256",
    "old": "3c54e7ba0613d1cd3a78819eede4915b1d268ffd904df83b2c034d914dca10e6",
    "new": "de53b6f0552165d4ce07549d07e5cb38999995befe9369e0d030fe7d6beb543d",
    "expected_task_bytes": 8727,
    "expected_task_sha256": "136619978274a7b541651ac7e9ed4cac58bc10cf826358d6f658c0c2f813cb78",
    "expected_task_git_blob": "e9f2d5c4784212d9d922628fc84c4873d89dce99"
  }
}
```

Pinning: the latest docs-only checkpoint containing this amended record supersedes `263d408c07e55f1bed287e32dc8444a3fbff5f4d` as the implementation base. Exact new SHA is sealed in Issue #315 after commit/push and must pass preflight before any implementation edits.
