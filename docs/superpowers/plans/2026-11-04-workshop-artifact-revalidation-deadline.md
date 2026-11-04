# Workshop artifact revalidation deadline correction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after this synchronized checkpoint is committed, full-SHA preflight passes, independent exact-checkpoint review approves and the coordinator dispatches implementation. This docs-only checkpoint authorizes no implementation or live action.

**Goal:** Bound verified-worker revalidation by the original operation deadline and cancellation ownership, and prohibit child spawn after expiry or cancellation while preserving dormant publisher execution.

**Architecture:** Own a single cancellation/deadline inspection scope before any selected-worker revalidation await. Thread its checks through every loader and file/tree operation, bound waiting and cleanup using the existing operation budget, and perform the final non-awaiting deadline/abort check immediately before the fixed child spawn. Keep the existing owned-process/pipe boundary and all activation denials.

**Tech Stack:** Reviewed Node22.23.4 linux/x64; standard filesystem, AbortController and monotonic timers; existing Node real-process contract tests and Python workflow/host tests. No dependency changes.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-artifact-boundary-corrections.md`; `docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md`; canonical `docs/agents/pre-implementation-gate.md`. Review and probe paths are retained below.

Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 .

## Status and exact source

Status: **synchronized planning / implementation blocked pending committed pinned preflight, independent exact-checkpoint review and coordinator dispatch**. Source is pushed candidate `bf7bb67bfbdca3b8186bb56d603cf4dee7e4116b` on `codex/workshop-publisher-artifact`. Independent review `/tmp/autodata-artifact-bf7bb67-review.md` confirms the original installed-tree, process-cancellation/output and FIFO findings are closed, with92 Node and143 Python tests passing. Approval remains withheld for one P2: ownedUpload awaits loadOfficialToolkit outside deadline/cancel ownership and starts its process timer only after spawn.

The retained synthetic verified-descriptor probe `/tmp/autodata-artifact-bf7bb67-deadline-probe.mjs` and JSON `/tmp/autodata-artifact-bf7bb67-deadline-probe.json` advance the injected monotonic clock during the second mount/tree inspection. Result: `{"mountReads":2,"spawned":1,"spawnedAfterDeadline":true,"error":"cleanup_failed"}`. A late cleanup error does not undo starting an upload-capable child after expiry. The probe used a /tmp synthetic package tree and mocked kernel mount text, never actual immutable-toolchain or owner activation evidence; its harmless child performed no SDK/network operation.

## Exact scope and inherited constraints

The implementation allowlist is exactly:

- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/test_publisher_artifact.mjs`

This checkpoint itself changes only this plan, its new record/task and an additive `docs/operations/workshop-gcp.md` note. No Python adapter/test, package/lock, workflow, production job, public CLI behavior, owner policy, activation file or application/runtime file may change. No package install/fetch, actual SDK import/upload, credential acquisition, cloud/registry/provider/host operation, workflow dispatch/activation, deployment or live publication is authorized. Local harmless fixtures and saved review evidence are allowed.

Preserve the exact reviewed artifact6.3.1 lock SHA256 `3e697f78715f0ef89dfd4f60c1ed9902e21dbfd3fadb2cbd7c39776192611bf5`, Node22.23.4 executable SHA256 `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`, complete independently selected installed-tree/read-only mount verification, fixed executable/helper/argv/env/private pipes, real process-group termination/reap/pipe closure, strict result/outer-vs-inner archive validation, no-follow/nonblocking FIFO-safe preflight and fixed redacted errors. All context/receipt schemas and run/attempt/source identity remain unchanged.

Default and explicit --internal-upload-worker CLI both remain unconditional fixed exit3 before stdin, ambient runtime credentials or SDK import. No authenticated fixed owner trust source/signature format, real installed manifest, runtime authenticator, REST readback transport or activation evidence is supplied. Seven moderate advisories and buffers licensing remain activation blockers. This correction does not turn an offline process contract into authenticated publication authority.

## Decision-complete correction

1. Before selected-worker revalidation begins, establish operation-owned cancellation including the caller AbortSignal and a temporary nonthrowing SIGTERM handler. Signal handling records cancellation/aborts the inspection scope; it never throws across child assignment. Keep this ownership through the final spawn check and until the existing child cleanup owns the same signal, with no await gap or unhandled handoff. Restore/remove only handlers owned by this operation in finally; retain existing child TERM/KILL/reap behavior.
2. Revalidation uses the existing absolute operation deadline and monotonic remaining() closure, maximum300s for the entire operation with its existing30s cleanup reserve. Give this inspection phase at most30s within that budget, selected once on phase entry; neither file/chunk checks nor loader calls reset it. Include a real monotonic wall-clock cap and bounded polling/abort wakeup while filesystem awaits are pending, rather than checking only after a late child timer starts.
3. Pass a private in-memory inspection scope through loadOfficialToolkit, verifyInstalledTree and fixedRead. It carries only cancellation/deadline/owned inspection state, never activation authority. Check before and after every filesystem await, directory traversal, bounded read/hash chunk, immutable-mount inspection and final descriptor registration. A check rejects fixed operation_timed_out or operation_cancelled, preserved through loader error redaction. Keep current two-argument public loader callers compatible by creating their own bounded30s local inspection scope; no serialized caller timeout/path/command/approval field is introduced.
4. Each asynchronous inspection continuation checks that scope before starting another operation or registering a descriptor. An operation returning a file handle after cancellation enters a finally block and closes it without reading further. Track outstanding inspection work; after timeout/abort, stop all follow-up verification and await handle closure/inspection settlement only within the original cleanup reserve. If closure/settlement cannot be proved before reserve expiry, return cleanup_failed with no child/result/readback. Promise.race rejecting the waiter is not proof that underlying filesystem work stopped. A stuck kernel filesystem request remains a supervisor limitation; the helper must never convert it into permission to spawn or import, even if it completes after the public failure.
5. Immediately before the actual fixed spawn, yield once to the event loop under the same scope so queued abort/SIGTERM is observed, then check the original remaining budget and combined cancellation state with no subsequent await before spawn. Repeat after any asynchronous loader/inspection/ready step. No expired or cancelled selected descriptor may trigger the low-level spawn callback, SDK callback, readback or receipt. If cancellation arrives during synchronous OS spawn/assignment, the existing owned-process cleanup remains mandatory; this amendment does not claim atomic cancellation of the kernel spawn syscall.
6. Preserve existing cleanup_failed precedence and the original reserve. No upload result is accepted after expiry or cancellation, no artifact binding is reused, and no new runtime/owner proof is invented. Continue to reject all runtime execution paths without the separately authenticated owner trust source.

## Concrete todo

- [ ] Synchronize the single revalidation finding, exact two-file scope and retained red probe across Issue186, Project8 and canonical docs; preserve the current PG adoption index/detail, commit and pass full-SHA pinned preflight for independent review before implementation.
- [ ] Add verified-descriptor-path deadline, abort and pending-inspection regressions that prove zero spawn and zero readback after the cutoff, using only a synthetic local toolchain and harmless OS child boundary.
- [ ] Thread one original-budget inspection scope through loader and file/tree awaits, own cancellation before revalidation, drain or fail cleanup for outstanding inspection work, and recheck deadline and cancellation immediately before the fixed spawn without resetting any budget.
- [ ] Run all existing Node and Python cloud/host/workflow suites plus syntax, exact-scope and pinned-gate checks; push the bounded candidate for independent exact-SHA review while retaining every owner, immutable-toolchain, advisory, licensing and activation blocker.

## Task1: synchronize docs only and obtain the new gate

Files: `docs/superpowers/plans/2026-11-04-workshop-artifact-revalidation-deadline.md`, `docs/agents/records/2026-11-04-workshop-artifact-revalidation-deadline.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-revalidation-deadline.json`, additive canonical operations note.

- [ ] After coordinator slot assignment, snapshot CURRENT Project8 index and full PG corrected-receipts adoption detail comment6621879747; preserve each verbatim with SHA256 in the new Issue186 comment. Include any closure index posted before the final comparison/readback. Coordinator confirms no closure index currently exists; its later audit/index may follow slot release.
- [ ] Read back the new Issue comment and Project text exactly, record hashes/URLs, commit/push docs and run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-artifact-revalidation-deadline.json --base-sha <full committed checkpoint SHA>`.
- [ ] Stop for independent exact-checkpoint review and coordinator dispatch. Both implementation files must remain byte-identical to bf7bb67 until then. Release the tracking slot after synchronization.

## Task2: verified-descriptor red regressions and bounded correction

Modify/test only the two allowed JavaScript files. Preserve the existing tests and use the actual exported loader/opaque descriptor, not an invented revalidate callback.

- [ ] Copy the exact helper into a private synthetic /tmp toolchain fixture as the independent probe does; write fixed package/lock/manifest bytes and exact policy hashes, readonly file/dir modes and a mocked read-only kernel-mount record. Obtain a genuine opaque descriptor through loadOfficialToolkit. The fixture has no token/owner authenticity and must never be called actual immutable-toolchain evidence; import sentinel remains unused.
- [ ] Add a regression advancing the injected monotonic clock during the SECOND mount/tree inspection past the operation deadline while retaining cleanup time. Assert the public fixed timeout, zero OS spawn, zero readback and completed bounded cleanup. Add a separate controller.abort during that same verified-descriptor await, requiring fixed cancellation and the same zero counts.
- [ ] Add a pending filesystem-await case: retain/release its local read promise after the clock/abort transition, prove the deadline/abort wakes bounded inspection, prove late continuations close any acquired handles and never proceed to another verification/import/descriptor/spawn, and use an external harmless-child watchdog as a test fail-safe. Include cleanup-reserve exhaustion returning cleanup_failed rather than falsely asserting settlement.
- [ ] Add a final-ready race that advances clock/aborts at the last revalidation/event-loop handoff; require zero spawn/readback. Keep synthetic injected OS spawn count explicit and ensure any unavoidable pre-revalidation runtime-auth fixture is accounted separately; no callback may newly start after the cutoff.

Illustrative behavior assertions, evaluated on the verified-descriptor path:

```js
await assert.rejects(helper.uploadRelease(request, dependencies), /operation_timed_out/);
assert.equal(spawned, 0);
assert.equal(readbacks, 0);
assert.equal(lateImportSentinelExists, false);
assert.equal(cleanupFinished, true);
```

- [ ] Run the new focused tests against bf7bb67 before implementation, retain their failure logs and the original independent JSON. Red must show an actual late spawn or missing bounded inspection, rather than fail on a missing unrelated owner input. Cancellation and deadline red cases must fail for the targeted verified path.
- [ ] Implement the shared private inspection scope, guarded file/tree awaits, tracked outstanding work and final immediate pre-spawn check specified above. Keep all existing owner/readonly/default-CLI denials. Run focused tests to green, including late completion after a failed public operation; commit/push only a coherent validated milestone.

## Task3: full verification and independent candidate handoff

- [ ] Verify the pinned Node executable hash; run `/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs` with all prior92 tests plus new regressions. Run Node --check on both files.
- [ ] From infra/deploy/gce run `python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q`; all unchanged143 tests, production job invariants and staging blockers remain required.
- [ ] Run git diff --check, exact two-file implementation allowlist check against this full checkpoint SHA and pinned preflight at that SHA. Keep package-lock, workflows, Python files and all production hashes unchanged.
- [ ] Commit/push the exact candidate and report red/green logs, helper hash, passed checks and remaining owner/activation/SDK/advisory/license limitations for independent review. Stop edits pending that review; do not claim live publisher approval.
