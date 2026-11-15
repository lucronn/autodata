# Workshop staging tester restriction

Goal: Restrict segregated staging Stripe TEST sessions to a server-owned Firebase project and UID allowlist.
Issue: https://github.com/lucronn/autodata/issues/413
Parent: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-workshop-staging-tester-allowlist.md`

The restriction applies only to staging + Stripe TEST. Immutable server JSON UID configuration binds the configured Firebase project. Normal signed-token verification precedes audience checking; audience checking precedes account/session rotation and applies to every stored-session lookup. Missing/malformed/empty restricted configuration fails startup. Production and other modes retain ordinary behavior. Browser/email/header values never supply audience authority. Implementation is code only; runtime acceptance remains separate.

Concrete todo:
- [x] Synchronize plan, Issue413, Project8 and canonical documentation; pass exact-base preflight
- [x] Add red-first strict staging configuration, login-before-rotation and every-session stale-cookie denial regressions
- [x] Implement immutable server UID restriction only in staging Stripe TEST mode without production effects
- [ ] Run focused and full relevant tests, independent exact-head review and required CI; retain separate runtime and licensed-data acceptance gates


For an explicitly segregated staging Stripe TEST process, configure
`AUTODATA_WORKSHOP_TESTER_UIDS_JSON` as a JSON array of1..100 exact Firebase UID
strings. Each is bound to the already configured Firebase project. Missing,
empty, duplicate, malformed, invalid-Unicode or oversized input fails startup
with a fixed redacted error. The list is read once; replacing configuration and
restarting the process removes a tester's access even if an old session cookie
still exists. A verified nonmember gets403 before account/session rotation;
every subsequent authenticated lookup enforces the same restriction. Normal
Firebase revocation/disabled checks and CSRF remain active for approved testers.
No audience list is exposed in auth/config. Other environments and commerce
modes ignore this setting and preserve their existing behavior.

Verification: `docs/verification/2026-11-14-workshop-staging-tester-allowlist.md`.
This does not approve credentials, supplier rights, testers, staging startup,
HTTPS routing or any payment/grant action.

## Protected-base integration checkpoint

Protected master: `92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a`, tree `0e4038a6bd506fd1349caa0bfa320813106ce5ad` (#412 then #417). Published PR415 implementation: `b7abe2fb358e9d959adddc757d60598fdd7b490f`. This task preserves its six auth-file delta, existing mode boundaries and Firebase(project,UID) authority. Prepare this docs-only checkpoint directly on protected master, synchronize tracking and pass exact-SHA preflight before merging into the published branch. Preserve both published histories. Combine documentation evidence with this current checkpoint; stop for coordinator if any application conflict alters reviewed behavior. No provider calls, login/domain updates, staging deployment, runtime credentials or session/payment/order/grant changes. Re-run relevant full/focused/race suites and strict CI, request independent exact-head review and hold merge.

Integration record: `docs/agents/records/2026-11-14-workshop-staging-tester-protected-base.json`

- [ ] Synchronize Issue413, Project8, plan and canonical architecture at protected master92d81a1 and pass checkpoint preflight
- [ ] Merge the synchronized checkpoint into PR415 preserving the reviewed six-file auth implementation and exact master ancestry
- [ ] Run focused staging audience, full Go API, auth Firebase race and full Workshop client regressions on integrated source
- [ ] Push the protected-base candidate, rerun strict required CI, hand off independent exact-head review and hold merge without runtime or provider actions
