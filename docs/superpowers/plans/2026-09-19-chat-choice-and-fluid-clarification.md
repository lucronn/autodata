# Chat Choice Rendering and Job Clarification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make required chat choices visible and clickable, bind jobs to the selected workspace vehicle, and prevent pump requests from triggering unrelated fluid clarification.

**Architecture:** Keep the existing query/selection API and durable worker lifecycle. The Python chat service will make an explicit workspace vehicle authoritative before intent resolution completes, while the vanilla dashboard will render the existing `vehicle_options` contract and submit selections against the pending query. No new provider, table, or frontend framework is introduced.

**Tech Stack:** Python `pytest`, existing AutoData chat service and HTTP contract, Go-served vanilla HTML/CSS/JavaScript dashboard, Docker Compose local runtime, GitHub Issue #109, Portfolio Project #8.

**Spec:** `docs/architecture/chat-choice-and-job-clarification.md`

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

- [ ] **Step 1: Write the failing backend regressions.** Add tests that create a query with a selected vehicle and message `oil and water pump procedure`, assert `status` is not `awaiting_vehicle`, assert the answer vehicle is the selected vehicle, and assert no warning asks for fluid type or another configuration. Add a pending ambiguous-vehicle test that asserts all options have `option_number`, `label`, `clickable`, and a valid `selection`.
- [ ] **Step 2: Run the focused tests to verify the contract failure.** Run `PYTHONPATH=workers/ingestion-python/src pytest -q workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_chat_intent.py`. Expected: the new selected-vehicle regression fails if the parser can downgrade the workspace context, or the test exposes the current missing fluid/choice contract without changing unrelated tests.
- [ ] **Step 3: Commit the red tests.** Run `git add workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_chat_intent.py && git commit -m "test: pin chat choice and pump clarification behavior"`.

### Task 2: Make the selected workspace vehicle authoritative

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Test: `workers/ingestion-python/tests/test_chat_service.py`
- Test: `workers/ingestion-python/tests/test_chat_intent.py`

**Interfaces:**
- Consumes: `_request_vehicle_context`, `_vehicle_candidates`, `interpret_chat_message`, and `ChatIntent`.
- Produces: a matched vehicle observation preserving the explicit workspace identity while retaining parsed operations and intent flags.

- [ ] **Step 1: Implement the smallest binding change.** When `request_params.vehicle` is present, construct the intent from the user message and the context candidate, then replace only the vehicle observation with a matched observation derived from the selected context. Preserve its internal and provider mappings, year, make, model, drivetrain, engine, and configuration fields. Do not add a fluid operation or a clarification for component-only pump requests.
- [ ] **Step 2: Run focused backend tests.** Run `PYTHONPATH=workers/ingestion-python/src pytest -q workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_chat_intent.py`. Expected: all focused tests pass, including existing ambiguous vehicle selection and structured context tests.
- [ ] **Step 3: Commit the backend fix.** Run `git add workers/ingestion-python/src/autodata_ingestion/chat_service.py workers/ingestion-python/tests/test_chat_service.py workers/ingestion-python/tests/test_chat_intent.py && git commit -m "fix: bind chat jobs to selected vehicle context"`.

### Task 3: Render and submit available choices in the dashboard

**Files:**
- Modify: `apps/api-go/dashboard/index.html`
- Modify: `apps/api-go/dashboard/app.js`
- Modify: `apps/api-go/dashboard/styles.css`
- Test: existing dashboard route/asset tests in `apps/api-go/dashboard_test.go`

**Interfaces:**
- Consumes: public query `vehicle_options`, `query_id`, `POST /chat/queries/{id}/selections`, `authHeaders`, and existing polling/event stream.
- Produces: native accessible choice buttons, idempotent selection submission, and correct pending-query messaging.

- [ ] **Step 1: Write the failing dashboard contract test.** Assert the dashboard asset contains a dedicated choice region, a selection handler for `/selections`, and a pending-state branch that does not claim a result is ready.
- [ ] **Step 2: Run the dashboard test to verify it fails.** Run `go test ./apps/api-go -run Dashboard -count=1`. Expected: FAIL because the current asset has no choice region or selection handler.
- [ ] **Step 3: Implement minimal choice rendering and selection.** Add a choice region next to the chat log. Render every `vehicle_options` item as a native button with number and label, remove stale options when the query proceeds, post the option selection to the existing endpoint, stream/poll the same query, and display an explicit unavailable/error message when options are missing. In `submitChat`, render the initial query response immediately and append “The result is ready below” only when `pollQuery` returns a terminal `available` or `failed` result.
- [ ] **Step 4: Run focused dashboard and syntax checks.** Run `go test ./apps/api-go -run Dashboard -count=1` and `node --check apps/api-go/dashboard/app.js`. Expected: PASS with no JavaScript syntax errors.
- [ ] **Step 5: Commit the dashboard fix.** Run `git add apps/api-go/dashboard/index.html apps/api-go/dashboard/app.js apps/api-go/dashboard/styles.css apps/api-go/dashboard_test.go && git commit -m "fix: show clickable chat choices"`.

### Task 4: Verify the integrated runtime and synchronize delivery

**Files:**
- Modify: `docs/architecture/chat-choice-and-job-clarification.md`
- Modify: `docs/superpowers/plans/2026-09-19-chat-choice-and-fluid-clarification.md`
- Create: `docs/agents/records/2026-09-19-chat-choice-and-fluid-clarification.json`
- Update: GitHub Issue #109 and Project #8

**Interfaces:**
- Consumes: exact implementation SHA, local test output, Compose runtime, live browser behavior, and GitHub Actions result.
- Produces: synchronized repository/GitHub status with reproducible evidence.

- [ ] **Step 1: Run complete relevant local verification.** Run the ingestion worker suite, Go suite, JavaScript syntax check, contract checks, and `git diff --check`; record exact pass counts and intentional skips.
- [ ] **Step 2: Rebuild and exercise the live browser flow.** Rebuild/restart the local API and ingestion services without printing secrets. Select a vehicle, submit `oil and water pump procedure`, verify no fluid/configuration clarification appears, and exercise an ambiguous query through visible numbered option buttons and a clicked selection. Capture terminal status and final query state.
- [ ] **Step 3: Update canonical docs and synchronized record.** Record the exact implementation SHA, test commands/results, browser URL and observed behavior, and CI run URL. Set the record to `status: synchronized` only after the Issue, Project item, and docs contain the same concrete todo and evidence.
- [ ] **Step 4: Push and verify remote state.** Run `git status --short --branch`, `git push origin HEAD`, and `gh run list --repo lucronn/autodata --branch "$(git branch --show-current)" --limit 5`. Expected: the pushed branch contains only intentional implementation/docs changes; user-owned untracked directories remain unstaged; the relevant verification run is identified without claiming success until its conclusion is `success`.
