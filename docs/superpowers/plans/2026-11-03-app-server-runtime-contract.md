# App-server runtime contract implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task after the fresh planning gate passes. No additional agents or live provider calls are authorized by this planning document.

**Goal:** Retain and replay truthful resolved local-cli execution settings through the bounded Codex 0.162.1 app-server protocol, with exact gpt-6.1-sol / medium / Fast and no fallback.

**Architecture:** A small trusted Python adapter owns one Codex 0.162.1 stdio app-server process, one ephemeral thread and one turn. It records actual client/server frames and validates resolved configuration before starting inference. Runner and orchestrator replay the same pure protocol reducer against retained, candidate-bound artifacts; a manifest assertion is never evidence by itself.

**Tech Stack:** Python standard library, subprocess/selectors/process groups, JSONL, existing v2 evidence contracts, installed Codex CLI 0.162.1. No new dependencies.

**Spec:** `docs/agents/runner-interface.md`, `docs/verification/2026-11-03-agent-evidence-hardening.md`, the canonical `docs/agents/pre-implementation-gate.md`, and the pinned official protocol sources below. This document supplies the bounded runtime adapter design.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Planning inspection base: `d437eff812b0efb0d3dbdf8388cd2f9c7916f12d`.

## Status and global constraints

**BLOCKED for implementation.** This is a proposed checkpoint, not a synchronized dispatch. The coordinator must synchronize the Issue/Project and canonical runner documentation, commit a fresh record with `status: synchronized`, pin the resulting implementation base, and run `validate_record` against that exact committed base. Do not use d437 or this blocked record as implementation authorization. Planning edits in this checkpoint are only this plan and `docs/agents/tasks/2026-11-03-production-release/r0-app-server-runtime.json`.

- Exact execution: `gpt-6.1-sol`, reasoning `medium`, Fast configuration/wire tier `priority`, `features.fast_mode=true`, `allow_fallback=false`; no substitutions.
- Certification means **resolved runtime model, reasoning effort and Fast request settings**. It does not mean a receipt for an upstream served or billed tier. Upstream served tier is unobserved and must never be claimed.
- Preserve all eight gates, candidate-scoped local verification, synthetic provenance scope, schema/runtime path safety, protected frozen inputs, isolated worktrees, retained local commits, parent environment filtering and command guards.
- No schema, registry, policy, evaluator (`validate_run.py`), workflow, release-controller, application or production changes. No live provider calls in tests, no GitHub writes, push, merge, deployment, bank access or credential inspection.
- Preserve prior failures, including `/tmp/autodata-cli-d437-ti73fxjo/evidence/run`; never backfill proof into an old run. Synthetic transcript tests cannot certify a real provider or real staging.

## Official source evidence and trust meaning

Official documentation: https://developers.openai.com/codex/app-server/ , https://developers.openai.com/codex/speed/ , https://developers.openai.com/codex/config-reference/ .

Freeze protocol support to official `rust-v0.162.1`, source commit `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d` (https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d). Relevant paths under that commit:

- `codex-rs/app-server-protocol/src/protocol/v1.rs`: InitializeParams/Response and capabilities.
- `codex-rs/app-server-protocol/src/protocol/v2/{model,thread,turn,item,thread_data}.rs`: catalog pagination/serviceTiers, thread/start resolved response, turn/start outputSchema, item/completed, turn/completed and error/approval shapes.
- `codex-rs/app-server/src/request_processors/thread_processor.rs:1622`: response fields come from the runtime configuration snapshot.
- `codex-rs/exec/src/lib.rs:1170`: exec uses the thread response as its authoritative bootstrap payload.
- `codex-rs/exec/src/{exec_events,event_processor_with_jsonl_output}.rs`: exec JSONL drops startup configuration; no session_config variant exists.
- `codex-rs/protocol/src/protocol.rs`: TurnContextItem has model/effort but no tier; ThreadSettingsApplied snapshots have configured tier.
- `codex-rs/rollout/src/policy.rs`: persists ThreadSettingsApplied, excludes SessionConfigured and ModelReroute. Do not rely on the stale SessionConfigured deserialization comment as persistence proof.
- `codex-rs/protocol/src/openai_models.rs:998` and `codex-rs/core/src/client.rs:979`: unsupported request tiers can be omitted. Require actual matching model catalog serviceTiers support in addition to resolved thread settings.

The existing ephemeral CLI stdout has no sufficient metadata. Rollout discovery is rejected as this adapter's evidence source: it requires persistence, omits tier in per-turn context, and does not retain reroutes. No model prose, CLI flags, catalog defaults alone, or inferred absent fields substitute for runtime fields. No upstream service receipt is added or invented.

## Exact implementation ownership and interfaces

Create `scripts/autonomy/app_server_adapter.py` and `scripts/autonomy/test_app_server_adapter.py`. Modify only `scripts/autonomy/runner.py`, `scripts/autonomy/test_runner.py`, `scripts/autonomy/orchestrator.py`, `scripts/autonomy/test_orchestrator.py`, `.cursor/agents/autodata-architect.md`, and `docs/agents/runner-interface.md`.

Adapter public interfaces (standard-library types):

```python
def replay_protocol(records: list[dict], *, expected: dict) -> dict:
    # Returns {profile: dict, thread_id: str, turn_id: str,
    #          response_text: str, completed: bool}; raises ProtocolError.
    ...

def run_app_server(*, argv: list[str], cwd: Path, env: dict[str, str],
                   prompt: str, schema: dict, expected: dict,
                   boundary_proof: Path, timeout_seconds: int) -> dict:
    # Existing bounded_process status/exit/output-budget fields, raw stdout/stderr,
    # plus protocol bytes, replay result and response bytes. No success on errors.
    ...
```

`expected` is constructed exclusively from validated frozen inputs plus the invocation: exact execution profile, absolute isolated cwd, run/task/agent/evidence label, trusted-base SHA, initial subject SHA, SHA-256 of prompt bytes and provider schema bytes. It is not provider-authored. `ProtocolError` becomes a blocking finding, never a permissive default. The adapter has no schema-policy authority, GitHub client or task mutation API.

Runner snapshots and byte-compares the loaded adapter against its blob at trusted_base_sha, retains it as a trusted-input artifact, and adds it to protected paths. An untrusted candidate cannot replace the reducer. Orchestrator uses the same frozen adapter bytes and independently derives expectations from trusted task/prompt/schema plus retained validated invocation; it does not trust the run's observed_execution or adapter summary.

## Disposable execution boundary and approval decision

Real adapter execution is supported **only inside the already authorized disposable no-GitHub/no-bank/no-production container**. Ordinary-host execution fails before spawning Codex, even if a caller sets a suggestive environment variable. Pure replay and fake-process tests remain usable outside the container and never invoke Codex.

The coordinator's trusted container supervisor must supply a read-only, root-owned regular attestation file outside the candidate checkout at `/run/autodata/runtime-boundary.json`. The adapter runs as a non-root UID. Require `lstat` regular/no symlink, root owner, no group/world write, read-only containing mount, version 1, `purpose: r0-disposable-provider`, `network_scope: codex-only`, `github_access: false`, `bank_access: false`, `production_access: false`, `host_credentials_mounted: false` (no host home/credential mounts; separately authorized disposable Codex credential delivery is not a host credential mount), an exact allowed worktree/output root, the container's current `/proc/self/ns/{mnt,net,pid}` identities, and the supervisor-declared disposable CODEX_HOME path. Compare namespace identities and real paths with the running process; reject missing/mismatched/unverifiable proof. This is a trusted supervisor assertion backed by OS isolation, not a claim that a marker creates isolation. The supervisor must establish the asserted restrictions independently; adapter checks alone cannot inspect every host/network capability.

No container launcher implementation is authorized in this change. The coordinator must provide this scratch attestation and non-root boundary when staging the already authorized container; if the existing launcher cannot supply it, runtime trials stay blocked until a separately scoped launch change is reviewed. Do not add host fallback or reinterpret a missing attestation as permission.

Use `approvalPolicy: never` and `sandbox: danger-full-access` **only after this boundary validation**, deliberately relying on disposable OS isolation for commands and Git metadata needed by local commits. Do not use `--approve-for-me`, automatic guardian approval, `--dangerously-bypass-approvals-and-sandbox`, host approvals or arbitrary server-request execution. An unexpected command/file approval request gets the supported `decision: cancel`, marks the run blocked and starts cancellation; permission/user-input/dynamic-tool/MCP/other server requests get JSON-RPC method-not-found and cancellation. Never dispatch their payloads locally. The container is essential because model commands can use absolute binaries and cannot be confined by PATH guards alone.

Retain parent `_safe_environment`, guard PATH, noninteractive Git and GH_CONFIG_DIR isolation. Supervisor supplies fresh disposable CODEX_HOME/config and only already authorized Codex authentication delivery; implementation never opens, copies, prints or diagnoses credentials. Do not reuse a host daemon, socket, config or auth home. Existing config files under candidate control cannot override the frozen effective fields without blocking. No new authentication workflow is introduced.

## Frozen 0.162.1 protocol and state machine

Start exact argv, without shell interpolation: `codex app-server --stdio --strict-config -c model="gpt-6.1-sol" -c model_reasoning_effort="medium" -c service_tier="fast" -c features.fast_mode=true`. These are argv element values, not shell text. Require a bounded local `codex --version` result exactly `codex-cli 0.162.1`; no automatic update or fallback. Retain the version result and exact subprocess argv in the protocol capture's runner-owned start record. Configuration is requested here but confirmed only through subsequent official responses.

Stdio is newline-delimited JSON request/response objects, without inventing a `jsonrpc` field. Unique integer client IDs start at 1. Match responses to an outstanding request exactly once, reject duplicate JSON keys, malformed frames, unknown response IDs, conflicting responses, unexpected second threads/turns, ID type confusion and unsupported profile-affecting events. Notification interleaving before corresponding responses is buffered within the same bounds and bound once IDs arrive; do not assume adjacent response/notification ordering.

1. Send `initialize` with `params: {clientInfo: {name: autodata-r0, title: AutoData R0, version: 1}, capabilities: {experimentalApi: false, optOutNotificationMethods: []}}` (string values). Require a successful response (`userAgent`, `codexHome`, `platformFamily`, `platformOs`); require returned codexHome equals supervisor disposable home. Then send notification `{method: initialized}`. Never suppress notifications or opt into raw Responses/MCP experimental events.
2. Send `model/list` with `{cursor: null, limit: 100, includeHidden: true}`. Follow returned `nextCursor` to proven exhaustion, maximum 16 pages/1600 entries, reject repeated cursors, duplicate IDs and inconsistent duplicate model identities. Each response has `data` and `nextCursor`. Require exactly one matching `model: gpt-6.1-sol` (record its `id` separately), an advertised `supportedReasoningEfforts` entry `reasoningEffort: medium`, and `serviceTiers` entry `id: priority`. Deprecated `additionalSpeedTiers`, picker defaults, model names inferred from displayName and availability promises are insufficient. Missing/ambiguous profile blocks before thread/start and inference.
3. Send `thread/start` with `{model: gpt-6.1-sol, modelProvider: openai, serviceTier: priority, cwd: <isolated cwd>, approvalPolicy: never, sandbox: danger-full-access, ephemeral: true, config: {model_reasoning_effort: medium, features.fast_mode: true}}`. Do not enable provider fallback, resume/fork, plugins, dynamic tools, external transports, goals or environments. The omitted experimental allowProviderModelFallback defaults false in 0.162.1. Require response `thread.id`, `model: gpt-6.1-sol`, `modelProvider: openai`, `reasoningEffort: medium`, `serviceTier: priority` (or explicitly documented equivalent fast), cwd, approvalPolicy and `sandbox: {type: dangerFullAccess}`; reject missing/null/mismatched fields. Require thread/started identity if emitted. The service tier is the resolved request setting and catalog-supported; it is not an upstream receipt.
4. Send one `turn/start` with `{threadId: <thread.id>, input: [{type: text, text: <frozen prompt>, text_elements: []}], outputSchema: <frozen provider schema>}`. `text_elements` is the field name in tagged UserInput::Text (no camelCase rename on that variant's fields); freeze against source/generated shape in tests. No model/effort/serviceTier/serviceTierForTurn/collaborationMode/cwd/permissions/settings override fields. Require successful response `{turn: {id, status, ...}}`. Bind every turn notification to this thread and turn; reject turn IDs from any other session. A completed response may race notifications; still require the matching authoritative turn/completed notification.
5. On `item/completed`, use `params.threadId`, `params.turnId`, `params.item`. Record only actual completed `agentMessage` items (`id`, `text`, optional phase). Accept one terminal `phase: final_answer` message; if phase is absent, require exactly one agentMessage total and no ambiguity. Commentary is never concatenated into JSON. Require its full text parses as one strict v2 JSON object, with no markdown stripping or tolerant repairs. Capture response bytes from that exact item, not model-written files or delta concatenation. `turn/completed` carries `{threadId, turn: {id, status, error, ...}}`; require matching `status: completed`, `error: null`, and no contradictory final item text in included turn.items. Deltas are informational only.
6. No outbound settings/update, turn/settings/update, turn/steer, resume/fork or second inference. Any `model/rerouted` blocks regardless of target; conflicting profile/settings notifications, explicit server error, turn failure/interruption, approval or protocol anomaly block. The informational notification allowlist is exactly `thread/status/changed`, `thread/name/updated`, `thread/tokenUsage/updated`, `turn/diff/updated`, `turn/plan/updated`, `item/started`, `item/agentMessage/delta`, `item/commandExecution/outputDelta`, `item/commandExecution/terminalInteraction`, `item/fileChange/outputDelta`, `item/fileChange/patchUpdated`, `item/reasoning/summaryTextDelta`, `item/reasoning/summaryPartAdded`, `item/reasoning/textDelta`, and `account/rateLimits/updated`. Retain them and validate any supplied threadId/turnId against the bound session; they cannot establish profile/completion. Thread/turn/item lifecycle methods described above are handled separately. Error, warning, configWarning, deprecationNotice, auth recovery, hooks, compaction, guardian approval, MCP, external agent and any other unknown methods block until separately reviewed. Allowed completed item types are `agentMessage`, `reasoning`, `commandExecution`, `fileChange`, and `plan`; other tool/collaboration items block. Token usage is not execution profile proof.
7. After valid completion, close stdin, wait up to 2 seconds, terminate/reap the process group if needed. Success requires completion and clean server exit 0; a valid message followed by process failure is blocked. No turn/read fallback or second provider inference to recover an incomplete transcript.

All object examples above describe exact wire keys with string values quoted when serialized; request sandbox `danger-full-access` differs from response sandbox `{"type":"dangerFullAccess"}`. The adapter must not camel-case `text_elements`. Version/shape fixture generation via installed `codex app-server generate-json-schema` is allowed offline in `/tmp` during implementation; compare the above spelling (especially tagged text input and approval/sandbox variants) to the pinned source before fixtures are committed. A contradiction is a plan error requiring coordinator checkpoint correction, not permission to guess or silently broaden acceptance.

## Bounds, cancellation and retained artifacts

One monotonic deadline covers version probe, handshake, catalog, thread startup and turn (caller timeout 1..1800 seconds); reserve the last 3 seconds for cleanup and do not start the provider if that leaves no execution budget. Catalog/handshake waits consume that deadline; real certification uses 120 seconds/provider and 400 seconds outer trial. Use selectors to drain stdout/stderr concurrently and send bounded stdin; no blocking readline, unlimited queues or nested provider retries. Maximum one protocol JSON line 1 MiB, server stdout 4 MiB, stderr 4 MiB, client protocol bytes 4 MiB, combined transcript 12 MiB, outbound prompt+schema 1 MiB, 10,000 frames. Budget exhaustion fails immediately and retains bounded diagnostic bytes with an explicit truncation flag. Preserve existing artifact 16 MiB and check output limits.

At deadline, interruption, approval or error: send `turn/interrupt` with `{threadId, turnId}` only if IDs are known, allow at most 1 second acknowledgement/drain, then SIGTERM process group and SIGKILL after at most 1 additional second, always reap. If IDs are unavailable, go directly to group termination. Cancellation frames are real writes and retained; interrupted/killed providers never certify regardless of final text. Outer caller cancellation follows the same finally cleanup path.

Keep raw server stdout, stderr and invocation artifacts. Add deterministic `<label>:protocol`, existing kind `stdout`, check_id null, bound to the same observed subject as the provider artifacts. Its JSONL records have local sequence number, direction (`client`/`server`), and exact raw line; a runner-owned header records protocol adapter version, actual CLI version/argv, expected-context digest and verified nonsecret boundary metadata. The header is expressly adapter metadata, not an official server event. Record complete client frames only after write completion. Retain all server frames and compare their exact byte sequence to retained raw stdout on replay; detect omitted/injected/reordered frames. Apply existing redaction before persistence, reject redaction that changes required protocol/control/profile fields, and do not dump arbitrary process environments. Never synthesize session_config.

Runner generates the existing provider-response artifact from the validated completed item. Provider invocation output_ids must reference both response and protocol artifacts. Update both producer and strict replay inventory/identity checks accordingly using existing kind values. Bind protocol, raw output, invocation and response to run/task/agent/evidence label, exact prompt/schema hashes, trusted inputs, actual thread/turn, candidate and worktree. The initial subject in the invocation may differ from a builder's locally committed final subject; preserve existing builder initial-to-final local commit rules and assign postrun artifact subject exactly as existing code does. Reviewers remain read-only; candidate checks continue to run before provider invocation at the required SHA.

The replay reducer recomputes profile and selected response, verifies exact request allowlist, completion, version and all identities, and compares derived response bytes with provider-response. Existing observed_execution is derived output only; tampering with it cannot pass. Legacy session_config-only synthetic proof and historical incomplete runs cannot certify the new transport. Retained real failures remain unchanged and blocked.

## Concrete todo

- [ ] Synchronize Issue #186, Project #8, canonical runner documentation, this plan and this concrete todo; commit a fresh synchronized task record and pass validate_record at the exact implementation base before code changes.
- [ ] Add failing protocol-state-machine and bounded-subprocess regressions, then implement the frozen Codex 0.162.1 app-server adapter and disposable-container launch preflight.
- [ ] Integrate retained bidirectional transcript artifacts, protected adapter loading, candidate binding and independent orchestrator replay without schema, registry, policy or gate relaxation.
- [ ] Add explicit role and assigned-check prompt instructions; preserve exact frozen architect contract and exact assessment assignment validation.
- [ ] Run focused and full autonomy suites, review the exact committed SHA independently, and promote only the reviewed implementation for disposable runtime trials.
- [ ] After independent promotion, run bounded real success, unavailable-profile and interrupted-provider trials solely in the authorized disposable container; preserve all old and new evidence and report configured settings separately from unobserved upstream served tier.

## Representative regression contract

These are tests against the proposed public reducer; the fixture helper constructs the full source-shaped ordered exchange specified above, including actual raw JSON lines and the runner-owned expected header. The helper is local to `test_app_server_adapter.py` and performs no provider calls.

```python
class ProtocolTests(unittest.TestCase):
    def test_requires_resolved_effort(self):
        records, expected = successful_exchange()
        startup = next(r for r in records
                       if r["direction"] == "server"
                       and json.loads(r["raw"]).get("id") == 3)
        frame = json.loads(startup["raw"])
        frame["result"].pop("reasoningEffort")
        startup["raw"] = json.dumps(frame) + "\n"
        with self.assertRaises(ProtocolError):
            replay_protocol(records, expected=expected)

    def test_matching_configured_profile_and_response(self):
        records, expected = successful_exchange()
        result = replay_protocol(records, expected=expected)
        self.assertEqual(result["profile"], {
            "model": "gpt-6.1-sol", "reasoning_effort": "medium",
            "service_tier": "fast"})
        self.assertTrue(result["completed"])
        self.assertEqual(json.loads(result["response_text"])["assessments"], [])
```

The fixture uses initialize ID 1, one-page model/list ID 2 and thread/start ID 3; multi-page fixtures allocate subsequent IDs monotonically. Implement the full negative matrix below rather than limiting coverage to these examples.

## Task 1: Protocol reducer, launch boundary and bounded adapter

Files: create `scripts/autonomy/app_server_adapter.py`, `scripts/autonomy/test_app_server_adapter.py`.

- [ ] Write table-driven fake transcript tests for the exact handshake above before implementation. A successful fixture must contain actual source-shaped catalog/thread/turn/item responses, explicit medium/priority support and a completed matching turn. Assert replay returns exactly the requested profile and response bytes.
- [ ] Add failures for missing/null profile fields, wrong model/provider/effort/tier, displayName-only match, absent/unsupported serviceTiers, duplicate matching model, unexhausted/repeated/over-limit pagination, unavailable profile, duplicate JSON keys/IDs, foreign thread/turn, reroute, forbidden request/update, ambiguous final messages, non-JSON/v2 output, missing completion, failed/interrupted turn and nonzero server exit. Test a settings-looking model message never counts as metadata.
- [ ] Add a deterministic fake server executable driven by stdio state, not canned one-shot output. Assert exact call order, writes-before-dependent-reads, buffered interleaving, no turn/start on catalog/profile failure and no second inference. Use no installed Codex or provider in unit tests.
- [ ] Add boundary tests rejecting ordinary host, env-marker-only claims, root UID, symlink/writable/missing proof, namespace/root/CODEX_HOME mismatch. Inject filesystem/process probes into unit tests; do not require real root/container privileges. Only the explicit fake-process test entrypoint can inject probes, not production CLI options or provider input.
- [ ] Test stdout/stderr floods, oversized/partial frames, blocked stdin, deadline before IDs, deadline after IDs with actual interrupt acknowledgement, caller cancellation, descendant pipe retention, process-group TERM/KILL/reap and valid-completion/nonzero-exit. Assert finite time and retained truncation status.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest scripts.autonomy.test_app_server_adapter -v`, observe intended failures, implement minimal state machine/bounded transport, rerun to pass, and commit only this task's two files after actual verification. No live provider.

## Task 2: Runner evidence and independent replay

Files: modify `scripts/autonomy/runner.py`, `scripts/autonomy/test_runner.py`, `scripts/autonomy/orchestrator.py`, `scripts/autonomy/test_orchestrator.py`.

- [ ] Add failing runner tests for exact app-server argv/version, preflight before spawn, safe environment/guards/isolated cwd, preserved local commits, candidate verification before inference, adapter byte mismatch at trusted base, protected adapter modification, and failed invocation cleanup. Retain current schema/path/trusted-loader tests.
- [ ] Add failing orchestrator tests that run the genuine fake server via runner and replay retained artifacts. Independently alter client frame, server frame, sequence, catalog support, startup field, prompt/schema hash, thread/turn/candidate, response and observed_execution. Every alteration blocks; require response bytes equal the selected completed item and raw stdout equal captured server frames. A fabricated session_config or claimed passed manifest never repairs missing evidence.
- [ ] Integrate adapter interfaces, snapshot/protect adapter, retain `<label>:protocol` with existing artifact kind, and expand strict artifact/output identity checks in producer and replay. Do not change schema enums, registry, policy, evaluator or fixed gate assignments. Keep legacy failures readable but unconfirmed.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest scripts.autonomy.test_runner scripts.autonomy.test_orchestrator -v`, first confirm new regressions fail, then implement the minimum integration and rerun to pass. Commit only these four files after verification.

## Task 3: Explicit assessment assignment and user-facing contract

Files: modify runner/test_runner (prompt construction), `.cursor/agents/autodata-architect.md`, `docs/agents/runner-interface.md`.

- [ ] Add failing prompt tests asserting explicit role, gate and exact assigned check IDs; architecture/planning/implementation receive `assessments: []`. For gates, assessments contain exactly assigned IDs once; never invent IDs. Explain that full contract checks describe downstream verification and are not assignments. Existing findings carry blockers. Supply only existing evidence IDs.
- [ ] Add actual response validation regressions for the observed six architecture-* assessments, duplicate/missing gate checks, and valid architect assessments=[] with exact frozen task_contract. Do not permit the architect to rewrite the contract or reassign checks.
- [ ] Add these literal assignment rules to runner prompt and architect instructions. Document bounded app-server invocation, configured-versus-served distinction, container-only launch, evidence/replay IDs, approvals, cancellation, version and negative behavior in runner-interface.md. Do not add runtime internals to product flows.
- [ ] Run the focused adapter/runner/orchestrator tests, inspect exact prompt output without credentials, and commit these scoped changes after tests pass.

## Task 4: Verification, promotion and bounded real trials

- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s scripts/autonomy -p 'test_*.py' -v` and `git diff --check`. Record actual counts, exact final SHA, changed files and clean status. No synthetic test result is provider certification.
- [ ] Independent reviewer inspects the exact SHA, source-shaped protocol fixtures, process boundaries and replay tampering tests. Coordinator separately verifies that same SHA and promotes it into a fresh disposable fixture clone. Do not push/integrate the fixture or grant release readiness.
- [ ] Only after promotion and supervisor boundary proof, coordinator runs three distinct real trials with new clones/evidence directories: success (architect assessments=[]; downstream exact eight-gate chain if available), unavailable exact profile (discovery fails before turn/start, zero inference/no fallback), and interrupted provider (force cancellation after thread/turn ID, retained interrupted result, no success). For the unavailable-profile trial, retain a genuine official catalog/startup rejection of the unchanged exact requested profile. Do not edit/relay-filter a catalog response, substitute a different model, disable the requested profile and call it equivalent, or count a synthetic negative as real. If the authorized provider currently makes that exact profile available and no genuine unavailable condition can be reproduced within the one bounded attempt, record this trial not_executed/blocked; the deterministic fake-server negative still remains useful test evidence only. Bound each provider to 120 seconds, each outer trial to 400 seconds; one attempt per case, no automatic retries. A skipped/unavailable trial is explicitly not_executed/blocked, never counted as pass.
- [ ] Check the retained transcript/profile against actual official protocol, exact candidate verification, independent replay and unchanged gate rules. Preserve all old evidence. Report configured model/effort/Fast support and matching completion; state upstream served tier unobserved. A real failure opens a separate remediation/checkpoint rather than broadening this plan.

## Proposed pre-implementation record

The following record is intentionally blocked. The coordinator owns synchronization and any fresh pinned base; no implementation agent may flip status locally to authorize itself.

```json
{
  "goal": "Retain and replay truthful resolved local-cli execution settings through the bounded Codex 0.162.1 app-server protocol, with exact gpt-6.1-sol / medium / Fast and no fallback.",
  "plan_ref": "docs/superpowers/plans/2026-11-03-app-server-runtime-contract.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/runner-interface.md",
    "docs/verification/2026-11-03-agent-evidence-hardening.md"
  ],
  "todo": [
    "Synchronize Issue #186, Project #8, canonical runner documentation, this plan and this concrete todo; commit a fresh synchronized task record and pass validate_record at the exact implementation base before code changes.",
    "Add failing protocol-state-machine and bounded-subprocess regressions, then implement the frozen Codex 0.162.1 app-server adapter and disposable-container launch preflight.",
    "Integrate retained bidirectional transcript artifacts, protected adapter loading, candidate binding and independent orchestrator replay without schema, registry, policy or gate relaxation.",
    "Add explicit role and assigned-check prompt instructions; preserve exact frozen architect contract and exact assessment assignment validation.",
    "Run focused and full autonomy suites, review the exact committed SHA independently, and promote only the reviewed implementation for disposable runtime trials.",
    "After independent promotion, run bounded real success, unavailable-profile and interrupted-provider trials solely in the authorized disposable container; preserve all old and new evidence and report configured settings separately from unobserved upstream served tier."
  ],
  "status": "blocked",
  "updated_at": "2026-11-03T10:29:29.128151+00:00"
}
```

## Handoff and remaining prerequisites

Architecture is fixed by this plan: single stdio adapter, configured-setting certification, catalog priority support, no profile overrides, one completed bound turn, strict replay, container-only execution and no host approvals. No provider availability or upstream-served-tier evidence is promised.

Remaining external prerequisites are coordinator GitHub/canonical-document synchronization and committed-base preflight, independent exact-SHA promotion after implementation, and a supervisor-provided non-root disposable boundary attestation matching the contract above. If the existing fixture cannot supply that boundary, real trials remain blocked and any launcher code requires separate scope approval. This checkpoint does not modify that launcher or run any provider.
