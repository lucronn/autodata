# Workshop purchase availability status

When a selected vehicle's article index returns `ENTITLEMENT_REQUIRED`, Workshop currently announces “This vehicle is available to purchase” even if its quote was not loaded or is invalid. In that state the rendered Buy action is disabled and the purchase section explains that purchasing is unavailable. The activity status must agree with the actionable UI. A valid exact-scope quote and configured merchant must keep the existing purchase invitation. A sign-in action must invite sign-in, and a validated, unresolved exact-scope order must continue to say confirmation is pending and not invite repayment.

Acceptance and verification:

- [x] Actual-function regression reproduces the missing-quote contradiction before the app change and passes after it.
- [x] Invalid merchant configuration, sign-in, and validated processing-order controls do not announce a new purchase when Buy is not available.
- [x] Valid quote/configuration control retains the available-to-purchase activity status.
- [ ] Focused/full Workshop Node, Go API, syntax, diff, and independent review evidence is recorded at an exact candidate SHA.
- [ ] Required GitHub CI passes; written CODEOWNERS-review policy is reconciled before merge.

Scope: client-only Workshop feedback. No change to quote validation, checkout, order, payment, grant, authentication, schema, or architecture. No production deployment or live payment is authorized.

Tracking: [Issue #388](https://github.com/lucronn/autodata/issues/388), [parent Issue #186](https://github.com/lucronn/autodata/issues/186), [Project #8](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-11-08-workshop-purchase-availability-status.md).

Planning checkpoint `8303196087424cf9197f06f81f5dbc69fbe46bae` passed exact-SHA preflight with `status: synchronized` and `errors: []` before the app/test change. On that baseline, the actual-function focused run had three expected failures: no quote, no merchant configuration, and an unresolved validated order all received “This vehicle is available to purchase.” The valid-quote control passed. After the first client-only status change, the signed-out control exposed one more false purchase invitation despite the action saying Sign in. The final change announces purchase availability only for an enabled Buy action. All five focused tests pass; the full Workshop client/demo Node suite passes (253 tests), the isolated Go API suite passes (`ok github.com/lucronn/autodata/apps/api-go 8.553s`), and JavaScript syntax plus `git diff --check` pass. Independent exact-head review and required CI remain pending. These tests do not establish live payment, grant, article-access, or production readiness.
