# Bankone and Banktwo API key management

## Goal

Provide one protected dashboard to issue, inspect, expire, and revoke credentials
for the independently hosted Bankone and Banktwo APIs. A key is scoped to exactly
one service. AutoData remains a consumer of those APIs and receives credentials
through deployment secrets.

## Components and boundaries

- **Key database:** managed PostgreSQL (Neon) shared by the manager and both
  API deployments. It is dedicated to API credentials and audit events; it is
  not the AutoData vehicle catalog database.
- **Manager:** a small standalone web application deployed as its own Vercel
  project. Enable Vercel Authentication with Standard Deployment Protection.
  Do not attach a production domain or public production alias; administrators
  use its protected deployment URL. This avoids depending on the paid
  All-Deployments protection scope. The project must not host Bankone/Banktwo
  public API routes.
- **Bankone and Banktwo:** each validates the caller's bearer key against the
  same PostgreSQL records on every request, before provider/source work. The
  service name is part of the validation predicate, so keys cannot cross API
  boundaries. Health/readiness endpoints retain their current public behavior.
- **AutoData:** server-side clients send the corresponding key from deployment
  secrets. No key is embedded in browser JavaScript, HTML, examples, or logs.

Use a PostgreSQL provider supported by Vercel in a no-cost tier for initial
development. Do not silently select a paid plan. Production enablement requires
the same database to be available to all three deployments; environment
variables are configured separately for each deployment and never committed.

## Key lifecycle and storage

Generate at least 256 bits of cryptographically secure randomness. Display a
service-identifying prefix and a random secret portion; store only the SHA-256
digest of the complete high-entropy token, plus a short non-secret display
prefix. No raw key can be recovered from the database. Show the raw value once
after creation and require the administrator to copy it then.

Each record contains an immutable ID, service (`bankone` or `banktwo`), label,
digest, display prefix, creation time, optional expiry, optional revocation
time, and last-used time. Listing returns metadata only. Revocation is
idempotent, records a fixed service-level actor label and timestamp, and takes effect for requests
whose validation starts after the revocation transaction commits. Expired and
revoked rows are retained for audit and never become valid again. Rotation is
create-new, deploy-new-secret, verify, then revoke-old; do not silently replace
a key in place.

Vercel Standard Deployment Protection supplies the dashboard's authentication
boundary, but the function runtime does not receive a verified individual user
identity or role claim. Audit events therefore use `vercel-authenticated-session`
and do not provide per-user attribution. Restrict Vercel project membership to
trusted key administrators. If individual actor attribution or delegated
per-service administrators are required, add a verified identity integration
before broadening access.

Every user granted access to this protected deployment has full management
authority over both services' keys. There is no application-level user, team,
or per-service role check. Keep deployment access limited to trusted key
administrators; do not grant access to general read-only dashboard viewers.

Key values and digests are excluded from logs, traces, audit payloads, database
errors, and API responses except the one-time creation response. Validate
constant-time digest equality where applicable. Key validation must not use a
shared cache; a cache hit could extend a revoked key's validity.

## API behavior

- Data routes require `Authorization: Bearer <key>`.
- Missing, malformed, unknown, expired, revoked, and wrong-service keys return
  the existing sanitized 401 contract before upstream calls or data work.
- Database connectivity or query errors fail closed with the established
  sanitized 503 response. Do not expose SQL, connection strings, or tokens.
- Health and readiness behavior remains unchanged and contains no protected
  catalog/article content.
- Response schemas remain unchanged, but requiring credentials on existing data
  routes is a breaking authentication change. Coordinate the Bankone, Banktwo,
  and AutoData deployment cutover: configure the matching AutoData secrets and
  deploy the clients with the new keys before enabling enforcement on each API.
- Keep the current Banktwo static-token mechanism only as a temporary,
  explicitly bounded migration fallback. Remove it after the API-key database
  and AutoData's server-side key are configured and a live valid-key request
  succeeds. Bankone transitions from its present public data routes to required
  keys in the same coordinated rollout.

## Dashboard behavior

After Vercel team authentication, an administrator can create a key for one
service, choose a human-readable label and optional expiry, list metadata for
active/revoked/expired keys, and revoke an active key. Mutations require
same-origin/CSRF protection and server-side validation. All database access
uses parameterized SQL. The UI distinguishes service scope and lifecycle state
clearly. It never displays the secret after leaving the one-time creation view.

Audit events record the service-level actor label, action, service, key ID, and
timestamp, but never credentials. The database role used by the manager may
perform lifecycle mutations. API runtime roles may only read valid key metadata and update
last-used state; they cannot create keys or alter scopes. Use separate
least-privilege database credentials where the provider supports them.

## Delivery and rollout

1. Build and migrate against local PostgreSQL; implement the manager and
   validation adapters with deterministic integration tests. Each migration
   runs transactionally and is recorded in a dedicated migration ledger; a
   failed version is retried only after its data or schema issue is repaired.
2. Provision the shared database on the provider's free tier, create
   least-privilege roles, and apply the migration once.
3. Deploy the manager as a distinct Vercel project with Vercel Authentication
   and Standard Deployment Protection. Leave production domains/aliases
   unattached. Verify direct deployment URLs block unauthorized requests and
   an authorized team member can reach the dashboard.
4. Configure DB credentials for Bankone, Banktwo, and AutoData as deployment
   secrets. Provision one initial key per service through the manager and add
   each key only to the matching AutoData server-side client secret.
5. Deploy Bankone and Banktwo key enforcement. Verify bad/missing/wrong-scope
   requests fail before any upstream call, and valid keys succeed.
6. Remove the temporary Banktwo static token fallback after the new path is
   live. Revoke temporary or test credentials. Confirm revocation live, then
   record the exact deployment SHAs and test evidence in Issue #129 and
   Project #8.

Do not deploy production or change production credentials as part of local
implementation. Dev deployment is allowed by repository policy after all
required review and verification gates pass.

## Acceptance evidence

- Migrations apply from empty and upgrade fixtures and rerun safely; migration
  versions are recorded only after commit. Uniqueness, service scope, retention,
  immutable key identity, matched audit service, and append-only audit constraints
  are verified.
- Tests cover creation, one-time plaintext display, list redaction, expiry,
  revoke/idempotency, cross-service rejection, concurrent revoke/validate,
  database outage fail-closed behavior, and secret leakage.
- Both API integrations prove absent/invalid/expired/revoked/wrong-scope keys
  are rejected before upstream work, and valid keys preserve existing response
  schemas.
- Manager protection is verified on the actual Vercel project, including the
  login boundary and server routes.
- AutoData makes a live authenticated request to both APIs using server-only
  secrets; no browser bundle or public response contains either key.
- Independent AutoData review and applicable cross-repository reviews pass.

## Tracking

- Issue: https://github.com/lucronn/autodata/issues/129
- Project: https://github.com/users/lucronn/projects/8
- Plan: `docs/superpowers/plans/2026-10-07-bankone-banktwo-api-key-management.md`
