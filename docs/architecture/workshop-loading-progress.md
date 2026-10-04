# Workshop loading progress

The workshop reports loading as a six-stage client workflow:

1. Years: 0–10%
2. Makes: 10–30%
3. Models: 30–50%
4. Engine / trim: 50–65%
5. Article catalog: 65–95%
6. Article: 95–100%

The ranges are intentionally fixed and deterministic. They represent the work the browser is doing, not a claim about upstream provider progress. A complete API response moves the current stage to its range end. When the API returns a partial, hydrating response, polling attempts move the indicator within the current range and stop below the end until the response is complete. A timeout remains an error and never becomes a false 100% success.

The status line contains the operation name, the stage number, the percentage, and a short detail such as the number of rows already available or the current polling attempt. The same values are exposed through the native `progress` element's accessible name and value. Cancellation, parent-selection changes, errors, and route replacement clear the active progress state so an old request cannot appear to be making progress for a new vehicle.

Tracking: https://github.com/lucronn/autodata/issues/113 in https://github.com/users/lucronn/projects/8.
Plan: `docs/superpowers/plans/2026-09-25-workshop-loading-progress.md`.

Todo: deterministic stage model and accessible progress UI; connect all catalog/article requests and bounded hydration polling; focused tests and live browser verification.
