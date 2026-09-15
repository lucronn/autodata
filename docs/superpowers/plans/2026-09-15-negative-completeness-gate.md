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

- [x] Add a regression for a complete response missing installation/removal.
- [x] Implement the complete-procedure severity gate.
- [x] Run focused and full developer tests.
- [x] Re-run the documented negative case and fresh five-case positive matrix.
- [x] Record the result in the issue and canonical documentation.

## Verification contract

The negative case must return `fail` with `expectation_met: true`, no final PDF,
and a high-severity phase finding. The positive five-case matrix must remain
5/5 pass with no findings.

## Acceptance evidence

Implementation commit: `87ca230` (`fix: fail false-complete procedures`). The
full developer suite passed with `74 passed, 2 subtests passed`; the prior full
autonomy, ingestion, Go API, and shared-contract suites also passed at the
same release-hardening sequence.

The fresh negative report
`tmp/consumer-review-live/negative-completeness-v2/consumer-review-0065a3f0d4368d9d841847ca.json`
has SHA-256
`fd7de16d67d87aa87a1088211804c598ac05caea36d96369d82f2ca4939e681d`, returns
`fail` with `expectation_met: true`, no PDF, and a blocking high-severity phase
finding.

The fresh positive report
`tmp/consumer-review-live/final-positive-v3/consumer-review-404c3bef2992b3eb731861aa.json`
has SHA-256
`33539182a7b02eaaf3df09716bf744bef3ef8208ad817e8d8e1138db80d1b038`. All five
cases passed at score 100 with zero findings and zero issue actions. The five
PDF SHA-256 values are recorded in the synchronized record.
