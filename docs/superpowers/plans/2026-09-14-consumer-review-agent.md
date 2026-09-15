# Consumer review agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exercise the live chat contract as a consumer, score each response, retain a safe response/review record, and create deduplicated GitHub issues for reproducible findings.

**Architecture:** A standard-library Python runner calls the configured chat HTTP API, polls the durable query projection, selects an exact vehicle option from case expectations, and evaluates the public answer with deterministic rubric rules. The runner writes a redacted JSON report and optionally uses `gh` with structured arguments to reuse or create issues marked by stable finding IDs.

**Tech Stack:** Python 3.11 standard library, `pytest`, GitHub CLI, existing chat v1 HTTP endpoints.

**Spec:** `docs/architecture/consumer-review-agent.md`

**Tracking:** [Issue #89](https://github.com/lucronn/autodata/issues/89) and
[Project #8](https://github.com/users/lucronn/projects/8)

**Todo:** register the consumer agent; implement bounded chat transport and
deterministic scoring; record redacted responses; deduplicate and create issue
findings; run the live review matrix; reconcile every finding.

## Global Constraints

- No provider credentials, authorization headers, cookies, raw provider HTML, or arbitrary request headers may enter a report or issue body.
- The runner may call only an explicitly configured dev/non-production chat URL and must never deploy production.
- Passing cases do not create issues; issue creation requires the explicit `--create-issues` flag.
- Finding markers are stable and deduplicated against all open and closed issues before creation.
- Reports include the exact implementation SHA, request case, response hash, decision, rubric scores, findings, and issue actions.

---

### Task 1: Register the consumer agent and report contract

**Files:**
- Create: `.cursor/agents/autodata-consumer-agent.md`
- Modify: `.autodata-agent-registry.json`
- Modify: `docs/agents/autonomous-development-system.md`
- Test: `scripts/dev/test_consumer_agent.py`

**Interfaces:**
- Consumes: `docs/architecture/consumer-review-agent.md` and `docs/agents/agent-contracts.md`.
- Produces: registry entry `autodata-consumer-agent` with report-only capability and a documented prompt that cannot merge, deploy, or approve its own result.

- [x] **Step 1: Write the failing registry test**

Assert that the registry contains one `autodata-consumer-agent`, its prompt path exists, and its capabilities exclude merge and production deployment.

- [x] **Step 2: Run the registry test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: FAIL because the registry entry and prompt do not exist.

- [x] **Step 3: Add the prompt, registry entry, and roster row**

The prompt must say the agent reads the supplied chat response, scores only the contract rubric, writes review artifacts, and returns `pass`, `fail`, `blocked`, or `needs_review`; it must not modify candidate implementation files, merge, deploy, or approve safety content.

- [x] **Step 4: Run the registry test to verify it passes**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: PASS.

- [x] **Step 5: Commit the registration**

Run: `git add .cursor/agents/autodata-consumer-agent.md .autodata-agent-registry.json docs/agents/autonomous-development-system.md scripts/dev/test_consumer_agent.py && git commit -m "chore: register consumer review agent"`

### Task 2: Implement the chat runner and deterministic consumer rubric

**Files:**
- Create: `scripts/dev/consumer_agent.py`
- Modify: `scripts/dev/test_consumer_agent.py`

**Interfaces:**
- Consumes: `POST /chat/queries`, `GET /chat/queries/{id}`, `POST /chat/queries/{id}/selections`, and the response shape in `packages/contracts/contract.json`.
- Produces: `run_cases(cases, api_base_url, report_dir, ...) -> dict`, `score_response(case, response, pdf_response=None) -> dict`, and a CLI accepting repeated `--case-file`, `--api-base-url`, `--report-dir`, `--implementation-sha`, `--timeout`, and `--create-issues`.

- [x] **Step 1: Write failing transport and rubric tests**

Cover a processing-to-available response, an ambiguous vehicle requiring selection, a complete illustrated guide, a partial guide that must score `needs_review`, consumer-copy bans, PDF signature/revision parity, and missing-response timeout.

- [x] **Step 2: Run focused tests to verify the new interfaces fail**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: FAIL because `consumer_agent.py` is absent.

- [x] **Step 3: Implement bounded HTTP transport and redaction**

Use `urllib.request` with HTTPS-or-loopback validation, finite connect/read timeouts, bounded response bytes, idempotency keys, and no logging of authorization values. Keep only consumer-visible query/answer data in the report.

- [x] **Step 4: Implement the score dimensions**

Return one score and evidence list for each of: `applicability`, `procedure_coverage`, `figures`, `safety_and_review`, `consumer_copy`, and `pdf_integrity`. Add findings with stable IDs and exact JSON paths; fail closed when required fields are missing.

- [x] **Step 5: Run focused tests to verify the runner passes**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: PASS.

- [x] **Step 6: Commit the runner**

Run: `git add scripts/dev/consumer_agent.py scripts/dev/test_consumer_agent.py && git commit -m "feat: add deterministic consumer chat reviewer"`

### Task 3: Add deduplicated GitHub issue creation and evidence reports

**Files:**
- Modify: `scripts/dev/consumer_agent.py`
- Modify: `scripts/dev/test_consumer_agent.py`
- Create: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: rubric findings and report hash from Task 2.
- Produces: `create_or_reuse_issue(finding, report, repo) -> dict` and stable JSON reports under the caller-provided report directory.

- [x] **Step 1: Write failing issue workflow tests**

Use a fake `gh` executable to assert pass reports make no calls, a finding creates one issue with a stable marker, and a second run reuses the matching open or closed issue.

- [x] **Step 2: Run focused tests to verify issue workflow fails**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: FAIL because issue workflow is absent.

- [x] **Step 3: Implement structured issue reuse/create**

Search issues with `gh issue list --state all --json number,title,body`, match the exact HTML comment marker, and otherwise call `gh issue create --title ... --body-file ... --label ...`. Keep full report content local; issue bodies contain only the bounded finding and report reference.

- [x] **Step 4: Add the operator runbook**

Document dev-only execution, case-file format, report retention, explicit issue creation, no-secret handling, and the rule that a `fail`/`needs_review` report blocks release until dispositioned.

- [x] **Step 5: Run focused tests to verify issue workflow passes**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`

Expected: PASS.

- [x] **Step 6: Commit the issue workflow**

Run: `git add scripts/dev/consumer_agent.py scripts/dev/test_consumer_agent.py docs/verification/consumer-review-runbook.md && git commit -m "feat: record consumer review findings"`

### Task 4: Execute live multi-vehicle review and reconcile findings

**Files:**
- Create: `scripts/dev/consumer_review_cases.json`
- Create: external report directory supplied at runtime, not committed as source.
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/superpowers/plans/2026-09-14-consumer-review-agent.md`

**Interfaces:**
- Consumes: the live dev chat URL and exact provider-backed cases.
- Produces: one report per case, one aggregate report, issue actions, and an updated production-readiness record.

- [x] **Step 1: Define cases**

Include the 1997 RAV4 oil/water-pump replacement, 2005 Camry starter, 2010 Forester SOHC water pump with an explicit selection, and 2002 Civic LX front caliper. Each case declares the expected vehicle identity and required procedure components.

- [x] **Step 2: Run the consumer agent in report-only mode**

Run: `PYTHONPATH=. python3 scripts/dev/consumer_agent.py --api-base-url "$AUTODATA_CHAT_BASE_URL" --case-file scripts/dev/consumer_review_cases.json --report-dir "$AUTODATA_CONSUMER_REVIEW_DIR" --implementation-sha "$(git rev-parse HEAD)"`

Expected: a report for every case with no unclassified findings and no GitHub mutations.

- [x] **Step 3: Review findings and create issues explicitly**

Run the same command with `--create-issues` only when the report contains a reproducible finding that is not already tracked. Record created/reused issue numbers in the aggregate report.

- [x] **Step 4: Re-run after fixes and reconcile tracked issues**

Require the rerun to show the corrected finding as resolved or absent, then update the runbook and canonical contract with exact report hashes and issue links.

- [x] **Step 5: Commit case definitions and evidence references**

Run: `git add scripts/dev/consumer_review_cases.json docs/architecture/consumer-review-agent.md docs/superpowers/plans/2026-09-14-consumer-review-agent.md && git commit -m "test: add live consumer review matrix"`
