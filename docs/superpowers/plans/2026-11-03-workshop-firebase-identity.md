# Firebase Customer Identity and PostgreSQL Sessions Implementation Plan

> For agentic workers: implement only after a committed synchronized exact-base gate and passing machine preflight. Use the repository's executing-plans workflow with independent exact-commit review. This draft grants no implementation authority until the new synchronized gate passes.

**Goal:** Give cars.tk customers Google sign-in through Firebase, a persistent account/personal organization and revocable opaque PostgreSQL sessions, ready for a separate $20 USD configuration+region purchase/access lane.

**Architecture:** Browser Firebase Google sign-in obtains a Firebase ID token; the Go API verifies it with the official Firebase Admin SDK and atomically maps its project+UID to a customer account and opaque session. Every protected session request checks PostgreSQL and the Firebase user record. Existing account-independent canonical content stays shared internally; paid access is enforced by the subsequent commerce/access lane, never by a global customer role alone.

**Tech stack:** Go1.26, `firebase.google.com/go/v4` Auth, existing pgx/PostgreSQL, existing private R3 Go/Python fixture image and shared migration runner. Google Cloud application-default/service identity for Admin SDK; public Firebase web config is not an Admin credential. No custom JWT verifier or new identity provider.

**Specs/tracking:** coordinator must amend `docs/superpowers/specs/2026-11-03-production-release-orchestration-design.md`, `docs/superpowers/specs/2026-11-03-source-fallback-web-design.md`, canonical production-access plan/handoff and r5-access task before code; Issue186 / https://github.com/lucronn/autodata/issues/186 ; Project8 / https://github.com/users/lucronn/projects/8 . Inspected root `521385fea0d0a57c92ba52cbb209a4dc79705c9a`; R3 candidate62e782c integrated and verified at `31ffe7ebcf28f345e0b5055b4dad10ebb7ed101c`, with all eight actual content cases passing.

## Fixed scope and supersession

This customer flow supersedes the old confidential OIDC client/discovery/code-PKCE redirect/callback, custom organization/role claims and auth_login_transactions design. Do not retain an unconfigured OIDC fallback or describe Google/Firebase as merely a new OIDC issuer value. No customer `/auth/callback`, PKCE transaction table, client secret, bearer API access or staff identity flow is added here. Existing injected local authenticators remain unit/fixture-only; explicit local development mode never creates a demo browser session.

Initial commercial scope is fixed by the coordinator: exactly the selected canonical vehicle configuration plus region, not VIN, family, free-form label or fuzzy/title merge. Both-bank articles qualify only through existing verified links to that scope. This identity migration creates no price, payment, checkout, entitlement, vehicle-scope or article-mapping table and grants no purchased scope. $20 USD ordering, permanent grants, safe previews, library and catalog/source/media entitlement enforcement require separate synchronized lanes. Identity alone is not production release readiness.

Execution profile for builder/reviewer: gpt-6.1-sol, medium, Fast/priority, no fallback. Read AGENTS and canonical gate first. Commit coherent validated milestones and promptly push only to the coordinator-owned assigned branch after checks; no merge/deploy/scope expansion.

## Configuration and startup contract

- `AUTODATA_ENV`: explicit development/test/staging/production. `AUTODATA_AUTH_MODE`: firebase for customer login, local allowed only development/test. Unset/unknown or staging/production local fails startup.
- `AUTODATA_PUBLIC_ORIGIN`: https://cars.tk in production; exact HTTPS origin for staging. No request Host/forwarded-header derivation. Explicit test mode alone permits configured loopback HTTP. Production web origin and service worker/API paths remain same-origin.
- `AUTODATA_FIREBASE_PROJECT_ID`: required nonempty exact project, pending owner selection. Public `AUTODATA_FIREBASE_WEB_API_KEY`, `AUTODATA_FIREBASE_WEB_APP_ID`, `AUTODATA_FIREBASE_AUTH_DOMAIN`: required for enabled browser Google sign-in and validated against that project/explicit domain configuration. These public values may enter `/auth/config`; Admin credentials never do. Do not infer or provision a project or authorized domain.
- Admin SDK obtains application-default credentials from the selected Google Cloud workload identity/service account. No inline credential JSON, private key, client secret or tracked credential file. Missing credentials/configuration fails firebase startup; project user-lookup permission is a deployment prerequisite. Readiness includes DB/schema/local client configuration, not an invented live certification from SDK initialization alone.
- Reject nonempty `FIREBASE_AUTH_EMULATOR_HOST` whenever Firebase mode is selected, including test startup. The pinned SDK otherwise accepts emulator tokens without production signature verification. Add an explicit startup regression; fixture SDK tests never use emulator mode.
- Firebase mode requires a working PostgreSQL pool and both039 tables; no memory-store fallback or startup auto-migration. Missing schema/store fails before serving. Local mode remains explicit headless-only and cannot be selected automatically when Firebase is unavailable.
- Pin `firebase.google.com/go/v4 v4.22.0` in API go.mod/go.sum. Independently resolved from the official Go module proxy and downloaded without editing repository manifests: module checksum `h1:+7ClMN69jOITseDXC7q0OKjMkRl3ZEJwZaLB900mvYs=`, go.mod checksum `h1:tXyH/bqgOst15PmgHUSFaLX9woyDwclTtz/cRX+NocQ=`. This release requires Go1.25 and is compatible with the pinned Go1.26 fixture. The module origin is Firebase Admin Go commit `66a72c371b4dbc592317ab7e7f99ce00d76c62ae`. Official SDK API/transport tests below must pass for this exact pin. Runtime cache uses the same candidate dependency manifests, GOPROXY=off and GOTOOLCHAIN=local.

## Identity and session policy

Use a narrow `CustomerIdentityVerifier` with `VerifyLogin(ctx, rawIDToken) (VerifiedCustomerIdentity, error)` and `CheckUser(ctx, projectID, uid, authTime) error`. VerifiedCustomerIdentity contains trusted projectID, UID, auth_time, iat and exp only. Official implementation calls Auth.VerifyIDTokenAndCheckRevoked for exchange; validate expected project issuer/audience, nonempty UID, exp/iat/auth_time and verified signed `firebase.sign_in_provider == google.com`. Initial browser provider is Google only; anonymous/custom/password identities are not alternate launch paths. Ignore email, organization, role and admin-looking token fields when provisioning customer authority.

The pinned SDK currently compares `IssuedAt` with `TokensValidAfterMillis` in its revocation check. The application additionally calls `CheckUser` against the verified `auth_time` before committing an exchange, so a freshly issued token cannot revive an authentication predating revocation. Test fresh iat with revoked auth_time and require no account/session grant. Do not replace the official signature verifier.

For exchange require token iat and auth_time no older than five minutes, no more than60s in the future, and token not expired. Firebase SDK cryptographic/time checks remain authoritative; additional freshness constraints are application checks. Returning browser with stale Firebase auth_time must explicitly reauthenticate with Google before exchange; silently refreshing an ID token does not change auth_time. Never log the token or return Firebase error bodies.

Map unique `(firebase_project_id, firebase_uid)` to server-generated customer_account_id and personal_organization_id UUIDs. Never key by email or permit a submitted account/org selector. UID relink/change creates a distinct identity unless separately authorized account migration is planned. Default account status active; blocked denies every protected request. There is no staff role column or admin grant on customer signup. Ordinary customer Principal receives server-defined dataset_viewer plus internal customer_account_id/project/UID, preserving existing organization-owned dataset checks. Existing staff routes stay denied to an ordinary customer; staff provisioning/login is separate work, not accepted from customer custom claims.

New sessions use random256-bit tokens, persist only SHA256 hashes, cookie `__Host-autodata_session; Secure; HttpOnly; SameSite=Lax; Path=/` with no Domain, and a12-hour absolute lifetime with no sliding extension. This explicitly replaces the old15-minute/capped-ID-token session policy: the Firebase token must be valid when exchanged, while subsequent access uses the server session plus live user-state checks. ID-token expiry does not silently renew or revoke the12-hour server session. Store verified auth_time on the session for Firebase revocation comparison. No raw ID/access/refresh/session token is persisted. Cookie Max-Age never exceeds server expiry.

On each new protected session request: lookup account/session, check expiry/revoked/account-blocked, then call official Auth.GetUser for the stored UID under the configured project. Deny disabled/deleted user and session auth_time earlier than TokensValidAfterMillis. Compare at SDK-compatible seconds/milliseconds precision and test equality/boundary cases. No positive user-state cache in this initial lane: each new request performs the lookup. Bound total verification/lookup work with a two-second context deadline; no unbounded retries. Timeout/permission/transport failures return sanitized retryable503 and do not authenticate from stale data. Definite invalid/revoked/disabled identity returns401 and clears the session cookie. Local revocation/account block takes effect at the next DB lookup across replicas. Firebase disable/revoke is checked on the next request against the actual returned user record; do not promise faster propagation than Firebase provides or recall already delivered bytes.

Logout needs the valid database session and CSRF/origin but need not call Firebase before committing its local revocation; it must remain usable during Firebase outage. It logs out this server session only, not all Google/Firebase devices. Explicit application logout also asks R4 to sign out its Firebase browser instance. No global-account/session-management UI or reset feature is added here.

## Additive HTTP contract for R4

- `GET /auth/config`: no-store public200 with `{version:"v1",mode:"firebase",login_available:true,providers:["google.com"],firebase:{apiKey,authDomain,projectId,appId}}` only after complete local configuration. Local mode returns `{version:"v1",mode:"local",login_available:false,providers:[]}` with no Firebase object. This public configuration contains no administrative credential or account information.
- `POST /auth/firebase/session`: JSON `{id_token:"..."}` only, max32KiB, exact configured Origin, application/json and custom `X-Autodata-Session-Exchange: 1` header. Reject cross-origin preflight/CORS and cross-origin Sec-Fetch-Site when present; never reflect origin. Together with exact Origin/content type/custom header this protects login exchange from cross-site session swapping without a new login-transaction table. Verify fresh token, atomically create/get account, revoke any valid presented old app session and insert new hashed session. Return204 with cookie; no session token/identity claims in response. Wrong/missing origin403, malformed413/400 as appropriate, invalid identity401, definite local-account block403, dependency failure sanitized503. No cookie is set until commit succeeds. Same signed Firebase token may be exchanged again while fresh: this is not an OAuth authorization code, so do not claim token one-time consumption or invent a replay table. Session rotation prevents old app-cookie reuse after committed exchange.
- `GET /auth/session`: preserve200 `{authenticated:true,roles:["dataset_viewer"],expires_at:"<RFC3339 UTC>",csrf_token:"<opaque>"}`;401 existing UNAUTHENTICATED envelope, fixed `Authentication is required.`, retryable:false, request ID, `details.login_available` true only for configured Firebase, false local. No email, UID, organization, Firebase token or staff claims. Sanitize503 dependency failure, distinct from401. Always no-store. Derive CSRF as base64url(HMAC-SHA256(raw session token,"autodata/csrf/v1")); constant-time check.
- `POST /auth/logout`: exact same-origin Origin plus X-CSRF-Token, committed session revoke, expired cookie,204; no-store. Cookie-authenticated state-changing API requests require the same Origin/CSRF boundary. GET does not mutate state beyond safe observational metadata.
- No implemented old OIDC `/auth/login` or `/auth/callback` route is assumed; R4 must use public config then Firebase Google popup sign-in and exchange. Local exchange returns503 AUTHENTICATION_UNAVAILABLE with fixed `Sign-in is unavailable.`, retryable:false and login_available:false, creates no account/session. Remove old proposed redirect/callback acceptance from canonical docs rather than maintaining dead routing.
- Ordinary customer APIs authenticate only the opaque session cookie in Firebase mode. Authorization bearer presence is rejected rather than falling back to a cookie; no Firebase token in query/localStorage/API header, and no privileged role/org header. A separately planned staff/API identity adapter may later add its own explicit contract.

Browser owner R4 uses pinned Firebase web SDK/configuration and Google popup, not a secret in the bundle. Provider/domain registration is a later configuration prerequisite. R4 handles blocked popup/cancel/unavailable config/401/403/503 distinctly, clears protected content on logout/denial, and never uses a demo/localStorage bearer fallback. Payment UI and purchased-scope browser flow are separate lanes. No Workshop file is edited by this identity builder.

## Migration039 and persistence

Exactly `db/migrations/039_production_identity_sessions.sql`, self-contained BEGIN/body/own version marker/COMMIT. Create only:

1. `customer_accounts`: customer_account_id UUID PK default gen_random_uuid; firebase_project_id and firebase_uid nonempty text, personal_organization_id UUID not null unique, status active/blocked check, created_at; unique(project_id,uid). No email/name/payment details or customer-controlled role.
2. `auth_sessions`: session_token_hash bytea32 PK; customer_account_id FK; firebase_auth_time bigint positive; created_at; expires_at greater than creation and at most12hours; revoked_at nullable. Index account ID and expiry. Identity comes from the account FK; there is no raw token or raw provider payload. Go enforces verified auth_time/new-session expiry and safe returned fields.

Store interfaces in auth_session.go; implement account upsert/get plus rotation and session insertion in a single PostgreSQL transaction in postgres_auth_sessions.go. Use ON CONFLICT(project,uid) then lock/read account so concurrent first logins cannot create separate personal organizations. Recheck blocked status under the transaction. Lock/conditionally revoke any presented active old session before issuing a replacement; unrelated caller IDs are never accepted as session ownership. Any failed insert/commit preserves old session and returns no new cookie. Session lookup joins current account status. Logout commits before returning204. Expired sessions are denied without relying on cleanup; bounded opportunistic retention cleanup may delete only expired/revoked sessions older than24hours, never account/grant history.

Append exact039 to the shell canonical manifest and Python test expectation; the production Python migration_files helper discovers numbered files and needs no separate hard-coded manifest edit; append039 at all FOUR explicit036|037|038 audit/synthetic-BEGIN/marker/COMMIT sites; add customer_accounts/auth_sessions to known-table adoption rejection. Remove the superseded planned auth_login_transactions guard/tests. Historical SQL001–038 immutable, shared advisory lock(186,3738),033 exception and explicit historical-prefix behavior unchanged. Preserve already planned full039 bootstrap,038 upgrade, populated account/session restart, rollback/retry and concurrent driver tests.

## Exact proposed identity-builder files

Create:

```text
apps/api-go/auth_config.go
apps/api-go/auth_config_test.go
apps/api-go/auth_firebase.go
apps/api-go/auth_firebase_test.go
apps/api-go/auth_session.go
apps/api-go/auth_session_test.go
apps/api-go/postgres_auth_sessions.go
apps/api-go/postgres_auth_sessions_test.go
apps/api-go/auth_http.go
apps/api-go/auth_http_test.go
db/migrations/039_production_identity_sessions.sql
scripts/dev/production_access_smoke.py
scripts/dev/test_production_access_smoke.py
docs/verification/production-access-runbook.md
```

Modify only:

```text
apps/api-go/main.go
apps/api-go/main_test.go
apps/api-go/api_test.go
apps/api-go/requests.go
apps/api-go/go.mod
apps/api-go/go.sum
apps/api-go/openapi.json
apps/api-go/openapi.yaml
scripts/dev/migrate_sql.sh
scripts/dev/test_migrations.py
scripts/dev/test_api_runtime.py
scripts/dev/test_k8s_manifests.py
workers/ingestion-python/tests/test_article_lifecycle_migrations.py
workers/ingestion-python/tests/test_catalog_api_integration.py
docs/operations/migration-runner.md
infra/compose/compose.yaml
infra/compose/compose.ci.yaml
docker-compose.base44.yml
infra/k8s/base.yaml
docs/architecture/infrastructure-and-dev.md
docs/architecture/workshop-interface.md
```

Total35 implementation paths. Main wires explicit configured customer dependencies without rewriting injected local unit constructors. requests.go extends internal Principal identity and retains existing role names. Runtime/deployment tests cover explicit local/fail-closed Firebase config. No auth_oidc.go, customer PKCE transaction, media/catalog implementation, worker payment code, contracts outside the two OpenAPI files, Workshop UI, fixture Dockerfile/Compose tooling rewrite or lifecycle_support.py edit. Paid catalog/media authorization is a separately gated lane with its own required R3 interface paths; this identity lane must not silently absorb it. Coordinator-owned canonical planning/task/tracking checkpoint edits are separate from this builder list.

## Tests: fake service seam versus actual SDK behavior

Handler/unit tests inject a strict in-process fake CustomerIdentityVerifier and deterministic clock/RNG to exercise configuration, account/session behavior and safe errors. Those tests are not evidence that the Firebase SDK validates signatures/project claims or performs revocation lookups.

Actual SDK adapter tests instantiate the pinned official Firebase Admin Auth client without ambient credentials, using explicit `option.WithoutAuthentication()` plus `option.WithHTTPClient(fixtureClient)` for user lookups. The pinned SDK certificate verifier does not inherit those client options: it creates its own unauthenticated HTTP client. The pinned google.golang.org/api v0.279.0 transport clones only a concrete `*http.Transport`; assigning a custom RoundTripper to http.DefaultTransport would silently miss certificate requests. Therefore a serial, scoped fixture temporarily installs a concrete `*http.Transport` with Proxy:nil, a fail-closed DialTLSContext routing only the exact Google certificate host to the local TLS certificate fixture, and rejection of every other dial. Its cloned callback survives SDK construction. Restore the original default transport with test cleanup and do not run these tests in parallel. Fixture responses supply locally generated RS256 certificates and exact user-lookup payloads; no certificate or user call may reach a real Google service. Set test-only GOOGLE_API_GO_EXPERIMENTAL_DISABLE_NEW_AUTH_LIB=true, GOOGLE_API_USE_CLIENT_CERTIFICATE=false, GOOGLE_API_USE_MTLS_ENDPOINT=never and EXPERIMENTAL_GOOGLE_API_USE_S2A=false to exclude ambient authentication/mTLS/S2A paths, restoring them afterward. Assert zero unexpected dials. Production code neither replaces default transports nor sets these test-only switches. No live Firebase project/network/emulator dependency. Exercise the official VerifyIDTokenAndCheckRevoked/GetUser path, not a replacement application JWT parser. Cover valid token, tampering, unknown key, wrong project issuer/audience, expiry/future time, non-Google provider, disabled/deleted user, TokensValidAfterMillis before/equal/after auth_time and permission/transport/timeout failures. Verify exact pinned SDK options avoid ambient auth discovery in this harness; if SDK endpoint/transport setup differs, adjust the allowed auth_firebase_test.go harness only and preserve production verification. Never enable an unsigned-token/emulator mode in production. Transport fixtures do not certify a real project's authorized domains, IAM or sign-in configuration.

## Five mandatory real PostgreSQL cases using the R3 fixture

Keep root `TestPostgresAuthSessionsIntegration`; replace the old OIDC transaction/callback subtest inventory explicitly with these exact five names:

1. `ConcurrentCustomerProvisionAndRotation`: two independent pools concurrently provision the same project+UID; exactly one account/personal org survives; sessions reference that account; a committed rotation revokes the old cookie; rollback leaves old session valid and no orphan new row. Different project/UID cannot adopt its account.
2. `SharedSessionRevocation`: two actual API/store instances sharing PostgreSQL; B accepts A's session, then rejects after A's logout commit or account block. No fake SQL rows.
3. `ExpiryAndPersistedSecrecy`: expiry boundary/absolute lifetime, hashed32-byte token, allowed identity fields, no raw Firebase/app tokens in persisted rows; stable account survives expiry and restart. Emit assertion outcomes only.
4. `FirebaseExchangeAndUserRevocation`: run real exchange/session HTTP handlers with real PostgreSQL and the actual SDK using the local certificate/user transport; fresh Google token creates session, old app cookie rotates, altered/wrong-project token fails, live fixture user disabled/revoked denies subsequent protected request, lookup outage returns503 with no stale acceptance. Same still-fresh valid ID token re-exchange is allowed; do not mislabel it a failed callback replay.
5. `FirebaseStartupRequiresMigratedPostgres`: full039 starts;038/unavailable pool/memory or missing persistence fail; never auto-migrate the038 database. Local mode remains explicit login-unavailable with no created account/session.

Coordinator clarification accepted during independent planning synchronization: `scripts/dev/test_production_access_smoke.py` adds `test_required_postgres_auth_sessions` importing existing lifecycle_support.fresh_database, so the frozen collector command actually collects the five-case auth bridge. The separately allowed `workers/ingestion-python/tests/test_catalog_api_integration.py` retains the eight R3 catalog cases and owns only current-head039/auth-table evidence adaptation. The auth bridge creates full039 and separate through038 DBs, and executes from /workspace/apps/api-go:

```text
go test -json -count=1 -run '^TestPostgresAuthSessionsIntegration$' .
```

Require AUTODATA_LIFECYCLE_TEST=1 and AUTODATA_REQUIRE_AUTH_INTEGRATION=1; bridge constructs only postgres fixture-owned lifecycle_test_<uuid> DSNs in AUTODATA_AUTH_TEST_DATABASE_URL and AUTODATA_AUTH_TEST_UNMIGRATED_DATABASE_URL. No inherited real Firebase/payment/bank/provider/DB config. Preserve actual R3 GOMODCACHE=/opt/go-module-cache, GOPROXY=off, GOFLAGS=-mod=readonly, GOTOOLCHAIN=local, CGO_ENABLED=0 and private writable GOCACHE/GOTMPDIR under executable/tmp. Build the same R3 image from the exact candidate manifests, not a divergent Firebase test image. No race-compiler assumption in this fixture; separate supported go test -race covers unit concurrency.

Frozen collector:

```text
python scripts/dev/production_access_smoke.py --mode fixture --candidate-sha <exact40hex> --output /artifacts/r5-access.json
python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/r5-access-migrations.xml scripts/dev/test_migrations.py workers/ingestion-python/tests/test_article_lifecycle_migrations.py scripts/dev/test_production_access_smoke.py
```

Required mode must fail rather than skip on absent config/DB/dependencies. Collector requires root plus all five named subtests pass, zero skips/errors/no-tests, nonzero pytest count, exact039 head and fresh per-run artifacts/complete before-after input and Git provenance. Preserve the reviewed R3 owned image/buildx/container/cleanup protocol, export AUTODATA_R3_TEST_IMAGE, AUTODATA_R3_CANDIDATE_SHA and isolated artifact dir, use supported run --pull never --no-deps. Coordinator separately reviews its R5 supervisor/validator with this new inventory. Existing R3 catalog bridge must require039/current auth tables and renamed001_039 evidence keys while retaining all eight content cases; its scratch regression validator needs separately reviewed039 adaptation. No supervisor approval or acceptance is claimed by prose.

## Implementation checklist and gates

- [ ] Coordinator: finalize verified R3 integration; retain the resolved official SDK pin; replace superseded customer OIDC plan/todo/file list and transaction table/old callback tests; synchronize amended release spec, R4 session contract, Issue186/Project8 and task with35 bounded paths plus exact five-case inventory. Commit checkpoint, re-pin and pass machine preflight before code.
- [ ] Add failing configuration, SDK transport, session/handler and039 manifest/real-PG tests. Implement minimal official verifier and account/session persistence, then require those tests pass. Keep SDK cryptographic tests distinct from fake handler seams.
- [ ] Wire explicit runtime mode and no-store auth routes/CSRF. Update OpenAPI/config manifests/runbook; prove local cannot become production and Firebase mode cannot use memory persistence. Preserve existing organization-owned reads and injected fixtures.
- [ ] Run ordinary Go/API/contracts and appropriate Python migration/runtime/manifest checks; run the required private five-case collector and preserved eight-case R3 regression with exact candidate evidence. Run separate supported unit race check and git diff --check. Fix only within scope; independent exact-SHA review checks SDK validation, account ownership, session revocation and error redaction.
- [ ] Commit/push validated milestones on the assigned owned branch; return the exact backend/R4 contract and deterministic evidence. Do not mark customer paid access or production launch complete from these tests.

Real Firebase/GCP project/app registration, Google provider enablement, cars.tk authorized domain, approved authDomain/redirect setup, runtime service identity/IAM and staging origin are explicit later configuration prerequisites. No value is invented or credential read here. Separate live staging must demonstrate Google sign-in, configured Admin verification/GetUser permission, disable/revoke behavior, two-replica logout, TLS/cookies/Cloudflare headers and sanitized logs before release. Checkout/grants/library/paid source+media enforcement must also pass their separate gates before the user goal is complete.

## Planning review amendments

Independent review `/tmp/autodata-workshop-firebase-plan-review.md` found two bounded test/startup clarifications, now incorporated: the SDK certificate transport ignores Auth client options, and ambient FIREBASE_AUTH_EMULATOR_HOST must be rejected explicitly. The exact SDK/transitive sources were inspected without production calls. Root resolved the SDK pin, requires the additional auth_time comparison at login, and verified R3 integration31ffe7e with all eight runtime cases passing. This draft still needs synchronized tracking, finalized task ownership and machine preflight before implementation.


## Synchronized dispatch checkpoint

Issue186 and Project8 were saved through the authenticated CLI and read back
against the prepared body and project fields on2026-11-03 at18:06:42UTC. The
Firebase task/specs, superseded OIDC handoff and R4 consumer contract now agree
on35 paths, five required PostgreSQL cases, the official SDK pin and separately
gated commerce/access. Independent planning review accepted both transport and
emulator amendments; root accepted the explicit test_production_access_smoke.py
bridge location so the frozen collector executes it. Prior drafts remain history.
This checkpoint must be committed and its exact SHA pass machine preflight before
implementation; R4 and later commerce/access are not dispatched by this record.


### Dependent paid-access boundary (reviewed planning handoff)

The separately gated [paid-access plan](2026-11-03-workshop-paid-access.md)
will make the four safe catalog selectors public, retaining only bounded metadata
read-through hydration. Paid article/list/source/media GETs are observational.
A session/Origin/CSRF-protected prepare POST starts or reuses durable article
preparation after exact configuration+region grant checks. Commerce owns initial
paid index intent. The unified customer UI passes configuration.id, prepares by
POST and then polls; expired media refreshes are bounded/coalesced. This amends
the future customer integration contract, does not expand the current35-path
R5 implementation scope, and requires verified identity/commerce plus its own
synchronized implementation gate. Existing explicit local R3 fixtures retain
their previously verified behavior.


### Firebase identity implementation and runtime acceptance

Candidate b4f3dc86a18a8087f8ff664e37bec594909eae80 is independently approved
and integrated at3fdcd0bc0ac993dd15ad2219df9d09ffeed27a4e. Five actual
PostgreSQL/SDK identity scenarios,55 outer cases plus7 subtests and all8 real
dual-bank regressions through039 pass. The initial report-parser failure is
retained separately; a reviewed strict correction passed fresh acceptance.
Integrated Go/contracts,104 development and19 contract checks pass. See
`docs/verification/2026-11-03-firebase-customer-identity.md` for exact evidence.
Full integration CI is pending; commerce's reviewed39-path checkpoint follows
that verified dependency and a fresh synchronized gate. No production launch
or live identity/merchant configuration is claimed by this foundation.
