# Workshop Firebase ADC refresh deadline verification

Issue: https://github.com/lucronn/autodata/issues/402
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-12-workshop-firebase-adc-refresh-timeout.md`

## Scope and evidence to collect

This task addresses the Workshop customer sign-in/revalidation latency regression in Issue #402. Firebase Admin SDK identity, signature, revocation and live user checks remain authoritative. ADC must outlive the startup context, but a caller's canceled or expired request must not wait for SDK credential retries. The dependency must fail closed. No Stripe mode, grant, provider rights, production service, DNS or live traffic changes are in scope.

Concrete todo:

- [x] Planning checkpoint `9d73b762bc3b4c75cbf16991de089e8904defdb2` committed; exact-base pre-implementation validation returned `{"status":"synchronized","errors":[]}` before Go edits.
- [x] Red-first SDK fixture: two 1.6-second token refresh attempts after a retryable 503 user lookup returned only after 3.206 seconds; caller cancellation remained blocked beyond 500 ms. After the fix, the retry, cancellation and bounded-admission tests passed three consecutive runs with the official SDK and real ADC token source, replacing only network endpoints.
- [ ] Record repeated focused/full Go, race/vet, independent exact-head review and current CI results.
- [ ] Record the merged SHA and Project/Issue disposition, or the exact remaining blocker.

The prior five-second token fixture passed 20/20 on local `origin/master` `74cc9e1` during this run; this does not erase the earlier intermittent failure recorded in Issue #402 and does not prove the race absent. The new deterministic regression covers the two-attempt path. Real Firebase staging acceptance remains separately required.

Local Go API `go test ./... -count=2` passed after the implementation and new regressions. Focused new regressions passed three consecutive runs; `go test -race . -run '^TestFirebase(ADC|TimedOutSDKCalls)' -count=1`, `go vet ./...`, and shared Go contracts `go test ./... -count=1` passed. Independent exact-head review, CI and merge remain pending at this checkpoint. These fixture results do not prove live Firebase or paid Workshop behavior.
