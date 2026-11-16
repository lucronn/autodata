# Workshop search/current legacy renderer parity repair

Issue: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8
Draft PR: https://github.com/lucronn/autodata/pull/394

## Decision and boundaries

Repair the proven visible-body search defect in draft394 exact39c3523fca2ca80ba1e8c83626ef3c848b8921eb. Integrate protected4246264a881382676927e22adad0a1d240f03268 (production apps/api-go tree identical to livea82b31dc8850aa3956972928b8c720969765a972) on isolated local branch codex/workshop-search-renderer-parity-20261116, worktree /home/corp/autodata-evidence/workshop-search-renderer-parity-20261116, device1792. Do not push, edit PR, merge protected master, deploy, run services/browser/provider/Stripe/SQL or allocate physical build artifacts. PR stays draft; guarded paid/runtime acceptance remains blocking.

Read-only three-way merge of baseb435/master424/head39c shows no textual conflicts. Both-changed paths are workshop/app.mjs and workshop-client.test.mjs; preserve both a82 local-image auth-mode calls/tests and draft search generation/empty pending/error/access handling. Protected catalog.mjs contains current intro/legacy logic and is not modified by this repair.

## Proven defect and minimal repair

Draft catalog_search.go50–94 drops all body text with usable steps. Current catalog.mjs153–203 renders legacy introduction blocks alongside usable steps. An unrelated compatibility body is retained rather than hidden; exact numbered/flat/instructions-only step replays are deduplicated only when their text already occurs in the displayed structured steps. Therefore always including no-document body text alongside usable steps searches visible introduction/body words or words already rendered in replayed steps. Keep a nonempty document authoritative, excluding its hidden body/legacy steps; keep IDs/locators/source metadata and paid image restrictions excluded. Do not copy the full JS layout parser into Go or change current renderer behavior.

Use a shared, independently authored fixture with no-document introduction+steps, flat and numbered/instructions-only replays, unrelated numbered/body text, partly empty steps and document-authoritative hidden-body negatives. Cross-check expected rendered text with the existing actual app/renderer Node harness and Go search outcomes. Red-first Go cases must fail against the current draft. Correct the stale test that currently labels visible coolant body text hidden. Include visible whitespace/callout/punctuation and hidden document/body cases to bound behavior. Add explicit paid URL-only opaque-image exclusion regression; no production image matching change. Current real local Postgres index is metadata-only and detail signs from storage keys already accepted by search; opaque-URL-only parity is potential DTO helper gap, not demonstrated live defect, so leave implementation unchanged.

## Verification/resources

Only offloaded code/tests/logs/temp/caches. Reuse accepted attempt2 offloaded Go cache through a fresh isolated read-through hardlink-free copy only if needed and feasible; prefer Go test single-file semantic fixture to avoid broad builds until capacity is checked. Full package tests may use existing cache read/write only if no active Go job and root permits provenance change; otherwise unique offloaded cache with <=512MiB incremental allocation, scratch<=128MiB and offload free>=1GiB, monitor and terminate on bound failure. No output under physical home or source release package. Go offline: GOPROXY=off/GOSUMDB=off/GOTOOLCHAIN=local/GOFLAGS=-mod=readonly/CGO_ENABLED=0/GOMAXPROCS=2/GOMEMLIMIT=1GiB/GOTELEMETRY=off, GOMODCACHE existing read-only historical host module cache; no download/build image/service. Node tests pure harness only, no Chromium.

Required: red-first focused semantic fixtures, focused/full relevant Go and Workshop Node suites if offline dependencies/admission permit, four lifecycle OpenAPI contract tests, syntax/diff checks, exact source/tree/diff and skipped acceptance inventory. Do not claim guarded Postgres execution from ordinary Go tests. Twelve-case two-provider guarded paid fixture remains unrun; paid-search source/canonical/revision/rights/takedown/exact-grant/metadata-only HTTP evidence, current exact-head CI and independent review remain merge blockers. Authored local M2A browser acceptance is separately held and cannot establish paid-reader search. Anonymous public canary establishes neither.

## Todo

- Synchronize this plan, Issue393/Project8, canonical verification document and JSON record; commit local checkpoint and pass pinned machine preflight before implementation. No push per root instruction.
- Integrate protected424 without losing a82 renderer/image behavior or draft search flow; author independent cross-renderer fixtures and red-first Go tests.
- Implement minimal legacy-body search fix only; preserve document authority, paid image URL/token rejection and existing auth/commerce boundaries.
- Run bounded offline verification, record exact local head/tree/changed files and actual acceptance gaps; leave draft PR unchanged/unpushed for root review.
