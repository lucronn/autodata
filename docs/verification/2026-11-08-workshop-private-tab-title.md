# Workshop private article tab title

`renderArticle()` sets the browser tab title to the purchased article title. `show()` and `clearProtected()` leave that title unchanged, so it can linger after navigating to the index/library or invalidating protected state. The bounded correction restores the existing public Workshop title at those boundaries.

Acceptance and verification:

- [ ] A rendered article retains its article-specific title while displayed, then protected-state invalidation restores the public title.
- [ ] Navigating away from a private article title restores the public title without changing section visibility.
- [ ] Focused red/green regression, full Workshop client/demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the exact candidate.
- [ ] Independent review and required CI pass before integration.

This is local client-behavior evidence, not live account/privacy, paid-access, or production-release acceptance.

Tracking: [Issue #381](https://github.com/lucronn/autodata/issues/381) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-private-tab-title.md).
