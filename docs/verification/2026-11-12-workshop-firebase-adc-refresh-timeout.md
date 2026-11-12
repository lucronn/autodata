# Workshop Firebase ADC refresh deadline verification

Issue: https://github.com/lucronn/autodata/issues/402
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-12-workshop-firebase-adc-refresh-timeout.md`

## Scope and evidence to collect

This task addresses the Workshop customer sign-in/revalidation latency regression in Issue #402. Firebase Admin SDK identity, signature, revocation and live user checks remain authoritative. ADC must outlive the startup context, but a caller's canceled or expired request must not wait for SDK credential retries. The dependency must fail closed. No Stripe mode, grant, provider rights, production service, DNS or live traffic changes are in scope.

Concrete todo:

- [x] Planning checkpoint `9d73b762bc3b4c75cbf16991de089e8904defdb2` committed; exact-base pre-implementation validation returned `{"status":"synchronized","errors":[]}` before Go edits.
- [x] Red-first SDK fixture: two 1.6-second token refresh attempts after a retryable 503 user lookup returned only after 3.206 seconds; caller cancellation remained blocked beyond 500 ms. After the fix, the retry, cancellation and bounded-admission tests passed three consecutive runs with the official SDK and real ADC token source, replacing only network endpoints.
- [x] Record repeated focused/full Go, race/vet, independent exact-head review and current CI results below.
- [x] Record the merged SHA and Project/Issue disposition below. Project #8 was still Review at the code merge; documentation closeout is the remaining gate before Done.

The prior five-second token fixture passed 20/20 on local `origin/master` `74cc9e1` during this run; this does not erase the earlier intermittent failure recorded in Issue #402 and does not prove the race absent. The new deterministic regression covers the two-attempt path. Real Firebase staging acceptance remains separately required.

Local Go API `go test ./... -count=2` passed after the implementation and new regressions. Focused new regressions passed three consecutive runs; `go test -race . -run '^TestFirebase(ADC|TimedOutSDKCalls)' -count=1`, `go vet ./...`, and shared Go contracts `go test ./... -count=1` passed. These fixture results do not prove live Firebase or paid Workshop behavior.

The independent read-only AI review of `d7630270206bebb3ec829ea9c9a2c559783dd1f8` found no Critical or Important issue and one Minor test gap: the admission test did not prove slots recover after background SDK calls finish. The successor test now drains those calls and requires a new successful admission. That correction passed 20 consecutive focused runs, a repeated full Go API suite (`-count=2`), targeted race, `go vet ./...` and `git diff --check`.

The successor's independent exact-head AI review of `e0e106144a035a831b2bca4a11cdea873c6e45a0` found no Critical, Important or Minor issue. This was a repository review decision under the single-maintainer rule, not a GitHub approval. Required CI run [43144545984](https://github.com/lucronn/autodata/actions/runs/43144545984) passed all three jobs, including `Validate autonomy policy and evidence contract`. The full Go API suite `go test ./... -count=1` and shared Go contracts passed again at that exact head, and pre-implementation validation at pinned planning base `9d73b762bc3b4c75cbf16991de089e8904defdb2` returned `status:synchronized`, `errors:[]`. Branch protection required no GitHub approval, and PR [#403](https://github.com/lucronn/autodata/pull/403) was squash-merged normally on 2026-11-12 at `bfbae458abecdbf89099b15f568142e84ff64db8`. Issue #402 closed automatically; Project #8 remained Review pending this documentation closeout. No live Firebase staging, Stripe test-mode checkout, licensed article access, or production deployment was verified by this fix.
