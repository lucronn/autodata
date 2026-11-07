# Selector failure UI verification

Goal: Distinguish Workshop selector loading failures and timeouts from authoritative empty configurations.

Plan: docs/superpowers/plans/2026-11-07-selector-failure-ui.md
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Planning synchronized before implementation. No runtime change.

- [x] Add failing Go regressions for completed-empty, incomplete-empty and malformed/incomplete configuration scopes.
- [x] Add actual loadOptions browser-logic tests for timeout, partial, saved-choice and completed-empty outcomes.
- [x] Keep completed-empty configurations terminal; show incomplete selectors as retryable loading failures while preserving usable rows.
- [x] Run Go and browser checks, obtain independent review, push coherent commits and open a PR; coordinate release separately.

## Implementation evidence

Planning checkpoint `15207c0` was pushed before implementation and machine preflight returned `status: synchronized`, no errors. Issue comment `6701702203` and dedicated Project field `Selector failure UI reference` were read back.

- Go regression initially failed: completed-empty response reported `complete=false/hydrating=true`.
- Actual `loadOptions` + `operation` tests initially failed for empty/partial timeout, nonhydrating incomplete responses and falsely unavailable saved choice.
- Commits `582bdbe` and `c490471` implement the bounded fix. No fabricated rows or provider error details.
- `/home/corp/go-sdk/bin/go test ./...` in `apps/api-go`: passed, 8.629s.
- `node --test workshop-client.test.mjs workshop-demo.test.mjs`: 196 passed, 0 failed.
- `git diff --check`: passed.

Accessibility guidance: reuse the existing error live region and native Retry button. The retrieved accessibility guide says “Announce dynamic errors via live regions”; loading updates do not add new announcements.

## Updated release candidate

Independent review passed at reviewed head `2cf62b76be5a0115e5dc72072fb5d3cde1445ea8` (coordinator confirmation). To meet branch protection after PR #366, master `c9c58fcd74e67c07d7014497a6f7433f79cf2ae3` was merged without conflicts at `5220d97ea5f93d49c834ebe2749c96dc866fbee7`, tree `1a0578b30ef6717912f0b1a4561567a79d4d415f`. Every `apps/api-go` blob remains identical to the reviewed head.

Fresh verification after the master merge:

- Pinned planning preflight at `15207c0`: `status: synchronized`, `errors: []`.
- Full Go API suite: passed.
- Workshop client and demo Node suites: 196 passed, 0 failed.
- `git diff --check`: passed.
- Issue #186 and Project #8 dedicated Selector failure UI reference were read back.

Required CI is running on the updated PR. Merge is authorized after required checks pass; deployment remains separately coordinated. No runtime operation was performed.
