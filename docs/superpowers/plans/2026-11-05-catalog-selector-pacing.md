# Catalog Selector Pacing Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this focused plan inline, task-by-task.

**Goal:** Bound, pace and cancel background selector deepening so catalog browsing leaves connector capacity for source-article ingestion.

**Architecture:** Keep the existing daemon and canonical persistence path. Admit one background run per ingestion process and apply a cancelable, finite request budget immediately around each actual background connector catalog request, including pagination. Foreground requests bypass this background guard.

**Tech Stack:** Python threading.Event/RLock, monotonic time, existing Source Connector client, pytest.

**Spec:** `docs/architecture/provider-neutral-catalog-api.md`, selector-deepening section.

## Global constraints

- Planning source: `c1c2a8cfddd155617d0889cfc556e5468b654eca` (`origin/master`). The committed planning checkpoint is the implementation base; obtain its SHA with `git rev-parse HEAD` and run exact-base preflight before editing implementation files.
- Issue: https://github.com/lucronn/autodata/issues/329
- Project: https://github.com/users/lucronn/projects/8 (In Progress).
- No live provider calls, schema/public API changes, new dispatcher, dependencies or distributed coordination. Current operational scope is one ingestion HTTP process; additional replicas require aggregate-budget review before deployment.
- Preserve canonical IDs, provenance, configuration writes, cache-first selectors, article responses and incomplete-scope retry semantics. Never mark an interrupted traversal complete.
- No durable resume exists in the current deepening path; do not invent one. A later foreground request still resolves its exact missing scope normally. A truncated background run can be requested again after cleanup; existing persisted rows survive.

## Evidence and decisions

`ensure_catalog_hydration` schedules deepening for populated makes/models. `_schedule_selector_deepening` deduplicates only equal keys, then starts an unrestricted daemon for each other key. `_deepen_selector_scope` traverses makes/models/configurations without pacing. `_SourceCatalogProvider.resolve_catalog` can perform 1,000 connector pages within one resolve, so pacing only outer model iterations would not bound traffic. TEST observed approximately 100 selector calls/52 seconds under the connector shared 60/min limiter; this checkpoint makes no new provider requests.

Use one process-wide slot under the existing lock. An occupied slot returns internal `already_running` for the same key or `busy` for another key; no queue and no new thread. Clear the slot in `finally`, including thread-start failure. Do not reuse the model-list lookup when semantics are uncertain; keep this change centered on traffic controls.

A per-run control owns a cancellation Event, `deadline=monotonic()+120`, a total remaining connector-attempt count of 12 across both providers. The next allowed background dispatch time is process-wide and survives run cleanup, including cancellation and 429. The first request in an idle process may start immediately; every later attempt, including a new run, starts at least six seconds after the previous attempt. Count failed attempts and each pagination page. Limit provider traversal loops using the same control; stop the run once exhausted rather than catching its stop exception as an ordinary provider failure and continuing. A 429 stops the current background run (no automatic retry loop); subsequent runs still obey normal pacing.

Pass the optional control only through background provider instances, e.g. `_configured_catalog_providers(*, deepening_control=None)` and `_SourceCatalogProvider(client, *, deepening_control=None)`. In `resolve_catalog`, call the control immediately before `client.catalog(...)`; foreground instances retain the existing path. Extend `SourceConnectorClient.catalog` with an optional keyword `timeout` only if needed to cap the actual request by remaining run time; default remains unchanged. Never mutate shared clients or install process-wide monkeypatches.

Provide `cancel_selector_deepening()` to set the active Event; it must be safe when idle and callable from tests/shutdown. Use `Event.wait(delay)` for pacing, rechecking the deadline/event before dispatch and before writes. Cancellation stops future calls and persistence; an in-flight response is discarded if canceled. Background response-body reads, including chunk framing, are bounded by `min(existing client timeout, remaining deadline)` (currently at most 25 seconds) using a tracked socket-shutdown timer that is canceled and joined. urllib pre-response header parsing retains a socket idle timeout; trickled headers may exceed the total wall-clock budget. The 120-second limit governs dispatch and body reads and is not an absolute wall-clock guarantee. Wire cancellation into `run_server` cleanup with a minimal `try/finally`; do not add signal handlers or public endpoints. No claim of immediate cancellation of urllib I/O. Ordinary process/container termination already kills the daemon.

## Todo and implementation tasks

### Task 1: Minimal guard and regression coverage

**Files:** modify `workers/ingestion-python/src/autodata_ingestion/catalog_service.py`; if deadline propagation requires it, `workers/ingestion-python/src/autodata_ingestion/source_connector_client.py`; minimal cleanup in `workers/ingestion-python/src/autodata_ingestion/http_service.py`. Add `workers/ingestion-python/tests/test_selector_deepening.py`; extend existing connector/HTTP tests only for changed interfaces.

- [x] Verify the pinned planning-checkpoint preflight before implementation.
- [x] Add deterministic regression tests for single-flight, per-page pacing, budgets, cancellation and foreground isolation.

Use fake monotonic time and cancelable wait, fake provider pages and persistence, and threading Events for the race tests. Assert these exact behaviors: two distinct simultaneous keys start one daemon; thread-start/provider/persistence failure releases the slot; twelve total attempts can dispatch but the thirteenth cannot; page two cannot bypass six-second spacing; cancellation during wait dispatches nothing further; deadline limits the transport timeout; cancellation during I/O prevents subsequent persistence; 429 stops traversal; foreground catalog/article calls execute while background waits; prior canonical rows remain readable and a stopped traversal sets no complete marker. No timing test should sleep six real seconds. Run the new test file first and record the baseline failure showing the missing guard.

- [x] Add minimal bounded/cancelable controls to the existing selector-deepening path, preserving rows and completeness semantics.

Use a private stop exception or explicit stop return that cannot be swallowed by `CacheFirstCatalogService.resolve`'s ordinary provider-error handler; propagate it out of nested loops to the run's `finally`. Keep exception handling for normal independent provider failures. Ensure the Event/slot is published under the same lock before thread start. Guard persistence after provider return; successful previously persisted configurations are never deleted. Do not change public response shapes.

### Task 2: Validate and synchronize

- [ ] Run focused catalog/connector tests and full ingestion tests; commit/push validated milestones.

Run from repository root (local fixture/stub calls only):

```sh
PYTHONPATH=workers/ingestion-python/src python -m pytest workers/ingestion-python/tests/test_selector_deepening.py workers/ingestion-python/tests/test_catalog_service.py workers/ingestion-python/tests/test_source_connector_client.py workers/ingestion-python/tests/test_http_service.py -q
PYTHONPATH=workers/ingestion-python/src python -m pytest workers/ingestion-python/tests -q
git diff --check
```

Report unavailable DB/container prerequisites and any skipped integration tests accurately; do not claim mocked tests prove live connector fairness. Keep the test command compatible with the project's available Python/Compose environment.

- [ ] Synchronize exact-SHA evidence and operational limits in canonical docs and GitHub; merge after required checks and independent review pass, without deploying.

Update the canonical selector section with implemented limits, cancellation latency and exact tested SHA; update Issue #329 and its Project item, and push small coherent validated commits. Preserve the one-process limitation explicitly. Request independent review before integration. Production deployment remains outside this task.

## Planning gate

Record: `docs/agents/records/2026-11-05-catalog-selector-pacing.json`.

```sh
python scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-catalog-selector-pacing.json --base-sha "$(git rev-parse HEAD)"
```

The implementation base is the pushed checkpoint containing this plan, canonical document update and synchronized record. Planning verification checks JSON, exact-base record validation and `git diff --check`; no application tests or live traffic are required for this documentation-only checkpoint.

## Implementation evidence

- Planning checkpoint `02be27245af55ee7d6cac4a3df2cc80bb61335fb`: exact-base preflight passed with synchronized status and no errors before implementation.
- Implemented code `0acac23e4b759d2ed8060824db97c6301a61276d`: focused catalog, connector, selector and HTTP tests passed 66 tests and 11 subtests; 15 integration-dependent skips.
- TDD baseline reproduced concurrent daemons and thread-start slot leaks. Review regressions reproduced adjacent-run bursts and slow plain/chunked response bodies before their fixes.
- The preceding implementation `392db99df134cc2a2492cf382bf2566e9eca3e60` passed the full worker suite: 912 tests and 142 subtests; 239 skipped. Final full verification of the body/framing deadline correction is running in `/tmp/autodata-selector-pacing-venv`, with pinned Stripe 16.1.0 installed because the host lacks it.
- `git diff --check` passed. All connector calls in new transport tests use loopback servers; no live provider validation or deployment was performed.
- [PR #330](https://github.com/lucronn/autodata/pull/330) is the integration boundary. The user authorized merge after required CI and independent review; deployment remains outside scope.
