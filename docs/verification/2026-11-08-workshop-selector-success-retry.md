# Workshop selector success retry visibility

The real Workshop selector currently gives `status()` a retry callback after a successful choice load. `status()` unhides the native “Try again” button whenever it receives that callback, so the page displays a failure affordance alongside a success or completed-empty message.

The scoped correction will hide retry for successful completed or resumable selection reads. Timeout, incomplete, and transport failures will retain their existing retry behavior and partial rows. No selector API, checkout, entitlement, or source behavior changes.

Acceptance and verification:

- [ ] Completed nonempty and completed-empty selector reads do not show “Try again”.
- [ ] A saved row found during partial hydration remains usable without showing “Try again”.
- [ ] Timeout, incomplete-without-desired, and transport failures retain visible retry.
- [ ] Focused red/green test, full Workshop client and demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.

Tracking: [Issue #373](https://github.com/lucronn/autodata/issues/373) under [paid Workshop parent issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-selector-success-retry.md).
