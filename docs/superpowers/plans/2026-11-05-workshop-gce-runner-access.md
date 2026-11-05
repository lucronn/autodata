# Task68 GCE Runner Access Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this single bounded task after the repository gate passes.

**Goal:** Restore UID/GID1000 workspace traversal in required GCE CI by granting only the missing execute bit on the ephemeral runner home, preserving the existing fail-closed preflight, complete suite, identity contract and R6 workflow binding.

**Architecture:** Add one runner-only permission command to the existing GCE step. Its unchanged first UID1000 preflight remains the fail-closed source-read check; update the existing script identity assertion and R6 workflow digest to bind the exact corrected workflow.

**Tech Stack:** GitHub Actions Bash, Python stdlib governance tests, disabled R6 JSON metadata.

**Spec:** `docs/agents/tasks/2026-11-03-production-release/workshop-gce-runner-access.json` (canonical task specification).

**Status:** synchronized tracking; implementation blocked until committed checkpoint, exact-base machine preflights and coordinator dispatch.
**Source base:** `25d44588cb1ab82fab3e39d28ef1ee5a12b5fb44` / tree `264fc8d7711c461d781d7eaa7af34391c802edac`.
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

## Evidence and constraints

Task67 diagnostic [run41988867014](https://github.com/lucronn/autodata/actions/runs/41988867014), artifact13397466412, identified `/home/runner` UID/GID1001 mode0750 as the source traversal barrier for UID1000 with cleared groups. Source descendants are readable; configured TMPDIR is also inaccessible through the same runner-home ancestor, while generic tempfile succeeds by falling back; the original preflight exits1 with EACCES. This is coordinator-provided evidence, not a new successful CI claim.

The correction applies only to the ephemeral hosted runner. Preserve the entire required GCE script except the one line below, all event filters/jobs/timeouts, actual/effective UID/GID1000, cleared groups, sanitized environment, temp ownership, required Compose flag, executable checks and full unittest discovery. Preserve production/source/tests under `infra/deploy/gce`, all disabled R6 authorities, historical failures, existing queue objects/root fields, release blockers and credits0. No merge or deployment authority.

## TODO (literal tracking list)

- [ ] Synchronize this literal goal, four todos, four gate documents and three implementation paths in Issue186/Project8; commit/push the planning checkpoint, pin its actual SHA/tree, pass standalone and nested exact-base preflights and obtain coordinator dispatch before implementation.
- [ ] Insert only sudo -n /bin/chmod o+x /home/runner immediately before the first run_gce Python preflight; preserve every other workflow byte, update the literal GCE script digest and add a deletion mutation in governance tests, and replace only the single R6 workflow_sha256 value with the corrected workflow digest.
- [ ] Run focused governance and workflow/R6 binding checks plus complete developer tests; verify the exact three-path implementation diff and unchanged UID/GID1000, cleared groups, sanitized environment, required Compose flag, source-read preflight and full GCE discovery command; commit and promptly push the validated milestone.
- [ ] Retain exact-source push and actual pull_request CI receipts for all three required jobs, including the first UID1000 preflight, complete required GCE suite and live Compose; append honest results while preserving historical failures, release blockers and acceptance credits0, without merge or deployment.

## Single implementation milestone

**Modify only:** `.github/workflows/autonomous-verification.yml`, `scripts/dev/test_repository_governance.py`, `docs/agents/tasks/2026-11-03-production-release/r6-release.json`.
**Gate documents only:** `docs/superpowers/plans/2026-11-05-workshop-gce-runner-access.md`, `docs/agents/records/2026-11-05-workshop-gce-runner-access.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-gce-runner-access.json`, `docs/agents/tasks/2026-11-03-production-release/queue.json`.

1. In governance tests, add a mutation removing the exact permission line and assert `gce_script_identity`; update the approved literal digest to `d305124edec61fca89e86d463413305f02a8c37208538d46bbe1de6c2766a602`. Against the original workflow the approved-script check must fail before the workflow correction.
2. Insert this exact command immediately before the existing first `run_gce "$gce_python" -B -c` preflight:

```bash
sudo -n /bin/chmod o+x /home/runner
```

This changes mode0750 to0751, adding traversal without directory read/write for other identities. Do not recurse, chown source, change UID/groups or add optional execution. The existing first preflight must still read both source files and create/clean a temporary directory as UID1000. Because tempfile can fall back, the verification receipt must additionally prove configured TMPDIR access under the unchanged wrapper by creating `tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])`; do not infer this from generic tempfile success.
3. Verify workflow SHA256 changes `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418` → `3c54e7ba0613d1cd3a78819eede4915b1d268ffd904df83b2c034d914dca10e6`. Replace only that single old ASCII digest in R6 `product_evidence.ci_profile.workflow_sha256`; do not serialize JSON. Expected R6 SHA256 `05b43e5a775e685d76bd44f0b05675cbd286476547c17e7e2cb9dade03a4e32d`; unchanged length `8727` bytes.
4. Run `python -m unittest scripts.dev.test_repository_governance -v`, `python -m unittest discover -s scripts/dev -p 'test_*.py' -v`, `git diff --check` and inspect the three-file diff. The workflow must equal its source-base bytes with only the specified line inserted; R6 must equal its source-base bytes with only one digest replacement. Commit/push this validated milestone after gate dispatch.
5. Obtain fresh source-push and actual pull_request CI results. Require all three existing jobs, the unchanged identity/source/temp preflight, full `python -B -m unittest discover -s infra/deploy/gce -p 'test_*.py' -v` under the existing wrapper, and live Compose. Record exact checkout SHA/tree/run/job receipts; failed checks stay failed and manual runs remain supplemental. Update this plan and tracking with results.

## Gate handoff

Root owns live Issue/Project writes. Read back the identical goal/todos/scopes and preserve prior Project text in the receipt. Only then change standalone/nested/queue Task68 statuses to `synchronized`, commit/push these four planning documents, externally pin the resulting checkpoint SHA/tree, and run canonical validator against both standalone record and nested task record at that exact checkpoint. An uncommitted plan cannot authorize implementation. No additional specification, workflow or architecture document is needed for this bounded correction.

Tracking synchronized by root: [Issue186 comment6652598903](https://github.com/lucronn/autodata/issues/186#issuecomment-6652598903) records the literal goal/four todos/four gate documents/three implementation paths. Project8 source preserves its prior prefix; source receipt `/home/corp/autodata-evidence/task68-tracking/PROJECT-SOURCE.txt`, 969 characters, SHA256 `e2c54c913e8bd33754534ea8958964fb61f8a4c3745842c7a946d83082d6570b` (local file digest verified). Checkpoint SHA/tree remain unassigned; this tracking update grants no dispatch or implementation authority.
