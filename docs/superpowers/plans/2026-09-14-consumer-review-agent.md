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
findings; enforce case-declared procedure-depth terms such as torque and final
checks; run the live review matrix; reconcile every finding.

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

For procedure-depth coverage, support case-declared required terms and fail the
coverage dimension when required torque or final-check language is absent.

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

### Task 5: Make clean Compose startup release-safe

**Files:**
- Modify: `infra/compose/compose.yaml`
- Modify: `scripts/dev/test_ingestion_smoke.py`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: the migration runner's completion state and the ingestion worker's
  durable chat queue tables.
- Produces: a clean-stack startup contract in which the worker cannot claim
  chat work until the durable runtime schema exists.

- [x] **Step 1: Write the failing Compose dependency regression test**

Assert that `ingestion-worker` declares `migration-runner` with
`service_completed_successfully`.

- [x] **Step 2: Run the regression test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest scripts/dev/test_ingestion_smoke.py -q`

Expected: FAIL because the worker currently starts after dependency health
only and can race the migration runner.

- [x] **Step 3: Add the migration completion dependency**

Make the Compose worker wait for successful migration completion without
changing production deployment or adding credentials.

- [ ] **Step 4: Run focused and live verification**

Run the focused test, recreate a fresh isolated Compose project, verify the
worker remains healthy, and execute the four-case consumer matrix with a
bounded cold-start timeout.

- [ ] **Step 5: Record exact runtime evidence and reconcile findings**

Update the canonical contract, runbook, and synchronized record with the
post-fix report hash, decision, service status, and any remaining human-review
or publication blockers.

### Task 6: Make ready-PDF delivery tolerant of transient upstream failures

**Files:**
- Modify: `apps/api-go/ingestion_http.go`
- Modify: `apps/api-go/ingestion_http_test.go`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: the internal ingestion PDF response and request context.
- Produces: bounded, context-aware retries for transient 502/503/504 PDF
  responses while preserving authorization and byte limits.

- [x] **Step 1: Write the failing proxy retry regression test**

Assert that a transient PDF response is retried and that a successful PDF is
returned without exposing upstream error content.

- [x] **Step 2: Run the regression test to verify it fails**

Run: `go test ./...` from `apps/api-go`.

Expected: FAIL because `GuidePDF` currently forwards the first transient
upstream status without retrying.

- [x] **Step 3: Add bounded context-aware retries**

Retry only transient 502/503/504 responses, with a finite attempt count and
context-aware delay. Do not retry authorization failures or arbitrary client
errors.

- [ ] **Step 4: Run focused and live verification**

Run Go tests, rebuild the QA API from the current checkout, and rerun the
consumer matrix after a cold request and a warm replay.

- [ ] **Step 5: Record exact response and PDF evidence**

Update the canonical contract, runbook, and synchronized record with the
post-fix aggregate report hash and individual PDF hashes.

### Task 7: Bound the long-running internal PDF proxy request

**Files:**
- Modify: `apps/api-go/main.go`
- Modify: `apps/api-go/ingestion_http_test.go`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: the internal ingestion timeout configuration used by chat and PDF
  forwarding.
- Produces: a 120-second default for long-running provider-backed guide
  retrieval while retaining caller cancellation and response-size limits.

- [x] **Step 1: Write the failing timeout-default regression test**

Assert that the API's documented/default internal ingestion timeout is at
least 120 seconds for provider-backed guide generation.

- [x] **Step 2: Run the regression test to verify it fails**

Run: `go test ./...` from `apps/api-go`.

Expected: FAIL because the current default is 30 seconds.

- [x] **Step 3: Raise the bounded default**

Use 120 seconds as the default only for the internal proxy client. Preserve
explicit environment overrides, context cancellation, authorization, and
maximum response bytes.

- [ ] **Step 4: Run focused and live verification**

Run Go tests, rebuild the QA API, and execute cold and warm consumer matrices
covering RAV4, Camry, Forester, and Civic.

- [ ] **Step 5: Record exact matrix evidence**

Update the canonical contract, runbook, and synchronized record with the
post-fix aggregate report and PDF hashes, including any remaining external or
human-review blockers.

### Task 8: Make provider-backed figure retrieval resilient on first use

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/autoapitwo_connector.py`
- Modify: `workers/ingestion-python/tests/test_autoapitwo_connector.py`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: allow-listed AutoAPI Two JSON and image reads used by chat/PDF
  generation.
- Produces: bounded, serialized retries for transient provider responses,
  including 502/503/504 and rate-limit responses, while preserving source
  origin validation, vehicle scoping, byte limits, and fail-closed behavior.

- [ ] **Step 1: Write failing source-read retry tests**

Assert that a transient provider response is retried and that a persistent
transient response remains `SourceUnavailable` after the finite attempt limit.
Assert that non-transient failures are not retried and that a successful
binary figure remains vehicle-scoped.

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/test_autoapitwo_connector.py -q`

Expected: FAIL because source reads currently abort on the first transient
provider response.

- [ ] **Step 3: Add bounded transient source retries**

Retry only the allow-listed transient statuses with a small finite backoff;
honor a numeric `Retry-After` only within a configured cap. Do not retry
redirects, validation errors, authorization failures, oversized responses, or
arbitrary exceptions. Keep all source failures sanitized at the public edge.

- [x] **Step 4: Run focused, full, and live verification**

Run connector and full worker tests, rebuild the isolated QA API/worker from
the current checkout, and execute cold and warm four-case consumer matrices.
The release gate requires RAV4, Camry, Forester, and Civic to complete on the
first PDF request with no blocked case.

- [x] **Step 5: Record exact runtime evidence and reconcile findings**

Update the canonical contract, runbook, synchronized record, and issues #90
and #91 with exact report hashes, PDF hashes, and container health. Close the
findings only when the fresh cold matrix reproduces the fix; otherwise retain
the release blocker. The source-read and query-poll retry regressions pass
locally, but the current cold matrix remains blocked at 2/4; the runtime
findings remain open.

### Task 9: Tolerate transient chat polling failures without hiding outages

**Files:**
- Modify: `apps/api-go/ingestion_http.go`
- Modify: `apps/api-go/ingestion_http_test.go`
- Modify: `scripts/dev/consumer_agent.py`
- Modify: `scripts/dev/test_consumer_agent.py`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: the internal chat query GET and the consumer runner's aggregate
  decision.
- Produces: bounded retries for transient 502/503/504 query reads, with
  caller cancellation preserved, and CLI output that reports the aggregate
  `blocked` decision without relabeling it as `needs_review`. The CLI timeout
  must bound both HTTP requests and per-case polling.

- [x] **Step 1: Write failing polling and status-report tests**

Assert that a transient internal query GET is retried and then returned when
successful, while persistent transient responses remain bounded. Assert that
the consumer CLI's reported decision equals the aggregate decision for
`blocked`, `fail`, `needs_review`, and `pass` outcomes, and that its timeout is
passed through to the per-case polling loop.

- [x] **Step 2: Run focused tests to verify they fail**

Run `go test ./...` from `apps/api-go` and
`PYTHONPATH=. python3 -m pytest scripts/dev/test_consumer_agent.py -q`.

- [x] **Step 3: Add bounded behavior**

Retry only transient query-read statuses with context-aware backoff; do not
retry authorization, validation, or arbitrary client errors. Preserve the
finite response-size limit. Map the runner's printed decision directly from
the aggregate report. Pass the CLI timeout into each case's bounded polling
loop instead of retaining a shorter hidden default.

- [x] **Step 4: Run full and live verification**

Rebuild the isolated API, restart the worker/HTTP process to clear in-process
PDF cache, and execute the cold and warm four-case matrix. Confirm the report
and CLI output agree and that transient polling does not conceal a persistent
failure.

- [x] **Step 5: Record exact evidence**

Update the canonical contract, runbook, synchronized record, and issues #90
and #91 with the exact implementation SHA, report SHA, service health, and
per-case results.

- [x] **Step 6: Continue through transient poll transport errors**

Treat retryable 502/503/504 responses from a GET while a query is still
processing as bounded, retryable poll events in the consumer runner. Continue
polling with context-free finite backoff until the case deadline, and retain a
blocking result for a persistent error or an expired deadline. Add a focused
regression that observes processing, a transient 502, then available; do not
weaken the contract for authorization, validation, malformed, or non-retryable
responses.

### Task 10: Keep public chat answers within the proxy response budget

**Files:**
- Modify: `workers/ingestion-python/src/autodata_ingestion/chat_service.py`
- Modify: `workers/ingestion-python/tests/test_chat_service.py`
- Modify: `docs/architecture/consumer-review-agent.md`
- Modify: `docs/verification/consumer-review-runbook.md`

**Interfaces:**
- Consumes: the durable chat answer and progress history.
- Produces: a compact public answer that preserves consumer procedure,
  figures, safety/review state, and PDF revision identifiers while omitting
  internal evidence/provenance metadata before the API proxy size limit.

- [x] **Step 1: Add a failing public-projection size/redaction regression**

Assert that repeated evidence and source metadata are omitted from the public
answer while procedure steps, image URLs, and worker progress summaries remain
available.

- [x] **Step 2: Implement bounded public projection**

Remove internal provenance keys recursively from the public answer before it is
serialized or sent through the API proxy. Keep durable source data and
internal event behavior unchanged.

- [x] **Step 3: Verify compact answers and the live matrix**

Run focused and full ingestion tests, rebuild the HTTP/worker services, and
repeat the cold four-vehicle consumer matrix. Persistent transport or size
failures remain release-blocking.

Cold and warm four-vehicle matrices pass at implementation `8a2a7ee` with
matching PDF hashes for RAV4, Camry, Forester, and Civic.
