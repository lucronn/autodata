# Workshop selector failure states

Goal: Distinguish Workshop selector loading failures and timeouts from authoritative empty configurations.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source base: 814a1c26e893fe181327516cfa4b48a800978c43

## Diagnosis and decision

loadOptions ignores readCollection.timedOut and reports empty or ready after its one-minute polling budget. Async provider failures are logged rather than returned by selector GET; do not invent source-error details. Report incomplete/timeout outcomes as choices not finished loading, with retry and retained partial rows. Preserve saved-choice resume if its real row exists; a missing saved choice is only declared unavailable for completed scopes. Authoritative completed-empty configuration scopes must return complete=true/hydrating=false and schedule no hydration. Existing incomplete rows still require hydration even with a scope marker. No synthetic rows, paywall changes, provider changes, runtime changes or architecture expansion.

## Concrete todo
- [x] Add failing Go regressions for completed-empty, incomplete-empty and malformed/incomplete configuration scopes.
- [x] Add actual loadOptions browser-logic tests for timeout, partial, saved-choice and completed-empty outcomes.
- [x] Keep completed-empty configurations terminal; show incomplete selectors as retryable loading failures while preserving usable rows.
- [x] Run Go and browser checks, obtain independent review, push coherent commits and open a PR; coordinate release separately.

## Verification

Go handler tests must cover empty-complete, empty-incomplete, usable markerless and incomplete-row cases. Actual loadOptions VM tests cover partial/empty timeout, nonhydrating incomplete responses, completed empty, saved-choice resume and stale generation. Run node --test workshop-client.test.mjs and go test ./... in apps/api-go. Use existing status live regions and native Retry button; avoid duplicate announcements.
