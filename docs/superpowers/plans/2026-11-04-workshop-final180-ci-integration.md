# Workshop final180 CI integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this single bounded repair task-by-task after the complete gate and explicit exact-checkpoint coordinator dispatch. Steps use checkbox syntax for tracking.

**Goal:** Carry the exact Stage A CI Git-metadata test-fixture isolation repair into the reviewed B2 stack without changing production behavior or earning runtime acceptance credit.

**Architecture:** Reuse the exact reviewed Stage A test-only repair on top of the complete reviewed B2 stack. Production Git configuration admission stays strict; every ProductionGitTests constructor reads owned passive fixture metadata. No adapter, runtime or acceptance contract changes.

**Tech Stack:** Python standard library unittest/mock/tempfile, host Git, GitHub Actions readback.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-ci-integration.md` (normative exact patch, source pins, regression and validation commands).

**Status:** Issue186/Project8 planning `synchronized` with live readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6638503013. The coordinator preserved all 160 prior comments, now 161, the Issue body and unrelated Project fields, and archived the prior Project Source verbatim. Independent pre-sync five-file draft review PASS with no findings is coordinator-reported. Committed-checkpoint preflight, independent exact-checkpoint review and explicit builder dispatch remain required; none is asserted by tracking synchronization.

**Goal:** Carry the exact Stage A CI Git-metadata test-fixture isolation repair into the reviewed B2 stack without changing production behavior or earning runtime acceptance credit.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8

**Exact planning parent / reviewed B2 head:** `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471` on `codex/workshop-final180-stage-b2-build`, draft PR https://github.com/lucronn/autodata/pull/230. Independent exact-head review PASS with no findings is coordinator-reported; this successor requires a separate exact-checkpoint review. **Application candidate remains:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. This CI integration changes tooling tests, not candidate identity.

## Global Constraints

- Implementation allowlist is exactly `scripts/dev/test_workshop_final180_runner.py` and `docs/verification/workshop-final180-runbook.md`.
- Test repair is byte-for-byte the pinned source version of the one test file; do not cherry-pick unrelated history or broaden the patch.
- ProductionGitReader and all Stage A runner/B1/B2 adapters and their tests other than the listed Stage A test file remain byte-identical to the reviewed B2 head. Do not change workflows or configure away CI checkout credentials.
- accepted_case_credit is exact integer0; profiles_enabled=false; enabled_tiers=[]; runtime_lock=null; run_record=null.
- All nine authority flags remain false: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized.
- Offline test subprocesses exercise only the fixed host Git executable and owned metadata; no fixture/application/Go/provider runtime, Docker, browser, network or payment execution is authorized by this plan. GitHub CI readback is evidence retrieval, not runtime admission.
- Complete raw validators, JUnit/result/process/environment/manifest bindings, dynamic-support inventory, genuine same-head180, source/bank attribution, real supervisor provenance, profiles, images/security/SDK/license/staging/live/release gates remain separate.

## File responsibilities

Planning-only paths: this plan, `docs/agents/specs/2026-11-04-workshop-final180-ci-integration.md`, `docs/agents/records/2026-11-04-workshop-final180-ci-integration.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-final180-ci-integration.json`, and an append-only successor entry in `docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md`. No implementation files may change before exact-checkpoint preflight, independent checkpoint review and explicit dispatch pass.

Future builder modifies only `scripts/dev/test_workshop_final180_runner.py` (exact Stage A patch) and `docs/verification/workshop-final180-runbook.md` (CI isolation evidence and synthetic limitations). Canonical task/record and tracking changes remain coordinator-owned. The spec includes a readable patch rendering, the exact command for the canonical4384-byte patch and all load-bearing source hashes so external evidence directories are not required to implement the repair.

## Live tracking receipt

The coordinator is the sole serialized GitHub writer. Saved receipt `/home/corp/autodata-evidence/final180-ci-integration-tracking/receipt.json` records `synchronized_live_readback`; its saved before/after hashes were verified during checkpoint preparation. Issue after SHA256 `b52fbb3d7a7a9b8ea543984133153793b3cc7abff119d69078179e46f106a750`; Project after SHA256 `5e85f52638b718d743c567d8bdb13ae8c61c64fc08cf1850ca148232415b948d`; current Project Source SHA256 `818d5bf9c5dd574c09816cd7c93db0549b37519a78437a7ff1023409cd02f5e9`; prior Project Source SHA256 `08e8c676cd8bb03f65ef29a6209da6fd0962a8b376df1b79632eaef4d7d10e14`. Project remains In Progress. The standalone record and identical nested task record retain full receipts, references and source hashes. No checkpoint review, implementation dispatch or runtime authority follows from this receipt.

## CI evidence and diagnosis

Historical pre-sync draft verification executed the contaminated-checkout regression against unchanged B2 source and confirmed exactly ten ProductionGitTests setup `git_config` errors (exit1). No implementation patch was applied. JSON/nested-record equality, all nine false authority values, source/hash/merge-base pins, embedded Python syntax, exact five planning paths and append-only79030-byte assembler prefix were checked. `git diff --check` passed. At that draft-verification point no synchronized implementation preflight, commit, push or GitHub write had been performed; current tracking synchronization is recorded separately below.

Coordinator-reported B2 code-only completion tracking was subsequently synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6638436396; this successor uses its own separate live receipt6638503013 and does not reuse that predecessor receipt as its synchronization.

The workflow `.github/workflows/autonomous-verification.yml`, job `Validate autonomy policy and evidence contract`, step `Run development adapter tests`, runs `python -m unittest discover -s scripts/dev -p 'test_*.py' -v`. Its normal Actions checkout may retain credential-related Git configuration. The strict production reader correctly rejects configuration outside its passive allowlist. The inherited test erroneously opens repository `ROOT` during each ProductionGitTests.setUp, before the individual test reaches its owned fixture.

- Stage A repaired source `93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a`: [run41880058587](https://github.com/lucronn/autodata/actions/runs/41880058587) completed success for both autonomy and DTO inventory jobs, verified by read-only run readback during planning. This is predecessor CI evidence only.
- B1 exact `54a7ca32eab80654310d862f0ac6957375d16e8b`: [run41881056411](https://github.com/lucronn/autodata/actions/runs/41881056411) and [run41881112326](https://github.com/lucronn/autodata/actions/runs/41881112326) failed. The first failed log was independently read during planning: 337 tests, ten errors in ProductionGitTests.setUp line258, `ProductionGitReader(ROOT)` raising `ContractError: git_config`. Coordinator reports the same ten-error pattern in the second run and passing DTO inventory. Failure is test-environment coupling; do not relax the reader.
- B2 exact `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`: [PR run41884839700](https://github.com/lucronn/autodata/actions/runs/41884839700) and [push run41884762336](https://github.com/lucronn/autodata/actions/runs/41884762336) were `in_progress` at planning readback. Do not state these runs passed or failed. The B2 test blob is independently verified identical to the old ancestor blob, so the same fixture coupling is inherited even while CI remains pending.

Historical local B2 handoff `/home/corp/autodata-evidence/final180-stage-b2-builder/handoff.json` reports focused100 and autonomy146 passed and developer discovery pending; it is not completed successor validation. Local B1 clean-checkout success cannot substitute for the observed CI failure. New successor exact-head CI and fresh full checks are required.

## Task 1: Synchronize and review the planning checkpoint (coordinator only)

**Files:** the five planning paths above. **Consumes:** exact reviewed B2 head0ccfe79 and repair source/ancestor. **Produces:** committed, pushed, independently reviewed checkpoint with synchronized standalone/nested record and exact two-path dispatch.

- [x] Preserve Issue186 history and Project8 source history, append the concrete goal/references/todo and record both live readbacks at comment6638503013.
- [x] Standalone and nested pre_implementation.status are synchronized identically, retaining all nine false authority values, zero credit, disabled profiles, null runtime lock/run record and exact B2/source pins. Task implementation remains blocked pending the remaining gate conditions.
- [ ] Commit/push only the five planning paths as `docs: gate final180 CI fixture integration` and pin the resulting full SHA. The immutable full commit SHA must be recorded externally after commit to avoid a self-reference.
- [ ] In the clean exact-checkpoint checkout run standalone and nested machine validation; require synchronized/empty errors from both, identical nested/standalone objects and visible Issue/Project/todo in the committed plan. Run this command only in the clean committed checkpoint checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'GATECHECK'
import json
from pathlib import Path
import subprocess
from scripts.autonomy.pre_implementation import validate_record
root = Path.cwd()
base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
record_path = 'docs/agents/records/2026-11-04-workshop-final180-ci-integration.json'
task_path = 'docs/agents/tasks/2026-11-03-production-release/workshop-final180-ci-integration.json'
record = json.loads(subprocess.check_output(['git', 'show', f'{base}:{record_path}']))
task = json.loads(subprocess.check_output(['git', 'show', f'{base}:{task_path}']))
policy = json.loads(subprocess.check_output(['git', 'show', f'{base}:.autodata-autonomy-policy.json']))
assert task['pre_implementation'] == record
for name, value in [('standalone', record), ('nested', task['pre_implementation'])]:
    errors = validate_record(value, root, base, policy)
    print(json.dumps(dict(record=name, base_sha=base, status='synchronized' if not errors else 'blocked', errors=errors)))
    assert not errors
GATECHECK
```

- [ ] Obtain independent exact-checkpoint review and explicit coordinator dispatch. Supply its full SHA as AUTODATA_CI_INTEGRATION_CHECKPOINT_SHA to the builder. A missing/failed condition blocks implementation.

## Task 2: Integrate and verify the exact fixture repair (future builder)

**Files:** Modify `scripts/dev/test_workshop_final180_runner.py`, `docs/verification/workshop-final180-runbook.md` only. **Consumes:** synchronized reviewed checkpoint and pinned diff in the spec. **Produces:** owned fixture setup, unchanged production/adapters, measured offline checks and exact-head code review/CI evidence.

- [ ] Read canonical gate, this plan/spec and immutable dispatch. Confirm checkout starts at the supplied checkpoint and both preflights and independent gate review passed.
- [ ] Run the spec's contaminated-checkout regression before any edit. Expect ten ProductionGitTests.setUp git_config errors; record output externally. A different failure must be investigated before applying anything beyond this scope.
- [ ] Check/apply only this exact patch; do not cherry-pick the source branch history:

```sh
git diff --binary 2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e 93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a -- scripts/dev/test_workshop_final180_runner.py | git apply --check
git diff --binary 2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e 93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a -- scripts/dev/test_workshop_final180_runner.py | git apply
```

- [ ] Rerun the same regression, expecting ten passes. Run Stage A52/B1 25/B2 23 focused tests and confirm existing helper/config/attributes/hook/alternate/executable rejection tests still pass. Source spec contains the exact commands.
- [ ] Append the required runbook note from the spec, including actual outcomes, exact source/ancestor and synthetic limitations. Do not state pending CI is successful.
- [ ] Run complete developer/autonomy discovery, in-memory compile, git diff --check and spec's exact source patch/unchanged module/two-path allowlist verification. Record actual completed suite counts/durations and any failure; do not substitute old reports or partial progress.
- [ ] Commit the validated two-file milestone as `test: integrate final180 CI Git fixture isolation`, promptly push the coordinator-assigned feature branch, and obtain independent review at its exact code SHA. Do not amend published history merely for activity.
- [ ] Read back Autonomous Verification for that exact SHA, record both autonomy and DTO inventory job states and any failures. CI tooling success is code-only evidence. Coordinator synchronizes exact-head result, receipts and todo disposition in Issue186/Project8; pending CI stays pending. Runtime lock/run remain null, all nine authorities false.

## Canonical todo

1. Synchronize this CI-integration plan/spec/record/task and exact two-path implementation allowlist with Issue186 and Project8, preserving history; commit/push the checkpoint descending from reviewed B2 0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471 and pass exact-checkpoint standalone/nested preflight plus independent gate review before explicit builder dispatch.
2. Reproduce the ten ProductionGitTests setup failures with harmless forbidden checkout metadata, then apply only the pinned Stage A test-file patch from ancestor 2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e to source 93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a; keep every production and adapter byte unchanged.
3. Update the final180 runbook to distinguish CI fixture isolation and code-only synthetic checks from genuine raw-fixture and runtime acceptance; preserve accepted_case_credit0, disabled profiles/tiers, null runtime lock/run record and all nine authority flags false.
4. Run the contaminated-checkout regression, 52 Stage A plus 25 B1 plus 23 B2 focused tests, complete developer/autonomy discovery, no-bytecode syntax and exact patch/two-path/unchanged-source checks; commit/push validated milestones and obtain independent exact-code-head review.
5. Read back exact-successor-head Autonomous Verification results and synchronize code-only evidence with Issue186/Project8; retain any pending or failed CI and every runtime/profile/release blocker without inferring acceptance or authority.

## Synchronized coordinator tracking summary

Final180 CI-integration successor: planning synchronized at Issue186 comment6638503013 on reviewed B2 `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471` (draft PR230, coordinator-reported exact-head review PASS/no findings). Goal: Carry the exact Stage A CI Git-metadata test-fixture isolation repair into the reviewed B2 stack without changing production behavior or earning runtime acceptance credit. Repair source `93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a` versus ancestor `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e`; exact file `scripts/dev/test_workshop_final180_runner.py`, patch SHA256 `c4567a3b03db9d8bb56af43a701f56ebaf15d68149ff6cadd326c93ecfb921eb` /stable patch-id `87df9ca6f05a0bbdf9f5c98bcc549fef1be6b3fc`. B1 CI41881056411/41881112326 failed ten ProductionGitTests.setUp git_config errors; Stage A41880058587 passed; exact B2 runs41884839700/41884762336 were pending at planning readback. Canonical references: `docs/superpowers/plans/2026-11-04-workshop-final180-ci-integration.md`, `docs/agents/specs/2026-11-04-workshop-final180-ci-integration.md`, `docs/agents/records/2026-11-04-workshop-final180-ci-integration.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-final180-ci-integration.json`, append-only `docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md`. Future implementation allowlist only `scripts/dev/test_workshop_final180_runner.py` and `docs/verification/workshop-final180-runbook.md`. Concrete todo is the five numbered entries immediately above. Tracking synchronization and live receipt are recorded above. No exact-checkpoint preflight PASS, checkpoint review or dispatch is asserted by this tracking summary; coordinator records those separately after they occur. accepted_case_credit0, profiles disabled, enabled_tiers empty, runtime_lock/run_record null, every authority false; genuine raw/runtime/full180/profile/staging/live/release gates remain open.
