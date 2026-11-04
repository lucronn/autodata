# R3 bounded fake-transport preparation collector Implementation Plan

> **For agentic workers:** Execute task-by-task only after the coordinator dispatch bound to a committed synchronized checkpoint, canonical exact-base preflight and independent committed-gate review. Use the coordinator-selected execution workflow; do not create parallel workers or obtain observation authority from this plan.

**Goal:** Implement and independently review a bounded fake-transport R3 preparation collector policy/state machine for exact candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; no host observation or execution adapter.

**Architecture:** A pure policy layer and deterministic event-driven collector consume explicit scripted ports. Fake tests exercise bounded parsing, privacy, prerequisite sequencing, cancellation and exclusive-output finalization. No production adapter or CLI exists in this increment.

**Tech Stack:** Existing coordinator-approved Python 3 interpreter, standard library, unittest; no dependency/package/install changes.

**Spec:** `docs/agents/specs/2026-11-04-workshop-r3-preparation-collector.md` (canonical copy of the two reviewed external revision-2 designs, with their original historical status qualifiers preserved).

## Global constraints

- Exact four new implementation/test paths: `scripts/r3_preparation/policy.py`, `scripts/r3_preparation/collector.py`, `scripts/r3_preparation/test_policy.py`, `scripts/r3_preparation/test_collector.py`. No `__init__.py`, CLI, wrappers, workflow, dependency, application or existing test edits.
- All authority flags remain false. `trusted:false`, `runtime_accepted:false`, `host_observed:false`, `evidence_kind:synthetic`, release `unverified` are mandatory on all synthetic results.
- No real files/commands are observed through collector ports. No host/Git/Docker/Compose execution, secrets, runtime/network/provider/payment/cloud action or source import. Interpreter loading of own modules/tests is the only ordinary verification execution.
- Preserve immutable candidate/launcher/supervisor/probe bytes and all historical evidence. No later owner acceptance or runtime receipt is invented to satisfy this code-only gate.
- Enforce every exact bound, safe projection, state transition, prerequisite, finalization rule and adversarial test in the canonical spec. Missing enforcing primitives block later real collection.
- Planning base is `e3eb94311f69f6e9ecab74be21d399a5cd126c21`; it is a source parent, not this future gate checkpoint. The actual six-document commit SHA is externally pinned after commit; no self-referential future SHA is fabricated.

## Tracking and concrete todo

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Status: `synchronized` tracking at https://github.com/lucronn/autodata/issues/186#issuecomment-6639936878; committed checkpoint/preflight/review and dispatch remain pending. This plan authorizes no implementation. Plan, record, task, canonical document and append-only queue entry carry this identical goal and todo:

- [ ] Independently review this code-only six-document draft; coordinator synchronizes Issue186/Project8 and the identical goal, references and todo, commits/pushes the checkpoint, pins its full SHA, passes canonical exact-base preflight and committed-gate review before explicit four-file code-only dispatch.
- [ ] Write failing strict-contract, command/environment, Git-prerequisite, bounded-JSON and closed-projection tests in scripts/r3_preparation/test_policy.py; implement scripts/r3_preparation/policy.py using synthetic inputs only and verify the focused tests pass.
- [ ] Write failing scripted-port tests in scripts/r3_preparation/test_collector.py; implement scripts/r3_preparation/collector.py with explicit fake file/command/output/clock/cancel ports, nonrenewable budgets, stop precedence and exact finalization ordering.
- [ ] Run the standard-library isolated fake-only suite and the complete adversarial acceptance matrix; assert production limit constants, zero unexpected port calls, no secret-sentinel persistence and synthetic nonpromotion markers; retain honest red/green evidence.
- [ ] Commit and promptly push validated coherent code milestones on the coordinator-assigned branch; obtain independent exact-code review and record exact source hashes, verification evidence and unresolved real-adapter obligations without changing authority.
- [ ] Handoff fake-only code and synthetic evidence with trusted:false, runtime_accepted:false and host_observed:false; leave real adapters, owner contracts, host/Git/Docker/Compose observations, initial probe, PR219 fixtures, final180 and all release/provider/payment/cloud activity behind separate gates.

Canonical planning/document scope (exact six paths):

- `docs/superpowers/plans/2026-11-04-workshop-r3-preparation-collector.md`
- `docs/agents/specs/2026-11-04-workshop-r3-preparation-collector.md`
- `docs/agents/records/2026-11-04-workshop-r3-preparation-collector.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-r3-preparation-collector.json`
- `docs/verification/2026-11-03-canonical-article-lifecycle.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`

## Source pins and review limits

- `/home/corp/autodata-evidence/r3-preparation-gate-draft/PLAN.md`: SHA256 `55d0b1ea66e4125d033e4eaa8a6caf7c77da9fd32925cbbcedc56e75fa59ed2a`.
- `/home/corp/autodata-evidence/r3-preparation-gate-review/revision2-review.md`: SHA256 `19c84aa814dc82388a9596156cd15408d5a8b2f79b98edcb75e2c69357364b99`.
- `/home/corp/autodata-evidence/r3-preparation-collector-design/PLAN.md`: SHA256 `07370ec9c7b3a0f26e0090e258e02bafbdd51ac0fa01f517c7aa365e37b84636`.
- `/home/corp/autodata-evidence/r3-preparation-collector-design-review/revision2-review.md`: SHA256 `007c140dcce6f8420f7a83f953765d47febf6e108e53a9b3858be711cc668546`.

Both revision-2 review reports PASS only correction of their stated findings. They grant no implementation or preparation authority; committed-gate and exact-code reviews remain required. The canonical spec preserves all original provenance and immutable source/image pins. Historical revision4 independent PASS remains a coordinator-reported session attestation, with no separately saved reviewer report/hash; historical test claims are not reruns.

## Task 1: Pure policy admission, parsing and projections

**Files:** create `scripts/r3_preparation/test_policy.py` and `scripts/r3_preparation/policy.py` only.

**Interfaces:** frozen Limits, Contract, CommandSpec, FileSpec, Identity, Problem, SafeObservation and Receipt; `admit_contract(document: bytes) -> Contract | Problem`, `parse_bounded_json(chunks, budget) -> JsonValue | Problem`, `project(kind, value, contract) -> SafeObservation | Problem`, as constrained by spec sections 3–7. Contract objects used by this increment are explicitly synthetic; no boolean promotes them to real trust. All errors are closed enum codes/counts, with exact literal exceptions in the spec.

- [ ] Add failing tests with synthetic fixtures covering every policy row of the spec acceptance matrix, including nested duplicate keys crossing chunk boundaries, exact/+1 budgets, prereq failure before ports, closed argv/env equality and sentinel-bearing arbitrary keys.
- [ ] Run `python3 -I -B -m unittest discover -s scripts/r3_preparation -p 'test_policy.py' -v`; retain the genuine behavioral/import failure, never describe a missing module as a completed policy test.
- [ ] Implement only the policy interfaces and bounded incremental JSON parser needed by those cases. No unrestricted parse followed by depth inspection; no ambient reads, process/socket/OS adapters or input-derived diagnostics.
- [ ] Repeat that focused command and confirm every test passes. Inspect exact diff for unintended paths or side effects.
- [ ] Commit the independently reviewable policy/test milestone and promptly push only under coordinator branch ownership after passing authorized checks.

## Task 2: Collector state, budgets and finalization

**Files:** create `scripts/r3_preparation/test_collector.py` and `scripts/r3_preparation/collector.py` only; policy files may change for integration within the same four-file allowlist.

**Consumes:** Task1 frozen policy types, admission, parser and safe projections.

**Produces:** `collect(contract, files, commands, outputs, clock, cancel) -> CollectionResult`; every port is explicitly injected, implements only the spec's bounded operation/event protocol, and has no default production instance. States are NEW → ADMITTED → FILE_ELIGIBLE → COMMAND_ELIGIBLE → PROJECTED → COMPLETE, with terminal BLOCKED/INCOMPLETE; prerequisites are per observation and stop events latch terminally.

- [ ] Add failing scripted-fake tests for every collector row of the spec matrix; assert exact call order, exact safe outputs, no unexpected calls, no retries/cleanup, and synthetic/nonpromotion fields.
- [ ] Run `python3 -I -B -m unittest discover -s scripts/r3_preparation -p 'test_collector.py' -v` and retain the red result.
- [ ] Implement deterministic event processing, charging before allocation, monotonic nonrenewable budgets, dependent eligibility, transient-only capture, terminal stop ordering and exact payload → REPORT.md → SHA256SUMS → in-memory receipt finalization. No real filesystem writes occur through fake ports; reviewer-owned independent-review.md cannot be fabricated.
- [ ] Run both modules with `python3 -I -B -m unittest discover -s scripts/r3_preparation -p 'test_*.py' -v`; verify all matrix scenarios and exact production constants.
- [ ] Commit/push the validated collector milestone under coordinator branch ownership. If any requirement cannot fit the four files or enforce the reviewed synthetic interface, stop for revised synchronized scope rather than adding adapters or files.

## Task 3: Independent code review and honest handoff

- [ ] Review the exact four-file diff for imports/defaults/CLI paths/ambient I/O, raw exception or JSON-key passthrough, authority promotion, unrestricted parsing and missed stop/finalization boundary cases.
- [ ] Obtain independent exact-code review; repair within the four-file scope, rerunning relevant focused tests then the full command after changes. Record exact verified full SHA and exact source hashes; checks are evidence at that SHA only.
- [ ] Coordinator records code-only completion and synthetic test evidence in a separately controlled documentation/tracking update; no implementation worker expands this checkpoint's scope to mutate unrelated documents.
- [ ] Handoff with real adapter/enforcement and all actual owner/tool/clone/config/observation/dispatch facts unresolved. No real preparation receipt, host observation, runtime approval or PR219/final180 completion is claimed.

## Checkpoint, machine preflight and dispatch

The sole coordinator writer must first supply real live Issue186/Project8 readback matching this exact goal, six refs, four-file future scope and six todos. Only then may the record status become `synchronized` and the matching receipt be copied into record/task/canonical index. Coordinator commits/pushes all six docs, externally pins the actual complete checkpoint SHA, and runs `scripts/autonomy/pre_implementation.py`'s canonical `validate_record` at that exact base with `.autodata-autonomy-policy.json`; retain exact record/preflight bytes and SHA256 with exit 0, `errors:[]`, not timed out. Independent review inspects committed bytes. Fresh dispatch binds that checkpoint and review to the four-file code-only allowlist. Until every step passes, no implementation edit is permitted.

A `status:synchronized` record means genuine tracking/document synchronization only. It cannot prove real adapter enforcement, owner approval, host compatibility or runtime acceptance. No future code SHA, execution checkpoint, owner identity, root/token, tool identity or observation is fabricated here.

## Self-review

The spec embeds the full reviewed acceptance matrix and every bound/command/privacy/finalization requirement; Tasks1/2 implement and test it, Task3 independently reviews its exact delivered bytes. The two revision-2 fixes remain mandatory: closed literal rejected-key projection, and REPORT included in sorted SHA256SUMS followed by a separate final in-memory receipt. Namespace-package test loading is explicit file-location loading rooted at the tests' own directory; no sys.path mutation, candidate imports, bytecode or fixture persistence.


### R3 collector live planning synchronization receipt

Issue detail: https://github.com/lucronn/autodata/issues/186#issuecomment-6639936878. Coordinator sole serialized writer read back exact matching goal, six planning paths, four future implementation paths and six todo entries. Issue body and all 173 prior comments are preserved (174 current); previous Project Source archived verbatim and other Project fields unchanged. Project status remains In Progress. Receipt `/home/corp/autodata-evidence/r3-preparation-collector-gate-tracking/receipt.json`, SHA256 `3d2937b91770feaffaa4bfd4a5df18b3fda15f13910654650ecbbb5d19d44be1`. Independent draft review PASS is coordinator-reported, not committed-gate/code/runtime acceptance.

Exact live receipt (verbatim field values):

```json
{
  "candidate_sha": "4d82e413e04fb2401ac7bc28dc828375ac662180",
  "current_comment_count": 174,
  "goal": "Implement and independently review a bounded fake-transport R3 preparation collector policy/state machine for exact candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; no host observation or execution adapter.",
  "implementation_allowlist": [
    "scripts/r3_preparation/policy.py",
    "scripts/r3_preparation/collector.py",
    "scripts/r3_preparation/test_policy.py",
    "scripts/r3_preparation/test_collector.py"
  ],
  "issue_after_sha256": "2ac723432b9a3ebd315ea66ed724e35066b89c210b732d1fcbb8da1e9f66f269",
  "issue_before_sha256": "376583bf9a466cfd7408c9619de4b45179fb86bb8ce02203034bff79ec63ca0c",
  "issue_body_unchanged": true,
  "issue_comment": "https://github.com/lucronn/autodata/issues/186#issuecomment-6639936878",
  "other_project_fields_unchanged": true,
  "planning_base_sha": "e3eb94311f69f6e9ecab74be21d399a5cd126c21",
  "planning_paths": [
    "docs/superpowers/plans/2026-11-04-workshop-r3-preparation-collector.md",
    "docs/agents/specs/2026-11-04-workshop-r3-preparation-collector.md",
    "docs/agents/records/2026-11-04-workshop-r3-preparation-collector.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-r3-preparation-collector.json",
    "docs/verification/2026-11-03-canonical-article-lifecycle.md",
    "docs/agents/tasks/2026-11-03-production-release/queue.json"
  ],
  "previous_source_archived_verbatim": true,
  "prior_comment_count": 173,
  "prior_comments_preserved": true,
  "prior_project_source_sha256": "db7aa0b80bfae8d8a6b2550f588b7d7ce635c070ae1dce5e80970aa9ab04091c",
  "project_after_sha256": "e4aef634865eee20e992ebea2fdc522690cce3ae1bc5379312478b4334b22a04",
  "project_before_sha256": "bdbcb5b32c7990bb0aaf5c6b08eaffd0248d5865e4b05ca676156995b37d719d",
  "project_source_sha256": "e4766212ff8a2a95f62e0893c583e5fc92577c55930efa2ea5599660d27f108f",
  "project_status": "In Progress",
  "status": "synchronized_live_readback",
  "todo": [
    "Independently review this code-only six-document draft; coordinator synchronizes Issue186/Project8 and the identical goal, references and todo, commits/pushes the checkpoint, pins its full SHA, passes canonical exact-base preflight and committed-gate review before explicit four-file code-only dispatch.",
    "Write failing strict-contract, command/environment, Git-prerequisite, bounded-JSON and closed-projection tests in scripts/r3_preparation/test_policy.py; implement scripts/r3_preparation/policy.py using synthetic inputs only and verify the focused tests pass.",
    "Write failing scripted-port tests in scripts/r3_preparation/test_collector.py; implement scripts/r3_preparation/collector.py with explicit fake file/command/output/clock/cancel ports, nonrenewable budgets, stop precedence and exact finalization ordering.",
    "Run the standard-library isolated fake-only suite and the complete adversarial acceptance matrix; assert production limit constants, zero unexpected port calls, no secret-sentinel persistence and synthetic nonpromotion markers; retain honest red/green evidence.",
    "Commit and promptly push validated coherent code milestones on the coordinator-assigned branch; obtain independent exact-code review and record exact source hashes, verification evidence and unresolved real-adapter obligations without changing authority.",
    "Handoff fake-only code and synthetic evidence with trusted:false, runtime_accepted:false and host_observed:false; leave real adapters, owner contracts, host/Git/Docker/Compose observations, initial probe, PR219 fixtures, final180 and all release/provider/payment/cloud activity behind separate gates."
  ],
  "writer": "coordinator sole serialized writer"
}
```

The coordinator authorized committing/pushing exactly this six-document checkpoint. Actual checkpoint SHA is externally pinned after commit; then standalone/nested canonical preflight and independent exact-committed-gate review remain required before fresh code-only dispatch. No implementation or observation dispatch is supplied by this receipt; all authorities remain false.
