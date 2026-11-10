# Workshop purchase availability status

On the planning base, when a selected vehicle's article index returned `ENTITLEMENT_REQUIRED`, Workshop announced “This vehicle is available to purchase” even if its quote was not loaded or was invalid. In that state the rendered Buy action was disabled and the purchase section explained that purchasing was unavailable. The activity status must agree with the actionable UI. A valid exact-scope quote and configured merchant must keep the existing purchase invitation. A sign-in action must invite sign-in, and a validated, unresolved exact-scope order must continue to say confirmation is pending and not invite repayment.

Acceptance and verification:

- [x] Actual-function regression reproduces the missing-quote contradiction before the app change and passes after it.
- [x] Invalid merchant configuration, sign-in, and validated processing-order controls do not announce a new purchase when Buy is not available.
- [x] Valid quote/configuration control retains the available-to-purchase activity status.
- [x] Focused/full Workshop Node, Go API, syntax, diff, and independent review evidence is recorded at original app candidate `832d955`.
- [x] Required GitHub CI passed at `832d955` in run 42551285320.
- [ ] The final policy-base candidate receives current exact-head review and CI before merge.

Scope: client-only Workshop feedback. No change to quote validation, checkout, order, payment, grant, authentication, schema, or architecture. No production deployment or live payment is authorized.

Tracking: [Issue #388](https://github.com/lucronn/autodata/issues/388), [parent Issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-purchase-availability-status.md).

The written single-maintainer review rule is on protected `master` at
`fd1a877e68c23c8441be674cacfba43a8f4189e3`, tree-identical to reviewed
policy candidate `a442cfb`. GitHub left policy PR #390 unmarked as merged after
a 502 response, so its duplicate PR record was closed with an exact-tree
integration note. This does not waive current exact-head review or CI for the
Workshop app candidate.

Planning checkpoint `8303196087424cf9197f06f81f5dbc69fbe46bae` passed exact-SHA preflight with `status: synchronized` and `errors: []` before the app/test change. On that baseline, the actual-function focused run had three expected failures: no quote, no merchant configuration, and an unresolved validated order all received “This vehicle is available to purchase.” The valid-quote control passed. After the first client-only status change, the signed-out control exposed one more false purchase invitation despite the action saying Sign in. The final change announces purchase availability only for an enabled Buy action. All five focused tests passed; the full Workshop client/demo Node suite passed (253 tests), the isolated Go API suite passed (`ok github.com/lucronn/autodata/apps/api-go 8.553s`), and JavaScript syntax plus `git diff --check` passed. Independent read-only review of exact head `832d9558370d85ef9f5f154cfe98e26954614cf1` found no Critical, Important, or Minor findings; required [CI run 42551285320](https://github.com/lucronn/autodata/actions/runs/42551285320) passed all three jobs at that head. This is not a GitHub approval. Final integration after the review-policy base advances still requires fresh exact-head review and CI. These tests do not establish live payment, grant, article-access, or production readiness.
