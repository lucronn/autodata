# Provider-neutral vehicle identity graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve natural-language vehicle descriptions to one durable AutoData vehicle identity while preserving one-to-many AutoAPITwo/ACES mappings, provider provenance, ambiguity, and fast local reuse.

**Architecture:** AutoData owns the canonical UUID. Provider identifiers are evidence-backed mappings, never canonical keys. Resolution normalizes a query, checks local mappings and aliases, searches AutoAPITwo when needed, scores candidates deterministically, persists only an exact or unambiguous match, and leaves ambiguous candidates pending review. Existing procedure retrieval consumes the canonical identity plus provider-specific lookup metadata.

**Tech Stack:** Python ingestion worker, PostgreSQL migrations, existing vehicle identity persistence, AutoAPITwo HTTPS connector, pytest, Docker Compose integration path, GitHub Issue #104 and Portfolio Project #8.

**Spec:** Issue: https://github.com/lucronn/autodata/issues/104

**Project:** https://github.com/users/lucronn/projects/8

**todo:** Add the typed provider mapping contract, deterministic AutoAPITwo
resolution, canonical UUID persistence, Silverado source fallback, and
focused/full/browser/cache/CI verification.

## Global Constraints

- The AutoData UUID is the only internal vehicle identifier used by domain and purchaser-facing code.
- AutoAPITwo `carid`, ACES vehicle IDs, ACES engine IDs, and ACES vehicle-to-engine-configuration IDs are external identifiers. Each is stored as a typed mapping with provider, raw label, source snapshot, evidence, confidence, and status.
- An ACES engine ID is not unique to a vehicle. A provider car ID is a source-content key, not an AutoData identity.
- Do not merge candidates on fuzzy similarity alone. A match must preserve year, make, model family, drivetrain, body/trim where present, engine displacement where present, and region when supplied.
- Ambiguous and unresolved candidates remain auditable and do not create a canonical identity.
- Every provider-derived mapping remains linked to immutable source/provenance records.
- Provider calls are bounded, cached, and idempotent; a local mapping hit must not call AutoAPITwo.
- Preserve user-owned untracked `output/`, `sample data/`, and `tmp/` paths; stage only intentional task files.

## Implementation Tasks

### Task 1: Add the provider mapping persistence contract

**Files:** Create `db/migrations/028_vehicle_provider_mappings.sql`; modify the vehicle identity persistence module and its tests.

- [x] Write failing persistence tests for typed provider identifiers, one-to-many ACES mappings, idempotent upsert, provenance requirements, and rejected/ambiguous mappings.
- [x] Add the migration for provider mapping rows linked to canonical vehicle/configuration records and source/evidence records, with uniqueness on provider/entity type/provider ID and an auditable status.
- [x] Add persistence helpers that upsert verified mappings and retain raw provider labels and payloads.
- [x] Verify migration SQL and persistence tests against the existing schema conventions.

### Task 2: Implement deterministic AutoAPITwo identity resolution

**Files:** Create `workers/ingestion-python/src/autodata_ingestion/vehicle_identity_provider.py`; modify `autoapitwo_connector.py` only as needed; add focused resolver and connector tests.

- [x] Write failing tests for `1999 Chevrolet Silverado 1500 2WD 5.3L`, `99 Silverado 1500 2WD 5.3L`, distinct 2WD/4WD candidates, ACES engine IDs shared by many vehicles, and malformed provider labels.
- [x] Normalize AutoAPITwo search rows into canonical observations, including provider aliases such as `Chevy Truck` and `C 1500 Truck 2WD`, engine displacement, drivetrain, ACES vehicle IDs, ACES engine IDs, and ACES VEC IDs.
- [x] Add deterministic candidate scoring and an explicit `matched`, `ambiguous`, or `unmatched` result. Require a single exact top candidate with a safe margin before publication.
- [x] Reuse one bounded connector instance so repeat lookups use its local cache and preserve the exact provider row in the candidate for provenance.

### Task 3: Connect identity resolution to the existing vehicle graph

**Files:** Modify `vehicle_identity_persistence.py`, `autoapitwo_guide.py`, and the current chat/source resolution path; add integration tests.

- [x] Write an integration-shaped persistence test proving equivalent YMME aliases use the same stable AutoData UUID while retaining provider mappings.
- [x] Persist a verified AutoAPITwo match through the existing canonical identity path and attach typed provider mappings without replacing the UUID with a provider key.
- [x] Preserve pending/ambiguous results instead of guessing and keep provider namespaces explicit.
- [x] Make current Silverado source retrieval use the normalized provider car ID when the legacy AutoAPI/MOTOR catalog has no exact target.
- [x] Keep source retrieval and article hydration idempotent and preserve existing retry/dead-letter behavior.

### Task 4: Verify the end-to-end vehicle resolution behavior

**Files:** Modify the canonical architecture documentation and this plan with evidence only after implementation.

- [x] Run focused resolver, persistence, chat, and connector tests, then the full applicable worker/API suites.
- [x] Run the local Compose path and browser-test the natural-language Silverado request, confirming the selected vehicle is consumer-readable and the Workers terminal shows the bounded lookup.
- [x] Verify repeat connector use and the dashboard's cache-served repeat request.
- [x] Update Issue #104, Project #8, the synchronized record, and the plan with exact implementation SHA, test output, CI result, and any remaining review state.

## Verification

Implementation commit: `59b369857e91e3bbec47101753c8ac04f79a66a2`

Final CI verification: [Autonomous Verification run 35370494978](https://github.com/lucronn/autodata/actions/runs/35370494978) passed on commit `125f0a296ee413d72ddc849e8a187dfa5bb6a5d3`.

- Focused identity, persistence, guide, and chat tests: `65 passed`.
- Full ingestion worker suite: `413 passed, 3 skipped, 12 subtests passed`.
- Go API suite: `ok github.com/lucronn/autodata/apps/api-go`.
- Fresh isolated Compose stack applied `028_vehicle_provider_mappings` and reported the migration row and table present.
- Live AutoAPITwo resolution: `99 Silverado 1500 2WD 5.3L` matched provider car `34218`, canonical `1999 Chevrolet Silverado 1500 2WD 5.3L`, score `97`, with eight typed provider mappings.
- Browser verification at `http://127.0.0.1:18080/dashboard/` displayed the exact vehicle, source-backed procedure, Workers terminal events, and an honest unreviewed warning for provider sections that were not available. A repeat request displayed `Cache served` and `available · normalized`.
- The live source currently lacks timing-belt and power-steering-pump article coverage for this row; the UI kept those sections explicitly labeled missing instead of fabricating instructions.

## Acceptance Criteria

- `1999 Chevrolet Silverado 1500 2WD 5.3L` and `99 Silverado 1500 2WD 5.3L` resolve to the same AutoData UUID and provider car ID `34218` in the acceptance fixture/live verification.
- 2WD and 4WD, distinct engines, regions, and trims cannot silently collapse into one identity.
- ACES engine IDs and ACES VEC IDs may map to multiple provider rows and are never used as unique vehicle keys.
- Provider mappings include provenance and can be replayed or reviewed after a source response changes.
- A local mapping hit avoids an upstream lookup; a miss is bounded, cached, retryable, and observable.
- Existing source retrieval can use the provider mapping to serve the vehicle-specific article path when the legacy catalog cannot match the canonical name.
- No implementation claim is made until the local browser flow and exact tests/CI are verified.
