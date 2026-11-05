# Workshop publisher Stage1A offline trust implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task only after the canonical repository gate passes and the coordinator dispatches. This local draft grants neither implementation nor delegation authority.

**Goal:** Build offline signed owner-policy and GitHub OIDC verification primitives while leaving Actions runtime-bearer authentication, SDK import, upload, all CLI/workflow execution and cloud activation unavailable.

**Architecture:** Two new Node modules perform bounded, passive owner-policy and OIDC verification using built-in cryptography. The installed-policy wrapper has one fixed independently provisioned trust source; pure fixtures cannot mint its private handle. Runtime-bearer authentication always throws `missing_dependency`; existing adapters, helper, package manifests and workflows are frozen.

**Tech Stack:** Linux x64 reviewed Node22.23.4, built-in crypto/filesystem modules and `node:test`; no new package dependency.

**Spec:** `docs/agents/specs/2026-11-04-workshop-publisher-stage1a-offline-trust.md` is the normative technical contract for this narrow proposed milestone.

## Planning and tracking status

SYNCHRONIZED DOCS-ONLY CHECKPOINT; `status: synchronized` after verified Issue/Project readback. Committed full-SHA preflight, independent exact-checkpoint review and root dispatch remain required; this is not implementation authority. Accepted baseline: `dde53d745f8422ce29d6e8b3d459f4a0b91ebd04`. Proposed branch: `codex/workshop-publisher-stage1a-plan`. Issue reference: https://github.com/lucronn/autodata/issues/186. Project reference: https://github.com/users/lucronn/projects/8. These references are synchronized by additive Issue detail and the Project index; full previous records are preserved verbatim/hash. No implementation or activation authority follows. Current PG and other lane details must be preserved by the tracking owner after serialized-slot release.

Record: `docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust.json`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage1a-offline-trust.json`. Canonical repository update: additive Stage1A planning-only section in `docs/operations/workshop-gcp.md`. No historical record or verified status is transplanted. The earlier local draft preflight was blocked as expected. Run machine preflight against the synchronized committed full SHA and retain the passing result; independent exact-checkpoint review and coordinator dispatch remain required before any implementation.

## Global constraints

- The canonical gate is `docs/agents/pre-implementation-gate.md`; no implementation before the complete committed synchronized record and passing full-SHA preflight.
- Proposed implementation allowlist is exactly the four new paths below. Existing source bytes, both helper CLI denials and every staging/production job body/permission remain unchanged.
- Use Node22.23.4 executable SHA256 `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90` at `/tmp/autodata-reviewed-node-v22.23.4` only after its bytes are verified. No ambient Node, dependency installation, SDK import or cloud/network operation.
- Fixed scope: Ed25519 exact-byte signed policy, strict bounded immutable trust reads, RS256 signed OIDC verification, and unconditional runtime-bearer denial. No active CLI, callbacks, transport, token acquisition, environment credential reads, factory composition, installed root provisioning or workflow changes.
- Actual roots, numeric IDs, protected subject/control SHA and authenticated JWKS bytes are absent owner inputs for future activation; tests use local fixture keys only. Their absence does not justify defaults or a positive installed-runtime assertion.
- New modules have no top-level operation. Their passive byte verifiers cannot supply installed-policy handles or current upload-session authority.

## Files and exact interfaces

| File | Responsibility |
| --- | --- |
| `infra/deploy/gce/publisher_policy.mjs` | Strict parser and base64 validation, pure Ed25519 envelope/schema verification, fixed installed bootstrap/policy/JWKS descriptor reads, private installed-policy handles. |
| `infra/deploy/gce/test_publisher_policy.mjs` | Real locally signed policy fixtures; strict parsing, tamper, times, file/mount-parser/descriptor cleanup and source-selection negatives. |
| `infra/deploy/gce/publisher_identity.mjs` | Pure bounded RS256 JWT verification using policy/JWKS bytes; installed-policy wrapper; unconditional runtime-bearer denial. |
| `infra/deploy/gce/test_publisher_identity.mjs` | Real RSA signed positive/negative fixtures, exact claims/time/key tests, OIDC/runtime type separation and zero-I/O denial tests. |

Freeze these exports; all record values are recursively immutable and all errors redacted:

```javascript
// publisher_policy.mjs
parseStrictJsonBytes(raw, limits) // passive strict JSON value
OwnedTrustReadScope // constructor({signal,budgetMs,cleanupReserveMs}); trackOpen(promise), track(promise), check(), finish()
verifyOwnerPolicyBytes(bootstrapBytes, envelopeBytes, jwksBytes, nowSeconds)
// returns frozen {policy,jwks,activation_sha256,trust_bytes}; passive, never installed authority
// trust_bytes exact shape {bootstrap_base64,envelope_base64,jwks_base64}; immutable strings
loadInstalledOwnerPolicy({signal} = {}) // Promise<opaque handle>; no path/fs/clock injection
installedPolicyClaims(handle) // deep-frozen {policy,jwks,activation_sha256}; rejects forged handle
// publisher_identity.mjs
verifyGithubOidcBytes(tokenBytes, validatedPolicy, expectedContext, nowSeconds)
// validatedPolicy is exactly policyResult.trust_bytes (PolicyTrustBytes), not parsed policy
// fully reverify its original bootstrap/envelope/JWKS bytes on every call
// frozen required verified OIDC claims only; never installed/runtime authority
verifyInstalledGithubOidc(tokenBytes, installedPolicyHandle, expectedContext)
// claims only, internal trusted clock, no network/acquisition
// expectedContext exact shape {run_id: canonical positive decimal string, run_attempt: integer1..1000}
authenticateActionsRuntime() // always throws Error('missing_dependency'), no argument inspection
```

The spec fixes `PolicyTrustBytes` as exactly three canonical-base64 strings containing the original bounded bootstrap/envelope/JWKS bytes. On every OIDC call, decode bounded copies and repeat the entire owner-policy signature/hash/epoch/schema/JWKS/lifetime verification with the current clock. Parsed/cached policy, full owner-policy result, accessor fields, `verified:true` and forged handles are rejected. The installed wrapper uses only privately stored original trust bytes attached to its fixed-loader handle; its public claims accessor exposes no trust bytes or marker. Passive supplied bootstrap validity never proves installed owner provenance. JWT `environment` binds `policy.protected_environment` (`workshop-staging-publish`); policy `environment` stays `staging`. No exported data grants upload capability.

## Concrete todo

- [ ] Independently review this Stage1A-only contract and exact four-file implementation allowlist; retain Stage0 source bytes and every CLI/workflow denial.
- [ ] After the coordinator releases the serialized tracking slot, synchronize this goal, plan/spec/canonical notes and concrete todo across Issue186/Project8 without overwriting current PG or other lane evidence; commit the checkpoint and pass full-SHA preflight before coordinator dispatch.
- [ ] After a passing synchronized gate and dispatch, add strict bounded trust-file/policy verification using built-in Node crypto and real local Ed25519 fixtures; commit and push the validated milestone.
- [ ] Add bounded RS256 GitHub OIDC byte verification and installed-policy wrapper with exact claim/time checks, plus unconditional missing_dependency runtime-bearer authentication; commit and push the validated milestone.
- [ ] Run new offline crypto/filesystem negative suites and unchanged Stage0 regressions, syntax, exact-scope and frozen-byte checks; obtain independent exact-SHA review with fixture-only evidence and every activation blocker retained.

## Task1: independent contract review and a real planning checkpoint

Files: this plan, spec, Stage1A record/task and additive operations note only.

- [ ] Review exact byte domain, Ed25519 backend, strict schema, bootstrap source, file/mount/cleanup rules, RS256 verification/claim lifetime, unsupported bearer and passive/installed type boundary against the spec.
- [ ] Verify actual draft diff is exactly the five declared documentation paths and that its ancestry starts at accepted Stage0 receipt `dde53d745f8422ce29d6e8b3d459f4a0b91ebd04`.
- [ ] Have the tracking owner preserve the immediately current PG and other lane index/detail evidence before synchronizing Stage1A. This docs-only tracking synchronization is authorized; it does not authorize implementation or provider operations.
- [ ] Commit the independently accepted, genuinely synchronized checkpoint; pin its full SHA and pass canonical preflight. Obtain independent exact-checkpoint acceptance and coordinator code-only dispatch. A draft preflight failure is blocking, not a waiver.

## Task2: offline owner-policy bytes and installed source boundary

Files: new `publisher_policy.mjs`, new `test_publisher_policy.mjs` only.

- [ ] Write red tests using `generateKeyPairSync('ed25519')`, standard SPKI/raw key conversion, signed exact payload bytes and an independently pinned fixture bootstrap digest. Keep all fixture key generation in the test file; no fixed root or production provisioning.
- [ ] Run `/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_policy.mjs`; require missing-module/API failure before implementation.
- [ ] Implement the spec's parser, canonical base64 checks and `crypto.verify(null, domainAndPayload, publicKey, signature)`. Test that alternate whitespace changes in signed payload fail without a new signature while unsigned envelope-byte changes fail the bootstrap digest check. Reject wrong key/domain/signature, altered payload, duplicate keys, unpaired surrogates, alternate encodings, excessive bounds, noninteger times, expired/future/rollback epoch and positive upload/runtime flags.
- [ ] Implement the fixed descriptor traversal, kernel mount-ID checks, bounded reads/identity rechecks, monotonic cancellation scope and exhaustive owned-descriptor cleanup. Keep lower-level metadata parsers testable as passive validators without any injection hook into `loadInstalledOwnerPolicy`.
- [ ] Test actual temp filesystem negatives: missing path, symlink final/intermediate, FIFO open cannot block, nonregular/multi-link/writable/wrong-owner or writable-mount inputs where the host supports the case. Exercise pure metadata parser branches with deterministic snapshots for unavailable privileged states; label those fixture-only. Never create `/etc/autodata` trust files or require mount/root provisioning. Test never-settling open/read/close, late-open/late-read/late-rejection and failed-close behavior through exported `OwnedTrustReadScope.trackOpen(promise)`, `.track(promise)` and `.finish()` with shortened integer budgets and scheduler tolerance; fake closable handles test resource ownership only. At the final cleanup cutoff require bounded `cleanup_failed`, no policy handle, retained late-handle ownership and no unhandled rejection. Require one active/quarantined installed scope at most, immediate denial of subsequent acquisition while quarantined, exactly one late close when safe, and no late parsing or success. Never claim that an uncancellable operation was terminated or that all work drained before this failed result. This class cannot mint installed-policy handles and `loadInstalledOwnerPolicy` accepts no scope/opener/clock override.
- [ ] Require ordinary missing trust and invalid signatures to perform zero environment-token reads, transport calls, SDK imports or child spawns. Require failed/deadline/cancelled filesystem cleanup to produce no handle and redact underlying values.
- [ ] Run the owner-policy suite and Node syntax check; review the two-file diff; commit `feat: add offline publisher owner-policy verification` and promptly push only after authorized dispatch and validation.

Example security regression shape (the test file defines the named local signing fixture helper):

```javascript
test('signed policy never authorizes upload', () => {
  const fixture = signedPolicyFixture({upload_enabled: true});
  assert.throws(() => verifyOwnerPolicyBytes(
    fixture.bootstrap, fixture.envelope, fixture.jwks, fixture.now
  ), {message: 'invalid_trust_input'});
});
```

## Task3: verified OIDC bytes with explicit runtime denial

Files: new `publisher_identity.mjs`, new `test_publisher_identity.mjs` only; existing Task2 files can receive only test-driven corrections within the same gate.

- [ ] Write red tests using actual RSA2048 and RSA4096 keys from `generateKeyPairSync`, projected public JWKs, strict normalized snapshot bytes signed into an Ed25519 fixture policy, and `crypto.sign('RSA-SHA256', signingInput, {key,padding:RSA_PKCS1_PADDING})`.
- [ ] Run the identity test file and retain missing-module/API failure; then implement the exact spec algorithm/header/JWKS/claims/time checks and imported strict parser.
- [ ] Verify valid fixtures at lifetime boundaries, passing exactly `policyResult.trust_bytes`. Require a positive signed JWT with `environment:"workshop-staging-publish"` while the policy product stage is `staging`; reject JWT `environment:"staging"`, another protected environment, missing or nonstring environment. Reject full-result/parsed-policy/accessor/extra-field substitutes for `PolicyTrustBytes`; mutate each raw trust component independently and recheck a previously valid record after policy/JWKS expiry to establish full revalidation. Verify valid fixtures at lifetime boundaries. Reject wrong signer, modulus/signature size, unknown/duplicate kid, malformed base64url, unsigned/HS256/PSS tokens, algorithm/key confusion, header URLs/crit, duplicate/unbounded JSON, unknown claims, array audience, issuer/audience/subject/owner/repository/environment/ref/event/workflow SHA mismatch, numeric/zero-padded run/attempt, previous attempt, expired/future/not-yet-valid or overlong tokens, stale snapshot, and missing jti. No unknown key fetch or claim-based key selection outside the signed snapshot.
- [ ] Recheck installed handle provenance and policy/JWKS expiry inside `verifyInstalledGithubOidc`; reject copied/forged/passive handles. Demonstrate `source_sha` is not an authenticated OIDC output and that a valid OIDC record cannot satisfy any upload runtime interface.
- [ ] Add `authenticateActionsRuntime` with its exact zero-inspection denial. Use hostile Proxy arguments and environment getters that throw on access: every call must throw `missing_dependency` without touching either. No callback/SDK/process/network seam exists.
- [ ] Run both new suites and syntax checks; review exact scope; commit `feat: add offline GitHub OIDC verification with runtime denial` and promptly push only after authorized dispatch and validation.

Example denial regression:

```javascript
test('runtime authenticator cannot inspect or accept input', () => {
  const hostile = new Proxy({}, {get() { throw Error('argument inspected'); }});
  assert.throws(() => authenticateActionsRuntime(hostile), {message: 'missing_dependency'});
});
```

## Task4: exact offline verification and independent handoff

- [ ] Verify reviewed Node binary SHA256 before executing it. Run both new Node test files together and `--check` for all four new files.
- [ ] Run unchanged Stage0 Node artifact suite from repository root: `/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs`.
- [ ] Run unchanged Python suites from `infra/deploy/gce`: `python3 -m unittest test_publisher_adapters -q` and `python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q`.
- [ ] Compare all preexisting implementation blobs against the accepted Stage0 receipt, including `publisher_adapters.py`, `publisher_artifact.mjs`, toolkit package/lock, `cloud-ops.py` and full `.github/workflows/release-workshop.yml`. No existing test may be edited to accommodate new behavior. Require zero changed existing implementation paths and no new path beyond the four-file allowlist.
- [ ] Run `git diff --check`, strict-parse the record/task, repeat pinned synchronized gate preflight for the eventual authorized implementation checkpoint, and record actual test counts/SHA without copying Stage0 counts.
- [ ] Update only current Stage1A documentation with fixture-only evidence and exact verified SHA. Request independent exact-SHA review; no activation, root installation, positive bearer or provider acceptance claim follows. Any installer/factory/worker/runtime design is a separate future gate.

## Current synchronized checkpoint and implementation block

Corrected draft `9ff1a36fb5fc6837a8699dabea69287316847a9d` passed independent review. The tracking owner synchronized the offline-only goal/todo with Issue186/Project8 after staging boot released its slot. The prior complete index and twelve boot/PG offline/Stage0/earlier details and pins are preserved verbatim/hash in `docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust-evidence.json` and six read-back preservation comments. The Issue body is unchanged. This pass performs only documentation JSON/scope/diff checks and canonical full-SHA preflight; new modules do not exist and Stage0 suites are not claimed rerun. SDK installation/import, credential acquisition, provider APIs, workflow changes, upload and cloud activation remain unauthorized. Independent exact synchronized-checkpoint review and root code-only dispatch are required after committed preflight.


Synchronization readback verified 2026-11-04T04:28:01.132963+00:00: https://github.com/lucronn/autodata/issues/186#issuecomment-6622550358. Prior Project index SHA256 `831c9c512f574c378ca88b9129fa2305a549a9a7062f3a67afecc7c865d1882e`; synchronized Project index SHA256 `069a03c4f9456f649c7b12a51d5f393ecc5d1f04b92e092121ab43d72e708b70`. Commit/push, full-SHA preflight and exact pin receipt follow. Actual owner trust provisioning and every activation blocker remain absent.


Exact synchronized checkpoint `38c6ffe420498fb3be5927df58dba6051f2df6f7` committed/pushed; full-SHA preflight exit0 returned `{"status":"synchronized","errors":[]}`. Exact pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622560758 and final Project index read back 2026-11-04T04:28:33.605452+00:00; index SHA256 `b37bb75e92fbb2bf448154464782067a88b2c97d2a26e376ed2fa856c95f4ec3`. The serialized tracking slot is released. Independent exact-checkpoint review and fresh root code-only dispatch remain required. No implementation, SDK import, cloud operation or activation occurred.
