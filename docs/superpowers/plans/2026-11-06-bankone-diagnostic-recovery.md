# Bankone Diagnostic Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Classify Mercury-3 response failures without retaining content and permit at most one guarded recovery dispatch for the existing Bankone prose canary.

**Architecture:** Extend the existing Mercury client failure boundary with bounded primitive diagnostics. Recover only the frozen terminal job using an explicit transactional one-use claim, preserving ordinary terminal-job behavior and existing canonical validation.

**Tech Stack:** Python ingestion worker, PostgreSQL, pytest; existing Mercury-3 HTTP client.

**Spec:** `docs/architecture/workshop-readonly-demo.md`, Bankone exact-job diagnostic recovery checkpoint below.

## Bankone exact-job diagnostic recovery checkpoint

Goal: Classify Mercury-3 response failures without retaining content and permit at most one guarded recovery dispatch for the existing Bankone prose canary.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-06-bankone-diagnostic-recovery.md`
Record: `docs/agents/records/2026-11-06-bankone-diagnostic-recovery.json`
Canonical document: `docs/architecture/workshop-readonly-demo.md`
Branch: `codex/bankone-diagnostic-recovery`, starting source `0d2db0d8abdb9531627252c2f6c12ef04ceeb29d` (PR346).

Frozen scope: Bankone job `a96ebe3a-16b9-4c3f-acb4-986efbb5ff2d`, article `aad66f67-355c-5d92-ab21-b4894bca9069`, source revision `acd11534-199a-40f7-bf94-717b34895752`, profile `full-prose-auto-v1`, 34 eligible prose slots. Existing outcome is `dead_letter` / `REWRITE_RESPONSE_INVALID`, one consumed dispatch, no candidate. Banktwo already published with one dispatch and zero ordinary-prose slots; it receives no further call. Original parse/output-budget cause remains unproven.

Maximum one additional Bankone provider dispatch, including diagnostic calls; cumulative Bankone <=2 and two-bank global <=4. Unknown delivery counts as consumed. Preserve every attempt/counter: no reset, new article/enrollment, broad worker/queue drain, fallback model, automatic second call, schema/profile/validator relaxation, checkout or grant change. For this sole recovery, pin `INCEPTION_MAX_TOKENS=32768` and `INCEPTION_API_TIMEOUT_SECONDS=60`. These bounded settings are a coordinator-approved hypothesis to accommodate 34 prose slots, not a proven diagnosis of the earlier 8192-token/20-second failure. The provider supports a higher token cap; 32768 is the existing client maximum. No separate tuning/diagnostic call and no further settings change or dispatch after failure is permitted. Never log or persist raw model body/content, prompt, licensed source, headers or exception text as diagnostics. Retain source fallback on failure.

Concrete todo:
- [ ] Add content-free Mercury-3 response diagnostics and focused parser/privacy regressions.
- [ ] Add an atomic one-use recovery claim for the frozen Bankone job with unchanged source/generation/profile fences and historical attempt budgets.
- [ ] Validate and push coherent implementation milestones; obtain exact-SHA review and required CI before coordinator deployment.
- [ ] Dispatch the frozen Bankone job at most once after fresh guards, or record its exact blocker; retain source fallback on failure.
- [ ] Verify all 34 prose slots, protected structure and permanent warm reuse on success; synchronize sanitized outcome evidence.

This is a docs-only checkpoint. The committed checkpoint must pass machine preflight at its full SHA before implementation. Runtime work follows coordinator integration/review/CI and fresh exact-job guards; this planning turn performs no provider or job call.

## Task 1: Content-free response diagnostics

Files: `workers/ingestion-python/src/autodata_ingestion/mercury2.py`, `article_lifecycle.py`, `article_lifecycle_store.py` in the same package; tests `workers/ingestion-python/tests/test_mercury2.py` and `test_article_lifecycle_integration.py`.

Interface: a typed ValueError with stable failure code and bounded primitive diagnostic mapping travels from `Mercury2Client.complete_json` to the existing locked attempt/job failure checkpoint. Keep successful return type `dict[str, Any]` and legacy direct-object compatibility. No new schema migration.

- [ ] Add failing tests distinguishing wire-size limit (>1MiB), envelope JSON decode, invalid/missing choices/message/content, content JSON decode, non-object content and `finish_reason=length` (reject even if JSON parses). Keep legacy direct-object success and older-model override regressions.
- [ ] Implement classifications with allowlisted stage enum, model/configured output limit, raw/content byte lengths, JSON position/line/column, bounded finish-reason enum, numeric usage counts, elapsed time and HTTP status only. Missing/malformed optional usage must not break success. Never retain exception text or arbitrary provider metadata; synthetic secret/prompt/source/body sentinels must be absent from serialized diagnostics.
- [ ] Add lifecycle tests proving client parse failures and storage-binding/projection failures are distinguishable, and timeout/unknown delivery remains consumed. Preserve renderer, protected-content and canonical failure semantics.
- [ ] Run focused client/lifecycle tests, check the diff, commit and push the passing diagnostics milestone.

## Task 2: One-use exact-job recovery

Files: `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py`, `article_lifecycle.py`, `article_lifecycle_store.py`; tests `workers/ingestion-python/tests/test_source_job_persistence.py` and `test_article_lifecycle_integration.py`. Keep any manual operational invocation private outside Git; do not add a generic endpoint or daemon.

Interface: an explicitly invoked recovery claim accepts the frozen job/article/source/profile plus expected generation, normalized hash, lease token/retry count, immutable recovery identifier, actor/reason and reviewed implementation SHA. It returns the existing fenced worker claim shape or a stable blocker. Ordinary ensure/polling/claiming never invokes recovery.

- [ ] Add failing transaction tests for the valid exact claim, repeated/concurrent claim, stale lease, source/generation/profile/normalization/hash/owner changes, wrong status/error, existing candidate/publication, active lease/prepared/dispatched attempt, unknown history, exhausted retry budget and dispatch called twice. Prove historical rows/counters and unrelated rows are preserved.
- [ ] Lock the exact job, owning article and historical attempts in one transaction. Require the frozen `dead_letter` + `REWRITE_RESPONSE_INVALID` job, current article ownership, source/profile/generation/normalization/hash agreement, no candidate/publication, no active claim and exactly one known prior Bankone delivery. Verify history for both frozen banks (Banktwo job `64888ce4-429e-4e22-9892-48d1fb4b82eb`); ambiguous delivery counts as consumed. Require Bankone<2, global<4 and existing `retry_count<max_attempts`; otherwise return a blocker without mutation.
- [ ] Atomically consume the immutable recovery identifier, acquire a fresh fenced processing lease and increment existing retry_count/lease_token, preserving prior values/history. Bind max_additional_dispatches=1 to the claim and consume it transactionally at rewrite dispatch. A prepared claim can resume only under its existing lease fences; dispatched/unknown delivery is terminal and cannot obtain a second call. Ordinary claiming continues to ignore the terminal job.
- [ ] Run the actual repository PostgreSQL integration fixture plus focused tests below; commit/push passing guarded recovery milestone. Required CI and independent exact-SHA review precede coordinator deployment.

```sh
PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_mercury2.py workers/ingestion-python/tests/test_source_job_persistence.py workers/ingestion-python/tests/test_article_lifecycle_integration.py
git diff --check
```

## Task 3: Coordinator execution and acceptance

- [ ] Inspect/back up private current database and immutable runtime; verify exact identities, current counters, fences, unchanged unrelated business/queue/source fingerprints and purchase-config `enabled:false`. Drift, unknown counts or exhausted budget blocks the operation. Never substitute an article or increase counters/budgets.
- [ ] Use only the explicit guarded claim and exact-job worker for one further dispatch. No separate diagnostic provider call. Preserve original failure and append sanitized outcome; any failure/timeout stops with source fallback.
- [ ] On success require persisted automatic `full-prose-auto-v1` canonical revision, truthful `UNREVIEWED`, no manual approval, all34 ordered slots accounted for with changed/retained counts and reasons, actual ordinary-prose changes and existing independent protected technical/table/safety/media/evidence/order validation. Mechanical validity does not prove semantic equivalence.
- [ ] Verify ten warm read/ensure pairs and a separate fresh-process read with actual zero source/media/model/scheduling calls and stable revision/content hashes, unchanged unrelated fingerprints, readiness200 and purchase disabled. Synchronize sanitized exact source/CI/review/counters/outcome to Issue/Project/canonical document; preserve failure if acceptance does not pass.

## Handoff and ownership

Diagnostics owner: Mercury client and its tests. Recovery owner: source-job persistence/claim tests. Coordinator owns the shared lifecycle boundary, integration and operational invocation; serialize shared-file edits. This checkpoint does not require parallel agents. Canonical preflight record is the companion JSON; implementation base is the full SHA of this committed docs checkpoint, supplied to `scripts/autonomy/pre_implementation.py --base-sha`.
