# Chat Choice Rendering and Job Clarification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make required chat choices visible and clickable, bind jobs to the selected workspace vehicle, and prevent pump requests from triggering unrelated fluid clarification.

**Architecture:** Keep the existing query/selection API and durable worker lifecycle. The Python chat service will make an explicit workspace vehicle authoritative before intent resolution completes, while the vanilla dashboard will render the existing `vehicle_options` contract and submit selections against the pending query. No new provider, table, or frontend framework is introduced.

**Tech Stack:** Python `pytest`, existing AutoData chat service and HTTP contract, Go-served vanilla HTML/CSS/JavaScript dashboard, Docker Compose local runtime, GitHub Issue #109, Portfolio Project #8.

**Spec:** `docs/architecture/chat-choice-and-job-clarification.md`

**GitHub Issue:** https://github.com/lucronn/autodata/issues/109

**GitHub Project:** https://github.com/users/lucronn/projects/8

## Global Constraints

- The selected `request_params.vehicle` is authoritative for the current workspace request.
- A choice prompt must render the available options before asking the user to choose.
- `oil pump` and `water pump` are component operations, not fluid-type requests.
- Existing query selection endpoint, idempotency behavior, and durable worker stream remain the integration boundary.
- User-owned untracked `output/`, `sample data/`, and `tmp/` remain unstaged.
- All implementation changes require focused tests, full relevant suites, live browser verification, a pushed commit, and synchronized Issue/Project evidence.

## Review Focus

- Ambiguous vehicle query: every returned option is visible, numbered, and clickable; test at the dashboard route/asset boundary.
- Clicked option: the original pending query resumes through the selection endpoint; test in `workers/ingestion-python/tests/test_chat_service.py`.
- Selected vehicle plus component words: `oil and water pump procedure` remains bound to the workspace vehicle and does not become a configuration clarification; test in `workers/ingestion-python/tests/test_chat_service.py`.
- Fluid-specific request: an explicit fluid operation retains its clarification boundary; test in `workers/ingestion-python/tests/test_chat_intent.py` or the chat service contract.
- Pending query: the dashboard does not append “result ready” or expose a stale result while it is awaiting a choice; test the JavaScript-visible route contract and browser flow.

### Task 1: Pin the backend context and choice contract with failing tests

**Files:**
- Modify: `workers/ingestion-python/tests/test_chat_service.py`
- Modify: `workers/ingestion-python/tests/test_chat_intent.py`

**Interfaces:**
- Consumes: `create_chat_query`, `select_chat_vehicle`, `process_chat_jobs`, and existing `request_params.vehicle` input.
- Produces: executable regressions proving selected vehicle binding, no pump/fluid clarification, and pending-option behavior.

- [x] **Step 1: Write the failing backend regressions.** Added selected-context and pump regression coverage plus the existing numbered-option contract assertions.
- [x] **Step 2: Run the focused tests to verify the contract failure.** The selected-context test failed with `failed` instead of `processing` because `Continental Oil And` was parsed as the model; the dashboard asset test also failed before the choice region and selection handler existed.
- [x] **Step 3: Commit the red tests.** The tests were kept with the implementation commit after the red/green cycle.

### Task 2: Make the selected workspace vehicle authoritative

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Test: `workers/ingestion-python/tests/test_chat_service.py`
- Test: `workers/ingestion-python/tests/test_chat_intent.py`

**Interfaces:**
- Consumes: `_request_vehicle_context`, `_vehicle_candidates`, `interpret_chat_message`, and `ChatIntent`.
- Produces: a matched vehicle observation preserving the explicit workspace identity while retaining parsed operations and intent flags.

- [x] **Step 1: Implement the smallest binding change.** `_bind_selected_vehicle_context` now makes the explicit workspace selection authoritative while preserving parsed operations and intent flags.
- [x] **Step 2: Run focused backend tests.** Focused chat service and intent tests passed (`52 passed`); the complete ingestion worker suite passed (`423 passed, 3 skipped, 12 subtests passed`).
- [x] **Step 3: Commit the backend fix.** The backend and dashboard implementation are committed at `6e96f491df7172595217227efdb9456c2ab56ff4`.

### Task 3: Render and submit available choices in the dashboard

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/app.js`
- Modify: `apps/api-go/dashboard/styles.css`
- Test: existing dashboard route/asset tests in `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: public query `vehicle_options`, `query_id`, `POST /chat/queries/{id}/selections`, `authHeaders`, and existing polling/event stream.
- Produces: native accessible choice buttons, idempotent selection submission, and correct pending-query messaging.

- [x] **Step 1: Write the failing dashboard contract test.** Added route/asset markers for the choice region, selection endpoint, awaiting state, and terminal completion copy.
- [x] **Step 2: Run the dashboard test to verify it fails.** The initial test failed because the current asset had no choice region or selection handler.
- [x] **Step 3: Implement minimal choice rendering and selection.** The dashboard now renders native numbered buttons, submits the existing selection payload, keeps the original query, and does not claim a result while awaiting a choice.
- [x] **Step 4: Run focused dashboard and syntax checks.** The dashboard tests and `node --check apps/api-go/dashboard/app.js` passed.
- [x] **Step 5: Commit the dashboard fix.** The implementation is committed at `6e96f491df7172595217227efdb9456c2ab56ff4`.

### Task 4: Verify the integrated runtime and synchronize delivery

**Files:**
- Modify: `docs/architecture/chat-choice-and-job-clarification.md`
- Modify: `docs/superpowers/plans/2026-09-19-chat-choice-and-fluid-clarification.md`
- Create: `docs/agents/records/2026-09-19-chat-choice-and-fluid-clarification.json`
- Update: GitHub Issue #109 and Project #8

**Interfaces:**
- Consumes: exact implementation SHA, local test output, Compose runtime, live browser behavior, and GitHub Actions result.
- Produces: synchronized repository/GitHub status with reproducible evidence.

- [x] **Step 1: Run complete relevant local verification.** The ingestion worker suite passed `423 passed, 3 skipped, 12 subtests passed`; `go test ./...`, dashboard JavaScript syntax, and `git diff --check` passed.
- [x] **Step 2: Rebuild and exercise the live browser flow.** Compose services were rebuilt/restarted. The browser pump request completed with an available procedure and no fluid/configuration clarification. The live API choice path returned four options and option 1 resumed the same query with the selected vehicle.
- [x] **Step 3: Update canonical docs and synchronized record.** This plan, the architecture contract, Issue #109, Project #8, and the gate record now reference the implementation SHA and current verification evidence.
- [ ] **Step 4: Push and verify remote state.** Run `git status --short --branch`, `git push origin HEAD`, and `gh run list --repo lucronn/autodata --branch "$(git branch --show-current)" --limit 5`. Expected: the pushed branch contains only intentional implementation/docs changes; user-owned untracked directories remain unstaged; the relevant verification run is identified without claiming success until its conclusion is `success`.

## Current evidence

- Implementation: `6e96f491df7172595217227efdb9456c2ab56ff4`.
- Local verification: Python `423 passed, 3 skipped, 12 subtests passed`; Go `go test ./...` passed; JavaScript syntax and diff checks passed.
- Browser verification: `http://127.0.0.1:8080/dashboard/?fresh=final` completed the selected-vehicle pump request without a fluid/configuration question.
- Remote CI: pending until the pushed commit's verification run concludes.
