# Ephemeral Multi-Component Procedure Composition

**Goal:** Return a unified, vehicle-matched procedure for a multi-component request using already normalized individual articles as the source of truth.

**Tracked delivery:** [Issue #110](https://github.com/lucronn/autodata/issues/110), [AutoData Portfolio Project](https://github.com/users/lucronn/projects/8), the [composition plan](../superpowers/plans/2026-09-19-mercury2-overlap-procedure-composition.md), the [provider-qualified hydration follow-up](../superpowers/plans/2026-10-03-provider-qualified-composition-hydration.md), and the [procedure-content quality gate](../superpowers/plans/2026-10-03-procedure-content-quality-gate.md).

## Provider integrity release follow-up

The [provider integrity plan](../superpowers/plans/2026-10-03-provider-integrity-follow-up.md) is tracked in Issue #110 and Project #8. Todo: qualify article identity by provider through stored reads and composition; preserve provider failure and missing scopes; test same numeric article ID from two sources; prove five fresh cold/warm vehicle requests before closure. A partial provider response must not be labeled complete.

## Data lifecycle

AutoData stores each vehicle-matched individual source article, its original source payload, normalized text, source/evidence references, and locally managed images. A composition request resolves the requested components to those individual records. If a required article is absent, AutoData retrieves and ingests that individual article through the catalog/source path, then uses the persisted normalized record. It must not repeat a provider detail call when that record is already available.
When catalog traversal has multiple revisions/rows for one article identity,
reads must prefer the row with usable normalized body/steps over a later
list-only row; indexing the same article again must not mask already ingested
content or trigger another provider detail request.

Provider vehicle IDs are source-scoped: AutoDBone IDs may only be sent to the
AutoDBone facade, and AutoDBtwo car IDs may only be sent to AutoDBtwo. A
composition request resolves provider mappings independently from the
canonical vehicle identity. On a cold article miss, it searches current
provider catalogs and hydrates only selected component details through their
own connector contracts. A failure or miss from one source must not prevent a
valid selected article from the other source from being used. Never infer a
provider identity from an unqualified numeric ID.

Mercury-2 receives the selected normalized individual articles and returns one unified procedure in the synchronous API response. The composed result is ephemeral: do not insert it into the article/catalog tables, derived-revision storage, review queue, reusable cache, or source-ingestion records. Labor is disabled for this work; it must not gate retrieval or composition, and composition must not fabricate labor values.

Cache readiness is content-based, not status-label-based. Each selected
individual source article must provide meaningful source-authored procedure
instructions for its requested component. Headings, section labels, metadata,
and empty steps do not make an article complete. Apply this validation when
ingesting, persisting, reading cached rows, composing, and projecting article
responses. Repair weak legacy rows from their immutable original source when
possible, otherwise fetch only that selected article; if usable content remains
unavailable, return an explicit incomplete/source failure rather than a ready
procedure. Preserve the source original and lineage, localize images, and expose
images through opaque same-origin routes. The combined procedure stays
ephemeral.

## Composition contract

- Scope every input article and output to the same canonical vehicle/configuration.
- Preserve every required source operation and its source article/evidence references; do not invent repair facts, specifications, warnings, tools, or images.
- Consolidate only clearly equivalent shared work, and retain traceability from a unified step to every source step it represents.
- Keep the order within each individual source procedure intact. The unified ordering may combine component procedures only where explicit prerequisite relationships support it; when sources conflict or cannot be safely reconciled, retain the source-specific order and surface the conflict rather than guessing.
- Use deterministic source-backed composition as a usable fallback when Mercury-2 is disabled, unavailable, times out, or returns invalid output. A provider failure must not become an empty procedure when usable normalized source articles exist.
- Return image references only from the supplied, locally stored image registry. Never fetch a source URL from the browser or synthesize an image.
- Return a clearly bounded error when a required source article is unavailable; do not silently claim completeness.

## API and persistence boundary

The public job-plan/composition API may return a unified procedure and composition diagnostics for the request. It must not expose or invoke the dashboard chatbot as a dependency. Persistence is limited to individual source-backed article ingestion and existing individual-article normalization. No composed-procedure write, derived article identity, derived response cache, or post-composition review workflow is allowed.

## Acceptance

Tests prove that a request composes normalized records without upstream calls when all requested individual articles exist; missing individual articles are ingested once and become reusable; the composition output is never persisted or cached; invalid/unavailable Mercury-2 falls back to a non-empty deterministic procedure when source data exists; and each output step/image maps to supplied source records. Exercise both one-article and multi-article requests through the public API/worker boundary. No labor behavior is part of acceptance.
