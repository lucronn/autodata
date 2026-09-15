# Vehicle-specific guide label plan

**Goal:** Make every consumer repair guide and generated PDF identify the exact
selected vehicle variant, including available body style, drivetrain, engine,
and provider label details, so a consumer can verify applicability before
starting work.

**Tracking:** [Issue #85](https://github.com/lucronn/autodata/issues/85) and
[Project #8](https://github.com/users/lucronn/projects/8).

**Finding:** The live 1997 RAV4 response resolved the exact 2-door 4WD variant,
but the guide/PDF applicability subtitle was reduced to `1997 Toyota RAV4`.
The structured response retained the exact vehicle, yet the downloadable
consumer artifact did not display that specificity prominently.

## Scope

- Build the public applicability line from the selected vehicle's canonical
  consumer label when available, with a deterministic structured fallback.
- Preserve exact vehicle resolution, source selection, procedure content,
  figures, redaction, and existing title/copy behavior.
- Add regression coverage for exact-label and structured-fallback rendering.
- Re-run the five-case live matrix and visually inspect a generated PDF cover.
- Do not modify user-owned `sample data/`, `output/`, or `tmp/` artifacts.

## Concrete todo

- Add a regression proving the exact selected vehicle variant appears in guide
  applicability.
- Implement the vehicle-specific applicability formatter.
- Run focused and full applicable test suites.
- Re-run the five-case live consumer matrix and verify all generated PDFs carry
  vehicle-specific applicability.
- Record hashes and reconcile Issue #85 and canonical documentation.

## Verification contract

The repair is complete only when the selected RAV4 guide visibly identifies its
2-door 4WD variant, fallback formatting is deterministic, all live cases pass,
and no existing procedure, PDF, or consumer-copy contract regresses.
