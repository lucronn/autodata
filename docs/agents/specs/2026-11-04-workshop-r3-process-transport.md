# R3 owned subprocess transport successor specification

**Goal:** Add a real Linux subprocess primitive that bounds retained output, accounts a nonrenewable shared budget and cancels/reaps only its owned local observation child/process group, providing the first enforcing building block for a later real R3 preparation adapter.

Canonical implementation plan: `docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md`. The decision-complete plan, including exact two-new-file ownership and adversarial real-child verification tasks, is normative alongside this mechanical contract. Planning parent is `e414e8537c8a6f0bc99747f6db09782b7743a949`; the future builder base is the externally sealed resulting checkpoint SHA. No production caller, CLI, host collector or existing fake-core file is in scope.

Allowed implementation paths, each new regular mode100644:

- `scripts/r3_preparation/process_transport.py`.
- `scripts/r3_preparation/test_process_transport.py`.

## Global limits and production meaning

Copy from the R3 preparation design: per-command stdout+stderr16MiB; shared attempt capture128MiB; ordinary deadline10s; source-related deadline30s; outer attempt30min; TERM grace2s followed by KILL grace2s. Read chunks are at most64KiB. Limits are nonrenewable; smaller remaining shared/outer allowance wins. No parsing, decoding, serialization, output files or exception text propagation occurs in this primitive.

A run owns only the process it spawned and the new process group/session it created. It never accepts caller-supplied PID/PGID, calls killall/pkill, touches Docker, cleans resources, signals the parent group, or cleans a prior attempt. Keep the leader unreaped until the final group signalling decision; this preserves its PID/PGID against reuse during that decision. After all signalling, reap only the direct child. Signal errors must be classified by fixed code; never serialize their text.

**Honest limits:** A POSIX process group is not a security sandbox. A malicious child can create a new session or pass descriptors to an external process. Python cannot guarantee that an uninterruptible kernel task is killed or reaped by a deadline; process creation itself can also block in the OS. This increment must return/record `cleanup_unconfirmed` when its bounded observation ends without proven direct-child reap/pipe closure. It must never report complete based on sending SIGKILL. A production collector additionally needs independently admitted executable/source provenance, trusted nonescaping command behavior or owner-controlled stronger containment, and an external supervisor/watchdog capable of detecting controller loss/startup stalls. None is supplied here. This primitive cannot satisfy the complete real-adapter obligation by itself.

The module's bounded loop starts before spawn for accounting, but no test or implementation claim may describe Popen, blocked kernel I/O or interpreter termination as absolutely bounded. No retries, fallback executable, daemon discovery, file collector or privilege escalation repairs an unsupported condition.

## Public contract

Use immutable exact dataclasses and exact-type validation; reject booleans as integers, unknown variants, NULs, empty arguments/paths, relative executable/cwd, nonfinite deadlines and mutated/missing required fields. Validation failure launches zero children. Constant `MiB=1024*1024`.

- `CaptureBudget(outer_deadline_ns: int, max_bytes: int = 128*MiB)` is the one mutable session ledger, with monotonically decreasing `remaining_bytes`, one stop latch, a lock, and a single-active-run lease. Reject max_bytes outside1..128MiB and require outer_deadline_ns strictly after construction monotonic time and at most30min away. The absolute outer deadline is stored once and cannot be replaced. No reset/copy/replenish method. Rejected concurrent admission has no side effects on the active child; it returns fixed `busy`.
- `RunRequest(command_id: str, executable: str, argv: tuple[str,...], cwd: str, env: tuple[tuple[str,str],...], kind: str)` contains a closed command label from the caller's future independently reviewed inventory, exact absolute executable/cwd, argv with argv[0]==executable, unique explicit environment pairs, and kind `ordinary` or `source`. Primitive validation limits command_id to ASCII `[a-z][a-z0-9_]{0,63}`, argv<=128 items/64KiB UTF8 total, env<=64 pairs/64KiB UTF8 total; names follow `[A-Za-z_][A-Za-z0-9_]*`. Input-derived labels are never used as diagnostics. No env inheritance or PATH lookup. This syntax admission does not approve a command or authenticate a path; caller authority/provenance remains mandatory before production use.
- `RunResult(status: str, returncode: int|None, stdout: bytes, stderr: bytes, captured_bytes: int, cleanup: str, elapsed_ns: int, primary_fault: str|None)` is immutable. status is exactly one of `completed`, `invalid_request`, `busy`, `cancelled`, `deadline`, `output_limit`, `spawn_failed`, `capture_failed`, `cleanup_unconfirmed`, `unsupported_platform`, `budget_stopped`. cleanup is exactly `not_started`, `reaped`, or `unconfirmed`. primary_fault is null or exactly one of cancelled/deadline/output_limit/capture_failed/spawn_failed; it preserves the first observed failure even when status becomes cleanup_unconfirmed. No PID/path/argv/env/arbitrary error/stdout/stderr text enters status. stdout/stderr are opaque bounded in-memory bytes, not safe persistent evidence. No JSON serializer or report is delivered.
- `run(request: RunRequest, budget: CaptureBudget, cancel: threading.Event) -> RunResult` uses only the real monotonic clock. Cancellation is observable at most50ms after the loop next runs, without claiming OS scheduling guarantees. The supplied event is read-only to the runner. Before spawn acquire the ledger lease, validate request/platform/budget/cancel/deadline; no later successful result may clear a terminal ledger latch. Ordinary nonzero exits return completed with that exact returncode; this means process lifecycle completion only, never acceptance of command output.

Implementation may use private helpers and a private injected backend solely for exhaustive syscall-failure tests, but public callers cannot select fake time, arbitrary limit profiles, alternate signals, shell, preexec_fn or unknown inherited descriptors. No production convenience wrapper is in scope. The test process can directly call private helpers for boundary/failure tests; those are explicitly synthetic assertions.

## Execution algorithm and precedence

1. Validate Linux/POSIX facilities, waitid/P_PID/WNOWAIT availability, ordinary SIGCHLD disposition (reject SIG_IGN and custom handlers), and exact input types before any spawn. The embedding caller must own direct-child reap and must not run a competing waitpid(-1) reaper; unsupported ownership blocks production admission. Admit one ledger lease. Check stop/cancel/outer deadline; select min(start+10s or30s, outer deadline). Start from a minimal explicitly provided env dict; subprocess uses shell=False, stdin=DEVNULL, stdout/stderr=PIPE, close_fds=True, start_new_session=True, no pass_fds, no preexec_fn. No global signal handlers, environment mutation, working-directory mutation or import I/O.
2. Spawn only the supplied absolute executable. Record the owned leader identity privately. Set both pipes nonblocking and register with selectors. Observe leader exit with os.waitid(os.P_PID, pid, os.WEXITED|os.WNOHANG|os.WNOWAIT); do not use Popen.poll(), waitpid without WNOWAIT, or any method that reaps the leader before the final signalling decision. Reap with one bounded owned wait only when no further group signal can occur. Incrementally read at most min(64KiB, command/shared remaining+1). Charge retained bytes before append. A one-byte sentinel beyond remaining capacity proves overflow but is discarded; retained bytes never exceed either cap. Never buffer unrestricted communicate()/read()/capture_output=True or decode child text. Readiness/EOF drain must be fair across both streams; do not drain one indefinitely.
3. Check cancellation/deadlines before each read and after selector wake. Poll no longer than50ms or the remaining deadline. Once breach/error/cancel occurs latch failure and stop accepting bytes. Close capture descriptors without a later unbounded drain. Discarding excess bytes is never a success-compatible truncation.
4. If leader termination plus EOF on both streams occurs before any fault, reap the direct child and return completed. This is deliberately a direct-child/pipe lifecycle result: absence of pipe holders is not proof that every descendant has exited. Production admission therefore needs the separate nonescaping/containment contract. If pipes remain open after leader exit, continue bounded capture until EOF, cancellation or deadline; a child nonzero status alone does not cause a shared latch. When termination is required, keep the leader unreaped until the final group-signalling decision. Do not infer group emptiness from killpg(pgid,0), since the unreaped leader itself can keep that group observable.
5. Termination uses owned PGID only: SIGTERM once, observe with WNOWAIT within2s; then SIGKILL once if needed and observe within2s. If the leader exited but descendants still hold pipes, SIGKILL must still target the preserved owned group before leader reap; leader exit alone cannot skip that escalation. One nonrenewable allowance covers every cleanup step. Do not start a fresh allowance per exception/pipe/process. Bound wait/reap calls with remaining time and never use an unbounded wait in finally. A process can still be unconfirmed at expiration; preserve that outcome and stop the budget. A confirmed reap does not attest escaped descendants or complete host cleanup.
6. Precedence: invalid request/platform before launch; busy before touching active run; after launch first observed primary fault latches (`cancelled`, `deadline`, `output_limit`, `capture_failed`); cleanup unconfirmed overrides result status but never erases primary_fault. Successful exit cannot override a latched fault. Child exit code is retained if known. All descriptors close on every path; only the direct child is reaped. Release the lease in bounded local cleanup without restoring budget.

No production caller integration is included. The future real CommandPort must bind this mechanical contract to exact reviewed argv/env/executable/cwd/descriptor/file provenance, free-space and output policy, and independently decide whether containment/startup limitations are acceptable. It cannot just alias the primitive into the fake collector and call preparation compatible.

## Authority and remaining release path

All public coordination receipts remain trusted:false, runtime_accepted:false, host_observed:false, accepted_case_credit exact integer0, profiles_enabled:false, enabled_tiers:[], runtime_lock:null and run_record:null. All nine authorities remain false: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized. The code dispatch authorizes the two files and synthetic local-child tests only; diagnostic authority fields do not turn true.

This gate does not claim production-adapter readiness. Separate successors must supply: descriptor-anchored cancellable FilePort/output I/O and incremental bounded JSON; actual CommandPort binding and accepted containment/watchdog policy; named owner/reviewer/cancellation identities and exact approved host/tool/plugin/config/env/image/clone/output contracts; separately authorized preparation-only observations; compatibility repair if needed; exact one-attempt execution/review; full retained raw identity/catalog/commerce/paid/browser contracts and profile promotion; authenticated publisher and staging lifecycle/schema/readiness/minimum recovery; real Firebase login, Stripe TEST $20 settled grant/persistence/refund behavior, both licensed banks and source/canonical/media/failure behavior; later production payment/DNS/TLS/recovery/alerts and cars.tk cutover authorization.

A missing owner identity, licensed connector endpoint, Stripe/Firebase project/account/version, accepted release image, GitHub readback, exact checkpoint or compatible kernel supervision remains a blocker for its corresponding later gate. None needs to be guessed or retrieved to implement and test these two files.


## Canonical synchronized planning record

This is the dedicated successor checkpoint for the owned subprocess primitive. The parent fake-only collector spec is immutable historical policy, not execution authorization. The actual resulting checkpoint SHA must be sealed externally; no self-referential SHA is invented here. Independent exact-checkpoint review and explicit dispatch remain required after committed preflight.

```json
{
  "schema_version": 1,
  "goal": "Add a real Linux subprocess primitive that bounds retained output, accounts a nonrenewable shared budget and cancels/reaps only its owned local observation child/process group, providing the first enforcing building block for a later real R3 preparation adapter.",
  "plan_ref": "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
  "spec_ref": "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
  "record_ref": "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
  "task_ref": "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md"
  ],
  "todo": [
    "Freeze the e414e853 parent, real-child-only verification contract, exact two-file scope and false authorities; synchronize dedicated plan/spec/task/record, canonical index and Issue186/Project8; pass committed exact-base standalone/nested preflight and independent checkpoint review before dispatch.",
    "Implement and test exact admission, nonrenewable shared capture accounting and bounded binary stdout/stderr retention using only owned synthetic Python children.",
    "Implement and test monotonic cancellation/deadline handling, identity-safe owned group termination, direct-child reap and conservative cleanup_unconfirmed outcomes without host/tool/provider discovery.",
    "Run the focused real-child suite, memory syntax/static checks and exhaustive two-file/predecessor preservation checks; commit/push coherent validated milestones and obtain independent exact-code-head review and normal CI readback.",
    "Synchronize code-only measured receipts and explicit unresolved production containment/startup/file/owner/host/runtime/product/payment/final180/staging blockers; grant no runtime, promotion, merge, deployment or cutover authority."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-04T19:35:00.908451+00:00",
  "planning_status": "tracking_synchronized_pending_checkpoint_review",
  "planning_base_sha": "e414e8537c8a6f0bc99747f6db09782b7743a949",
  "implementation_base_sha": null,
  "execution_gate_sha": null,
  "scope": "owned_subprocess_transport_primitive_only",
  "allowed_gate_document_paths": [
    "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
    "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
    "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
    "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
    "docs/agents/tasks/2026-11-03-production-release/queue.json"
  ],
  "allowed_implementation_paths": [
    "scripts/r3_preparation/process_transport.py",
    "scripts/r3_preparation/test_process_transport.py"
  ],
  "source_document_sha256": {
    "/home/corp/autodata-evidence/next-release-gate-analysis/PLAN.md": "a80cb38985ed5b42d0f3020bd9903f10ce75371c289c633bac0980df59fdab30"
  },
  "external_plan_review_ref": "/home/corp/autodata-evidence/next-release-gate-review/verdict.json",
  "tracking_sync": {
    "accepted_case_credit": 0,
    "current_comment_count": 177,
    "future_implementation_paths": [
      "scripts/r3_preparation/process_transport.py",
      "scripts/r3_preparation/test_process_transport.py"
    ],
    "goal": "Add a real Linux subprocess primitive that bounds retained output, accounts a nonrenewable shared budget and cancels/reaps only its owned local observation child/process group, providing the first enforcing building block for a later real R3 preparation adapter.",
    "issue_after_sha256": "982000b290b2ebb0cb447620f1a3065a647898be8828f5f82dc2d05b2bf3c17b",
    "issue_before_sha256": "5a651a9cddf2e01ed3ab3b17c984914d44469cf69567877d0c734703baf7997b",
    "issue_body_unchanged": true,
    "issue_comment": "https://github.com/lucronn/autodata/issues/186#issuecomment-6640162652",
    "other_project_fields_unchanged": true,
    "planning_parent_sha": "e414e8537c8a6f0bc99747f6db09782b7743a949",
    "planning_paths": [
      "docs/superpowers/plans/2026-11-04-workshop-r3-process-transport.md",
      "docs/agents/specs/2026-11-04-workshop-r3-process-transport.md",
      "docs/agents/records/2026-11-04-workshop-r3-process-transport.json",
      "docs/agents/tasks/2026-11-03-production-release/workshop-r3-process-transport.json",
      "docs/superpowers/plans/2026-11-04-workshop-integrated-r3-runtime.md",
      "docs/agents/tasks/2026-11-03-production-release/queue.json"
    ],
    "previous_source_archived_verbatim": true,
    "prior_comment_count": 176,
    "prior_comments_preserved": true,
    "project_after_sha256": "bff82971b35007013586fd80d2012b1fd4cb34de6d9a8f485ede169183d2eddf",
    "project_before_sha256": "6c5b27b6a65662fa337c53168c7c0bbc6c255dc0157e1ee60080b47c45d23654",
    "status": "synchronized_live_readback",
    "todo": [
      "Freeze the e414e853 parent, real-child-only verification contract, exact two-file scope and false authorities; synchronize dedicated plan/spec/task/record, canonical index and Issue186/Project8; pass committed exact-base standalone/nested preflight and independent checkpoint review before dispatch.",
      "Implement and test exact admission, nonrenewable shared capture accounting and bounded binary stdout/stderr retention using only owned synthetic Python children.",
      "Implement and test monotonic cancellation/deadline handling, identity-safe owned group termination, direct-child reap and conservative cleanup_unconfirmed outcomes without host/tool/provider discovery.",
      "Run the focused real-child suite, memory syntax/static checks and exhaustive two-file/predecessor preservation checks; commit/push coherent validated milestones and obtain independent exact-code-head review and normal CI readback.",
      "Synchronize code-only measured receipts and explicit unresolved production containment/startup/file/owner/host/runtime/product/payment/final180/staging blockers; grant no runtime, promotion, merge, deployment or cutover authority."
    ],
    "receipt_ref": "/home/corp/autodata-evidence/r3-process-transport-planning-tracking/receipt.json",
    "receipt_sha256": "0318d50bcd8777658834495559b3820a0609a6b5faa508808d151b38754f9c76",
    "writer": "coordinator sole serialized writer"
  },
  "implementation_blockers": [
    "Commit/push the actual six-path checkpoint and externally pin its full SHA; pass standalone/nested canonical preflight at that SHA, independent exact-checkpoint review and explicit two-file dispatch before implementation."
  ],
  "execution_blockers": [
    "Production containment/startup supervision, descriptor-anchored FilePort/output I/O and bounded JSON remain separate.",
    "Named owner/reviewer/cancellation identities, approved host/tool/plugin/config/env/image/clone/output contracts and separately authorized preparation observations remain unresolved.",
    "Real CommandPort binding, compatible kernel supervision, runtime attempt/review, authenticated product/provider/payment/browser evidence, final180, profile promotion, staging, publisher/recovery and production/cars.tk cutover gates remain separate."
  ],
  "trusted": false,
  "runtime_accepted": false,
  "host_observed": false,
  "accepted_case_credit": 0,
  "profiles_enabled": false,
  "enabled_tiers": [],
  "runtime_lock": null,
  "run_record": null,
  "authority": false,
  "fixture_verified": false,
  "product_candidate_verified": false,
  "staging_verified": false,
  "deployment_authorized": false,
  "cutover_verified": false,
  "implementation_authorized": false,
  "runtime_execution_authorized": false,
  "profile_promotion_authorized": false,
  "merge_authorized": false,
  "authorities": {
    "fixture_verified": false,
    "product_candidate_verified": false,
    "staging_verified": false,
    "deployment_authorized": false,
    "cutover_verified": false,
    "implementation_authorized": false,
    "runtime_execution_authorized": false,
    "profile_promotion_authorized": false,
    "merge_authorized": false
  },
  "release_state": "unverified"
}
```
