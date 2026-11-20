# Autonomous Run Planning Contract

**Status:** enforced by `scripts/autonomy/runner.py` and `scripts/autonomy/orchestrator.py`
**Scope:** tasks submitted to those autonomous systems
**Direct user-directed work:** follow `AGENTS.md`; no synchronized planning record is required

**Current verified implementation:** `99175fff019957264ab77914dbdf6c53b9d5aaf8`

## Purpose

The autonomous runner and orchestrator accept machine-readable task envelopes. Before they invoke an implementation agent, they require a pinned plan, GitHub tracking, and canonical repository documentation. This protects unattended runs from acting on an unreviewed or stale envelope.

This contract does not apply to an agent working directly with a user in a checkout. Direct work should verify the smallest working product path and use focused tests. A user request does not need a new Issue, Project item, plan, or machine preflight before code changes.

## Required order

1. Write a decision-complete plan under `docs/superpowers/plans/`.
2. Create or identify the GitHub Issue and add or identify its Project #8 item.
3. Update the Issue, Project item, and canonical repository documentation with the goal, references, and concrete `todo` list.
4. Record the synchronized pre-implementation record and pin it to the implementation base SHA.
5. Run the machine preflight. A failed or missing preflight is a blocking result.
6. Only after preflight passes may the autonomous system invoke its implementation agent.

The plan/checkpoint commit must be present at the pinned base SHA. An uncommitted or later plan cannot authorize a builder. A Project item is a synchronized index and work queue; it is not a second source of technical truth.

## Required record

The architect or task coordinator must provide this object to the implementation boundary:

```json
{
  "goal": "Enforce an agent-agnostic planning gate before implementation",
  "plan_ref": "docs/superpowers/plans/2026-09-11-pre-implementation-gate.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/86",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/pre-implementation-gate.md",
    "docs/github/operating-model.md"
  ],
  "todo": [
    "Add the canonical rule and adapters",
    "Add machine preflight enforcement and tests",
    "Synchronize the verified implementation SHA in GitHub"
  ],
  "status": "synchronized",
  "updated_at": "2026-09-11T00:00:00Z"
}
```

The machine validator requires every field, validates the GitHub Issue and Project URL shapes, confirms that the plan and referenced repository documents exist at the pinned base SHA, requires non-empty work items, and accepts only `status: synchronized`. The plan must visibly contain the Issue reference, Project reference, and todo record. A malformed, stale, or incomplete record is blocked.

## Agent responsibilities

- Planning roles within an autonomous run may create or revise the plan and return the record; they do not implement the task.
- Implementation roles within an autonomous run verify the preflight and stop when it fails.
- Verification roles within an autonomous run inspect the exact implementation SHA and do not silently change scope.
- Release roles within an autonomous run re-check the task record and exact SHA before a pull request or merge.

An autonomous-run role cannot treat a natural-language approval, untracked file, unverified Issue number, or Project title as a passing record.

## Enforcement boundary

The checked-in `.autodata-autonomy-policy.json` declares this record and its canonical paths. `scripts/autonomy/pre_implementation.py` validates the record. `scripts/autonomy/runner.py` rejects implementation-role envelopes before output setup, worktree creation, or provider invocation. `scripts/autonomy/orchestrator.py` rejects an architect result before invoking the builder.

`AGENTS.md` and `.cursor/rules/product-fast-path.mdc` guide direct work. They link here only for use of the autonomous runner or orchestrator.

## Verified delivery

The gate is implemented at commit `99175fff019957264ab77914dbdf6c53b9d5aaf8`.
The planning checkpoint was committed and pushed at
`ef1a8582818086228a06dedb8c02a60e400e11d0` before implementation began.

Local verification at the implementation commit passed:

- autonomy tests: `37 passed`;
- ingestion worker tests: `240 passed, 12 subtests passed`;
- enrichment worker tests: `46 passed, 16 subtests passed`;
- developer adapter tests: `44 passed`;
- Go API and shared-contract tests: passed;
- contract checks: `7 tests`, `OK`; and
- policy parsing and `git diff --check`: passed.

The GitHub verification workflow passed, including the live Compose fast-lane
smoke, at [run 34564744459](https://github.com/lucronn/autodata/actions/runs/34564744459).
Issue [#86](https://github.com/lucronn/autodata/issues/86) and the
[AutoData Portfolio Project](https://github.com/users/lucronn/projects/8) item
are the synchronized delivery records for that autonomous run. The gate remains
required for future tasks submitted to the runner or orchestrator.

## Evidence and recovery

For an autonomous run, the Issue and Project item retain the goal, plan/document links, concrete todo, status, and verified commit. If its record cannot be verified, stop that autonomous run and correct the record. This recovery rule does not block direct user-directed work.

### Source media binding consumer checkpoint

The source media binding task passed the machine preflight at pinned planning
base `5be336ccfbe1bb2323a546eac0169291ecc485dc` before implementation.
[PR #332](https://github.com/lucronn/autodata/pull/332) carries the consumer;
verification and remaining release boundaries are recorded in
`docs/verification/2026-11-05-source-media-bindings.md`. This historical task used
the autonomous-run gate.
