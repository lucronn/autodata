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

- [ ] The existing protected article-index route accepts an optional bounded
  `q` search. An empty query retains the current metadata-only index behavior.
- [ ] After the existing exact-configuration grant check, a nonempty query can
  match words in the current readable document, or legacy body/steps when no
  document is rendered, and returns metadata descriptors only—no text snippets,
  document, steps, images, source review, or provider identifiers.
- [ ] Current lifecycle rights, quarantine, takedown, and revision selection
  remain in force; wrong-configuration, unpurchased, and revoked requests
  return the existing protected-route error behavior.
- [ ] The Workshop search box requests protected content search for nonempty
  queries, ignores stale responses after typing or vehicle changes, and never
  fetches every article detail to emulate search in the browser.
- [ ] Pending/incomplete index results are not presented as definitive no-match;
  result counts and status remain understandable to keyboard and screen-reader
  users.
- [ ] Red-first API and actual Workshop-flow tests cover a content-only match,
  title match, wrong vehicle, denied/revoked grant, lifecycle exclusion, stale
  response, and incomplete index.
- [ ] Full relevant suites, exact-head independent review, current CI, and live
  branch protection pass before merge. Live owned-vehicle purchase/search
  acceptance is separately required once the origin is healthy.

This is Workshop app work, not an architecture or database-schema redesign.
It does not change checkout, price, grant issuance, production service state,
DNS, or live traffic. The public Workshop origin still returns 502, tracked in
[Issue #391](https://github.com/lucronn/autodata/issues/391); unit tests alone
cannot establish paid release readiness.

Plan: [2026-11-10-workshop-owned-article-content-search](../superpowers/plans/2026-11-10-workshop-owned-article-content-search.md).
