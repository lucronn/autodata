# AutoAPItwo Vehicle Catalog Ingestion Contract

## Purpose

AutoData needs a durable vehicle vocabulary for natural-language matching and
the dashboard selector. The vocabulary is warmed from AutoAPItwo as the app is
used, then served locally. A warm-up means years, makes, models, engines, and
the provider vehicle identity/ACES metadata required to link a YMME query. It
does not mean downloading every repair article.

The work is tracked in [Project #8](https://github.com/users/lucronn/projects/8)
and the feature plan is
[`2026-09-18-autoapitwo-vehicle-catalog-ingestion.md`](../superpowers/plans/2026-09-18-autoapitwo-vehicle-catalog-ingestion.md).

## Source traversal

The configured provider origin is `AUTODATA_AUTOAPITWO_BASE_URL`, defaulting to
`https://autoapitwo.vercel.app`. The catalog adapter uses only the documented
fleet endpoints:

1. `GET /api/v1/fleet/years`
2. `GET /api/v1/fleet/years/{year}/makes`
3. `GET /api/v1/fleet/years/{year}/makes/{make}/models`
4. `GET /api/v1/fleet/years/{year}/makes/{make}/models/{model}/engines`
5. `GET /api/v1/fleet/years/{year}/makes/{make}/models/{model}/engines/{engine}/car?scope=summary`

The last call is made only when the engine row does not already provide the
provider car identity needed for stable linking. The adapter follows only
validated same-origin redirects and records the final provider ID. No
`/content/`, article, PDF, image, or repair-procedure endpoint is part of this
catalog contract.

## Local persistence and identity

AutoData remains the system of record. AutoAPItwo IDs are provider mappings,
not canonical IDs. The normalizer maps observations into the existing
`vehicles`, `vehicle_identity_bases`, and `vehicle_configurations` graph. It
retains provider IDs and labels in `vehicle_provider_mappings`, including
AutoAPItwo car, ACES vehicle, ACES engine, and ACES vehicle-engine-configuration
identifiers when supplied.

Every provider response is tied to a source snapshot, response hash, endpoint,
parameters, source version, and extraction evidence. Raw provider labels are
retained as aliases/observations so `97 Toyota RAV4 4WD`, `1997 Toyota RAV4`,
and later engine-qualified inputs can converge safely without guessing across
conflicting drivetrain or engine facts.

The stable AutoData identity is selected by normalized year, make, model,
region, drivetrain, trim, and engine configuration. A richer later observation
adds a configuration to the same compatible base. Conflicting known dimensions
remain reviewable observations and do not silently merge.

## One-time warm-up behavior

`GET /vehicle-identities/selectors` is cache-first. It returns whatever durable
catalog is already available and includes readiness metadata. If the configured
source/version has not completed, the request schedules one durable sync and
returns without waiting for upstream traversal. Concurrent requests coalesce
on the same provider/source-version/traversal-version key.

The worker claims the sync with a database lock, checkpoints each year/make/
model/engine scope, retries transient failures with bounded backoff, and
continues independent branches after a failure. A completed source/version is
not fetched again on selector reads. An operator can explicitly replay a
failed or dead-lettered sync with a new attempt while retaining the previous
source evidence.

The selector can therefore show partial years/makes/models/engines while the
catalog is warming. Existing cached options stay usable; upstream failure does
not erase them. Natural-language vehicle resolution uses the same local graph
and provider mappings, so later requests do not repeat the catalog calls.

## State contract

The durable sync exposes:

- `pending`: scheduled but not claimed;
- `running`: a worker owns the current checkpoint;
- `completed`: all planned scopes succeeded for the source/version;
- `partial`: some scopes succeeded and others require retry or review;
- `failed`: the run stopped before a usable checkpoint was published;
- `dead_letter`: retry limit exhausted and explicit replay is required.

Each scope has its own status, attempt count, last error, response hash, and
watermark. Replaying a scope is idempotent: it upserts the same canonical
identity/configuration and provider mapping keys rather than creating a
duplicate.

## API response addition

The existing selector response remains backward compatible and adds readiness
metadata:

```json
{
  "years": [1997, 1999],
  "vehicles": [],
  "catalog_sync": {
    "provider": "autoapitwo",
    "source_version": "autoapitwo-fleet-v1",
    "status": "running",
    "available_through": "1999",
    "last_completed_at": null,
    "next_retry_at": null
  }
}
```

This metadata is informational. It does not authorize a client to call
AutoAPItwo directly, and it never blocks a read of already persisted options.

## Verification requirements

The implementation must prove cold scheduling, concurrent coalescing, replay
after failure, duplicate convergence, evidence retention, zero repeated source
calls after completion, and browser behavior with the upstream unavailable.
The implementation plan, Issue, Project item, and final verification record
must contain the same goal, todo list, exact SHA, and CI evidence.
