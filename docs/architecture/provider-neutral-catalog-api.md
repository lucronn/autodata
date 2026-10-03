# Provider-neutral catalog API

AutoData is the durable catalog service for external applications. A client
selects a year, make, model, engine/base/trim, and article through versioned
API resources. AutoData serves stored canonical records and hydrates missing or
incomplete records from AutoAPI and AutoAPItwo.

The public contract is published at `/openapi.json`; `/swagger/` serves the
same-origin interactive Swagger UI with prefilled examples for the full
cascade.

The source boundary keeps each provider's raw response and provenance. The
normalization boundary converts provider fields into canonical vehicle,
configuration, article, step, and image records. The public API returns only
provider-neutral projections. A source list is not treated as complete until
the adapter proves its expected scope was enumerated; an incomplete record is
usable only as an explicit incomplete state that can trigger hydration.

Article detail is normalized once. Its original provider content remains
immutable, normalized steps retain source order, optional wording rewrite is
phrase-only, and served images reference local stored objects. Labor and
combined procedures are not part of this API.

The active product path has no chatbot routes or UI, chat event streams, chat
worker activation, or chat-scoped guide URLs. Legacy chat implementation must
not be registered, served, or started by the default API, dashboard, worker, or
Compose configuration. Catalog browsing and article viewing use the direct
provider-neutral API and remain available without a chat runtime.
