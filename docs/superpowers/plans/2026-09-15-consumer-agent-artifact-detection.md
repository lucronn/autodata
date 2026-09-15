# Consumer agent artifact-detection plan

**Goal:** Make the consumer review agent fail a consumer response that exposes a
provider-only or truncated procedure summary, so the live evaluator records a
reproducible finding and can create or reuse a GitHub issue.

**Tracking:** [Issue #85](https://github.com/lucronn/autodata/issues/85) and
[Project #8](https://github.com/users/lucronn/projects/8).

**Finding:** The five-case live run discovered provider-summary artifacts during
manual PDF review, but the consumer agent rated that output as a pass because
its rubric checked provenance commentary without checking procedure actions for
ellipsized or provider-reference-only text.

## Scope

- Add deterministic response-level artifact detection to the existing consumer
  agent rubric.
- Detect ellipsized actions and provider-reference-only procedure rows when
  they carry no structured instructions or figures.
- Emit a stable non-info finding so report-only runs record it and explicit
  `--create-issues` runs create or reuse the normal deduplicated GitHub issue.
- Preserve valid detailed removal/installation steps, concise procedure steps,
  PDF integrity checks, redaction, idempotency, and report-only defaults.
- Do not modify the user-owned `sample data/`, `output/`, or `tmp/` artifacts.

## Concrete todo

- Add a regression for provider-summary detection and valid-step preservation.
- Implement deterministic artifact findings in the consumer rubric.
- Run the focused and full developer test suites.
- Re-run the five-case live consumer matrix and confirm all current outputs pass
  with zero artifact findings.
- Record the implementation and report evidence in the issue and repository
  documents.

## Verification contract

The repair is complete only when a synthetic artifact produces a stable finding
with the expected severity/category/path, valid current responses still pass,
and the fresh five-case live matrix remains pass with no artifact findings.
