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

- Add a regression proving truncated provider summaries are omitted while
  detailed and concise procedure steps remain.
- Implement the consumer-summary filter.
- Run focused and full applicable test suites.
- Re-run the five-case live consumer matrix and verify no raw summary or
  ellipsis artifact remains in the consumer response or PDF.
- Render representative pages and inspect layout and final installation/check
  coverage.
- Record hashes and reconcile the GitHub Issue only after fresh evidence passes.

## Verification contract

The repair is complete only when the consumer response and matching PDF contain
no provider-summary ellipsis/reference artifact, retain complete removal and
installation coverage, preserve embedded figures and revision parity, and the
live consumer agent still passes all cases.
