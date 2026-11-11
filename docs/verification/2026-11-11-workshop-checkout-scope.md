# Workshop checkout scope isolation

Goal: A rapid change of selected vehicle must not make a new purchase action
reuse the previous vehicle's in-flight Checkout response. This is tracked in
[Issue #396](https://github.com/lucronn/autodata/issues/396) and
[Project #8](https://github.com/users/lucronn/projects/8).

The existing client stores one idempotency attempt in session storage and
deduplicates all overlapping `createCheckout.start` calls with one global
promise. A controlled reproduction with two valid configuration IDs returned
the same promise and made only the first configuration request. The Workshop
navigation aborts the old operation, so this generally fails rather than
redirecting to the wrong Stripe session, but the second vehicle's purchase
does not start until a user retries. Starting both requests concurrently
would also let their completions overwrite the one saved attempt out of order.

Acceptance:

- [x] Concurrent starts for the same configuration and region share one
  request and idempotency key, as before.
- [x] A start for a different configuration or region waits for the current
  request to settle, then sends its own scope/body and a distinct saved key;
  it never receives the earlier scope's Checkout response.
- [x] An aborted queued start sends no Checkout request. A replacement start
  after an aborted same-scope request may reuse the saved idempotency key.
- [x] The client continues to validate the server response and hosted Stripe
  URL, and stores no CSRF value. No server, Stripe, price, order, grant, or
  production setting changes.
- [ ] Red-first Workshop client tests, exact-head independent review, current
  required CI, and live branch protection pass before merge. This is client
  behavior verification, not a live paid-access acceptance claim.

Todo: commit the synchronized plan/record, run exact-SHA preflight, add the
red-first regression, implement the bounded client fix, run relevant suites,
review the exact head, and integrate only after all applicable gates pass.

Local verification on 2026-11-11:

- Planning-only checkpoint `faf611733a0fa4a62e345b6ba54707bec10a3279`
  passed exact-SHA machine preflight with `status: synchronized`, `errors: []`.
- The three new Checkout tests failed against the original global in-flight
  promise: a second configuration received the same promise, an aborted queued
  selection did not reject, and a replacement after an old navigation abort
  made no second request. All three passed after the bounded change.
- Direct Workshop client tests: 258 passed, 0 failed, 0 skipped. Demo tests:
  4 passed, 0 failed, 0 skipped. The Node file-level runner passed both files.
- The guarded paid-access, real browser, and live Stripe acceptance inventories
  are not established by these client tests. Independent exact-head review,
  current required CI, and branch protection remain pending.
