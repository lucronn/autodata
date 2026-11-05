# Firebase identity verification

The canonical scope is `docs/superpowers/plans/2026-11-03-workshop-firebase-identity.md`.
This lane implements customer identity and revocable application sessions. It
does not establish production readiness or paid catalog/media authorization.

Run ordinary Go tests from apps/api-go and the collector unit tests with
`python -m unittest discover -s scripts/dev -p test_production_access_smoke.py`.
The pinned official Firebase Admin SDK is v4.22.0. Its serial TLS harness generates
local RS256 certificates and user responses, routes only the exact certificate
and user hosts into local TLS fixtures, and rejects every unexpected dial. Tests
use explicit unauthenticated fixture clients and never an emulator or real cloud.

The coordinator owns the immutable plain clone, input manifest, private lifecycle
Compose project, pinned Go1.26 image, bounded supervisor and cleanup. No host
ports, credentials, Docker socket, live provider/model API or Firebase project is
needed. The required entry point inside that runner is:

```
python scripts/dev/production_access_smoke.py --mode fixture --candidate-sha <40hex> --output /artifacts/r5-access.json
```

The collector verifies the host input manifest and actual Git SHA/status/remotes
before/after, sets AUTODATA_REQUIRE_AUTH_INTEGRATION=1 for the child and runs the
frozen three-module pytest inventory: scripts/dev/test_migrations.py,
workers/ingestion-python/tests/test_article_lifecycle_migrations.py and
scripts/dev/test_production_access_smoke.py. The last module defines the one
required PostgreSQL bridge. It creates separate full039 and through038 databases
and executes TestPostgresAuthSessionsIntegration with exactly five subtests:

- ConcurrentCustomerProvisionAndRotation
- SharedSessionRevocation
- ExpiryAndPersistedSecrecy
- FirebaseExchangeAndUserRevocation
- FirebaseStartupRequiresMigratedPostgres

Root and all five must actually run and pass. Missing dependencies/configuration,
zero tests, skips, timeout or nonzero exit cannot succeed. The bridge retains raw
Go JSON/stderr and captures only synthetic account/session columns, including
hexadecimal SHA256 hashes, never raw session or provider tokens. Actual039 ledger
and unchanged 038 startup ledger are mandatory. Shared migration tests additionally
cover fresh/twice, upgrade/restart, rollback/retry, adoption rejection and racing
runners. The eight R3 catalog cases retain their original semantics with039 and
all 16 evidence tables; their independent current-head supervisor remains required.

`r5-access.json` has schema_version1, candidate/input/host hashes, timestamps,
pytest and Go exits, exact root/subtest IDs, migration head, nine fixed boolean
assertions, passed and failures. Its allowlisted artifact_sha256 binds exactly
r5-access-migrations.xml, r5-access-go-events.jsonl, r5-access-go-stderr.log,
r5-access-migration-rows.json and runner-input/runner-git before/after JSON.
The result never hashes itself. Preserve failed artifacts and use an independently
reviewed supervisor to certify this evidence; the collector alone is no approval.

Before deployment, configure the real Firebase project and web app, enable Google
sign-in, authorize cars.tk and the approved authDomain, provision Admin SDK ADC/IAM,
apply039 using the shared driver, configure HTTPS/public origin and verify proxy
headers and sanitized logs. Live staging must demonstrate sign-in, disabled/deleted
and revoked-user denial, dependency outages, two-replica logout and secure cookies.
The current Kubernetes external migration image also needs exact 039 verification.
Those external prerequisites do not block deterministic implementation, but remain
required before release. Checkout/grants/library and paid source/media enforcement
have separate gates.
