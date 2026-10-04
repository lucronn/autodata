# Provider-neutral catalog API and non-chat procedure access

Issue: https://github.com/lucronn/autodata/issues/113
Project: https://github.com/users/lucronn/projects/8
Canonical repository document:
- `docs/architecture/provider-neutral-catalog-api.md`
- `docs/agents/pre-implementation-gate.md`

## Goal

Make AutoData a durable provider-neutral catalog service consumed by external
applications. The public flow is years, makes, models, engine/base/trim,
vehicle article catalog, and normalized article detail. AutoData reads its own
database first and retrieves missing or incomplete data from AutoAPI and
AutoAPItwo only when needed.

## Rules

1. Provider adapters translate both sources into canonical AutoData records.
2. Raw responses from both providers are retained with source, URI, version,
   hash, and retrieval metadata.
3. Catalog rows are published only when completeness is proven; incomplete
   rows remain explicitly incomplete and trigger bounded hydration.
4. Article detail is normalized once, keeps source step order, retains the
   original article, and uses local image references.
5. Public responses expose stable provider-neutral IDs and versioned DTOs;
   they never expose database columns or provider-specific shapes.
6. Chat routes, chat UI, chat worker activation, and chat-scoped artifacts are
   removed from the active product path after direct catalog/article tests pass.
7. Labor and combined-procedure persistence are out of scope.

## Concrete todo

- Add a versioned public catalog API for the cascade and normalized articles.
- Add source-complete catalog hydration and raw-response provenance for both providers.
- Extract article hydration from chat orchestration into a reusable catalog service.
- Enforce article normalization, fixed order, immutable originals, and local images.
- Replace the dashboard chat flow with direct catalog/article browsing and disable chat runtime activation.
- Add contract, persistence, source, and live cascade tests; verify no provider call occurs for complete cached data.

## Acceptance

- A third-party client can complete the full cascade without using chat routes.
- Missing makes, models, configurations, or article indexes trigger bounded source ingestion and then return catalog data.
- A missing article triggers one source hydration, stores its normalized form and original, and subsequent reads are database-only.
- AutoAPI and AutoAPItwo contributions merge into one canonical record with both provenance links.
- Chat is absent from the active dashboard and default worker/API path.
