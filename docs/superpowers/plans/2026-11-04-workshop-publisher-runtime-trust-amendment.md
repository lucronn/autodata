# Workshop publisher runtime trust protocol amendment plan

> **For agentic workers:** Use superpowers:executing-plans only after a new synchronized checkpoint, passing canonical preflight and explicit coordinator code-only dispatch. This pending draft authorizes no implementation or delegation.

**Goal:** Decide and document a runner-boundary publisher trust protocol using signed GitHub OIDC run/attempt identity, opaque Results credentials, independent original-byte artifact readback and a signed post-upload statement; preserve every implementation and activation denial until separately gated.

**Architecture:** Keep the Results bearer opaque and require an explicit owner choice about trusting the protected runner. If accepted, use signed OIDC run/attempt identity, independent original-byte REST readback and a cryptographically verified post-upload statement to establish the stated runner-origin guarantee. Preserve Stage1A's unsupported runtime authentication and every CLI/workflow denial.

**Tech Stack:** Existing pinned Linux x64 Node22.23.4, built-in cryptography for offline fixtures, Python adapter tests; future Sigstore profile and roots must be owner-selected and pinned before a new gate. No dependency install or runtime operation in this draft.

**Spec:** `docs/agents/specs/2026-11-04-workshop-publisher-runtime-trust-amendment.md`.

## Draft status and references

Status **pending/blocked**; `implementation_authorized:false`. Exact source candidate `4d82e413e04fb2401ac7bc28dc828375ac662180`; branch `codex/workshop-publisher-trust-amendment`. Issue https://github.com/lucronn/autodata/issues/186 and Project https://github.com/users/lucronn/projects/8 are existing references only. No GitHub update, commit/push, synchronized status or positive preflight is claimed. The canonical gate is `docs/agents/pre-implementation-gate.md`. Historical Stage1A synchronization is not synchronization of this amendment.

## Scope

This draft may change exactly these six documentation paths:

- `docs/superpowers/plans/2026-11-04-workshop-publisher-runtime-trust-amendment.md`
- `docs/agents/specs/2026-11-04-workshop-publisher-runtime-trust-amendment.md`
- `docs/agents/records/2026-11-04-workshop-publisher-runtime-trust-amendment.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-runtime-trust-amendment.json`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/operations/workshop-gcp.md`

All implementation/workflow bytes remain equal to the source candidate. Add one pending queue entry without modifying any existing entry. Keep old specs/records/todos intact; the canonical operations note links this additive proposal.

The proposed future **dormant code-only** allowlist is exactly six paths, subject to owner decisions and a separate complete gate:

- `infra/deploy/gce/publisher_runtime_trust.mjs`
- `infra/deploy/gce/test_publisher_runtime_trust.mjs`
- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/test_publisher_artifact.mjs`
- `infra/deploy/gce/publisher_adapters.py`
- `infra/deploy/gce/test_publisher_adapters.py`

`publisher_runtime_trust.mjs` would own bounded passive protocol/statement validation and explicit runner-trust result types; its test file owns real local cryptographic and hostile-input fixtures. The artifact pair would replace the misleading injected bearer-authentication requirement with an explicitly named runner-boundary contract in the dormant injected path. The Python pair would bind existing statement validation to the amended trust-model evidence and exact signer attempt checks. No production handle factory, installed runtime policy schema/loader, transport, token acquisition, signer client, dependency/package/pin change, workflow permission/blocker change or CLI wiring fits this allowlist. If implementation requires any such path or new authority, stop for a separate plan/gate rather than expanding this draft. Stage1A policy/identity modules and tests are frozen.

## Concrete todo

- [ ] Obtain the owner decision on independent cryptographic Results bearer binding versus explicit protected-runner trust; reject the proposed protocol if independent bearer binding remains required.
- [ ] Review the proposed exact identity, original-byte readback, post-upload signature and negative-test contracts at candidate 4d82e413e04fb2401ac7bc28dc828375ac662180; retain all existing Stage1A and workflow denials.
- [ ] Resolve owner signer/verifier roots and pins, numeric repository/owner IDs, protected workflow/environment policy, endpoint/credential separation and replay policy; record actual decisions without fixture substitution.
- [ ] After independent draft review and coordinator tracking-slot release, synchronize this goal, six-document scope, proposed future implementation allowlist and concrete todo with Issue186/Project8 preserving all prior lane evidence; commit/push a checkpoint, pin its full SHA and pass canonical preflight before any builder dispatch.
- [ ] Only under a separately approved code-only gate, implement and test the six-path dormant protocol amendment with real local cryptographic fixtures, original-byte negative cases and unchanged Stage0/Stage1A/workflow regressions; obtain exact-SHA review before any separate live activation gate.

## Task1: owner trust decision and independent draft review

- [ ] Compare the unsupported bearer-authentication callback in candidate `publisher_artifact.mjs` with the unconditional Stage1A denial and the research references in the spec.
- [ ] Have the owner record choice1 (remain blocked) or choice2 (accept precisely stated runner boundary). Record signer/identity profile and replay decisions. No owner decision is fabricated by this plan.
- [ ] Review the exact signed-statement field inventory, source/control separation, original-byte/ZIP semantics, inability of artifact metadata or exact-attempt REST alone to prove originating attempt, and real-signature negative matrix.
- [ ] Check that the six proposed code-only paths can implement passive/dormant contracts without an installer/factory/runtime policy or credential acquisition. Any required broader mechanism is a separate gate.

## Task2: tracking and checkpoint, only after new authorization

- [ ] Obtain coordinator tracking-slot release; preserve every immediately current Issue/Project lane index/detail receipt. Add amendment goal/spec/plan/six-path proposed code scope and the exact todo to Issue186/Project8; verify live readback and record hashes. This draft does not authorize those writes.
- [ ] Update canonical operations note and record/task/queue consistently, then commit/push the reviewed synchronized docs checkpoint. Pin the full committed checkpoint SHA, never pretend the source candidate already contains it.
- [ ] Run `scripts/autonomy/pre_implementation.py` through the existing canonical preflight caller using the new record and exact checkpoint. Retain full output. Require `status:synchronized`, no errors, independent exact-checkpoint acceptance and explicit root dispatch before code.

## Task3: separately gated future offline protocol changes

- [ ] Write failing tests for the spec matrix using actual local signatures, exact raw byte digests, instrumented fake transports and owned child fixtures. Retain red output before changing the dormant protocol.
- [ ] Add bounded passive strict schemas for trust-model/statement observations; no callback or caller boolean can mint installed runtime authority. Keep `authenticateActionsRuntime()` unconditionally unavailable and do not reuse Stage1A offline policy as runtime authorization.
- [ ] Amend the dormant artifact callback name/contract to describe runner-boundary association, never independently authenticated bearer identity. Test that no fabricated callback output claims `runtime_bearer_authenticated:true` and that unsupported/missing boundaries fail before spawn.
- [ ] Enforce the ordered OIDC/context → upload → original-byte readback → complete owned cleanup → signed statement → independent consumer verification protocol. Existing Python v3 statement/core field schemas remain exact; any schema version change requires updated exact contracts and gate review first.
- [ ] Run focused new Node and Python tests, all unchanged Stage0/Stage1A/artifact/adapter regressions and `test_release_workshop_contract.py`; syntax/scope/diff checks and exact frozen workflow/source comparisons. Use only the repository-reviewed Node binary after checking its SHA256; no ambient Node substitution or network setup.
- [ ] Commit/push small validated milestones only after authorized implementation dispatch; obtain independent exact-SHA review. Evidence remains fixture-only. Stop before every installer/factory/SDK/live upload/workflow/signing operation; those require separate accepted owner inputs and live activation gate.

## This draft's validation

Check JSON parsing, matching goal/todo/base/allowlists across record/task/queue, exact six-path docs scope, `git diff --check`, and byte equality of every tracked non-document path to the source candidate. Call `validate_record` against the source candidate and retain expected blocking errors: pending status and amendment plan/spec absent at that committed base. An expected blocking result is not a passing implementation preflight. No application suite or live compatibility run is claimed for this docs-only draft.
