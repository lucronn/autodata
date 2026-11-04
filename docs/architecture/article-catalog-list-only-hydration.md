# Article catalog discovery and selected content

The November 2026 lifecycle replaces synchronous article hydration with durable
SQL scheduling. `ensure_catalog_hydration` routes `scope=articles` and
`scope=article` through `_ensure_lifecycle_catalog` before any process cache.
Other selector scopes retain their existing behavior.

A catalog ensure proves the requested vehicle/configuration and creates or
reuses one `catalog_index` job independently for Bankone and Banktwo. Workers
resolve each bank's opaque vehicle reference, capture its index and store
list-only descriptors. Index work never fetches article bodies or assets.
A selected article ensure requires its canonical UUID or an explicitly proven
legacy alias. Vehicle, configuration and any supplied bank/opaque references
must match exactly. Ambiguous bindings return `409
ARTICLE_BINDING_REVIEW_REQUIRED`; selectors never widen scope or guess from
article titles.

The selected ensure acknowledgment has exactly `job_id`, `state`,
`canonical_article_id`, `source_revision_id` and `retry_after_seconds`. Pending
work returns 202; readable source or completed content returns 200; review or
exhausted work returns 409. SQL scheduling failure returns 503
`ARTICLE_SCHEDULING_UNAVAILABLE`. The handler performs no source, asset or model
IO. Repeated complete ensures do not mutate jobs or schedule new work.

The dedicated `scripts/dev/article_worker.py` process claims jobs with PostgreSQL
row locks and expiring fencing tokens. Source capture persists immutable raw
snapshots, ordered source projections, evidence and observations before model
work. Reads remain explicit source content until the matching canonical rewrite
publishes. A failed required source upload retains the previous publication.
When changed source is captured, its source projection replaces the older
canonical projection until that new source's transformation publishes.

The reader contract is `catalog_article_current`: canonical identity, source
identity, content origin, availability, processing/retry state and ordered
projections come from SQL. R3 owns the public Go detail/ensure integration and
browser rendering. A warm public detail read must read SQL directly without
calling the ensure service; R2's direct ensure tests prove zero newly scheduled
jobs and zero bank/asset/model calls.

Catalog acknowledgment aggregation returns 202 while any provider has active or
retryable work, 409 when no active work remains and any provider needs review or
has exhausted its budget, and 200 only when both durable jobs completed. Each
provider's job/retry row remains visible, so partial coverage is not erased.
The entire SQL scheduling operation shares a monotonic budget inside two
seconds, including repeated connections and provider lock waits. Each statement
gets the remaining server timeout; expiry cancels active connections and
prevents late connections from executing SQL or late transactions from starting
commit. Timeout rolls back all job writes in that transaction and returns 503.

Offline compatibility mapping is `scripts/dev/backfill_article_lifecycle.py`.
Its default dry-run reports mapped/already-mapped/quarantined/unresolved counts.
`--apply` requires exact provider/vehicle/configuration/opaque article and body
references plus an approved extraction-evidence record bound to the actual
snapshot. Equal titles and numeric-looking references prove nothing. Invalid
mappings create review items; existing legacy job histories remain untouched.

The previous September 2026 synchronous behavior and issue #113 are historical;
current lifecycle work is tracked in issue #186 and the canonical lifecycle plan.


## Paid index readiness correction (2026-11-04; historical synchronized planning checkpoint)

Issue: https://github.com/lucronn/autodata/issues/186; Project: https://github.com/users/lucronn/projects/8.
Plan: [workshop-index-readiness](../superpowers/plans/2026-11-04-workshop-index-readiness.md); record: `docs/agents/records/2026-11-04-workshop-index-readiness.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-index-readiness.json`. Inspected candidate: `e5fed171bb36fdb759c592cbcd0e15aea5490c97`. Live tracking readback is verified in the receipt below; committed checkpoint, full-SHA preflight and independent committed-gate review remain required before code edits.

The planned correction derives Retryable from the current source job only: failed, retryable=true, retry_count<max_attempts, including future backoff. Terminal current jobs and terminal scopes are failures; a terminal job with stale running scope remains terminal. Aggregate precedence is both current provider generations complete, then any pending/processing current job, then failure, then pending. Total=2, Processed=current completed generations, Percent=Processed*50. Active progress can coexist with retryable work in another bank.

Paid article GET remains a read of descriptors/progress and never schedules preparation. Incomplete pending/running/retryable-failed responses hydrate; terminal failure does not; complete always suppresses hydration. The browser clears the previous completion live-region text at the start of each current index load, then announces ready only for complete=true, including a completed empty index. Incomplete results retain usable partial rows; an available saved article opens immediately. Terminal copy never promises provider restart; check-again means another read. The existing one-minute collection poll and abort/navigation guards remain intact.

This draft does not establish implemented behavior, successful fixture acceptance, provider rehearsal or production readiness. The plan carries the concrete todo and exact six implementation/test paths; no worker/schema/commerce/polling-helper changes are authorized.


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
