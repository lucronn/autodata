# Workshop route state contract

Goal: Restore vehicle selector and article-search state from the current URL so direct article links, browser history, and library vehicle navigation cannot reuse another vehicle’s choices or query.

Issue: https://github.com/lucronn/autodata/issues/446

Parent: https://github.com/lucronn/autodata/issues/398
Related search: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8
Canonical document: docs/architecture/workshop-route-state.md
Source base: a82b31d

## Decision

At route restoration, clear all selector rows/options with the existing populate function and restore search from q before any direct configuration/library/order branch. Hierarchical routes then repopulate the exact saved hierarchy using unchanged loadOptions. Clear vehicle and quote before branch dispatch so library/order routes cannot render a prior vehicle purchase context. A library vehicle activation clears the query and all selector options before building its direct configuration URL. Preserve explicit q on direct article links. Use existing navigation generation fences and native selectors; no new browser APIs.

## Concrete todo

- Synchronize Issue/Project/canonical docs and pass the exact committed checkpoint preflight before implementation.
- Add production-function regressions for direct configuration/article links with and without q, library routes and library vehicle activation, partial hierarchy and full saved hierarchy restoration; include stale prior selector options/query/context.
- Reset route-owned selector/search/context state and clear library vehicle search without changing article access, checkout, order polling, API or source data.
- Run focused failing/green regressions, complete Workshop client/demo tests, syntax and diff checks; commit/push evidence for coordinator review.
- Hold deployment and external authenticated/provider/Stripe calls; coordinator owns integration and public runtime.

Implementation allowlist: apps/api-go/workshop/app.mjs and apps/api-go/workshop-client.test.mjs, plus the task’s canonical docs/record. No runtime mutation or deployment.

Planning checkpoint synchronized with Issue #446 / Project #8 before implementation. Runtime and deployment remain coordinator-owned.

## Implementation checkpoint

Pre-implementation gate passed at `2c90eff82a95b6ee58e68f42b0100d62c3dee45d`. The route reset and regressions are implemented; the complete Workshop client/demo suite passes 314 tests. See `docs/verification/2026-11-16-workshop-route-state.md`. Coordinator review/integration and runtime acceptance remain pending.
