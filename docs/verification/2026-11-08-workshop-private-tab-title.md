# Workshop private article tab title

`renderArticle()` sets the browser tab title to the purchased article title. `show()` and `clearProtected()` leave that title unchanged, so it can linger after navigating to the index/library or invalidating protected state. The bounded correction restores the existing public Workshop title at those boundaries.

Acceptance and verification:

- [x] A rendered article retains its article-specific title while displayed, then protected-state invalidation restores the public title.
- [x] Navigating away from a private article title restores the public title without changing section visibility.
- [x] Focused red/green regression, full Workshop client/demo Node tests, Go API tests, JavaScript syntax, and diff checks pass on the local candidate after isolated Go rerun.
- [ ] Independent review and required CI pass before integration.

This is local client-behavior evidence, not live account/privacy, paid-access, or production-release acceptance.

The baseline 213 Workshop Node tests and full Go API suite passed before editing. Two actual-function title regressions both failed before the browser edit with the stale `Pump service | AutoData` title, then both passed after it. The full Workshop client/demo Node suite passed (215 tests), as did JavaScript syntax and diff checks. The first full Go suite run concurrently with Node failed one unrelated time-bounded Firebase ADC credential-refresh assertion (`elapsed=4.003641428s`, expected at most 3 seconds); the isolated test then passed three consecutive runs, and a separate full Go API rerun passed (`ok github.com/lucronn/autodata/apps/api-go 9.051s`). The initial failure is retained rather than relabeled as a pass. Exact candidate and CI disposition are tracked in Issue #381 and its PR.

Tracking: [Issue #381](https://github.com/lucronn/autodata/issues/381) under [paid Workshop issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-private-tab-title.md).
