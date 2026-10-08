# Restore live Bankone and Banktwo API-key authentication

Issue: https://github.com/lucronn/autodata/issues/129  
Project: https://github.com/users/lucronn/projects/8

## Goal

Make the keys issued through the protected AutoData key manager work against
their matching live APIs, while requiring authentication on both public API
paths. Keep Vercel Deployment Protection enabled on the key manager. The user
explicitly authorized this task-specific production auth remediation and will
replace the supplied keys afterward; do not revoke, rotate, display, or log
those values.

## Observed failure and working hypothesis

On 2026-10-08, authenticated read-only requests found that
`https://cars.tk/bankone/v1/api/years` returned HTTP 200 with no key, a Bankone
key, and a Banktwo key. `https://cars.tk/banktwo/v1/fleet/years` returned HTTP
401 with the supplied Banktwo key and with a Bankone key; `/readyz` returned
HTTP 200. Vercel production environment metadata showed no
`API_KEYS_DATABASE_URL` on either API project. The corresponding variable is
configured only for Preview. The active production deployments also predate
the commits that add shared-database validation. This suggests the protected
dashboard issued the keys against Preview's database while `cars.tk` still
serves older production code without the shared-key configuration.

Validate the actual protected-dashboard environment and the three preview
database connections without printing or persisting secret values. Confirm
they address the same managed database and service-scoped roles before
promoting configuration to Production.

## Concrete todo

1. Verify the key manager's protected deployment, environment target, shared
   database identity, and existing key records using secret-safe checks.
2. Confirm the Bankone and Banktwo production deployments are older than the
   scoped-key commits and record the exact deployment SHAs.
3. Run current Bankone and Banktwo tests, builds, and preview auth checks,
   including missing, invalid, wrong-service, valid, and database-unavailable
   requests before upstream work.
4. Configure the production API projects with their least-privilege,
   service-specific shared-database credentials; configure the protected
   manager's production environment to use its manager role if required.
5. Deploy the authenticated Bankone and Banktwo builds to their existing
   production projects without changing domains, upstream credentials, or
   Deployment Protection.
6. Verify that no-key and wrong-service requests return 401, matching keys
   return 200, and database outages fail closed. Report only status codes and
   non-sensitive semantics; never print key or connection-string values.
7. Update Issue #129, Project #8, and canonical docs with exact deployed SHAs
   and evidence. Leave key rotation to the user.

## Constraints

- Keep Standard Deployment Protection / Vercel Authentication enabled for the
  key manager.
- Never rotate, revoke, disclose, or log the keys supplied in this task.
- Do not expose credentials in command output, files, browser bundles, or
  responses.
- Do not change source-provider credentials, API payload contracts, or domains.
- The user will replace the keys after successful live verification.

## Acceptance

- The manager remains protected and uses the same durable database as both
  APIs.
- Each live API rejects missing and cross-service credentials with HTTP 401.
- Each API accepts a valid key scoped to that service with HTTP 200.
- Database outages fail closed without leaking details.
- Verification demonstrates the live `cars.tk` routes, not only local tests
  or deployment readiness.
