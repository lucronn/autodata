# Task69 Release Essentials Integration Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded adoption after canonical preflight passes.

**Goal:** Integrate the reviewed Task58 supervisor patch and private-material helper into the corrected release candidate, finish the remaining Vercel DNS plan corrections, and verify the combined source without runtime or release operations.

**Architecture:** Adopt six existing reviewed technical files unchanged and apply two existing documentation corrections. Preserve the corrected Task68 workflow and R6 binding; no new subsystem or behavior design.

**Tech Stack:** Python supervisor/helper tests, Git, GitHub Actions and Markdown.

**Spec:** This plan defines the complete bounded adoption scope.

**Status:** synchronized tracking; implementation blocked until committed exact-base preflight and root checkpoint review/dispatch.
**Base:** `3421df91184e4a428450ee089a628ed144c05b15`, tree `b940480ab1c4329262f92edfdd17016d3cb05ac9` (Task68/PR297).
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8; existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

## Global constraints and sources

Planning may proceed while PR297 and PR225 CI finish; implementation/release review must retain their honest actual results. No cloud, service, credential, secret, provider, DNS, installation, publication, deployment or runtime-acceptance operation is authorized. Keep accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified and runtime/release authorities disabled.

- Task58 PR286 exact reviewed head `f667cbb84825e591e816c05bd5781153b76228b0`: source for four supervisor files below. Its old squash on another branch does not establish presence in this candidate.
- Private-material PR227 reviewed head `b46217747f103f08a144f9474047a7f2a857f73f`, merged into PR225 as `ec93551a39c157ee4f5b428e248e8fd766f68dee`: source for the two helper files below. Reference PR225's committed historical gate/spec/evidence at that exact SHA; do not import its historical documentation bundle or claims of operational readiness.
- DNS PR272 exact head `ca5bba686ea2a05dfc880b89f39a012b456016a3`: source for remaining corrections in the two plan files below. The current commerce contract already says Vercel and exact USD2000; preserve it.
- Preserve every byte of Task68 workflow SHA256 `3c54e7ba0613d1cd3a78819eede4915b1d268ffd904df83b2c034d914dca10e6` and R6 SHA256 `05b43e5a775e685d76bd44f0b05675cbd286476547c17e7e2cb9dade03a4e32d`/8727 bytes. No workflow rebind is required.

## TODO (literal tracking list)

- [ ] Synchronize Issue186/Project8, the Task69 plan and canonical operating-model entry; commit the planning checkpoint and pass canonical preflight at its exact SHA before implementation.
- [ ] Adopt the exact four Task58 files and two reviewed private-material helper files, and apply only the two remaining Vercel DNS plan corrections while preserving all other source and historical gates.
- [ ] Run focused supervisor, private-material, governance and workflow-binding checks plus exact byte/scope verification; commit and promptly push the validated candidate for independent review and full hosted CI.
- [ ] Retain exact candidate review and fresh source-push and actual-PR three-job CI evidence, record remaining blockers and keep credits0, verified IDs[] and runtime/release authorities disabled.

## Planning checkpoint

Only this plan and an appended Task69 section in `docs/github/operating-model.md` form the planning checkpoint. Root owns Issue186/Project8 synchronization and readback. Preserve prior tracking and canonical document text. After root confirms synchronization, set the embedded record to synchronized with actual UTC time, commit/push the two docs and pin actual checkpoint P/tree externally. Extract the JSON below from the committed plan at P into an external record file and run:

```sh
python3 scripts/autonomy/pre_implementation.py --record /home/corp/autodata-evidence/task69-supervisor-integration-prep/checkpoint-record.json --base-sha "$integration_checkpoint" --repo-root .
```

Require exit0/status synchronized/errors[] and independent exact-checkpoint review before source edits. There is no need for another spec/task/queue document or nested record when no orchestrator envelope is used.

## Exact adoption allowlist after the gate

Adopt byte-for-byte and mode-for-mode from Task58:

- `scripts/dev/workshop_browser_execution_contract.py`
- `scripts/dev/workshop_browser_execution_supervisor.py`
- `scripts/dev/test_workshop_browser_execution_contract.py`
- `scripts/dev/test_workshop_browser_execution_supervisor.py`

Adopt byte-for-byte and mode-for-mode from PR225 combined head `ec93551a39c157ee4f5b428e248e8fd766f68dee` (also verify equality to reviewed PR227 head):

- `infra/deploy/gce/private_material.py`
- `infra/deploy/gce/test_private_material.py`

Apply only PR272's existing corrections to:

- `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`: replace its two obsolete Cloudflare DNS/hosting-summary paragraphs with PR272's Vercel DNS ownership wording and explicit unverified hosting/proxy/TLS/origin boundaries; preserve the rest of the larger current file.
- `docs/superpowers/plans/2026-11-03-workshop-firebase-identity.md`: apply PR272's one paragraph replacement requiring headers appropriate to the verified proxy topology and making Cloudflare headers conditional on actual deployment.

Do not wholesale restore these plan files from PR272, which would discard later history. Do not edit `docs/architecture/workshop-commerce.md`; its Vercel/price corrections are already present. All non-allowlisted tracked bytes/modes must remain identical to P. No new tests, helper repairs, historical gate copies or queue entries are required. If source adoption reveals a real defect or conflict, diagnose and amend the gate before expanding scope.

## Implementation and verification

1. On the exclusively assigned clean branch at P, confirm all source identities and adoption scope. Import the six existing technical files with Git source restore and apply the three known paragraph corrections from PR272 to the two current plans. An ordinary coherent adoption commit is sufficient; no special parent graph or Task66 integration ancestry protocol is required.
2. Run these focused checks using provisioned supported dependencies; retain commands, exits, counts and skips:

```sh
env -u AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION -u AUTODATA_LIFECYCLE_TEST -u AUTODATA_WORKSHOP_BROWSER_CHILD PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=scripts/dev python3 -B -m pytest -q -p no:cacheprovider scripts/dev/test_workshop_browser_execution_contract.py scripts/dev/test_workshop_browser_execution_supervisor.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s infra/deploy/gce -p test_private_material.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.dev.test_repository_governance scripts.dev.test_workshop_browser_smoke.DTOWorkflowBindingTests -v
git diff --check
```

3. Independently verify the six technical blobs/modes against their exact reviewed sources, the two documentation deltas against PR272's intended wording, unchanged workflow/R6 digests and exact eight-path adoption delta relative to P. No duplicate full local developer/GCE/regression matrix is required; full hosted CI provides the broader regression run. Focused supervisor pytest was292 passing in earlier dry-run; treat that as historical until rerun on this candidate. The helper additions change total GCE inventory, so do not freeze the old274 inventory or inherit old green counts.
4. Commit/promptly push the validated source milestone. Obtain independent exact-candidate review and fresh source-push and actual pull_request full CI: all three existing jobs, full required GCE with no required skips, live Compose/cleanup and actual checkout SHA/tree/PR provenance, plus DTO120 final same-attempt artifact/receipt/cleanup. Retain failed parent or candidate attempts honestly. No local full suite duplication or inherited parent-green claim.
5. Append concise actual candidate SHA/tree, review and CI links, skips and remaining blockers to canonical plan/tracking in a coherent docs milestone; treat any new commit identity honestly. Preserve credits0/IDs[], disabled operational authorities and outstanding owner/staging/source/runtime/capture/trace blockers. No merge into a protected target or live operation follows automatically.

## Tracking synchronization receipt

Root confirmed Issue186 [comment6652770502](https://github.com/lucronn/autodata/issues/186#issuecomment-6652770502) exact-body readback PASS and Project8 Source appended-pointer readback PASS (1016 bytes, prior prefix preserved), status In Progress. Recorded at `2026-11-05T07:55:25.114444+00:00`. This tracking synchronization grants no implementation or runtime authority.

## Committed pre-implementation record

```json
{
  "goal": "Integrate the reviewed Task58 supervisor patch and private-material helper into the corrected release candidate, finish the remaining Vercel DNS plan corrections, and verify the combined source without runtime or release operations.",
  "plan_ref": "docs/superpowers/plans/2026-11-05-workshop-release-essentials-integration.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/github/operating-model.md"
  ],
  "todo": [
    "Synchronize Issue186/Project8, the Task69 plan and canonical operating-model entry; commit the planning checkpoint and pass canonical preflight at its exact SHA before implementation.",
    "Adopt the exact four Task58 files and two reviewed private-material helper files, and apply only the two remaining Vercel DNS plan corrections while preserving all other source and historical gates.",
    "Run focused supervisor, private-material, governance and workflow-binding checks plus exact byte/scope verification; commit and promptly push the validated candidate for independent review and full hosted CI.",
    "Retain exact candidate review and fresh source-push and actual-PR three-job CI evidence, record remaining blockers and keep credits0, verified IDs[] and runtime/release authorities disabled."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T07:55:25.114444+00:00"
}
```
