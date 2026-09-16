# Repair-guide artifact contract

**Goal:** Serve a self-contained HTML repair guide as the fastest, most portable consumer artifact while preserving the existing PDF download for compatibility. Correct provider vehicle labels at the source boundary so canonical identity is never replaced by provider prose.

**Plan:** `docs/superpowers/plans/2026-09-15-html-guide-and-silverado-label.md`

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/96

## Decision

The persisted procedure and immutable revision remain the single source of guide content. The authorized service prepares source figures once, then renders either:

- HTML: a standalone document with inline CSS and every prepared figure embedded as a base64 `data:` URI. It is the preferred dashboard/download output and does not require a network connection after delivery.
- PDF: the existing revision-matched compatibility artifact, retained for established consumers.

Both artifacts are gated by the same complete-guide contract and carry the same revision ID, source watermark, warnings, and review label. The persisted guide retains internal evidence linkage for auditability; public artifact serialization exposes only permitted review/evidence metadata and never raw provider HTML or internal provenance IDs. HTML rendering never fetches a remote image and never invents missing content.

Vehicle applicability is derived from canonical year, make, model, drivetrain, and engine fields when a provider candidate has a malformed prose label. A candidate value such as `For A Chevrolet` is normalized to `Chevrolet` with an alias trail; the consumer heading for the supplied Silverado example is `1999 Chevrolet Silverado 1500 2WD 5.3L`.

## Concrete todo

- [x] Synchronize the Issue, Project item, plan, canonical docs, and machine-checked pre-implementation record at one checkpoint SHA.
- [x] Add failing HTML-artifact and Silverado-label tests.
- [x] Implement HTML rendering, worker caching, internal delivery, Go proxying, answer metadata, dashboard preference, and consumer verification.
- [x] Implement provider-label sanitization without changing valid detailed vehicle labels.
- [x] Run focused/full verification and record exact evidence here and in GitHub.

## Boundaries

No source data, credentials, or user-owned runtime artifacts are part of this delivery. The GitHub Project is a synchronized delivery index; this document and the linked implementation plan are the normative technical record. Verification evidence is added below after the final local test run.

## Local verification checkpoint

The current chat acceptance repair passed these local checks:

- `400 passed, 3 skipped, 12 subtests passed` in the Python worker suite.
- `go test ./... -count=1` passed in `apps/api-go`.
- `node --check apps/api-go/dashboard/app.js` passed.
- `git diff --check` passed.

## Follow-up: natural-language source retrieval acceptance

The browser acceptance run exposed two separate defects tracked in
[Issue #96](https://github.com/lucronn/autodata/issues/96) and the
[follow-up plan](../superpowers/plans/2026-09-15-chat-source-failure.md): the
local 8080 Compose API/worker were stale, and the chat parser treated the
natural-language introducer `for a` as the vehicle make. The current parser
must normalize `for a 1999 Chevrolet Silverado 1500 2WD 5.3L` to the canonical
Chevrolet identity before source lookup.

The subsequent browser run identified a warm-read defect as well. A persisted
combined article can contain complete nested `procedure.steps` and
`labor.operations`, while the compatibility composer expects top-level
operation fields. Without an explicit compatibility mapping, the UI regresses
to a one-component placeholder and loses known labor/overlap data. The
acceptance contract therefore requires warm composed revisions to retain every
requested component, source-linked step, and known labor value.

When source retrieval exhausts its retries without any usable answer, the
persisted query and nested answer must both expose terminal `failed` /
`unavailable` state. The worker stream must publish the correlated terminal
answer event so the dashboard cannot continue to show `processing ·
normalizing`. If a provisional source-backed answer already exists, later
normalization or composition failure keeps that answer visible and marks the
affected work as failed; deep work never hides data that can already be shown.

The warm-read compatibility path must preserve nested labor operations and
procedure steps rather than rebuilding a partial placeholder.

The rebuilt browser acceptance on 2026-09-15 produced query
`f4634f2f-93e9-5c92-b523-6feb50fac5d6` and rendered `1999 Chevrolet Silverado
1500 2WD 5.3L` with four distinct component steps and 9 known labor hours.
The correlated Workers terminal ended after five events. The cached revision
contained no source-priced parts, and the UI exposed that absence explicitly;
it did not fabricate a price.

This follow-up is not accepted by unit tests alone. The local API and ingestion
containers must be rebuilt from the checked-out revision, and the exact
Silverado request must be exercised in the browser with the canonical vehicle
label, Workers terminal progress, and a visible procedure/quote result
verified. User-owned `output/`, `sample data/`, and `tmp/` remain local-only.

## Follow-up: source-authored procedure fidelity

The warm derived-answer cache must not treat a composed record containing only
generated operation labels such as `Replace oil pump` as a complete procedure.
When a selected operation has no meaningful source-authored instruction or
source evidence, the cache lookup falls through to the narrow source path so
the selected AutoAPI article body/steps and labor are rehydrated. The current
answer remains available while that work runs; it is labeled provisional or
needs review rather than presented as a finished repair procedure.

The canonical procedure projection preserves the source instruction order (or
an explicit dependency order for shared work), phase, source article IDs,
evidence IDs, source URI, and content watermark. It may consolidate shared
operations for labor arithmetic, but it may not replace source instructions
with generic labels or invent warnings, torque values, installation steps, or
other repair facts. If the source does not provide instructional content, the
response exposes `procedure_content_unavailable` and keeps the gap visible.

This work is tracked in [Issue #101](https://github.com/lucronn/autodata/issues/101)
and the [source-fidelity plan](../superpowers/plans/2026-09-15-source-fidelity-procedure-hydration.md).
The Project #8 item is an index to that canonical plan, not a competing source
of technical truth. Acceptance requires a rebuilt local Compose service and a
browser run of the RAV4 multi-component request that visibly shows source
instructions and the correlated Workers terminal.

## Verification evidence

The source-fidelity implementation was exercised through the live local
dashboard after rebuilding the Compose `ingestion-http`, `ingestion-worker`,
and API services. Query
`7c8fa284-b5de-556c-9639-2c1ac48fba61` selected the 1997 Toyota RAV4 4 Door
4WD 2L and rendered 99 source-authored steps, including detailed oil-pump
and water-pump removal/reassembly instructions, timing-belt dependencies,
tool and torque text, refilling, and leak checks. The Workers terminal showed
the same query's cache-miss and source-retrieval events. A later lookup served
the normalized cache while retaining those 99 steps; it did not regress to
generic `Replace ...` labels.

## Follow-up: procedure artifact navigation and formatting

The complete guide actions in the dashboard are inspection actions. They must
open the revision-matched HTML or PDF in a new browser tab/window so the user
can read the formatted procedure while keeping the chatbot answer available.
They must not force a download: the dashboard links omit `download`, use
`target="_blank"` with `rel="noopener noreferrer"`, and the authorized Go and
ingestion guide responses use `Content-Disposition: inline`.

This follow-up is tracked in [Issue #101](https://github.com/lucronn/autodata/issues/101),
the [procedure artifact navigation plan](../superpowers/plans/2026-09-16-procedure-artifact-navigation.md),
and Project #8. The artifact content contract is unchanged: HTML remains a
self-contained document with inline CSS and base64-embedded figures, while
the PDF remains the revision-matched compatibility artifact. Acceptance
requires clicking the live dashboard action and inspecting the opened,
formatted artifact in a separate browser tab/window.

The 2026-09-16 implementation was rebuilt into the local API and exercised in
the live dashboard with query
`f96e0394-671e-5cd7-b07f-31415b6ec967`. The dashboard rendered the selected
1997 Toyota RAV4 4-door 4WD 2L with 99 source-authored steps and both new-window
actions. An authenticated HTTP check of the HTML artifact returned 200,
`Content-Disposition: inline`, the expected guide title and vehicle content,
and 80 embedded image payloads. The Codex in-app browser blocked the final
cross-tab click by its browser security policy, so that limitation is retained
in the verification record rather than reported as a successful tab inspection.

## Evidence presentation

Evidence is an audit contract, not repeated prose. A generated guide may carry
guide-level evidence for the complete source bundle, step-level evidence for a
specific instruction, and figure-level evidence for a specific image. The
detailed artifact must render step-level and figure-level references only with
the step they support, then render the deduplicated guide-level evidence list
once. It must never attach the complete guide-level list to every step. Stable
IDs and their persisted source locators remain unchanged; only presentation
scope is reduced. This rule is tracked in [Issue #103](https://github.com/lucronn/autodata/issues/103)
and the [evidence deduplication plan](../superpowers/plans/2026-09-16-evidence-reference-deduplication.md).

The implementation was rebuilt into the local Compose `ingestion-http` service
and checked through the live guide route. The returned HTML was HTTP 200 with
99 step evidence blocks and one aggregate list containing 1,104 unique
references and no aggregate duplicates; the dashboard also loaded at
`http://127.0.0.1:8080/dashboard/`. This bounds repetition without discarding
the persisted provenance needed for audit and detailed review.
