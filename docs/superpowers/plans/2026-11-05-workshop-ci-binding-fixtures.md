# Task65 Workshop CI binding and deterministic installer fixture plan

**Synchronized planning-only checkpoint.** Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.

Issue: https://github.com/lucronn/autodata/issues/186; Project: https://github.com/users/lucronn/projects/8; item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4.

Plan/spec/task/standalone and nested record contain the same literal goal, six todos, eight gate paths and two future implementation paths. Execution policy is Sol6.1 medium Fast, no fallback, as retained from queue. Root owns tracking and future dispatch. Current implementation allowlist is empty; every authority false; credits0; release unverified.

The exact actual checkpoint SHA/tree will be externally sealed at `/home/corp/autodata-evidence/task65-gate-draft/CHECKPOINT.json` after commit; null checkpoint/base fields avoid a self-hash. Independent checkpoint review and explicit two-path dispatch are mandatory after both exact-checkpoint preflights.

## Approved external proposal adopted as the technical plan

Proposal SHA256 e3e2f2f514684814ee865c7753f16b845028f6c7fdfc012e1d060595c35ed885; independent proposal-only PASS SHA256 139f81c24546dcb41e2276d4e6173170b1d178502503ef8cbcb90e88017f661d. No revised implementation exists.

## Decision and exact implementation scope

Use one fresh synchronized correction gate with exactly two implementation paths and two independently reviewable implementation commits:

1. `docs/agents/tasks/2026-11-03-production-release/r6-release.json`: replace exactly one ASCII hash value in `product_evidence.ci_profile.workflow_sha256`, from `b7dc37359faea4cdaff29ce7b0460d2f5d289ad7d3ae4c2c0c788a8992556e4d` to `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418`. Preserve every other byte and field.
2. `infra/deploy/gce/test_host_install.py`: hold the original temporary manifest inode open through replacement, installer return and assertions, making the existing replacement-denial fixture deterministic across Linux filesystems.

Preserve `scripts/dev/test_workshop_browser_smoke.py`, `scripts/dev/test_release_acceptance.py`, `scripts/dev/release_acceptance.py`, the entire workflow and every production GCE helper/wrapper byte-for-byte. No current DTO-job digest/helper/test changes are proposed. This restores the existing independent whole-workflow binding and fail-closed trusted-loader contract rather than changing that contract.

Goal: Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.

One explicitly combined gate is sufficient: both bounded corrections unblock Task64 CI, have no new runtime behavior and carry separate test cycles/commits. The canonical gate does not require a separate record per independent correction. Task64's existing two-path scope authorizes neither path here; a fresh synchronized exact-base gate is mandatory. Any third implementation path or behavioral change requires gate amendment before work.

## Source, verified diagnosis and historical preservation

Pinned source: Task64 PR294 source `c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b`, tree `2119fb9d394994472b20243cfbbebe0cbba7ae25`. Its checkpoint parent is `f6b7bee50e9c3dfab93d8fa2cb069c85738c926f`; predecessor Task62 source is `4fe83b29b86411d104b1edb203e9b26fde67ad02`.

| Source path | Exact SHA256 |
|---|---|
| `.github/workflows/autonomous-verification.yml` | `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418` |
| `docs/agents/tasks/2026-11-03-production-release/r6-release.json` | `0b7a892bf0ea51d5a3197dce795d2be451bd7535809c9c82c8bbd5fe5bdecc52` |
| `infra/deploy/gce/test_host_install.py` | `89285c85ca6c99704629557164de5a27fbcc0d47443bdc92d5082b75071e87f4` |
| `infra/deploy/gce/host_install.py` | `6b2e25e6a6861dd292d15816e1f3fb926d94aa2f2a416fd9c1ca463fad5fa6f1` |
| `scripts/dev/test_workshop_browser_smoke.py` | `8b86b5aaba6ddc4766fb261b68f0ebaf55ba8b03cc2fdcc66e0606b2f5a59ee6` |
| `scripts/dev/test_repository_governance.py` | `ba42d12411b746e93b32052cb6f1d586b33b4bc3ea7577d53a13adafee295822` |

Source push41981562383 and actual PR41981617643 fail the main job at the unchanged `DTOWorkflowBindingTests.test_dto_job_matches_shared_contract_and_disabled_r6_hash`, line1259. It compares old R6 `b7dc...` against current workflow `b9cc...`. GCE and live Compose are skipped, not covered. Those saved status snapshots were interim and remain retained as historical evidence. Root terminal readback confirms both Task64 runs failed overall; DTO and R3 jobs completed successfully. These independent job successes do not cover the skipped GCE/live Compose steps or confer acceptance credit.

Crucially, unchanged `release_acceptance.load_trusted`, lines3654–3659, requires the pinned task's whole-workflow hash to match workflow bytes at the same trusted base. Unchanged `TrustedBoundaryTests` also depend on that contract. Independent review red evidence at `/home/corp/autodata-evidence/task65-ci-binding-review/release-acceptance-red.log` reports7 tests, failures2/errors4, including `workflow_hash_mismatch` and CLI exit2 instead of expected plan0/disabled validate3. Revision1's browser-only proposal would leave this regression. Revision2 follows prior single-field rebind commit `209aa420b391dc81275b0178fd8988a61f591cb7`, which established the old `b7dc...` pin; earlier correction `8e661fdc38ce944d97a01d087b997439f36d4f91` provides the same exact-field preservation precedent.

The frozen GCE wrapper independently ran274 tests/failure1: `InstallTests.test_temporary_tree_replacement_before_promotion_denied`, expected6/got3. Reviewer `/home/corp/autodata-evidence/task64-code-independent-review/installer-diagnostic.log` records identical original/replacement dev/inode `[66315,3722488]` in iteration0 and `[66315,3722490]` thereafter. The copied file descriptor had closed, so unlink/recreate reused an inode. Verification still denies injected bytes; cleanup identifies the reused inode and succeeds, producing3. This is a fixture identity ambiguity, not proof of promotion. Builder repeat100/0 failures in another temporary environment is not exact-wrapper counterevidence.

Archive the historical old digest, exact source/task SHA/blob, raw old bytes, original CI failures and prior verified receipts in **new** Task65 plan/spec/verification/evidence notes; do not rewrite historical Task64/R6 verification records. The old R6 file is preserved externally at `archive/revision1/r6-release-at-task64.json`. Historical evidence remains pinned to its old source and is never relabeled as new CI/acceptance evidence. The new R6 pin describes only current disabled-profile integrity.

## Coordinator-only gate paths and tracking

Proposed eight gate paths:

- `docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md`
- `docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json`
- `docs/agents/records/2026-11-05-workshop-ci-binding-fixtures.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json`
- `docs/verification/2026-11-05-workshop-ci-binding-fixtures.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/operations/workshop-gcp.md`
- `docs/github/operating-model.md`

These are coordinator planning/evidence scope, separate from the exact two-path implementation scope. Do not alter R6 JSON while creating the checkpoint: the R6 field change itself is implementation and follows a passing gate.

Use existing Issue186 / Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Append this task and canonical notes preserving prior task objects/root values/history and Issue/Project content; save before/after readbacks. Synchronize literal goal, six todos below, eight/two-path scopes, source SHA/tree, old/new digest, exact output R6 metadata and canonical references in plan/spec/task/standalone/nested record and Issue/Project index. Preserve existing execution model/tier/profile values under coordinator policy. Commit/push the planning-only checkpoint. Seal its actual SHA/tree externally, pass both standalone/nested preflights there with errors=[], obtain independent checkpoint review and explicit two-path dispatch. Never encode a future checkpoint self-hash in predecessor bytes.

Literal todo:

- [ ] Independently review Task64 exact source, unchanged whole-workflow trusted-loader/browser contracts, red receipts and the two-path correction; preserve historical evidence and every authority/credit limit.
- [ ] Synchronize this goal, six todos, eight gate paths, two implementation paths, exact old/new R6 metadata and canonical refs in Issue186/Project8; commit/push the checkpoint, seal its actual SHA/tree, pass both exact-base preflights and obtain independent checkpoint review before dispatch.
- [ ] Retain original browser-binding and trusted-boundary failures; replace only the single R6 ASCII workflow hash with the exact reviewed current-workflow digest, prove every other R6 byte/field unchanged and expected output hash/blob/length, run focused existing binding/trusted-boundary/disabled CLI tests, and commit/push the independently reviewable one-field milestone.
- [ ] Retain exact-wrapper inode-reuse red evidence; pin the temporary manifest with an open descriptor through installer cleanup, assert distinct identities and existing6/no-commit/preserved-injected-file outcomes, run focused repeats on disk-backed/tmpfs storage and host-install verification, then commit/push the fixture-only milestone.
- [ ] Run complete release-acceptance/browser/developer/governance checks and required-mode GCE under the unchanged UID/GID1000 wrapper, check exact two-path/protected integrity at final source, obtain independent exact-source review and retain fresh source-push plus actual-PR receipts for all three jobs/GCE/live Compose.
- [ ] Append honest exact-source local/CI results and retain the prior R6 digest/Task64 failures as historical evidence; preserve all disabled profiles, trusted-loader boundaries, owner/staging/activation/payment/browser/provider/DNS blockers, credits0 and every release authority false; perform no merge/deployment/publication.

## Commit1: exact single-field R6 rebind

No serialization or formatting rewrite. Read raw source bytes, assert exactly one occurrence of old64-byte ASCII digest, replace it once with new64-byte ASCII digest, and assert JSON structural delta is exactly `product_evidence.ci_profile.workflow_sha256`. Preserve key order/whitespace/trailing LF/mode and every other byte. Expected file remains **8727 bytes**, mode100644, SHA256 **`09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7`**, Git blob **`132307774cb0baabb1f320b0e2ea7bde3aae9526`**. Original Git blob is `789c9e202e9cf9199853c54af9f09c7923cd00a4`.

Expected byte operation only:

```python
old = b'b7dc37359faea4cdaff29ce7b0460d2f5d289ad7d3ae4c2c0c788a8992556e4d'
new = b'b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418'
assert original.count(old) == 1
replacement = original.replace(old, new, 1)
assert len(replacement) == len(original) == 8727
assert hashlib.sha256(replacement).hexdigest() == '09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7'
```

Explicitly preserve `ci_profile.enabled=false`, `dto_upload_required=true`, all binding/slot/report profiles disabled, `supervisor_profiles=[]`, `enabled_tiers=[]`, `assembler_sha256=null`, expected slot counts, policy/evaluator refs/hashes, pre-implementation record, execution and dispatch fields. This correction enables no profile/tier/trust identity, collector or evidence acceptance. The workflow must remain exactly SHA256 `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418`; no dynamic expected digest or loader weakening.

For independent integrity inspection, the unchanged DTO byte block from unique `  workshop-dto-browser:\n` through immediately before `  r3-preparation-unit:\n` remains7477 bytes/SHA256 `0f9dff0d7f0bea96b098066231b2e53d97376c70484d921e6022e2e9e2b067a8`. This is an external preservation invariant, **not a new browser-test edit or replacement for the whole-workflow binding**.

Red: rerun unchanged `DTOWorkflowBindingTests` and all seven `TrustedBoundaryTests` at exact pre-implementation source; retain expected hash-mismatch/CLI failures. Green: same tests unchanged at committed new trusted base, disabled CLI plan exit0/planned and validate exit3/unavailable with all verification/deployment flags false and derived counts0. The trusted loader reads Git-pinned source, so uncommitted working-tree changes alone cannot provide green trusted-base proof. Commit the one-field milestone after pure byte/diff/browser checks, then run trusted-boundary tests at that exact committed checkout before push. The unchanged test module obtains TRUSTED_BASE from `git rev-parse HEAD`; the new commit must be HEAD in its assigned checkout. No external base override or test edit is needed. Require full release-acceptance and browser modules plus their existing rejection/promotion mutations; existing workflow-hash mismatch negative tests must still reject wrong digests. No synthetic profile can be promoted by success.

## Commit2: deterministic pre-promotion inode replacement


Root cause: `Transaction.build` records `(st_dev,st_ino)` and closes copied file descriptors. The fixture unlinks `release.json` and immediately recreates it. A disk filesystem may reuse its now-free inode. `Transaction.verify` still denies injected bytes, but cleanup recognizes the reused identity, removes it safely and returns code3; the test intended a genuinely replaced inode which cleanup must preserve and report code6.

Modify only `test_temporary_tree_replacement_before_promotion_denied`. Immediately before unlink, open the original manifest read-only and register its close with `self.addCleanup`. The open reference keeps that inode allocated until test cleanup after installer return and assertions. Do not hold a hard link (would change nlink), mock stat/identity/cleanup, change TMPDIR/workflow, add sleeps/retries, relax expected6 to3/nonzero or change the production helper. Keep current chmod sequence, injected payload and existing outcome assertions.

Concrete callback delta, with `replacement_identities=[]` initialized before the callback:

```python
original = base / 'release.json'
retained = original.open('rb')
self.addCleanup(retained.close)
before = os.fstat(retained.fileno())
original.unlink()
original.write_bytes(b'injected')
original.chmod(0o600)
after = original.stat()
replacement_identities.append(((before.st_dev, before.st_ino),
                               (after.st_dev, after.st_ino)))
base.chmod(0o500)
```

After `code, receipt = self.install()` assert `len(replacement_identities)==1` and that its two identity tuples differ. Retain `code==6`, `release_material_committed is False`, final release absent, and injected temporary `release.json` content preserved. Add explicit `failure_code=='recovery_incomplete'` and `commit_state=='incomplete'` assertions to bind intended cleanup refusal. The descriptor must remain live through these assertions; unittest cleanup closes it even if an assertion fails. Opening only inside a callback-local with block is insufficient if it closes before the installer performs cleanup.

No neighboring inbox-race change is needed: original source descriptors are already retained by the production input pins. No new root test count is required for this repair. Full GCE suite remains274 tests unless separately approved additions are explicit in final inventory.

Red/green: retain exact source original fixture failure and reviewer dev/inode proof; run original fixture under the exact frozen wrapper/disk-backed temp root, capturing filesystem and identity. Apply the scoped change only after gate. Run the fixed focused fixture100 times on the same disk-backed root and100 times with verified tmpfs temp storage as supplemental portability checks; require0 failures and actual distinct identities, no retry-until-pass. Run entire host-install module, then entire required-mode GCE suite using the byte-identical Task64 wrapper and its actual runner-temp-derived TMPDIR. Fixed fixture must also pass the ordinary developer test environment. Do not replace disk-backed mandatory coverage with tmpfs success.

## Final verification and CI receipts

- Final checkpoint→implementation delta is exactly the two allowed files. Prove the complete R6 delta is one64-byte field replacement and exact length/hash/blob above. Coordinator gate/evidence edits remain separately attributable. Run `git diff --check` and inspect full diff.
- Protect the entire workflow, browser test/producer, release loader/tests, GCE production helper/wrapper, governance tests, policy, application, SQL/Compose and every other non-allowlisted implementation path. Compare protected bytes to exact source/checkpoint, not a moving branch. Preserve old history and task/root fields except explicit new Task65 append.
- Run existing DTO binding/all browser tests, all seven trusted-boundary tests/full release-acceptance module, governance and full developer-adapter discovery, complete host-install module and complete required-mode GCE. Retain raw command/exit/stdout/stderr, named inventories/skips/duration, exact SHA/tree, and UID/GID/groups/executable/temp-filesystem readbacks. Overlapping suite counts are not additive accepted cases.
- Complete GCE runs the unchanged frozen script digest `5adc3b0b3b56c75f8df1faed2dd461a71ac37c3622b973af185baf99941e3502`, sanitized env, numeric actual/effective UID/GID1000, cleared groups, required Compose flag1, fixed tools/version preflight and complete discovery. Preserve Unicode/transport/protected wrapper requirements. Supplemental tmpfs success cannot replace mandatory exact disk-root wrapper evidence.
- Obtain independent final exact-source review. Retain fresh source-push and actual pull_request event receipts: source SHA/tree; actual checkout SHA/tree and exact workflow bytes/hash; event/ref/head/base; run/attempt/job IDs; terminal all-three-job conclusions; GCE named step/test inventory/skips/exit; live Compose smoke; and DTO artifact identities. Inspect any PR checkout tree delta. Manual dispatch is supplemental; source success alone does not prove actual PR success.
- New green receipts do not rewrite Task64 historical failures/skipped GCE. Preserve previous R6 digest/source/raw bytes, previous receipts and old limits under new evidence notes. New candidate identity is explicit. Local fixtures remain local and DTO120 remains inventory, with observer/containment/trace-admission blockers and accepted-case credit0.
- Preserve all owner/host/immutable-generation/activation/staging/restore/provider/identity/payment/browser/DNS boundaries, Task61 actual-PR evidence, R6 disabled profiles and trusted-loader rejection behavior. accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified; every acceptance/merge/deploy/publication authority false.

## Risks and stop conditions

This is a mechanical disabled-profile integrity rebind to an independently pinned unchanged workflow, not provenance or acceptance promotion. Any workflow modification changes the required target and invalidates the sealed metadata; stop and re-review the exact bytes instead of deriving a replacement target dynamically. Any R6 second-field/formatting/mode delta fails scope checks. Do not repeat the rejected browser-only solution: both existing browser equality and trusted loader remain authoritative unchanged checks.

The open-descriptor fixture relies on normal Linux inode lifetime semantics and tests genuine replacement. If distinct inode identity cannot be demonstrated, code6 is absent, injected material is promoted, required dependencies fail or wrapper execution differs, stop with raw evidence. Do not broaden accepted codes, skip/retry until success, alter production cleanup or force workflow TMPDIR to tmpfs. Any extra path, authority, dependency or runtime behavior requires prior gate amendment.

## Historical terminal CI clarification from root tracking

{
  "task64_source_sha": "c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b",
  "task64_source_tree": "2119fb9d394994472b20243cfbbebe0cbba7ae25",
  "task64_source_push_run": 41981562383,
  "task64_actual_pr_run": 41981617643,
  "task64_main_result": "failure at unchanged browser whole-workflow/R6 equality; GCE and live Compose skipped",
  "task64_r3_dto_result": "success, per root tracking readback; no acceptance credit",
  "task64_required_gce_local": "274 tests, one failure: temporary-tree replacement expected6/got3; same dev/inode reused. Original failure retained.",
  "task64_original_browser_red": "/home/corp/autodata-evidence/task65-ci-binding-review/dto-red.log",
  "task64_original_trusted_boundary_red": "/home/corp/autodata-evidence/task65-ci-binding-review/release-acceptance-red.log; seven tests failures2/errors4, workflow_hash_mismatch and CLI2 instead of0/3",
  "task64_inode_diagnostic": "/home/corp/autodata-evidence/task64-code-independent-review/installer-diagnostic.log",
  "r6_original_raw_archive": "/home/corp/autodata-evidence/task65-ci-binding-design/archive/revision1/r6-release-at-task64.json",
  "task62_source_sha": "4fe83b29b86411d104b1edb203e9b26fde67ad02",
  "task62_supplemental_manual_run": 41979473005,
  "task62_supplemental_manual_result": "success all three jobs including live Compose; supplemental only, no source/PR GCE substitute",
  "task61_actual_pr": "41977907070 success at its own source with qualifications retained; no inherited current-source CI green",
  "inherited_ci_green": false,
  "acceptance_credit": 0
}

## Canonical synchronized record

```json
{
  "goal": "Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.",
  "plan_ref": "docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json",
    "docs/verification/2026-11-05-workshop-ci-binding-fixtures.md",
    "docs/operations/workshop-gcp.md",
    "docs/github/operating-model.md"
  ],
  "todo": [
    "Independently review Task64 exact source, unchanged whole-workflow trusted-loader/browser contracts, red receipts and the two-path correction; preserve historical evidence and every authority/credit limit.",
    "Synchronize this goal, six todos, eight gate paths, two implementation paths, exact old/new R6 metadata and canonical refs in Issue186/Project8; commit/push the checkpoint, seal its actual SHA/tree, pass both exact-base preflights and obtain independent checkpoint review before dispatch.",
    "Retain original browser-binding and trusted-boundary failures; replace only the single R6 ASCII workflow hash with the exact reviewed current-workflow digest, prove every other R6 byte/field unchanged and expected output hash/blob/length, run focused existing binding/trusted-boundary/disabled CLI tests, and commit/push the independently reviewable one-field milestone.",
    "Retain exact-wrapper inode-reuse red evidence; pin the temporary manifest with an open descriptor through installer cleanup, assert distinct identities and existing6/no-commit/preserved-injected-file outcomes, run focused repeats on disk-backed/tmpfs storage and host-install verification, then commit/push the fixture-only milestone.",
    "Run complete release-acceptance/browser/developer/governance checks and required-mode GCE under the unchanged UID/GID1000 wrapper, check exact two-path/protected integrity at final source, obtain independent exact-source review and retain fresh source-push plus actual-PR receipts for all three jobs/GCE/live Compose.",
    "Append honest exact-source local/CI results and retain the prior R6 digest/Task64 failures as historical evidence; preserve all disabled profiles, trusted-loader boundaries, owner/staging/activation/payment/browser/provider/DNS blockers, credits0 and every release authority false; perform no merge/deployment/publication."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T06:47:55Z",
  "tracking_status": "synchronized",
  "current_implementation_allowlist": [],
  "authorities": {
    "implementation": false,
    "implementation_dispatch": false,
    "provider": false,
    "runtime": false,
    "host": false,
    "host_execution": false,
    "docker": false,
    "network": false,
    "cloud": false,
    "dns": false,
    "capture": false,
    "profile_activation": false,
    "acceptance": false,
    "fixture_execution": false,
    "image_build_pull_install": false,
    "service_start": false,
    "payment": false,
    "account_mutation": false,
    "staging": false,
    "release": false,
    "merge": false,
    "deployment": false,
    "cutover": false,
    "secrets": false,
    "github_write": false,
    "code_approval": false,
    "ci_success": false,
    "merchant_enablement": false,
    "manifest_injection": false,
    "artifact_admission": false,
    "owner_approval": false,
    "stripe_test_acceptance": false,
    "live_sales": false,
    "code_import": false,
    "ci_execution": false,
    "capture_admission": false,
    "fixture_api21": false,
    "fixture_dto120": false,
    "final180": false,
    "current_source_browser_acceptance": false,
    "owner_tax_decision": false,
    "firebase_enrollment": false,
    "stripe_test_enrollment": false,
    "supervisor_timing_change": false,
    "merge_to_protected_branch": false,
    "hot_reload": false,
    "purchase_enablement": false,
    "production_config_delivery": false,
    "dns_change": false,
    "provider_secret_delivery": false,
    "dispatch": false,
    "commit": false,
    "push": false,
    "config_generation": false,
    "install": false,
    "drain": false,
    "restart": false,
    "rollback": false,
    "rollout": false,
    "public_ingress_resume": false,
    "publication": false,
    "runner_fixture_setup": false,
    "ci_filter_change": false
  },
  "accepted_case_credit": 0,
  "accepted_new_case_credit": 0,
  "verified_case_ids": [],
  "release_state": "unverified",
  "tracking_sync": {
    "status": "synchronized",
    "writer": "root",
    "issue_comment_ref": "https://github.com/lucronn/autodata/issues/186#issuecomment-6651645549",
    "project_ref": "https://github.com/users/lucronn/projects/8",
    "project_item_id": "PVTI_lAHOCSJ8cc4BiQ2BzhFocs4",
    "before_snapshot_path": "/home/corp/autodata-evidence/task65-ci-binding-design/TRACKING-BEFORE-GOAL-REFINEMENT.json",
    "before_snapshot_sha256": "80a849d14dce06acf1b25e3f5dbc00d96f75ddda83f3b36cc379923be35469ff",
    "after_snapshot_path": "/home/corp/autodata-evidence/task65-ci-binding-design/TRACKING-AFTER-GOAL-REFINEMENT.json",
    "after_snapshot_sha256": "5af5a28591352582de1b0f8c8327675c0aae7295bbda41de31b36f3e4257cbba",
    "preservation_path": "/home/corp/autodata-evidence/task65-ci-binding-design/TRACKING-GOAL-REFINEMENT-VERIFY.json",
    "preservation_sha256": "3ea0520b796d4ca873878de1848f0e4dc423a00176b8e2922701c0ffbe7bf7b9",
    "verified_at": "2026-11-05T06:46:36.997642+00:00",
    "preservation_checks": 9,
    "project_source_sha256": "9243b8b20b29679bf55165b6d39a830b7abcb5ffb44c71584e38a211e0d805cc",
    "issue_body_sha256": "927b46ef47b1dbf5b117273e3d3f5c0e6d9f23b722a5245869eb5323b96c4f25",
    "comment_body_sha256": "3045a91d757b1a233aa6084c41b915f8f8e7576e2ea9daf16642f1f4ca77e83e",
    "prior_tracking_preservation_path": "/home/corp/autodata-evidence/task65-ci-binding-design/TRACKING-VERIFY.json",
    "prior_tracking_preservation_sha256": "b300018d8df3772104fc7c895785d79c9fca1feed71541bebf9b2f4e69165996"
  },
  "source_candidate_sha": "c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b",
  "source_candidate_tree": "2119fb9d394994472b20243cfbbebe0cbba7ae25",
  "allowed_gate_document_paths": [
    "docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md",
    "docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json",
    "docs/agents/records/2026-11-05-workshop-ci-binding-fixtures.json",
    "docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json",
    "docs/verification/2026-11-05-workshop-ci-binding-fixtures.md",
    "docs/agents/tasks/2026-11-03-production-release/queue.json",
    "docs/operations/workshop-gcp.md",
    "docs/github/operating-model.md"
  ],
  "allowed_implementation_paths": [
    "docs/agents/tasks/2026-11-03-production-release/r6-release.json",
    "infra/deploy/gce/test_host_install.py"
  ],
  "r6_rebind": {
    "path": "docs/agents/tasks/2026-11-03-production-release/r6-release.json",
    "field": "product_evidence.ci_profile.workflow_sha256",
    "old_workflow_sha256": "b7dc37359faea4cdaff29ce7b0460d2f5d289ad7d3ae4c2c0c788a8992556e4d",
    "new_workflow_sha256": "b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418",
    "original_sha256": "0b7a892bf0ea51d5a3197dce795d2be451bd7535809c9c82c8bbd5fe5bdecc52",
    "original_git_blob": "789c9e202e9cf9199853c54af9f09c7923cd00a4",
    "expected_sha256": "09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7",
    "expected_git_blob": "132307774cb0baabb1f320b0e2ea7bde3aae9526",
    "bytes": 8727,
    "mode": "100644",
    "byte_operation": "Exactly one old64-byte ASCII hash occurrence replaced once; every other byte/field unchanged. No JSON serialization. R6 remains byte-identical during planning."
  },
  "reviewed_gce_script_sha256": "5adc3b0b3b56c75f8df1faed2dd461a71ac37c3622b973af185baf99941e3502",
  "historical_evidence": {
    "task64_source_sha": "c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b",
    "task64_source_tree": "2119fb9d394994472b20243cfbbebe0cbba7ae25",
    "task64_source_push_run": 41981562383,
    "task64_actual_pr_run": 41981617643,
    "task64_main_result": "failure at unchanged browser whole-workflow/R6 equality; GCE and live Compose skipped",
    "task64_r3_dto_result": "success, per root tracking readback; no acceptance credit",
    "task64_required_gce_local": "274 tests, one failure: temporary-tree replacement expected6/got3; same dev/inode reused. Original failure retained.",
    "task64_original_browser_red": "/home/corp/autodata-evidence/task65-ci-binding-review/dto-red.log",
    "task64_original_trusted_boundary_red": "/home/corp/autodata-evidence/task65-ci-binding-review/release-acceptance-red.log; seven tests failures2/errors4, workflow_hash_mismatch and CLI2 instead of0/3",
    "task64_inode_diagnostic": "/home/corp/autodata-evidence/task64-code-independent-review/installer-diagnostic.log",
    "r6_original_raw_archive": "/home/corp/autodata-evidence/task65-ci-binding-design/archive/revision1/r6-release-at-task64.json",
    "task62_source_sha": "4fe83b29b86411d104b1edb203e9b26fde67ad02",
    "task62_supplemental_manual_run": 41979473005,
    "task62_supplemental_manual_result": "success all three jobs including live Compose; supplemental only, no source/PR GCE substitute",
    "task61_actual_pr": "41977907070 success at its own source with qualifications retained; no inherited current-source CI green",
    "inherited_ci_green": false,
    "acceptance_credit": 0
  }
}
```
