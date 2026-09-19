# Mercury-2 Combined Procedure Contract

**Goal:** Use Mercury-2 as the reasoning layer that combines normalized, vehicle-scoped component procedures into one overlap-aware repair procedure while the application remains authoritative for source identity, evidence, arithmetic, and publication.

**Tracked delivery:** [Issue #110](https://github.com/lucronn/autodata/issues/110), [AutoData Portfolio Project](https://github.com/users/lucronn/projects/8), and the [implementation plan](../superpowers/plans/2026-09-19-mercury2-overlap-procedure-composition.md).

## Boundary of responsibility

The application performs vehicle binding, source retrieval, normalization, article selection, labor arithmetic, image preparation, provenance validation, persistence, and artifact rendering. Mercury-2 performs the non-deterministic reasoning required to recognize shared work and produce a safe order from the supplied procedures.

Mercury-2 receives only the selected normalized articles for one canonical vehicle. It may combine, order, and phrase supplied operations, but it may not invent vehicle facts, parts, tools, torque values, warnings, labor values, evidence, images, or source URLs. A provider failure or invalid response falls back to the deterministic source-bound procedure; it must never hide a usable viewable result.

## Required Mercury-2 input

The request is a JSON object containing:

- `vehicle`: canonical year, make, model, engine/base, drivetrain, and internal vehicle/configuration IDs.
- `requested_components`: the components named by the user.
- `articles`: normalized source articles, each with `article_id`, title, vehicle scope, procedure phases, source instructions, labor operations, evidence records, and prepared image records.
- `labor`: application-calculated operation records and known/unknown duration values. Missing duration never prevents procedure composition.
- `deterministic_procedure`: a source-bound fallback and completeness reference, not an authority Mercury-2 may silently contradict.

Each prepared image record includes a stable `image_id`, source article ID, evidence IDs, source locator, caption/alt text, media type, and either prepared bytes or an artifact reference. The model receives metadata and stable IDs, never an instruction to fetch a URL or fabricate image bytes.

## Prompt contract

The user prompt sent to Mercury-2 must explicitly require the following reasoning:

1. Build a dependency-aware plan with phases: preparation, access/disassembly, shared service, component-specific removal, inspection/cleanup, installation/reassembly, refill/bleed/adjustment, and final verification.
2. Compare all supplied operations and instructions for shared prerequisites and shared work. Emit a shared operation once, attach every affected component, and identify the source operations it replaces. Do not repeat a shared drain, cover removal, belt/chain access, refill, bleeding, adjustment, inspection, or cleanup step merely because it appears in multiple articles.
3. Preserve required source order inside each article unless a dependency-safe merged order is explicitly represented. Removal must precede the corresponding installation; common access must precede dependent component removal; reassembly must be reverse/dependency-safe; refill, bleed, adjustment, leak checks, and final verification must follow installation.
4. Use the supplied labor operation IDs for coverage and overlap explanation. Never calculate or invent hours in the model. The application-owned quote remains the labor authority, including unknown-duration values.
5. Copy source-backed instructions faithfully, choosing the most complete supplied wording when the same operation is present in multiple articles. Do not create generic placeholder instructions when a source instruction exists.
6. Attach source article IDs and evidence IDs to every step and warning. Attach image IDs only from the supplied image registry and only to steps supported by those image records.
7. Mark uncertainty, conflicting instructions, absent images, missing labor, and unresolved safety questions as review warnings. Do not resolve a conflict by guessing.

The exact JSON response shape is versioned in `mercury2.py`. It contains a title, ordered steps, warnings, `overlap_groups`, `dependency_edges`, `image_refs`, review state, and excluded operation IDs. Every step contains an operation ID, action, components, phase, source article IDs, evidence IDs, instructions, and image IDs. `overlap_groups` explain one shared operation, the affected components, and the source operation IDs represented by that step.

## Image and artifact policy

Markdown remains the canonical persisted text projection and carries portable stable image references such as `![Figure caption](artifact://<image_id>)` plus an image-reference table containing the image ID, evidence IDs, source locator, and render status. Markdown does not embed untrusted remote URLs and does not pretend that a renderer can fetch provider images.

The preferred consumer artifact is the existing self-contained HTML guide. The authorized renderer resolves only prepared source-backed image bytes and embeds them as `data:<media-type>;base64,...` images. It includes the same revision ID, captions, step-scoped evidence, and review label. If a referenced image has no prepared bytes, the HTML renderer reports a visible figure gap/review state rather than fetching a remote URL or inventing a replacement. PDF remains a compatibility artifact and uses the same prepared image set.

## Publication guarantees

- The combined procedure receives a deterministic derived article identity scoped to vehicle, requested component set, source watermarks, and composition version.
- Published revisions are immutable. A new source snapshot or composition version creates a new revision with lineage and changelog data.
- The response may expose a source-backed deterministic procedure immediately while Mercury-2 is unavailable; it labels the result unreviewed or provisional.
- An invalid Mercury-2 response is rejected locally with a bounded warning and never persisted as authoritative procedure content.
- Image and evidence references are deduplicated at artifact presentation time, but persisted lineage remains intact for audit.

## Verification contract

The acceptance test must use a real selected vehicle and at least three source articles with overlapping access/removal work. It must prove that the Mercury-2 prompt contains the overlap/dependency/image rules, the validated result contains one shared step with multiple components and source lineage, no unsupported image ID survives validation, and the HTML artifact contains prepared base64 images. A simulated provider failure must still return the deterministic source-backed procedure.
