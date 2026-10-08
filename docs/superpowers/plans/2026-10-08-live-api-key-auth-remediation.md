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

## Execution evidence (2026-10-08)

- The protected key-manager Preview deployment was left protected. Its
  manager-specific credential remains scoped to Preview.
- The existing service-specific `API_KEYS_DATABASE_URL` environment variables
  were extended from Preview to Production by updating their Vercel targets;
  the encrypted values were preserved and never read or printed.
- Bankone production runs commit
  `469612d75649cd18e41998bb9ba67bf7447c52c6`, deployment
  `dpl_4rKTrz5htWkV4gMB4aWUbv98wuQx`.
- Banktwo production runs commit
  `62964c6ccfd628b9a9305569d0b08801c8f6f858`, deployment
  `dpl_CaxirZPLPpEuapEn3Vb22kEs7Pp7`. Its Vercel project uses the Fastify
  framework adapter, and the serverless handler now lives in `src/server.ts`.
  The `@fastify/static` lock is pinned to the CommonJS-compatible `10.1.3`
  release required by Vercel's Fastify function wrapper.
- Vercel routing version
  `b79834c3-aea7-4dad-9509-70bcdd58854c` is active. It preserves both
  `/bankone/*` rewrites and adds `/banktwo/*` rewrites to the Banktwo project.
- Live checks through `cars.tk`: each API returned 401 without a key and for
  the other service's key; each returned 200 for its own key. Banktwo returned
  62 catalog records. Banktwo readiness and its docs page returned 200.
- Bankone tests/build passed (69 tests); Banktwo tests/build passed (10 tests).
  The independent AutoData review agent found no actionable findings in the
  Banktwo code diff.
- The protected manager access policy was not changed. The user will replace
  the shared-in-chat keys after this fix.
