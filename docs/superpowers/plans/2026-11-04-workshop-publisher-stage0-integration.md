# Workshop Publisher Stage0 Dormant Integration Implementation Plan

> **For agentic workers:** Execute the bounded tasks below only after the canonical gate passes and the coordinator dispatches implementation. Use superpowers:executing-plans; no delegated or expanded implementation scope follows from this draft.

**Goal:** Integrate the exact corrected dormant Python and Actions artifact publisher candidates while preserving reviewed implementation bytes and every activation blocker, then verify the combined offline contracts.

**Architecture:** Preserve Python head `101f7d6e2a2795206f16b4419fe561cad531071e` and integrate artifact head `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` unchanged. Resolve the sole documentation append conflict, then run the existing combined offline suites. The result remains dormant library and workflow definitions with no executable production factory, authenticated official upload worker or activation authority.

**Tech Stack:** Git three-way merge; Python standard-library unittest; pinned Node22.23.4 test runner; current JSON workflow contracts.

**Spec:** `docs/agents/pre-implementation-gate.md`; `docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md`; the exact source records and byte map below.

## Authority and exact source boundary

Status: **synchronized documentation checkpoint; implementation blocked pending committed full-SHA preflight, independent exact-checkpoint review and coordinator dispatch**. Intended existing Issue: https://github.com/lucronn/autodata/issues/186 . Intended existing Project: https://github.com/users/lucronn/projects/8 . The coordinator authorized docs-only synchronization after staging M1 released tracking at receipt `5bd9b82aa71b68938c130c58062b8664596c6758`; the verified synchronization and preservation evidence is recorded below. Record `docs/agents/records/2026-11-04-workshop-publisher-stage0-integration.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage0-integration.json`; canonical notes `docs/operations/workshop-gcp.md`.

Selected planning baseline `101f7d6e2a2795206f16b4419fe561cad531071e` on `codex/workshop-publisher-stage0-plan`. Artifact source `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` on `codex/workshop-publisher-artifact`. Exact common ancestor `b431e548df4f379f6752e021c6fb42e8837a5311`. Root inspected source `eddcf724028683dbb083191e4f8c42064b866bf0`. This checkpoint changes only its plan/record/task, canonical preservation-evidence record and an additive operations note; implementation remains byte-identical to Python baseline. The synchronized checkpoint SHA must be pinned explicitly after commit; neither synchronization alone nor either historical source gate authorizes the new merge.

Non-writing three-way `git merge-tree` inspection found exactly one conflict: `docs/operations/workshop-gcp.md`. Implementation deltas are disjoint; shared `cloud-ops.py` is identical. Text compatibility is not semantic acceptance. Artifact source includes `220d9c3` plus close-failure correction `bba43a0`; independent exact-head review evidence must be attached before dispatch. Do not cherry-pick only either final correction commit, change the selected source pair or substitute latest branch tips.

## Global constraints

- Stage0 only preserves exact selected implementation blobs; no implementation fixes, refactors, new tests, dependency installs, SDK imports/uploads or production dependency factory/worker work. A failing existing check blocks and needs a separate correction gate.
- No tokens, OIDC/WIF/IAM, cloud/registry/provider/host/Docker/toolkit execution, workflow run, signing, policy installation, staging/production activation, deployment, schema/services/readiness, DNS or commerce action.
- Retain current CLI exit3/missing_dependency, both production job bodies/permissions/blockers, staging activation blockers, source/workflow/run-attempt separation, independent approval and original outer/inner/member hash contracts. Runtime readiness remains false.
- Preserve historical records/tasks/plans as evidence at their original byte identities; their synchronized labels apply only to historical scopes. Do not copy them as authority for this integration. Do not modify queue/PG records or live tracking while another lane owns the slot.
- Commit/push only a completed validated implementation milestone after authorized dispatch. Push the synchronized docs checkpoint for independent exact-SHA review; do not begin implementation before its pinned passing preflight and coordinator dispatch.

## File map and byte contract

Future implementation merge delta allowlist (each file must equal artifact source exactly):

- `.github/workflows/release-workshop.yml`
- `infra/deploy/gce/publisher-toolkit/package-lock.json`
- `infra/deploy/gce/publisher-toolkit/package.json`
- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/test_cloud_ops.py`
- `infra/deploy/gce/test_publisher_artifact.mjs`
- `infra/deploy/gce/test_release_workshop_contract.py`

Python library/test and shared `cloud-ops.py` must remain exactly Python source. Exact Git blobs are below; JSON record also carries SHA256 of each source file:

| Path | Selected source SHA | Required Git blob |
| --- | --- | --- |
| `.github/workflows/release-workshop.yml` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `a8f5ef0fc4ab79ee7a42afb58662a3fbe81766e9` |
| `infra/deploy/gce/publisher-toolkit/package-lock.json` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `ae1c96e2703ca55ce440706d93b559c158c8c3f0` |
| `infra/deploy/gce/publisher-toolkit/package.json` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `54ec1370e156229936d252e9d634c7fa1d14e160` |
| `infra/deploy/gce/publisher_artifact.mjs` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `8d72f191b9228f8a19ec1ba145755a8cfd7a93e6` |
| `infra/deploy/gce/test_cloud_ops.py` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `4cdc9f05c671bfdd75a7b2775ee292bc254c1129` |
| `infra/deploy/gce/test_publisher_artifact.mjs` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `ae92b91ab5015ec4ca7e268d2712fcd0f06a9a9a` |
| `infra/deploy/gce/test_release_workshop_contract.py` | `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` | `a7c3555187681e52339e18c3d6933edf216f5009` |
| `infra/deploy/gce/publisher_adapters.py` | `101f7d6e2a2795206f16b4419fe561cad531071e` | `33c478264c48685615a8d4d338b5ad5c8a63169b` |
| `infra/deploy/gce/test_publisher_adapters.py` | `101f7d6e2a2795206f16b4419fe561cad531071e` | `8cea6954a8fbb80dadcdee20f4fe8246414e49d5` |
| `infra/deploy/gce/cloud-ops.py` | `101f7d6e2a2795206f16b4419fe561cad531071e` | `ea5facecf4285b7d3366a08e714c1f2137a82623` |

Future merge may add only these historical documentation files byte-for-byte from artifact source:

- `docs/agents/records/2026-11-03-workshop-artifact-boundary-corrections.json`
- `docs/agents/records/2026-11-03-workshop-staging-workflow-regression.json`
- `docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure-preflight.json`
- `docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure.json`
- `docs/agents/records/2026-11-04-workshop-artifact-revalidation-deadline.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-boundary-corrections.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-inspection-close-failure.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-revalidation-deadline.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-staging-workflow-regression.json`
- `docs/superpowers/plans/2026-11-03-workshop-artifact-boundary-corrections.md`
- `docs/superpowers/plans/2026-11-03-workshop-staging-workflow-regression-amendment.md`
- `docs/superpowers/plans/2026-11-04-workshop-artifact-inspection-close-failure.md`
- `docs/superpowers/plans/2026-11-04-workshop-artifact-revalidation-deadline.md`

The only manually resolved path is `docs/operations/workshop-gcp.md`. Keep the complete common prefix, the full Python delivery/correction/SIGTERM sections, the full artifact delivery/workflow/boundary/deadline/close-failure sections, and this Stage0 note; remove only conflict marker lines. No editing historical claims/todos or readiness. The current Stage0 plan/record/task may receive only synchronized tracking/pin and later verification metadata. All other paths must be unchanged from the synchronized checkpoint. No queue change is necessary for this isolated draft; coordinator chooses any separately reviewed queue synchronization before checkpoint pinning.

## Concrete todo

- [ ] After the coordinator releases the serialized tracking slot, synchronize this Stage0-only goal, exact source tuple, allowlists and todo across Issue186/Project8/canonical operations notes; preserve the immediately current full PG index/details verbatim with hashes; commit the synchronized checkpoint and pass full-SHA preflight for independent review and coordinator dispatch.
- [ ] After independent exact-checkpoint review and dispatch, merge only artifact bba43a0675628db3ac90ca7c72bc47eb8c381cb0 into the checkpoint descended from Python 101f7d6e2a2795206f16b4419fe561cad531071e; resolve only docs/operations/workshop-gcp.md by retaining both source histories and the new Stage0 note.
- [ ] Prove every integrated implementation blob equals its selected source, cloud-ops.py and all other implementation files remain unchanged, production jobs and staging blockers retain their reviewed definitions, and all historical gate files retain their original bytes.
- [ ] Run the combined offline Python publisher, cloud/host/workflow and reviewed Node artifact suites plus syntax, exact-scope, diff and pinned-gate checks; record actual results without adding or modifying tests.
- [ ] Commit and push the validated dormant integration milestone for independent exact-SHA review, retaining missing dependency, owner trust, authenticated worker, dependency factory, toolkit advisory/license and staging/production activation blockers.

## Task1: serialized docs-only synchronization

- [ ] Keep this draft unsynchronized until the coordinator releases the tracking slot. Record exact source-review evidence; reject a changed source tuple.
- [ ] Tracking owner snapshots then-current Issue body/full Project index and PG details/exact-pin comments; preserves complete current text verbatim with hashes in the Stage0 synchronization comment, compares current values immediately before write and reads back all new values. Never substitute the stale index carried by either source branch.
- [ ] Update goal/references/todo in Issue/Project/canonical notes and dedicated record/task only after verified readback; set status synchronized only then. Commit/push that docs checkpoint and record its full SHA.
- [ ] Run `python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-04-workshop-publisher-stage0-integration.json --base-sha <full synchronized checkpoint SHA>`. Require exit0 at the pinned committed checkpoint, independent exact-checkpoint review and fresh coordinator dispatch. The historical unsynchronized draft returned nonzero solely for unsynchronized status; require a fresh exit0 at this synchronized committed checkpoint.

## Task2: exact dormant merge after dispatch

- [ ] Confirm clean isolated worktree, exact checkpoint HEAD, passing pinned preflight and coordinator source-review/dispatch evidence. Verify no unrelated PG/branch changes.
- [ ] Run `git merge --no-ff --no-commit bba43a0675628db3ac90ca7c72bc47eb8c381cb0`. This is a future authorized implementation operation, not a command to run while this draft is unsynchronized. Abort if conflicts appear outside `docs/operations/workshop-gcp.md` or implementation differs from selected source blobs.
- [ ] Resolve only the operations append conflict as specified above, retaining both sides and the new Stage0 section. Do not repair code, update lock versions or alter tests. Confirm no conflict markers remain.
- [ ] Compare all selected paths with the map and record. Compare all artifact historical doc additions byte-for-byte to artifact source. Compare every remaining existing path to the synchronized checkpoint; allow only operations-note resolution and current Stage0 verification metadata. Verify there are no extra paths.

Read-only byte-contract check after the future merge:

```python
import hashlib, json, subprocess
from pathlib import Path
record = json.loads(Path('docs/agents/records/2026-11-04-workshop-publisher-stage0-integration.json').read_text())
for filename, expected in record['selected_implementation_blobs'].items():
    actual = Path(filename).read_bytes()
    assert hashlib.sha256(actual).hexdigest() == expected['sha256'], filename
    source = subprocess.check_output(['git', 'show', expected['source_sha'] + ':' + filename])
    assert actual == source, filename
for filename in record['historical_document_additions']:
    assert Path(filename).read_bytes() == subprocess.check_output(['git', 'show', record['artifact_candidate_sha'] + ':' + filename]), filename
workflow = json.loads(Path('.github/workflows/release-workshop.yml').read_text())
source = json.loads(subprocess.check_output(['git', 'show', record['artifact_candidate_sha'] + ':.github/workflows/release-workshop.yml']))
for name in ('publish', 'deploy', 'staging-build-candidate', 'staging-finalize'):
    assert workflow['jobs'][name] == source['jobs'][name], name
```

## Task3: combined offline checks and reviewable milestone

Run only after Task2 is authorized. Do not install dependencies or use ambient Node. Check pinned test binary before execution:

```bash
sha256sum /tmp/autodata-reviewed-node-v22.23.4
```

Require exactly `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`; if absent/different, stop and request the reviewed offline runtime through the coordinator. No automatic download/substitution.

Run the Python suites from `infra/deploy/gce`:

```bash
python3 -m unittest test_publisher_adapters -q
python3 -m unittest test_cloud_ops test_host_runtime test_release_workshop_contract -q
```

Run the Node suite and syntax checks from the repository root. The tests spawn `infra/deploy/gce/publisher_artifact.mjs` relative to their current working directory; running them from `infra/deploy/gce` causes the two CLI-denial checks to fail before exercising the intended helper.

```bash
/tmp/autodata-reviewed-node-v22.23.4 --test infra/deploy/gce/test_publisher_artifact.mjs
/tmp/autodata-reviewed-node-v22.23.4 --check infra/deploy/gce/publisher_artifact.mjs
/tmp/autodata-reviewed-node-v22.23.4 --check infra/deploy/gce/test_publisher_artifact.mjs
```

These existing suites exercise owner-pin denial, FIFO-safe reads, Python SIGTERM child mask/races/cleanup, JS cancellation-before-spawn and late-open failed-close cleanup, strict workflow authority and host default denial. Offline fixtures must remain fixtures; do not invoke installed SDK/toolkit or real provider transports. Capture actual counts/results at the merged SHA; historical183/103/143 counts are not new acceptance evidence.

Run `git diff --check` and exact-scope/blob checks against the synchronized checkpoint, plus its pinned preflight. Confirm no installs/untracked implementation outputs and no production/staging blocker changes. Record commands/results/source tuple/implementation SHA and retained blockers in Stage0 evidence metadata/canonical note. Commit the exact merge as one coherent dormant integration milestone, promptly push the assigned branch only after checks pass, and obtain independent exact-SHA review. No merge to master or activation follows automatically.

## Remaining blocked gates

Concrete dependency factory/fixed entrypoint, authenticated owner-policy loading, runtime-token identity verification, actual official upload worker/private IPC import/call, GitHub raw REST and OCI transports, WIF exchange, clean isolated Buildx execution, Syft/Cosign signing and independent attempt-bearing certificate/transparency verification, immutable candidate/approval storage and deadline-bound fixed IAP executor remain uninstalled. Seven moderate toolkit advisories and buffers licensing, immutable installed-tree/runtime/helper pins, exact owner trust/identity/IAM tuple and real Actions size/digest semantics remain blockers. PG17 acceptance/image release, host lifecycle and all staging/production activation remain separate gates. Stage0 does not close any of them.

## Verified Stage0 tracking synchronization

Readback verified 2026-11-04T04:07:54.663787+00:00. Issue detail https://github.com/lucronn/autodata/issues/186#issuecomment-6622268742; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`. Prior full Project index SHA256 `acfd6664aec1798bf581fed620f185faf4155896ddb77674664ea7d1b2a9b33a`; current text SHA256 `cc28ab97ee9d02b678552c2303171b73b6e528c88d8ed5ed79d1ffc049649b07`. Canonical full-text/hash evidence: `docs/agents/records/2026-11-04-workshop-publisher-stage0-integration-evidence.json`. Staging M1 detail/pin6622232881/6622247097, PG detail/pin6622201950/6622210398 and artifact detail/pin6622115738/6622126651 are preserved verbatim/hash in that file and the linked preservation comments. Existing Issue body is unchanged; the new Issue comment contains the current Stage0 goal/references/todo. No prior record status or execution denial is reinterpreted. Corrected local draft `c2ebdbc10780523ce486ed293a92f88674abdfff` passed independent scoped review; exact committed synchronized checkpoint review and coordinator dispatch remain pending. No implementation merge or runtime operation occurred.
