# Production customer identity and access planning handoff

> Planning only. The authoritative identity implementation plan is [Firebase Customer Identity and PostgreSQL Sessions](2026-11-03-workshop-firebase-identity.md). Use the repository executing-plans workflow only after its committed synchronized exact-base gate passes.

**Goal:** Give cars.tk customers Google sign-in through Firebase, persistent accounts/personal organizations and secure PostgreSQL sessions as the identity prerequisite for separately gated $20 USD configuration+region purchases and permanent grants.

**Status:** tracking synchronized with actual Issue186/Project8. The approved Firebase plan supersedes this file's former OIDC implementation design. Commit/re-pin this checkpoint and pass machine preflight before implementation; tracking alone does not claim a passing gate.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8
**Record:** `docs/agents/records/2026-11-03-workshop-firebase-identity.json`
**Dependency:** verified R3 integration `31ffe7e`; planning inspection root `521385f`.

## Authoritative scope and supersession

Follow the [Firebase plan](2026-11-03-workshop-firebase-identity.md) for the exact official SDK pin, configuration, verifier contracts, account/session policies,35-path inventory and mandatory five-case collector. The [migration/runtime handoff](2026-11-03-production-access-migration-handoff.md) applies those decisions to shared migration039 and the actual R3 fixture.

The former confidential OIDC discovery/client-secret/code-PKCE redirect/callback, claim-controlled organization/roles, optional API bearer, auth_login_transactions table and15-minute ID-expiry-capped sessions are superseded. They are historical design decisions, not alternatives or fallback routes. Do not implement `/auth/login`, `/auth/callback`, an OIDC adapter or a customer transaction-consumption test from older revisions.

The ordinary customer is mapped by verified `(firebase_project_id,firebase_uid)` to one server-generated account and personal organization, with server-defined dataset_viewer only. Email and customer token role/org claims confer no authority. Staff identity is separate. Existing organization-owned dataset checks remain; customer identity does not grant purchased catalog scope.

New opaque256-bit sessions persist only SHA256 hashes, account FK and verified auth_time plus expiry/revocation metadata. Use `__Host-autodata_session; Secure; HttpOnly; SameSite=Lax; Path=/`, no Domain, absolute12-hour expiry and no sliding extension. Require a working migrated PostgreSQL store. Every protected session request checks current local status and official Firebase GetUser; compare stored auth_time against TokensValidAfterMillis, deny disabled/deleted/revoked users and return sanitized503 on lookup outage without stale authentication. SDK exchange verification additionally checks fresh iat/auth_time and google.com provider. Logout commits local revocation even during Firebase outage.

## Frozen R4 backend/session handoff

R5 owns identity backend files; R4 owns Workshop files after the committed contract is integrated. The exact payloads and error envelopes are defined in the authoritative Firebase plan's additive HTTP section:

- `GET /auth/config`: public no-store Firebase web config/provider availability, or explicit local `login_available:false` with no Firebase object. Public app config contains no Admin credential.
- `POST /auth/firebase/session`: fresh Google Firebase ID token as JSON, max32KiB, exact configured Origin, application/json and `X-Autodata-Session-Exchange: 1`; reject cross-origin fetch/preflight. Atomic account provisioning and old-cookie rotation return204/new cookie only after commit. The same still-fresh ID token can be exchanged again; no fabricated single-use callback semantics.
- `GET /auth/session`: no-store authenticated roles/expires_at/csrf_token, or fixed401 UNAUTHENTICATED with explicit login_available; distinguish sanitized dependency503. No UID/org/email/provider token is returned.
- `POST /auth/logout`: valid database session, exact Origin and session-bound X-CSRF-Token; commit local revocation, expire cookie and return204 without requiring a Firebase lookup. Cookie-authenticated mutations use the same CSRF/origin boundary.

R4 reads config then session, uses pinned Firebase web SDK Google popup and exchange, then same-origin opaque cookies. A returning user with stale auth_time must explicitly reauthenticate; ID-token refresh alone is insufficient. Handle blocked/cancelled popup, unavailable/malformed config,401,403 and503 distinctly. Clear protected content and cancel polling/renewal on denial/logout; application logout also signs out the browser Firebase instance. Explicit local mode is headless-only and reports login unavailable; no demo token/session, localStorage bearer or redirect/callback assumption is allowed. Browser fixtures intercept these new boundaries without external identity calls and cannot certify real project registration.

## Separate commerce and media enforcement boundary

The canonical [Workshop commerce policy](../../architecture/workshop-commerce.md) requires $20 USD once for exactly the normalized configuration+region, permanent account grants, safe previews, library and current entitlement/rights checks on full source/canonical/status/media reads. Those changes require a separate synchronized plan and task. The identity builder's35 paths exclude catalog/media implementation, checkout/grants/library and Workshop UI; completing identity alone cannot complete the user goal or production release.

R3 public projections and current media capabilities are not proof of session/entitlement revocation. Preserve the future requirement to authenticate before hydration/S3, enforce current article/revision/asset association and rights on each media read, deny old references after withdrawal or revoked access, and retain safe media CSP/type handling. Media renewal retains R4's one-coalesced-renewal-per-view contract. The later paid-access lane must select and gate its exact interfaces; this identity handoff does not silently authorize those files.

## Concrete todo and deterministic acceptance

- [ ] Synchronize the approved Firebase plan, canonical documents, R4/R5 tasks and actual Issue186/Project8; commit the checkpoint and pass exact-base machine preflight before implementation.
- [ ] Pin firebase.google.com/go/v4 v4.22.0; add actual SDK generated-RS256 certificate/user-lookup tests with scoped concrete transport isolation and explicit emulator-host startup rejection, separate from fake handler tests.
- [ ] Implement persistent unique project+UID customer accounts/personal organizations and SHA256-only opaque sessions with atomic provisioning/rotation/rollback, absolute12-hour expiry, account block and per-request Firebase auth_time revocation checks.
- [ ] Wire no-store /auth/config, /auth/firebase/session, /auth/session and /auth/logout with exact same-origin exchange, session-bound CSRF, sanitized401/403/503 and explicit local login-unavailable behavior; hand the committed contract to R4.
- [ ] Append self-contained migration039 at all four shared-runner transaction sites, reject untracked customer_accounts/auth_sessions, preserve SQL001–038 and historical-prefix regressions, and verify full039/038 upgrade/populated restart/rollback/concurrency using real PostgreSQL.
- [ ] Run TestPostgresAuthSessionsIntegration with exactly ConcurrentCustomerProvisionAndRotation, SharedSessionRevocation, ExpiryAndPersistedSecrecy, FirebaseExchangeAndUserRevocation and FirebaseStartupRequiresMigratedPostgres; require root/all five pass with zero skips and exact039 candidate provenance.
- [ ] Rebuild the existing verified R3 image from candidate manifests without fixture-tooling changes, preserve offline Go flags, update catalog evidence to039/auth tables and retain all eight required R3 content cases with separately reviewed supervisor adaptation.
- [ ] Run ordinary Go/API/contracts, migration/runtime/manifest checks, supported unit race tests, diff/scope verification and independent exact-SHA security review; preserve real Firebase registration/IAM/TLS/staging and paid commerce/catalog/media acceptance as separate prerequisites.

Required PostgreSQL root: `TestPostgresAuthSessionsIntegration`. Exact mandatory subtests:

1. `ConcurrentCustomerProvisionAndRotation`: two independent pools concurrently provision the same project+UID; exactly one account/personal org survives; sessions reference that account; a committed rotation revokes the old cookie; rollback leaves old session valid and no orphan new row. Different project/UID cannot adopt its account.
2. `SharedSessionRevocation`: two actual API/store instances sharing PostgreSQL; B accepts A's session, then rejects after A's logout commit or account block. No fake SQL rows.
3. `ExpiryAndPersistedSecrecy`: expiry boundary/absolute lifetime, hashed32-byte token, allowed identity fields, no raw Firebase/app tokens in persisted rows; stable account survives expiry and restart. Emit assertion outcomes only.
4. `FirebaseExchangeAndUserRevocation`: run real exchange/session HTTP handlers with real PostgreSQL and the actual SDK using the local certificate/user transport; fresh Google token creates session, old app cookie rotates, altered/wrong-project token fails, live fixture user disabled/revoked denies subsequent protected request, lookup outage returns503 with no stale acceptance. Same still-fresh valid ID token re-exchange is allowed; do not mislabel it a failed callback replay.
5. `FirebaseStartupRequiresMigratedPostgres`: full039 starts;038/unavailable pool/memory or missing persistence fail; never auto-migrate the038 database. Local mode remains explicit login-unavailable with no created account/session.

Actual official-SDK signature/user tests use local generated RS256 certificates and isolated transports; fake handler seams are separate evidence. No live Firebase registration, provider call, Docker run, migration or implementation is performed by this planning update. Real project/app/Google-provider/domain/IAM configuration and staging TLS/cookie/two-replica checks remain release prerequisites, not reasons to block deterministic implementation. No production deployment is authorized.

## Historical planning evidence (superseded)

The prior OIDC plan remains recoverable in Git blob `a563bc142ab577b816737483cd766438c371d827` (pre-amendment SHA256 `c1badc2f96e2bf98f6e1c0b9f71da6a5400e07f6d18cab8e52f1bbc5c2991d9d`). Its selected protocol, table design, callbacks,15-minute session policy, broader catalog/media path ownership and issuer-based acceptance are replaced by the Firebase plan. The independently reviewed migration/runtime amendment's original hashes and findings are retained in its revision-history section; that review certifies only its historical planning contract, not the newly amended Firebase implementation. Actual legacy tracking or reviewed prose cannot substitute for the new synchronized record and exact-base gate.
