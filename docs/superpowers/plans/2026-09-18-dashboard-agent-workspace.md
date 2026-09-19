# Dashboard Agent Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add back navigation and a vehicle-bound chat/worker workspace after engine/base selection. Reuse normalized records first, ingest AutoAPItwo fallback responses, compile overlap-aware procedures, and persist the compiled result as an immutable Markdown derived article.

**Architecture:** Keep the dashboard as a thin same-origin client. The Go API remains the authenticated boundary. The Python chat/worker runtime receives a structured selected-vehicle context, resolves normalized cache before source fallback, emits bounded progress events, and persists source and derived article data through the existing durable paths.

**Tech Stack:** Static HTML/CSS/JavaScript dashboard, Go API, Python ingestion/chat workers, PostgreSQL derived-article persistence, NATS-backed progress events, AutoAPItwo provider adapter, existing Docker Compose stack.

**Spec:** `docs/architecture/dashboard-agent-workspace.md`

**Issue:** https://github.com/lucronn/autodata/issues/108

**Project:** https://github.com/users/lucronn/projects/8

## Concrete todo

- [ ] Add selector Back behavior that restores the prior row and clears dependent choices.
- [ ] Add the post-configuration chat and bounded worker-terminal workspace.
- [ ] Bind chat requests to the selected canonical vehicle/configuration context.
- [ ] Ensure cache-first lookup, AutoAPItwo fallback, source ingestion, retries, and progress summaries remain durable and idempotent.
- [ ] Render and persist compiled overlap-aware procedures as Markdown derived-article revisions with lineage.
- [ ] Add focused tests, run the full local suite, and exercise the real browser flow.
- [ ] Synchronize the implementation SHA, Issue #108, Project #8, and CI evidence.

## Global constraints

- Preserve user-owned untracked `output/`, `sample data/`, and `tmp/` directories; do not stage them.
- Do not make provider calls from browser JavaScript.
- Do not display secrets, raw provider payloads, or full procedures in the worker terminal.
- Do not block an already viewable result on deep enrichment or a later revision.
- Do not create duplicate source snapshots, normalized articles, or derived revisions for an idempotent retry.
- Keep Markdown body text source-backed and preserve structured lineage/evidence.
- Keep the existing endpoint contracts backward-compatible; add optional request context rather than replacing natural-language messages.

## Task 1: Synchronize the dashboard interaction contract

**Files:**
- Modify: `docs/architecture/dashboard-agent-workspace.md`
- Modify: `apps/api-go/dashboard_test.go`
- Test: `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: existing vehicle selector route and selected configuration records.
- Produces: Back control, workspace shell, chat controls, terminal controls, and stable DOM markers for browser tests.

- [ ] Write failing Go dashboard assertions for the Back control, workspace/chat/terminal/procedure markers, and new JavaScript event markers.
- [ ] Run the focused dashboard test and observe the expected failure.
- [ ] Keep the architecture contract synchronized with the exact UI states and accessible labels.

## Task 2: Add vehicle-bound chat context and Markdown procedure output

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/worker.py`
- Modify: `workers/ingestion-python/src/autodata_ingestion/derived_article_persistence.py`
- Test: `workers/ingestion-python/tests/test_chat_service.py`
- Test: `workers/ingestion-python/tests/test_derived_article_persistence.py`

**Interfaces:**
- Consumes: optional `request_params.vehicle` from `POST /chat/queries`.
- Produces: a selected-vehicle-bound query, source/provider progress summary, and `procedure.markdown` persisted in `derived_article_revisions.body`.

- [ ] Write failing tests proving a supplied vehicle context is used even when the free-text message contains only the job, and that a compiled result contains required Markdown sections.
- [ ] Run the focused Python tests and observe the expected failure.
- [ ] Apply the selected context before intent matching, while preserving the original message for audit and idempotency.
- [ ] Add a deterministic Markdown renderer for vehicle, quote/labor, ordered steps, safety, provenance, and review status.
- [ ] Store the Markdown in the existing immutable revision body and expose it alongside structured procedure data.
- [ ] Add bounded progress summaries for cache hit/miss, AutoAPItwo retrieval, normalization, compilation, persistence, retry, and dead-letter outcomes.

## Task 3: Implement the dashboard Back/workspace client

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/app.js`
- Modify: `apps/api-go/dashboard/styles.css`
- Test: `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: selector response, `POST /chat/queries`, `GET /chat/queries/{id}`, and `GET /chat/queries/{id}/events`.
- Produces: in-place Back navigation, selected vehicle request context, chat transcript, bounded terminal, and Markdown result display.

- [ ] Implement Back as a state-aware control that preserves loaded catalog data and returns to the immediately prior selector row.
- [ ] Show the workspace only after a valid engine/base selection and provide a workspace Back action to return to configuration selection.
- [ ] Send an idempotent request with the selected vehicle context; use a streaming `fetch` reader or durable polling that works with the existing auth boundary.
- [ ] Render terminal events as short stage/message lines with a bounded history and retry/dead-letter labels.
- [ ] Render the default response in consumer-friendly form and expose the generated Markdown in a technical/details region.
- [ ] Handle vehicle options, not-viewable states, section failures, stale/revoked responses, and duplicate requests without losing the selected context.

## Task 4: Verify end-to-end behavior and synchronize delivery

**Files:**
- Modify: `docs/superpowers/plans/2026-09-18-dashboard-agent-workspace.md`
- Modify: `docs/architecture/dashboard-agent-workspace.md`
- Modify: GitHub Issue #108 and Project #8 metadata

**Interfaces:**
- Consumes: local Compose services, AutoAPItwo adapter configuration, browser dashboard, and CI.
- Produces: exact implementation SHA, test output, browser evidence, CI URL, and synchronized tracking.

- [ ] Run focused Go/Python tests, JavaScript syntax checks, integration/contract tests, and `git diff --check`.
- [ ] Rebuild/restart the local services as needed and use the browser to select a real engine/base, press Back, reselect it, submit a natural-language job, and observe chat plus terminal output.
- [ ] Verify a cache hit avoids a provider call where a normalized/derived record exists, and verify a miss reports AutoAPItwo retrieval and persists reusable data.
- [ ] Update Issue #108 and Project #8 with the implementation SHA, verification commands, browser result, and remaining review state.
- [ ] Push the intentional implementation commits to the current remote branch and record the CI run after it completes.

## Base and gate synchronization

The pre-implementation record is pinned to the planning checkpoint base SHA
`a6cc88aed5d8ce73cf0f0c4ac446cc446801368a` and records this plan, Issue #108,
Project #8, the canonical architecture document, and the concrete todo list.
Implementation files may be changed only after the machine preflight reports a
pass for that synchronized record.
