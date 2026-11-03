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
