# Workshop Firebase ADC refresh deadline verification

Issue: https://github.com/lucronn/autodata/issues/402
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-12-workshop-firebase-adc-refresh-timeout.md`

## Scope and evidence to collect

This task addresses the Workshop customer sign-in/revalidation latency regression in Issue #402. Firebase Admin SDK identity, signature, revocation and live user checks remain authoritative. ADC must outlive the startup context, but a caller's canceled or expired request must not wait for SDK credential retries. The dependency must fail closed. No Stripe mode, grant, provider rights, production service, DNS or live traffic changes are in scope.

Concrete todo:

- [ ] Commit the synchronized planning checkpoint and pass exact-base pre-implementation validation.
- [ ] Preserve a failing two-refresh SDK fixture result before the Go fix; verify cancellation and no accepted identity after the fix.
- [ ] Record repeated focused/full Go, race/vet, independent exact-head review and current CI results.
- [ ] Record the merged SHA and Project/Issue disposition, or the exact remaining blocker.

The prior five-second token fixture passed 20/20 on local `origin/master` `74cc9e1` during this run; this does not erase the earlier intermittent failure recorded in Issue #402 and does not prove the race absent. The new deterministic regression must cover the two-attempt path. Real Firebase staging acceptance remains separately required.
