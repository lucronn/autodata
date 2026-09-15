# Consumer PDF figure-caption cleanup plan

**Goal:** Remove generic placeholder figure captions such as `image` from
consumer repair-guide PDFs while preserving meaningful source-provided
captions and keeping the existing deterministic PDF layout unchanged.

**Tracking:** [Issue #92](https://github.com/lucronn/autodata/issues/92) and
[Project #8](https://github.com/users/lucronn/projects/8).

**Finding:** A rendered 1997 Toyota RAV4 guide visibly prints the literal
caption `image` beneath figures because the source response supplies a generic
alt value. This is a consumer-facing artifact and is not caught by the current
procedure-completeness rubric.

## Scope

- Change only the PDF renderer and its focused tests.
- Treat blank, whitespace-only, and generic values such as `image` as having no
  usable caption; omit the caption rather than inventing source meaning.
- Preserve meaningful captions such as `Pump figure` when supplied.
- Do not change the consumer response contract, source evidence, image bytes,
  image validation, guide revision, or PDF authorization behavior.
- Do not modify the user-owned `sample data/`, `output/`, or `tmp/` artifacts.

## Concrete todo

- Add a focused regression proving generic image labels are omitted from PDF
  text while meaningful captions remain available.
- Implement caption filtering at the PDF rendering boundary.
- Run focused PDF tests and the complete applicable worker/developer/API test
  suites.
- Render representative first, middle, and final pages and inspect for
  clipping, spacing, image placement, and absence of generic caption artifacts.
- Re-run the consumer agent against the affected RAV4 case and record the new
  report/PDF hashes in canonical documentation and Project #8.
- Reconcile the finding in the GitHub Issue; do not close it until the fresh
  rendered evidence passes.

## Verification contract

The repair is complete only when a complete guide with a generic image alt
value produces a valid PDF whose extracted text does not contain that generic
caption, a meaningful caption still renders, image objects remain embedded,
and the live consumer review remains a pass with revision-matched PDF output.
