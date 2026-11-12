# Workshop Firebase ADC refresh deadline

Issue: https://github.com/lucronn/autodata/issues/402
Project: https://github.com/users/lucronn/projects/8
Verification: `docs/verification/2026-11-12-workshop-firebase-adc-refresh-timeout.md`

## Goal

Keep Workshop sign-in and paid-content revalidation responsive when Firebase's SDK retries a user lookup while Application Default Credentials (ADC) are slow. A canceled request or the existing two-second verifier budget must return a dependency error promptly without accepting an unverified identity.

## Root cause and bounded design

The Go OAuth2 transport calls `TokenSource.Token()` without passing the SDK HTTP request context. The ADC token source retained a startup-independent context on purpose, so an SDK retry can start a second credential refresh just before the request deadline and continue past it. The two-second credential HTTP-client timeout applies to each refresh, not to the full verifier call. The existing five-second token-delay fixture passed 20/20 locally on this base, while Issue #402 records intermittent two-request, four-second failures on earlier exact SHAs. A deterministic two-attempt regression is needed.

Keep the official Firebase Admin SDK, signature/revocation/user checks, existing ADC context and per-refresh HTTP timeout. Wrap each SDK call with a verifier-owned completion channel and select on its existing caller-derived two-second context, so the API denies promptly when the SDK is still finishing a retry. Bound concurrent in-flight SDK calls per verifier to prevent timed-out requests from creating unbounded background work; release a slot when the SDK actually finishes. Do not cache or fabricate verified identities, alter the grant/payment path, or relax the existing timeout assertion. This is a local API-sign-in reliability fix, not an architecture or production configuration change.

## Tech stack and files

Go 1.26, Firebase Admin SDK v4, oauth2 ADC, standard `context`/`sync`/`net/http`. Change only `apps/api-go/auth_firebase.go`, `apps/api-go/auth_firebase_test.go`, and the planning/verification documents for this issue.

## Concrete todo

- [x] Synchronize this plan, Issue #402, Project #8, verification document and record at committed pinned base `9d73b762bc3b4c75cbf16991de089e8904defdb2`; machine preflight returned `status:synchronized`, `errors:[]` before Go edits.
- [x] Add a red-first SDK fixture regression with two slow credential refreshes after a retryable user lookup, plus a canceled-caller case. Baseline failures were 3.206 seconds/two token calls and a still-blocked canceled caller; the real SDK and token source remain in the fixture.
- [x] Implement the request-deadline guard and bounded in-flight work around SDK calls, preserving official Firebase checks and startup-independent ADC refresh.
- [ ] Run focused repeated auth tests, full Go suite repeatedly, race checks where feasible, `go vet`, diff checks, independent exact-head AI review, and required CI.
- [ ] Merge only after current repository policy and branch protection pass; update Issue #402 and Project #8 with exact evidence. Do not infer live Stripe/demo or Firebase staging acceptance from local tests.
