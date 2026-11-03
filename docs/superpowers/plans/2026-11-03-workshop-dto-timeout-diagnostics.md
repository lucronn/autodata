# Workshop DTO Timeout Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after coordinator dispatch and the synchronized exact-base gate.

**Goal:** Retain actionable diagnostics for failed or cancelled Workshop DTO browser cases while preserving the strict 120-case inventory and 20-second case timeout.

**Architecture:** Keep DTO execution in the existing runner. Give each DTO case a mutable diagnostic record shared by the case body and its timeout wrapper, so cancellation cannot discard the last stage or fixture observations. Record a per-case Playwright trace, export before context close and retain it on any execution or cleanup failure; cap diagnostic cleanup separately from the unchanged execution watchdog. Preserve all API-fixture behavior.

**Tech Stack:** Python asyncio/unittest, Go TLS fixture, Playwright 1.64.1 and its pinned browser revisions.

**Spec:** The bounded contract and acceptance cases below, derived from retained CI evidence and the coordinator's plan-only request.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Canonical runbook: `docs/verification/workshop-customer-ui-runbook.md`
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-dto-timeout-diagnostics.json`
Record: `docs/agents/records/2026-11-03-workshop-dto-timeout-diagnostics.json`
Queue: `docs/agents/tasks/2026-11-03-production-release/queue.json`

**Planning state:** synchronized cleanup/trace amendment pending committed-checkpoint preflight and independent gate approval. Active source base: `b11c29444cde7b505bed3dd31bc7515d6d4ece5c`. Earlier c3659bc draft/review and receipts below are historical; b11 acceptance is failed, not promoted.

## Global constraints

- Implementation allowlist is exactly `scripts/dev/workshop_browser_smoke.py` and `scripts/dev/test_workshop_browser_smoke.py`. The runbook is the evidence/documentation companion; plan/task/record/queue are gate bookkeeping.
- Keep 40 distinct DTO scenarios across chromium/firefox/webkit, once each, strict result validation and failed/missing/skipped/unavailable rejection. Keep the separate 21 actual API cases and their 65-second timeout unchanged.
- DTO execution watchdog remains 20 seconds; no blanket retry, extra attempt, timeout increase, skip or failed-to-passed conversion. Explicit existing assertion timeouts, including the 15-second popup cancellation assertion, remain unchanged.
- Use DTO-context action and navigation defaults of 10,000 milliseconds. This does not guarantee every compound case finishes within 20 seconds; the outer watchdog still owns that boundary.
- The existing watchdog already awaits cancellation cleanup. Replace its unbounded teardown tail with a shared maximum 3-second diagnostic cleanup budget, rather than changing the 20-second execution timeout. Report execution and cleanup durations separately. A cancelled case may consume at most that documented bounded cleanup tail; do not describe 23 seconds as a new execution timeout.
- Capture only the owned DTO fixture/browser transport. No provider calls, external credentials, release actions or application changes. New diagnostics must not persist session/CSRF/token values, headers, response bodies, storage or source files. DTO trace DOM/network snapshots contain synthetic fixture data; treat them as restricted test artifacts.
- Keep Playwright 1.64.1, current browser revisions and workflow retention/upload unchanged. If the current uploader cannot retain the new files, stop and request a separately reviewed scope amendment.

## Evidence and limits

Push run [41735157815](https://github.com/lucronn/autodata/actions/runs/41735157815) tested exact `f9afa62dfdabf13041c13e9fd0bb2b4371818e0d`: 117 cases passed; WebKit bankone-cascade, banktwo-cascade and dual-bank-coverage failed after 20.091, 20.082 and 20.086 seconds. Their evidence has only generic TimeoutError; screenshots show vehicle selection complete and Article index ready, still on the listing page. Interrupted operation and failed-case requests were discarded. This is an unresolved failure, not proof that the article click specifically failed.

PR run [41735165863](https://github.com/lucronn/autodata/actions/runs/41735165863) has head SHA f9afa62 but its artifact candidate is merge checkout `cbabf8438f7da063d7e64cb67cc76a5145184428`; all 120 cases passed. All six input hashes, eleven served asset hashes, SDK hash, Playwright version and browser revisions/versions match the failed push. Both hosted jobs used Ubuntu 24.04 image 20261025.353.1 and runner 2.338.2. Both fixture logs contain the same 214 Firefox-phase TLS certificate errors, without a WebKit-correlated fixture error.

Exact-f9 local diagnostic execution passed the first six WebKit cases twice, then all 40 WebKit cases in 31.738 seconds. Source input hashes matched the failed artifact. Runtime image: `sha256:26aea6a9df1a7139e20a6893d9b63a11ab6b9978d113c718c6a792616be5a888`, Playwright 1.64.1/WebKit 2370 (27.2), 2 GiB memory/256 PID/256 MiB shared memory. These are diagnostic-only local passes, not a fresh 120-case acceptance run or proof of a resource/browser-regression cause.

Retained local evidence: `/tmp/autodata-ci-f9-push-dto-artifact`, `/tmp/autodata-ci-f9-pr-dto-artifact`, `/tmp/autodata-ci-f9-push-dto-full.log`, `/tmp/autodata-ci-f9-pr-dto-full.log`, `/tmp/autodata-dto-f9-diagnosis-receipt.json`, `/tmp/autodata-dto-f9-webkit40-results/evidence.json`, `/tmp/autodata-dto-f9-webkit40-browser.log`. Preserve these originals. GitHub artifact retention expires 2026-11-17; local paths are workstation evidence, not portable repository inputs.

## Cleanup budget and pre-close trace amendment (active)

Amendment source base: `b11c29444cde7b505bed3dd31bc7515d6d4ece5c` (owned candidate branch, not an accepted integration or release). The original approved gate was integrated at `510de650b7b0986027bfa968f68de7027f43c83f`. This is a plan-only amendment: no follow-up code is authorized until this synchronized committed checkpoint passes full-SHA preflight and independent gate review. Historical draft/review/receipt text below remains historical.

The exact b11 full owned Go TLS DTO run exited 1 with 117 passed and three Firefox failures: `google-popup-exchange`, `quote-exact-scope`, `logout-and-bfcache-clear`. All three failed at `context.close` after their scenario assertions completed, with cleanup durations 1.003, 1.004 and 1.004 seconds respectively; execution durations were 0.896, 0.417 and 0.712 seconds. The existing explicit one-second per-operation close cap caused these failures; they are real failed acceptance results. Their `trace_status=discarded` exposes a separate failure-diagnostics gap: trace discard happened before cleanup could fail. Do not relabel b11 as passing, infer that the earlier CI timeouts were harmless or modify b11 to hide this evidence.

Retained b11 evidence: `/tmp/autodata-dto-timeout-b11-browser/receipt.json`, `browser/evidence.json`, `browser.log`, `go-fixture.log`, `ready.json`, `command.json` and `probe/evidence.json` under that owned directory. Full-run evidence SHA256: `960cbc5bee642aef39a3e15f26404ec78e85c42f83f2fbb3c891e307f395a018`. Separate WebKit 27.2 deliberate action-timeout and outer-timeout probes both stayed failed at `article.open.click`, retained observed fixture requests/errors and produced valid Playwright ZIPs of 137865 and 351945 bytes. Their ZIPs are `probe/action_timeout/controlled-timeout-probe-failure-trace.zip` and `probe/case_timeout/controlled-timeout-probe-failure-trace.zip`; ZIP integrity checks and trace entries passed. Probe harness exit 0 means its expected-failure assertions passed, not that those cases passed. Runtime image was `sha256:26aea6a9df1a7139e20a6893d9b63a11ab6b9978d113c718c6a792616be5a888`, Playwright 1.64.1, pinned Chromium/Firefox/WebKit, 2 GiB RAM/256 PIDs/256 MiB shared memory. Owned processes were stopped and evidence preserved; no live providers were used.

**Precise replacement contract:** retain the 20-second execution watchdog, 10-second DTO action/navigation defaults, unchanged explicit scenario assertion limits, one execution per inventory case and no retry. Start one monotonic three-second cleanup deadline after execution/cancellation; never reset it. Screenshot (only when already failed) and trace export each receive `min(1 second, remaining shared budget)`. Capture the trace to the owned case path before closing the context even when scenario assertions passed. Validate that capture exists and is nonempty and at most 16 MiB; export failure, missing/empty/oversize capture or its timeout is an explicit failed case with diagnostic status, never a success. Remove oversize and late exports. Context close then receives only the remaining shared budget, potentially more than one second; no independent three-second close allowance. Cancellation-resistant work is cancelled without an unbounded join, retained until bounded DTO browser shutdown and prevented from leaving a late artifact. Keep primary failure/stage/call log; cleanup-only failure becomes a failed row at its actual cleanup stage, with fixture observations retained. External cancellation still propagates after bounded capture/cleanup.

Keep a valid pre-close ZIP on any scenario, export, context-close or final artifact-cleanup failure/cancellation. Delete the staged ZIP only after scenario execution, required capture and context.close all succeed; deletion failure is explicit failed cleanup and keeps the surviving ZIP. Fully successful cases retain the original success row fields and no ZIP. Trace start/export/cleanup status must distinguish retained, deleted after complete success, oversize, missing and failed/timed out capture. Never report a discarded trace for an otherwise successfully captured cleanup-only failure. This does not promise a trace when capture itself fails; preserve an explicit reason and the failed row. Restrict directories/files to 0700/0600 and preserve synthetic-data artifact restrictions.

**Resource/time tradeoff:** pre-close export now compresses/writes a trace for every DTO case, including passes; that adds CPU and I/O inside the existing one-second export and shared three-second cleanup limits. Sequential execution means one staged passing ZIP at a time, deleted after close; each retained failed ZIP is capped at 16 MiB (all 120 failures could retain up to 1920 MiB). The size check limits retained artifacts, not Playwright's in-memory trace buffers or transient export bytes before size inspection; the one-second export deadline and removal of oversize/late output bound the operation, not a claimed hard disk quota. The two probe sizes establish feasibility for those failures only. If fresh full acceptance exposes export-budget failures, preserve them and return for review; do not raise limits, omit required traces or retry. Workflow, upload retention, application, fixtures, dependencies and API mode remain outside scope.

**Meaningful red/green coverage:** use real wrapper/cleanup with fake owned browser operations. A close lasting at least 1.1 seconds but finishing inside the actual remaining three-second budget must fail under b11 and pass under the amendment. A close exceeding the remaining budget must remain failed and bounded; preceding screenshot/export time must subtract from close, with no deadline reset. Verify successful pre-close capture remains when close alone fails, and capture is deleted only after complete success. Verify failed/empty/missing/oversize capture cannot produce a passed row; retain original primary timeout evidence when diagnostics also fail, and cancel resistant/late exports safely. Keep screenshot/export one-second cap checks, inner action timeout, outer timeout, external cancellation propagation, strict failed-row rejection and single-execution assertions. Run targeted/developer suites plus fresh unchanged exact-candidate 120-case command and browser-backed ZIP probes; record head SHA and tested candidate separately. No test or code changes are part of this amendment checkpoint.

## Concrete todo

- [ ] Synchronize this cleanup/trace amendment in Issue #186/Project #8 and the five canonical documents, commit/push the plan-only checkpoint and pass full-SHA preflight; obtain independent gate approval before any follow-up implementation.
- [ ] In workshop_browser_smoke.py only, retain outer 20-second and inner 10-second timeouts; keep screenshot and trace export at most one second each within one shared three-second cleanup deadline, and allow context.close only the remaining shared budget without a fresh deadline or retry.
- [ ] Export the bounded DTO trace before context.close, retain it on any scenario or cleanup failure/cancellation, and delete it only after fully successful cleanup; keep retained ZIPs at most 16 MiB, remove oversize/late exports and explicitly fail missing or failed required trace capture.
- [ ] In test_workshop_browser_smoke.py only, prove a context close longer than one second succeeds within the remaining budget, exhausted cleanup stays bounded/failed, cleanup-only failure retains a trace and complete success deletes it; preserve controlled inner/outer timeout, cancellation, strict rejection and no-retry tests.
- [ ] Run focused and developer tests, fresh exact-candidate owned TLS 120-case DTO acceptance and valid browser-backed failure ZIP probes; preserve b11 117/3 and original f9 push 117/3 versus PR merge 120 provenance, then obtain independent exact-commit review before coordinator integration.

## Task 1: Prove diagnostic retention with controlled cancellation

**Files:** Modify `scripts/dev/test_workshop_browser_smoke.py`; consume the proposed DTO-only interfaces in Task 2. No browser/network is needed for these deterministic tests.

**Interfaces:** `run_dto_case(browser, origin, name, output, *, case_timeout=20)` returns a normal result dict; `dto_case(..., diagnostics=None)` accepts an optional diagnostic holder; `DTODiagnostics` holds named stage, fixture reference, failure classification and trace/cleanup metadata. Optional parameters preserve existing callers. Patch case execution/owned fake contexts in tests; production exposes no new CLI or environment test override.

- [ ] Add an `IsolatedAsyncioTestCase` suite using fake context/page/tracing objects and `asyncio.Event` barriers. One test holds an article click after publishing stage `article.open.click`, one observed GET and a synthetic page error. Release it via a Playwright-style inner timeout carrying a distinctive call-log string. Assert failed status, original error string, exact stage, request/error arrays and failure trace metadata.
- [ ] Add a second test that holds that same operation indefinitely and calls the real DTO timeout wrapper with test-local `case_timeout=0.05`. Assert outer timeout classification, one execution, no duplicate row, preserved stage/requests/errors, and `validate_results` rejection of the resulting failed inventory row. Keep production 20 seconds unchanged.
- [ ] Add cleanup failure tests: screenshot failure, trace stop failure, trace oversize and close that never finishes; each keeps the primary failure and records diagnostic errors/trace status. Test the shared cleanup deadline, including a cancellation-resistant fake cleanup task, under an enclosing 1-second test guard with a test-local 0.05-second cleanup budget. Cancel pending cleanup without an unbounded await; do not leave test tasks running. External cancellation must propagate as CancelledError after diagnostic capture rather than becoming a successful result.
- [ ] Add a passing-case test proving one invocation, no retained trace ZIP, normal requests/sdk fields and unchanged acceptance behavior. Assert DTO inner defaults are 10,000 milliseconds and API contexts/defaults are untouched. These contract tests must exercise runtime behavior, not just search implementation text.
- [ ] Run `python -m unittest discover -s scripts/dev -p test_workshop_browser_smoke.py -v`; record the expected failing diagnostics assertions before implementing Task 2. Do not weaken existing tests to obtain the red result.

### Concrete outer-timeout regression test shape

The named holder fields and wrapper in Task 2 must support this behavioral test; use the existing module's `unittest.mock.patch` and `tempfile.TemporaryDirectory` imports and retain its normal test discovery:

```python
async def test_outer_timeout_retains_observed_failure_state(self):
    entered = asyncio.Event()
    fixture = SimpleNamespace(
        requests=[{'method': 'GET', 'path': '/v1/catalog/years', 'query': {}}],
        errors=['synthetic-page-error'], unexpected=[])
    async def held_case(browser, origin, name, output, *, diagnostics=None):
        diagnostics.stage = 'article.open.click'
        diagnostics.fixture = fixture
        entered.set()
        await asyncio.Event().wait()
    with TemporaryDirectory() as directory:
        with patch.object(smoke, 'dto_case', side_effect=held_case) as case:
            row = await smoke.run_dto_case(None, 'https://127.0.0.1:32001',
                'bankone-cascade', Path(directory), case_timeout=0.05)
        self.assertTrue(entered.is_set())
        self.assertEqual(case.call_count, 1)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['diagnostics']['failure_kind'], 'case_timeout')
        self.assertEqual(row['diagnostics']['failure_stage'], 'article.open.click')
        self.assertEqual(row['diagnostics']['requests'], fixture.requests)
        self.assertEqual(row['diagnostics']['errors'], fixture.errors)
        with self.assertRaises(ValueError):
            smoke.validate_results([dict(browser='webkit',
                scenario='bankone-cascade', **row)], [('webkit', 'bankone-cascade')])
```

The fake exercises cancellation/evidence classification, not actual trace bytes or browser acceptance. Add the other explicit acceptance cases above with fake trace/context operations; use an owned browser-backed deliberate failure for ZIP validation.

## Task 2: Retain DTO failure state within bounded execution and cleanup

**Files:** Modify `scripts/dev/workshop_browser_smoke.py` only; use Task 1 tests. Preserve existing DTO fixture transport, every scenario assertion and API case logic.

**Produces:** Additive `diagnostics` on failed DTO rows: `failure_stage`, `failure_kind` (`action_timeout`, `case_timeout`, `exception` or `cancelled`), `requests`, `errors`, `unexpected`, `trace_status`, optional relative `trace_path`, `cleanup_elapsed_seconds` and `diagnostic_errors`. Existing row status/error/browser/scenario/provenance fields remain intact. Retain successful request/sdk fields as before. Diagnostics unavailable before fixture initialization use explicit empty arrays and the actual setup stage, never fabricated observations.

- [ ] Introduce `DTODiagnostics` in the same file. Set named stages before context/page creation, navigation, each vehicle select (`vehicle.year`, `vehicle.make`, `vehicle.model`, `vehicle.configuration`), article click/title wait, scenario-specific action group and final assertions. Preserve the failure stage before cleanup overwrites any lifecycle state. Add optional diagnostics arguments to shared selection/open helpers; pass them only from DTO execution so API behavior stays identical.
- [ ] Attach the actual DTOFixture to the holder immediately after construction. Preserve its observed request rows, page errors and unexpected requests when the body raises or is cancelled; capture snapshots before teardown. Preserve the original Playwright exception text/call log, and record outer timeout distinctly. Never retain raw headers/post bodies/session tokens in JSON.
- [ ] Set DTO context default action/navigation timeout to 10 seconds. Start tracing on that owned context with snapshots/screenshots enabled and source-file capture disabled. Keep recording within the single bounded case; export before context close for every DTO case and delete only after fully successful cleanup. On failure or cancellation, retain `<scenario>-failure-trace.zip` inside the existing per-engine output directory; chmod directories 0700/files 0600. Retain at most 16 MiB per trace ZIP: reject an oversize new trace with `trace_status=oversize`, remove only that new owned trace and keep the failure. A trace can include synthetic DOM/transport values; do not claim header-level redaction inside the ZIP. Never trace API mode.
- [ ] Use a shared 3-second diagnostic cleanup deadline: attempt screenshot and trace export with limits of min(1 second, remaining budget), then context close with only the remaining shared budget (no separate close deadline). Cancellation-resistant operations must not make the deadline wait indefinitely: cancel pending work, record the incomplete operation, and avoid an unbounded cancellation join. Keep references until browser shutdown; browser shutdown must also be deadline bounded for the DTO path so abandoned context work cannot escape the contract. Do not alter API shutdown. Record trace startup/export/cleanup failures explicitly; diagnostic errors never replace or erase the primary case failure. Trace startup failure itself fails that DTO case before scenario execution.
- [ ] Add `run_dto_case` as the DTO-only owner of the holder and unchanged 20-second timeout; preserve `CancelledError` propagation for external runner cancellation after capture. Outer timeout becomes a failed result with retained diagnostics. Wire only the DTO branch of the existing loop to it, leaving the 65-second API branch untouched. Preserve one row per expected case and final strict `validate_results` behavior.
- [ ] Run the focused test module to green, then `python -m unittest discover -s scripts/dev -p 'test_*.py'` and `git diff --check`. Inspect the two-file diff for unchanged scenario inventory, assertions, transport, provenance checks and API mode. Commit/push the validated milestone only after coordinator authorization under the repository cadence.

## Task 3: Validate actual owned fixture evidence and record its limits

**Files:** Update `docs/verification/workshop-customer-ui-runbook.md` with actual candidate evidence; update task/record/queue only as coordinator bookkeeping. No workflow change.

- [ ] Before follow-up implementation, coordinator independently reviews this synchronized cleanup/trace amendment checkpoint and reconciles latest integration; retain the exact five todos and allowed paths read back in Issue186/Project8 and record/task/queue. Pin the actual checkpoint SHA and run `python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-dto-timeout-diagnostics.json --base-sha "$CHECKPOINT_SHA"`. Implementation is blocked unless that committed-base result passes.
- [ ] Run the existing unchanged owned Go TLS/Playwright DTO command from `.github/workflows/autonomous-verification.yml` at the exact implementation SHA with Playwright 1.64.1, all three pinned engines and `--browser all --mode dto-fixture`; use its existing readiness/cleanup/upload contract. Retain its ready.json, fixture log and browser evidence. Do not substitute a subset or local helper for 120-case acceptance.
- [ ] Separately inject a controlled cancellation through the unittest seam and inspect its actual temporary diagnostic JSON/trace artifact, including failed status, original stage, observed requests/errors and trace status. A fake trace export validates lifecycle only; require one browser-backed controlled failure in an owned external diagnostic harness (not an inventory scenario) to confirm a nonempty ZIP can be opened and contains expected Playwright entries. Label this deliberate failure as diagnostic proof, never add it to or replace a case in the 120 inventory.
- [ ] Obtain fresh push/PR artifacts through the normal coordinator CI run; record both workflow head SHA and evidence candidate SHA, browser/input/asset provenance and all result counts. Verify any deliberate or real timeout remains failed/nonzero. Download and preserve artifacts before retention expiry.
- [ ] Independent reviewer checks exact commit and these results, including shutdown deadlines and cancellation propagation; coordinator integrates the approved milestone and updates evidence. A passing future candidate does not relabel the original 117/3 failure or the historical PR merge checkout, and does not establish the separate 21-case real API/release gate.

## Original plan-only draft verification (historical)

Clean worktree was created at the stated source base. Existing `test_workshop_browser_smoke.py` baseline: 17 tests passed. That original draft involved no implementation, new tests or browser runs; its GitHub synchronization and receipt correction are historical below. The active amendment changes only five canonical documents and authorized tracking, followed by commit/push and preflight. The original draft preflight intentionally blocked before tracking synchronization; it did not authorize implementation. Structural consistency/hash/diff checks passed. A fresh full-checkpoint preflight must pass after this synchronized checkpoint is committed.

## Tracking synchronization receipt

Independent re-review approved draft SHA256 `0ab6debc22818f9231a97987c82423c2bade0907d13c297a0472601be9221ae5` at source base `c3659bce633a439d2ad713296b3a1443ba39473d`. [Issue186 comment6617902111](https://github.com/lucronn/autodata/issues/186#issuecomment-6617902111) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, were read back at `2026-11-03T23:14:57.867643+00:00` with exact matching goal/five todos/two-file allowlist/five-document references and strict failure boundaries. Comment body SHA256 `28bf8f178facef692d3354b6b5c2a37251f90e4b481dac43661459e16eb06198`; Project field SHA256 `237f706c07636c0fcfb4ae1d12b161850130fcdb26695369ef50cfc431b41ce5`. The Issue body is unchanged; prior full Project text is preserved verbatim in the comment and all A/B/R6/retry references remain indexed. Original f9 push117/3 and PR merge120 evidence remains unchanged. Synchronization is plan-only; no implementation, CI rerun, release promotion or deployment is claimed.

### Receipt hash correction

At `2026-11-03T23:17:06.457458+00:00`, the live Issue186 body, comment6617902111 body and Project8 field were re-read. Issue **body** SHA256: `4e9bf6686796f231108f0886e7b083acd58def6cb14b49a81fae322c66ef1cec`; Issue **comment body** SHA256: `28bf8f178facef692d3354b6b5c2a37251f90e4b481dac43661459e16eb06198`; Project **field text** SHA256: `237f706c07636c0fcfb4ae1d12b161850130fcdb26695369ef50cfc431b41ce5`. Checkpoint `4b97ab44c6a944f883741e5a9b8f4a4a0384c2b6` incorrectly stored the comment body hash under `issue_body_sha256`; the corrected task/record/queue now retain these as separate named fields. The original readback time `2026-11-03T23:14:57.867643+00:00` remains historical. The live Issue body equals both saved pre/post-sync bodies; no Issue body or other GitHub content was changed for this correction. Goal, todo, allowlist, failure boundaries and all historical evidence remain unchanged. Independent exact-checkpoint approval is still required before implementation.

## Active amendment synchronization receipt

At `2026-11-03T23:29:01.292644+00:00`, [Issue186 amendment comment6618124676](https://github.com/lucronn/autodata/issues/186#issuecomment-6618124676) and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, were read back against the exact amended goal/five todos/two-file allowlist/five canonical paths and cleanup/trace contract above. Issue **body** SHA256: `534997d1af2a9abc240fac8d2d6e9e22121befb9fceb81a078668cf2b855438e`; Issue **comment body** SHA256: `a2bfdf53f3085d92607bf7598413c1b55ed2a89084424be7ff195bff6fdd5f9c`; Project **field text** SHA256: `bda629e6972eb3dff68be47ee1a009324b18e0ddd078c11613a09165e88bd019`. The Issue body concurrently gained an authorized PG17 successor appendix from its separate planner (previous body hash `4e9bf6686796f231108f0886e7b083acd58def6cb14b49a81fae322c66ef1cec`); this DTO task did not modify or restore it, and the final two readbacks match. Full original and immediately preceding Project indexes are preserved verbatim in this new comment; PG17 successor comment6618084753/checkpoint proof6618111784 and plan-only checkpoint `5d0571c73dd27fbb531425f3f740e1443f907cd1` remain indexed. Task/record/queue carry the same current receipt. A/B/R6/retry entries and top-level queue authority are unchanged. This authorizes only the synchronized plan checkpoint; full-SHA preflight and independent exact-checkpoint approval precede follow-up implementation. b11 remains failed117/3 and the original push/PR distinction remains unresolved.

Amendment checkpoint checks: existing browser runner baseline27 tests passed; JSON parse, exact task/record/queue/todo/hash/allowlist consistency, unchanged non-DTO queue/top-level authority, valid retained WebKit ZIPs and five-document scope checks passed. `git diff --check` passed. No implementation or new tests changed. Exact committed-SHA preflight and remote cleanliness are verified after commit, not inferred from these uncommitted checks.
