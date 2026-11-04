# Workshop artifact boundary corrections implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after a committed synchronized checkpoint, pinned passing preflight, independent exact-checkpoint review and coordinator dispatch. This draft authorizes no implementation or live operation.

**Goal:** Authenticate installed toolkit bytes and enforce an owned process-and-pipe termination boundary plus nonblocking archive preflight while preserving dormant publisher execution.

**Architecture:** Verify an independently selected complete installed-file manifest on a read-only toolchain mount before any official package import. Run the official upload in an owned child process with a dedicated result pipe and captured log pipes, and require process termination/reap plus pipe closure before returning any upload observation or cancellation. Read the fixed archive with nonblocking no-follow descriptors inside the total deadline; absent owner inputs retain the existing denial.

**Tech Stack:** Node22.23.4 linux/x64; standard node:fs, crypto and child_process; reviewed official @actions/artifact6.3.1; Node contract tests with harmless local child processes; existing Python workflow/host tests.

**Spec:** docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md; docs/agents/pre-implementation-gate.md. Independent review: /tmp/autodata-artifact-a2453848-review.md and retained JSON probes below.

Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 .

## Status, exact base and evidence

Status: **synchronized planning / implementation blocked pending committed pinned preflight, independent exact-checkpoint review and coordinator dispatch**. Source candidate `a2453848ed596a00574d63a2ca5cc77d28464c99` on `codex/workshop-publisher-artifact` is not approved as a runnable authenticated publisher. Earlier checkpoint b431e548 authorized the candidate, and 3db18c1 authorized only its named legacy workflow-test correction. Neither silently authorizes this security repair. The coordinator accepted the three correction directions and the explicit self-child mode, subject to this new narrow gate.

The independent review retained52 passing Node tests,143 passing Python cloud/host/workflow tests and unchanged production-job hashes, but proved three untested failures:

1. `/tmp/autodata-artifact-a2453848-loader-probe.json`: `unhashedReplacementPackageAccepted=true`. Package name/version/main and lock SRI text do not hash installed executable or transitive bytes; a replacement module can execute with the runtime bearer present.
2. `/tmp/autodata-artifact-a2453848-cancel-probe.json`: `doneAtReturn=false`, `operationCompletedAfterReturn=true`, `lateOutputEscapedSuppression=true`, `cleanupCalled=true`. Promise.race only rejects the waiter; restoring parent stdout/stderr leaves a still-running official SDK able to upload/log. The current never-resolving fake tests no actual termination.
3. `/tmp/autodata-artifact-a2453848-fifo-probe.json`: `fifoBlocked=true`, `timerElapsed=true`, `returnedError=false`. Blocking O_RDONLY happens before regular-file validation and outside the bounded cleanup path.

These failures remain historical red evidence; fixture success is not live Actions compatibility, publication acceptance or remote cancellation proof.

## Exact scope and global constraints

Implementation allowlist is exactly:

- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/test_publisher_artifact.mjs`

No workflow, toolkit package/lock, Python implementation/test, production job, CLI, application, schema, runtime, registry, owner policy or activation file may change under this correction. Documentation synchronization may additionally change this new plan/record/task and the appended canonical operations note. No dependency install, package fetch, real SDK network operation, token acquisition, cloud/registry/provider/host operation, workflow dispatch or workflow activation is authorized. Existing saved official tar/Node evidence may be read locally.

Preserve the existing exact request and response fields, source/workflow/run/attempt identity, single release.zip input, outer-vs-inner digest checks, immutable fresh artifact ID, retention7days/compression0/no overwrite, fixed redacted errors and every production denial. Default direct helper execution, including malformed/unknown arguments, must exit3 without reading stdin, runtime environment credentials or loading a package. A separately explicit internal worker mode is permitted only under the guarded owned-child boundary below; a flag or caller JSON is never activation authority.

Retain selected official artifact6.3.1 SRI `sha512-DBXgdB9T4yj2KSe0tFg+MTi9T5se+16bdrFQh+3Y6Nq1lZ3gYQk1BjHoTof+7Zf36bEAlfVMf+8ifRKeyGJugQ==`; lock SHA256 `3e697f78715f0ef89dfd4f60c1ed9902e21dbfd3fadb2cbd7c39776192611bf5`; Node archive SHA256 `1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce` and executable SHA256 `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`. Do not upgrade/override packages or invent an accepted tree/owner policy. Seven moderate advisories and buffers0.1.1 unresolved licensing remain explicit activation blockers.

## Decision1: authenticate the whole installed tree before import

Extend only the loader's private exact policy schema with `toolkit_tree_sha256`. This is an independent owner-selected SHA256 under the authenticated toolchain/trust policy, not a hash derived from the currently installed tree at operation start. Keep context activation/toolchain/trust/workflow/helper/lock/Node pins and strict primitive checks. Missing tree hash, manifest or read-only proof returns fixed missing_dependency; drift is invalid authenticated publication input. No callback or package top-level code may run before this check.

A separately provisioned reviewed toolchain supplies the fixed file `publisher-toolkit/installed-tree.json`; this runtime input is absent from the repository and this task must not create a real activation manifest. Its exact schema is:

```text
{protocol_version:1, toolkit_lock_sha256:64hex,
  packages:{<exact lock node_modules path>:{version, resolved, integrity}},
  files:[{path:<normalized relative POSIX path>, bytes:<int>, sha256:64hex, mode:<int>}]}
```

The authenticated manifest hash is SHA256 of its original bounded UTF-8 bytes; strict parsing rejects duplicate keys, nonfinite/boolean numbers, unknown fields, paths containing dot segments/backslashes/control characters, repeated paths, symlinks, hardlinks and excessive depth. Maximum manifest8MiB, file count50000, relative path1024bytes/depth32, each file64MiB and total tree1GiB. File entries sort uniquely by path. The packages map must equal every nonroot package in the reviewed lock by path/version/resolved/integrity, with no extra/missing package; every resolution stays exact HTTPS npm with SHA512 integrity. Each expected package has its package.json bound and matching name/version. The files inventory includes all regular files under publisher-toolkit except installed-tree.json itself, including root package.json/package-lock.json and every node_modules executable/transitive/data file; no unlisted files/directories/links or writable/special entries are accepted. Directories are the exact parent-prefix closure plus the manifest parent. The toolchain assembly owner derives/reviews file bytes against the exact integrity-verified package tarballs before approving the manifest; hashing installed files cannot create approval.

The helper independently reads /proc/self/mountinfo and requires a read-only effective mount covering the fixed canonical toolchain root, with no writable nested mount covering a listed entry. Reject a read-write mount even when file mode bits look read-only. Verify expected owner, regular-file/no-follow/nonblocking descriptors, single link, size/mode/hash, and stable device/inode/stat around reads. Open/read/hash through the selected descriptors; a read-only mount and independently selected immutable toolchain prevent replacement between validation and import. Filesystem inspection shares the global deadline. No package import occurs in the parent uploader; the child repeats verification immediately before its fixed import. Missing actual mount/manifest evidence remains blocked; synthetic unit fixtures do not certify real toolchain immutability.

Pure verification functions may accept explicit fixture roots/manifest bytes in tests, but the real loader selects only its fixed sibling toolchain path. No caller path/module/command option is added to the CLI. The loader produces a guarded fixed worker descriptor rather than an in-process SDK upload callback. Public `uploadRelease(request, dependencies)` and its final observation shape remain stable; dependencies migrate from arbitrary toolkit.uploadArtifact callbacks to the owned fixed-process constructor and separate trusted readback/clock/cleanup operations. Injection remains at the OS spawn boundary for tests, never a caller-asserted `terminated:true` or `tree_verified:true` report.

## Decision2: own and terminate the SDK process before returning

The real parent always spawns the reviewed absolute Node binary with exactly `[fixed_helper_path, '--internal-upload-worker']`, shell=false, detached=true on the selected Linux runtime and one upload per child. The helper path/hash and Node path/hash are verified before spawn; callers cannot choose argv, executable, module, mode or arbitrary package path. The child receives only fixed allowlisted Actions runtime/GitHub job identity environment after owner/context/tree checks. It receives no REST GITHUB_TOKEN, WIF credentials, developer/proxy/agent environment or inherited secrets. Parent REST readback remains independent and follows only a validated fresh SDK result.

Use stdin for one bounded exact internal envelope `{request, policy}` (maximum64KiB) and fd3 for one bounded exact SDK observation JSON `{id, size, digest, digestMismatch?}` (maximum64KiB); stdout/stderr are separate parent-owned pipes that are always captured/discarded and never forwarded. Strict duplicate/type/field parsing applies at both ends. Internal child mode requires exact argument count, private pipe descriptors and the independently authenticated/installed owner-toolchain context; direct flag/JSON calls without it fail closed before tokens/import. A private channel proves process association, not owner approval. Do not manufacture an installed activation policy in tests or this gate.

Only the child imports and calls official DefaultArtifactClient.uploadArtifact(name,[fixed_release_path],fixed_private_root,{compressionLevel:0,retentionDays:7}). Parent wrapper enforces no overwrite/delete/hidden input and validates bare-hex SDK digest; `sha256:` normalization remains solely the observation format. No list/latest/download/delete or arbitrary toolkit method is exposed. The worker cannot accept a supplied artifact ID or return caller evidence.

The parent session tracks actual ChildProcess ownership/PID/process group, child close/wait status and all four streams internally. Success requires one valid complete result, zero child exit, drained/closed streams and proven termination before raw REST readback can start. A zero exit with missing/truncated/multiple/extra result messages fails. SDK stdout/stderr have individual64KiB caps and combined64KiB cap; result pipe has its own64KiB cap. Unknown lengths stop on limit+1; no buffered unbounded log or raw error enters a receipt.

Every upload uses the existing monotonic absolute deadline, maximum300s and30s reserved cleanup; no child or phase resets it. On abort/timeout/overflow/error/cancellation/SIGTERM: stop new operations, mark the result unusable, close stdin, send SIGTERM to only the owned process group, retain pipe capture/drain, wait2s then SIGKILL if needed, wait/reap the direct child and prove no owned process group remains plus all pipes/readers closed before returning the fixed operation_cancelled/operation_timed_out/output_limit_exceeded error. All termination/draining/reaping fits within the original30s cleanup reserve. Missing process/group/pipe closure proof or expiry returns cleanup_failed with no upload observation. No cancellation success is inferred from a callback invocation, AbortSignal or Promise rejection. Do not restore/monkeypatch parent output: process-isolated pipes make late SDK output unable to enter the parent's private JSON stream.

An accepted local termination does not prove rollback of an already transmitted remote upload. Failed/cancelled sessions never issue an accepted binding, sign evidence, reuse an artifact ID or claim remote deletion. Orphans and actual remote cancellation remain separately owned future staging evidence.

## Decision3: reject blocking archive types inside the deadline

After pure request/policy/deadline shape checks, enter the owned operation try/finally before filesystem preflight. Require the dedicated0700 directory and exactly release.zip. lstat its entry and reject nonregular files without opening. Open `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`; immediately fstat again and require regular file, owner,0600 mode, single link, exact bounded size and stable identity versus pre-open stat. Read at most the approved inner length+1 through that descriptor, compare the approved SHA256, verify post-read identity and close in finally. The nonblocking flag prevents a replacement FIFO from hanging between lstat/open. Do not accept a platform missing the selected nonblocking/no-follow primitives.

Filesystem validation has a maximum30s phase bound within the existing monotonic total deadline and30s cleanup reserve. Close every acquired handle and invoke owned cleanup even on FIFO/type/path/hash/race failure; no runtime authenticator, SDK child or readback starts. Regular files on the approved private local workspace are the only accepted input; filesystem hang/descriptor cleanup still depends on the containing reviewed process supervisor and cannot be asserted away.

## Concrete todo

- [ ] Synchronize the three review findings, exact two-file correction scope and retained red evidence across Issue186, Project8 and canonical docs; commit and pass pinned preflight for independent review before implementation.
- [ ] Bind a complete independently approved installed package-tree manifest to the exact reviewed lock and immutable toolchain; reject package or transitive file drift before import or runtime credential use.
- [ ] Replace in-process SDK callbacks and Promise-only cancellation with one fixed verified child process, private result pipe, bounded log pipes, termination and reap proof before any cancellation or upload result returns.
- [ ] Open release.zip nonblocking and no-follow, reject nonregular or replaced files, and put filesystem preflight under the same deadline and cleanup reserve.
- [ ] Run real local tamper, late-output, process-group, cancellation, deadline, overflow and FIFO red/green regressions plus existing focused suites; push exact candidates for independent review with every activation denial and audit limitation intact.

## Task1: synchronize the correction gate, without implementation

Files: this plan; `docs/agents/records/2026-11-03-workshop-artifact-boundary-corrections.json`; `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-boundary-corrections.json`; docs/operations/workshop-gcp.md appended correction note.

- [ ] Refresh the CURRENT Issue186/Project8 index after the assigned tracking slot is released. Preserve the immediately preceding full PG17 index/detail verbatim and SHA256 in an Issue comment, then point the Project index to both histories with the exact goal/todo/scope. Do not overwrite unrelated status or claim previous candidate acceptance.
- [ ] Read back Issue comment and Project text exactly, write synchronized hashes/URLs into the new record/task, commit/push a docs-only checkpoint and run the canonical preflight against its full SHA.
- [ ] Obtain independent exact-checkpoint review and explicit coordinator dispatch; until then leave both implementation files byte-identical to a2453848.

## Task2: reproduce and repair installed-tree trust

Files: publisher_artifact.mjs and test_publisher_artifact.mjs only. Interfaces: strict tree manifest/policy above; pure verifier returns no executable and throws fixed errors. Loader produces only a fixed worker descriptor after all checks.

- [ ] Add tests with a synthetic local package tree whose expected manifest is independently written before mutation. Replace root package executable while keeping package.json metadata and lock unchanged; require rejection before an import sentinel can write. Repeat for a nested transitive dependency file, missing/extra file, symlink/hardlink, duplicate manifest key/path, mismatched lock package/SRI, unbound tree hash and writable mount fixture. The valid synthetic expected tree passes byte verification but is never represented as GitHub-authenticated code.
- [ ] Run these tests against the old loader/verifier boundary and retain failure evidence; the replacement probe must fail for its demonstrated metadata-only acceptance, not a missing arbitrary credential.
- [ ] Implement bounded complete manifest/tree verification and fixed read-only mount checks before any credential/import boundary. Keep absent real manifest/owner policy as missing_dependency. Verify old replacement and transitive tamper tests reject, positive pure fixture passes, and default CLI remains exit3. Commit/push a coherent validated milestone without generating a real installed manifest or acquiring a token.

Illustrative assertions, driven by explicit synthetic files rather than self-generated approval:

```js
await assert.rejects(verifyInstalledTree(treeRoot, approvedManifestBytes, approvedManifestHash, reviewedLockBytes), /invalid authenticated publication input/);
assert.equal(await sentinelExists(), false);
assert.equal(outboundCalls.length, 0);
```

## Task3: reproduce and repair actual process cancellation/output isolation

Files: the same two files. Interfaces: fixed self-child mode/internal request/result schema above; parent-owned OS child/pipe state, unchanged final public upload observation.

- [ ] Preserve a local child fixture that schedules a delayed stdout/stderr marker and completion-file write after the parent aborts. Run the old implementation's cancellation probe to establish `operationCompletedAfterReturn=true` and escaped output. Tests must observe the real child state/marker/parent output, not merely a mocked cleanup-call count.
- [ ] Add actual spawned harmless fixtures for: valid one-result exit0; exit without result; duplicate/truncated/oversized result; stdout-only/stderr-only/combined limit+1; child ignoring SIGTERM; abort and deadline races immediately before/after result; inherited pipe held open by a same-group child; and a fixture child that reaps its descendant. All use /tmp and unmistakably synthetic origins/tokens, no official SDK import or outbound socket. Inject only the low-level spawn boundary to execute the local fixture while asserting the real constructor requested the fixed Node/helper/args/environment.
- [ ] Implement fixed child ownership, private result/log pipes and TERM/KILL/reap/pipe closure state machine. Missing or failed group-absence/stream-closure proof yields cleanup_failed and no readback/result. After a successful abort return, wait past the fixture's delayed marker deadline and assert no completion marker, no live child/group and no secret marker in parent stdout/stderr. Repeat the timed-out and output-overflow paths. No success boolean from a fake replaces these observations.
- [ ] Run complete Node contracts and unchanged CLI denial tests. Commit/push this validated milestone, retaining the review's original failed probe. Do not invoke the real official SDK or install an owner activation manifest.

## Task4: reproduce and repair FIFO preflight

Files: the same two files. Interfaces: fixed release.zip file and existing archive hash/size; no caller path argument is added.

- [ ] In a private /tmp0700 fixture create release.zip with local `mkfifo -m 600` and no writer. Run the library in an externally supervised harmless child with a subsecond test watchdog. The old implementation must remain pending and be killed by the watchdog, matching the retained red probe.
- [ ] Add negatives for directory, socket/symlink/hardlink, wrong owner/mode/size and replacement between lstat/open. Verify regular approved bytes still succeed through the unchanged readback digest checks.
- [ ] Implement nonblocking/no-follow open and pre/fstat/post-read identity/type validation inside the bounded try/finally. Require prompt fixed invalid-input error for FIFO, closed file descriptors, no authenticator/worker/readback call, and completed cleanup. Retain the external watchdog as a fail-safe, but green is the helper returning its own rejection before the watchdog fires. Commit/push after focused tests pass.

## Task5: final verification, exact scope and independent handoff

- [ ] Run all Node tests with `/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs`, verify the executable SHA256 first, and retain complete logs. Run Node --check on both files.
- [ ] From infra/deploy/gce run `python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q`; previous143 cases and all unchanged production checks remain required. Python publisher tests belong to the separate worker and may be run after coordinator integration, never fabricated on this branch.
- [ ] Run py_compile on unchanged focused Python tests only if required by integration, git diff --check, full-SHA pinned preflight and an exact implementation diff allowlist against the new gate. Verify both staging blockers and frozen production hashes through the existing dedicated tests; do not edit their expectations.
- [ ] Push coherent validated candidate(s), report real red/green evidence and remaining absent owner/immutable-tree/origin/runtime/staging inputs, then request independent exact-SHA review. Do not call the result a runnable/authenticated publisher until that review and a separately synchronized activation gate accept it.
