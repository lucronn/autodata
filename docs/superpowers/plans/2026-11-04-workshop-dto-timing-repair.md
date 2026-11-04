# DTO timing successor gate draft

Status: **synchronized** planning and literal successor tracking. Exact committed-J preflight and independent checkpoint review pending; no implementation dispatched.

Goal: Repair DTO browser fixture lifetime and finite lifecycle scheduling without acceptance or release authority
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source C: 8e661fdc38ce944d97a01d087b997439f36d4f91
Published DTO history: a7a079e64f3b266e34ef58c2deb91e46cdaaf607

Corrected-source prerequisite verified from independently reviewed retained receipts: push41922039185 and PR41922084582 completed success, all3 jobs each and required steps successful. Actual PR checkout45bbf481012345e5c5d1ef0f5ab121a93c58b814 has the same tree as C. Independent verdict: /home/corp/autodata-evidence/r6-workflow-hash-ci-independent-review/verdict.json; source-C tracking: https://github.com/lucronn/autodata/issues/186#issuecomment-6643689750. This proves corrected-C CI only, not successor J/DTO repair or runtime acceptance. New literal successor tracking is synchronized below; actual J/preflight receipts will be sealed externally after commit. All authorities false, accepted-case credit0.

## Literal todo

1. Admit exact R6 corrected candidate 8e661fdc38ce944d97a01d087b997439f36d4f91 only after both its normal push and PR Actions succeed at the exact source and actual merge fixture; preserve e3 failure and published DTO checkpoint a7a079e64f3b266e34ef58c2deb91e46cdaaf607 as history.
2. Freeze corrected source 8e661fdc38ce944d97a01d087b997439f36d4f91, its tree, eight source blob/mode/hash pins,45-task queue, all120 ordered DTO IDs, ten deterministic failure schedules and conditional4430<4440 proof; independently review the six-document successor and explicit seven-path implementation scope.
3. Synchronize this literal goal, todo list, six canonical checkpoint paths and seven implementation paths in Issue186/Project8 with live readback; preserve all45 corrected-source queue objects/root fields and both tracking histories, append only workshop-dto-timing-repair as the46th distinct stable task.
4. Commit and push only the reviewed six-document successor checkpoint J on codex/workshop-dto-timing-repair-successor-gate, descending from both corrected candidate 8e661fdc38ce944d97a01d087b997439f36d4f91 and published DTO checkpoint a7a079e64f3b266e34ef58c2deb91e46cdaaf607; seal actual J externally, require standalone and nested exact-J preflight errors=[] and independent checkpoint review before explicit seven-path code-only dispatch.
5. Implement the reviewed strict shared timing contract and DTO lifecycle/parent-worker/stage-only I/O design within seven paths; preserve API4400, all120 IDs, original diagnostics, ten deterministic failure schedules, terminal attempt/epoch fencing and conditional4430<4440 schedule while keeping independent watchdog, containment and trace gates separate.
6. Modify only the existing DTO workflow job, preserving all triggers/R3 filters/R3 job and every non-DTO byte; in the same coherent candidate rebind only product_evidence.ci_profile.workflow_sha256 in the disabled R6 task to the SHA256 of those exact reviewed new workflow bytes, preserving every other R6 byte and false profile semantics.
7. Run approved offline checks including the seven former R6 failures and broad release-acceptance/dev/autonomy coverage, independently review exact code/hash bindings, observe honest new source and actual merge-fixture Actions, then synchronize measured code-only evidence with all authorities false and credit0.

## Gate and integration contract

Six canonical checkpoint paths:

- docs/superpowers/plans/2026-11-04-workshop-dto-timing-repair.md
- docs/agents/specs/2026-11-04-workshop-dto-timing-repair.md
- docs/agents/records/2026-11-04-workshop-dto-timing-repair.json
- docs/agents/tasks/2026-11-03-production-release/workshop-dto-timing-repair.json
- docs/verification/2026-11-04-workshop-dto-timing-repair.md
- docs/agents/tasks/2026-11-03-production-release/queue.json

Exactly seven later implementation paths:

- scripts/dev/workshop_browser_smoke.py
- scripts/dev/test_workshop_browser_smoke.py
- apps/api-go/workshop_browser_fixture_test.go
- apps/api-go/workshop_browser_fixture_deadline_test.go
- scripts/dev/fixtures/workshop_customer/timing.json
- .github/workflows/autonomous-verification.yml
- docs/agents/tasks/2026-11-03-production-release/r6-release.json

The eighth immutable source pin is verification-only source input, not an eighth implementation path. Existing source files and both prior records/queue entries are archived byte-for-byte externally. Active C queue45 objects/root fields are preserved verbatim; only the distinct refreshed DTO entry is appended for46. Its complete previous queue entry is retained under historical_provenance.

Create a future checkpoint J descending from both C and a7a079 using an owned branch and a semantic queue merge; preserve published history without rebase/force push. The only diff from C is these six canonical documents. Do not copy either45-task queue wholesale or use ours/theirs. Unexpected source/root/original-object changes stop adoption.

Both C Actions gates have passed at the exact reviewed source/fixture. Obtain independent successor differential review, then the coordinator alone serializes new literal Issue186/Project8 updates and live readback preserving old history. Only after authentic readback set the new records synchronized. Embed the identical standalone record in task.pre_implementation. Commit/push J, seal its actual full SHA externally (self-SHA fields remain null), load policy/standalone/nested records at J and require both canonical preflight errors=[]; obtain independent exact-J review and explicit seven-path code-only dispatch. Old readback/review receipts remain history and cannot authorize this expansion.

The seventh path allows only the R6 workflow_sha256 field, and only if DTO workflow bytes change. In the same coherent candidate bind it to SHA256 of exact reviewed new workflow bytes. Preserve every other R6 byte, all disabled profiles, enabled_tiers[], assembler_sha256:null, all triggers/R3 filters/R3 job and non-DTO workflow bytes. Future workflow hash is null until real exact bytes exist. No trust-loader change, arbitrary hash acceptance, enabling or profile promotion is permitted.

The later candidate needs fresh exact-source/actual-merge-fixture normal Actions; source/target workflow drift requires a new exact binding review. Preserve120 IDs/order/digest, ten failure schedules, diagnostics, API4400, conditional4430<4440 model and separate real-watchdog/containment/trace16MiB-vs8MiB blockers.

## Retained technical implementation plan

## Task1 — Timing contract and pure deadline decisions

**Files:** new timing.json; smoke.py; test_workshop_browser_smoke.py; fixture_test.go; new fixture_deadline_test.go.

**Interfaces:** Python `load_dto_timing(path: Path) -> dict`, `validate_dto_schedule(timing: dict, case_count: int) -> dict`, `remaining(deadline: float, now: float) -> float`. Go `loadWorkshopBrowserTiming(path string) (workshopBrowserTiming, error)` and `workshopBrowserFixtureLifetime(paid bool, timing workshopBrowserTiming) time.Duration`. Do not create listeners/timers in these pure helpers.

- [ ] Add failing tests with these exact arithmetic assertions and invalid-input rejection:

```python
def test_complete_inventory_budget():
    values = smoke.validate_dto_schedule(TIMING, 120)
    assert values['serial_seconds'] == 2994
    assert values['parent_total_seconds'] == 4430
    assert values['fixture_requirement_seconds'] == 4640
    assert values['go_requirement_seconds'] == 4980
    assert smoke.remaining(12.0, 12.0) == 0
```

`TIMING` is a fixture loaded from the proposed timing.json values in budget-proof.json, not a weakened test-only budget. Parametrize unknown key, duplicate JSON key, missing key, bool-as-number, NaN/infinity, nonpositive number, wrong version, fewer/more than120 full IDs, and each violated strict inequality. Assert rejection before any fake process factory is called.

- [ ] Add pure Go tests selecting4800s for DTO and4400s for API, invalid contract rejection and byte hash metadata. Test with injected channel/clock events that deadline expiry and stopped events are terminal without a listener.
- [ ] Implement strict config parsing and the helpers; fixture selects DTO4800 only when paid==nil, starts timer before readiness publication, and emits lifetime_seconds + timing_contract_sha256. Timing contract becomes an evidence input pin. Preserve API ready schema/behavior apart from optional non-authoritative metadata.
- [ ] Run focused Python tests and Go `-run '^(TestWorkshopBrowserTiming|TestWorkshopBrowserFixtureDeadline)'`; verify expected red before implementation and green after. No `TestWorkshopBrowserFixtureHTTP` execution. Commit/push the validated milestone only after gate authorization.

## Task2 — Explicit bounded DTO lifecycle and complete failure rows

**Files:** smoke.py and its existing test file.

**Interfaces:** `run_dto_inventory(args, *, clock, lifecycle, persist, timing) -> dict` runs only DTO; `complete_dto_failure(expected, observations, *, stage, kind, cleanup) -> list[dict]` preserves IDs and observations; the existing API run branch remains distinct. `lifecycle` exposes async start/launch/close/stop and registers task ownership. `persist` is injected and its acknowledgement is required for success.

- [ ] Add fake-time tests for normal120-case worst cost2994, exact deadline equality, phase exhaustion before launch, engine3 launch at its budget edge, startup/launch/stop cancellation resistance, late context/late browser result, lost cleanup acknowledgement, failed or hung persistence, external cancellation during every phase, secondary cancellation and backward clock. A fake scheduler advances due callbacks when `advance_to` is called; never wait seconds or invoke real Playwright.
- [ ] Test every global fault yields120 terminal failed IDs, preserves previous case failures and successful observations only under observed_case_result, never retries, and blocks validate_results.

```python
def test_global_stop_failure_never_promotes_observed_pass():
    ids = [(engine, name) for engine in smoke.ENGINES for name in smoke.inventory()]
    observed = [{'browser': ids[0][0], 'scenario': ids[0][1], 'status': 'passed'}]
    rows = smoke.complete_dto_failure(ids, observed, stage='playwright.stop',
                                     kind='deadline', cleanup='unverified')
    assert [(x['browser'], x['scenario']) for x in rows] == ids
    assert all(x['status'] == 'failed' for x in rows)
    assert rows[0]['observed_case_result']['status'] == 'passed'
```

- [ ] Replace DTO implicit async-with with capped explicit start/launch/close/stop, native launch timeout15000 plus independent15s deadline; keep20s case and3s shared cleanup, one3s browser close,10s Playwright stop. Register late cleanup work and preserve first failure. Do not use wait_for to await cancellation acknowledgement past a deadline.
- [ ] Retain all existing BrowserDTOTimeoutDiagnostics and response-loss tests; add stage/cancellation assertions rather than rewriting their success criteria. Run the full existing Python unit test module under fake Playwright; commit/push after focused checks.

## Task3 — DTO-only hard watchdog and atomic terminal receipt

**Files:** smoke.py and its existing test file.

**Interfaces:** `supervise_dto(args, *, clock, process_factory, writer_factory, timing) -> int`; process adapter exposes bounded create/poll/signal_owned_group/reap, writer adapter exposes bounded staging and raw failure only; a separate parent-owned publisher exposes fenced commit. Production adapters call only their directly created process handles; no arbitrary PID or shell. Worker internal entry requires owned control descriptor. Existing public CLI arguments remain unchanged. Begin the one4440s deadline at the first main action before DTO configuration/inventory/initial output I/O. All helpers stage/read/parse under capped nonblocking adapters; only the parent owns terminal publication. Exact state/receipt/consumption protocol is frozen in docs/agents/specs/2026-11-04-workshop-dto-timing-repair.md and the retained revision2 vectors.

- [ ] First write fake process transition tests: worker success and clean reap; stuck Playwright start/stop; cancellation-resistant event-loop drain; hard deadline at4380; TERM expiry2; KILL expiry2; reap expiry2; create fails/returns late; worker PID mismatch; unexpected exit; parent signal at each phase; malformed/stale/partial progress; writer timeout; signal/reap failure. Add F1 cases: timeout/cancel immediately before commit, late staging rename/ACK after revocation, wrong/old attempt/epoch/nonce, lost commit ACK and receipt without same-attempt exit0. Helpers must never receive canonical publication targets. Add F2 cases: blocked initialization read/parse/write/allocation, expired initialization ACK, blocked progress read/parse while worker deadline fires, and late I/O completion. No worker starts unless current init ACK is valid before its10s deadline. A frozen parent syscall tests the explicit independent-watchdog blocker, not an unconditional lifetime assertion. Assert exact ordered actions and no admission of an unowned PID.
- [ ] Implement the DTO parent/worker boundary and stage-only I/O helpers with one absolute parent deadline4440 and maximum4430 modeled seconds: init10 +worker4380 +worker cleanup6 +I/O helper cleanup12 +final read/parse/stage10 +parent commit2 +reserve10. Cumulative progress read/parse10 overlaps the worker interval; no progress syscall or parse runs in the watchdog loop. Set worker deadline=min(worker_start+4380, producer_deadline-50). Initialization failure revokes before any worker start; absent/unacknowledged inventory or output is not fabricated as complete initial evidence.
- [ ] Implement terminal states INITIALIZING/ACTIVE/PREPARED/COMMITTED/REVOKED, fresh exclusive128-bit attempt identity, monotonic epoch and exact staging ACK tuple. Revoke+increment epoch before signaling on any timeout/cancellation/uncertainty; never allow success actions after REVOKED. Parent-only critical-section commit requires unexpired current fence, all120 passing IDs and all worker/helper ACK+reap acknowledgements. Helpers stage private bytes only and cannot invoke canonical rename.
- [ ] Parent publishes commit.json last, binding attempt/epoch/candidate/timing/evidence digest/cleanup; success requires matching same-attempt invocation exit0. Missing, stale, bare evidence, partial receipt, ambiguous commit or nonzero invocation is nonpass. The responsive parent publication critical section has2s explicit conditional budget; if that I/O assumption fails, mark commit_uncertain/nonzero and keep independent-watchdog admission closed. Do not claim a signal send revokes future helper writes; helpers never had publication rights.
- [ ] Enforce writer/reader cleanup TERM2/KILL2/reap2, no more than two post-fault cleanup episodes total12s. One global fault stops new work; permit at most one subsequent nonpass staging helper, then no further helper creation. Retain last acknowledged nonpass snapshot and original diagnostics; if no durable snapshot exists, say so.
- [ ] Test parent never calls asyncio.run or unbounded wait/join, reads files, parses JSON or blocks on control pipes in its supervision loop; worker direct entry is rejected without descriptor; argv/env logs omit secrets; output paths cannot escape fresh owned attempt; file0700/0600 and atomic replacement are retained. Do not claim session signaling establishes real descendant containment.
- [ ] Run the entire test module and static no-browser/process-factory assertions; commit/push after verification. Real processes, filesystem-block probes and browser runs are explicitly deferred.

## Task4 — Workflow binding and independent offline verification

**Files:** existing DTO workflow job and the R6 task workflow_sha256 field only, plus in-scope tests. Canonical evidence uses only the six checkpoint documents.

- [ ] Test workflow binds shared config, DTO fixture metadata validation, readiness120, Go5040s, exercise5100s, job100m and artifact if:always. Assert other workflow jobs/triggers and API path unchanged. Tests parse the workflow or inspect its concrete command text and compare config values; do not execute commands.
- [ ] Implement those exact bindings and, in the same coherent candidate if workflow bytes changed, update only the disabled R6 workflow_sha256 field to the exact new reviewed workflow SHA256. Use bounded TERM/KILL/reap for the directly owned fixture session; remove existing unbounded shell wait. Cleanup failure exits nonzero without replacing original producer error. No additional network/provider/install behavior.
- [ ] Offline verification: existing Python module, pure Go timing/deadline tests, JSON schema/arithmetic checks, workflow consistency tests, `git diff --check`, exact diff allowlist and immutable120 ID comparison against the pinned source manifest. Any changed scenario ID, loss of failed evidence or true authority flag blocks completion.
- [ ] Independent reviewer inspects exact final source SHA, budgets, async cancellation/worker boundary, cleanup uncertainty, all-fail evidence and scope. Record measured results and update canonical Issue/Project/docs at that same SHA; commit/push validated review milestones.

## Completion and handoff

Original revision2, integrated-base differential and historical six-path external draft independently passed review; the external revision2 seven-path successor independently passed210 checks; actual committed-checkpoint review remains pending. The4430 bound is conditional DTO-main scheduling, not unconditional interpreter/process lifetime. Code completion is PASS_CODE_ONLY after required offline checks and review. It grants neither live runtime admission nor actual fixture credit. New source bytes require new candidate identity, refreshed immutable input pins, separate integrated-candidate review and later fresh same-candidate acceptance. Transport16MiB/8MiB, admitted concrete adapters, authentic banks/staging and release integration remain independent gates.

## Revision2 acceptance tests required before code review

F1 test fixture `FakeStageWriter` can hold before its private rename and return a late ACK after parent timeout. Assert the parent's epoch advanced, terminal state REVOKED, no canonical publish action, and `accept_success(evidence, receipt, invocation_exit=1)` is false even with old success bytes. Repeat with cancel just before commit, duplicate ACK, old attempt reuse and commit syscall completion after its2s budget. Helpers cannot emit a publish operation in the fake action vocabulary.

F2 fake helpers independently hold initialization read/write/parse/allocation and progress read/parse. Clock starts at first main action. Initialization expiry produces nonpass with zero worker starts; late init ACK cannot restart it. A progress helper held across worker deadline does not delay TERM/KILL/reap. Include both helper cleanup episodes in4430. No claimed initial120-row evidence is asserted without actual inventory+persistence ACK. Simulated parent syscall stalls retain an explicit responsive-I/O precondition failure and independent watchdog blocker; they are not counted as proved finite runtime.





## External draft revision2 source-C CI update

Source-C-CI-evidence.json binds both actual successful runs, source/checkout SHA, independent verdict and tracking https://github.com/lucronn/autodata/issues/186#issuecomment-6643689750. The earlier pending draft is retained at /home/corp/autodata-evidence/dto-timing-successor-gate-draft-revision1-snapshot. Successor tracking/readback is synchronized as recorded below; actual J/preflight receipts will be sealed externally after commit, while independent exact-J review and explicit code-only dispatch remain pending. Historical e3 failure remains historical. No new successor or DTO code CI result, fixture credit, runtime/provider/staging/release authority follows.

## Measured successor planning adoption

Literal successor Issue186/Project8 tracking: https://github.com/lucronn/autodata/issues/186#issuecomment-6643762797; actual readback timestamp 2026-11-04T22:28:43Z. Tracking receipt SHA256 7e553bfd83bd2f63b516cc0694df46efa2ce8866c94a0cf58b056d68557cc5a1. Issue body and prior comments, prior Project Source and all other Project fields were preserved. External revision2 successor review PASS:210 checks, no findings; verdict SHA256 f003f5910949bbabde31931b47e299f5dd3ce87855d8bc2265cebc49d4539f24. The branch codex/workshop-dto-timing-repair-successor-gate combines exact corrected C8e661fdc38ce944d97a01d087b997439f36d4f91 and published DTO history Da7a079e64f3b266e34ef58c2deb91e46cdaaf607 without rewriting either history. Exactly six planning paths change against C; complete C45 objects/root fields and complete prior DTO entry/record provenance remain. Only the distinct refreshed DTO task is appended for46. The reviewed seven-path scope includes only conditional R6 workflow_sha256 rebinding when the reviewed DTO workflow bytes change. This is adopted planning scope with no implementation dispatch authority. Actual J and canonical standalone/nested preflight receipts will be sealed externally after commit; independent exact-J review and explicit seven-path dispatch remain pending. Source-C CI success is retained solely for C; successor and DTO-code CI results remain null. All authorities remain false, credit0.
