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

- [x] Synchronize plan, Issue413, Project8 and canonical documentation; pass exact-base preflight
- [x] Add red-first strict staging configuration, login-before-rotation and every-session stale-cookie denial regressions
- [x] Implement immutable server UID restriction only in staging Stripe TEST mode without production effects
- [ ] Run focused and full relevant tests, independent exact-head review and required CI; retain separate runtime and licensed-data acceptance gates


## Local implementation checkpoint

Planning checkpoint f35aedf was committed/pushed before tests or code and passed
machine preflight with synchronized/errors[]. Issue413 and its Project8 item
were read back with the same goal and concrete todos. The focused regressions
were observed red before implementation: malformed/missing config accepted,
outsider verified login rotated a session, removed tester reached commerce and
wrong-project/UID stale cookies were accepted. Those cases now pass. Final full
Go API suite and261 Workshop client tests pass; focused race checks and exact
review/required CI are tracked in the verification document. No runtime was
changed and no real tester/credential/provider/content acceptance was attempted.

## Protected-base integration checkpoint

Protected master: `5b3e19d3b34208773a77b4b9cfccd3085726cabe`, tree `92da3c0238725728e43a2bbd4df7a0ec29d02de6` (#412, #417, then #421). Published PR415 implementation: `b7abe2fb358e9d959adddc757d60598fdd7b490f`. This task preserves its six auth-file delta, existing mode boundaries and Firebase(project,UID) authority. Prepare this docs-only checkpoint directly on protected master, synchronize tracking and pass exact-SHA preflight before merging into the published branch. Preserve both published histories. Combine documentation evidence with this current checkpoint; stop for coordinator if any application conflict alters reviewed behavior. No provider calls, login/domain updates, staging deployment, runtime credentials or session/payment/order/grant changes. Re-run relevant full/focused/race suites and strict CI, request independent exact-head review and hold merge.

Integration record: `docs/agents/records/2026-11-14-workshop-staging-tester-protected-base.json`

- [x] Synchronize Issue413, Project8, plan and canonical architecture at protected master5b3e19d and pass checkpoint preflight
- [x] Merge the synchronized checkpoint into PR415 preserving the reviewed six-file auth implementation and exact master ancestry
- [x] Run focused staging audience, full Go API, auth Firebase race and full Workshop client regressions on integrated source
- [ ] Push the protected-base candidate, rerun strict required CI, hand off independent exact-head review and hold merge without runtime or provider actions

This final checkpoint supersedes planning-only22b8433 on92d81a1. PR421 is protected-merged at5b3e19d with identical reviewed tree92da3c02; integrate only after this refreshed exact-base gate passes.

## Current protected-base validation

Protected master `5b3e19d3b34208773a77b4b9cfccd3085726cabe`, tree
`92da3c0238725728e43a2bbd4df7a0ec29d02de6`, includes PR412, PR417 and PR421.
Refreshed docs-only gate `8487ec03f57a3827b8a329b956a057919f490127`
was committed/pushed and synchronized to Issue413/Project8; its exact-SHA
preflight returned synchronized/errors[] before integration merge
`673a1ce8fec18c79ca9b873268672b84e4aa6409`. Both published histories were
preserved. Only two documentation add/add overlaps needed resolution; no
application conflict occurred. All six auth-file implementation deltas are
byte-identical to independently reviewed b7abe2f (normalized patch SHA256
`ecebb58d57a9554cdc995a75ba76225bb6bd868eacd057097bec64eccba06e74`).

Fresh integrated-source validation:

- Full Go API `go test ./... -count=1`: passed17.037s.
- Focused auth/Firebase/staging audience `go test . -race -count=1 -run
  'Test(StagingTester|CustomerAuth|OfficialFirebase|FirebaseADC|FirebaseTimedOut)'`:
  passed15.895s.
- All Workshop client tests:262 passed, zero failures.
- Exact gate preflight, ancestry, scope and diff checks passed.

Final exact-head independent review and fresh strict required CI remain merge
gates; terminal results are tracked in Issue413/Project8 to preserve the CI
candidate. No real provider calls, runtime configuration, deployment, DNS,
credentials, production database/grants or public TEST enablement occurred.
The source restriction does not establish actual tester approval, isolated
HTTPS/data/Firebase readiness or genuine TEST settlement/grant/refund.
