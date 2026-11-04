# Workshop final180 Stage B1 Identity Translation and Fake Replay Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans only after this dedicated B1 record is synchronized at a committed checkpoint, exact-base preflight passes, independent committed-gate review passes and the coordinator explicitly dispatches implementation. This synchronized planning record authorizes no implementation until exact-base preflight, independent committed-gate review and explicit coordinator dispatch.

**Goal:** Add only an in-memory identity Go JSONL adapter and finite fake-runtime replay for the five frozen identity IDs; preserve Stage A and zero accepted-case credit, disabled profiles and every authority false.

**Architecture:** A new standard-library library parses a restricted in-memory Go JSONL profile and maps exactly five literal identity tests to synthetic outcomes. A finite FakeFrame replay supplies only bytes and simulated termination facts. Stage A admission/reconciliation and its CLI remain unchanged; real execution and the other 175 cases remain separate blocked successors.

**Tech Stack:** Python 3 standard library, frozen dataclasses, unittest and synthetic bytes-only fixtures.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-stage-b1-identity.md` (including embedded exact mapping/provenance and normative review-repair examples).

## Global constraints

- Issue186/Project8 tracking is synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6637529257; committed checkpoint B, exact-B standalone/nested preflight, independent gate review and explicit dispatch remain required.
- Exact planning parent `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e` (reviewed Stage A / PR223 dependency); application candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`. B must descend from that exact parent. A different base requires revised scope/base review.
- Issue https://github.com/lucronn/autodata/issues/186 ; Project https://github.com/users/lucronn/projects/8 ; historical item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4, Source field PVTF_lAHOCSJ8cc4BiQ2BzhhJhxU. These IDs prove no current live state.
- Exact future implementation allowlist: `scripts/dev/workshop_final180_identity_adapter.py`, `scripts/dev/test_workshop_final180_identity_adapter.py`, `docs/verification/workshop-final180-runbook.md`. No Stage A module/test, producer, assembler, evaluator, profile/policy, application, SQL, Compose, workflow or dependency edits.
- All nine authority booleans false; accepted_case_credit=0; profiles_enabled=false; enabled_tiers=[]; runtime_lock=null and run_record=null. Support/root adds zero logical IDs. No full180 output.
- gpt-6.1-sol / medium / Fast if available, no silent fallback. Tool exposes no explicit Fast toggle; an unsupported speed request is not a claim of actual Fast execution.
- Exact contract, parser/replay budgets, error vocabulary and status precedence are normative in the spec. No new compatibility inference or live Go/runtime observation is authorized.

## Canonical todo

- [ ] Synchronize the identity-only B1 plan/spec/task/record and exact three-path allowlist with Issue186/Project8; commit/push checkpoint B descending from reviewed Stage A 2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e, pass standalone/nested exact-B preflight and independent gate review before explicit coordinator dispatch.
- [ ] Implement bounded bytes-only Go JSONL parsing and deterministic five-ID identity translation with frozen context/receipt types, exact lifecycle/status precedence and failing-first adversarial synthetic tests.
- [ ] Implement finite FakeFrame replay with total equal-time ordering, fixed 180s deadline/5s TERM grace/10s cleanup ceiling, bounded bytes and no process/filesystem/network execution; serialize exactly five ordered synthetic rows with zero credit and all authority false.
- [ ] Update only the runbook alongside the two new modules; run focused/Stage A/developer/autonomy/syntax/allowlist checks, commit/push coherent validated milestones and obtain independent exact-implementation-SHA review.
- [ ] Record code-only evidence while preserving disabled profiles/tiers, null runtime lock/run record and separate gates for other raw validators, real runtime/Docker supervision and actual final180 execution.

## File responsibilities and interfaces

- Create `scripts/dev/workshop_final180_identity_adapter.py`: frozen dataclasses plus `parse_identity_events`, `translate_identity`, `replay_identity_fake`, `serialize_identity_diagnostic` exactly as specified. Importable library only, no CLI/entrypoint, filesystem reads, mutable execution plan or real runtime callbacks.
- Create `scripts/dev/test_workshop_final180_identity_adapter.py`: offline unittest fixtures built independently from spec literals and adversarial repaired inputs; no genuine-run artifact or new case ID.
- Modify `docs/verification/workshop-final180-runbook.md`: explain synthetic-only trust, diagnostic metadata, omitted migration/JUnit/SQL semantics and unchanged Stage A commands/blocked successors.
- Interfaces consume only bytes, `IdentityContext`, `SimulatedExit` and tuple `FakeFrame`; produce typed `GoEvent`, `CaseOutcome`, `IdentityDiagnostic`, `FakeReplay` and bounded canonical bytes. Exact field types/signatures are copied in the spec, not inferred from producer imports.

## Failing-first milestones and concrete todo

Each milestone starts only after coordinator promotion, synchronized committed checkpoint, exact-base passing preflight, independent gate review and explicit branch dispatch. Commit small coherent milestones after checks and push promptly to assigned feature branch; never change candidate source or expand allowlist. Tests use synthetic bytes only. Set `PYTHONDONTWRITEBYTECODE=1` to keep generated caches outside source expectations.

### M1: strict raw parser and deterministic five-ID translation

- [ ] Create the new test module with positive minimal package/root/five-child synthetic stream and table-driven parser/semantic counterexamples; import of the absent new module must be the initial expected failure.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_identity_adapter.py -v`; retain failing output and distinguish missing behavior from environment errors.
- [ ] Implement only dataclasses, bounded parse, context/receipt validation and translation in the new adapter module.
- [ ] Test each active ID one-at-a-time missing/duplicate/skip/fail; duplicate run and pass; terminal before run; child after root terminal; package missing/failed/skipped/wrong identity; parent-only pass; foreign/nested IDs; repeat output; source summary flags containing passed=true cannot substitute; process nonzero/timeout/cancel despite complete clean bytes; all5 output order and zero authority/credit.
- [ ] Test all grammar/type/size limits at bound and bound+1, duplicate keys/nonfinite/BOM/invalid UTF8/surrogate/null/unknown field/action, bool Elapsed, huge string/depth/line/count, blank/CRLF and optional final LF. Unsupported profile -> all unavailable with no prefix, not merely a count mismatch.
- [ ] Run focused suite, baseline `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v`, `git diff --check`, exact allowlist check; commit and push the validated parser milestone only with coordinator branch ownership.

Minimal synthetic positive fixture recipe, to encode locally in tests (never label it captured evidence): one package start; root run; for each full literal child in frozen order one run then pass; root pass; package pass. All event Time='2026-11-04T00:00:00Z', Package exact above; append one LF per compact JSON object. SimulatedExit(0,False,False,False,True). Expected status consistent, five passed rows and accepted_case_credit0. Removing the first child's pass -> inconsistent and that child failed; replacing its pass with skip -> inconsistent and that child skipped; adding wrong Package anywhere -> all5 failed.

### M2: bounded fake replay and serialization handoff

- [ ] Add failing tests for fake frame validation (every terminal kind rejects None/bool code; every nonterminal kind rejects int/bool code), no-exit EOF, normal nonzero, deadline equality, TERM acknowledgement before/at5s, KILL acknowledgement before/at10s, ownership loss before/during cleanup and at scheduled TERM/KILL, cancellation at same timestamp as exit/term_exit/kill_exit, every total-order table tie in both tuple permutations, frames after exit, chunks at/exceeding all bounds, repeated trigger attempts and no deadline replenishment.
- [ ] Run focused suite and record intended failures; implement finite replay exactly above, with no real clock/process/filesystem/network adapters.
- [ ] Connect fake stdout/stderr/result to translate_identity; test clean bytes+timeout/cancel/lost identity cannot be consistent; parser rejection plus receipt failure ordering; serializer deterministic roundtrip; exactly5 unique ordered rows; four/six/duplicate/reordered/wrong-family rows rejected; explicit profiles_enabled=false/enabled_tiers=[] present; nonempty tiers/true profiles/unknown authority keys/true values rejected; maximum diagnostic bound. Assert dynamic Output/unknown Test never leaks into failures.
- [ ] Add tests checking module AST/import surface excludes subprocess/socket/http/asyncio/OS signal paths, and run Stage A baseline proving CLI inspect/reconcile contracts and run rejection unchanged. AST check is scope evidence, not a security sandbox.
- [ ] Document synthetic library usage/trust in runbook, including omitted migration/JUnit/SQL validation and unchanged blocked real180 successors.
- [ ] Run focused adapter suite; Stage A suite; `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'`; `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'`; syntax via AST parse of both new files, `git diff --check`, exact three-path allowlist. Report dependency/environment failures with exact command/result; never claim unrun checks pass. Do not launch Docker or fixtures to repair environment failures.
- [ ] Commit/push bounded fake replay milestone; independent exact-SHA code review must check source/profile restrictions, all status precedence, fake deadline/ownership decisions, byte bounds, preserved Stage A behavior and absence of real adapters. Record reviewed exact implementation SHA and checks in canonical plan/Issue186/Project8; any changes require fresh tests/review.


## Coordinator synchronization and dispatch

1. Coordinator alone reads current Issue186/Project8, preserves complete prior Issue content/comments and archives Project Source verbatim, then updates the same B1 goal, references, exact allowlist and five todo items above. Prior Stage A receipts are historical and cannot prove B1 synchronization.
2. Read back both writes and bind exact receipts/hashes. Only after matching live tracking and repository documents agree may the coordinator replace record status `blocked` with `synchronized` and copy the identical complete object into task.pre_implementation. Keep all authority false and runtime_lock/run_record null. Broader Stage B remains blocked.
3. Commit/push the docs checkpoint; B is its actual full40 SHA, supplied externally without self-reference. Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-final180-stage-b1-identity.json --base-sha B --repo-root <owned-checkout> --policy <policy-at-B>`, substituting actual values. Require exit0, status synchronized, errors empty. Validate task.pre_implementation with the same canonical validator/policy at B and verify exact equality with the record. These are coordinator-direct task documents, not autonomous runner TaskContract envelopes.
4. Obtain independent exact-B review and fresh Issue/Project readback before explicit branch-owner implementation dispatch. A changed plan/spec/record creates a new checkpoint and repeats preflight/review. Never implement at parent `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e` merely because Stage A passed.
5. After each milestone run its checks, commit/push coherent validated code to the assigned feature branch and obtain independent exact-implementation-SHA review. Coordinator records actual code/check/review evidence and preserves B as authorizing checkpoint. No merge/deployment/runtime/profile acceptance follows from unit success.

## Planning provenance and self-review

Corrected external DRAFT.md SHA256 `1e596d2d71c11b90a4428ac094c397703706063b065261c3957ca82218284ca1`; report SHA256 `f8ee1a1c0bfdb3e2dbf3410937a790d30ac4247464a543763bb08596f31c1588`. Exact source copies, mappings and immutable pins live inside the spec. Draft review PASS is coordinator-reported; committed-gate review remains required. Promotion independently verified 79 immutable candidate/Stage A source/context pins plus inventory bytes/hash, and all180 literal IDs/counts against frozen inventory. This is a source/document check, never fixture or application execution.

Coverage: M1 covers public types, strict grammar, fixed mapping and lifecycle/receipt precedence; M2 covers complete finite replay ordering/bounds, serializer authority/row invariants, unchanged Stage A behavior and runbook. The spec's normative boundary examples are explicit acceptance cases for M2. No technical input depends on an external temporary locator. Unresolved facts are only the separately gated actual Go compatibility, other-family semantics and runtime/tool/operator/retention facts listed in the spec.

## Code-only implementation receipt (2026-11-04)

The synchronized planning checkpoint was committed and independently reviewed at `006fab0d1380c2506330bbc0b48397a32294b6cc`; standalone and nested preflight returned `status: synchronized`, `errors: []` before explicit branch dispatch. The builder pushed parser milestone `ddef4e51533cc6693ce58479180ecfb93fe91e14` and fake-replay/serializer milestone `54a7ca32eab80654310d862f0ac6957375d16e8b` on `codex/workshop-final180-stage-b1-build`. The exact three-path diff is draft [PR #228](https://github.com/lucronn/autodata/pull/228).

Independent read-only exact-head review of `54a7ca32eab80654310d862f0ac6957375d16e8b` reported **PASS with no actionable findings**. The reviewer reran 25 adapter, 52 Stage A and 146 autonomy tests, confirmed the unchanged Stage A module/tests, verified the source and evidence hashes and inspected the builder's passing 335-test developer log. The 335-test run loaded 23 adapter tests before two further coverage tests were added; the final 25-test run covers the exact head. AST syntax, whitespace and exact three-path scope checks passed. Builder evidence report `/home/corp/autodata-evidence/final180-stage-b1-builder/report.json` has SHA-256 `011549c357d18fb7ec3563ad1d8d0c19247fc68e1cfb4758a730a03c81fa4676`.

This receipt supersedes historical pending-review wording only for the synthetic identity slice. All nine authority flags remain false, accepted-case credit is zero, profiles are disabled, and runtime lock/run record remain null. Real Go execution, the other 175 raw validators, complete final180, profile promotion, merge and deployment remain separate blocked successors. The Stage A CI fixture follow-up on its own branch does not change this checkpoint or authorize a new B1 scope.
