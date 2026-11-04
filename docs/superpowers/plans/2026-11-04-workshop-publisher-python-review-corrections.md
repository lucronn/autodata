# Workshop publisher Python review corrections implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development only after the coordinator independently reviews the committed full-SHA machine-passing checkpoint and explicitly dispatches correction implementation. This turn is documentation and tracking only.

**Goal:** Correct the dormant Python publisher library's missing upload-pin acceptance, FIFO open hang and SIGTERM child leak without adding live publication or activation authority.

**Architecture:** Keep candidate and publication phases separate. Require a finite upload policy before finalize/verify callbacks, open private outputs without blocking on special files, and make the synchronous main-thread executor own SIGTERM and its isolated child process group from creation through cleanup. Preserve all existing authenticated-composition dependencies and false readiness.

**Tech Stack:** Python standard library; unittest; local harmless child processes and temporary files; injected local signing/transport fixtures only.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md`; `docs/agents/pre-implementation-gate.md`; independent review of candidate `d94b2a4a77aad1cd7f3d62514e4c20729ba4cd39`.

## Pinned source and evidence

Source candidate: `d94b2a4a77aad1cd7f3d62514e4c20729ba4cd39` on `codex/workshop-publisher-python`; original adapter gate `b431e548df4f379f6752e021c6fb42e8837a5311`. The correction checkpoint is a new descendant containing only this plan, its task/record and an additive canonical operations note. Its full SHA, machine preflight and independent coordinator review must precede implementation. This plan is not an integration or activation approval.

Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 . Dedicated record: `docs/agents/records/2026-11-04-workshop-publisher-python-review-corrections.json`. Dedicated task: `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-python-review-corrections.json`.

Independent reviewer reproduced: (P1) absent `toolkit_lock_sha256` and `runtime_service_origin`, together with null signed observations, can yield `uploaded_unaccepted` and `publication_verified`; (P2) an owned0600 FIFO blocks `private_read` in `open` before `fstat`; (P2) default SIGTERM exits the executor owner without Python cleanup, leaving its isolated child alive. Review file: `/tmp/autodata-publisher-d94b2a4-review.md`; process probe: `/tmp/autodata-publisher-d94b2a4-review-process-probes.json`, containing `fifo_blocked:true` and `bounded_child_survived_parent_SIGTERM:true`. These local temporary paths are evidence pointers, not required runtime inputs or authority. The reviewer killed its owned probes. Available candidate suites had169 passing tests; the absent JS workflow module was not reported passing.

## Global constraints and exact scope

- Implementation allowlist: only `infra/deploy/gce/publisher_adapters.py`, `infra/deploy/gce/test_publisher_adapters.py` and additive `docs/operations/workshop-gcp.md` notes.
- This planning turn may additionally create this plan and its dedicated record/task; it changes no implementation bytes. Preserve historical plans, records and Project index verbatim/hash in the synchronized Issue comment.
- No workflow/toolkit/production job, runtime/cloud CLI, schema, application, IAM, environment variable, secret, tool or dependency-lock changes. No cloud, registry, provider, host, Docker, live toolkit, token or credential operation.
- Default WIF/OCI push/Syft/keyless signature and certificate-extension/transparency composition remains uninstalled. Trusted injected local fixtures do not establish authenticated provider functionality. All deployment/schema/services/runtime-evidence readiness remains false.
- Keep original outer ZIP bytes, inner/member hashes, source/workflow SHA separation, exact run/attempt authentication, independent full-manifest approval, rollback argument/hash and finalization without build/copy/retag/evidence regeneration intact.
- Error messages remain fixed/redacted. Missing or malformed phase upload policy fails before `prepare`, credential, signing, upload, metadata, download, registry or other dependency callbacks. Candidate-only operation may continue to omit upload pins because it does not upload Actions artifacts.

## Concrete todo

- [ ] Synchronize this three-defect correction goal, exact source/allowlist and todo across Issue186/Project8/canonical operations notes; preserve the previous Project index verbatim/hash; commit/push, pin full-SHA preflight, and stop for independent checkpoint review and fresh coordinator dispatch.
- [ ] After dispatch, add red/green regressions for missing/null/empty/malformed upload owner pins and observations; require typed canonical HTTPS origin and lowercase64 toolkit SHA before finalize/verify callbacks, preserving a valid fresh signed positive control.
- [ ] Add a subprocess-isolated FIFO red/green regression with an external test deadline; open private outputs nonblocking/no-follow and reject every nonregular output before reading, retaining existing ownership/mode/link/size/digest guards.
- [ ] Add owner-boundary SIGTERM red/green regressions for an ordinary child and a SIGTERM-ignoring child; install and restore bounded main-thread cancellation ownership around process creation through cleanup, reject unsupported thread/mask ownership before spawning, and prove owned child termination/reaping.
- [ ] Run focused and existing Python regressions, syntax, exact-scope/diff and pinned preflight; commit/push coherent verified corrections for independent exact-SHA review, retaining every no-live/default-dependency/readiness limitation.

### Task1: phase-specific upload owner policy

**Files:** publisher_adapters.py and test_publisher_adapters.py under `infra/deploy/gce/`.

**Consumes:** the existing finite policy projection, `LiveContextV3`, independently signed approval and injected fixture dependencies. **Produces:** a pure `_upload_policy(policy)` guard and strict observation validation; no new wire fields or credentials.

- [ ] Write regressions extending `FullFlowTests` and `VerificationTests`: remove each owner pin, set it to null/empty, use a malformed SHA, HTTP origin, wildcard/userinfo/path/query/fragment/non443 origin, and set each signed observation to null/empty/malformed. For finalize and verify, instrument **every** dependency operation (including `prepare`/cleanup) and assert zero calls for invalid owner policy. First build a valid local binding for verifier tests, then reset call history and remove policy pins; reconstruct the review's null/null observation case. Keep the valid current fixture as positive control.
- [ ] Run `python3 -m unittest test_publisher_adapters.FullFlowTests test_publisher_adapters.VerificationTests -v`; confirm the null/null case fails the new rejection assertion on the source candidate.
- [ ] Implement the pure guard before any dependency access in finalize and verify. Require `type(value) is str`, SHA pattern `[0-9a-f]{64}`, and a canonical HTTPS origin whose spelling is exactly `https://HOST` (lowercase DNS host; no IP, wildcard, port spelling, userinfo, path including trailing slash, query, fragment or controls). Use the existing strict URL guard without DNS/network calls. Raise fixed `missing_dependency` for missing owner policy; malformed data remains a fixed invalid-input error. Use direct typed validation of observed toolkit SHA/runtime origin followed by equality to already validated policy. No `None == policy.get(...)` authority check survives. Host checks inherit the same guard via independent verification.
- [ ] Repeat the focused tests, then run the full Python regression command below; commit a coherent validated correction after green.

### Task2: bounded private output open

**Consumes:** private parent directory fd, fixed member name and existing maximum size. **Produces:** unchanged regular-file byte result or immediate fixed rejection for a FIFO/socket/device/directory/symlink/hardlink.

- [ ] Write a local subprocess probe test that creates an owned0600 FIFO in a private0700 directory and calls `private_read`. The test runner uses `communicate(timeout=3)` and kills/reaps its exact probe group in `finally` if the old implementation hangs. On the source candidate this must fail with an explicit bounded-test timeout; no test process is left blocked. Retain the existing regular-file positive control, symlink-parent and hardlink negatives.
- [ ] Run that single test and observe red before implementation.
- [ ] Change only the output open flags to include `os.O_NONBLOCK` alongside `O_RDONLY|O_NOFOLLOW` and existing `dir_fd`. Immediately `fstat` and require a regular file before any read. Preserve0700 parent,0600 file, exact owner, single link, before/after identity/size/mtime and maximum-byte checks. `O_NONBLOCK` is harmless on regular files and prevents the FIFO open from waiting for a writer; do not open a writer, retry a special file or follow a fallback path.
- [ ] Repeat the single test and all existing private-file tests; commit after focused regressions pass.

### Task3: synchronous SIGTERM ownership

**Consumes:** the existing fixed argv/cwd/env/deadline and executor's isolated process group. **Produces:** the same normal result or fixed `operation_cancelled` exception after bounded owned cleanup, with prior SIGTERM handler/mask restored.

- [ ] Add a subprocess **owner-boundary** test. A disposable owner invokes `bounded_process` on a harmless child that writes its PID/ready marker then sleeps. The test waits for ready with a monotonic3s limit, sends SIGTERM to the owner (not just the child), waits at most6s, and asserts the owner reports fixed cancellation and the child no longer exists after reaping. The test's outer `finally` kills only recorded owned PID/group probes on failure. Add a child that ignores SIGTERM to require escalation; keep timeout, overflow and normal-result tests. Add main-thread restriction and prior-handler/mask restoration assertions. Non-main-thread execution must fail before `Popen` because Python cannot install a process-wide handler there.
- [ ] Run the signal tests against the source candidate and observe the surviving-child failure reproduced by the reviewer.
- [ ] In `bounded_process`, require main-thread signal ownership and `pthread_sigmask` support before spawning; reject an inherited SIGTERM-blocked mask or nested executor ownership before `Popen`. Establish `process=None` and save prior SIGTERM handler/mask. Block SIGTERM while installing a temporary handler and starting the new-session child, then restore the unblocked prior mask **inside** the exception/cleanup scope after the child handle is assigned. This closes the start/assignment race. The temporary handler raises fixed `AdapterError('operation_cancelled')`, so the existing cleanup path runs.
- [ ] Keep SIGTERM blocked during final cleanup to prevent repeated delivery from interrupting it. Send SIGTERM only to the owned group, wait at most2s, send SIGKILL to that group even if its leader exited, and wait/reap the leader. Close every pipe. Restore prior SIGTERM handler and original mask after cleanup; any further pending SIGTERM then follows the caller's restored policy only after owned cleanup. Restore ownership on normal success, timeout, overflow, process-creation failure and cancellation. No global permanent handler, ambient supervisor assumption, remote cleanup claim or worker-thread spawning workaround is introduced.
- [ ] Repeat owner-boundary tests for both child behaviors, restoration/non-main-thread tests and existing process tests, then run all focused regressions and commit/push after green.

## Verification and handoff

From `infra/deploy/gce`:

```sh
python3 -m unittest test_publisher_adapters test_cloud_ops test_host_runtime -v
python3 -m py_compile publisher_adapters.py test_publisher_adapters.py
```

From repository root:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-publisher-python-review-corrections.json --base-sha FULL_COMMITTED_CORRECTION_GATE_SHA
git diff --check
git diff --name-only FULL_COMMITTED_CORRECTION_GATE_SHA
```

The coordinator supplies the full committed correction gate SHA after checkpoint review; it is not an input placeholder in executable code. Require exact implementation scope equality/subset of the two Python paths and additive operations notes; no JS/workflow suite is claimed available in this Python branch. Preserve individual red/green results, final suite output, fixed error codes, no-live limits and exact pushed candidate SHA for independent review. Do not edit implementation during this checkpoint turn or treat a passing preflight as independent review/dispatch. No integration, activation or runtime acceptance follows.

## Synchronized checkpoint tracking

Issue/Project readback verified 2026-11-04T03:22:25.061793+00:00. Synchronization comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621647909. Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, text field `Source or dependency reference` (`PVTF_lAHOCSJ8cc4BiQ2BzhhJhxU`). Previous Project index SHA256 `b8bca1611e3ed2563fb5ce71bfacbde542ee1f069e7ffd4c08f131fc30e4d26b` is preserved verbatim in that comment. Exact Issue body/comment/Project hashes are retained in the dedicated record. This records planning synchronization only; full committed checkpoint preflight, independent review and coordinator dispatch remain pending. No implementation bytes changed.
