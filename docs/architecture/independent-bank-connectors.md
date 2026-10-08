# Independent Bankone and Banktwo Connector Boundaries

## Target ownership

AutoData (`lucronn/autodata`), Bankone (`lucronn/bankone`), and Banktwo
(`lucronn/banktwo`) build, test, release, deploy, and operate independently.
AutoData owns product APIs, canonical vehicle identity, normalized records,
provenance, review, storage, and job orchestration. Each bank owns its source
protocol, provider parsing/search, credentials/session, retry/cache policy,
assets, and read-only connector API. Banks do not import AutoData, access its
database/object store, or call one another.

## Runtime names and contract

- Bankone origin: `https://bankone.cars.tk`
- Banktwo origin: `https://banktwo.cars.tk`
- Connector API major version: `/v1`; probes: `/healthz` and `/readyz`.
- Shared OpenAPI consumer contract: `packages/contracts/source-connector/v1/openapi.yaml`.
- Wire provider slugs `bankone`/`banktwo` map to persisted AutoData lineage values
  `autoapi`/`autoapitwo`; do not rename historical source IDs, article IDs,
  source versions, or migration history in this extraction.

Each subdomain is directly attached to its corresponding bank deployment.
Detach `cars.tk` from Banktwo. Retire the old `cars.tk/bankone` and
`cars.tk/banktwo` routes after AutoData clients switch. Do not keep a shared
router or forward bearer credentials between origins.

## Concrete todo

- [ ] Freeze v1 OpenAPI, errors, capabilities, catalog pagination, vehicle
  resolution, article search/list, opaque resources, and conformance fixtures.
- [ ] Move all Bankone-specific upstream logic and source response parsing into
  the Bankone repository; independently build, test, deploy, and attach its
  subdomain.
- [ ] Move all Banktwo-specific upstream logic and source response parsing into
  the Banktwo repository; independently build, test, deploy, and attach its
  subdomain.
- [ ] Replace AutoData-specific bank modules/callers with generic HTTP clients;
  preserve normalized output, provenance, source snapshots, and persisted IDs.
- [ ] Migrate Bankone article-fetch jobs to a provider-neutral AutoData job store
  while preserving legacy in-flight UUIDs and idempotency keys.
- [ ] Remove Banktwo submodule/build/runtime dependencies and all Banktwo-owned
  Bankone routing; move AutoData defaults to direct subdomain origins.
- [ ] Canary each service independently, compare source and normalized behavior,
  verify retry/rollback, and remove embedded adapters after parity passes.

See [the approved design](../superpowers/specs/2026-10-08-independent-bank-connectors-design.md)
and [the implementation plan](../superpowers/plans/2026-10-08-independent-bank-connectors.md).


**Issue:** https://github.com/lucronn/autodata/issues/132
**Project:** https://github.com/users/lucronn/projects/8
