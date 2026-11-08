# Workshop selector success retry visibility

The real Workshop selector gave `status()` a retry callback after a successful choice load. `status()` unhides the native “Try again” button whenever it receives that callback, so the page displayed a failure affordance alongside a success or completed-empty message.

The scoped correction omits that callback on successful completed or resumable selection reads. Timeout, incomplete, and transport failures retain their existing retry behavior and partial rows. No selector API, checkout, entitlement, or source behavior changes.

Acceptance and verification:

- [x] Completed nonempty and completed-empty selector reads do not show “Try again”.
- [x] A saved row found during partial hydration remains usable without showing “Try again”.
- [x] Timeout, incomplete-without-desired, and transport failures retain visible retry.
- [x] Focused red/green test, full Workshop client and demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.

Evidence: the existing selector cases passed after the harness began using the real `status()`; the new success regression then failed with `false !== true` for `#retry.hidden` before the app change and passed afterward. Both Workshop Node files passed (201 tests), the Go API suite passed, and `node --check` plus `git diff --check` passed.

Tracking: [Issue #373](https://github.com/lucronn/autodata/issues/373) under [paid Workshop parent issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-selector-success-retry.md).
