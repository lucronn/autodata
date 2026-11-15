# Restricted staging Firebase tester sessions

Issue: https://github.com/lucronn/autodata/issues/413
Parent: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-workshop-staging-tester-allowlist.md`
Gate: f35aedf (committed/pushed before code); exact-base machine preflight
returned `status:synchronized`, `errors:[]`. Issue/Project goal and todo
readbacks matched. Prospective six-file auth allowlist was retained.

The new immutable config is active only for staging + stripe_test. Nonmember
verified identities cannot reach session/account rotation; every existing
session lookup rechecks configured Firebase(project,UID). Removed testers and
wrong-project cookies fail closed before Firebase user lookup or downstream
commerce. Public production/live/disabled/development/test behavior remains
unchanged. Missing/malformed restricted configuration prevents startup. No
browser/email/header field supplies membership; actual Firebase verification,
revocation/disabled-user, persistence and CSRF checks remain in effect.

Local red-first evidence: the focused staging tests failed against the gated
base for missing/malformed config, production-origin staging, outsider session
rotation and stale-cookie checkout/session access. After the six-file change,
the focused group passes. An initial Go command from repository root failed
because the Go module is under apps/api-go; meaningful red/green runs used the
module directory.

Validation on the implementation candidate:

- Full Go API `go test ./... -count=1`: passed (including new strict config,
  exact membership, verified-login-before-rotation, stale session/project,
  environment immutability, unaffected-mode and Firebase revocation cases).
- Workshop client `node workshop-client.test.mjs`:261 tests passed,0 failures.
- Focused Go `-race` checks for staging testers, auth/session, official Firebase
  SDK and bounded ADC/revocation behavior: passed.
- Pinned-base preflight and `git diff --check`: passed.

The tests inject existing verifier/store fixtures and local transports; there
were no genuine Firebase, Stripe, supplier or licensed-data requests. Existing
integration tests retain their opt-in requirements; no new PostgreSQL/runtime
acceptance claim is made. No secrets, service, DNS, database, order or grant
changes. Independent exact-head review and required CI remain pending; code
merge alone does not complete398's restricted real-data browser acceptance.

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
