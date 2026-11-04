# Workshop reviewed-leaf integration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans only after synchronized committed checkpoint, passing full-SHA preflight, independent exact-checkpoint review and fresh coordinator dispatch. This local draft grants neither implementation nor delegation authority.

**Goal:** Integrate the three independently reviewed dormant R6, publisher and staging histories into one byte-pinned offline candidate without live activation.

**Architecture:** Preserve complete histories through three ordered non-fast-forward merges. Select implementation bytes exactly from reviewed leaves; reconcile only five shared documentation/tracking files. No feature corrections, profile promotion or dependency installation.

**Tech Stack:** Git, Python unittest/standard library, previously reviewed Node22.23.4, existing offline suites.

**Spec:** `docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md` freezes every source/blob pin. `docs/agents/pre-implementation-gate.md` is normative for planning/tracking.

## Draft status and source tuple

**Status: unsynchronized. Execution: blocked.** PG owns the serialized tracking slot. This package exists only under `/tmp/autodata-release-integration-gate-draft-2026-11-04/`. No Issue/Project/PR or repository/worktree/index changes have occurred. Historical source records cannot authorize this integration.

Prospective tracking: https://github.com/lucronn/autodata/issues/186 and https://github.com/users/lucronn/projects/8.

Root: `eddcf724028683dbb083191e4f8c42064b866bf0`, branch `codex/production-release-orchestration`, draft PR187. Future docs-only checkpoint must descend directly from this root with only this integration gate's approved documentation changes. Root/source drift blocks execution and requires review; never silently substitute a SHA.

Deterministic merge order:

1. R6 `a4a0d7cc5e95f16793d80dfd73596b40c27e6757`, `codex/workshop-r6-dto120-gate`, https://github.com/lucronn/autodata/pull/190; includes PR188 `99df69caaeb4d5ccf6d0ffbf0377fe6d5d872a3d`.
2. Publisher `12e69449d8a0e53c4817c3d523d2cab4da57e38c`, `codex/workshop-publisher-stage1a-builder`, https://github.com/lucronn/autodata/pull/196; includes Stage0 `dde53d745f8422ce29d6e8b3d459f4a0b91ebd04` and joined PR189/191/192/193 histories.
3. Staging `10a454a3c4160ac8e423c25fcf38ab58b426fb86`, `codex/workshop-staging-m2a-builder`, https://github.com/lucronn/autodata/pull/197; includes corrected M1 `ef536cc24478424efc3cc084425322cfb8056145` (PR195).

Earlier PRs are not replayed separately. PR base names are review topology; this plan grants no retarget/merge authority over those PRs. Sources report independent exact-SHA review; final combined head needs fresh checks/review.

## Prospective repository files

- Plan: `docs/superpowers/plans/2026-11-04-workshop-reviewed-leaves-integration.md`.
- Spec: `docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md`.
- Record: `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json`.
- Task: `docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-integration.json`.
- Evidence: `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`.

The record and task's nested `pre_implementation` contain the identical goal, refs and concrete todo. Current unsynchronized status/null checkpoint/all false authorities are deliberate. Future evidence holds then-current tracking snapshots, hashes, readbacks, checkpoint/preflight/dispatch and candidate checks.

`blob-pins.json`, copied in full into the local spec and record, pins all **23 implementation paths** and **59 historical nonconflicting documentation paths**, with full source SHA, Git blob OID, SHA256 and byte count. Those exact maps must travel in committed spec/record, not depend on `/tmp`. Two R6 Python files use R6 leaf, fourteen publisher/workflow files use publisher leaf, seven bootstrap/installer files use staging leaf. Implementation paths are disjoint. All unaffected implementation bytes/modes remain root-identical. Unexpected conflict, new code change or test failure requires a new correction gate, not repair inside this plan.

## Five deterministic conflict resolutions

`prospective-resolutions/` contains local review examples. The spec pins pre-note resolved bytes and blocked-note variants. These are prospective documentation text only, not a Git merge.

1. `docs/agents/tasks/2026-11-03-production-release/queue.json`: assert root and all leaves have identical top-level values outside `tasks`; retain those values. Index unique task IDs. Start in root order, visit R6/publisher/staging, select complete leaf objects only when different from root and append new IDs in leaf order. Reject removals or divergent changes to one ID by multiple leaves. Exactly nine selected IDs: `r6-release`, `r6-paid-selector-work`, `r6-dto120-receipts`, `workshop-publisher-transport`, `workshop-migration-build-arg`, `workshop-authenticated-publisher`, `workshop-staging-bootstrap`, `workshop-staging-boot-device`, `workshop-staging-m2-host-install`. They are mutually exclusive across lanes. Preserve each entire historical object including pending states/receipts/denials; append the new integration item. Format two spaces/final newline. Never copy a source's historical Project index over current live tracking.
2. `docs/architecture/infrastructure-and-dev.md`: assert exact root prefix in every leaf; compose root + R6 suffix (empty) + publisher suffix + staging suffix + integration note.
3. `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`: root exact prefix + R6 suffix + publisher suffix + staging suffix + integration note.
4. `docs/superpowers/plans/2026-11-03-workshop-hosting.md`: root exact prefix + R6 suffix (empty) + publisher suffix + staging suffix + integration note.
5. `docs/operations/workshop-gcp.md`: retain complete publisher version, including early inserted orchestration sections and Stage0 history, append staging suffix after its exact root prefix, then integration note. R6 equals root here. Do not reduce publisher to an end-only suffix.

Integration notes carry exact source tuple, goal, plan/spec/record/task references, concrete todo and no-live/false-readiness limits. Inherited records remain unchanged, historical pending statements are retained as history. At docs checkpoint, append only the integration note to current canonical files; historical suffixes arrive only with the respective authorized merges. Compose imported suffixes before the integration note. Replace only the integration note's unsynchronized status after real synchronization; never reinterpret old review/dispatch statements. Whole-file ours/theirs selection for these five conflicts is forbidden.

## Task 1: serialized synchronization and checkpoint

- [ ] Independently review local bundle/hash. Wait for explicit coordinator PG tracking-slot release; no tracking writes before it.
- [ ] Snapshot then-current Issue body/full relevant comments, Project status/full Source or dependency field and exact IDs. Preserve predecessor bytes/SHA256 in new Issue detail and canonical evidence. Compare live state immediately before write; stop on concurrent drift. Retain every PG/publisher/staging/R6 reference. If 1024-character Project index cannot retain references, ask coordinator for preservation/index handling; drop nothing silently.
- [ ] Synchronize exact goal/source tuple/scope/refs/todo in Issue186/Project8/canonical notes/record/task/queue. Independently read back/hash all values and predecessor preservation. Only then set new integration record and identical nested task to `status: synchronized`; inherited objects stay unchanged.
- [ ] Commit/push docs-only checkpoint on assigned isolated `codex/` feature branch from root. Obtain full checkpoint SHA externally as `INTEGRATION_GATE_SHA`; do not invent a SHA in this draft.
- [ ] Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json --base-sha "$INTEGRATION_GATE_SHA" --repo-root "$PWD"`. Require exit0, `status: synchronized`, `errors: []`, clean worktree and matching remote SHA.
- [ ] Obtain independent exact-checkpoint review and fresh coordinator code-only dispatch. No implementation before both.

## Task 2: preserve histories through exact merges

From clean assigned isolated branch at synchronized checkpoint, run only after Task1 passes. These commands were not executed for this draft:

```bash
git merge --no-ff --no-commit a4a0d7cc5e95f16793d80dfd73596b40c27e6757
# resolve approved docs, check and commit/push before next merge
git merge --no-ff --no-commit 12e69449d8a0e53c4817c3d523d2cab4da57e38c
# resolve approved docs, check and commit/push before next merge
git merge --no-ff --no-commit 10a454a3c4160ac8e423c25fcf38ab58b426fb86
```

- [ ] Verify preflight against original checkpoint, exact sources and clean branch before each merge. Resolve only approved five paths with literal algorithms. Stop on any other conflict.
- [ ] Compare every imported implementation and historical-doc path to selected source `git show`, SHA256, byte length, Git blob OID and mode. All unaffected implementation files equal root. Only five conflict paths plus this gate's five docs may differ from selected source/root bytes. Detect duplicate task IDs/conflict markers/unmerged index entries and reject.
- [ ] Run applicable Task3 checks after each milestone. Commit `integrate: preserve reviewed R6 diagnostic history`, `integrate: preserve reviewed dormant publisher history`, `integrate: preserve reviewed inert staging history`; promptly push each validated coherent milestone to assigned feature branch. Preserve full source histories; no squash/cherry-pick/rebase or published-history rewrite.
- [ ] Require `git merge-base --is-ancestor` exit0 for root and each three leaf full SHAs at final head. Freeze actual new candidate SHA. Never merge master/retarget source PRs/deploy under this gate.

## Task 3: combined offline checks and exact-head review

Require `/tmp/autodata-reviewed-node-v22.23.4` SHA256 exactly `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90` before use. Missing/different runtime blocks; request reviewed offline runtime through coordinator, without automatic download/install/ambient Node substitution.

From repository root:

```bash
python3 -m unittest scripts/dev/test_release_acceptance.py -v
python3 -m unittest discover -s scripts/dev -p 'test_*.py'
python3 -m unittest discover -s scripts/autonomy -p 'test_*.py'
python3 -m unittest discover -s infra/deploy/gce -p 'test_host_install.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_staging_bootstrap.py' -v
/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs infra/deploy/gce/test_publisher_policy.mjs infra/deploy/gce/test_publisher_identity.mjs
bash -n infra/deploy/gce/deploy.sh infra/deploy/gce/cloud-bootstrap.sh
git diff --check "$INTEGRATION_GATE_SHA" HEAD
```

From `infra/deploy/gce`:

```bash
python3 -m unittest test_publisher_adapters test_cloud_ops test_host_runtime test_release_workshop_contract -q
```

AST-parse selected Python without repository bytecode; reviewed Node `--check` every selected `.mjs`; strict-parse changed JSON; recheck original pinned preflight and all pins/modes/allowlists/ancestry. Artifact Node tests run from repository root because child CLI tests use repository-relative paths. Record actual commands/counts/exits/commit and failures, never copy historical totals.

Verify workflow four protected jobs equal selected publisher definitions; CLI/internal worker deny before SDK/credentials; Stage1A runtime bearer remains `missing_dependency`; R6 profiles/CLI dispatch remain disabled, verified IDs empty/all verification flags false; M1 evidence remains fake transport and M2A remains inert. Existing tests plus exact-byte checks are acceptance; add no tests mirroring merge choices.

Independent reviewer verifies final exact SHA, source ancestry, all23 implementation pins/all59 historical docs, five conflict resolutions, checks and unchanged denials. A later receipt commit needs fresh exact-head verification; older head review does not cover newer bytes automatically. Failures/source drift/missing runtime/lost history block acceptance and require coordinator action/new gate.

## Evidence limits and later gates

Root's independently reviewed180/180 inventory applies only to eddcf724. DTO120 is not API21; paid12 seeds grants, commerce injects Stripe, API21 uses fixture services, dual-bank lacks real API/PostgreSQL restart evidence. R6 consistency is not browser/provenance acceptance and does not enable certification. M1/M2A/Stage0/Stage1A offline reviews prove no cloud bootstrap, authenticated upload, installed-source privileged success or real host install.

This integration runs only offline checks. Final fixture reruns, authenticated exact-push-head CI/artifact readback, branch-protection/Vercel handling, image/security/dependency/license acceptance and product acceptance require separately scheduled gates. PG17 schema/image successor is not imported: a new exact reviewed PG leaf requires revised pins/conflicts/checks and synchronized gate before integration.

No provider/cloud/registry/SDK/Docker/browser/live-bank/Stripe/Firebase operation, credentials, real disk/host install, service start, DNS/cars.tk cutover or deployment is authorized. Actual WIF/OCI/SBOM/signing/runtime trust, owner-selected staging resources, licensed content, Firebase/Stripe TEST enrollment, protected storage, recovery/restore/alerts and live staging remain separate blockers. All production/readiness/deployment/cutover authority stays false.

## Concrete todo

- [ ] Independently review local draft; remain unsynchronized/blocked until PG tracking-slot release.
- [ ] Preserve current Issue/Project text/hashes; synchronize source tuple/goal/refs/todo/canonical notes; commit/push and pass full-SHA preflight.
- [ ] Obtain independent exact-checkpoint review/fresh coordinator dispatch in isolated worktree.
- [ ] Merge R6/publisher/staging in order; resolve only five docs/tracking paths; preserve23 implementation pins,59 historical documents and full histories.
- [ ] Run offline checks, retain actual evidence and commit/push coherent validated milestones.
- [ ] Independently review/freeze exact final SHA; keep fixture/CI reruns and live activation behind separate gates.


## Verified docs-only integration tracking synchronization

This additive receipt supersedes only the local-draft tracking statements above. Coordinator explicitly released PG writer slot. Independent local draft review PASS pinned plan SHA256 ea42fcac66cc397482f985be8a26e6e73dc1fc22c0b4e008eec742d4e384e553 / bundle manifest ca34e3e8be70bac131aabf7b600032a9b4531f0d87b85f5a8fa5f75f03c94a63. https://github.com/lucronn/autodata/issues/186#issuecomment-6622915925 read back at 2026-11-04T04:54:35.010852+00:00. Entire current Issue body/all115 prior comment bodies and full current PG Project index preserved verbatim+hash in `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`; independent API readback confirmed Issue/prior comments unchanged. PG gate74dfe57/receiptd662cb0, Stage1A and M2A details/pins/statuses/denials preserved. Project current index SHA256 20ab190a8c0e78eb994b5e99ba133e7df2cdebd1258f29c0680d0cb32422407c.

Record/task status synchronized after actual readback. Full committed checkpoint/preflight, independent exact-checkpoint review and fresh coordinator dispatch remain required before any ordered integration. No implementation merge, provider, cloud, runtime, staging activation or deployment occurred. This synchronization alone authorizes none of them.

Goal: Integrate the three independently reviewed dormant R6, publisher and staging leaf histories into one byte-pinned offline candidate without live activation.

Refs: `docs/superpowers/plans/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-integration.json`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`

Concrete todo:
- [ ] Obtain independent local-draft review; keep status unsynchronized and integration blocked until PG releases the serialized tracking slot.
- [ ] After slot release, preserve then-current Issue186/Project8 texts and hashes; synchronize exact source tuple, plan/spec/record/task/canonical notes and concrete todo; commit/push the docs-only checkpoint and pass full-SHA preflight.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh coordinator code-only dispatch; create an isolated feature worktree/branch from the checkpoint.
- [ ] Merge exact R6, publisher and staging leaf histories in that deterministic order, resolving only five approved documentation/tracking conflicts and preserving all 23 implementation blob pins and historical additions.
- [ ] Run combined offline Python/Node/preflight/syntax/scope/authority checks after each milestone; commit and promptly push validated coherent merges to the assigned branch.
- [ ] Obtain independent exact-head review, freeze the combined candidate SHA and retain results; obtain separate gates before fixture/CI reruns or any live activation.


### Exact committed integration checkpoint pin

Gate `2728ac1acaf173d6f244e200e584dac7922fda1d` pushed on `codex/workshop-reviewed-leaves-integration-plan`; canonical preflight at that full SHA exit0, `status: synchronized`, `errors: []`, stderr empty. Pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622928529 read back 2026-11-04T04:55:31.706681+00:00. Final Project index SHA256 `578438413fa8b6738efbf960c46e55ff7b6623772fac191b697af862d57bf0d2` (934 characters), containing every explicit predecessor reference ID including full PG gate74dfe57, receiptd662cb0 and M2A gate9a2b57d0. Complete Issue body/all115 predecessor bodies unchanged on fresh paginated readback. Evidence retains exact prior/full current index, pin hash, command/stdout/stderr and readback.

Independent exact-checkpoint review and fresh coordinator code-only dispatch remain required before any ordered integration. No code merge or activation occurred. Receipt commit records this gate without changing its pinned base.


## Additive offline integration completion supplement

Goal: Record the independently reviewed offline integration candidate in draft PR #198 while preserving current PG17 tracking and every release denial.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8; draft PR https://github.com/lucronn/autodata/pull/198. Exact reviewed candidate `e5fed171bb36fdb759c592cbcd0e15aea5490c97`, gate `2728ac1acaf173d6f244e200e584dac7922fda1d`, receipt `507e3ddb977ddd45910cba978c7255fac3cb669e`. This separate docs/tracking branch does not change the reviewed candidate or reinterpret inherited pending records. Coordinator relayed independent exact-candidate PASS by `/root/app_server_plan_review`; no file-backed review was supplied. Offline evidence summary SHA256 `03af0e6d41cfa99261a6c92f431cfa0fd9fafacdc8ea2723b264f53899c1896d`, manifest `d17c0dcb33a07c674b0c8f738635df825fee8bed2bc0360252a970ab2572977e`; all12 manifest files verified. Suites81/233/146/188/142/40/33 passed at the exact candidate;23 implementation and59 historical doc pins match. Evidence is retained under `docs/verification/2026-11-04-workshop-reviewed-leaves-completion`.

Completion record `docs/agents/records/2026-11-04-workshop-reviewed-leaves-completion.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-completion.json`; full tracking snapshot `docs/agents/records/2026-11-04-workshop-reviewed-leaves-completion-tracking.json`. The entire current Issue body/all121 prior comments and1001-character Project source field are preserved verbatim+SHA256. Only the bounded Project index is compacted because its1024-character limit cannot retain old prefix plus completion links. PG completion detail6623105546/pin6623119656 stay linked; historical installation remains failed/quarantined. Project Status remains In Progress; Issue body/history and other fields remain unchanged.

CI observation is timestamped in the completion record; push run41776726134 passed both jobs, PR run41777148511 was pending at initial readback, Vercel rate-limited FAILURE. Later observations are additive; offline suites and DTO inventory are not current-tree product acceptance or production readiness.

Concrete todo:
- [ ] Preserve full current Issue body/all121 prior comments and Project item/field bytes and hashes.
- [ ] Verify exact integrated head, all23 implementation/all59 historical pins, offline evidence hashes and coordinator-relayed independent review.
- [ ] Append a completion detail to Issue186 and compact only the Project source index within1024 characters, retaining PG completion detail/pin and PR198; leave Issue body/history/other Project fields unchanged.
- [ ] Read back complete tracking, commit/push docs-only completion checkpoint and run exact full-SHA preflight.
- [ ] Append exact checkpoint/preflight pin and retain final readback in a receipt commit; no future implementation or runtime authority.

This completion supplement grants no new implementation, fixture/CI rerun, SDK/upload, credentials, Docker/provider/cloud/host/service/activation/deployment/DNS/cars.tk cutover authority. New work requires a separate decision-complete synchronized gate, exact preflight, independent checkpoint review and fresh dispatch. No independent checkpoint review is sought for future implementation here.


### Verified additive completion tracking readback

Completion detail https://github.com/lucronn/autodata/issues/186#issuecomment-6623150233 read back 2026-11-04T05:12:02.611072+00:00. Complete original Issue body/all121 prior comments unchanged; only Project source index changed to792 characters, SHA256 `833157f569a02e5d0aac2226f5ada599d5ce6088effcbeba86989e0dc481cc0c`; Status In Progress/all other fields unchanged. Full old1001-character field and PG detail6623105546/pin6623119656 bodies remain retained verbatim in tracking evidence. All12 evidence files and23/59 pins authenticated. Exact checkpoint/preflight pin follows; this is documentation/tracking completion only and authorizes no future implementation.
