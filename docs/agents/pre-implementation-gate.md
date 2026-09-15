# Pre-Implementation Planning and Tracking Gate

**Status:** enforced repository workflow
**Scope:** every implementation agent, provider, model, IDE, and automation interface
**Canonical location:** this document is the sole normative source for the gate

**Current verified implementation:** `99175fff019957264ab77914dbdf6c53b9d5aaf8`

## Purpose

AutoData work begins with a traceable plan. Before any implementation agent changes application, schema, infrastructure, workflow, or other implementation files, the task must have a written plan, synchronized GitHub tracking, and canonical repository documentation that state the same goal and work items.

This rule is agent-agnostic. The agent name, model, provider, CLI, and editor do not change the required order or allow an implementation to bypass the gate.

## Required order

1. Write a decision-complete plan under `docs/superpowers/plans/`.
2. Create or identify the GitHub Issue and add or identify its Project #8 item.
3. Update the Issue, Project item, and canonical repository documentation with the goal, references, and concrete `todo` list.
4. Record the synchronized pre-implementation record and pin it to the implementation base SHA.
5. Run the machine preflight. A failed or missing preflight is a blocking result.
6. Only after preflight passes may an implementation agent create or modify implementation files.

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

- Planning agents may create or revise the plan and return the record; they do not implement the task.
- Implementation agents must read this gate and the referenced plan, verify that preflight passed, and stop with a blocking result when it did not.
- Verification agents inspect the exact implementation SHA and do not repair a missing planning record by silently changing scope.
- Release agents re-check the Issue, Project item, canonical documents, and exact SHA before creating or merging a pull request.

No agent may treat a natural-language approval, an untracked file, an unverified Issue number, or a Project title alone as a passing record.

## Enforcement boundary

The checked-in `.autodata-autonomy-policy.json` declares this record and its canonical paths. `scripts/autonomy/pre_implementation.py` validates the record. `scripts/autonomy/runner.py` rejects implementation-role envelopes before output setup, worktree creation, or provider invocation. `scripts/autonomy/orchestrator.py` rejects an architect result before invoking the builder.

`AGENTS.md` and `.cursor/rules/plan-before-implementation.mdc` are discovery adapters only. They point here so agents that discover different repository instruction files still receive one rule and one record shape.

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
are the synchronized delivery records. The rule remains required for all later
implementation work; this verified implementation does not waive the gate for
future tasks.

## Evidence and recovery

The Issue and Project item must retain the goal, plan/document links, concrete todo, current status, and exact verified commit. The plan and gate document must record test and CI evidence after implementation. If GitHub or repository synchronization cannot be verified, leave the task blocked and do not begin implementation. Correct the record, commit the checkpoint, and run preflight again; do not bypass the gate or rewrite an earlier implementation result.
