# Restricted staging Workshop testers

Issue: https://github.com/lucronn/autodata/issues/413
Parent: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Canonical architecture: `docs/architecture/workshop-staging-tester-allowlist.md`

## Goal

Restrict segregated staging Stripe TEST sessions to a server-owned Firebase project and UID allowlist. This is code only: no runtime, secrets, deployment, DNS, payments, provider calls, orders or grants. Coordinate with PR412 by avoiding commerce_client.go.

## Configuration and behavior

Activate the restriction only when AUTODATA_ENV is exactly staging and AUTODATA_COMMERCE_MODE is exactly stripe_test. Require Firebase mode and a distinct non-production HTTPS origin using existing validation. Require AUTODATA_WORKSHOP_TESTER_UIDS_JSON as an immutable startup JSON array containing1..100 unique opaque UID strings, each nonempty, at most128 Unicode characters, not all whitespace and containing no control characters. Limit input to32768 UTF-8 bytes; reject invalid Unicode, null/non-array/non-string entries, duplicates, trailing values and empty/missing/malformed configuration with a fixed redacted authentication configuration error. Do not trim, case-fold, normalize, log or expose UIDs. Project binding is the configured Firebase ProjectID; the signed token and stored session must match it. Read the variable only for the restricted mode; other environments, Stripe live/disabled and production authentication keep existing behavior even if that unrelated variable is present.

Store the parsed allowlist privately in customerAuthConfig, with immutable commerce mode. After normal Firebase verification and freshness/project checks, reject a nonmember before session token generation or store.Rotate, so no account/session is created. Check stored(session.ProjectID, session.UID) immediately after every session lookup, including auth/session, protected routes, checkout and logout; a removed tester or wrong-project existing cookie fails closed before Firebase user lookup or downstream commerce. Constructor defensively rejects restricted configs with empty lists before DB/schema/SDK work. No request email/header/role, browser flag or token custom claim supplies audience membership.

Existing Firebase revoked/disabled-user checks, CSRF, session persistence/rotation, exact-scope payment/grant/source/media checks remain. Config changes require process reconstruction. No hot reload, public config/UID endpoint or fake entitlement. The public demo readiness needs no separate change because a staging Stripe TEST process without this config cannot start.

## Implementation allowlist

- apps/api-go/auth_config.go
- apps/api-go/auth_http.go
- apps/api-go/auth_session.go
- apps/api-go/auth_config_test.go
- apps/api-go/auth_http_test.go
- apps/api-go/auth_session_test.go

Documentation and tracking may be updated after validation. No commerce_client.go, frontend, ingestion, database, infrastructure or runtime files.

## Verification

Observe focused regressions red before implementation, then green. Cover malformed/oversized/duplicate/invalid-Unicode configuration, one/multiple approved UIDs, nonmember verified login with zero Rotate calls/cookies, signed wrong-project identity, approved persisted session, wrong-project or removed-UID existing cookies across lookup modes, downstream protected checkout denial, unchanged ordinary Firebase revocation/CSRF and production/live/disabled/test/development mode behavior. Use existing fake verifier/store and loopback integration; no real Firebase/Stripe calls or secrets. Run full Go API suite, race-focused auth checks, Workshop client tests, syntax/diff/scope checks and pinned-base preflight. Obtain independent exact-head review and required CI before merge. Supplier rights, tester approval, credential validity, isolated runtime and authentic licensed-data/browser acceptance remain separate.

## Concrete todo

- [ ] Synchronize plan, Issue413, Project8 and canonical documentation; pass exact-base preflight
- [ ] Add red-first strict staging configuration, login-before-rotation and every-session stale-cookie denial regressions
- [ ] Implement immutable server UID restriction only in staging Stripe TEST mode without production effects
- [ ] Run focused and full relevant tests, independent exact-head review and required CI; retain separate runtime and licensed-data acceptance gates
