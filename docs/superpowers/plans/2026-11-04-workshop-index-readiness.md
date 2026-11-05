# Paid article index readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the committed gate passes. Steps use checkbox (`- [ ]`) syntax for tracking. Coordinator dispatch and branch ownership apply.

**Goal:** Prevent paid article indexes from appearing ready until both current provider generations explicitly complete, while polling pending or retryable work and preserving usable partial descriptors.

**Architecture:** Keep existing durable provider scopes and current source jobs as the readiness authority. Correct the store aggregate, map its progress to HTTP hydration, and gate browser ready copy on explicit completion. Retain the existing bounded collection polling helper and paid GET access/descriptor boundaries.

**Tech Stack:** Go/pgx/PostgreSQL; browser ES modules; Node native tests; existing isolated Python/R3 fixture runner.

**Spec:** `docs/architecture/article-catalog-list-only-hydration.md`, section “Paid index readiness correction”. The reviewed external proposal was inspected at `/home/corp/autodata-evidence/index-readiness-plan.md`; this repository plan carries its full implementation requirements.

**Current leaf status:** reviewed implementation and isolated acceptance complete at `23a2f3b2e12c0b14b1d4989ab13a075cf1bee084`; completion tracking is synchronized; independent review of the docs completion checkpoint remains required before integration. Historical gate prerequisites below describe the pre-code boundary.

## Gate and pinned provenance

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-04-workshop-index-readiness.json`
Task: `docs/agents/tasks/2026-11-03-production-release/workshop-index-readiness.json`

Inspected application candidate: `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. The revised technical draft passed independent review. Issue/Project synchronization was freshly read back and the record is **synchronized**, with the receipt below. Implementation remains blocked until this docs-only checkpoint is committed/pushed, full-SHA preflight passes, and independent committed-gate review and coordinator dispatch occur. The implementation base must be the later full SHA of the committed docs-only synchronized checkpoint containing this plan and its refs. Run the canonical preflight at that exact SHA before any implementation-file edit. A passing earlier integration gate does not authorize this change.

Preserve the complete then-current Issue body/comments and Project index, including PG, Stage1A, M2A and reviewed-leaf records. Append/update only this task’s tracking through the coordinator’s serialized writer slot. Retain exact before/after text hashes and API readback references before setting this record synchronized. Do not replace predecessor evidence with this correction.

## Global constraints and file boundaries

- Agents: GPT-6.1 Sol, medium reasoning, Fast / priority service (fastest available), per the user’s preference.
- Production allowlist is exactly `apps/api-go/catalog_store.go`, `apps/api-go/catalog_http.go`, `apps/api-go/workshop/app.mjs`.
- Test allowlist is exactly `apps/api-go/postgres_catalog_lifecycle_test.go`, `apps/api-go/catalog_access_test.go`, `apps/api-go/workshop-client.test.mjs`.
- Gate-document allowlist is this plan, its record/task, the existing release queue, and the two canonical repository documents listed in the record. Preserve all unrelated queue entries and fields.
- No changes to `catalog.mjs`, workers, commerce, schema, contracts, payment flows, deployment configuration or provider credentials. Paid GET remains read-only and descriptor-only. HTTP collection responses remain 200 with existing access and no-store behavior.
- Both bankone and banktwo must be complete at their current generation; descriptor counts and article-body completion do not decide index readiness. Both completed with zero descriptors is a valid complete empty index.
- Source authority is `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py:230`: retryable failure stays `failed` only within budget; exhausted work becomes `dead_letter`; nonretryable work becomes `needs_review`. Scope and job error writes can be observed in separate transactions. A terminal job can coexist with a stale running scope.
- No live payment, paid provider request, provider-rehearsal claim, merge, release, deployment or activation is authorized by this plan. Fixture/unit outcomes establish only their measured scope.

## Concrete todo

- [x] Preserve live Issue186 and Project8 history, append this goal/refs/todo, read back both records, then synchronize the docs-only checkpoint and pass full-SHA preflight.
- [x] Add real PostgreSQL current-job progress regressions within the existing cold fixture root; correct aggregate retryable/terminal predicates in catalog_store.go and restore fixture state.
- [x] Add paid Handler hydration and read-only descriptor regressions in catalog_access_test.go; correct catalog_http.go incomplete hydration mapping.
- [x] Execute actual loadArticles with real bounded readCollection in workshop-client.test.mjs; clear prior completion live-region text at current-load entry and require explicit complete before ready while preserving partial rows and desired-article opening.
- [x] Run exact-candidate Node/Go/contract and required non-skipped isolated PostgreSQL acceptance; record commands, counts, SHA and scope checks, then commit/push validated milestones.
- [x] Obtain independent exact-head review and synchronize final evidence; retain separate release/provider/payment/deployment gates.

## Task 1: Current-job progress truth

**Files:** modify `apps/api-go/catalog_store.go:610`; test `apps/api-go/postgres_catalog_lifecycle_test.go`.
**Interface:** `(*postgresCatalogStore).CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error)` retains all current fields and scope boundaries.

- [x] Add a real-query table matrix through `r3Setup` and its `pgxpool`, using isolated scope/job rows and restoring every changed fixture row. Run it as a plain helper/table loop within existing `TestPostgresCatalogLifecycleColdHTTPRaceOneJob`, before its original assertions; the Python bridge freezes four exact Go root names and `validate_go_events` requires exactly one root run/pass per case. Do not use `t.Run`, add test roots, emit subtest run/pass events, or modify the Python harness. Record every named matrix case with expected/observed full tuples and assertion outcomes in `f.extra["index_readiness_cases"]` (included in `go-measurement.json`) and `t.Logf` output for both providers. Keep the existing nonempty partial-scope regression: because it changes only the scope and leaves a completed current job, change its incorrect `Retryable=true` expectation to `Retryable=false`, retaining `Complete=false` and `Status=failed`. Preserve fixture/provider counters.
- [x] Prove regression failure against the unchanged store in required fixture mode. Assert the full tuple `(Status, Complete, Retryable, Processed, Total, Percent)`; Total is always 2 and Percent is Processed*50. Use this matrix:

| Persisted observation | Status | Complete | Retryable | Processed |
| --- | --- | --- | --- | --- |
| No scopes | pending | false | false | 0 |
| One pending scope/current pending job | running | false | false | 0 |
| Both pending/current pending jobs | running | false | false | 0 |
| Processing current job | running | false | false | 0 |
| Partial scope + failed retryable current job within budget, future next_attempt_at | failed | false | true | 0 |
| Complete current bank + failed retryable other bank | failed | false | true | 1 |
| Processing bank + terminal failed other bank | running | false | false | 0 |
| Processing bank + retryable failed other bank | running | false | true | 0 |
| needs_review current job + stale running scope | failed | false | false | 0 |
| dead_letter current job + stale running scope | failed | false | false | 0 |
| failed current job with retryable=false | failed | false | false | 0 |
| failed current job with retry_count=max_attempts | failed | false | false | 0 |
| Terminal scope partial/failed/needs_review/not_configured without retryable current job | failed | false | false | 0 |
| Both current generations complete | completed | true | false | 2 |
| Both complete with empty descriptor list | completed | true | false | 2 |
| Completed scope with stale completed_generation and no active/failed current job | pending | false | false | 0 |

A pending scope without an active current job remains pending. No due-time filter belongs in retryability. Use real transaction-safe fixture updates and restore state even when a case fails; never change production DB targets.

- [x] Extend the existing single aggregate query with independent retryable count and job-terminal failure predicates, leaving existing vehicle/configuration/provider filtering and current-generation completion expression intact:

```sql
-- Retryability belongs only to the joined current source job:
job.status = 'failed' AND job.retryable = true
  AND job.retry_count < job.max_attempts
-- Failure indicators (in addition to terminal scope states):
job.status IN ('needs_review', 'dead_letter')
  OR (job.status = 'failed' AND
      (job.retryable = false OR job.retry_count >= job.max_attempts))
```

Retain scope states `partial`, `failed`, `needs_review`, `not_configured` as failure indicators; also count failed retryable jobs as failed work even if the scope is temporarily running. Set Retryable independently from this count. Aggregate precedence is: both current generations complete => completed; otherwise any current pending/processing job => running; otherwise any failed work => failed; otherwise pending. Complete suppresses hydration at the HTTP boundary even for a defensive inconsistent progress object.

- [x] Re-run the required SQL matrix and existing cold regression, then the Go suite. Commit and promptly push the coherent store/test milestone to the coordinator-assigned branch after checks pass.

## Task 2: Paid HTTP hydration contract

**Files:** modify `apps/api-go/catalog_http.go:179`; test `apps/api-go/catalog_access_test.go`.
**Interfaces:** `listCatalogArticles` and `CatalogHydrationResponse` retain their shape. Extend `paidHTTPStore` with controlled progress, preserving its default nil result for existing tests; use `paidHTTPServer` with `grant.err=nil` through the real Handler.

- [x] Add table cases for pending/running/retryable-failed/terminal-failed/completed/nil progress, each with empty and nonempty descriptors. Assert 200; explicit complete flag; hydration; private no-store headers; no article body/source metadata; zero ingestion calls. Retain denied-grant-before-protected-read assertions. Test contradictory complete=true/running defensively: complete suppresses hydration.
- [x] Run the targeted paid Handler tests before the fix and retain the expected pending/retryable failures. Replace the hydration predicate with:

```go
hydrating := progress != nil && !progress.Complete &&
    (progress.Status == "pending" || progress.Status == "running" ||
        (progress.Status == "failed" && progress.Retryable))
```

Keep the existing paid-mode guard around scheduling, descriptor projection and grants. Nil progress is incomplete/nonhydrating; it cannot mean ready in the app.

- [x] Run `go test ./...` from `apps/api-go`, then commit and promptly push the HTTP/test milestone after it passes.

## Task 3: Browser readiness and actual polling flow

**Files:** modify `apps/api-go/workshop/app.mjs:339`; test `apps/api-go/workshop-client.test.mjs`.
**Interfaces:** actual `loadArticles(g, articleID='')` consumes unchanged `readCollection` from `workshop/catalog.mjs`; use the existing `appSection`/`runInNewContext` test boundary and actual imported helper. Stub request/render/navigation boundaries for sequence tests; add a separate regression that executes the actual `status` function and DOM boundary for stale completion text. For deterministic tests inject wait/attempts through a wrapper that still executes the actual helper, and assert request counts.

- [x] Add real-function sequence cases: pending->running->complete (3 reads), retryable failed->complete (2), terminal incomplete (1), persistent pending (3 configured attempts then timedOut), incomplete nonhydrating/nil-progress (1), completed empty (1), partial rows visible/clickable during preparation, desired article present while incomplete (1 and immediate `loadArticle`), stale generation and abort suppression. Seed `#completion-status` with ready text from completed vehicle A, begin loading vehicle B, and prove it clears immediately before B’s first request resolves; repeat for B pending and terminal outcomes using actual `status` and DOM. Assert no ready status occurs until `complete===true`; existing helper tests stay green. Use the existing renderArticles/DOM boundary to prove the partial link still targets the selected article, rather than merely checking an array length.
- [x] Run the new native tests before modifying the app and retain both premature-ready and stale-completion-text failures. At `loadArticles` entry, after verifying this is the current navigation and before its first await, explicitly clear the completion live region. The current `status(..., {complete:false})` leaves prior completion text in place, and `clearProtected` does not clear it, so merely changing final status options is insufficient. Implement the local entry boundary within the allowed app file:

```javascript
if (!g.current()) return;
$("completion-status").textContent = "";
stage("articles");
status("Opening your article index…", { busy: true });
```

Preserve the current desired-article branch before overall readiness classification. After `g.current()` check, classify outcomes explicitly:

```javascript
// Keep the existing desired-article fast path first.
if (data.complete === true) {
  status(data.items.length ? 'Article index ready.' :
    'Article index ready. No articles are currently available.', { complete: true });
} else if (data.progress?.status === 'failed' && data.progress?.retryable !== true) {
  status('Your article index could not be prepared. Available articles can still be opened.',
    { complete: false });
} else {
  status('Your article index is still being prepared. Check again.', {
    complete: false,
    retry: () => operation((next) => loadArticles(next)),
  });
}
```

The existing wire progress property is `progress`, emitted by `CatalogArticlesResponse.Progress`. The check-again callback performs another read, not a restart of provider work. Keep terminal status safe and omit restart instructions. Retain partial rows, generation checks, signal handling and existing helper default 40 reads / 1500ms interval / one-minute window. Do not modify `catalog.mjs` or add new polling behavior.

- [x] Run `node --test apps/api-go/workshop-client.test.mjs`, then Go tests (embedded asset compile) and commit/push the UI/test milestone after passing.

## Task 4: Exact-candidate verification and handoff

- [x] Freeze the implementation candidate with a full 40-hex SHA; verify the diff from the synchronized checkpoint touches only the six allowlisted implementation/test paths and approved gate documents. Run `git diff --check`.
- [x] Run `node --test apps/api-go/workshop-client.test.mjs`; run `go test ./...` from `apps/api-go`; run `python -m unittest discover -s scripts/contracts -p 'test_*.py'`. Record exact commands, exits, counts and skips. Ordinary Go test skips are not SQL acceptance.
- [x] In the coordinator-owned existing isolated R3 Go runner, execute the unchanged Python fixture harness with `AUTODATA_LIFECYCLE_TEST=1`, `AUTODATA_CATALOG_INTEGRATION_REQUIRED=1`, `AUTODATA_R3_CANDIDATE_SHA` and `AUTODATA_CATALOG_TEST_CANDIDATE_SHA` set to the exact candidate, and the pinned existing Go cache/image/private network/read-only source/artifact mounts:

```sh
python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/index-readiness-r3.xml \
  workers/ingestion-python/tests/test_catalog_api_integration.py
```

Before invoking pytest, preserve the existing coordinator `host-before.json` / `inputs.sha256.json` exact-input preparation and a clean, remote-free plain-clone checkout: `check_inputs` requires those receipts and verifies every mounted byte before/after. Do not substitute a dirty worktree. The harness owns fresh isolated `postgres:5432/lifecycle_test_<32hex>` databases and supplies `AUTODATA_CATALOG_TEST_DSN`, candidate SHA, vehicle/article/provider IDs, loopback ensure/control URLs, control token and case artifact directory; never invent or reuse a production DSN. Retain eight non-skipped provider/root outcomes, the existing single-root Go JSON event contract plus `go-measurement.json`/log receipts showing every named matrix case and its expected/observed full tuple executed in the plain cold-root helper for both providers, original invariant receipts and exact-SHA input hashes. Existing `r3Setup` skips without required mode; a skipped/absent matrix fails this task. If the owned runtime is unavailable, record acceptance blocked rather than broadening files or claiming SQL verification.
- [x] Obtain independent review of the full implementation SHA and read back synchronized Issue/Project completion updates; record actual evidence in this docs-only completion milestone. Independent review of this committed documentation checkpoint remains required before integration. No production/provider/payment outcome follows from fixture success.

## Modern Web Guidance

I searched “poll asynchronous status” and checked the guide catalog. No description directly covers bounded collection polling/readiness state transitions, so no unrelated guide applies. Existing abort/generation and polling helper behavior remain the required baseline.


### Live planning synchronization receipt (2026-11-04)

The revised technical draft received independent PASS before synchronization. Fresh read-only API readback at `2026-11-04T15:02:40.245180+00:00` verified [Issue186 detail](https://github.com/lucronn/autodata/issues/186#issuecomment-6634018122) (body SHA-256 `c1597703501cec2abb5055e120c7d7bce37692bd4c95083045d810aff5d1931d`, 2794 bytes), the complete current Issue body (SHA-256 `927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25`) and all 136 comments. Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` has Source-or-dependency text length 957 / SHA-256 `51f2da943694be8f11e86e2463fe769f92f3a1f99b7151329f1eb175ba20b510` and Status `In Progress`; its full text matches the coordinator’s post-update readback. The existing source index and predecessor references are preserved; coordinator readback confirms other fields unchanged.

Full Issue/comments/Project readback and hashes are retained at `/home/corp/autodata-evidence/index-readiness-gate-checkpoint-20261104/`; before/after Project text is retained at `/home/corp/autodata-evidence/index-readiness-project-readback.json`. The canonical record/task are now synchronized against the exact matching goal, references and six todo items. No GitHub write was performed by this architect. The next implementation base is this docs-only checkpoint’s full committed SHA, verified by canonical preflight after commit; independent committed-gate review and fresh coordinator dispatch remain required. No implementation, runtime/provider/payment evidence, merge, activation or deployment is claimed.


## Reviewed code and isolated acceptance completion (2026-11-04; tracking synchronized)

Implementation is `23a2f3b2e12c0b14b1d4989ab13a075cf1bee084` in [draft PR211](https://github.com/lucronn/autodata/pull/211), based on synchronized gate `d60121c41a680d699da575d9883f9ecf45b0fb72`. Exact-base machine preflight and independent gate review passed before implementation. The diff touches exactly the six approved production/test paths; workers, schema, commerce, contracts, payment, deployment and `catalog.mjs` were unchanged. Current-job retryability and terminal aggregation, incomplete HTTP hydration, explicit complete-only ready copy and pre-await completion-live-region clearing are implemented. Paid GET remains read-only/descriptor-only; partial links, saved articles, bounded polling and navigation/abort behavior remain covered.

Exact-code local verification: `go test ./...` from `apps/api-go` passed 155 root tests with 12 ordinary fixture skips; `node --test apps/api-go/workshop-client.test.mjs` passed 62/62 with 0 skips; `python -m unittest discover -s scripts/contracts -p 'test_*.py'` passed 19/19; six-path scope and `git diff --check` passed. Raw exact-code receipt: `/home/corp/autodata-evidence/index-readiness-unit-evidence/verification-exact-23a2f3b.json`. Independent exact-code review **PASS** was provided by the coordinator; that code reviewer did **not** independently rerun Go.

The retained runtime sequence is deliberately separate:

- RED `402fbb2b348df54d9b7dbd55496f6dcf73e3c32f`, run `index-readiness-red-9ddd89c1ed01`: all 42 tuples executed, with 10 intended readiness mismatches per provider; two cold cases failed and six other lifecycle cases passed, with 0 skips/timeouts. The original failed receipt remains intact; the short/full-ID cleanup mismatch was recovered with a separate exact-owner receipt.
- First GREEN at the final code SHA, run `index-readiness-green-0407301b80b0`: six cases and all 42 tuples passed; two warm fixtures failed before Go on SeaweedFS disk capacity (2.15% free). This attempt remains **failed**, with its raw receipt and successful owned cleanup preserved.
- Final fresh GREEN at the same code SHA, run `index-readiness-green-68fd8e922a26`: **8/8 non-skipped Python/Go cases and 42/42 tuples passed** in 76.36s; supervisor exit 0/status passed/failures empty. The run used a clean remote-free clone, exact mounted-input hashes, eight isolated PostgreSQL databases, real fixture S3/NATS/HTTP probes, source/job/projection/counter measurements, and successful bounded owned cleanup. It retained backend-final inspect/log, removed only its build backend before fixtures, and used a private test-only Compose override binding only SeaweedFS `/data` to a fresh owned `/home` directory with at least 12 GiB headroom; the actual mount, config-only delta and cleanup interpreter were verified. No application source changed between GREEN attempts.

Final receipt: `/home/corp/autodata-evidence/index-readiness-green-68fd8e922a26/artifacts/acceptance-result.json`, SHA-256 `a677ebea4d8234d222c2d71065b0bf9337b2fbef0e51ed23f2b0eef5a967209a`. Independent raw-evidence audit **PASS**: `/home/corp/autodata-evidence/index-readiness-green-independent-audit-68fd8e922a26.json`, SHA-256 `9e8bb8769123928682401fab64f899924b7d168775dd317d09031eb2843bd61b`. Storage cleanup receipt SHA-256: `355598ffef4fcc101245fbe6bc72169a1e261b6e2db23dd1cf68d78a60fd9a44`. Final supervisor SHA-256: `e4a8f054f85207b5dc8e83155cf1b39e67ffcbc467d8f0a44eb08bc86a0e26b9`.

Completion tracking is synchronized from the coordinator's serialized readback: [Issue186 completion detail](https://github.com/lucronn/autodata/issues/186#issuecomment-6634845885), body SHA-256 `9acb67f385d4f0c038afa12917c76d5799de7b9068e70cd4f869158bd548294b`; final Project8 Source SHA-256 `9c99e5508b2cf825dd8919a125962cb3a4c12df741df53722740de57f535e9b4` (476 bytes), with other Project fields unchanged. The exact predecessor Source SHA-256 `46b8e75e2a62481d106c77c1b6677dd8c1f865ef53b5377c0d31950280c68a7b`, its full text and all 138 predecessor comment hashes remain preserved in the linked detail and durable `/home/corp/autodata-evidence/index-readiness-completion-tracking-before.json` and `index-readiness-completion-tracking-readback.json`; the wording correction is retained in `index-readiness-completion-project-correction.json`. The earlier planning receipt remains historical evidence. No GitHub write was performed by this documentation agent. The full-SHA preflight receipt for this docs-only checkpoint is retained externally after commit; independent committed-checkpoint review remains required before integration. All release authorities remain false and `release_state` remains `unverified`; final180, stateful release-readiness review, live provider rehearsal/payment, PG/Stage1A/M2A/publisher/release, activation and deployment gates remain separate/open. The result establishes isolated fixture behavior only.
