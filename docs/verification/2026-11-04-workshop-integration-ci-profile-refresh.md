# Disabled R6 binding verification contract

Canonical planning checkpoint. Goal: Rebind the disabled R6 CI profile to the exact reviewed integrated workflow without enabling acceptance or release authority.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Literal tracking and external proposal review have been measured as recorded below. Exact committed-checkpoint preflight/review remain pending. No corrected commit, repaired test pass or normal-CI success is claimed. Credit0 and false authorities remain.

1. At exact checkpoint B, read standalone record and task.pre_implementation from git objects. Invoke scripts.autonomy.pre_implementation.validate_record for each with repository root, B, and .autodata-autonomy-policy.json loaded at B; retain exact inputs and two errors=[] outputs. Confirm tracking live-readback receipts and independent exact-B review separately: the validator cannot prove GitHub truth. All six checkpoint paths and no implementation changes must exist at B.
2. After explicit dispatch, retain an isolated, clean exact-B baseline showing the seven original synthetic failures (or attach the already pinned exact-e3 reproduction without pretending B was executed). Avoid services/browser/provider execution. After correction, verify source R6 bytes differ only by one occurrence of the declared old hash replaced with the declared new hash; require exact resulting SHA256 240aad0a76f22e46ff37c26f76b191a5af810a87c33da28a2e73a3b9ce8bd35d and blob 3acd5de4b0b358b854a5ee58559d805317adcb6b. Confirm workflow SHA256 99b68b40c7bcad1647bd0bf22f37aa4381c156f1c4f37bd4424454c659b38a89 and all other implementation blobs equal sourcee3. Structural diff must contain only product_evidence.ci_profile.workflow_sha256, leaving every other profile/task field unchanged.
3. At exact corrected candidate C, with C as test TRUSTED_BASE, run from scripts/dev: python -m unittest -v <the seven IDs below>; then python -m unittest -v test_release_acceptance. From repository root run python -m unittest discover -s scripts/dev -p 'test_*.py' -v and python -m unittest discover -s scripts/autonomy -p 'test_*.py' -v; retain actual counts, failures, skips, exits and environment. These are synthetic unit checks. No new test file is needed for this one-field correction. Require all selected tests pass with no unexplained skips and git diff --check passes. Inspect disabled CLI plan exit0/planned, validate exit3/unavailable, all verification flags false, all derived counts0, enabled tiers[], ci_profile.enabled=false and assembler hashnull; never label unavailable as acceptance.
4. Review exact C independently, push the validated coherent milestone promptly, and observe fresh normal push/pull_request Actions for C and actual merge fixture M. Record full SHA, run/event/job/step conclusions and checked-out M from logs; verify workflow and corrected task at M equal reviewed bytes. All required workflow jobs and subsequent Compose steps must finish successfully; pending, skipped, cancelled or stale-e3 success is insufficient. Do not rerun stalee3 as proof of repair. No claim of whole CI success before actual readback.
5. If integration includes DTO timing work, perform the plan's three-way semantic queue merge, independently review exact integration head, revalidate trusted workflow hash against that head, and observe normal Actions at that new source/merge fixture; old C evidence does not transfer automatically. Synchronize truthful code/CI results under the reviewed docs scope without granting acceptance/runtime/release authority.

Seven exact test IDs:

- test_release_acceptance.TrustedBoundaryTests.test_actual_unpromoted_task_is_diagnostic_only
- test_release_acceptance.TrustedBoundaryTests.test_disabled_slot_profile_hash_must_match_committed_profile
- test_release_acceptance.TrustedBoundaryTests.test_fabricated_pass_claims_cannot_enable_any_tier
- test_release_acceptance.TrustedBoundaryTests.test_invocation_cannot_be_selected_by_manifest
- test_release_acceptance.RawPrimitiveTests.test_raw_foundations_are_never_selected_by_the_disabled_cli
- test_release_acceptance.TrustedBoundaryTests.test_cli_actual_planning_task_returns_unavailable_and_redacts_bad_input
- test_release_acceptance.TrustedBoundaryTests.test_plan_performs_no_evidence_root_io_and_integrity_does_not_promote

Baseline evidence: /home/corp/autodata-evidence/integration-ci-failure-diagnosis/REPORT.md, seven-tests.json, hash-probe.json, exact-correction-design.json and failed CI logs. Future measured results must be appended with exact commit identity and hashes; do not rewrite the historical failure.

## Measured planning adoption

Literal Issue186/Project8 tracking is synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6642798543; actual readback timestamp 2026-11-04T21:39:49Z. Receipt SHA256 6ab37254147bd452737e6d60a64556242ac08ef4fede4265445252cad808cbbe. Issue body and prior comments, prior Project Source and other Project fields were preserved. Independent external six-document proposal review PASS:93 checks, no findings; verdict SHA256 f6fd0d3e93cff43a0bbe10a8b326cbf3e1e868c00db3482da21ba93d40a00d02. Gate branch is codex/workshop-r6-workflow-hash-gate, from exact e3ffba5037cea484ad0b12bcf594d726ad6b0311 without DTO PR252. Actual checkpoint B and two canonical preflight receipts will be sealed externally after commit; independent exact-B review and explicit one-path implementation dispatch remain pending. No corrected R6 bytes, repaired tests or CI success are claimed. All authorities remain false and credit0.
