# Preserve source-authored repair procedure information

Issue: https://github.com/lucronn/autodata/issues/101
Project: https://github.com/users/lucronn/projects/8
Canonical repository document: `docs/architecture/guide-artifacts.md`

## Goal

When a natural-language request asks for a repair procedure, AutoData must
return the source-authored instructional content that supports the selected
vehicle and operation. A cached composed answer containing only labels such as
`Replace oil pump` is not a complete procedure and must not prevent source
article hydration. The current response may remain immediately visible while
the source body, ordered steps, warnings, figures, and evidence are normalized
and published into a new revision.

The acceptance example is a 1997 Toyota RAV4 oil-pump and water-pump request.
The generated result must retain the meaningful removal, shared-access,
installation or reassembly, safety, specification, and source-evidence details
available in the supplied source material. It must not claim that installation
or other source content is unavailable when that content was retrieved.

## Diagnosis

The warm-read path accepts a derived article after checking requested
components and labor/procedure shape. A prior composed row can satisfy those
checks with generic operation actions and no instructional text. The
compatibility composer then has no source body to display, so the UI shows
labels rather than a procedure. The source adapter and AutoAPI detail path
already preserve article bodies and evidence when they are fetched; the cache
gate is too permissive and the composed procedure does not make the distinction
between an action label and source-authored instruction explicit.

## Design

1. Define source-fidelity predicates for a selected article and composed
   revision. A source-backed operation is instructional only when it has a
   non-empty source step/body that is not the generated operation label. A
   revision with any selected operation lacking instructional content is a
   cache miss for procedure reads, while a previously viewable answer remains
   available as provisional data.
2. On that cache miss, reuse the existing narrow AutoAPI path: fetch the
   vehicle article index, fetch only the selected article detail and associated
   labor records, and normalize the returned body/steps into ordered procedure
   instructions. Do not fetch every article in the vehicle catalog.
3. Preserve source order, source article IDs, evidence IDs, source URI,
   content hash, and section/phase metadata on every emitted instruction.
   Keep shared operations represented once and retain the overlap calculation;
   the composer may order compatible source steps but may not invent missing
   repair facts, torque values, warnings, or installation steps.
4. If the source body is absent or only a provider summary is returned, publish
   an explicit `needs_review`/`procedure_content_unavailable` warning and keep
   the available quote and operation label visible. Do not mark the answer
   complete and do not describe a label-only result as a full procedure.
5. Keep source PDFs and other document inputs under the existing universal
   source-adapter boundary. OCR/native extraction remains evidence-backed; the
   procedure projection consumes extracted text and linked media rather than
   replacing it with a generic summary. Published revisions remain immutable.
6. Add regression coverage for label-only warm cache invalidation, source-body
   hydration, ordered multi-component instructions, source evidence linkage,
   and honest partial behavior when one selected article lacks instructional
   content. Rebuild the local ingestion service before the browser acceptance.

## Concrete todo list

- [x] Create and synchronize the GitHub Issue and Project #8 item.
- [x] Update the canonical guide artifact contract and this plan with the exact
  tracking references and machine-checked checkpoint record.
- [x] Add failing tests for label-only derived cache rows and source-body
  hydration.
- [x] Make the derived cache completeness check require source-authored
  instructional content for every selected operation.
- [x] Preserve ordered source instructions, phases, source IDs, and evidence
  in the composed procedure without inventing content.
- [x] Verify partial/needs-review behavior for missing source instruction text.
- [x] Run the full applicable test suites and diff checks.
- [x] Rebuild the local Compose ingestion service and exercise the exact browser
  request, inspecting the visible procedure and Workers terminal.
- [ ] Push the synchronized branch, wait for required CI, and update the Issue
  and Project with exact evidence.

## Acceptance contract

- A warm cached answer with only generated operation labels is not accepted as
  a complete procedure and triggers narrow source hydration.
- A source-backed procedure includes meaningful instructions for each selected
  operation whenever the source provides them, in source order or a documented
  dependency order, with source article and evidence linkage.
- A missing source body is visible as a review/availability gap, not silently
  converted into a generic one-line procedure.
- Multi-component labor and overlap remain unchanged by content hydration.
- A source retrieval or normalization failure never hides an already-viewable
  answer and never creates fabricated instructions.
- The browser result for the RAV4 example displays actual source-backed
  instructional content, not only `Replace ...` labels, and its Workers
  terminal is correlated to the same request.
- User-owned `sample data/`, `output/`, and `tmp/` remain untouched and
  unstaged.

## Implementation verification evidence

- `PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q workers/ingestion-python/tests` — `404 passed, 3 skipped, 12 subtests passed`.
- `PYTHONPATH=workers/enrichment-python/src python3 -m pytest -q workers/enrichment-python/tests` — `46 passed, 16 subtests passed`.
- `PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q scripts/dev/test_*.py` — `77 passed, 2 subtests passed`.
- `python3 -m pytest -q scripts/contracts` — `14 passed`.
- `node --check apps/api-go/dashboard/app.js` and `go test ./...` in `apps/api-go` passed.
- Rebuilt `ingestion-http`, `ingestion-worker`, and `api` from this checkout; `/healthz` and `/readyz` returned healthy.
- Browser query `7c8fa284-b5de-556c-9639-2c1ac48fba61` selected the 1997 Toyota RAV4 4 Door 4WD 2L and visibly rendered `99` source-backed procedure steps. The first step was `Disconnect Power Steering (PS) reservoir and remove reservoir bracket.` and the rendered sequence included oil-pump removal, water-pump removal, timing-belt, torque, installation, refill, and leak-check instructions. The Workers terminal was correlated to the same query and showed the cache-miss/source-retrieval path.
- The resulting durable query was `available` / `normalized`; a subsequent browser lookup served the normalized cache while retaining the full source-authored procedure.

## Boundaries

This plan changes procedure-content selection and source hydration only. It
does not change payment, authorization, provider credentials, labor arithmetic,
or the immutable-revision model. The GitHub Project remains an index and work
queue; this document and the linked canonical repository document remain the
technical source of truth.
