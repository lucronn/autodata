# Workshop final180 Offline Admission and Reconciliation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans only after this dedicated Stage A record is synchronized at a committed checkpoint and exact-base preflight passes. This synchronized checkpoint authorizes no implementation until exact-base preflight, independent committed-gate review and coordinator dispatch.

**Goal:** Implement only offline final180 source admission and normalized claim reconciliation; keep the executable runner backend blocked and every authority false.

**Architecture:** A standard-library offline diagnostic reads the pinned inventory from trusted Git objects, inspects the clean selected candidate, and reconciles caller-supplied normalized IDs. It collects no fixtures and parses no raw producer formats; Stage B executable supervision remains a separate blocked gate.

**Tech Stack:** Python3 standard library, unittest, injected GitReader and owned temporary files.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-runner.md`, Stage A only.

## Global constraints

- Planning parent d8579c824eb1ebf546b46b13a0f69079890ad44e (PR218); application4d82e413e04fb2401ac7bc28dc828375ac662180; historical inspection df52326b2a12fd17db39d9368f66a28a366f38ad. Future authorizing checkpoint and reviewed runner SHA are separate external inputs.
- Issue https://github.com/lucronn/autodata/issues/186 ; Project https://github.com/users/lucronn/projects/8 ; item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 has live coordinator synchronization/readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6636377383.
- Exact allowlist scripts/dev/workshop_final180_runner.py, scripts/dev/test_workshop_final180_runner.py, docs/verification/workshop-final180-runbook.md. No producer/assembler/evaluator/policy/profile/application/SQL/Compose/workflow/dependency edit.
- Exactly5+8+14+12+120+21 literal IDs; support0; all authority false. No run command or runtime backend in Stage A.
- gpt-6.1-sol / medium / Fast if exposed, no silent fallback.

## Canonical todo

- [ ] Implement Stage A strict immutable inventory loading and clean pinned-candidate source inspection within the three-path allowlist.
- [ ] Implement Stage A normalized observation schema, exact literal-ID multiset reconciliation and private offline diagnostic output with all authority false.
- [ ] Run adversarial offline unit tests and independent exact-SHA review; document blocked Stage B runtime/backend and separately gated raw validators.

## Task1: strict immutable source admission

Create scripts/dev/workshop_final180_runner.py and scripts/dev/test_workshop_final180_runner.py. Consume Contract/GitReader schemas from Stage A spec; produce SourceInspection and inspect diagnostic. Do not implement future supervise/Adapters/raw parsers. Write table-driven stdlib unittest/tempfile/fake GitReader tests first: valid pinned inventory/candidate; wrong SHA; dirty/untracked/ignored/missing/extra/mode-changed source; symlink/hardlink/device/path traversal; nested JSON/duplicate keys/NaN/BOM/wrong primitive/null/missing/unknown observation keys; input drift and unsafe output parent. Test all82 pins and full tracked source independently; test checkpoint contract mismatch; assert no preflight-receipt CLI/file dependency and no candidate imports/network/Docker/fixture command. Test fixed Git path resolution/version argv, recorded git_tool path/hash/version and executable drift; admit stock executable/nonexecutable .sample hooks and reject nonsample/custom hooks/configured hooksPath. Production Git uses isolated fixed read-only argv and no caller override.

- [ ] Write failing tests for public load_contract/inspect_candidate/load_json_strict interfaces and exact source failures.
- [ ] Run `python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v`, confirming failures target missing behavior.
- [ ] Implement only strict immutable loading, source admission and inspect output per Stage A schemas.
- [ ] Run suite, `python3 -m py_compile scripts/dev/workshop_final180_runner.py scripts/dev/test_workshop_final180_runner.py`, diff and three-path allowlist checks; commit/push validated milestone only after coordinator branch authorization.

## Task2: normalized reconciliation and handoff

Same files plus create docs/verification/workshop-final180-runbook.md. Consume exact Stage A observation schema; produce diagnostic.json and source-manifest.json. Test exact180 pass claims and for each family one missing/duplicate/extra/skipped/failed/unavailable ID while count remains unchanged; reject DTO substituted for API and wrong candidate. Assert raw_refs are never opened or trusted, caller count/authority/profile/summary rejected, source inventory immutable, deterministic failure order, duplicate occurrence retained, authority false for consistent diagnostics. Test atomic private output/modes/drift/size ceilings and interruption. Test512 maximum-length/control-character unknown failed IDs produces a complete diagnostic below4MiB;513 rows (including the3500-row review counterexample) must reject before reconciliation with unavailable/observation_count_exceeded, no prefix result. Independently test diagnostic_size_invariant fallback remains bounded/nonpass and every successful diagnostic records git_tool. `run`/unknown options must exit2 before output creation; all diagnostics must make clear claims are not measured execution. Runbook documents exact inspect/reconcile CLI, pins, claim-only trust, pending Stage B and raw/acceptance gates.

- [ ] Write failing tests for these reconciliation/output/CLI cases; implement minimal matching Stage A functions only.
- [ ] Run `python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v`, `python3 -m unittest discover -s scripts/dev -p 'test_*.py'`, `python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'`, syntax/diff/allowlist checks. Report unsupported environment/dependency failures exactly; do not claim unrun checks pass.
- [ ] Commit/push coherent validated milestone after coordinator authorization; obtain independent exact-SHA scope/behavior review. No fixture execution, profile promotion, merge or deployment follows.

## Gate synchronization and blockers

The task.pre_implementation and record are synchronized with coordinator Issue186/Project8 live readback and independent draft review PASS. Initial checkpoint `82b0b0b15fa70452d44c65160f4d3f412be30584` passed standalone/nested preflight but exact review found stale status wording; this corrective checkpoint replaces it for dispatch. For the full SHA B of this committed synchronized docs state, run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-final180-runner.json --base-sha B --repo-root <owned-checkout> --policy <policy-at-B>`; require exit0/status synchronized/errors empty and matching references at B. The record must already be synchronized at B; an older parent cannot authorize Stage A. Preflight result and live tracking freshness are coordinator-only dispatch enforcement, not a Stage A CLI input or receipt schema. Any correction after B requires a new committed checkpoint and preflight at its exact SHA. This gate can become Stage A implementation-ready after those steps.

Full bounded runner Stage B is not implementation-ready. Its exact raw producer schemas/result-to-ID mappings, concrete Docker/service/image argv and run-record/runtime-lock contracts need a separate completed gate. Actual immutable host tools, images/recipes, offline dependencies/browser-cache, storage/headroom/retention locator and registered operator/run authority remain unobserved. Retained design choices (serial budgets, DTO lifecycle, private16MiB traces) do not authorize backend implementation or execution. No nominal synchronized full-runner gate may hide this discretion.
