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

- [x] Add a focused regression proving generic image labels are omitted from PDF
  text while meaningful captions remain available.
- [x] Implement caption filtering at the PDF rendering boundary.
- [x] Run focused PDF tests and the complete applicable worker/developer/API test
  suites.
- [x] Render representative first, middle, and final pages and inspect for
  clipping, spacing, image placement, and absence of generic caption artifacts.
- [x] Re-run the consumer agent against the affected RAV4 case and record the new
  report/PDF hashes in canonical documentation and Project #8.
- [x] Reconcile the finding in the GitHub Issue; do not close it until the fresh
  rendered evidence passes.

## Verification contract

The repair is complete only when a complete guide with a generic image alt
value produces a valid PDF whose extracted text does not contain that generic
caption, a meaningful caption still renders, image objects remain embedded,
and the live consumer review remains a pass with revision-matched PDF output.

## Completed evidence

The renderer fix is application commit
`f289c8fe81a5ca546e6e53ab64623cbc4f3dac85`. The fresh five-case live report
passed 5/5 with no findings at
`tmp/consumer-review-live/pdf-caption-fix-v2/consumer-review-5be2f4fa5d5976c2bd260bf0.json`
(SHA-256
`12c67c1fe3cc906456b466595763cc485d9bd905e6eddd90d655b53cf2438cd2`).
All five returned PDFs matched their report hashes, embedded figures remained
present, and the generic-caption scan passed for every PDF. The representative
RAV4 first, middle, and final pages were rendered and visually inspected with
no caption, clipping, or placement defect found.
