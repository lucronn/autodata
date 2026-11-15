# Workshop staging tester restriction

Goal: Restrict segregated staging Stripe TEST sessions to a server-owned Firebase project and UID allowlist.
Issue: https://github.com/lucronn/autodata/issues/413
Parent: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-workshop-staging-tester-allowlist.md`

The prospective restriction applies only to staging + Stripe TEST. Immutable server JSON UID configuration binds the configured Firebase project. Normal signed-token verification precedes audience checking; audience checking precedes account/session rotation and applies to every stored-session lookup. Missing/malformed/empty restricted configuration fails startup. Production and other modes retain ordinary behavior. Browser/email/header values never supply audience authority. No implementation or runtime acceptance is claimed at this planning checkpoint.

Concrete todo:
- [ ] Synchronize plan, Issue413, Project8 and canonical documentation; pass exact-base preflight
- [ ] Add red-first strict staging configuration, login-before-rotation and every-session stale-cookie denial regressions
- [ ] Implement immutable server UID restriction only in staging Stripe TEST mode without production effects
- [ ] Run focused and full relevant tests, independent exact-head review and required CI; retain separate runtime and licensed-data acceptance gates
