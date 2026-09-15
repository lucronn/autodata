# Negative-path completeness gate plan

**Goal:** Make the consumer review agent classify a replacement response that is
marked `complete` but lacks either removal or installation as a blocking fail.

**Tracking:** [Issue #85](https://github.com/lucronn/autodata/issues/85) and
[Project #8](https://github.com/users/lucronn/projects/8).

**Finding:** The documented missing-content battery case returned `needs_review`
because missing phases were only a medium finding, even though the response
advertised a complete replacement procedure. That weakens the fail-closed
negative-path contract.

## Scope

- Raise the severity of the missing-phase finding when a procedure is marked
  `complete`, making the review decision `fail`.
- Add a deterministic regression for the false-complete response.
- Preserve softer `needs_review` behavior for genuinely partial responses and
  preserve all positive-matrix behavior, issue markers, redaction, and report
  semantics.
- Do not modify user-owned `sample data/`, `output/`, or `tmp/` artifacts.

## Concrete todo

- Add a regression for a complete response missing installation/removal.
- Implement the complete-procedure severity gate.
- Run focused and full developer tests.
- Re-run the documented negative case and fresh five-case positive matrix.
- Record the result in the issue and canonical documentation.

## Verification contract

The negative case must return `fail` with `expectation_met: true`, no final PDF,
and a high-severity phase finding. The positive five-case matrix must remain
5/5 pass with no findings.
