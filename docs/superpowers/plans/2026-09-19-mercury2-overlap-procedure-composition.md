# Mercury-2 Overlap-Aware Procedure Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Mercury-2 the validated reasoning layer for combining normalized vehicle procedures while preserving deterministic source/evidence lineage and renderable image references.

**Architecture:** Keep application-owned retrieval, normalization, labor arithmetic, provenance, and publication authoritative. Extend the existing Mercury-2 JSON boundary with dependency phases, overlap groups, and stable image references; wire the configured client into the chat composer with deterministic fallback. Keep Markdown as the canonical text projection and use the existing self-contained HTML artifact for embedded base64 images.

**Tech Stack:** Python ingestion worker, existing `Mercury2Client`, `job_plan.py`, `chat_service.py`, `derived_article_persistence.py`, `guide_html.py`, pytest, Docker Compose local services, GitHub Issue #110, Project #8.

**Spec:** `docs/architecture/mercury2-procedure-composition.md`

**Issue:** https://github.com/lucronn/autodata/issues/110

**Project:** https://github.com/users/lucronn/projects/8

## Global Constraints

- Mercury-2 may only reason over selected normalized source articles for one canonical vehicle.
- The application remains authoritative for labor values, source identity, evidence, image bytes, validation, persistence, and publication state.
- Missing labor duration must not prevent composition; unknown duration remains unknown in the quote.
- Provider failure or invalid output must preserve a deterministic source-backed procedure when one exists.
- No implementation file changes occur until the synchronized planning record is committed at the pinned base SHA and machine preflight passes.
- No credential is printed, committed, embedded in prompts, or stored in repository files.

## Review Focus

- Shared access/removal work appears once while preserving all affected components and source operations; test this with oil pump, water pump, timing belt, and power-steering articles.
- A reassembly dependency cannot be placed before its removal/access prerequisite; test phase/dependency validation.
- An image ID not present in the supplied registry is rejected; a prepared source image is rendered in HTML as base64.
- A Mercury-2 timeout returns the deterministic source-backed procedure and a review warning; it does not return an empty result.
- Missing labor hours do not block a composed procedure; the quote exposes unknown hours without fabricated arithmetic.

### Task 1: Lock the contract and tracking checkpoint

**Files:**
- Create: `docs/architecture/mercury2-procedure-composition.md`
- Create: `docs/superpowers/plans/2026-09-19-mercury2-overlap-procedure-composition.md`
- Create: `docs/agents/records/2026-09-19-mercury2-overlap-procedure-composition.json`
- Modify: `docs/architecture/dashboard-agent-workspace.md`
- Modify: `docs/architecture/guide-artifacts.md`

**Interfaces:**
- Consumes: current source-bound procedure and HTML artifact contracts.
- Produces: the decision-complete prompt, schema, image, fallback, and acceptance contract used by implementation tasks.

- [x] **Step 1: Write the architecture contract and this plan.**
- [x] **Step 2: Update canonical docs with the same concrete goal and todo list.**
- [ ] **Step 3: Update Issue #110 and its Project #8 item with the plan and document references.**
- [ ] **Step 4: Pin the checkpoint SHA in the required synchronized record.**
- [ ] **Step 5: Run `python scripts/autonomy/pre_implementation.py --record <record>` and require a passing result before any implementation file change.**

### Task 2: Expand the Mercury-2 composition schema and prompt

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/mercury2.py`
- Test: `workers/ingestion-python/tests/test_mercury2.py`

**Interfaces:**
- Consumes: canonical vehicle, quote/labor, normalized article procedures, evidence, and prepared image metadata.
- Produces: versioned JSON prompt and response fields for `phase`, `overlap_groups`, `dependency_edges`, `image_refs`, and step-level image IDs.

- [ ] **Step 1: Add a failing prompt test.** Capture the prompt passed to a fake client and assert it contains explicit shared-work, dependency-order, source-fidelity, labor-authority, and image-registry instructions plus the supplied image IDs.
- [ ] **Step 2: Run `pytest workers/ingestion-python/tests/test_mercury2.py -q` and verify the new assertions fail against the short prompt/schema.**
- [ ] **Step 3: Extend `PROCEDURE_COMPOSITION_SCHEMA` with the exact fields and closed enums described in the architecture contract.** Keep `additionalProperties: false` at each object boundary.
- [ ] **Step 4: Replace the short task string in `compose_procedure_draft` with a detailed JSON-only prompt containing the rules and an explicit output example.** Keep temperature zero and never include credentials or remote fetch instructions.
- [ ] **Step 5: Run the focused Mercury-2 tests and verify they pass.**

### Task 3: Validate overlap, dependency, provenance, and image references

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/job_plan.py`
- Test: `workers/ingestion-python/tests/test_job_plan.py`

**Interfaces:**
- Consumes: the expanded Mercury-2 response and application-owned operation/image registries.
- Produces: validated procedure steps with `phase`, `overlap_groups`, `dependency_edges`, `image_refs`, and preserved source instructions.

- [ ] **Step 1: Add failing tests for a valid shared access step, an unsupported image ID, a duplicate operation, a missing operation, and missing labor duration.**
- [ ] **Step 2: Run the focused job-plan tests and verify the new tests fail.**
- [ ] **Step 3: Build an image registry from selected article image/evidence records and pass it into the Mercury-2 payload.**
- [ ] **Step 4: Extend `_validate_llm_procedure` to reject unsupported image IDs, invalid article/evidence bindings, invalid phase/dependency references, duplicate represented operations, and overlap groups that do not map to supplied operation IDs.**
- [ ] **Step 5: Preserve application-owned instructions and labor values in the validated result; attach model ordering metadata without accepting model-generated hours.**
- [ ] **Step 6: Run focused tests and the complete ingestion-worker suite.**

### Task 4: Wire Mercury-2 into chat composition with safe fallback

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/worker.py`
- Test: `workers/ingestion-python/tests/test_chat_service.py`

**Interfaces:**
- Consumes: selected chat articles and configured environment-only `Mercury2Client`.
- Produces: dashboard chat answers whose composed procedure is Mercury-2-generated when available, with deterministic source-backed fallback on failure.

- [ ] **Step 1: Add a failing chat test using an injected fake Mercury client and assert `_default_composer` invokes the procedure composer for a multi-component AutoAPItwo result.**
- [ ] **Step 2: Add a failing fallback test where the fake client raises and assert the answer retains source instructions and includes `procedure_composition_failed`.**
- [ ] **Step 3: Add an explicit procedure-composer dependency/configuration boundary so tests can inject a client and production obtains `Mercury2Client.from_environment()` only when `AUTODATA_MERCURY2_PROCEDURE_COMPOSITION_ENABLED=1`.**
- [ ] **Step 4: Wire the worker runtime to pass the configured client while leaving deterministic composition available when the feature flag is disabled or the key is unavailable.**
- [ ] **Step 5: Ensure a missing/unknown labor duration is represented as unknown and does not short-circuit procedure composition.**
- [ ] **Step 6: Run chat tests and the complete ingestion-worker suite.**

### Task 5: Render canonical image references in Markdown and HTML

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/guide_html.py`
- Test: `workers/ingestion-python/tests/test_derived_article_persistence.py`
- Test: `workers/ingestion-python/tests/test_guide_html.py`

**Interfaces:**
- Consumes: validated step-level image IDs and prepared image artifacts.
- Produces: Markdown stable `artifact://` references and self-contained HTML/PDF-compatible figure output.

- [ ] **Step 1: Add failing tests for Markdown image-reference blocks, HTML base64 embedding, image deduplication, and missing prepared bytes.**
- [ ] **Step 2: Run focused artifact tests and verify they fail.**
- [ ] **Step 3: Render stable Markdown references without remote URLs or base64 blobs.**
- [ ] **Step 4: Resolve validated image IDs to prepared bytes in HTML and preserve captions plus scoped evidence.**
- [ ] **Step 5: Make missing bytes a visible review gap rather than a remote fetch or fabricated image.**
- [ ] **Step 6: Run focused artifact tests and the complete worker suite.**

### Task 6: Verify live browser behavior and synchronize delivery

**Files:**
- Modify: `docs/architecture/mercury2-procedure-composition.md`
- Modify: `docs/superpowers/plans/2026-09-19-mercury2-overlap-procedure-composition.md`
- Modify: `docs/agents/records/2026-09-19-mercury2-overlap-procedure-composition.json`

- [ ] **Step 1: Rebuild local ingestion/API services from the implementation commit.**
- [ ] **Step 2: Use the browser to select a real vehicle and submit a multi-component query with at least three source procedures.**
- [ ] **Step 3: Confirm the Workers terminal shows bounded retrieval, composition, image preparation, and publication stages.**
- [ ] **Step 4: Inspect the returned structured procedure for one shared overlap step, ordered removal/reassembly, source/evidence IDs, and image refs.**
- [ ] **Step 5: Open the HTML artifact and confirm it is self-contained with embedded prepared images; record exact query/revision IDs and test commands.**
- [ ] **Step 6: Run full local verification, update Issue #110 and Project #8 with exact evidence, commit, push, and verify CI at the pushed SHA.**
