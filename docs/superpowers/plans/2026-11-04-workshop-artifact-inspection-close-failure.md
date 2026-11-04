# Workshop artifact inspection close-failure correction plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after tracking synchronization, committed full-SHA preflight, independent exact-checkpoint approval and coordinator dispatch. This docs-only checkpoint authorizes no implementation before those conditions.

**Goal:** Preserve cleanup_failed when an owned inspection handle fails to close, and never treat rejected inspection settlement as proof of successful cleanup.

**Architecture:** Track inspection handles separately from asynchronous task settlement. A rejected close leaves closure unproved and records a sticky cleanup failure. Preserve that failure through inspection draining, loader redaction and operation cleanup, with precedence over cancellation, timeout and validation errors. Keep all existing deadlines and process isolation.

**Tech Stack:** Existing reviewed Node22.23.4 linux/x64, standard filesystem and private inspection scope; existing Node real-FD/process fixtures and unchanged Python contract suites. No dependencies or policy changes.

Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Canonical gate: `docs/agents/pre-implementation-gate.md`.

## Status and evidence

Status: **synchronized docs-only planning; implementation blocked pending committed full-SHA preflight, independent exact-checkpoint approval and coordinator dispatch**. Source candidate `220d9c3099e190c3a3dc60fde11c43b7300bda7c` on `codex/workshop-publisher-artifact`. PG Task1B explicitly released tracking at receipt c16f40a2730e7bc8a5fb3afd3ac2d10abf551637. Exact Issue/Project readbacks and preserved PG text hashes are recorded in the matching record. Tracking synchronization does not replace committed pinned preflight, independent review or dispatch.

Independent review `/tmp/autodata-artifact-220d9c3-review.md` closes the previous late-spawn defect and retains the original installed-tree, process/output and FIFO corrections. Its103 Node and143 Python checks passed. Approval remains withheld for one P2: `fixedRead` awaits `h.close()` but records no failed closure, and `inspectionScope.run` counts either resolution or rejection of the inspection task as successful draining. Cancellation can therefore win over a failed close while an actual descriptor remains open. Ordinary loader close errors can also become `missing_dependency`.

Retained probe: `/tmp/autodata-artifact-220d9c3-close-failure-probe.mjs`; result `/tmp/autodata-artifact-220d9c3-close-failure-probe.json`. It wraps a real late-opened FileHandle, makes close reject without closing, and uses independent later fixture cleanup. Observed: `operation_cancelled`, `fdOpenAtReturn:true`, zero spawn/readback, and `closedHandleAtReturn:false`. It uses a synthetic toolchain/mount fixture, with no SDK import, owner authentication or network operation.

## Exact scope and inherited constraints

Implementation allowlist is exactly:

- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/test_publisher_artifact.mjs`

This docs checkpoint changes only this plan, its matching record/task and an additive `docs/operations/workshop-gcp.md` note. Do not edit Python, package/lock, workflow, production jobs, owner policy or CLI activation. Retain complete owner-selected installed-tree/readonly binding; fixed verified executable/helper/argv/env; actual process-group TERM/KILL/reap/pipe closure; output isolation; original absolute deadline, cancellation/SIGTERM ownership and final no-await pre-spawn guard; strict request/result/readback/identity and FIFO-safe archive reads.

Normal CLI and explicit `--internal-upload-worker` remain unconditional fixed exit3 before stdin, ambient credential reads or SDK import. Missing independently authenticated fixed owner trust, immutable installed manifest, runtime authenticator and real readback remain blockers. Seven moderate advisories and unresolved buffers license remain blockers. No install/fetch, SDK import/upload, token, cloud/registry/provider/host/Docker action, workflow execution/activation, signing, publication or deployment is authorized.

## Decision-complete correction

1. In the existing private inspection scope, retain ownership of each successfully acquired `fixedRead` FileHandle before the first post-open check or await. Keep ownership until its close resolves successfully. A handle delivered by an open that completes after cancellation is still owned and must enter the same finally-close path. This state carries no runtime authority and must not be caller-serializable.
2. Wrap `h.close()` so every rejection marks sticky `cleanup_failed` before throwing only that fixed redacted error. Mark failure even when cancellation, timeout or another validation error already exists, and even when task settlement has already been observed. Do not infer closure from task rejection, `.fd` sentinel, an unrelated cleanup callback or a later successful retry. A close that actually closes but rejects is still unproved at this contract boundary. No retry or extra cleanup budget is introduced.
3. Distinguish asynchronous inspection settlement from closure proof. During error draining, wait for pending inspection completion only within the existing shared cleanup reserve; require all acquired handles to have successfully closed and no recorded close failure before classifying inspection as drained. Recheck sticky cleanup status after the task settles and immediately before selecting the public error, including the already-settled branch. Rejected task settlement alone is never sufficient. Unsettled work, owned unclosed handles or recorded close failure yields `cleanup_failed`; otherwise retain the original cancellation/timeout/validation reason.
4. Preserve `cleanup_failed` through `loadOfficialToolkit` redaction and the exported pure verifier/upload path. A normal inspection failure plus a close rejection must return `cleanup_failed`, not `missing_dependency`; cancellation/timeout plus close rejection must also return `cleanup_failed`. The shared `fixedRead` finally must use the same fixed error for any close rejection even on its archive/unscoped caller, without changing archive selection or parsing. Later operation cleanup must not downgrade an already recorded cleanup failure. No result, spawn, SDK/readback or descriptor registration may follow failure.
5. Keep original phase/global/cleanup deadlines and their ownership. Failure reporting cannot prove that an OS descriptor closed after close rejects; report the unproved cleanup explicitly and return bounded failure. A deliberately failing close may leave a descriptor open at failure: tests must observe that fact and independently close it afterward; the implementation must never label that state successfully drained. Do not claim cancellation alone closed the underlying resource.

## Concrete todo

- [ ] Synchronize the single close-failure finding and exact two-file scope across Issue186, Project8 and canonical docs after the coordinator releases the tracking slot; preserve the then-CURRENT PG index/details verbatim with hashes, commit and pass full-SHA pinned preflight for independent review before implementation.
- [ ] Add actual-file-descriptor regressions for cancelled late-open and ordinary inspection close failure, plus timeout and successful-close controls; prove cleanup_failed precedence, zero spawn/readback and bounded independent fixture cleanup.
- [ ] Retain explicit inspection handle ownership and sticky closure failure, distinguish task settlement from proved closure, and propagate fixed cleanup_failed through loader and operation cleanup without resetting budgets or weakening earlier guards.
- [ ] Run the full existing 103 Node and 143 Python tests plus new regressions, syntax, exact-scope and pinned-gate checks; push the candidate for independent exact-SHA review with all owner, immutable-toolchain, advisory, license and activation blockers retained.

## Task1: synchronize this docs-only correction gate

- [ ] Keep this draft local/uncommitted while PG owns the tracking slot. Do not modify implementation or GitHub.
- [ ] After coordinator slot release, snapshot the then-CURRENT full Project8 index and relevant PG detail/exact-pin/closure comments. Preserve full text verbatim and hashes in the new Issue186 correction comment; use comparison/readback before replacing the index so concurrent updates cannot be lost. Do not assume the cached PG closure or Task1B state is current.
- [ ] Read back exact new Issue comment and Project index; record URLs/hashes/timestamp, mark record synchronized, commit/push the four docs files, then run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure.json --base-sha <full checkpoint SHA>`.
- [ ] Obtain independent exact-gate approval and coordinator implementation dispatch. Both allowed implementation files remain byte-identical to 220d9c3099e190c3a3dc60fde11c43b7300bda7c until then. Release the tracking slot after synchronization.

## Task2: red actual-FD regressions and bounded correction

Use the existing externally supervised synthetic-toolchain fixture and actual exported loader/opaque descriptor. Mocked mount text and package bytes are fixture data only; no actual owner/immutable evidence is supplied. No actual SDK import or network operation is needed.

- [ ] Add a cancelled late-open case matching the retained probe: intercept a real selected-worker revalidation open, acquire its real FileHandle, delay delivery until after abort, and make its close reject without closing. Record actual descriptor openness with `fstatSync` using a captured descriptor before independent cleanup. Require `cleanup_failed`, zero spawn/readback/result, and no continuation into verification/import/descriptor registration. The test must fail against220d9c3 for the observed `operation_cancelled`, not an unrelated missing policy.
- [ ] Add an ordinary inspection-failure case after a real open (for example a controlled file stat/identity failure), together with a rejected close. Require `cleanup_failed` instead of missing_dependency/invalid input; assert zero spawn/readback. Exercise the path where the inspection rejection is already settled when the catch/error selection runs.
- [ ] Add timeout plus rejected late-open close, requiring the same cleanup_failed precedence. Add a case where close actually succeeds then its wrapper rejects, proving rejection is never normalized into successful closure. Retain successful-close cancellation/timeout controls to prove those still return their original reason when cleanup succeeds.
- [ ] Each failure fixture records actual FD state at public return and independently closes through a captured original close in finally, including assertion/watchdog failure paths. Require bounded fixture completion and prove the captured FD is closed afterward. The independent fixture close must not run before the public-result observations or impersonate production cleanup success. An external watchdog prevents hangs; it is not the tested cleanup mechanism.
- [ ] Run focused tests against220d9c3 before implementation and retain red logs/probe evidence. Implement only the ownership, failure precedence and closure proof specified above; run focused tests green with no unhandled rejection or residual descriptor. Commit only a coherent validated milestone.

## Task3: full verification and exact candidate review

- [ ] Verify reviewed executable SHA256 `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`; run `/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs` (all prior103 plus new regressions) and Node --check on both files.
- [ ] In `infra/deploy/gce`, run `python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q` (unchanged143 tests). Keep dedicated staging blockers and production job hashes unchanged.
- [ ] Run git diff --check, exact two-file implementation allowlist comparison against this full checkpoint SHA and its pinned preflight. Verify package/lock, Python and workflow remain identical.
- [ ] Commit/push and report exact candidate/helper hashes, red/green evidence and remaining owner/live/advisory/license blockers. Stop for independent exact-SHA review; passing offline tests does not authorize live publication.

Tracking synchronization: https://github.com/lucronn/autodata/issues/186#issuecomment-6622115738; exact Issue/Project readback verified 2026-11-04T03:56:17.962371+00:00. Full immediately prior Project index SHA256 `b659ea4027bf30ac2eb7f2f1baec139efeff9b924d5d0a8b5566980d595896c8` and PG details6622084338/6622103154 are preserved verbatim/hash in that comment. No PG authority or readiness status is changed.
