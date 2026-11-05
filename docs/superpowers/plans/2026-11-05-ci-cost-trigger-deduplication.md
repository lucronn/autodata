# CI Cost Trigger Deduplication Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this single task after the exact planning checkpoint passes preflight and the coordinator dispatches implementation.

**Goal:** Avoid duplicate Autonomous Verification suites for feature-branch pushes while retaining pull_request verification and push verification on master.

**Architecture:** Add a branches filter containing only master under the existing push event. Preserve pull_request path filters, workflow_dispatch, all jobs, steps, required check names, permissions, timeouts and existing push path filters.

**Tech Stack:** GitHub Actions YAML; existing Python stdlib repository governance checks.

**Spec:** Narrow CI cost correction described in this plan and docs/github/operating-model.md.

## Global Constraints

- Planning source: `2e5c483e40bd6fa930382319dfaea1c8bbfdedce` on origin/master.
- This checkpoint changes documentation only. No workflow implementation, PR, merge or deployment.
- Future implementation scope: `.github/workflows/autonomous-verification.yml` and focused regression coverage in `scripts/dev/test_repository_governance.py`; any additional workflow-digest binding correction needs separately reviewed scope before editing.
- Existing jobs and required checks must remain unchanged. Do not add pull_request branch filters or alter path filters.

## Task 1: Limit push verification to master

- [ ] Re-run the committed JSON record preflight at the exact checkpoint SHA before implementation.
- [ ] Add focused governance regression coverage for the event matrix: matching feature push does not schedule; matching master push schedules; matching pull_request schedules; manual dispatch remains available. Confirm current unrestricted push configuration fails the new assertion.
- [ ] Under the existing `push:` key, before `paths:`, add exactly `branches:` followed by the YAML list item `- master`; preserve every other workflow byte. Keep all jobs and required check names.
- [ ] Run `python -m unittest discover -s scripts/dev -p 'test_repository_governance.py' -v`, the existing workflow binding checks found during source inspection, and `git diff --check`. Compare the jobs subtree and all path lists byte-for-byte to the pinned checkpoint. If a whole-workflow binding requires another file, stop for a revised gate rather than weakening the binding.
- [ ] Commit and promptly push the small validated implementation milestone on the assigned feature branch; obtain independent review and actual pull_request Actions receipts for every existing required job. After merge by an authorized coordinator, inspect master push receipt and absence of duplicate feature-push runs. No merge authority comes from this plan.
- [ ] Synchronize Issue/Project and canonical documentation with the exact source SHA, local/hosted evidence and any remaining blockers. Do not claim future master evidence before it exists.

## Acceptance

The workflow event matrix is feature push=no, master push=yes (existing paths apply), pull_request=yes (existing paths apply), workflow_dispatch=yes. Existing full-suite jobs and required checks are identical. Local structural tests prove the trigger change and hosted PR evidence proves checks remain present. Planning-only validation does not claim implementation or CI success.

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
    "Run structural/workflow-binding checks, inspect unchanged job definitions and push a validated implementation milestone for independent review and actual PR CI evidence.",
    "Synchronize exact-source evidence and remaining blockers in canonical docs and GitHub; retain master-push verification as pending until available."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T13:30:31.547925Z",
  "project_item_id": "PVTI_lAHOCSJ8cc4BiQ2BzhGR-0Q",
  "planning_source_sha": "2e5c483e40bd6fa930382319dfaea1c8bbfdedce",
  "implementation_paths": [
    ".github/workflows/autonomous-verification.yml",
    "scripts/dev/test_repository_governance.py"
  ]
}
```

Pinning: the planning checkpoint commit containing this plan, record and canonical document is the implementation base. Resolve and pass its full SHA explicitly to the machine preflight; the SHA is sealed in the Issue after push to avoid self-referential commit content.
