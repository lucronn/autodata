# Bankone and Banktwo API key management implementation plan

## Goal

Create a protected management dashboard and shared database for API keys, then
require a correctly scoped key for every Bankone/Banktwo data request while
keeping the APIs consumable by AutoData and third-party applications.

## Decision

Use a dedicated managed PostgreSQL database shared by Bankone, Banktwo, and a
new standalone dashboard Vercel project. The manager project uses Vercel
Authentication / Deployment Protection across all deployments; it must not
share a Vercel project with the public APIs. Store only SHA-256 digests of
256-bit random keys, perform uncached service-scoped validation against the
database on every request, and fail closed. Keep AutoData's vehicle-data store
separate. Begin on a free database tier and do not create paid infrastructure
without explicit user approval.

The full normative lifecycle, access, schema, rollout, and acceptance contract
is [API key management](../../architecture/api-key-management.md).

## Canonical references

- Issue: https://github.com/lucronn/autodata/issues/129
- Project: https://github.com/users/lucronn/projects/8
- Architecture: `docs/architecture/api-key-management.md`
- Implementation base before checkpoint: `1fbfa274bb88a91d99343fabb7b84a20d4b3ccd9`

## Concrete todo list

1. [ ] Implement a dedicated key-management schema/migration, indexes,
   constraints, least-privilege roles, and repeatable local migration path.
2. [ ] Implement key issuance, metadata listing, expiry and revocation,
   append-only redacted audit events, one-time secret display, and an
   authenticated dashboard protected by Vercel Authentication on a separate
   Vercel project.
3. [ ] Implement shared key parsing/digest validation contract and integrate
   Banktwo; preserve health/readiness, reject invalid credentials before source
   work, and remove static-token fallback only after successful cutover.
4. [ ] Implement equivalent service-scoped key validation in the separate
   Bankone repository without disturbing its existing uncommitted changes.
5. [ ] Configure AutoData server-side Bankone/Banktwo clients to read separate
   deployment secrets; prove no key enters browser bundles or logs.
6. [ ] Add migrations, lifecycle, security, failure, API compatibility, and
   dashboard integration tests; verify both APIs and the dashboard against a
   live dev configuration, including immediate revocation and outage behavior.
7. [ ] Run independent schema, security, reliability, and final AutoData agent
   reviews; resolve findings and synchronize exact evidence and SHAs to Issue
   #129 and Project #8.

## Out of scope

- Production deployment or production credential rotation.
- User registration, teams/customers, quotas, billing, metering, or OAuth.
- Changes to the vehicle/article API payloads or AutoData vehicle-data schema.
- A browser-visible API key or recoverable key storage.

## Rollout order

Complete the canonical pre-implementation gate first. Then implement and test
against local PostgreSQL; provision only a free shared development database;
protect the standalone manager project; configure server-only credentials;
deploy/test the consumers; and remove Banktwo's legacy static token only after
valid-key requests succeed. Production remains untouched.

## Verification requirements

Follow the architecture acceptance evidence. In particular, test negative
credentials against an upstream-call counter, key-scope isolation, expired and
revoked rows, database outage, simultaneous revocation, response compatibility,
manager access boundaries, and secret scanning of logs/bundles/HTTP output.
Live verification must report status codes and semantic outcomes without
revealing credential values.
