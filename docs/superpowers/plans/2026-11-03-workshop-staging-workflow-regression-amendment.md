# Dormant staging workflow regression assertion amendment

**Goal:** Scope legacy cloud-workflow production assertions to production jobs while retaining strict dormant staging checks and every activation denial.

Issue: https://github.com/lucronn/autodata/issues/186 . Project: https://github.com/users/lucronn/projects/8 .

Status: synchronized planning checkpoint; exact-checkpoint review and coordinator dispatch required before implementation. This is an additive one-file test scope amendment to the authenticated publisher plan, not integration or activation authority.

## Observed regression and exact base

Authenticated-publisher checkpoint b431e548df4f379f6752e021c6fb42e8837a5311 authorized six JavaScript/toolkit/workflow implementation paths in this worker. Validated helper milestone d9751f6 and staging-definition milestone `e9faaf594ecd671e113190fe0c57229d9824ad04` are pushed on `codex/workshop-publisher-artifact`; neither is independently accepted for integration yet.

At `e9faaf594ecd671e113190fe0c57229d9824ad04`, 52 Node tests and five new staging workflow tests pass. The focused cloud/host/workflow suite runs143 tests:142 pass, one fails. `test_cloud_ops.WorkflowTests.test_every_cloud_job_is_explicitly_enabled_separate_bounded_and_fail_closed` iterates every release job, derives a production-only variable name and then assumes production-only permissions, unique production environments/principals, an operation timeout dictionary and no Actions steps. Its first failing assertion seeks `WORKSHOP_STAGING-BUILD-CANDIDATE_ENABLED`, whereas the approved dormant staging definition correctly uses `WORKSHOP_STAGING_PUBLISH_ENABLED`. The test has never previously represented staging authority. The failed result is retained; no all-green claim is made.

Production `publish` canonical JSON SHA256 remains `5e1618ac1a73b3ecdb08a43226be6edc9d3178922be3c1e7369b2f9f36168763`; `deploy` remains `f9f4133f0092899a1174044ea4fd7dd8258e1fd21ae1828cb543095dd013f731`. The new dedicated tests freeze those entire objects and check staging permissions/guards/blocked execution independently.

## Exact implementation scope and decision

Only `infra/deploy/gce/test_cloud_ops.py` may change under this amendment. Modify only the named legacy test: for the release workflow, first require exactly publish/deploy/staging-build-candidate/staging-finalize jobs, then run every existing production invariant against the fixed publish/deploy pair. For backup/monitor, retain iteration over their existing workflow jobs. Preserve every existing assertion and subprocess blocker check on all four production operations; do not skip tests, weaken permissions or widen timeouts.

Staging authority stays covered by `test_release_workshop_contract.py`: exact protected staging environment, mutually exclusive master/repository/dispatch/enable guards, actions:read/id-token:write scopes, 125minute limit, validated phase-specific inputs, unconditional second-step exit3 before pinned control checkout and frozen production bodies. The amendment cannot change that file, workflow, helper/toolkit lock, production jobs, CLI, applications, schema, runtime, credentials, deployment or live tooling. The reviewed candidate toolkit has seven moderate audit findings and an unresolved buffers0.1.1 license; owner/trust/origin/staging evidence remains absent. No activation follows.

## Concrete todo

- [ ] Synchronize the narrow test-only amendment across Issue186, Project8 and canonical docs; commit and pass pinned preflight before correction.
- [ ] Limit legacy release-loop production invariants to publish/deploy, retain all their assertions, and reject unknown release jobs alongside dedicated dormant staging checks.
- [ ] Run retained red/green workflow, cloud and host regressions plus Node/syntax/scope checks; push for independent exact-SHA review without activation.

## Verification and handoff

1. Save the existing failed143-test run as red evidence at the candidate base above.
2. Synchronize Issue186/Project8/canonical operations documentation with the same goal and todo, preserving prior Project index verbatim and its SHA256 in the Issue comment. Commit the docs-only checkpoint and run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-03-workshop-staging-workflow-regression.json --base-sha CHECKPOINT_SHA`. Failed synchronization blocks the implementation.
3. Obtain independent exact-checkpoint review and coordinator dispatch. Apply only the loop/known-job correction in the named test. Run from infra/deploy/gce: `python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q`; run all52 Node tests using the archive-verified Node22.23.4 binary, Python/Node syntax, exact one-file implementation allowlist and diff checks.
4. Commit/push the validated correction, recheck pinned gate, and request independent exact-candidate review. Keep all previous failures and audit limits. Never activate or dispatch a workflow or acquire runtime credentials.

The machine record lives at `docs/agents/records/2026-11-03-workshop-staging-workflow-regression.json` and the task at `docs/agents/tasks/2026-11-03-production-release/workshop-staging-workflow-regression.json`. The pinned base for this narrow implementation is the eventual docs-only checkpoint, not an uncommitted plan. The prior authenticated-adapter authorization and all unrelated PG17/DTO/R6/production records remain historical authority with their own gates.
