# Workshop Smoke Timeout Assertion Implementation Plan — Task57 Synchronized Planning Checkpoint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this single task after the synchronized gate passes. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align only the existing ingestion-smoke workflow timeout assertion with the reviewed 30-minute autonomy-policy budget on the exact Task56 combined source, preserving every other byte and every runtime, acceptance and release block.

**Architecture:** One existing source-contract assertion is stale after the reviewed Task55 workflow budget change. Replace only its literal timeout20 with timeout30 on exact Task56 combined source; freeze every other byte and authority.

**Tech Stack:** Python unittest, existing YAML workflow, Git immutable objects, canonical gate validator.

**Spec:** `docs/agents/specs/2026-11-05-workshop-smoke-timeout-assertion.json`.

Issue: https://github.com/lucronn/autodata/issues/186. Project: https://github.com/users/lucronn/projects/8, existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

Planning/tracking synchronized; execution blocked. No checkpoint seal, positive exact-checkpoint preflight or dispatch exists. All authorities false, current implementation allowlist empty, credits0, verified IDs[], release unverified.

## Global Constraints

- Exact planning parent `209aa420b391dc81275b0178fd8988a61f591cb7`, tree `ef740d24e7348f358c445aaf9c050bd30c097ff5`; no Task56 code-worktree edit.
- Task56 independent source/diff review PASS: `/home/corp/autodata-evidence/task56-integration-final-review/REPORT.md`, SHA256 `d34316c1e3948c8672a45ee842e94a95a3ece076d578e9673fdfea8ac808ec2a`. It certifies no final full-suite or CI success.
- The stale assertion at `scripts/dev/test_ingestion_smoke.py:58` has been independently reproduced on clean exact Task56 source. Task56 remaining full-suite/CI inventory is pending and confers no inherited success; its terminal completion is not required before Task57 synchronization or dispatch. Any additional defect requires a separate synchronized gate.
- Sole future implementation path `scripts/dev/test_ingestion_smoke.py`, sole old/new line below. Current allowlist remains empty until explicit dispatch.
- Existing workflow remains byte-identical at autonomy-policy30, DTO100/exercise85, R3 5; R6 hash/enabled=false and all other Task56 source remain byte-identical.
- Preserve all first56 queue task raw objects/order/separators and all root bytes. Append only Task57; entire queue then remains sealed-checkpoint-identical through implementation.
- accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. No deployment, release, protected merge, local services, providers or CI execution authority in this draft.

## Literal todo

- [ ] Independently review exact Task56 code 209aa420b391dc81275b0178fd8988a61f591cb7/tree ef740d24e7348f358c445aaf9c050bd30c097ff5, its retained final code-review receipt and the independently reproduced clean-source stale assertion; freeze only scripts/dev/test_ingestion_smoke.py line58 timeout-minutes: 20 to timeout-minutes: 30. Task56 remaining full-suite/CI inventory is not a Task57 synchronization or dispatch prerequisite and confers no inherited success; any additional defect requires a separate synchronized gate.
- [ ] Synchronize this literal goal, six todos, six gate paths and sole implementation path in Issue186/Project8 with fresh before/after preservation readbacks; preserve all prior56 queue objects and root bytes, commit/push only the synchronized checkpoint rooted at exact Task56 code, externally seal its actual SHA/tree, and require standalone/nested exact-checkpoint preflights errors=[] plus independent checkpoint review before explicit coordinator dispatch.
- [ ] Reproduce the existing focused workflow-contract assertion failure before repair, then replace only the sole exact line58 assertion string timeout-minutes: 20 with timeout-minutes: 30 in scripts/dev/test_ingestion_smoke.py; preserve every other file byte, the reviewed workflow30/DTO100/exercise85/R3 5, R6 hash binding and all existing assertions, tests and smoke cleanup.
- [ ] Require the focused assertion and complete ingestion-smoke module green, rerun the full developer/autonomy suites and frozen Task56 offline combined checks on the exact candidate, retain actual commands/counts/skips/failures/exits and verify the deterministic one-line diff; stop for a new gate on any extra repair or path.
- [ ] Commit and promptly push the validated one-line milestone under coordinator branch ownership, obtain independent exact-code/diff review, and require fresh corrected source-push and actual PR-checkout Autonomous Verification terminal success for all three jobs and the complete live Compose step; bind logs and artifacts to actual checkout SHA/tree and report ordinary skips and external Vercel status separately.
- [ ] Keep accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[] and release_state=unverified; leave owner policy/tax, merchant manifest injection/rebuild and artifact/served-byte proof, provider/Firebase/Stripe TEST enrollment, source/runtime admission, supervisor timing, real API21/DTO120/final180 acceptance, host/services, DNS, staging, protected merge, deployment and release behind separate measured gates.

## Six-document checkpoint scope

- `docs/superpowers/plans/2026-11-05-workshop-smoke-timeout-assertion.md`
- `docs/agents/specs/2026-11-05-workshop-smoke-timeout-assertion.json`
- `docs/agents/records/2026-11-05-workshop-smoke-timeout-assertion.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-smoke-timeout-assertion.json`
- `docs/verification/2026-11-05-workshop-smoke-timeout-assertion.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`

## Task 1: Synchronize, seal and repair the single stale assertion

**Files:** Six gate documents above; after dispatch modify only `scripts/dev/test_ingestion_smoke.py:58`.
**Interfaces:** Consumes exact Task56 source, preserved workflow digest and canonical preflight. Produces deterministic corrected test bytes and evidence only; no application/runtime interface changes.

- [ ] Independently inspect the clean exact Task56 source and retained focused stale-assertion reproduction. Freeze the sole one-character repair below. Task56 remaining full-suite/CI results confer no inherited success and are not prerequisites for Task57 synchronization or dispatch; any additional defect or repair needs a separate synchronized gate.
- [ ] Coordinator archives fresh Issue186/Project8 before state, verifies item ownership, adds this literal goal/six todos/six gate paths/one implementation path and exact byte constraint, preserving Issue body/prior comments/other Project fields and prior Project Source verbatim. Retain fresh after snapshots and exact matching readback. Only then set standalone/nested and Task57 spec/task/queue statuses consistently to synchronized with actual tracking evidence and UTC time; leave old56/root bytes unchanged.
- [ ] Commit/push only six gate paths on assigned gate branch rooted at exact parent. Externally seal actual checkpoint SHA/tree; never guess or embed a future commit. Extract policy and both records from that checkpoint and require both errors=[] plus independent exact checkpoint PASS before explicit coordinator one-path dispatch.

```sh
python3 - "$TASK57_GATE_SHA" <<'PY_PREFLIGHT'
import json,pathlib,subprocess,sys
from scripts.autonomy.pre_implementation import validate_record
sha=sys.argv[1]; repo=pathlib.Path('.').resolve()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
def read(path): return json.loads(subprocess.check_output(['git','show',f'{sha}:{path}']))
policy=read('.autodata-autonomy-policy.json')
standalone=read('docs/agents/records/2026-11-05-workshop-smoke-timeout-assertion.json')
nested=read('docs/agents/tasks/2026-11-03-production-release/workshop-smoke-timeout-assertion.json')['pre_implementation_record']
errors={name:validate_record(record,repo,sha,policy) for name,record in [('standalone',standalone),('nested',nested)]}
print(json.dumps({'base_sha':sha,'errors':errors},indent=2))
assert errors=={'standalone':[],'nested':[]}
PY_PREFLIGHT
```

- [ ] In separately assigned clean implementation checkout at sealed checkpoint, run the first focused command below before repair. Expected failure is the existing missing `timeout-minutes: 20` assertion; a dependency/import failure is not the expected red receipt. Use existing provisioned dependencies; no install or services implied. Retain stdout/stderr/exit and exact source SHA/tree.
- [ ] Replace only this exact line (parent line58):

```diff
-        self.assertIn("timeout-minutes: 20", workflow)
+        self.assertIn("timeout-minutes: 30", workflow)
```

Original file: blob `c4513119139c0ef0e2dfa5f505cd9554d5a20035`, SHA256 `95e1aabe49bc702133f6f7cbe1749bd0423582b6694185da988b0b690055edae`, 5369 bytes. Expected corrected file: blob `a82f48ad546feef950b335823b25ba90fd8ef6d7`, SHA256 `ec50bedac82105f54d894c5a18ecd535603c26cc2eac42050b6d823627cc5a39`, 5369 bytes. Compute in memory from original bytes; verify exactly one original-line occurrence and every other byte/mode unchanged. No test creation/deletion/skip/weakening or workflow edit is admitted.
- [ ] Require focused assertion and complete module green; run all commands below with retained actual command/env/tool versions, collected/executed counts, ordinary skips, failures and exits. Use the available recorded Go SDK if required; missing dependencies/tools or failures block, never count as success. Frozen Task56 commands are repeated explicitly so a builder need not infer the inventory. No local real integration flags, service startup or authentic acceptance is admitted.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=workers/ingestion-python/src:packages/contracts/python python3 -B -m unittest scripts.dev.test_ingestion_smoke.IngestionSmokeContractTests.test_protected_workflow_runs_live_fast_lane_smoke_with_cleanup -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=workers/ingestion-python/src:packages/contracts/python python3 -B -m unittest scripts.dev.test_ingestion_smoke -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.dev.test_workshop_browser_smoke.DTOWorkflowBindingTests.test_dto_job_matches_shared_contract_and_disabled_r6_hash -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.dev.test_workshop_browser_smoke -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.dev.test_release_acceptance -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scripts/dev -p test_workshop_merchant_manifest.py -v
env -u AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION -u AUTODATA_LIFECYCLE_TEST -u AUTODATA_WORKSHOP_BROWSER_CHILD PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=scripts/dev python3 -B -m pytest -q -p no:cacheprovider --collect-only scripts/dev/test_workshop_browser_environment.py scripts/dev/test_workshop_browser_execution_contract.py scripts/dev/test_workshop_browser_execution_evidence.py scripts/dev/test_workshop_browser_execution_supervisor.py scripts/dev/test_workshop_browser_preparation_probe.py
env -u AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION -u AUTODATA_LIFECYCLE_TEST -u AUTODATA_WORKSHOP_BROWSER_CHILD PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=scripts/dev python3 -B -m pytest -q -p no:cacheprovider scripts/dev/test_workshop_browser_environment.py scripts/dev/test_workshop_browser_execution_contract.py scripts/dev/test_workshop_browser_execution_evidence.py scripts/dev/test_workshop_browser_execution_supervisor.py scripts/dev/test_workshop_browser_preparation_probe.py
env -u AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION -u AUTODATA_LIFECYCLE_TEST -u AUTODATA_WORKSHOP_BROWSER_CHILD PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -B -m pytest -q -p no:cacheprovider --confcutdir=workers/ingestion-python/tests workers/ingestion-python/tests/test_workshop_browser_observability.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scripts/autonomy -p "test_*.py" -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=workers/ingestion-python/src:packages/contracts/python python3 -B -m unittest discover -s scripts/dev -p "test_*.py" -v
node --test apps/api-go/workshop-client.test.mjs
node --check apps/api-go/workshop/app.mjs
go -C apps/api-go test ./...
git diff --check
```

- [ ] Compare complete recursive tree to sealed checkpoint: exactly `scripts/dev/test_ingestion_smoke.py` differs and equals frozen expected blob; queue, six gate documents, policy, workflow, R6 and every other path/mode equal checkpoint. Obtain independent exact-code/diff review, commit/push the validated one-line milestone under coordinator branch ownership, and retain the exact final SHA/tree. Any additional failure requires new gated scope.
- [ ] Under explicit coordinator CI dispatch, require fresh corrected-source push and actual PR-checkout Autonomous Verification success for all three jobs and `Run live Compose fast-lane smoke`; preserve all workflow steps/commands. Retain actual per-job checkout SHA/tree/logs, PR commit parents/tree and DTO artifact ZIP digests/original receipts/timing/source bindings. PR metadata head_sha alone is insufficient; if actual PR tree differs, review/test it or block/replan. Ordinary skipped integrations and external Vercel failures stay separately reported; cancelled/timed-out/skipped required steps never pass. No Task56 or isolated lane success substitutes.
- [ ] Coordinator appends exact final evidence to Issue/Project with credits0 and release unverified. DTO120 stays synthetic fixture/source smoke; R3 stays synthetic/owned-child. Local full-suite green alone does not admit source, runtime, acceptance or release.

## Remaining boundaries

- No real provider credentials/enrollment, Firebase identity project/configuration or authentic Stripe TEST account/Price/checkout/webhook/durable grant/duplicate/revocation evidence is admitted; stripe_live/live sales remain blocked.
- Owner must independently approve exact Terms/Privacy/Refund/Contact URLs and snapshot bytes and tax/final USD20 price treatment. prepared_offline proves supplied-byte consistency only. The shipped 168-byte disabled manifest remains unchanged; no injection/rebuild, immutable OCI/binary/served-byte artifact admission is authorized.
- Task52 v2 remains internal, unavailable, complete=false, credits0 and verified IDs empty; historical v1/public CLI exit3/profiles unchanged. Task53 static contract pins Task51 product6949/tree47ec; combined tooling SHA never silently rebinds the producer/product source.
- Unchanged supervisor dto_running=4560s versus compiler command ceiling5100s and whole attempt7500s is an explicit unresolved runtime blocker. No timer repair, runtime observer/admission, containment/watchdog or real API finite-success proof is admitted. Producer trace16MiB versus consumer8MiB and original authenticated JUnit/log capture remain blocked.
- No real API21, DTO120 or same-candidate final180 acceptance is established. DTO CI is synthetic fixture/source smoke only, even when all120 rows pass; R3 CI is synthetic/owned-child preparation only. Local Compose smoke is CI infrastructure proof, not authentic staging/provider/customer acceptance.
- cars.tk DNS is Vercel-managed and owner can change it; this is owner-provided planning context. External Vercel deployment/rate-limit failures remain separate from Actions success and prohibit a full green rollup claim while failing. No Vercel setting/retry/hosting, host execution, Docker/services, DNS, staging, protected-branch merge, deployment, cutover or release authority follows.

## Coordinator tracking readback — planning synchronized

Issue comment https://github.com/lucronn/autodata/issues/186#issuecomment-6649804778 at 2026-11-05T04:37:08Z records the literal goal, six todos, six gate paths, sole implementation path and exact line58 byte constraint. Before snapshot `/home/corp/autodata-evidence/task57-before-tracking.json` SHA256 `2b684f5cdf9ebd1a18b8de1633e72350baf9568eb36359c3f0b045b9e2b30dbe`; after snapshot `/home/corp/autodata-evidence/task57-after-tracking.json` SHA256 `cef0003e2253ebef31627ea17045058e87f0aa8360a04ad9f8f32e6c9526c99b`. Issue body, prior255 comments and other Project fields are unchanged; prior Project Source is archived verbatim in the comment. Project Source after SHA256 `8edb13185d2da2f79ee24adead6fa8254820024bacc301d21f969e43d3052a35`. Independent revised-draft PASS report `/home/corp/autodata-evidence/task57-smoke-timeout-assertion-draft-review/REPORT.md` SHA256 `351654845ea9128827dcb13b041bf35cf6130a775ee34e6bb974ab5a27f76052`.

Standalone/nested records and Task57 spec/task/queue planning/tracking status are synchronized at 2026-11-05T04:37:08Z; execution remains blocked, all authorities false and current implementation allowlist empty. Credits0, verified IDs[], release unverified. Exact checkpoint commit/push, external actual SHA/tree seal, dual exact-checkpoint preflights, independent checkpoint review and explicit coordinator one-path dispatch remain required. Task56 remaining full-suite/CI inventory is pending and provides no inherited success; terminal completion is not a Task57 synchronization or dispatch prerequisite. Any additional defect requires a separate synchronized gate.
