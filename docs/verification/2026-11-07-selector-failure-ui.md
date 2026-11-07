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
