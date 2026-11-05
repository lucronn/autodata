# Release Controller Preflight Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. This is a planning artifact; implementation requires the synchronized Issue/Project record and exact-base preflight described in AGENTS.md.

**Goal:** Make the release controller validate the candidate and Project tracking before merge, emit commands supported by the installed GitHub CLI, and distinguish merge requests from confirmed merges.

**Architecture:** Keep `release_controller.py` separate from provider execution. Preserve read-only planning as the default. A dedicated release identity may execute a validated plan only after immutable local evidence and live GitHub state agree on the exact candidate. No production deployment is introduced.

**Tech Stack:** Python standard library, Git, GitHub CLI, existing AutoData evidence validator.

**Spec:** `docs/superpowers/specs/2026-11-03-production-release-orchestration-design.md`, R0.

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

## Concrete todo

- [ ] Validate the complete release context and generate supported Project/merge argv.
- [ ] Revalidate pinned v2 evidence and live GitHub Issue/Project/PR state before any mutation.
- [ ] Order tracking before merge, recheck the exact head, and distinguish queued from confirmed merge.
- [ ] Implement idempotent tracking-only recovery for a confirmed merged candidate.
- [ ] Run focused and complete autonomy suites, verify installed CLI flags, update the canonical release-controller document, and obtain independent exact-SHA review.

## Global constraints

- After planning, implementation and review use `gpt-6.1-sol`, medium reasoning, and Fast/priority service, as explicitly requested by the user.

- Own only `scripts/autonomy/release_controller.py`, `scripts/autonomy/test_release_controller.py`, and `docs/agents/release-controller.md`.
- Consume `orchestrator.validate_evidence_bundle(manifest, trusted, evidence_root)` and the trusted-policy interface established by the evidence-hardening task; do not edit those shared files in parallel. The legacy `evaluate` call alone is insufficient for a v2 release.
- No shell interpolation, force push, admin merge, branch-protection bypass, production deployment, token output, or automatic issue closure.
- Every mutation names the repository and exact candidate; missing or stale evidence blocks it.
- Project status reflects verified state. A merge request accepted into a queue is not a merged release.
- Issue #186 and its Project #8 item are verified. R0 evidence was independently reviewed and tested at `a7493d41be4f0c4aa93bdaaa74afa14c30d49965`, then integrated at `643b8d3fc762cfdc9b456d28a47b7a4a9cde6402`. The coordinator may dispatch this task directly after this refreshed synchronized checkpoint passes preflight. Real CLI runtime certification is still outstanding and is not inferred from deterministic R0 acceptance.

## Interface

Use a JSON release context instead of a partially specified collection of IDs:

```python
@dataclass(frozen=True)
class ReleaseContext:
    repository: str
    base_branch: str
    head_branch: str
    pr_number: int
    issue_number: int
    project_owner: str
    project_number: int
    project_id: str
    project_item_id: str
    status_field_id: str
    review_option_id: str
    done_option_id: str
    dependency_field_id: str
```

The CLI adds `--context PATH`; validate its object type and every required
field. Repository must match the manifest. Numeric identifiers must be positive
integers and strings must be nonempty, without control characters or leading
option prefixes. Branch names must pass `git check-ref-format --branch`.
Project owner is independent of repository owner. Existing CLI input flags may
remain for read-only compatibility, but incomplete legacy input cannot enter
`--execute`.

`build_release_plan(manifest, context)` returns named phases containing
structured argv. It remains pure. `validate_live_context(context,
implementation_sha, run_command)` performs read-only discovery and returns
errors plus normalized remote evidence. `execute_release_plan(plan,
run_command)` executes the tracking phase, rechecks the PR head, requests merge,
then confirms remote merge state before any Done transition. The injectable
`run_command` returns `CompletedProcess` and allows tests without GitHub writes.

PR creation is a separate proposal path, not a hidden part of `--execute`.
`--propose-pr --base-branch BRANCH` produces `gh pr create` argv only; the
coordinator performs creation/discovery and attaches the resulting PR before
supplying a complete release context. The repository default is `master`;
never hard-code `main` or silently infer a branch from the task title.

## Task 1: Context and pure command planning

- [ ] Add `ReleaseContext` parsing and validation with unit cases for missing IDs, malformed branches, repository mismatch, invalid numbers, newline/control data, and complete valid input.
- [ ] Build Project commands with `--project-id`, `--id`, `--field-id`, and `--single-select-option-id`; preserve `--match-head-commit` on merge.
- [ ] Target the existing issue Project item. Do not add a duplicate PR item as a side effect of merge.
- [ ] Place the Review tracking update and dependency/evidence text before the merge request. Place Done only in a separate confirmed-merge phase.
- [ ] Keep the command proposal free of network access and make it machine readable by phase.

Required regression assertions:

```python
plan = build_release_plan(manifest, context)
review = plan["before_merge"][0]
assert review[:3] == ["gh", "project", "item-edit"]
assert review[review.index("--project-id") + 1] == context.project_id
assert "--project-number" not in review
merge = plan["request_merge"][0]
assert merge[merge.index("--match-head-commit") + 1] == manifest["implementation_sha"]
assert not any("--admin" in argv for phase in plan.values()
               if isinstance(phase, list) for argv in phase)
```

Run: `python3 -m unittest discover -s scripts/autonomy -p 'test_release_controller.py' -v`.

## Task 2: Read-only remote preflight

- [ ] Reopen and validate the v2 bundle through `orchestrator.validate_evidence_bundle` using the pinned trusted context before GitHub discovery. It must recompute command/artifact/profile/SHA validity and measured coverage, then invoke the legacy validator. Claimed manifest metrics or a previous pass file cannot substitute for this check.

- [ ] Read the repository/PR using `gh pr view NUMBER --repo OWNER/REPO --json number,headRefOid,headRefName,baseRefName,state,isDraft,mergeStateStatus,statusCheckRollup`.
- [ ] In normal merge mode, require the exact candidate SHA, expected head/base branches, open non-draft PR, and successful required checks. Unknown/pending state blocks execution; no check is converted into pass by absence.
- [ ] Read the project with `gh project view NUMBER --owner OWNER --format json` and its fields with `gh project field-list NUMBER --owner OWNER --format json`. Verify project ID, Status field, named Review/Done options, and dependency-text field IDs belong to that project.
- [ ] Verify the specified item belongs to that project and references the expected issue. Use paginated GraphQL reads or a bounded response that explicitly proves enumeration completion; never treat a first-page miss as definitive.
- [ ] Read the linked issue and confirm canonical plan/document links, task goal, current verified candidate/evidence reference, and unresolved blocker status agree with the local planning record.
- [ ] Fail before any mutation on scope denial, unavailable discovery, mismatched IDs, stale SHA, closed/draft PR in normal merge mode, unknown check state, or absent tracking. The preflight output must state which read failed without leaking credentials or source payloads.

Test each remote failure with a fake `run_command` and assert zero mutation
argv were invoked. Include a non-ASCII issue body and paginated item lookup.

## Task 3: Ordered execution and honest recovery state

- [ ] Preserve `AUTODATA_RELEASE_AUTOMATION=enabled` and full validated context as execution requirements.
- [ ] Execute Review/dependency tracking updates first. If either fails, return blocked with merge unattempted.
- [ ] Re-read PR head immediately before the merge request. Reject a head change even after earlier checks passed.
- [ ] Request merge with exact head matching. Query the PR again for `state`, `mergedAt`, `mergeCommit`, and `headRefOid`.
- [ ] If GitHub queued the PR or enabled auto-merge, record `merge_pending` and leave the Project in Review. Never claim deployment or completion from the merge command exit code alone.
- [ ] When the exact candidate is confirmed merged, update Project Done and persist merge/candidate/evidence identifiers. If this tracking update fails, return `merged_tracking_failed`, retain the confirmed merge result, and provide a retryable tracking-only action. Never attempt a second merge or label the code unmerged.
- [ ] Store phase outcomes, argv, exit codes, and sanitized failure text under the external evidence directory. Repeated execution consults recorded and live state before retrying mutations.

Required scenarios are tracking failure before merge, changed head after
preflight, merge command failure, merge queued with exit zero, confirmed merge,
and confirmed merge with failed Done update. Tests assert the exact executed
argv sequence and resulting state, not only string presence.

### Tracking-only recovery entrypoint

Add `--repair-tracking` as a separate execution mode, mutually exclusive with
normal merge execution and PR proposal. It uses a state-specific preflight:
validate the same immutable local bundle and trusted context; require the
remote PR to be `MERGED`, its recorded head SHA to equal the verified candidate,
and its merge commit/target branch to match the retained release receipt. If
there is no receipt because the process died after merge, reconstruct it from
verified remote PR metadata before writing tracking state. Verify the linked
Issue/Project item and field IDs again. Do not apply the normal OPEN/draft/check
preconditions to this already-merged repair mode. Closed-unmerged or a different
merged candidate remains blocked.

This mode emits only outstanding Project field updates and a repaired receipt;
its plan must contain no `gh pr merge`, PR creation or Review regression. If
tracking already agrees with the verified merge, return `tracking_repaired`
without mutation. Keep `AUTODATA_RELEASE_AUTOMATION=enabled` and report an
unsuccessful repair as `merged_tracking_failed`, retaining the original merge.
Add a two-invocation test: normal execution merges then fails its Done update;
a later `--repair-tracking` call succeeds on the MERGED PR and invokes only
Project commands. Add a third idempotent invocation, and negative cases for
closed-unmerged PR, wrong merged head, wrong target branch and mismatched item.

## Task 4: Review and integration

- [ ] Run the focused controller suite and the complete autonomy suite.
- [ ] Verify generated argument names against `gh project item-edit --help`, `gh project item-add --help`, and `gh pr merge --help` without executing mutations.
- [ ] Update `docs/agents/release-controller.md` with the context format, discovery commands, new state vocabulary, PR proposal boundary, and recovery behavior.
- [ ] Have a reviewer inspect this bounded diff and command-order tests at the exact commit.
- [ ] Integrate after evidence hardening; rerun complete autonomy tests at the integrated SHA. Keep production deployment disabled and record unavailable real release-identity verification separately.

## Current evidence

The installed GitHub CLI exposes `project item-edit --project-id` and no
`--project-number` flag. The baseline controller uses the latter after its
merge command and hard-codes `main` in its PR proposal. Existing tests check
only two small cases. These are verified reasons for the task, not completed
fixes.
