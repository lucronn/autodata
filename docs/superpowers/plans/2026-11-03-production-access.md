# Production Identity and Access Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task, after the machine preflight passes. Planning does not authorize implementation.

**Goal:** Replace local production identity defaults with verified identity and secure Workshop sessions, preserving existing shared-catalog roles and organization-owned dataset entitlements across source, canonical, progress, and media reads.

**Architecture:** Extend the existing `Authenticator` and `Principal` boundaries. Use standards-based OIDC authorization-code login with PKCE and server-side PostgreSQL sessions for same-origin browser reads; optionally accept verified JWT access tokens for API clients from the same explicitly registered issuer/resource audience. Reuse existing stores and R2/R3 lifecycle/policy boundaries.

**Tech Stack:** Go 1.26, maintained OIDC/OAuth2 libraries (`github.com/coreos/go-oidc/v3`, `golang.org/x/oauth2`, pinned in go.mod/go.sum during implementation), PostgreSQL, existing Compose/Kubernetes configuration. No custom JOSE implementation.

**Spec:** `docs/superpowers/specs/2026-11-03-source-fallback-web-design.md`, especially its production-authentication and media sections; release design `docs/superpowers/specs/2026-11-03-production-release-orchestration-design.md`.

**Inspection base:** `0ed449fe5119484f8dd8f40b40607aa3beb11e49`.
**Project:** https://github.com/users/lucronn/projects/8
**Issue:** https://github.com/lucronn/autodata/issues/186
**Status:** Reviewed plan with verified Issue/Project tracking. R5 remains blocked until the R3 checkpoint, external identity registration contract and fresh synchronized task preflight are resolved. No live identity verification is claimed.

## Global constraints and repository evidence

- All later implementation, verification, and review agents use `gpt-6.1-sol`, `medium`, Fast mode (`service_tier = "fast"`, request tier `priority`), with no fallback.
- `SECURITY.md` requires explicit security/audit verification for access and entitlement changes. Keep sensitive findings private; no credentials, licensed payloads, or vulnerability reproduction payloads in public tracking or artifacts.
- `requests.go` defines `Authenticator.Authenticate(*http.Request) (Principal, error)`, organization and role fields, and the existing role names `dataset_viewer`, `data_reviewer`, `ingestion_operator`, `platform_admin`. `main.go` installs the local adapter in the executable. Workshop reads a local-storage token and supplies a demo default.
- `docs/architecture/infrastructure-and-dev.md` specifies issuer, audience, role claim and key-set configuration, but no issuer/client registration, verified adapter, login gateway, or session implementation exists in inspected deployment configuration or Go dependencies. OIDC is the selected repository-compatible new integration, not a claim that a deployed identity provider already exists.
- `catalog_store.go` has a shared catalog without organization ownership or a catalog purchase relation. Dataset/request stores separately enforce organization ownership and existing entitlements. Do not introduce catalog billing, infer entitlements from roles, or equate source-connector credentials with user identity.
- R2 provides `catalog_article_current`, scoped aliases and takedown/review state. R3 provides source/canonical projections and image localization. Denied/quarantined/withdrawn content cannot become available through fallback. Existing `UNREVIEWED` display remains honest; do not require a newly invented blanket approval rule.
- No production deployment, user provisioning, payment changes, unrelated admin UI, broad middleware/store rewrite, or provider credential changes. Health probes and public static shell assets remain usable without exposing protected content.

## Required external configuration and fail-closed contract

The maintainer/deployment owner must provide a real HTTPS issuer supporting discovery, authorization code + PKCE S256, signed ID tokens and a registered confidential web client. Register exactly `<AUTODATA_PUBLIC_ORIGIN>/auth/callback` and the same-origin Workshop return location. Provide an organization UUID claim and explicit role mapping controlled by that issuer. If API bearer access is enabled, separately register the API resource audience and confirm signed JWT access-token support; opaque access tokens are unsupported in this lane. No provider brand or deployment target is invented.

Proposed exact runtime names:

| Name | Required value/behavior |
| --- | --- |
| `AUTODATA_ENV` | `development`, `test`, `staging`, or `production`; missing/unknown fails startup. |
| `AUTODATA_AUTH_MODE` | `oidc` in staging/production; `local` permitted only with explicit development/test environment. Missing mode fails startup. |
| `AUTODATA_PUBLIC_ORIGIN` | One HTTPS origin in staging/production; callback derived from this value, never request Host/forwarded headers. |
| `AUTODATA_OIDC_ISSUER` | Exact HTTPS issuer; discovery issuer must match. Discovery/JWKS fetches have timeouts and bounded response sizes. No request-selected issuer or key URL. |
| `AUTODATA_OIDC_CLIENT_ID` / `AUTODATA_OIDC_CLIENT_SECRET` | Registered web client ID / secret-manager supplied secret; never sent to browser or logged. |
| `AUTODATA_OIDC_ORG_CLAIM` / `AUTODATA_OIDC_ROLES_CLAIM` | Explicit top-level claim names; org must be a UUID, roles an array of strings. Missing/type-invalid claims deny identity. |
| `AUTODATA_OIDC_ROLE_MAP_JSON` | Explicit issuer-role to existing AutoData-role map; unknown external roles grant nothing. `platform_admin` requires an explicit mapping. |
| `AUTODATA_AUTH_BEARER_ENABLED` | Defaults false; explicit true also requires `AUTODATA_OIDC_API_AUDIENCE`. No unverified/opaque bearer fallback. |
| `AUTODATA_OIDC_API_AUDIENCE` | Exact registered API audience; required only for verified bearer mode. |

Require asymmetric RS256 token signatures for the first bounded integration; the external issuer must support it. Reject other algorithms, missing/incorrect issuer or audience, missing subject/expiry, expired tokens, future `nbf`, and unreasonably future `iat` (60-second clock allowance). Verify ID-token nonce and client audience in the callback; API access tokens require the API audience. Never accept an ID token solely because it has the web client audience at a bearer API boundary. API access tokens additionally require `iat` and `exp - iat <= 900` seconds. JWT role/organization claims are used only after signature and claim validation. Obtain keys from the configured issuer discovery metadata; no token-supplied key locations. Refresh unknown keys once with bounded concurrency; unsuccessful verification denies access. Pin chosen library versions and verify these behaviors with a local issuer fixture, including rotation.

Sessions have a 15-minute absolute lifetime capped by the verified ID-token expiry, no refresh-token storage and no silent extension. A subsequent login obtains current identity claims. Role/membership revocation for bearer credentials is bounded by issuer token lifetime; require a maximum 15-minute access-token lifetime in the registration. Dataset entitlement and article takedown decisions are rechecked on each read. A deployment demanding faster global identity revocation must provide a revocation integration in a separately planned extension; do not claim instant issuer revocation from offline JWT validation.

Missing registration or configuration blocks staging/release; it never enables local/demo identity. OIDC discovery failure at startup blocks production readiness/startup. Session-store failure denies requests with sanitized retryable service-unavailable errors. No credential or token fragment appears in errors, metrics labels, correlation logs, traces, or session evidence.

## Frozen R4 backend/session contract

R5 owns the backend; R4 owns all Workshop edits after this contract is integrated. No R5 edits under `workshop/`.

- `GET /auth/session`: `200 {"authenticated":true,"roles":[...],"expires_at":"<RFC3339 UTC>","csrf_token":"<opaque>"}` for a valid session; `401` with the existing `UNAUTHENTICATED` error envelope otherwise. Derive the CSRF token deterministically as base64url(HMAC-SHA256(key=raw session token, data="autodata/csrf/v1")); reconstruct server-side and compare in constant time, permitting multiple tabs without storing another secret. No bearer token, provider claims, user PII, or organization selector is returned. Always `Cache-Control: no-store`.
- `GET /auth/login`: creates a 5-minute single-use server-side state/nonce/PKCE transaction and redirects to the configured issuer. Fixed return `/workshop/`; reject arbitrary return destinations. A Secure/HttpOnly/SameSite=Lax transaction cookie binds the callback to the initiating browser.
- `GET /auth/callback`: validate state, transaction cookie, nonce, code exchange and ID token; consume the transaction exactly once, rotate any old session, create a new opaque session and `303` to `/workshop/`. Failures expose fixed safe copy without provider bodies or query credentials. Clear the transaction cookie.
- `POST /auth/logout`: require same-origin `Origin` and `X-CSRF-Token`, revoke the database session, expire cookie, return `204`. No provider global-logout claim. The token from `/auth/session` is also required on all cookie-authenticated state-changing API requests, together with same-origin Origin validation. Login initiation does not switch accounts without the bound callback transaction.
- Cookie name `__Host-autodata_session`; random 256-bit value, `Secure; HttpOnly; SameSite=Lax; Path=/`, no Domain attribute. Persist only SHA-256 session-token hashes, issuer/subject/org/roles, expiry and revocation metadata. PostgreSQL enables consistent logout/revocation across API replicas. Never persist OAuth access/refresh tokens or the raw ID token.
- Production API authentication accepts either this cookie or an explicitly enabled verified API bearer. If Authorization is supplied and invalid, deny rather than falling back to a cookie. Client role/org headers and token-shaped query parameters are ignored. Add verified issuer and subject to `Principal` without changing existing handler role names.
- R4 bootstrap uses `GET /auth/session` with same-origin credentials, shows a sign-in action to `/auth/login` on 401, and calls catalog/source/media with same-origin cookies. Remove demo-token/localStorage production assumptions. Auth 401 stops polling and requests sign-in; 403 retains access-denied behavior. Logout clears rendered protected content and cancels polling. An `<img>` needs no JavaScript Authorization header.
- Deterministic R4 browser fixture intercepts exactly `/auth/session`, `/auth/login`, `/auth/callback`, `/auth/logout` as relevant to each scenario, and catalog/media routes. Supply the exact successful session JSON above, expired-session 401 and denied-role 403 fixtures; no external identity network is permitted in those tests. R5's separate local-issuer tests exercise real redirect/callback/session behavior.

## Access and media contract

Shared catalog selectors, article index/detail/source and embedded processing metadata require a verified `dataset_viewer` or explicitly mapped `platform_admin`. Shared catalog access by another entitled-role organization is allowed by design. Organization-owned requests/datasets/evidence retain existing store checks and denial codes; reviewer/operator roles cannot become viewers implicitly. Test cross-organization denial on those owned resources, not a fabricated ownership restriction on the shared catalog. Raw source/job administrative reads must not expose extra fields through the reader role. There is no new public job-management route.

R3 and R5 serialize changes to `main.go`, `catalog_http.go`, `catalog_store.go`, `catalog_media_token.go` and source/media tests. R5 takes the post-R3 base and freezes these interfaces before R4 completion:

```go
// New policy boundary; R3 supplies the immutable association lookup through its store.
type CatalogMediaScope struct {
    VehicleID, ArticleID, SourceRevisionID, OrganizationID, ObjectKey string
    ExpiresAt time.Time
}
type CatalogMediaAuthorizer interface {
    AuthorizeCatalogMedia(context.Context, Principal, CatalogMediaScope) error
}
```

Use a new versioned authenticated-encrypted opaque token carrying that scope, with a five-minute maximum expiry and a distinct AEAD additional-data version. Keep object keys/provider refs absent from public JSON. Mint only after an authorized article/source projection; bind to exact vehicle/article/source revision and organization. The source revision also binds media used by its canonical rewrite. At media retrieval, first authenticate and require viewer role, then decode/validate expiry and org, then re-read current rights/takedown policy and exact stored article→revision→asset association before opening S3. Unknown/mismatched association returns 404, existing authorized withdrawn content returns 410, unauthenticated returns 401, role denial 403, unavailable policy/storage dependencies return sanitized 503. An encrypted locator alone is not access authority. Reusing content-addressed bytes in another article does not transfer rights. R2/R3 must expose the association; absence fails closed, not object-key-only serving.

Do not accept legacy object-key-only v1 references in production; reloading detail mints new references. Preserve the opaque route `/v1/catalog/images/{token}`. Retain R3 media type/CSP isolation. Set protected catalog/source/media `Cache-Control: private, no-store`; intermediaries cannot reuse protected responses or turn revocation into a stale-cache read. Existing downloaded/displayed bytes cannot be recalled, but subsequent network reads must obey current policy. Media URL expiry uses R4's bounded renewal contract: one coalesced automatic authorized detail refetch per selection/view revision, reconciling URLs by stable asset ID without replacing unchanged content. Repeated failures stop with manual refresh; denial, withdrawal or changed selection cancels renewal. Completed-detail renewal never calls a provider/model or schedules ingestion.

## Bounded implementation file ownership

Create:
- `apps/api-go/auth_config.go`, `auth_oidc.go`, `auth_session.go`, `postgres_auth_sessions.go`, `auth_http.go`, `catalog_access.go`.
- Matching tests: `auth_config_test.go`, `auth_oidc_test.go`, `auth_session_test.go`, `postgres_auth_sessions_test.go`, `auth_http_test.go`, `catalog_access_test.go` in `apps/api-go/`.
- `db/migrations/039_production_identity_sessions.sql`, after the serialized R2 migrations 037/038; if the integrated sequence differs, stop and have the coordinator re-pin an updated path before builder dispatch.
- `scripts/dev/production_access_smoke.py`, `scripts/dev/test_production_access_smoke.py`, `docs/verification/production-access-runbook.md`.

Modify only as needed:
- `apps/api-go/{main.go,requests.go,catalog_http.go,catalog_store.go,catalog_media_token.go,catalog_media_test.go,main_test.go,api_test.go,go.mod,go.sum,openapi.json,openapi.yaml}` for configured adapter wiring, Principal metadata, media association enforcement and documented session/auth/error behavior. Preserve injected local authenticators in unit fixtures; the executable must use explicit configuration.
- `infra/compose/{compose.yaml,compose.ci.yaml}`, `docker-compose.base44.yml`, `.env.base44-defaults` for explicit development/test mode only; never copy identity secrets or bank credentials into compose environment. `infra/k8s/base.yaml` declares production/oidc mode and external configuration/Secret references without values or fake issuer/client defaults.
- `scripts/dev/{test_migrations.py,test_k8s_manifests.py,test_api_runtime.py}` and `docs/architecture/{infrastructure-and-dev.md,workshop-interface.md}` for migration enumeration, runtime/deployment checks and the session contract.

The migration creates `auth_login_transactions` (hash identifier, hashed cookie binding, nonce, PKCE verifier, expiry, consumed state) and `auth_sessions` (token hash, verified identity/role fields, expiry, revoked timestamp); indexes expiry, makes transaction consumption atomic and expires/reaps records. PKCE verifiers remain protected server-side until consumed. Do not store credentials or create new user/billing tables. Implement session lookup/revocation through narrow injected store interfaces so handler tests need neither production credentials nor an external issuer.

## Concrete todo and deterministic acceptance

- [ ] **1. Gate/contract checkpoint:** Coordinator synchronizes the actual Issue, Project #8 item, canonical docs, exact todo and committed planning record. Re-pin after R2/R3 integration; verify preflight before code. Confirm the external issuer registration contract above and R4 session handoff. Missing external configuration is recorded separately from implementable deterministic work.
- [ ] **2. Identity configuration/verifier:** Add failing table-driven tests for missing/unknown env/mode, staging/production local mode, malformed/unsigned/forged/wrong-algorithm JWT, wrong issuer/audience, expired/future claims, missing subject/org/roles, unknown role, discovery failure and key rotation; then implement the configured adapter and production executable wiring. Use an in-process local issuer and generated test keys, never live tokens. An unconfigured binary must fail closed. Run `go test ./...` in `apps/api-go`.
- [ ] **3. Browser/session boundary:** Add failing handler and real-PostgreSQL tests for the complete code+PKCE flow, state/nonce mismatch, replay, transaction expiry, rotation, cookie attributes, session expiry/revocation across two server instances, logout CSRF/origin rejection, invalid Authorization with a valid cookie, and sanitized dependency errors. Implement migration/stores/routes, enforce CSRF on cookie-authenticated mutations and prove persisted records contain no raw session/ID/access/refresh tokens. Run the Go suite and clean/upgrade migration fixtures using the existing local migration runner before exposing this contract to R4.
- [ ] **4. Access/media:** Add deterministic reader/reviewer/operator/admin principals across two organizations. Exercise source, canonical, source-review, processing and media before/after withdrawal; wrong article/revision/asset/org token scope, tampering, expiry and replay after session revocation; dataset entitlement revocation and cross-org request/dataset/evidence denial. Prove unauthorized reads issue zero hydration/model/S3 calls, shared catalog remains role-based, and revoked media cannot be served from API caches. Implement current-policy media checks and update both OpenAPI formats. Run `go test ./...` and `go test -race ./...` in `apps/api-go`.
- [ ] **5. Deployment/runbook and independent audit:** Update explicit local/test opt-ins and production config checks, document secret-manager names and registration checklist, and add a smoke collector that emits only candidate SHA, safe fixture identifiers, outcomes and timestamps. Run `python3 -m unittest discover -s scripts/dev -p 'test_migrations.py'`, corresponding `test_k8s_manifests.py`, `test_api_runtime.py`, and `test_production_access_smoke.py`; run `git diff --check`. Review the exact SHA independently for identity validation, session/CSRF isolation, access rechecks and credential redaction. Give R4 the committed contract; R4 owns JS edits and browser acceptance.

All new tests first demonstrate the missing behavior, then pass on the implementation. Avoid broad synthetic payloads in public evidence. No check is counted passed without actual command output. Preserve test/fixture-local HTTP only in test mode; production requires HTTPS. The migration tests must run against real PostgreSQL, not an in-memory substitute. Dependency availability failure, unavailable DB or missing browser engine is reported as unavailable rather than successful evidence.

## Separate staging evidence and unresolved prerequisites

After deterministic tests and independent review, R6 runs the reviewed candidate in staging with the registered real issuer, HTTPS origin, external secrets and isolated accounts in two organizations. Verify actual browser login/logout, session expiry, mapped viewer/reviewer/operator/admin behavior, a rejected audience/issuer, dataset entitlement revocation, source/canonical transitions from both banks, source-review access and withdrawal denying old media URLs. Verify two replicas share revocation state and ingress/logging do not record callback codes, cookies or bearer credentials. Retain only safe IDs and exact-SHA outcomes in the release record; protected identity/source proof stays in the restricted evidence store. A health endpoint, local issuer, fixture token or connector canary cannot certify user identity integration.

Concrete prerequisites still unresolved at planning time: actual issuer URL, web-client registration/secret, staging/public origin and callback allowlist, issuer organization/role claim names and role mapping, API audience/JWT access-token capability if bearer access is requested, and real test-account provisioning. These are external configuration decisions; none can be inferred from bank credentials. Without them R5 cannot be marked production-verified. If the selected issuer cannot supply this contract, revise and synchronize this plan before implementation rather than inventing an alternate gateway. Deployment remains outside current authority.
