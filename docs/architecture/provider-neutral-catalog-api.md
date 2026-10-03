# Provider-neutral catalog API

AutoData is the durable catalog service for external applications. A client
selects a year, make, model, engine/base/trim, and article through versioned
API resources. AutoData serves stored canonical records and hydrates missing or
incomplete records from AutoAPI and AutoAPItwo.

The public contract is published at `/openapi.json`; `/swagger/` serves the
same-origin interactive Swagger UI with prefilled examples for the full
cascade.

The API binary embeds the dashboard, Workshop, OpenAPI JSON/YAML, Swagger HTML,
and Swagger UI assets. The API container build must copy every matching asset
into its compile stage before `go build`; verify the same-origin docs from the
container image, not only from a host-built binary. The packaging follow-up is
tracked in Issue #113 and
`docs/superpowers/plans/2026-10-03-swagger-container-assets.md`.

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

## OpenAPI source and image coverage

The published contract must include the stored-source review endpoint and the
opaque image-token endpoint, with their response representations and error
behavior. It must not expose the internal image storage key. This follow-up is
tracked in [Issue #113](https://github.com/lucronn/autodata/issues/113), with
[Issue #116](https://github.com/lucronn/autodata/issues/116) tracking image
path privacy, and Project #8. Plan:
`docs/superpowers/plans/2026-10-03-openapi-source-media-contract.md`.

Todo:

- Document source review JSON and HTML responses plus authentication.
- Document same-origin opaque image paths and the rejected legacy query route.
- Remove internal `storage_key` from the public image schema.
- Test that the spec contains the registered routes and passes JSON/YAML
  validation.
