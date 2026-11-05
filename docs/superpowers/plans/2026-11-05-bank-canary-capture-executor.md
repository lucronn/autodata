# Finite dual-bank canary capture executor implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Scope is offline tooling only.

**Goal:** Build and offline-verify a finite dual-bank connector capture executor that preserves raw failure evidence before parsing; authenticated execution remains separately gated.

**Architecture:** A small controller enforces the frozen operation graph and
budgets; a disposable per-request HTTPS child streams originals to private
spools before the unchanged source client validates them. A narrow evidence
contract retains failures and fixed denominators; all implementation verification
uses synthetic offline transports.

**Tech Stack:** Python standard library, existing SourceConnectorClient, unittest.

**Spec:** `docs/agents/specs/2026-11-05-bank-canary-capture-executor.md` (normative schema, bounds, failure contract and exclusions).

Issue: https://github.com/lucronn/autodata/issues/304; parent https://github.com/lucronn/autodata/issues/186.
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhGO_X0`.
Planning branch: `codex/bank-canary-executor-gate`; planning parent:
`c0be267fe31dc578bec0b8528679b6fd6671ed12`. The immutable checkpoint SHA
containing this plan is the builder's base B; obtain full B after commit/push,
read record/task/spec from B and run canonical preflight against exact B.
No self-referential SHA is invented inside its own checkpoint.

## Global constraints

- Do not modify existing product/client bytes or acquire dependencies.
- Only synthetic data and inert credentials during this milestone; no real bank,
  DNS/TLS/provider calls, credential reads or source capture.
- 58 requests/bank, 116 total; 10 pages/branch; one in flight; >=1 second between
  starts; zero retries/redirects; 20,000,000 bytes/response; 100,000,000/bank;
  25-second socket timeout; 900 seconds/bank; 1,800 seconds total including
  10-second cleanup reserve. Smaller test budgets/fake clocks may prove bounds;
  production defaults cannot be enlarged by enrollment.
- Commit small validated milestones and promptly push the assigned codex branch.
- Independent exact-implementation review and a separate enrolled execution gate
  precede any real call; this checkpoint does not authorize merge or deployment.

## Files and interfaces

- Create `scripts/dev/bank_canary_capture.py`: strict enrollment, graph, budgets,
  evidence lifecycle and CLI. Expose `validate_enrollment(document)`,
  `run_capture(enrollment, transport_factory, clock, evidence_root)` and `main(argv)`.
  `run_capture` returns the fixed result schema in the spec, never a raw exception.
- Create `scripts/dev/bank_canary_transport.py`: `CaptureTransport`, a callable
  opener `(request, timeout) -> captured response` injected into each existing
  source client; dedicated child and watchdog own stream capture/cancellation.
- Create `scripts/dev/tests/test_bank_canary_capture.py`: inert fixtures, fake
  clock/transport, child/socketpair cancellation, raw failure and secret tests.
- Update only this plan, spec, synchronized record/task and
  `docs/architecture/independent-bank-connectors.md` for exact implementation
  verification references. No queue/policy/client/application/dependency changes.

## Task 1 — Freeze enrollment and bounded graph

- [ ] Read gate/record/spec from full B; verify synchronized child Issue/Project
  content and exact-B preflight before creating implementation files.
- [ ] Write unittest cases requiring complete two-bank enrollment, missing/extra
  fields rejection, no network creation on invalid input, graph of 58 calls/bank,
  exact one POST/bank, bound cursors and complete frozen article/resource membership.
- [ ] Run the focused suite and observe the expected missing module/function
  failures; implement only `validate_enrollment` and the graph/controller skeleton.
- [ ] Use injected fake `clock.monotonic()/sleep()/utcnow()` and transport fixture
  responses to prove request 59/page 11 never launch, no null terminal cursor,
  exact selector/region/ref/provider/revision correspondence and independent banks.
- [ ] Run the focused suite, `git diff --check`, commit and push this coherent unit.

## Task 2 — Transport capture and hard cancellation

- [ ] Add failing tests for HTTPError/non-200, malformed successful JSON, wrong
  provider/hash/media, byte and aggregate overflow, write failure, no proxy/redirect/
  retry and child blocked-connect/slow-trickle cancellation with partial raw spool.
- [ ] Implement `CaptureTransport` with parent attempt accounting/watchdog and
  bounded child streaming as specified. Capture status/headers/raw before client
  parsing; returned response adapter lets the unchanged client reject envelopes.
- [ ] Prove exact ceiling/EOF handling, global cleanup reserve, no leaked child,
  all failed bytes included in totals and no deadline reset per read/page. Never
  import environment registry or touch application storage entrypoints.
- [ ] Run focused suite and existing source-client tests; commit/push validated unit.

## Task 3 — Evidence contract, CLI and independent handoff

- [ ] Add failing tests for every complete/partial/absent/quarantined raw state,
  killed child journaling, actual inert-token and signed-query leakage, strict
  summary allowlist, immutable earlier run directories, denominator conservation,
  both-bank stop on shared incident and absent receipt/credentials before network.
- [ ] Implement private run/attempt/inventory/result/summary outputs with exclusive
  owner-only files and sanitized enums. CLI `validate --enrollment FILE` performs
  syntax validation only; CLI `offline-selftest` uses inert internal fixtures only.
  CLI `capture --enrollment FILE --approval FILE --bankone-key-fd N
  --banktwo-key-fd N --evidence-root DIR` is implemented but never exercised against
  real origins/credentials under this gate; reject absent/mismatched run approval
  before opening transport. No default capture command or ambient secret fallback.
- [ ] Run focused offline suite, existing source-client suite, syntax checks and
  whitespace checks. Record actual commands/counts/exits and exact SHA; preserve
  failed attempts. Confirm `git diff B --name-only` stays within exact allowlist.
- [ ] Commit/push; obtain independent exact-SHA review of controls and raw failure
  retention. Synchronize only tool-delivery status/evidence. Any later authenticated
  canary requires its own enrolled gate; do not mark source/release acceptance done.

## Verification commands

Run in the assigned checkout with no provider credentials and no application stack:

```sh
PYTHONPATH=workers/ingestion-python/src python3 -m unittest discover -s scripts/dev/tests -p test_bank_canary_capture.py -v
PYTHONPATH=workers/ingestion-python/src python3 -m unittest discover -s workers/ingestion-python/tests -p test_source_connector_client.py -v
python3 -m py_compile scripts/dev/bank_canary_capture.py scripts/dev/bank_canary_transport.py scripts/dev/tests/test_bank_canary_capture.py
git diff --check
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-bank-canary-capture-executor.json --base-sha FULL_GATE_SHA
```

Tests are acceptance-driven cases named in Tasks 1–3 and spec, not mirrored
implementation assertions. All observations are fixture-only. Planning-stage
verification uses the last two applicable commands only (no implementation exists).

## Concrete todo (literal synchronized record)

- [ ] Implement strict frozen enrollment validation and the sequential 58-request-per-bank operation graph using the unchanged provider-bound source client.
- [ ] Implement a cancellable streaming transport with fixed request/page/rate/byte/time budgets, no retries or redirects, and raw response capture before validation.
- [ ] Implement private append-only attempt/raw-inventory and failure outcomes with fixed denominators, quarantine handling and an allowlisted public summary.
- [ ] Prove all limits and failure retention offline with inert credentials and fake transport/socketpair tests; independently review the exact implementation SHA before any later enrolled execution gate.

## External inputs and status

External plan: `/home/corp/autodata-evidence/authentic-bank-canary-plan/PLAN.md`,
SHA256 `dd940de4c74ea73a8552ea1981395d08b66f605144d1de59207e042f25410b06`.
Independent review: `/home/corp/autodata-evidence/authentic-bank-canary-review/REPORT.md`,
SHA256 `3c0620ad4d8a9059703c712d5b1db3928ae5dfb6dbe1279aa8a5a0006e8843db`.
Review found finite executor/raw-error capture absent; this plan supplies that
missing separately gated offline work only. Source client bytes match inspected
candidate 4d82e413 at parent c0be267. Gate synchronization means planned scope
matches repository/child Issue/Project item, not owner enrollment or execution
approval. Authenticated acceptance remains zero; release remains unverified.
