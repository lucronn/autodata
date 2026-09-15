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

- [x] Add a regression proving the exact selected vehicle variant appears in guide
  applicability.
- [x] Implement the vehicle-specific applicability formatter.
- [x] Run focused and full applicable test suites.
- [x] Re-run the five-case live consumer matrix and verify all generated PDFs carry
  vehicle-specific applicability.
- [x] Record hashes and reconcile Issue #85 and canonical documentation.

## Verification contract

The repair is complete only when the selected RAV4 guide visibly identifies its
2-door 4WD variant, fallback formatting is deterministic, all live cases pass,
and no existing procedure, PDF, or consumer-copy contract regresses.

## Acceptance evidence

Implementation commit: `256a42f` (`fix: show exact vehicle applicability`).
Focused guide tests passed (`9 passed`). Full verification passed: developer
`73 passed, 2 subtests`; autonomy `37 passed`; ingestion `386 passed, 3 skipped,
12 subtests`; Go API and shared-contract suites passed; and `git diff --check`
passed.

Fresh live report-only matrix passed all five cases at score 100 with zero
findings and zero issue actions. Report:
`tmp/consumer-review-live/vehicle-label-v1/consumer-review-72b81614a35210f063b9cdfb.json`
with SHA-256
`be89b7f8cbcf2954ecf2f146016b8188f0fce3626056c8db37504c7b8bf4ee28`. The
RAV4 PDF cover was rendered and visually inspected; it displays the exact
`1997 Toyota Truck RAV4 2-Door 4WD L4-2.0L (3S-FE)` applicability line.
