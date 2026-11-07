# Catalog buffered-body deadline repair

Goal: Restore bounded catalog connector reads when urllib has closed the underlying socket while buffered response bytes remain.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Canonical evidence: docs/verification/2026-11-07-catalog-closed-socket.md
Record: docs/agents/records/2026-11-07-catalog-closed-socket.json
Planning parent: 0ebbd72c6c3ee29ec65255c207e129e539befa57. The committed documentation checkpoint is the pinned implementation base; run machine preflight against its full SHA before any implementation/test edits.

## Evidence and design

Live configured SourceConnectorClient calls to both providers succeed without the per-call deadline but raise OSError errno9 at source_connector_client.py:270 with timeout=8. The background selector path always supplies a timeout; urllib may retain complete buffered bytes while its socket is already closed. Guarding each settimeout against the closed descriptor and letting response.read1 consume buffered bytes preserves valid responses. Ignore only EBADF from timeout adjustment, not genuine body-read errors. Retain the elapsed deadline checks and tracked shutdown timer; a missing live transport does not remove monotonic checks. Prefer checking socket liveness before timer creation plus narrow EBADF handling for close races.

Add actual loopback HTTP tests with Connection: close, ordinary fixed-length and chunked responses, sufficiently small bodies buffered by header parsing, and both ordinary and bounded calls. Verify selector background uses this path. Existing trickle and chunk-framing deadline regressions must still pass. No provider credentials or live calls are needed for implementation tests.

Allowlist: workers/ingestion-python/src/autodata_ingestion/source_connector_client.py; workers/ingestion-python/tests/test_source_connector_client.py; workers/ingestion-python/tests/test_selector_deepening.py only if needed for the background seam. No schema, selector completeness, catalog persistence, lifecycle, rewrite, payment or runtime changes. Foreground configured source calls already proved source data exists: 2027 makes27/34 vs public6; 2014 makes34/57 vs DB0; Ford2020 models21/9 vs DB9. This fix does not claim fleet completeness: sparse scope markers and absence of durable resume remain separate defects.

## Concrete todo

- [x] Reproduce closed-socket deadline failure with real loopback urllib responses for plain and chunked bodies, retaining foreground behavior and slow-body deadline tests.
- [x] Fix only deadline body reads so buffered bytes remain readable after transport close while live socket and elapsed deadline controls remain enforced.
- [ ] Run focused connector/selector/catalog tests and full ingestion checks as appropriate, obtain independent review and required CI, and push small coherent commits.
- [x] Record exact evidence and outstanding selector completeness limitations; do not deploy, hydrate the fleet, or modify serving data under this code-only gate.

## Validation

Run connector/selector/catalog focused tests and full ingestion tests using the existing isolated Python runtime. Record actual skips and unavailable prerequisites. Check git diff --check. Commit/push checkpoint, verify synchronized tracking readback and exact-base preflight, add failing test, run to show errno9, implement minimal fix, rerun tests and submit reviewed PR. No merge/deploy or production writes under this leaf task.
