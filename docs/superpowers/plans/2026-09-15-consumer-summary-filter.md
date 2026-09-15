# Consumer guide summary-artifact cleanup plan

**Goal:** Keep truncated provider summary rows and provider-only reference
fragments out of the consumer repair guide and its PDF while preserving the
source-backed removal and installation steps.

**Tracking:** [Issue #93](https://github.com/lucronn/autodata/issues/93) and
[Project #8](https://github.com/users/lucronn/projects/8).

**Finding:** Fresh live RAV4, Camry, and Forester consumer outputs contain
`phase: procedure` rows with 180-character ellipsized actions, including
provider references such as `Refer to Figs...`. These rows appear after the
detailed illustrated procedure and are not consumer-ready instructions.

## Scope

- Change only the consumer-guide composition boundary and focused tests.
- Suppress a procedure-phase row when it is an ellipsized/provider summary and
  has no structured instructions or figures.
- Preserve detailed source-backed removal/installation steps and any concise
  procedure step that carries actual instructions or figures.
- Keep the source article, evidence, internal audit data, and legacy quote
  behavior intact.
- Do not modify the user-owned `sample data/`, `output/`, or `tmp/` artifacts.

## Concrete todo

- [x] Add a regression proving truncated provider summaries are omitted while
  detailed and concise procedure steps remain.
- [x] Implement the consumer-summary filter.
- [x] Run focused and full applicable test suites.
- [x] Re-run the five-case live consumer matrix and verify no raw summary or
  ellipsis artifact remains in the consumer response or PDF.
- [x] Render representative pages and inspect layout and final installation/check
  coverage.
- [x] Record hashes and reconcile the GitHub Issue only after fresh evidence passes.

## Verification contract

The repair is complete only when the consumer response and matching PDF contain
no provider-summary ellipsis/reference artifact, retain complete removal and
installation coverage, preserve embedded figures and revision parity, and the
live consumer agent still passes all cases.

## Acceptance evidence

Implementation commit: `2c5e404` (`fix: preserve complete consumer steps`).

Focused guide/PDF tests passed: `9 passed, 3 skipped`. Full verification passed:
developer tests `72 passed, 2 subtests passed`; autonomy tests `37 passed`;
ingestion tests `385 passed, 3 skipped, 12 subtests passed`; Go API and shared
contract tests passed; and `git diff --check` passed.

Fresh live report-only matrix passed all five cases at implementation SHA
`2c5e404`, with aggregate report
`tmp/consumer-review-live/summary-filter-v2/consumer-review-fb86fbcb2918b9b0388cf5f3.json`
and report SHA-256
`c3d23ba97d6dc5dee8ab2b9610c86458724a5705a3129471e6d78d1b588652c2`.
The generated PDFs matched their recorded hashes exactly:

- RAV4 4WD, four-component: `f39c1ffb4a82e95d680ff089789ba6df4994fc5072cefba4412aacd1c9d5e036`
- RAV4 2WD, oil/water pumps: `9ba8abadbb2bdebc22fd037dde4084dff26661a4e8055749141702ac5370f143`
- Camry starter: `33c9a203051e76dd95d8c2e710fb1fa94e0f979c1e53be1cca0e95274e487aa3`
- Forester SOHC water pump: `70eabcb6615670b0264ebc961a8d774597bd44e545d1c9daff861911b4090c3b`
- Civic LX front caliper: `388438000f0a2e1368de18eca5aa22f8ea1ed139cdf40b4ddb5fde55d33cd1a6`

Response and PDF scans found zero generic caption lines, ellipses, or raw
`Figs`/`service and repair` provider remnants. Representative first, middle,
and final RAV4 pages were rendered and visually inspected; installation and
final check coverage remained present through step 127.
