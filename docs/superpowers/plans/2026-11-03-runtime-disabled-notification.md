# Disabled remote-control startup notification implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans after the coordinator commits the synchronized checkpoint and pins a passing base. No additional agents or live provider calls are authorized during implementation.

**Goal:** Accept the one source-defined Codex 0.162.1 disabled remote-control startup snapshot while preserving exact gpt-6.1-sol / medium / Fast configured execution, strict replay, and rejection of every unsupported or active remote-control state.

**Architecture:** Add one dedicated startup-state transition to the existing trusted app-server reducer. Successful initialize queues only `initialized`; a validated disabled snapshot then queues the existing first `model/list` request. Live transport and retained-bundle replay use this same reducer, so missing, early, repeated, malformed or active reports cannot advance to a thread or inference. No notification is added to the broad INFO set.

**Tech Stack:** Python standard library, existing version-pinned app-server JSONL transport/reducer and fake-process tests. No dependencies.

**Spec:** `docs/superpowers/plans/2026-11-03-app-server-runtime-contract.md`, `docs/agents/runner-interface.md`, `docs/agents/pre-implementation-gate.md`, and pinned official source below.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Status, authorization and global constraints

This plan passed independent planning review at source SHA256 `7cef44842dc7407d20842bf19bc6c3e9b86f07a0aee0bcd14fa944c5317f1c20` (report `/tmp/autodata-runtime-notification-plan-review.md`). The coordinator is synchronizing Issue #186 / Project #8 / canonical documentation and the task record. Implementation remains blocked until that checkpoint is committed, its exact SHA pinned, and `validate_record` passes. The exact three-file implementation scope below is unchanged.

Parent-reported history: reviewed adapter `f43508beedc4d5ccb1a29ed8e49912d5d6d55a49` integrated at `f4d9568`; scratch prerequisite checkpoint `31d1582` corrected missing bubblewrap. The one actual retry then blocked before model/list or inference on the unmodeled startup notification. Those earlier checkpoints do not authorize this new implementation or another trial. Read-only local implementation inspection used clean f43508b; the coordinator must stage this work on its current integrated base.

- Exact profile: `gpt-6.1-sol`, `medium`, Fast / wire `priority`, `features.fast_mode=true`, `allow_fallback=false`. Keep exact argv, resolved fields, model catalog support/exhaustion and completed-turn requirements.
- Keep all eight gates, schemas, registry, policy, evaluator, protected/frozen adapter bytes, isolated worktrees, environment safeguards, command guards, candidate binding, retained-root binding and cancellation/output/deadline bounds unchanged.
- No profile fallback, settings/configuration changes, daemon reuse, remote-control enable/disable/status/pairing RPC, notification opt-out, automatic retry or privilege change.
- No implementation/testing provider calls, credential inspection, GitHub mutation, push, merge, deployment, bank or production access. Only deterministic fake-process tests during implementation and review.
- Preserve every failed trial, including the earlier d437 evidence and `/tmp/autodata-appserver-success-x0bqiuyu/payload/run`. Never rewrite it to insert proof or claim success.
- A disabled report is informational remote-control connection metadata. It is not model/effort/tier proof, a hostname attestation, proof of historical absence of connections, or an upstream served/billed-tier receipt.

## Evidence and exact source citations

Public official app-server documentation was fetched from https://developers.openai.com/codex/app-server/ ; it does not document this method. Therefore the behavior below is pinned to official `rust-v0.162.1`, commit `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`. Source reads were unauthenticated public reads retained only under `/tmp/autodata-codex-01621-source`.

1. [Method registration, common.rs:2007](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-protocol/src/protocol/common.rs#L2007): `RemoteControlStatusChanged => "remoteControl/status/changed"`.
2. [Notification type, remote_control.rs:26–35](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-protocol/src/protocol/v2/remote_control.rs#L26): camelCase `status`, `serverName: String`, `installationId: String`, `environmentId: Option<String>`. [Status enum:158–166](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-protocol/src/protocol/v2/remote_control.rs#L158) is exactly disabled / connecting / connected / errored.
3. [Initialize response, initialize_processor.rs:212–229](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/request_processors/initialize_processor.rs#L212) is queued before initialization returns. [Transport startup, lib.rs:1231–1254](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/lib.rs#L1231) detects the first successful initialized session, sends configured warnings, sends the current remote-control snapshot to that connection, then completes connection setup. This happens on successful `initialize`, not in response to the client `initialized` notification. [message_processor.rs:746](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/message_processor.rs#L746) only logs client notifications. The disabled report may validly arrive before the client's `initialized` is written, but cannot precede a successful initialize response on this stdio path.
4. [Controller initial state, controller.rs:271–310](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-transport/src/transport/remote_control/controller.rs#L271) initializes a disabled snapshot with hostname, installation ID and environmentId None; start_session at lines80–90 sets connecting only for an enabled desired state. [Disabled-state projection, mod.rs:954–970](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-transport/src/transport/remote_control/mod.rs#L954) always clears environmentId for disabled. Accepting null is source-based, not an invented absence default.
5. [Notification envelope, common.rs:2063–2079](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-protocol/src/protocol/common.rs#L2063) adds camelCase `emittedAtMs: Option<i64>`; [outgoing_message.rs:898–902](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/outgoing_message.rs#L898) always populates it in this pinned emitter. The proposed exception requires this actual current-version field, rather than accepting older serialization variants. Responses and startup notifications use the same outgoing sender (outgoing_message.rs:865–886 and761–795).
6. [Installation identity, installation_id.rs:20–61](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/core/src/installation_id.rs#L20) parses existing UUIDs and returns canonical UUID text, or creates canonical UUIDv4 text. The implementation will validate the notification string, not read this file or the auth home.
7. [Later status watch, lib.rs:1277–1289](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/lib.rs#L1277) suppresses equal snapshots and broadcasts changed snapshots. [mod.rs:817–845](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server-transport/src/transport/remote_control/mod.rs#L817) also suppresses unchanged status updates. General sessions can emit repeated notifications on state transitions; that does not make repeated unchanged disabled reports necessary for this single initialized, stable disabled session. A transition through any active/errored state is outside the allowed session and blocks immediately. The bounded adapter will accept exactly one startup snapshot and reject all repeats, including identical repeats.
8. [Official test, app-server/tests/suite/v2/remote_control.rs:137–153](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/tests/suite/v2/remote_control.rs#L137) consumes a startup disabled/null-environment report. It does not authorize adding its managed-requirements configuration to this task.

Selected nonsecret fields from the retained actual protocol were inspected without opening authentication files: sequence1 client initialize; sequence2 successful initialize response; sequence3 server remoteControl/status/changed; method params keys exactly status/serverName/installationId/environmentId; status disabled; environmentId null; string identity fields; emittedAtMs integer; adapter then failed. No model/list, thread/start or turn/start client frame occurred. The report matches the source-shaped case below.

### Other startup emissions investigated

`InitializeRequestProcessor.send_initialize_notifications_to_connection` (initialize_processor.rs232–243) iterates existing `config_warnings`; these are conditional, not an unconditional clean startup requirement. They remain blocked. `MessageProcessor.connection_initialized` (message_processor.rs815–829) calls workspace-routing notification setup and registers the connection. `workspace_routing.rs131–153` sends `account/updated` only after successful account read with non-null workspace routing and unchanged owner generation; this is conditional and remains blocked. `thread_state.rs384–394` registers the connection without emitting a notification. `AccountRequestProcessor::new` (account_processor.rs115–154) also starts account-cache initialization and a gateway status subscriber; the subscriber (gateway_oauth_notifications.rs24–67) first awaits a gateway-auth change and emits only for a matching configured gateway, so it is conditional rather than a guaranteed startup report and remains blocked. No other unconditional notification was established on this exact clean stdio initialization path. This is a bounded source audit, not a promise that an account/configuration cannot cause another event; any other event still blocks and requires a separately gated diagnosis.

## Exact implementation ownership and fixture audit

Allowed implementation paths are exactly:

1. `scripts/autonomy/app_server_adapter.py`: dedicated state/validation and discovery barrier; no generic INFO expansion.
2. `scripts/autonomy/test_app_server_adapter.py`: actual-shaped snapshot, positive/negative replay tests, shared fake-server startup and process negatives; update pagination fixture indexing affected by the extra frame.
3. `docs/agents/runner-interface.md`: document exact startup exception, discovery barrier, multiplicity, blocked states and certification limits.

Read-only fixture audit at f43508b found all executable app-server fakes in `test_app_server_adapter.py` (`FAKE_CODEX`/`fake_codex`); pure protocol goldens are owned by that file's `exchange()`. `test_runner.py:1299–1322` imports `fake_codex`; its caller script only invokes runner and mocks boundary OS validation. `test_orchestrator.py:147–154` imports the same `fake_codex` and boundary helper for every full-chain run. No other test_*.py defines an independent app-server executable or startup exchange. Therefore updating these shared definitions covers runner signal and orchestrator fixtures without editing those files. They remain required unchanged integration suites. The existing pagination test directly indexes exchange()[0][4] and slices the transcript; update that test to find the model/list response by direction/id/result, then insert pages relative to it rather than assuming a frame offset.

No runner/orchestrator production changes, policy/schema/registry/validate_run changes, workflows, release-controller or application changes. The coordinator alone owns preflight plan/task/tracking checkpoint edits; those are not builder implementation authority.

## Frozen acceptance rule

Accept only a server notification with the following current-version serialization (identity and timestamp examples are synthetic fixture values):

```json
{"method":"remoteControl/status/changed","params":{"status":"disabled","serverName":"autodata-fixture","installationId":"123e4567-e89b-12d3-a456-426614174000","environmentId":null},"emittedAtMs":1793700000000}
```

Require exact top-level key set `{method, params, emittedAtMs}` and exact params key set `{status, serverName, installationId, environmentId}`. No id, error/result, threadId/turnId or profile/config/settings fields are accepted. `status` must equal the string disabled, and environmentId must be present and exactly None. Require emittedAtMs to be an integer with `type(value) is int` (not boolean), `0 <= value <= 2**63-1`; retain it, never use it as wall-clock or profile proof. Require serverName to be a nonempty trimmed string, 1–255 UTF-8 bytes, containing no ASCII control characters; Unicode is allowed. Require installationId to be a string whose `str(uuid.UUID(value)) == value` (canonical lower-case, hyphenated UUID; do not require version4 because source also reuses existing UUIDs).

Add `_Session.initialize_complete = False` and `_Session.remote_control_snapshot = None`. Set initialize_complete only after all existing initialize result/home validation succeeds. At that point queue `initialized` only. The dedicated method branch requires initialize_complete, no prior snapshot, no thread/turn request or completion, and no catalog page/request yet. Validate every field, retain a copy of the params as non-authoritative session metadata, and queue existing `model/list` id2 with cursor null/limit100/includeHidden true. It may be queued behind still-unwritten `initialized`; that preserves client ordering. Require the snapshot in finish as a defense-in-depth invariant. Never regenerate, suppress, normalize or fabricate a server frame.

The reducer's client request/response matching, complete-write causality, thread/turn identities, before-response interleaving once the corresponding request is written, terminal-event rejection, exact runtime profile and retained-root proof all stay unchanged. No new remote-control RPC is sent. Missing notification times out within the existing invocation budget, with no model/list, thread/start or turn/start written. Invalid or active notification blocks immediately before discovery/inference. Repeated reports at any later stage block. This is intentionally stricter than the general protocol's possible changed-state stream.

## Task 1: Reproduce, implement and verify the bounded startup transition

**Files:** modify only adapter and test_app_server_adapter above.

**Interfaces:** keep public `replay_protocol`, `replay_capture`, `run_app_server`, `provider_argv` and caller signatures unchanged. Add only reducer state and the dedicated method branch; an optional private validator may return the copied params. No schema field/artifact kind is added. Retained protocol already captures this actual method and metadata.

- [ ] Read AGENTS, canonical gate, parent runtime plan and synchronized task at the coordinator-pinned base. Re-run validate_record against that committed base; stop on any error before editing code.
- [ ] Add an initially failing actual-shaped positive test by inserting the disabled frame after the valid initialize response in the current golden. Also add a missing-snapshot negative against the old golden; it currently certifies and must stop certifying. Re-number sequence fields after insertion/removal; do not alter candidate/run/profile expectations. Run these tests and retain the actual failures before implementation.
- [ ] Add table-driven negatives for all enum alternatives connecting/connected/errored, arbitrary active/unknown strings, null/bool/object status, missing/null/non-string/empty/whitespace/control/oversized serverName, noncanonical/invalid/missing/non-string UUID, missing or non-null environmentId, omitted/null/bool/string/negative/overflow emittedAtMs, extra params/top-level keys including profile fields, id-bearing server request, duplicate JSON keys, notification before initialize request, between initialize request and response, after a failed initialize, and identical or identity-changing repeats before discovery/during turn/after completion. Validate all fail with ProtocolError, not uncaught exceptions.
- [ ] Add positives for source-ordered notification immediately after initialize response before initialized is written, and after initialized is written but before model/list. Preserve the existing valid thread/turn notifications-before-response regression and rejection before request or after terminal completion.
- [ ] Implement the state transition and validation exactly as frozen above. Import uuid from the standard library only. Move initial model/list queuing from initialize handling to successful disabled snapshot handling; keep IDs/order/params otherwise unchanged. A representative invariant is:

```python
_require(self.initialize_complete and self.remote_control_snapshot is None,
         "unexpected disabled startup snapshot stage/repetition")
_require(self.pages == 0 and not self.thread and not self.turn
         and "model/list" not in self.pending.values()
         and "thread/start" not in self.pending.values(),
         "remote-control snapshot outside initialization")
# Validate exact frame/params keys, disabled/null environment, timestamp,
# bounded textual hostname, and canonical UUID before either assignment.
self.remote_control_snapshot = dict(params)
self.request("model/list", {"cursor": None, "limit": 100, "includeHidden": True})
```

- [ ] Update exchange() to include exactly one actual-shaped disabled snapshot and FAKE_CODEX to emit it immediately after its successful initialize response. Keep intentional version/flood/stall/descendant failures failing before that point. Update the pagination test to locate catalog records by identity, not fixed offsets. Keep all previous failures meaningful; do not skip tests or remove assertions.
- [ ] Extend the real fake process modes with missing/connecting/connected/errored/malformed/repeated disabled reports and a post-valid-report unknown/configWarning. Assert bounded completion, retained actual raw frames and blocked status. Missing/invalid first report must show outbound methods at most initialize/initialized, and zero model/list/thread/start/turn/start; repeated-after-valid may have discovery already written but must have zero thread/start/turn/start. An unavailable exact model must still block after a valid disabled report with no thread or inference. No local execution of request payloads.
- [ ] Run affected tests, then the unchanged runner/orchestrator suites. A successful fake process must retain one disabled snapshot before its first model/list; raw server stdout and selected response still replay byte-for-byte. Existing real caller SIGINT/SIGTERM tests, unavailable-provider tests, all eight-gate fixtures and hash-refresh/retained-root/causality attacks must remain meaningful and pass.

Commands, using the implementation worktree selected by the coordinator:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/autonomy python -m unittest test_app_server_adapter -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/autonomy python -m unittest test_runner test_orchestrator -v
```

## Task 2: Document, complete offline verification and obtain exact-SHA review

**Files:** modify only docs/agents/runner-interface.md, in addition to Task1's two files.

- [ ] Document the exact method and field restrictions, initialize-response ordering, one-snapshot rule, model/list barrier, handling of unavailable/invalid state, and unchanged rejection of config warnings, approvals, reroutes and unknown notifications. Explain that informational disabled state cannot certify effective model, remote-control historical absence, or upstream served tier.
- [ ] Run full offline autonomy verification and diff/scope checks. Record actual counts and exact final SHA; the current reviewed baseline is131 tests, not a target count that may be copied into a result.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
git diff --check
```

- [ ] Commit only the three authorized implementation paths, keep prior retained commits, and confirm clean status. Re-run the full suite at the exact commit because fixture/trusted inputs can depend on HEAD. Hand off exact SHA, actual logs/counts, changed files and limitations to the coordinator.
- [ ] Independent reviewer verifies the exact SHA, source-shaped startup fixture and multiplicity/ordering decisions, all negative/no-inference cases, unchanged strict profile/gates/protected bytes/retained-root semantics, bounded cancellation and the full suite. A passing unit suite alone does not authorize promotion or a provider call. Coordinator separately verifies/promotes only the approved immutable SHA into a new scratch clone.

## Task 3: Coordinator-only single bounded real retry after a fresh checkpoint

No implementation agent or reviewer executes this task. Before it, coordinator must synchronize a fresh trial checkpoint identifying the independently approved exact SHA, verified scratch image prerequisites including existing bubblewrap, permitted non-root boundary proof, retained-root layout and the unchanged exact profile. Inspect the actual container launch, with no privilege/config/profile changes, authorised read-only Codex auth delivery, private default writable Codex home, no GitHub/bank/production credentials/integrations or host sockets, and truthfully recorded standard Docker unrestricted outbound networking. Do not inspect/print auth. Keep the exact original /evidence/... layout for independent replay; copying evidence to a different root does not establish trusted relocation.

- [ ] Create a fresh no-remotes scratch clone, evidence directory and container from the promoted SHA; preserve every previous failed trial directory unchanged. Record exact image/code/checkpoint and the existing supervisor boundary proof; no fixture push/integration.
- [ ] Run exactly one real success-path retry with 120-second per-provider bound and400-second outer trial bound, using the unchanged gpt-6.1-sol/medium/Fast no-fallback task. No automatic retry after any provider/config/notification/runtime failure. Inspect live progress only through actual frames; do not inject, filter, rewrite or synthesize metadata.
- [ ] Retain the actual initialize response, exactly one disabled snapshot, exhausted supported-model catalog, exact resolved model/provider/effort/priority/cwd/permissions, bound strict assigned-check response, matching completed turn and actual exit. Downstream candidate verification and all eight gates remain required if execution reaches them. A partial startup success is not release readiness or authenticated staging acceptance.
- [ ] On another unknown/warning/active/invalid report, retain blocked evidence and stop; open a separately reviewed/gated remediation. If the trial cannot run within the authorized bounds, record blocked/not_executed. Do not convert unavailable/interrupted synthetic negatives into real-trial success. Report configured request settings separately from unobserved upstream served/billed tier. Further real cases/retries require separate coordinator authorization/checkpoint.

## Concrete synchronization todo for coordinator record

1. Review this plan and its source-supported serialization/stage/multiplicity decisions; promote it to the canonical plan path stated above.
2. Synchronize Issue #186, Project #8 and runner-interface documentation with this goal, three-file scope, concrete todo and retained actual failure; create the canonical blocked proposal task record, then set synchronized only after those updates exist.
3. Commit the checkpoint, pin its exact SHA and pass validate_record before implementation; keep exact execution fields and no-fallback settings unchanged.
4. Execute Task1/Task2 with failing regressions, three-file scoped implementation, unchanged integration suites, actual full results and immutable commit.
5. Obtain independent exact-SHA review and coordinator verification/promotion; update tracking with evidence rather than claiming readiness from tests.
6. Create the fresh real-trial checkpoint and perform only Task3's single bounded coordinator retry, retaining every old/new failure and reporting unavailable observations honestly.

No unresolved implementation architecture is left in this proposal. External prerequisites remain the new synchronized planning gate, independent code promotion and fresh authorized trial checkpoint. Availability and future provider notifications remain empirical; any new unsupported behavior stays blocked.
