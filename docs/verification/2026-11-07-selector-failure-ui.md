# Selector failure UI verification

Goal: Distinguish Workshop selector loading failures and timeouts from authoritative empty configurations.

Plan: docs/superpowers/plans/2026-11-07-selector-failure-ui.md
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Planning synchronized before implementation. No runtime change.

- [ ] Add failing Go regressions for completed-empty, incomplete-empty and malformed/incomplete configuration scopes.
- [ ] Add actual loadOptions browser-logic tests for timeout, partial, saved-choice and completed-empty outcomes.
- [ ] Keep completed-empty configurations terminal; show incomplete selectors as retryable loading failures while preserving usable rows.
- [ ] Run Go and browser checks, obtain independent review, push coherent commits and open a PR; coordinate release separately.

## Implementation evidence

Planning checkpoint `15207c0` was pushed before implementation and machine preflight returned `status: synchronized`, no errors. Issue comment `6701702203` and dedicated Project field `Selector failure UI reference` were read back.

- Go regression initially failed: completed-empty response reported `complete=false/hydrating=true`.
- Actual `loadOptions` + `operation` tests initially failed for empty/partial timeout, nonhydrating incomplete responses and falsely unavailable saved choice.
- Commits `582bdbe` and `c490471` implement the bounded fix. No fabricated rows or provider error details.
- `/home/corp/go-sdk/bin/go test ./...` in `apps/api-go`: passed, 8.629s.
- `node --test workshop-client.test.mjs workshop-demo.test.mjs`: 196 passed, 0 failed.
- `git diff --check`: passed.

Accessibility guidance: reuse the existing error live region and native Retry button. The retrieved accessibility guide says “Announce dynamic errors via live regions”; loading updates do not add new announcements.

Independent review and GitHub CI are pending. No runtime change, merge or deployment performed by this task.
