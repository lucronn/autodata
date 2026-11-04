# Workshop final180 Stage D paid12 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this bounded adapter task-by-task only after synchronized tracking, committed exact-checkpoint preflight, independent gate review and explicit coordinator dispatch. Steps use checkbox syntax.

**Goal:** Add a bytes-only restricted synthetic paid12 Go-event adapter with twelve literal caller-selected slots, zero accepted-case credit and all authority false.

**Architecture:** Supply twelve in-memory byte/receipt slots to a side-effect-free standard-library translator. Delegate only the restricted grammar to B1's pinned public parser/types; implement paid-root lifecycle and independently revalidate strict synthetic serialization locally.

**Tech Stack:** Python standard library dataclasses/hashlib/json/re and unittest; four pinned B1 public symbols only.

**Spec:** `docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md` (normative self-contained public interfaces, twelve literal IDs/refs, source pins, complete admission/lifecycle/status/serializer rules and adversarial test matrix).

**Status:** Issue186/Project8 planning `synchronized` at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727. Independent five-file pre-sync review PASS/no findings is coordinator-reported. Exact committed-checkpoint preflight, independent checkpoint review and explicit coordinator dispatch remain required; implementation remains blocked until those conditions pass.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8

**Exact planning parent:** `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc`, reviewed CI integration PR https://github.com/lucronn/autodata/pull/232. Independent code review PASS is coordinator-reported. Exact-head CI remained pending at coordinator readback; no CI success is asserted. **Application candidate:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. Parallel Stage C commerce planning grants no Stage D authority.

## Global Constraints

- Future implementation allowlist is exactly `scripts/dev/workshop_final180_paid_adapter.py`, `scripts/dev/test_workshop_final180_paid_adapter.py`, `docs/verification/workshop-final180-runbook.md`.
- Preserve Stage A/B1/B2/CI/inventory bytes at spec section13 pins; no B2/commerce/application/producer import, parser extraction or refactor.
- No filesystem/artifact I/O, CLI, subprocess, environment, clock, callbacks, fake scheduler, network, DB, S3, provider/payment client or actual fixture execution.
- Bank attribution is caller-selected; identical bytes across bank slots are admitted. Go events do not authenticate candidate/source-manifest/process/receipt/payment semantics.
- Source Go grants seed paid rows directly; `payment_grants_persist` asserts `payment_calls == 0`. No real Stripe settlement, charge or TEST/LIVE transaction acceptance follows.
- `accepted_case_credit=0`, `profiles_enabled=false`, `enabled_tiers=[]`, `runtime_lock=null`, `run_record=null`; all nine authority values remain false.
- B1 first-raised parser control flow governs conflicts: CR/empty delimiter check precedes per-line size even though vocabulary lists line_size first.
- Full raw/JUnit/result/SQL/HTTP/media/nested semantics, genuine compatibility/bank/payment/runtime, trusted profiles, complete final180 and staging/release acceptance remain separately blocked.

## File responsibilities

Planning author changes exactly this plan, `docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md`, `docs/agents/records/2026-11-04-workshop-final180-stage-d-paid.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-d-paid.json` and an append-only successor in `docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md`. Coordinator alone synchronizes tracking. Current standalone/nested records are equal and synchronized; task implementation remains blocked pending exact-checkpoint preflight, review and explicit dispatch.

Future builder creates the library for frozen context/case/outcome/diagnostic types, literal constants, parser wrapper, translation and serializer; creates the tests with independent literal expectations and fake bytes/receipts; appends the accurate runbook note. No other path is permitted. Shared runbook is coordinator-reconciled with parallel Stage C before a new exact checkpoint/dispatch; do not rebase onto unreviewed code or alter its contract silently.

## Task 1: Coordinator planning/tracking checkpoint

**Consumes:** this five-path draft and reviewed parent `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc`. **Produces:** synchronized, committed, pushed and independently reviewed exact checkpoint, with explicit three-path dispatch.

- [x] Independent five-file pre-sync review PASS/no findings is coordinator-reported; exact source pins remain intact.
- [x] Sole coordinator preserved Issue186 body/comment history and prior Project8 Source, synchronized goal/references/todo/allowlist, and retained live readbacks at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727; unrelated fields remain intact.
- [x] Standalone/nested records are identically synchronized after verified live tracking readback, retaining zero credit/false authority; no authorizing SHA is invented before commit.
- [ ] Commit/push the five-path checkpoint descending from reviewed parent; retain full resulting SHA externally to avoid self-reference. Run the exact clean-checkpoint command below only then.
- [ ] Obtain independent exact-checkpoint review and explicit coordinator dispatch with full SHA and assigned branch. A missing condition blocks implementation. Parent CI pending/failure must remain accurately recorded and coordinator must resolve its dispatch significance explicitly.

```sh
# Run only after the synchronized five-path checkpoint is committed and checkout is clean.
PYTHONDONTWRITEBYTECODE=1 python3 - <<'GATECHECK'
import json
from pathlib import Path
import subprocess
from scripts.autonomy.pre_implementation import validate_record
root = Path.cwd()
base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
record = json.loads(subprocess.check_output(['git', 'show', f'{base}:docs/agents/records/2026-11-04-workshop-final180-stage-d-paid.json']))
task = json.loads(subprocess.check_output(['git', 'show', f'{base}:docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-d-paid.json']))
policy = json.loads(subprocess.check_output(['git', 'show', f'{base}:.autodata-autonomy-policy.json']))
assert task['pre_implementation'] == record
for name, value in [('standalone', record), ('nested', task['pre_implementation'])]:
    errors = validate_record(value, root, base, policy)
    print(json.dumps(dict(record=name, base_sha=base, status='synchronized' if not errors else 'blocked', errors=errors)))
    assert not errors
GATECHECK
```

## Task 2: Parser wrapper and twelve-slot lifecycle translator (future builder)

**Files:** Create `scripts/dev/workshop_final180_paid_adapter.py` and `scripts/dev/test_workshop_final180_paid_adapter.py`. **Consumes:** exact `PaidContext`, `PaidCase`, B1 `GoEvent`, `AdapterError`, `SimulatedExit` and literal SLOTS in spec sections2–6. **Produces:** `parse_paid_events(raw: bytes) -> tuple[GoEvent, ...]` and `translate_paid(cases: tuple[PaidCase, ...], context: PaidContext) -> PaidDiagnostic`.

- [ ] After dispatch, read gate/plan/spec, verify exact authorizing SHA and clean checkout, and verify all preservation pins. Import only the allowed public B1 symbols and four standard-library modules.
- [ ] Write failing tests with independent literal IDs/refs for twelve slots, strict outer admission/precedence and clean event construction below. Run focused paid unittest; expected first failure is missing paid module, not environment/runtime setup.

```python
# Test helper constructs bytes only; root comes from independent literal test rows.
def stream(root):
    package = 'github.com/lucronn/autodata/apps/api-go'
    rows = []
    for action, test in [('start', None), ('run', root), ('pass', root), ('pass', None)]:
        row = dict(Time='2026-11-04T00:00:00Z', Action=action, Package=package)
        if test is not None:
            row['Test'] = test
        rows.append(json.dumps(row, separators=(',', ':')).encode('ascii'))
    return b'\n'.join(rows) + b'\n'
# Every literal PaidCase uses stream(root), b'', SimulatedExit(0, False, False, False, True).
# Assert twelve ordered passed rows, top consistent, exact SHA256 and raw refs, credit0.
```

- [ ] Define exact frozen types/constants and delegate wrapper with `return parse_identity_events(raw)`; implement complete six-stage outer admission before any parse/hash, then independent canonical-order row translation. Spec sections4–7 determine every stable error/order/status; no input coercion or partial success prefix.
- [ ] Add the full spec section10 adversarial matrix. In particular, independently damage each of12 roots; accept identical bank-slot bytes; verify parser failure plus receipt flags, skip plus poison and interruption top precedence.

```python
# Direct wrapper conflict regression; also replace one otherwise valid slot's bytes.
with self.assertRaisesRegex(AdapterError, '^line_delimiter$'):
    parse_paid_events(b' ' * 1048576 + b'\r')
with self.assertRaisesRegex(AdapterError, '^line_size$'):
    parse_paid_events(b' ' * 1048577)
# Damaged slot: failures == ('line_delimiter',), status unavailable;
# other11 passed, top unavailable; add interrupted receipt => top interrupted.
```

- [ ] Run paid plus existing Stage A/B1/B2 focused tests. Review exact diff; commit a coherent passing translation milestone and promptly push assigned branch. A test failure permits fixes only in the three-path scope.

## Task 3: Strict serializer, adversarial boundary and runbook (future builder)

**Files:** Same two new modules and `docs/verification/workshop-final180-runbook.md` only. **Consumes:** `PaidDiagnostic`/`PaidOutcome` exact types/fields from spec section2 and section8 admission. **Produces:** `serialize_paid_diagnostic(value: PaidDiagnostic) -> bytes`, canonical bounded synthetic JSON and runbook limitations.

- [ ] Write failing serializer mutation tests for every field and all nine authority flags; use `dataclasses.replace` and require `AdapterError('diagnostic_invalid')` for wrong primitives/subclasses, bool credit, reordered/missing/extra rows/refs/codes, parser+semantic mixing, wrong recomputed row/top status, nonempty tiers or any authority mutation. Assert exact top/row key sets and no untrusted Output/stderr text leaks.
- [ ] Implement all nine serializer validation stages in spec section8, then only `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)` plus one LF and <=65536-byte bound. Serializer validates claims; it cannot authenticate raw bytes or receipts.
- [ ] Add static AST/import/call checks for exact imports, no CLI/entrypoint/I/O/runtime/eval/exec/dynamic import/callbacks. Compile changed sources in memory without bytecode. Assert frozen dataclass field order and exact shared B1 types.
- [ ] Append a coordinator-reconciled runbook note with exact paid checkpoint/code SHA, twelve slots, constructed-only source profile, first-raised regression, caller bank ambiguity, direct seeded grants/payment_calls0, zero credit/all false authority and separate real raw/payment/runtime/final180 blockers. Report actual checks; preserve pending CI accurately.
- [ ] Run all commands below and record actual counts/results externally; inspect unchanged source pins and exact three-path diff against supplied authorizing checkpoint. Commit/push validated serializer/test/runbook milestone and obtain independent exact-code-head review; coordinator reads back that exact SHA's CI and synchronizes code-only evidence. No merge or runtime authority follows.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_paid_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py scripts/dev/test_workshop_final180_identity_adapter.py scripts/dev/test_workshop_final180_catalog_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
git diff --check
```

Keep runtime integration opt-in flags absent; a dependency/environment issue does not authorize application, Docker or provider execution. Use `compile(Path(path).read_text(), path, 'exec')` for both new modules, exact AST/import checks, and read-only Git hashes for every spec section13 preservation pin. The future runbook is the sole permitted difference among those pins. Reject any diff path outside the three-path allowlist, including untracked files; compare all changed paths from checkpoint, not only unstaged diff.

## Canonical todo

1. Synchronize the Stage D paid plan/spec/record/task and exact three-path implementation allowlist with Issue186 and Project8, preserving history; commit/push the checkpoint descending from reviewed CI integration fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc and pass exact-checkpoint standalone/nested preflight plus independent gate review before explicit coordinator dispatch.
2. Implement bounded bytes-only twelve-slot paid translation using only the pinned B1 public parser/types; preserve first-raised parser precedence, full outer admission, per-slot lifecycle, receipt/status order, literal refs and caller-selected bank limitations.
3. Add failing-first constructed fake-byte tests and strict serializer mutation checks for every literal slot, grammar/bounds/conflicts, lifecycle, receipts, hashes, code ordering, zero credit and all nine false authority flags; preserve Stage A/B1/B2/CI bytes.
4. Append the coordinator-reconciled synthetic-only runbook note; run focused paid and Stage A/B1/B2, developer/autonomy, syntax/AST, exact allowlist and unchanged-source checks; commit/push validated milestones and obtain independent exact-code-head review.
5. Synchronize code-only verification and exact-head CI readback with Issue186/Project8 while retaining pending/failing states, disabled profiles/tiers, null runtime lock/run record and all false authority; keep complete raw paid semantics, real payment/runtime and final180 acceptance separately blocked.

## Synchronized coordinator tracking text

Add a bytes-only restricted synthetic paid12 Go-event adapter with twelve literal caller-selected slots, zero accepted-case credit and all authority false. Planning parent `fa0c1bca6c61340c743e2b575bc54fc23a0d2fdc` (PR232); application candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`; parent exact-head CI pending at readback. Canonical plan `docs/superpowers/plans/2026-11-04-workshop-final180-stage-d-paid.md`, spec `docs/agents/specs/2026-11-04-workshop-final180-stage-d-paid.md`, record `docs/agents/records/2026-11-04-workshop-final180-stage-d-paid.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-final180-stage-d-paid.json`, append-only assembler index `docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md`. Future allowlist exactly `scripts/dev/workshop_final180_paid_adapter.py`, `scripts/dev/test_workshop_final180_paid_adapter.py`, `docs/verification/workshop-final180-runbook.md`. External DRAFT/SPEC restricted-scope reviews and independent five-file pre-sync review PASS/no findings are coordinator-reported; live Issue186/Project8 synchronization is recorded at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727. Concrete todo is the five entries above. Tracking synchronization alone does not assert exact-checkpoint preflight, committed-checkpoint review or dispatch; full checkpoint SHA and post-commit checks are sealed externally after commit. Credit0, profiles/tiers disabled, runtime lock/run null and all nine authority false. Direct fixture paid grants and payment_calls0 prove no real Stripe settlement or charge acceptance. Full raw/runtime/final180/release blockers remain.

## Live tracking receipt

Coordinator synchronization is recorded at https://github.com/lucronn/autodata/issues/186#issuecomment-6639038727; saved receipt `/home/corp/autodata-evidence/final180-paid-gate-tracking/receipt.json` SHA256 `fcc31f428c6f49f41d4a523d2c62b071ff74c7515a25c5cf4751943913298761` has status `synchronized_live_readback`. Issue before/after SHA256 are `46a8b5e3fda4f6efc54ce390e3ab93b1ec16ad662cc289b62f67a078fdeeeb35` / `17cd1425c2300b4c68b321ef99a06291a0a3e68dea85d237620a32c0d5bd73fd`; Project before/after SHA256 are `8900b3a8fd1ca381c66e4c22763e313ece3ba15e745a0380cb76ad0cd6c3cf18` / `87454561a76fae5f08b45b3ce94af847a4963d11fcb37872275e2e479700f5fd`. All 166 prior comments are preserved (167 total), Issue body and unrelated Project fields are unchanged, and previous Source is archived verbatim. Previous/current Project Source SHA256 are `52904c974a884f2e8c3da217e954118cb02aac28c4914df44c54b05604c8a3f3` / `bd9b9e55ec29d898de6e8fb2c56b3834abf44ab4b08658dbcee18e28b603fcc7`; Project remains In Progress. Standalone and nested records retain the full receipt. Independent five-file pre-sync review PASS/no findings is coordinator-reported. This receipt does not assert checkpoint preflight, committed-checkpoint review or implementation dispatch.

## Historical code-only completion — repaired paid12 head, CI pending

This additive historical update records the implementation and review outcome at
`2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7` on
`codex/workshop-final180-stage-d-paid-build`, draft
[PR236](https://github.com/lucronn/autodata/pull/236), authorized by checkpoint
`70c9a6ebb2cec338f938122c8c570fd5b22a6f28` and coordinator
[dispatch](https://github.com/lucronn/autodata/issues/186#issuecomment-6639114586).
The original planning text, unchecked historical task list, synchronized record,
task and normative spec remain historical checkpoint evidence. The separate
`docs/agents/records/2026-11-04-workshop-final180-stage-d-paid-completion.json`
records this successor outcome; it is not a new synchronized implementation gate.

The original independent exact-head review at
`f476ba63068c7fc6a5be2d994874f4907b6daea5` returned **FINDINGS/P2**:
caller-constructible incomplete exact-type dataclasses leaked `AttributeError`
instead of stable `AdapterError` codes. Its report is preserved at
`/home/corp/autodata-evidence/final180-paid-exact-head-review/REVIEW.md`, SHA256
`bb582445c4efbf6c96d042f4a1c975a571a2bf52b02bc2213b9897affb61af42`.
Six regression methods produced 37 AttributeErrors before the repair. The repair
milestone `894f49b85dbabdf8f07c82074bc960f13d6910c1` adds required-field admission
before dereference, preserving the specified error-stage precedence. The final
head adds only the runbook after that repaired code milestone.

The independent final exact-head review is **PASS/no remaining findings** at
`2774cdfe44e7c99a0cae5606ad1ea5f20863c0d7`; original five malformed-instance
probes and all omitted-field regressions pass. Review receipt
`/home/corp/autodata-evidence/final180-paid-final-repaired-review/receipt.json`
has full SHA256
`29091141c2a5968c61de46f83d752e163b7549e486aa2fb4e1135af6250727b8`;
report SHA256 is
`e8e158a340b2f0abdc3432bab611affaf5aa50615a92404018100e8964181d8d`.
This supersedes the P2 only for the final reviewed successor head and preserves
the original finding as history.

Builder evidence is sealed in
`/home/corp/autodata-evidence/final180-paid-build/receipt.json`, SHA256
`26e3a861b000e496d55482398a3203def9705b0de79d8982ca033b26b350be69`,
and `checks.json`, SHA256
`53509f17198ff9f02645eff97e7d43d6d108f632faae5b8d61ffe13078257a1d`.
The repaired results were paid **38/4.065s**, focused **138/21.373s**, developer
**398/521.229s**, and autonomy **146/49.044s**, all OK. The independent reviewer
reran **138 focused tests/21.645s**, OK, and inspected and hashed the builder's broad
suite evidence without independently rerunning those broad suites. This docs
worker verifies the sealed receipts/log summaries rather than rerunning tests.

Fresh docs verification confirms all receipt-indexed hashes, three final code
file hashes, all **40 Git-object source-pin records**, eight unchanged
code/test/workflow/inventory preservation pins, append-only runbook baseline,
exact three-path implementation scope, and original standalone/nested
`validate_record` results `status:synchronized`, `errors:[]` at the authorizing
checkpoint. The original record/task/spec bytes are unchanged. Evidence is
retained at `/home/corp/autodata-evidence/final180-paid-completion-docs/`.

Exact-head [CI run41894466041](https://github.com/lucronn/autodata/actions/runs/41894466041)
was **in progress at coordinator readback**; no successful CI conclusion is
asserted. Coordinator-only Issue186/Project8 completion synchronization remains
pending and is not performed by this docs worker.

Credit remains exact int0; profiles/tiers stay disabled, runtime lock/run record
null, and all nine authority values false. The adapter accepts constructed
bytes/receipts only. Bank labels remain caller-selected. Direct seeded grants
and `payment_calls == 0` prove no real Stripe charge or settlement. Full raw paid
344-reference/nested/JUnit/process/manifest semantics, real bank/payment/runtime,
actual Go compatibility, complete final180 and staging/release acceptance remain
separately blocked. This code review grants no merge, runtime, profile promotion,
deployment, cutover or accepted-case credit.
