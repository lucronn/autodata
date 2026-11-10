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
DNS, or live traffic. The public Workshop origin still returns 502, tracked in
[Issue #391](https://github.com/lucronn/autodata/issues/391); unit tests alone
cannot establish paid release readiness.

Plan: [2026-11-10-workshop-owned-article-content-search](../superpowers/plans/2026-11-10-workshop-owned-article-content-search.md).
