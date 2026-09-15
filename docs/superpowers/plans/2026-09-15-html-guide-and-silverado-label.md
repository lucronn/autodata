# HTML Guide Artifact and Silverado Identity Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a self-contained HTML repair guide with base64-embedded figures the preferred downloadable artifact while preserving the existing PDF contract, and correct AutoAPI vehicle normalization so the 1999 Chevrolet Silverado 1500 2WD 5.3L is labeled with its canonical identity.

**Architecture:** Keep guide composition, authorization, revision matching, and source evidence unchanged. Add an additive HTML renderer and authenticated delivery route that reuses the same immutable guide revision and prepared image bytes as PDF. Sanitize provider vehicle identity at the AutoAPI candidate boundary and build applicability from canonical fields when a provider label contains prose. Maintain the dashboard’s existing PDF link as a secondary compatibility path.

**Tech Stack:** Python standard-library HTML rendering with base64 and HTML escaping, existing Python ingestion service and AutoAPI Two connector, Go API proxy, vanilla dashboard JavaScript/HTML/CSS, unittest/pytest, Go tests, and existing consumer contract evaluator.

**Spec:** The HTML artifact must be standalone, render without network access, embed every prepared guide figure as a `data:` URI, expose the guide revision/source watermark/review state, and be available only for complete immutable guides. The PDF endpoint remains supported. A provider value such as `For A Chevrolet` must never become the canonical make or consumer heading; the target label for the supplied example is `1999 Chevrolet Silverado 1500 2WD 5.3L`.

## Global Constraints

- Follow `docs/agents/pre-implementation-gate.md`; implementation begins only after the synchronized record is committed at the pinned base SHA and machine preflight passes.
- Do not modify or stage the user-owned `sample data/`, `output/`, or `tmp/` directories.
- Do not expose, persist, or add credentials or provider secrets.
- Do not change the existing PDF authorization, revision, completeness, evidence, or cache semantics except where shared preparation is safely reused.
- Do not fetch remote images from the HTML renderer; image bytes must be fetched once by the authorized service preparation path and embedded locally.
- Do not invent a new source of truth: the canonical guide remains the persisted procedure/revision and the GitHub Project remains an index linked to repository documentation.

## Task 1: Synchronize planning and tracking

- [x] Create the GitHub Issue for this plan, link it to Project #8, and apply the issue labels `area:api`, `area:fast-lane`, `area:deep-lane`, `type:feature`, `type:source-ingestion`, `priority:p1`, and `risk:high`.
- [x] Update the Issue body with this plan path, canonical document path, exact acceptance contract, and the concrete todo list below.
- [x] Add the Issue to Project #8, set Status to `Ready`, and populate Source or dependency reference with the Issue, plan, and canonical document URLs.
- [x] Add the synchronized pre-implementation record under `docs/agents/records/` pinned to the checkpoint commit and run `scripts/autonomy/pre_implementation.py` validation.

## Task 2: Establish failing tests and traceable identity behavior

- [x] Add a regression test in `workers/ingestion-python/tests/test_autoapitwo_guide.py` for a provider candidate whose make/description contains `For A Chevrolet`, asserting canonical candidate fields and applicability equal `1999 Chevrolet Silverado 1500 2WD 5.3L`.
- [x] Add focused HTML renderer tests in `workers/ingestion-python/tests/test_guide_html.py` for standalone output, escaped text, base64 image embedding, meaningful-caption preservation, generic-caption omission, and rejection of incomplete guides.
- [x] Add API, internal ingestion HTTP, chat-service, dashboard, and consumer-contract test cases for the additive HTML artifact and compatibility PDF path.

## Task 3: Implement the standalone HTML guide artifact

- [x] Add `workers/ingestion-python/src/autodata_ingestion/guide_html.py` with a deterministic `render_guide_html` function that emits escaped inline HTML/CSS, guide metadata, preparation, warnings, ordered steps, evidence references, and `data:{media_type};base64,...` images.
- [x] Extend `workers/ingestion-python/src/autodata_ingestion/chat_service.py` with revision-keyed HTML caching and `render_chat_guide_html`, reusing the existing authorized image preparation and complete-guide checks without changing PDF behavior.
- [x] Add HTML metadata to the public chat answer while retaining the existing PDF metadata and revision IDs.
- [x] Add `/v1/chat/queries/{id}/guide.html` to the ingestion service and proxy it through the Go API as `text/html; charset=utf-8` with a private attachment filename.
- [x] Make the dashboard present the HTML guide as the primary action and the PDF as a secondary compatibility action, with clear unavailable-state behavior.
- [x] Extend `scripts/dev/consumer_agent.py` and its tests to validate HTML readiness, revision matching, standalone bytes, and embedded-image integrity without weakening PDF checks.

## Task 4: Correct provider vehicle identity normalization

- [x] Normalize provider candidate make values before constructing the consumer label, stripping only a leading prose prefix such as `For A` when the remaining value is a make and preserving an alias/evidence trail.
- [x] Ensure applicability is composed from canonical year, make, model, drivetrain, and engine fields when the provider label is malformed; do not copy a malformed label over canonical identity.
- [x] Preserve exact valid provider labels for compatible existing cases, including the detailed RAV4 label covered by current tests.

## Task 5: Verify, document, and deliver

- [x] Run focused worker, Go API, dashboard, and consumer-contract tests, then the complete applicable test suites and `git diff --check`.
- [x] Exercise a representative complete guide offline and verify that removing network access after preparation still leaves a renderable HTML document with embedded figures.
- [ ] Run the live/local Silverado example through the chat path, verify the canonical heading and HTML/PDF revision parity, and record measured evidence in the plan and canonical guide document.
- [x] Update `docs/architecture/consumer-repair-guides.md`, `docs/verification/consumer-review-runbook.md`, and `docs/wiki/Getting-Started.md` to make HTML the preferred artifact while documenting PDF compatibility and the identity-label rule.
- [ ] Update the GitHub Issue and Project item with exact implementation SHA, tests, and remaining review status; push the synchronized branch and merge only after required CI and independent review gates pass.

## Acceptance Contract

- `GET /chat/queries/{id}/guide.html` returns a complete, revision-matched, authorized standalone HTML document whose figures are base64 embedded and whose text is HTML escaped.
- `GET /chat/queries/{id}/guide.pdf` continues returning the existing PDF contract.
- The chat answer exposes the HTML and PDF links with the same revision ID; HTML is the default dashboard action.
- The Silverado example renders `1999 Chevrolet Silverado 1500 2WD 5.3L`, never `1999 For A Chevrolet Silverado 1500 2WD 5.3L`.
- Incomplete guides remain unavailable for final artifacts, source evidence and review status remain visible, and user-owned untracked directories remain untouched.

**Tracking:** [Issue #96](https://github.com/lucronn/autodata/issues/96) and [Project #8](https://github.com/users/lucronn/projects/8).

## Local verification checkpoint

Implementation commit `d63ab7b` passed:

- `PYTHONPATH=workers/ingestion-python/src python3 -m pytest -q workers/ingestion-python/tests scripts/dev/test_consumer_agent.py scripts/contracts/test_chat_quote_contract.py scripts/contracts/test_contracts.py` — `426 passed, 3 skipped, 12 subtests passed`.
- `go test ./... -count=1` from `apps/api-go` — passed.
- `node --check apps/api-go/dashboard/app.js` — passed.
- `git diff --check` — passed.

The live/local Silverado chat run and HTML/PDF parity check are still pending a
restart of the running service on this branch; this plan does not claim that
runtime result yet.
