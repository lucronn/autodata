# Task65 planning checkpoint verification and historical evidence

Goal: Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.

Synchronized planning checkpoint; no implementation tests or current-source CI success claimed. All authorities false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified.

Source c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b / tree 2119fb9d394994472b20243cfbbebe0cbba7ae25. Canonical plan: `docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md`; spec: `docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json`; record: `docs/agents/records/2026-11-05-workshop-ci-binding-fixtures.json`. Tracking https://github.com/lucronn/autodata/issues/186#issuecomment-6651645549 and https://github.com/users/lucronn/projects/8.

## R6 original and expected future metadata

```json
{
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
}
```

Original raw bytes remain at the external archive above and the unchanged source R6 file; planning must not modify them. New expected metadata is a future integrity correction, with no acceptance promotion.

## Historical receipts retained at their own sources

```json
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
```

## Todo

- [ ] Independently review Task64 exact source, unchanged whole-workflow trusted-loader/browser contracts, red receipts and the two-path correction; preserve historical evidence and every authority/credit limit.
- [ ] Synchronize this goal, six todos, eight gate paths, two implementation paths, exact old/new R6 metadata and canonical refs in Issue186/Project8; commit/push the checkpoint, seal its actual SHA/tree, pass both exact-base preflights and obtain independent checkpoint review before dispatch.
- [ ] Retain original browser-binding and trusted-boundary failures; replace only the single R6 ASCII workflow hash with the exact reviewed current-workflow digest, prove every other R6 byte/field unchanged and expected output hash/blob/length, run focused existing binding/trusted-boundary/disabled CLI tests, and commit/push the independently reviewable one-field milestone.
- [ ] Retain exact-wrapper inode-reuse red evidence; pin the temporary manifest with an open descriptor through installer cleanup, assert distinct identities and existing6/no-commit/preserved-injected-file outcomes, run focused repeats on disk-backed/tmpfs storage and host-install verification, then commit/push the fixture-only milestone.
- [ ] Run complete release-acceptance/browser/developer/governance checks and required-mode GCE under the unchanged UID/GID1000 wrapper, check exact two-path/protected integrity at final source, obtain independent exact-source review and retain fresh source-push plus actual-PR receipts for all three jobs/GCE/live Compose.
- [ ] Append honest exact-source local/CI results and retain the prior R6 digest/Task64 failures as historical evidence; preserve all disabled profiles, trusted-loader boundaries, owner/staging/activation/payment/browser/provider/DNS blockers, credits0 and every release authority false; perform no merge/deployment/publication.

## Required candidate evidence after separate dispatch

- Retain unchanged browser-binding/all seven TrustedBoundaryTests red at pre-implementation source; expected CLI hash failures are historical.
- Green unchanged focused binding/trusted-boundary/disabled CLI tests at new committed HEAD; plan0/planned, validate3/unavailable, derived counts0, all flags false. Full browser/release-acceptance modules plus rejection/promotion mutations required.
- 100 fixed focused repeats each on mandatory disk-backed root and verified tmpfs supplemental; zero failures and actual distinct identities; no retry-until-pass.
- Complete host-install module, full developer/governance checks and complete required-mode274-test GCE under byte-identical wrapper; numeric actual/effective UID/GID1000, cleared groups, sanitized env, runner-temp-derived disk TMPDIR, required Compose1, absolute executable/version/temp ownership readbacks.
- Exact two-path implementation delta and protected bytes; R6 single field/hash/blob/length/mode checked; git diff --check and full diff inspection.
- Independent exact-source review and fresh source-push plus actual pull_request checkout SHA/tree/workflow/event/ref/job terminal all-three-job receipts; named GCE inventory/skips/exit, live Compose and DTO artifact identities. Manual dispatch is supplemental.

Checkpoint verification/seal will be recorded externally at `/home/corp/autodata-evidence/task65-gate-draft/REPORT.json` and `CHECKPOINT.json`, with actual SHA/tree, exact branch/remote/worktree, clean status, both machine preflight outputs, schema/governance results, and protected-byte/queue preservation checks. This file cannot claim those future results or encode its own commit. Independent checkpoint review and explicit implementation dispatch remain pending.
