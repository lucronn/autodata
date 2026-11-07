# Provider-neutral catalog API

AutoData is the durable catalog service for external applications. A client
selects a year, make, model, engine/base/trim, and article through versioned
API resources. AutoData serves stored canonical records and hydrates missing or
incomplete records from Bankone and Banktwo.

The public contract is published at `/openapi.json`; `/swagger/` serves the
same-origin interactive Swagger UI with prefilled examples for the full
cascade.

The source boundary keeps each provider's raw response and provenance. The
normalization boundary converts provider fields into canonical vehicle,
configuration, article, step, and image records. The public API returns only
provider-neutral projections. A source list is not treated as complete until
the adapter proves its expected scope was enumerated; an incomplete record is
usable only as an explicit incomplete state that can trigger hydration.

Usable complete configuration rows already stored for a year/make/model must
remain selectable while background hydration continues. The configurations
response must not keep `hydrating: true` solely because the durable scope
marker is missing when every returned item is already complete. Tracked in
[Issue #134](https://github.com/lucronn/autodata/issues/134) and
[Project #8](https://github.com/users/lucronn/projects/8); plan:
[`2026-10-08-catalog-step5-usable-configurations.md`](../superpowers/plans/2026-10-08-catalog-step5-usable-configurations.md).

Article detail is normalized once. Its original provider content remains
immutable, normalized steps retain source order, optional wording rewrite is
phrase-only, and served images reference local stored objects. Labor and
combined procedures are not part of this API.

The active product path does not require chatbot routes, chat runtime state,
chat event streams, or chat-scoped guide URLs. Tracked in
[Issue #113](https://github.com/lucronn/autodata/issues/113) and
[Project #8](https://github.com/users/lucronn/projects/8); plan:
[`2026-10-03-disable-chat-active-path.md`](../superpowers/plans/2026-10-03-disable-chat-active-path.md).

## Source fallback lifecycle (Issue #186)

The article index reads canonical provider-scoped descriptors, including rows
without source capture. Bankone precedes Banktwo, followed by persisted source
order and canonical UUID. Eligible unmapped legacy UUIDs follow in title order.
Proven aliases resolve only within the requested vehicle/configuration;
ambiguous provider-local references fail closed. List/search never fetches,
schedules or rewrites article detail.

Detail selects document, media and revision metadata from one
`catalog_article_current` snapshot. A known cold descriptor makes a bounded
two-second durable scheduling request, then rereads PostgreSQL. Accepted pending
work yields `202`; readable stored source yields `200` throughout rewrite and
retry/review failure. Only validated canonical publication sets `complete:true`.
An acknowledgment alone cannot establish completion. Unmapped legacy detail is
source with null lifecycle identity and no polling job.

Detail/source use `Cache-Control: private, no-store`. `Retry-After` agrees with
persisted processing state. Terminal missing content returns `409`, withdrawal
`410`, unknown/wrong-scope identity `404`, and scheduling/storage outage `503`.
Provider/model diagnostic messages remain private. Index completion requires
both provider coverage rows to complete their current generation, including
successful empty enumeration. Partial/failed coverage retains usable rows.

Required Go/Python acceptance crosses actual internal HTTP, workers, PostgreSQL,
S3 and JetStream. Only the coordinator's bounded supervisor against a clean
immutable plain clone can certify its eight cases; unit tests and skipped
integration cases do not. Production identity/media revocation remains R5/R6.

## Selector-deepening traffic guard (Issue #329)

Background selector deepening admits one active traversal per ingestion HTTP
process. An occupied scope returns `already_running`; a different scope returns
`busy`, without starting or queuing another traversal. A process-wide dispatch
floor spaces actual background connector attempts by at least six seconds,
including pagination, failed attempts, adjacent runs and runs stopped by 429.
Each run allows twelve total attempts across both providers and has a
120-second deadline for dispatch and response-body reads. A 429 ends the run.

Cancellation interrupts pacing waits and prevents subsequent calls and writes.
An in-flight response is discarded after cancellation. Background body reads
use the smaller of the existing client timeout (currently 25 seconds) and the
remaining deadline; a canceled/joined timer shuts down the response socket if
body reads or chunk-framing parsing block past that deadline. urllib parses
response headers before this body guard is available. Those operations retain
the socket idle timeout, and trickled headers can exceed the total wall-clock
budget. The 120-second limit is therefore not an absolute wall-clock guarantee,
and cancellation does not immediately interrupt an in-flight HTTP operation.

Foreground selectors and articles retain their existing path. Canonical rows
and provenance already persisted remain available, and interrupted traversal
does not establish completeness. There is no durable traversal-resume
mechanism. Multiple ingestion processes require aggregate-budget review before
rollout; these tests do not establish live connector fairness. Deployment
remains outside this change. Merge is authorized after required checks and
independent review pass.

Implementation: `0acac23e4b759d2ed8060824db97c6301a61276d`.
Exact-base planning preflight at
`02be27245af55ee7d6cac4a3df2cc80bb61335fb` returned
`{"status": "synchronized", "errors": []}`. Focused local checks passed
**66 tests and 11 subtests**, with **15 skipped** for unavailable integration
prerequisites. Regression coverage includes distinct concurrent keys,
thread/provider/persistence failures, cross-run pacing, both providers' attempt
budget, cancellation, foreground isolation, and local HTTP body/framing
trickles. The final full worker suite is running in a temporary environment
with the repository-pinned Stripe 16.1.0 SDK; no live provider calls are used.
The preceding implementation `392db99df134cc2a2492cf382bf2566e9eca3e60` passed
912 tests and 142 subtests, with 239 skipped. `git diff --check` passed.

Tracking: [Issue #329](https://github.com/lucronn/autodata/issues/329),
[PR #330](https://github.com/lucronn/autodata/pull/330),
[Project #8](https://github.com/users/lucronn/projects/8),
[implementation plan](../superpowers/plans/2026-11-05-catalog-selector-pacing.md),
and [gate record](../agents/records/2026-11-05-catalog-selector-pacing.json).

Todo:
- [x] Verify the pinned planning-checkpoint preflight before implementation.
- [x] Add deterministic regression tests for single-flight, per-page pacing, budgets, cancellation and foreground isolation.
- [x] Add minimal bounded/cancelable controls to the existing selector-deepening path, preserving rows and completeness semantics.
- [ ] Run final full ingestion tests and record exact-SHA evidence.
- [ ] Synchronize final evidence in GitHub; merge after required checks/review, without deploying.


## Sparse selector completeness repair (2026-11-06)

Planning: `docs/superpowers/plans/2026-11-06-catalog-scope-completeness.md`; synchronized record: `docs/agents/records/2026-11-06-catalog-scope-completeness.json`. Issue https://github.com/lucronn/autodata/issues/186 and Project https://github.com/users/lucronn/projects/8 track the same goal: persist sparse make/model selectors and require all-provider completeness, healing legacy partial scopes through bounded catalog GETs.

Concrete todo: add failing sparse/provider/legacy regressions; migrate selector_rows and completion_version; persist selector rows atomically with completeness; union scoped API reads; retain existing single-flight/replay bounds; verify and push a reviewable PR. Deployment order: connector fix, migration, worker/API restart, then affected-scope GET healing. No fleet crawl or production action is part of this implementation.
