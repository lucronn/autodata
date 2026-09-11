# Pre-Implementation Planning and Tracking Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce an agent-agnostic gate that blocks implementation until a measurable plan, synchronized GitHub Issue/Project record, and canonical repository documentation record exist.

**Architecture:** Keep one normative gate under `docs/agents/`, expose it through a root `AGENTS.md` pointer and an always-applied `.cursor/rules` adapter, and enforce the same record in the checked-in autonomy policy. The runner rejects implementation envelopes before worktree creation, while the orchestrator validates architect output before invoking a builder.

**Tech Stack:** Markdown rule adapters, JSON policy configuration, Python `pathlib`/`subprocess` validation, the existing autonomy runner/orchestrator, `unittest`, GitHub Issue #86, and GitHub Project #8.

**Spec:** `docs/agents/pre-implementation-gate.md`

## Pre-Implementation Tracking

- **Goal:** Enforce an agent-agnostic gate that blocks implementation until a measurable plan, synchronized GitHub Issue/Project record, and canonical repository documentation record exist.
- **GitHub Issue:** [#86 — Enforce pre-implementation planning and tracking gate](https://github.com/lucronn/autodata/issues/86)
- **GitHub Project:** [Project #8 — AutoData Portfolio](https://github.com/users/lucronn/projects/8)
- **Repository record:** This plan is the canonical planning record for the gate implementation; the normative rule will live at `docs/agents/pre-implementation-gate.md`.
- **Todo before implementation:** create the canonical rule and adapters; add policy-backed validation; enforce runner/orchestrator boundaries; add focused tests; verify and synchronize the final commit in GitHub.
- **Tracking status:** implementation complete; the planning checkpoint was synchronized before implementation and the verified delivery records are synchronized below.

## Implementation and verification status

- **Planning checkpoint:** `ef1a8582818086228a06dedb8c02a60e400e11d0`
- **Implementation commit:** `99175fff019957264ab77914dbdf6c53b9d5aaf8`
- **GitHub Issue:** [#86](https://github.com/lucronn/autodata/issues/86)
- **GitHub Project:** [Project #8](https://github.com/users/lucronn/projects/8)
- **CI verification:** [Autonomous Verification run 34564744459](https://github.com/lucronn/autodata/actions/runs/34564744459) passed, including the live Compose fast-lane smoke.
- **Local verification:** autonomy `37 passed`; ingestion `240 passed` plus `12 subtests`; enrichment `46 passed` plus `16 subtests`; developer adapters `44 passed`; Go API/shared contracts passed; contract checks `7 tests`, `OK`; policy and diff checks passed.
- **Working-tree boundary:** the user-owned untracked `sample data/` directory remains untouched and is not part of the implementation commits.

## Global Constraints

- The rule applies to every implementation agent and provider; it must not depend on a model, CLI, IDE, or agent name.
- The order is plan -> synchronize GitHub Issue/Project and canonical repository docs -> validate the record -> implement.
- The gate fails closed before an implementation worktree is created or a builder process is invoked.
- Normative documentation remains under `docs/`; `AGENTS.md` and `.cursor/rules/` are discovery adapters, not competing sources of truth.
- Existing sample data remains untracked and credentials remain outside the repository.

---

### Task 1: Write the canonical gate and discovery adapters

**Files:** Create `docs/agents/pre-implementation-gate.md`, `AGENTS.md`, and `.cursor/rules/plan-before-implementation.mdc`; modify the orchestrator, architect, Go-builder, and Python-builder agent prompts under `.cursor/agents/`.

**Record contract:** The pre-implementation record contains non-empty `goal`, `plan_ref`, `issue_ref`, `project_ref`, `repository_doc_refs`, `todo`, `status`, and `updated_at` fields. `plan_ref` points under `docs/superpowers/plans/`; repository document references point under `docs/`; `status` must be `synchronized`.

- [x] Write the canonical gate with purpose, scope, required fields, execution order, fail-closed behavior, evidence requirements, and the rule that Project items are an index while repository docs remain authoritative. Include the concrete Issue #86 and Project #8 record for this change.
- [x] Add the root and `.cursor` adapters as short pointers to the canonical gate. State that every implementation agent must stop when the record is absent, stale, or unsynchronized.
- [x] Add the same gate reference to the existing coordinator, architect, and builder prompts. The architect returns the record; builders cannot override the gate.
- [x] Run `git diff --check` and a focused `rg` scan for the record field names.
- [x] Stage only these documentation/adapters, inspect `git diff --cached --name-only`, and commit `docs: add pre-implementation planning gate`.

### Task 2: Add policy-backed preflight validation

**Files:** Create `scripts/autonomy/pre_implementation.py` and `scripts/autonomy/test_pre_implementation.py`; modify `.autodata-autonomy-policy.json`.

**Interface:** Implement `validate_record(record: Any, repo_root: Path, base_sha: str, policy: dict[str, Any]) -> list[str]`. A valid record returns `[]`; every other result is a deterministic blocking error naming the failed field or pinned repository reference.

- [x] Write failing tests for a missing record, missing fields, invalid Issue/Project URLs, empty todo, non-canonical or missing plan, missing repository docs, unsynchronized status, and a valid record.
- [x] Run `PYTHONPATH=scripts/autonomy python3 -m pytest scripts/autonomy/test_pre_implementation.py -q` and observe the expected missing-module/validation failure.
- [x] Implement validation of the required fields, URL shapes, canonical paths, plan/document existence at `base_sha`, non-empty todo strings, `status=synchronized`, and a non-empty UTC timestamp. Read references with `git show <base_sha>:<path>` so newer uncommitted files cannot authorize a builder.
- [x] Add policy keys `pre_implementation.required`, `required_status`, `required_fields`, `plan_paths: ["docs/superpowers/plans/**"]`, and `repository_doc_paths: ["docs/**"]`.
- [x] Run the focused tests, inspect staged paths, and commit `feat: validate pre-implementation tracking records`.

### Task 3: Enforce the gate at runner and orchestrator boundaries

**Files:** Modify `scripts/autonomy/runner.py`, `scripts/autonomy/orchestrator.py`, `scripts/autonomy/test_runner.py`, and `scripts/autonomy/test_orchestrator.py`.

**Interfaces:** Add `pre_implementation` to the architect task-contract schema. `run_agent` validates it for implementation-role agents before output setup, guard creation, worktree creation, or provider invocation. `orchestrate_task` validates the architect contract against the pinned base SHA before constructing or invoking the builder envelope.

- [x] Extend the runner schema and orchestrator contract validation with the nested record.
- [x] Add a test proving a builder without the record raises a blocking error and leaves no worktree; add a test proving a stale architect record returns a planning block without calling the builder.
- [x] Implement runner enforcement for implementation-role agents and orchestrator enforcement after planning. Planning and gate agents may run without the record so they can produce or inspect it.
- [x] Run `PYTHONPATH=scripts/autonomy python3 -m pytest scripts/autonomy/test_runner.py scripts/autonomy/test_orchestrator.py -q`, inspect the staged paths, and commit `feat: enforce planning gate before implementation`.

### Task 4: Verify and synchronize delivery records

**Files:** Modify the canonical gate and this plan with exact verification; update Issue #86 and its Project #8 item through the authorized GitHub interface.

- [x] Run the complete relevant Go, Python, autonomy, developer-script, contract, and `git diff --check` suites.
- [x] Verify missing, stale, and valid records at the implementation boundary; confirm the provider remains unable to contact GitHub or deployment targets.
- [x] Record the exact implementation SHA, local test results, CI URL, and remaining follow-ups in the canonical gate and plan.
- [x] Update Issue #86’s acceptance checklist and Project #8 source/dependency reference to that exact SHA. Do not close the issue without fresh evidence for every criterion.
- [x] Push with `git push origin HEAD:automation/knowledge-fallback-runtime`, verify `git rev-parse HEAD` equals `git ls-remote`, and re-read the GitHub issue/project/CI records.

## Expected implementation outcome

Every implementation agent, regardless of provider or interface, encounters one machine-checked pre-implementation gate. A task cannot reach builder work until its goal, plan, GitHub Issue/Project references, canonical repository docs, and concrete todo list are synchronized and pinned to the builder’s base SHA.
