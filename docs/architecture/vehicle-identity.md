# Provider-neutral vehicle identity

**Issue:** https://github.com/lucronn/autodata/issues/104  
**Project:** https://github.com/users/lucronn/projects/8  
**Plan:** [2026-09-18 provider-neutral vehicle identity plan](../superpowers/plans/2026-09-18-provider-neutral-vehicle-identity.md)

## Purpose

AutoData must accept natural-language vehicle descriptions such as `99
Silverado 1500 2WD 5.3L`, resolve them to a stable internal vehicle identity,
and use source-specific identifiers only at the provider boundary. This keeps
procedures, quotes, cache keys, entitlements, and revisions stable when a
source changes naming conventions or when a second source is added.

The canonical identity is an AutoData-owned UUID backed by the existing
`vehicles`, `vehicle_identity_bases`, `vehicle_configurations`, and
`vehicle_aliases` graph. Provider identifiers are typed, provenance-bound
mapping rows. They are never substituted for the AutoData UUID.

## Identity layers

```text
Natural-language query
        |
        v
Canonical observation: year / make / model / body / drivetrain / engine / region
        |
        +--> local aliases and provider mappings
        |       |
        |       +--> verified AutoData UUID + provider lookup identifiers
        |
        +--> bounded provider search on a cache miss
                    |
                    +--> candidate normalization and deterministic scoring
                              |
                              +--> verified mapping or pending ambiguity
```

The AutoData UUID identifies the canonical vehicle configuration. A provider
mapping identifies an external record and includes `provider`, `entity_type`,
`provider_id`, provider label, source snapshot, extraction evidence, raw
payload, confidence, and resolution status. A single canonical configuration
may have mappings to several providers and several provider records may share
an ACES taxonomy identifier.

## AutoAPITwo and ACES policy

AutoAPITwo `carid` is a source-content key used to fetch that provider's
vehicle-specific search and article content. It is not an AutoData identity.
ACES vehicle IDs, ACES engine IDs, and ACES vehicle-to-engine-configuration
IDs are taxonomy or configuration references. The live API demonstrates that
an ACES engine ID can return thousands of source vehicle rows and that an ACES
VEC ID can still return more than one row. These identifiers are therefore
stored as one-to-many external mappings and never as a unique primary key for
the vehicle.

For example, the AutoAPITwo search result for the acceptance query can expose
source car ID `34218`, provider make `Chevy Truck`, model `C 1500 Truck 2WD`,
and engine `V8-5.3L VIN T`. The resolver normalizes those provider labels to
the canonical observation `1999 Chevrolet Silverado 1500 2WD 5.3L`, retains
the provider labels and ACES IDs as evidence, and associates the row with an
AutoData UUID. A later equivalent query reuses that mapping rather than
calling the provider again.

AutoAPITwo and AutoAPI/MOTOR identifiers are not interchangeable. The
provider name and source namespace are mandatory on every mapping and every
downstream lookup.

## Resolution rules

1. Parse the natural-language request into a canonical observation, retaining
   missing fields and aliases rather than inventing them.
2. Look up exact canonical aliases and verified provider mappings locally.
3. On a miss, call the bounded provider search with the normalized YMME and
   supplied drivetrain/engine details. Preserve the query and source
   watermark.
4. Normalize provider labels using explicit alias rules. Provider-specific
   labels such as `Chevy Truck` and `C 1500 Truck 2WD` are translation inputs,
   not consumer-facing canonical names.
5. Score year, make, model family, drivetrain, body/trim, engine, and region.
   Publish only one exact top candidate with a safe margin. A fuzzy or tied
   result is `ambiguous`/`needs_review`, not a silent merge.
6. Persist the canonical identity and all verified provider mappings in one
   idempotent transaction. Use the mapping's source snapshot and evidence for
   provenance.
7. Use the AutoData UUID for procedure, quote, cache, and revision operations;
   use the provider mapping only when making a provider request.

## Lifecycle and failure behavior

Provider resolution is read-through and cache-first. Identical misses are
single-flight/bounded by the connector, and retryable upstream failures retain
their existing retry and dead-letter semantics. A provider response that is
valid but ambiguous is durable review state, not a transient error. Source
takedown or mapping rejection marks the mapping unavailable and preserves the
historical source snapshot and evidence.

The mapping does not make a source article canonical by itself. Article
normalization, evidence extraction, quality checks, and publication still
follow the existing ingestion and revision lifecycle. Every published fact
must point back through the mapping to source material.

## Concrete work queue

- [ ] Add the typed provider mapping schema and persistence helpers.
- [ ] Add deterministic AutoAPITwo candidate normalization and ambiguity
      handling.
- [ ] Connect mapping resolution to the existing canonical vehicle graph and
      source fallback.
- [ ] Verify the Silverado acceptance case, cache reuse, provenance, and
      browser-visible source trace.
- [ ] Synchronize Issue #104, Project #8, repository records, tests, and CI.

The GitHub Project remains an index and work queue. This document and the
implementation plan are the technical source of truth for the identity
contract.
