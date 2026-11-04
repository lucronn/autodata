# Workshop retryable reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after the coordinator synchronizes and pins this gate, passes machine preflight and authorizes dispatch. This synchronized planning checkpoint authorizes no implementation until the exact-SHA preflight and independent coordinator gate handoff pass.

**Goal:** Keep readable Workshop source visible and continue bounded sequential article GET polling through retryable job failures until canonical publication or a terminal outcome, without scheduling another rewrite.

**Architecture:** Interpret an existing durable job's retryable failure as active in the exported browser predicate. The existing sequential reader loop then keeps displaying available source and observing GET responses until canonical publication, a terminal outcome, cancellation or its existing budget. Backend transformation ownership remains authoritative; the browser performs no new prepare POST or rewrite dispatch to recover.

**Tech Stack:** Existing ESM modules, node:test, node:assert/strict, deterministic fake clock and AbortController; no dependencies.

**Spec:** docs/architecture/dataset-lifecycle.md (Workshop retryable reader amendment) and docs/agents/pre-implementation-gate.md.

## Historical synchronized planning checkpoint

The planning statements and unchecked execution checklist below are retained as the pre-implementation record. The completion addendum at the end gives the current result; their earlier pending status does not describe current implementation status.

## Global Constraints

- Gate tracking status: **synchronized**, read back at `2026-11-04T14:54:42Z`. [Issue #186 detail comment](https://github.com/lucronn/autodata/issues/186#issuecomment-6624605837) records the exact goal, two-file allowlist, five todos and five canonical references. Project #8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` indexes that comment in Source or dependency reference; Status remains In Progress and all other fields are unchanged. Commit/push this checkpoint, pass full-SHA preflight and obtain independent gate handoff before implementation.
- Source integration base: `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. Planning branch: `codex/workshop-retryable-reader-plan`.
- The future implementation base must be the full committed planning checkpoint SHA containing the synchronized plan, task, record, queue and canonical document, not this pre-plan source SHA. Coordinator must pin that full SHA when invoking preflight and dispatch; do not put a self-referential commit hash into its own contents.
- Implementation allowlist: `apps/api-go/workshop/article-read.mjs` and `apps/api-go/workshop-client.test.mjs` only.
- Preserve the existing 120000ms maximum reader budget, request timeout, backoff, retry-after, cancellation, source fallback and terminal authorization/takedown handling.
- Preserve one canonical rewrite per backend transformation key, stored-source media provenance/rights and warm publication reuse. Reader GET polling confers no scheduling or payment authority.
- Keep the pending/failed article-index hydration finding and missing-engine labels in separate gates. No API, payment, grant, source/model, media, bundle, browser fixture, schema, dependency or acceptance-inventory changes.
- Preserve all historical plans, verification records and failed acceptance receipts; Node fixtures prove browser helper semantics only, not live Firebase, Stripe, connectors, model success or production readiness.
- No merge, deployment, cloud/DNS/secret operation, production-data change or payment is authorized.

## Tracking and document map

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: docs/superpowers/plans/2026-11-04-workshop-retryable-reader.md
Task: docs/agents/tasks/2026-11-03-production-release/workshop-retryable-reader.json
Record: docs/agents/records/2026-11-04-workshop-retryable-reader.json
Queue: docs/agents/tasks/2026-11-03-production-release/queue.json
Canonical lifecycle document: docs/architecture/dataset-lifecycle.md

The docs-only planning allowlist is the five paths above. Existing queue entries and root metadata retain their historical contents/statuses. The new reader entry and standalone/nested records are synchronized from fresh live readback for this exact scope; implementation_authorized remains false until the coordinator supplies the exact-base gate handoff. No synchronization evidence is borrowed from another scope.

## Confirmed diagnosis and evidence limits

At the source integration SHA, `processingArticle` in `article-read.mjs:30-35` excludes every `failed` state. `readArticle:67-68` therefore returns immediately even for `processing.retryable === true`. The SQL view intentionally returns failed/retryable jobs and a retry delay (`038_article_transform_publication.sql:104-106`); worker claim logic can resume failed jobs (`source_job_persistence.py:168-169`).

A direct import of the pinned candidate's production reader, supplied readable source with a retryable failed job followed by an available canonical response, returned `{"active":false,"reads":1,"resultOrigin":"source","timedOut":false}`. The candidate's existing `node --test apps/api-go/workshop-client.test.mjs` passes all 55 tests; its transient-failure test covers a thrown network error rather than a successful HTTP response carrying failed/retryable processing state. This is a deterministic client defect, without an inference about production state or whether any particular failed model delivery can be retried safely.

## Concrete todo for Issue #186 / Project #8 / gate synchronization

1. Synchronize this reader-only goal, exact two-file scope, five todos, plan/task/record/queue and dataset lifecycle document in existing Issue #186 and Project #8; read back live tracking, commit and push the planning checkpoint, pin its full SHA and pass machine preflight before implementation.
2. Add a failing deterministic Node regression for readable source with failed/retryable=true and retry_after_seconds transitioning through queued and rewriting to completed canonical; assert source updates, sequential GET reads, honored delay and one terminal canonical update.
3. Change processingArticle only so failed is active exactly when retryable===true and job_id exists; preserve completed, needs_review, withdrawn and nonretryable failure as terminal, with no additional prepare POST or rewrite scheduling.
4. Add deterministic boundary tests for failed with false or missing retryable, persistent retryable failure reaching the existing absolute budget with source retained, and navigation abort during backoff preventing a later read or update.
5. Run focused red/green tests, the full Workshop Node suite, syntax and diff/scope checks; commit and promptly push the coherent validated fix to the coordinator-assigned branch, obtain independent exact-commit review and record evidence without merge, deployment or live-payment authority.

## One bounded implementation task: reader predicate and meaningful regressions

**Files:**
- Modify: `apps/api-go/workshop/article-read.mjs` — exported `processingArticle` predicate only.
- Test: `apps/api-go/workshop-client.test.mjs` — extend existing reader cases near the sequential/transient-failure and retry-after/budget tests.

**Interfaces:** Consume `processingArticle(article)` and `readArticle(read, {signal, onUpdate, wait, now, budgetMs})`. `read` returns `{status, data: {article}, retryAfterSeconds}`; `wait(ms, signal)` advances a deterministic clock or rejects when the supplied navigation signal is aborted. Produce the same return shapes and exports with corrected retryable-failure interpretation.

- [ ] **Step 1: Add the failing recovery regression.** Use the production exported helpers and existing node:test assertions. Require failed/retryable to be active, readable source to remain visible in emitted updates, the delay to be honored, reads never to overlap and canonical completion to stop the loop. This core case is directly executable:

```javascript
test('reader retries failed jobs until canonical without losing source', async () => {
  const { readArticle, processingArticle, readableArticle } =
    await import('./workshop/article-read.mjs');
  let now = 0, reads = 0, inFlight = 0, maxInFlight = 0;
  const waits = [], updates = [];
  const source = {
    content_origin: 'source', body: 'Stored source remains readable',
    processing: { job_id: 'job', state: 'failed', retryable: true,
      retry_after_seconds: 3 },
  };
  const responses = [source,
    { ...source, processing: { job_id: 'job', state: 'queued' } },
    { ...source, processing: { job_id: 'job', state: 'rewriting' } },
    { content_origin: 'canonical', body: 'Published canonical',
      processing: { job_id: 'job', state: 'completed', retryable: false } },
  ];
  const result = await readArticle(async () => {
    reads++; inFlight++; maxInFlight = Math.max(maxInFlight, inFlight);
    try {
      await Promise.resolve();
      assert.ok(responses.length, 'must stop after canonical completion');
      return { status: 200, data: { article: responses.shift() } };
    } finally { inFlight--; }
  }, {
    now: () => now,
    wait: async ms => { waits.push(ms); now += ms; },
    onUpdate: response => updates.push(response.data.article),
  });
  assert.equal(processingArticle(source), true);
  assert.equal(reads, 4);
  assert.equal(maxInFlight, 1);
  assert.deepEqual(waits, [3000, 2000, 4000]);
  assert.ok(updates.slice(0, 3).every(readableArticle));
  assert.ok(updates.slice(0, 3).every(a => a.body === source.body));
  assert.equal(updates.filter(a => a.content_origin === 'canonical').length, 1);
  assert.equal(result.data.article.content_origin, 'canonical');
  assert.equal(result.timedOut, false);
});
```

- [ ] **Step 2: Establish red evidence.** Run `node --test --test-name-pattern='reader retries failed jobs' apps/api-go/workshop-client.test.mjs`. The candidate exits before canonical and fails the active/read-count assertions. Retain this expected red result in the implementation handoff; do not mark the baseline suite as acceptance for this new behavior.

- [ ] **Step 3: Apply the minimal predicate repair.** Replace the unconditional terminal failed-state classification with the following equivalent explicit rule; leave the loop and all request/scheduling boundaries intact:

```javascript
export function processingArticle(article) {
  const processing = article?.processing;
  return Boolean(
    processing?.job_id &&
      !['completed', 'needs_review', 'withdrawn'].includes(processing.state) &&
      (processing.state !== 'failed' || processing.retryable === true),
  );
}
```

- [ ] **Step 4: Add boundary regressions using deterministic time.** For each of false and missing retryable, supply one failed source response and require exactly one read/update with timedOut false; additionally assert completed/needs_review/withdrawn remain inactive even with retryable true and absent job_id stays inactive. For a persistent retryable failed source with retry_after_seconds 9 and budgetMs 5000, require one read, clock 5000, timedOut true and the same source object returned. For navigation cancellation, create a NavigationGeneration, use its signal and arrange the injected wait to call navigation.clear() then `signal.throwIfAborted()`; require `assert.rejects` with AbortError, exactly one read and one source update. A later generation must remain current. Do not simulate recovery with a POST or alter backend retry policy.

- [ ] **Step 5: Verify and hand off the coherent milestone.** Run the focused and full tests, syntax and scope checks below. After all required checks pass, the assigned builder commits and promptly pushes the fix to its assigned branch and requests independent exact-SHA review. Coordinator records the actual implementation SHA and evidence in canonical tracking, then controls any integration and further browser acceptance under its existing gates. The initial draft author performed no commit, push, GitHub mutation or synchronized marking; the coordinator-delegated gate completion agent may verify and commit/push this five-path documentation checkpoint only.

```sh
node --test --test-name-pattern='reader|generation invalidation' apps/api-go/workshop-client.test.mjs
node --test apps/api-go/workshop-client.test.mjs
node --check apps/api-go/workshop/article-read.mjs
node --check apps/api-go/workshop-client.test.mjs
git diff --check
git diff --name-only <pinned-planning-checkpoint-sha> --
```

For the final command, use the exact committed SHA selected by the coordinator after live synchronization. Its output may contain only the two implementation allowlist paths before coordinator-owned evidence updates. If another implementation path is needed, stop and establish a separately synchronized scope amendment.

## Tracking readback and implementation boundary

The standalone record and nested task record carry identical goal, five todos and `status: synchronized`; the queue entry is `planning_synchronized_awaiting_gate_handoff`. All three retain `implementation_authorized: false` pending exact-base preflight and independent coordinator handoff. The earlier blocked preflight at source SHA e5fed171 correctly rejected the unsynchronized record and plan absent from that commit; that historical result is not relabeled.

Fresh readback evidence:

- Issue detail: https://github.com/lucronn/autodata/issues/186#issuecomment-6624605837; exact body 3674 bytes; SHA256 `1682662386e574c6dd775c56aa8817e0883b4ee2c86e7850630936004ed3a763`.
- Project #8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, Source or dependency reference: 812 characters; SHA256 `a3bd593ab8933a2bac46f4cf09daed0dcfdeb0a7401af3c2fc4320500dae9f22`. The prior Source text and hash are retained verbatim in record/task/queue tracking_sync; Status remains In Progress. The coordinator confirmed its original mutation asserted all other fields unchanged; the original temporary before-snapshot was lost, so this checkpoint does not claim a fresh before/after comparison.
- Full live Issue body and all 134 comments, exact scope comment and Project Source before/after history: `/home/corp/.codex/worktrees/workshop-retryable-reader-plan/reader-gate-live-tracking.json`; archive SHA256 `1b2e1bc9012b6fbc1e500f2cb85a1c053e5a13c261fba3571e52f8b8dbeead98`. The archive includes fresh REST Issue/comment data, GraphQL Project readback and the full current Project item from `gh project item-list`. The standalone/nested records retain archive references, hashes, body bytes and comment count. This is retained readback evidence, not a substitute for canonical plan files.
- The original pre-update Project snapshot and earlier /tmp readback archive were lost across a turn interruption. Prior Source text/hash survive verbatim in the draft; the coordinator confirmed its original mutation asserted every other field unchanged. This fresh read-only archive contains complete current Issue body, all 134 comments and current Project item; it does not reconstruct a full before-item snapshot. Existing Issue body/comments and historical queue evidence were not edited. The only live tracking writer was the coordinator; this planning agent performed read-only verification.

After committing and pushing the five docs paths, invoke machine preflight with the resulting full checkpoint SHA:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-retryable-reader.json --base-sha <full-committed-planning-checkpoint-sha> --repo-root .
```

Pass the exact full SHA and retained preflight output to independent review. Implementation dispatch additionally requires the coordinator's exact-base gate handoff and branch assignment. Old synchronized records, a draft plan, Node results or natural-language approval cannot substitute for this boundary. This work grants no release authority and does not change the existing release decision.

## Reviewed implementation and completion checkpoint — 2026-11-04

Implementation `4076ad3a197a6e520269f3dabd2a14f9b2e3d50f` is pushed on `codex/workshop-retryable-reader-build` ([draft PR #206](https://github.com/lucronn/autodata/pull/206)), based exactly on synchronized planning checkpoint `4f007d040da9834ead006d48aa2d641b3df412a7`. The builder reran full-SHA preflight successfully (`status: synchronized`, no errors) before implementation. Only the two implementation allowlist paths changed; production code changed only `processingArticle`. Failed jobs with a job ID remain active exactly when retryable is boolean true. The existing loop, source fallback, limits and scheduling boundaries are preserved.

Before the fix, three regressions failed for the expected causes: recovery classified the source inactive (`false !== true`), budget time remained zero (`0 !== 5000`), and navigation abort never rejected. After the predicate fix, `node --test --test-name-pattern='reader|generation invalidation' apps/api-go/workshop-client.test.mjs` passed 8/8 and `node --test apps/api-go/workshop-client.test.mjs` passed 59/59. Both changed modules passed `node --check`; diff whitespace and exact two-file scope checks passed. The recovery test observes four sequential reads, waits `[3000, 2000, 4000]`, readable source through queued/rewriting and one canonical update. Terminal false/missing/string retryable flags, terminal completed/needs_review/withdrawn, missing job ID, retained source on budget exhaustion and navigation backoff cancellation are covered. No prepare POST or rewrite scheduling code changed.

Independent exact-code review: **PASS**, reviewer `/root/reader_code_review`, coordinator-relayed in this chat. The reviewer reproduced the parent defect and independently reran focused 8/full 59 tests, syntax checks, pinned preflight and exact scope checks; no actionable findings. There is no saved review receipt or review artifact hash, and none is claimed.

Todo disposition: items 1–4 are complete. Item 5's implementation verification, commit/push and independent code review are complete; this docs-only completion checkpoint still requires its full-SHA preflight and independent docs review. The five original todos, historical gate record and historical planning tracking evidence remain intact. `implementation_authorized: false` continues to deny any new implementation dispatch; it does not retract the completed coordinator-authorized historical dispatch.

Completion tracking is synchronized in [Issue #186 completion comment](https://github.com/lucronn/autodata/issues/186#issuecomment-6633937350), body 1269 bytes / SHA256 `9e603d18026806d94df1f54acef01b10d4798057f86be4b840691293a68b5893`, and Project #8 Source (887 characters / SHA256 `941219fb79a17908c0afb6f60a7b76627802239fb249659e8d856d74153df8ec`). Status remains In Progress. The coordinator asserted all other Project fields unchanged; its retained Source readback is not a complete before/after item snapshot. Fresh read-only archive `/home/corp/autodata-evidence/reader-completion-live-tracking.json` (SHA256 `804cc9816b385b51e5c0356258ce023ce0bc87d7f49f3f98a171962dc1284aa7`) retains the complete Issue body, all 135 comments, the current full Project item and coordinator Source readback. Exact hashes, bytes and provenance are recorded under `completion.tracking_sync` in record/task/queue.

Synthetic Node reader fix at the e5fed171bb36fdb759c592cbcd0e15aea5490c97 lineage only. Final integrated candidate acceptance for 180 distinct cases (identity 5, catalog 8, commerce 14, paid 12, DTO 120, API 21), support/CI/security/image/SDK/license checks, and real staging Firebase/Stripe TEST/both-bank/model/recovery/cars.tk remain unverified and separately gated. No merge, deployment or production-readiness claim.

This checkpoint changes canonical documentation only. After commit/push, run the canonical preflight with its full SHA and retain the result under `/home/corp/autodata-evidence/`; no self-referential SHA is embedded here. Coordinator owns independent checkpoint review and further integration.
