# Owned-vehicle Workshop article content search

**Goal:** A signed-in consumer with a current grant can search the readable
content of articles for the selected vehicle, without putting paid article
content into the metadata-only index response or exposing another vehicle's
articles.

This is [Issue #393](https://github.com/lucronn/autodata/issues/393) in
[Project #8](https://github.com/users/lucronn/projects/8). The current Workshop
input calls `filterArticles`, which checks only title, component, and kind.
The paid index deliberately clears body, document, steps, and images before
responding. The Python ingestion query utility from PR #392 has no Workshop UI
call site and does not satisfy this feature.

Acceptance:

The exact-head review of PR #394 at `7d49e86ea1e090d88f8ca83b98a399013cf12e10`
found integration work that must be completed before this feature can merge:
the guarded twelve-case paid fixture's strict assertion names and HTTP receipt
counts still describe the pre-search probes; the embedded YAML API description
lacks `q`; and no-document search can match a compatibility body hidden when
the Workshop renders usable steps. The linked plan now includes red-first
collector/contract/renderer tests and the corresponding bounded repairs.
These are open findings, not waived gates.

- [x] The existing protected article-index route accepts an optional bounded
  `q` search. An empty query retains the current metadata-only index behavior.
- [x] After the existing exact-configuration grant check, a nonempty query can
  match words in the current readable document, or legacy body/steps when no
  document is rendered, and returns metadata descriptors only—no text snippets,
  document, steps, images, source review, or provider identifiers.
- [ ] Current lifecycle rights, quarantine, takedown, and revision selection
  remain in force; wrong-configuration, unpurchased, and revoked requests
  return the existing protected-route error behavior. The same SQL predicates
  are used and fixture assertions were added, but isolated Postgres execution
  is still pending.
- [x] The Workshop search box requests protected content search for nonempty
  queries, ignores stale responses after typing or vehicle changes, and never
  fetches every article detail to emulate search in the browser.
- [x] Pending/incomplete index results are not presented as definitive no-match;
  result counts and status remain understandable to keyboard and screen-reader
  users.
- [ ] Red-first API and actual Workshop-flow tests cover a content-only match,
  title match, wrong vehicle, denied/revoked grant, lifecycle exclusion, stale
  response, and incomplete index. Local tests pass; lifecycle fixture assertions
  still need the required guarded runtime.
- [ ] Full relevant suites, exact-head independent review, current CI, and live
  branch protection pass before merge. Live owned-vehicle purchase/search
  acceptance is separately required once the origin is healthy.

Local verification on 2026-11-10:

- `GOCACHE=/tmp/autodata-workshop-go-cache /home/corp/.local/go/bin/go test ./...`
  in `apps/api-go`: passed. The isolated paid Postgres fixture cases are skipped
  locally because their guarded runtime and DSN are absent; the new fixture
  assertions must run in the required integration gate.
- `node --test --test-reporter=tap workshop-client.test.mjs workshop-demo.test.mjs`
  in `apps/api-go`: 265 passed, 0 failed, 0 skipped. Actual search input,
  stale-query/vehicle responses, revoked-access, paid no-repay handling,
  repeated hydrating polls, completeness transitions in both directions,
  withdrawal or revision changes on index reopen, and accessible pending/error
  announcements are covered.
- `python -m unittest scripts.contracts.test_catalog_lifecycle_contract`:
  3 passed. OpenAPI now records the optional bounded `q` parameter and the
  paid grant/metadata-only behavior.
- No live browser acceptance: `https://autodata.cars.tk/workshop/` still returns
  502, tracked separately in Issue #391. No production service or payment
  setting was changed for this feature.

This is Workshop app work, not an architecture or database-schema redesign.
It does not change checkout, price, grant issuance, production service state,
DNS, or live traffic. The public Workshop origin returned 502 on 2026-11-10,
tracked in [Issue #391](https://github.com/lucronn/autodata/issues/391);
unit tests alone cannot establish paid release readiness.

Repair verification on 2026-11-11, based on planning checkpoint
`417912427b3597a7bb2cb5f303e835f3db9b7860` (preflight synchronized):

- Red-first paid inventory tests failed at the old three missing assertion keys
  and old 18/11 HTTP observation counts. The smoke collector and independent
  release parser now recognize the three new keys and 19/14 observations per
  affected provider case. The Python bridge imports the smoke collector map.
- The offline paid HTTP/scope parser mutation suites passed: 29 tests in
  435.629 seconds. The paid collector tests passed: 4 tests. These validate
  strict local receipt interpretation, not actual isolated Postgres execution.
- A red-first Go test proved that search previously matched a hidden legacy
  body when usable steps were rendered. The search fallback now mirrors the
  Workshop renderer. Full Go API tests passed in 8.586 seconds.
- Exact-head review of `6af3f5fb6f369cc51feb3984f241d15f16e89b71` found
  two further visible-text cases: a table-level image alt omitted from search
  and a legacy heading indexed despite a rendered action taking precedence.
  Both regression cases failed before the bounded Go fix and passed after it;
  the full Go API suite passed again in 8.545 seconds. The reviewer also noted
  a minor circular test oracle in the paid fixture's query-term selector; the
  guarded runtime and a fresh exact-head review remain open.
- Review of `cd4b4fce543decb0590e283c91ab05e196be72f8` found that a
  table-level image skipped by the Workshop because the same asset was already
  rendered in a cell could still contribute a hidden alt to search. A new
  red-first test uses resolvable distinct and duplicate assets with different
  alt text. Search now follows the renderer's resolved asset-ID deduplication
  for table-level images; the focused test and full Go API suite passed (8.493
  seconds). The current head still needs independent review and guarded paid
  runtime evidence before merge.
- Exact-head review of `f01a058d5d9cdf2feb073a6437e79100573d8266`
  found an integration gap: the paid Postgres search query omitted the
  current article's image list, so a visible table-level image alt could not
  resolve at the actual endpoint. A red-first store-projection test failed
  before the repair. The query now selects `c.images` into a private search
  projection while returning a metadata-only descriptor; the focused test and
  full Go API suite passed (8.581 seconds). This tests row assembly with a
  fixture row, not the guarded isolated Postgres/HTTP case.
- A red-first contract test caught served JSON/YAML OpenAPI drift. Both formats
  now parse to the same contract; four lifecycle contract tests passed.
- Workshop Node test runner reported two file-level subtests passed, zero
  failures, for `workshop-client.test.mjs` and `workshop-demo.test.mjs`.
- The guarded twelve-case paid fixture has not been run for this candidate.
  It requires an immutable candidate and the coordinator-reviewed isolated
  runtime; offline tests and ordinary CI are not substitutes. PR #394 must
  receive a new exact-head independent review and current CI and satisfy live
  branch protection before merge. Live owned-vehicle purchase/search acceptance
  remains separate. One bounded public `/readyz` probe returned 200 on this
  date, but it does not prove reboot durability or paid access; Issue #391 stays
  open.

Plan: [2026-11-10-workshop-owned-article-content-search](../superpowers/plans/2026-11-10-workshop-owned-article-content-search.md).

## 2026-11-12 integration checkpoint

After PR #400 advanced `master` to `74cc9e1e7f9cf460645c5976262fee07733066df`, the search branch required a merge. The only textual conflict was in `workshop/app.mjs`: retain the search request generation and the test-banner checkout assertion together. The automatically merged HTML retains the visible search label, initial disabled sign-in, and separate sample/test banners. This checkpoint changes neither the grant check nor the metadata-only search response.

Before the merge, the existing search branch passed the full Go API suite and Workshop Node tests. On the combined uncommitted tree, `node --test workshop-client.test.mjs workshop-demo.test.mjs` passed 277 tests with no failures or skips; full Go API tests passed; four lifecycle contract tests passed; `node --check` and `git diff --check` passed. These are code/fixture checks, not real paid-access acceptance.

The guarded twelve-case paid Postgres fixture is still unrun. Its runbook requires a coordinator-reviewed isolated R3 test image and owned Compose project; `AUTODATA_R3_TEST_IMAGE` is unset in this checkout, and the host has unrelated live and staging containers. Do not substitute the ordinary CI `go test ./...` (which skips guarded cases), reuse those containers, or claim paid fixture credit. PR #394 must remain unmerged until the isolated required-mode receipts pass, followed by current exact-head review, CI and branch protection. A bounded public check returned HTTP 530 for Workshop and `/readyz`; Issue #391 separately tracks origin durability and live acceptance.

Independent review of merge head `7c0326c4a4915875c3ec5376b759075a705f0a58` caught one important visible-text mismatch: a document image reference could contribute alt text to search even when Workshop would display only “Illustration unavailable.” A red-first Go test reproduced this for missing, unavailable, and external image assets across figure, callout, step, and table-cell references. The reviewer also noted that the paid fixture chose content terms by invoking the function under test; its queries now use independently known source, canonical, and refreshed fixture phrases, including a superseded-revision negative assertion. The isolated fixture is still required to validate that test change and the full paid flow.

Review of `8c0008ed2b182e7196c848330fc150fa2ddf4289` caught the reverse mismatch: the paid search row reads persisted images before detail signs their URLs. A second red-first test showed that a valid stored source image did not match even though detail would render it. Search now accepts either a Workshop-local media URL or a valid stored object key; the paid projection additionally checks the selected source revision's image ID, storage key, and availability, matching the detail URL-minting boundary. Missing, unavailable, and mismatched assets remain excluded. Focused Go tests passed after this repair; the guarded Postgres fixture and new exact-head review remain required.

## 2026-11-12 current-master integration

PR #394's search branch merged current `master` `8ee61de152483ec3a7708000b7c6875dbf76558c` without a textual conflict. The combined candidate before this note is `aa0239a3279417a93682c7475586c83210957d2a`. The Issue #393 planning record passed exact-base preflight at its committed checkpoint `417912427b3597a7bb2cb5f303e835f3db9b7860` and on the combined candidate. Full Go API `go test ./... -count=1` passed; Workshop Node tests passed 277/277 with no failures or skips; four lifecycle contract tests passed; `git diff origin/master...HEAD --check` passed.

The required twelve-case paid Postgres fixture remains **unrun**. The reviewed runbook requires an isolated, candidate-bound R3 runner image and owned Compose project. `AUTODATA_R3_TEST_IMAGE` is unset here. The host has unrelated live and staging containers and about 3.3 GB free on its root filesystem, while `/tmp` has less than 1 GB free. No candidate image was built, no shared Docker resource was pruned or reused, and no fixture receipt was claimed. Before merge, the exact combined candidate still needs the guarded fixture, a fresh independent exact-head review, current CI and live branch-protection checks. None of these local tests proves live licensed article search or paid access.
