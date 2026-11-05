# Retry queue test clock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the two retry-queue pre-due assertions deterministic by supplying an explicit instant before the persisted retry due time, with application behavior unchanged.

**Architecture:** Use the existing `now: str | None` injection accepted by `process_chat_jobs` and `process_chat_price_jobs`. Derive a timezone-aware cutoff one microsecond before the persisted `next_attempt_at`, preserving the existing checks that work runs exactly at its due time. Keep scheduling, timestamp formatting and all application behavior unchanged.

**Tech Stack:** Python 3.12 CI, pytest, standard-library datetime/timedelta.

**Spec:** This narrow canonical plan and `docs/agents/pre-implementation-gate.md`.

## Global constraints and draft status

- Inspection/integration base: `3a511f1d8a7c3b45fcc67c93a121063286c95097`. This base is source context, not an authorizing implementation checkpoint.
- Planning status: `synchronized`; independent review approved the original draft and rebased four-document patch `aa1865c6293c6975c612bec8b54fcfeb4f5fd6c8c3a0556aa09aba15ccfaa61f`. Issue #186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6617577291 and the existing Project #8 item were read back at `2026-11-03T22:55:56.306591+00:00` with the exact goal/four todos/one-file scope/four refs. The compact Project field preserves A/B/R6 references; its previous complete text is retained verbatim in this comment. This synchronization permits the documentation checkpoint only; commit/push, pinned preflight and independent coordinator gate handoff remain required before implementation.
- Issue: https://github.com/lucronn/autodata/issues/186
- Project: https://github.com/users/lucronn/projects/8 ; existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
- Task: `docs/agents/tasks/2026-11-03-production-release/retry-queue-test-clock.json`. Record: `docs/agents/records/2026-11-03-retry-queue-test-clock.json`. Queue: `docs/agents/tasks/2026-11-03-production-release/queue.json`.
- Builder allowlist: exactly `workers/ingestion-python/tests/test_chat_service.py`; two existing assertions plus the standard-library import they require.
- Documentation checkpoint allowlist: this plan, the task, the record and the existing queue entry addition only. This plan is the dedicated canonical repository documentation for the fix; no application or broad release-plan amendment is needed.
- Execution: gpt-6.1-sol, medium reasoning, Fast/priority when exposed, no model fallback.
- No runtime/timestamp-format/backoff-policy changes, test suppression, dependency changes, release authority or acceptance/profile promotion.

## Evidence and root cause

PR CI run https://github.com/lucronn/autodata/actions/runs/41732657383 attempt1 at `a0eed5dce45171f5f94f72d99d2fdf694235df0d` failed `tests/test_chat_service.py::test_due_only_retry_queue_persists_backoff_and_dead_letters` at line923: its second real-time `process_chat_jobs()` returned a legitimately due retry instead of `[]`. The same-SHA push run https://github.com/lucronn/autodata/actions/runs/41732582488 passed. These historical outcomes establish intermittency; they do not certify this draft or any future candidate. The coordinator owns the already-requested PR rerun and its final outcome.

Retained failed log: `/tmp/autodata-ci-a0eed-pr-failure.log`, SHA256 `c8a337fd7d7e092a0e934b350b3cf3282772576f81b0198243b67ad762fbf0e9`.

`chat_service.py:1125` schedules first source retry as `_timestamp(datetime.now(UTC).timestamp() + 1)`; the price branch at 1079 uses the same calculation. `_timestamp` at 2322–2324 floors microseconds. A failure at `22:41:47.999000Z` therefore schedules `22:41:48Z`, only 1 ms later. After a 2 ms pause, the next real-time claim at `22:41:48.001000Z` correctly finds it due. The adjacent price-refresh test at 959 makes the same invalid assumption. This is a deterministic explanation of the failure mechanism, not a claim that CI captured the exact subsecond scheduling instants.

At `052bbf9ac29a9c74163162f0f91adc2f6a656e4e`, the two original tests passed normally (`2 passed in 0.14s`). A read-only controlled-clock harness reproduced each original failure and passed each in-memory proposed assertion change under that same 2 ms boundary crossing. No application or test files were changed for these checks. The harness is reproduced below so an executor can verify the evidence without relying on `/tmp` retention.

## Concrete todo

1. Independently review this blocked four-document draft; synchronize the exact goal, one-file scope, references and todo in existing Issue #186/Project #8 only after review; commit/push the synchronized checkpoint and pass exact-base machine preflight before implementation.
2. In workers/ingestion-python/tests/test_chat_service.py only, import datetime and timedelta and replace the two immediate real-time empty-queue assertions with explicit now values one microsecond before each persisted next_attempt timestamp; retain all due-time, retry-count, dead-letter and available-answer assertions.
3. Verify both controlled-clock boundary reproductions fail with the original assertions and pass with the proposed assertions; run both focused tests, the complete chat-service test module and ingestion suite, and inspect the exact one-file diff.
4. Commit and promptly push the validated test-only milestone, obtain independent exact-commit review, then let the coordinator integrate and record fresh exact-candidate CI without relabeling historical evidence or changing release authority.

## Task 1: Synchronize the reviewed checkpoint before code

**Files:** the four documentation paths listed above. **Consumes:** independent review of these exact draft bytes. **Produces:** a committed synchronized record at a fresh immutable checkpoint `B` descended from `3a511f1d8a7c3b45fcc67c93a121063286c95097`.

- [ ] Obtain independent draft review; resolve any finding in documentation only. Completed: original and rebased draft reviews approved; synchronization receipts below are documentation-only.
- [ ] Coordinator updates existing Issue #186 and its existing Project #8 item with the exact goal, literal one-file scope, references and four todo items above; preserve unrelated tracking context and read back both records.
- [ ] Record actual readback provenance, change this dedicated record/task object to `status: synchronized`, and update only this queue entry accordingly. Never infer synchronization from the global queue field.
- [ ] Commit/push the four-document checkpoint. Supply its full SHA as external `B`; do not embed a commit's own SHA in its contents. Re-read all plan/task/doc bytes at `B`.
- [ ] Run `python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-retry-queue-test-clock.json --base-sha B --repo-root <owned-checkout> --policy <owned-checkout>/.autodata-autonomy-policy.json`. Require exit0 and `{"status":"synchronized","errors":[]}`, actual tracking readback and independent coordinator gate handoff before implementation. Before synchronization, the blocked/uncommitted draft failed preflight as required; the synchronized committed checkpoint must pass at its full SHA.

## Task 2: Make the two pre-due assertions explicit

**Modify:** `workers/ingestion-python/tests/test_chat_service.py` only. **Consumes:** `next_attempt` returned by each existing test, an RFC3339 UTC timestamp. **Produces:** explicit ISO8601 `now` cutoffs for the two existing queue checks; no new production interfaces.

- [ ] From the clean authorized base `B`, run the controlled-clock harness below against original test bytes; require both expected boundary failures. Do not add a new test case for this reversible test-only repair.
- [ ] Add `from datetime import datetime, timedelta` among standard-library imports. Replace only the source-test assertion currently at 923 with:

```python
    not_due = (
        datetime.fromisoformat(next_attempt) - timedelta(microseconds=1)
    ).isoformat()
    assert process_chat_jobs(now=not_due) == []
```

- [ ] Replace only the price-test assertion currently at 959 with:

```python
    not_due = (
        datetime.fromisoformat(next_attempt) - timedelta(microseconds=1)
    ).isoformat()
    assert process_chat_price_jobs(now=not_due) == []
```

`datetime.fromisoformat` accepts the existing `Z` timestamp on the repository's Python 3.12 CI. Keep `now=next_attempt` executions, three-attempt terminal assertions, backoff metadata and available-answer checks exactly as they are. Do not introduce sleeps or increase backoff durations.

- [ ] Run the harness below; on edited bytes both actual tests must pass for both harness modes. Before editing, expected original FAIL / in-memory proposed fix PASS is the diagnostic baseline. The inline replacement in the harness only recognizes original assertions, so it leaves already-fixed source untouched.
- [ ] From `workers/ingestion-python`, run `PYTHONPATH=src python -m pytest -q tests/test_chat_service.py::test_due_only_retry_queue_persists_backoff_and_dead_letters tests/test_chat_service.py::test_price_refresh_retry_is_due_only_and_never_blocks_available_answer`, then `PYTHONPATH=src python -m pytest -q tests/test_chat_service.py`, then the CI ingestion command `PYTHONPATH=src python -m pytest -q tests` with its existing environment/skip policy. Record failures honestly; do not broaden scope to repair unrelated failures.
- [ ] Run `git diff --check` and inspect `git diff --name-only B`; only the one allowed test file may differ during implementation. Confirm all other test assertions and runtime source bytes are unchanged.
- [ ] Commit the validated milestone as `test: make retry queue due checks deterministic`, promptly push the assigned branch, and obtain independent exact-commit review. Coordinator owns integration and fresh exact-candidate GitHub CI; retain historical failures and no deployment or release-acceptance implication.

## Read-only controlled-clock reproduction

Save the following outside the repository (for example `/tmp/autodata-retry-boundary-repro.py`) and run from `workers/ingestion-python` using `PYTHONPATH=src python /tmp/autodata-retry-boundary-repro.py`. Before the fix require original expected boundary FAIL followed by in-memory proposed fix PASS for both tests. After the fix require both modes PASS; the harness detects whether the original assertion remains and selects the expected result accordingly. The harness patches clocks and loaded function source in memory; it writes no repository files.

```python
import inspect
import runpy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
import autodata_ingestion.chat_service as service

TESTS = (
    ('test_due_only_retry_queue_persists_backoff_and_dead_letters', 'process_chat_jobs'),
    ('test_price_refresh_retry_is_due_only_and_never_blocks_available_answer', 'process_chat_price_jobs'),
)
for name, process in TESTS:
    for proposed_fix in (False, True):
        tests = runpy.run_path('tests/test_chat_service.py')
        original_install = tests['install_runtime']
        state = {'now': datetime(2026, 11, 3, 22, 41, 47, 999000, tzinfo=UTC)}
        class ControlledDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return state['now']
        def install_runtime(**kwargs):
            result = original_install(**kwargs)
            original_enqueue = service._runtime.queue.enqueue
            def enqueue(query_id, **queue_kwargs):
                result = original_enqueue(query_id, **queue_kwargs)
                if queue_kwargs.get('available_at') == '2026-11-03T22:41:48Z':
                    state['now'] = datetime(2026, 11, 3, 22, 41, 48, 1000, tzinfo=UTC)
                return result
            service._runtime.queue.enqueue = enqueue
            return result
        test = tests[name]
        source = inspect.getsource(test)
        original_assertion = f'assert {process}() == []'
        expect_failure = not proposed_fix and original_assertion in source
        if proposed_fix:
            source = source.replace(
                f'assert {process}() == []',
                f'assert {process}(now=(datetime.fromisoformat(next_attempt) - timedelta(microseconds=1)).isoformat()) == []',
            )
        namespace = dict(test.__globals__, install_runtime=install_runtime, datetime=datetime, timedelta=timedelta)
        exec(source, namespace)
        failed = False
        with patch.object(service, 'datetime', ControlledDateTime):
            try:
                namespace[name]()
            except AssertionError:
                failed = True
        assert failed == expect_failure, (name, proposed_fix, failed)
        print(f'{name}: {"expected original boundary FAIL" if expect_failure else "controlled-boundary PASS"}')
```

## Review and evidence limits

This test change proves due-only queue behavior against a selected pre-due instant and preserves the existing execution at the persisted due instant. It does not assert that nominal 1 s retry delay lasts a full wall-clock second: the existing truncation remains unchanged and would need its own application-behavior gate if changed later. A passing rerun establishes only that run's result; the deterministic reproduction remains the basis for this small follow-up.

## Tracking synchronization receipt

Issue comment: https://github.com/lucronn/autodata/issues/186#issuecomment-6617577291. Project: https://github.com/users/lucronn/projects/8, item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, status In Progress, field `Source or dependency reference`. Exact readback time: `2026-11-03T22:55:56.306591+00:00`. Issue body SHA256 `1818a092a98cb40bf172284ed9450488965a7dd25d73e714430b737fb65ecc17`; Project text SHA256 `e51731eb7c7da9dbeffd6b86f2eb0cbaf2e4ad6ebc5527b405128fb1b45537f6`. Task and standalone record retain the identical `pre_implementation` object; the queue entry shares its todo and receipt. The pinned documentation commit is supplied externally after commit/push, avoiding commit self-reference.
