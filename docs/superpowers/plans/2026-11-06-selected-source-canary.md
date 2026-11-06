# Selected-page source canary execution plan

> **For agentic workers:** Execute inline using superpowers:executing-plans only after the synchronized full-SHA gate and separate coordinator dispatch. This checkpoint changes documentation only; it does not dispatch a source run.

**Goal:** Capture one frozen source article per bank from its complete authentic index page, including a nonterminal page, while retaining selected-only partial scope and zero model requests or canonical publication.

**Architecture:** Retain the existing e4af provider-bound source capture and fenced persistence. Change only the private driver's index-selection prerequisite: a fully read authentic page containing the frozen descriptor is sufficient even when the page is nonterminal. Preserve authentic page bytes and selected-only partial provider scope.

**Tech Stack:** Existing Python ingestion runtime, PostgreSQL17 and source S3 storage; no dependency or product change.

**Spec:** docs/verification/2026-11-06-selected-source-canary.md. Canonical gate: docs/agents/pre-implementation-gate.md.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Branch: codex/selected-source-canary-gate. Planning parent: 4513c387c900add7138330555ccfca92f74b9894. Product remains e4af8621c12352e465ee28e87a67f78e67ab9091.

## Scope and prior evidence

This successor supersedes only the requirement to reach a terminal article-index page in docs/superpowers/plans/2026-11-06-serving-source-canary.md (merged gate e54f26f8add07f7adf073a61e0b8a5ee9617d4a1). All other enrollment, runtime, bounds, persistence, preservation and execution controls in that plan remain mandatory. Only this plan, its verification document and its new record change at this checkpoint. No application, schema, source connector, runtime, model, infrastructure or existing run artifact changes.

Private prior result: /home/corp/autodata-evidence/serving-source-canary-20261106/execution-03-correction01/result.json. It remains a failed bounded attempt: Bankone made five HTTP200 calls (one resolution and four index pages); page1 contained the frozen descriptor, all four pages were nonterminal; no article body requests or serving writes occurred; Banktwo was not attempted. Protected57-table hashes and all preexisting source rows were unchanged. Its failed completion audit is not relabeled as success. Preserve that attempt, execution-02 and the stopped apex404 preflight without modification.

## Selection rule and unchanged constraints

- Fresh resolution must bind exactly the previously frozen provider, vehicle and configuration. Keep Bankone article2e9b300d-99e9-58ed-a443-c57967932d61 / vehicle1d34da00-6238-5d2f-beb5-df6a74299e98 / configuration null; Banktwo article036e122a-72bc-5610-bf35-40108f0e9039 / vehicle5f50c31d-750c-53d9-80bd-36bd97d18ccf / configuration91de3edf-192d-5ab8-9067-9f16e56f1478. Frozen private enrollment SHA256 remains319cc94d8f73ce42476d18aad0d82182c23f7536b24f25dad9f9ae463848a088. No substitution or new article enrollment.
- Read and validate each entire authentic index page before deciding. The page must contain exactly one descriptor matching the frozen provider-scoped article reference and enrolled applicability/context. Duplicate or conflicting matches, invalid envelope or applicability ambiguity fail closed. Preserve descriptor identity/provenance checks and record legitimate revision drift; titles never establish identity.
- Once a page qualifies, stop index traversal immediately, including if complete=false and next_cursor is present. Preserve the entire original page bytes, response hash, observed complete flag, next_cursor and resolution evidence privately; do not filter, truncate, rewrite or relabel the upstream envelope. Persist only the frozen selected descriptor. This proves page membership only, not global uniqueness or completeness across unvisited pages.
- A nonterminal fourth page is no longer itself failure if that full page qualifies. No match after four pages, or terminal traversal without a match, remains failure. No fifth page, follow-up enumeration or alternative article is allowed.
- Keep sequential banks, one HTTP request in flight, zero retries/redirects; at most16 actual source HTTP calls and4 index pages per bank; at most4MiB per response and32MiB per bank;10s socket timeout; at least1s between starts;90s hard bank bound including DB/S3/verification/drain/cleanup,180s independent whole-run watchdog. Retain process-group termination/reaping and bounded failure-safe audit; stop if quiescence cannot be proved. Existing30s capture deadline and serialized source asset calls remain.
- Actual serving DB remains autodata; source runtime autodata-ingestion-candidate-e4af862 and read-only mount must match e4af exactly. Correct preview origin is https://autodata.cars.tk. Require ready200 and purchase enabled=false, exact backup/driver/enrollment hashes, actual seven-table source inventory, zero active source claims and exclusive coordinator source slot before requests or writes. Stop on drift; no restart or queue clearing.
- Persist only selected authentic resolution/index snapshots, selected descriptor, source artifacts/blobs, selected scope, fenced job/source revision/observation. Provider scopes must remain status=partial, error_code=SELECTED_SOURCE_CANARY, row_count=1, generation=0, completed_generation=0. Never mark the catalog complete, retire unseen descriptors or infer coverage from a selected page.
- Existing direct capture_source_article/store_captured_source path only; reread the lease after store and terminally fail the selected job SOURCE_CANARY_ONLY without retry. No model construction/request, normalization, rewrite attempt, review, canonical revision/publication, payment, grant, session or entitlement change. Existing offline bank_canary_capture CLI stays unchanged and unused. Unavailable media stays unavailable; body and media completeness are separate.
- Private originals, source prose, opaque cursors/references, credentials and pg_dump remain under0700 directories/0600 files. Retain all attempts and residual rows; no automatic retry, cleanup or restore. A prior valid backup must be reverified, never treated as authority to restore serving data.

## Concrete todo

- [ ] Synchronize the successor plan, canonical verification and record with Issue186/Project8; commit/push the docs-only checkpoint and pass exact full-SHA preflight.
- [ ] Revise only the private driver selection predicate, preserve the entire authentic selected page and next_cursor, add offline terminal/nonterminal/missing/duplicate tests, and obtain independent exact-hash review before fresh execution dispatch.
- [ ] Revalidate unchanged frozen enrollment, e4af product/runtime, serving DB, exclusive source slot, bounded driver and backup; stop on drift before requests or writes.
- [ ] After fresh dispatch, capture at most one frozen article per bank, retain partial selected-only scopes, verify source fallback/resource hashes and all preservation checks, and report sanitized result without catalog/paid/canonical acceptance.

## Review and execution checkpoints

1. Coordinator synchronizes the exact goal/todo/paths in Issue186/Project8 and returns the saved comment URL/readback UTC. Commit/push these three docs. Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-selected-source-canary.json --base-sha FULL_CHECKPOINT_SHA`; require exit0, status synchronized, errors[]. Pin the actual full SHA externally.
2. Only after coordinator dispatch for private preparation, change the private driver selection predicate and its offline tests; no checked-in product/run/model edit. Test a complete authentic page with one match and next_cursor (success, no next-page call); terminal page with one match (success); missing match within four pages (failure); duplicate/conflicting match on a full page (failure). Verify raw selected page/complete/next_cursor preservation, partial scope fields and all existing deadline/quiescence/preservation checks. Record test results and new driver SHA256; obtain independent rereview and coordinator exact-hash approval. Do not reuse prior driver approval or execution authorization.
3. Fresh source-only execution requires a separate explicit coordinator dispatch for this checkpoint and new driver hash. Use fresh exclusive private/container driver and evidence paths. Revalidate all identities, claims, preview state, backup and hashes; stream exact reviewed bytes to writable tmpfs0600 and independently verify SHA before a single bounded attempt. No retry on failure.
4. On success verify exactly two selected source revisions, source-origin catalog_article_current views with nonempty bodies and null canonical revisions, source pointer binding and manifest hash/byte reads. Report resource availability separately. Require terminal SOURCE_CANARY_ONLY jobs, valid partial scope fields, unchanged all protected tables and preexisting source rows, zero model/rewrite/review/publication/commerce changes and zero active claims. On failure retain bounded final audit, raw evidence and exact residual rows; report incompleteness honestly. Database view proof is not authenticated browser/paid access proof.
5. Save sanitized result with product/checkpoint/driver/enrollment/backup hashes, per-bank request counts/statuses, selected page position/complete/next_cursor-presence, body/resource/fallback results and preservation hashes/counts. Synchronize the exact result via coordinator. No full catalog, canonical, paid or production acceptance follows.

## Tracking synchronization

Status: synchronized/read back by coordinator at 2026-11-06T07:37:06Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6679765071; Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4, Release hotfix reference field contains the issue link (length997). Exact checkpoint SHA and preflight remain to be sealed externally. No implementation or source execution dispatched by this document.
