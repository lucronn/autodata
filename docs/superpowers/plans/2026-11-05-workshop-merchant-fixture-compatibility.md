# Workshop merchant fixture compatibility implementation plan (Task61) — planning synchronized

> **For agentic workers:** Execute only after the canonical gate, independent checkpoint review and explicit coordinator three-path dispatch. Use superpowers:executing-plans task by task; planning/tracking status is synchronized; execution remains blocked.

**Goal:** Isolate historical Task54 merchant-preparation fixtures from the evolving application tree, preserving the exact validator contract and Task59 server-owned configuration authority.

**Architecture:** Keep the Task54 offline evaluator frozen. Archive its historical embed and disabled JSON test inputs under scripts/dev, point only the test module at those inputs, and preserve the live Dockerfile pin. Current Go/Python runtime authority remains exactly Task59's server-owned route.

**Tech Stack:** Python unittest/hashlib, exact git blobs, Go1.26.4 and Node22.23.1 regressions.

**Spec:** `docs/agents/specs/2026-11-05-workshop-merchant-fixture-compatibility.json`

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Gate and evidence boundaries

Planning/tracking synchronized by root; execution remains blocked. All authorities false; current_implementation_allowlist=[]; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Root authorized only eight-document planning checkpoint commit/push. Implementation and GitHub Issue/Project writes are not authorized. A planning checkpoint does not authorize merge/deployment/live sales.

Materialization parent/source: `8d9f1a379924ae6636369e4b3b8e01ab6c258ccb` / tree `ea2992091f0d00e10d3aa89f967ba735176f284d`. Preserve Task59 gate c62c37772730d9ce46b7947030410492845d741b and all its task/source evidence as historical dependency. Gate and implementation PRs should target `codex/workshop-purchase-config-code` where possible to isolate eight-document and three-path diffs; no merge.

Diagnosis: `/home/corp/autodata-evidence/task61-merchant-compat-diagnosis/REPORT.md`, SHA256 `eedb7510faa232e046c25b2e41f6c8ebcab7600525d73f852345369f3869a625`. The exact source reproduces20 tests/24 failures/1 error: success fixtures read changed live main.go and one baseline test reads intentionally deleted JSON. The offline evaluator is correct. Historical Task58 had20/20 green; that is not repaired-source evidence. Failed CI41975141600 had603 tests/24 failures/1 error. Fresh Task59 runs41976449833/41976455204 were in progress in diagnosis; no terminal success is asserted.

## Exact paths

Eight gate documents only:
- `docs/superpowers/plans/2026-11-05-workshop-merchant-fixture-compatibility.md`
- `docs/agents/specs/2026-11-05-workshop-merchant-fixture-compatibility.json`
- `docs/agents/records/2026-11-05-workshop-merchant-fixture-compatibility.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-merchant-fixture-compatibility.json`
- `docs/verification/2026-11-05-workshop-merchant-fixture-compatibility.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/architecture/workshop-commerce.md`
- `docs/verification/workshop-commerce-runbook.md`

Three future implementation paths only:
- `scripts/dev/test_workshop_merchant_manifest.py`
- `scripts/dev/fixtures/workshop_merchant_manifest/historical-main.go.txt`
- `scripts/dev/fixtures/workshop_merchant_manifest/historical-disabled-purchase-config.json`

## Literal todo

1. Independently review the exact Task59 merchant-test failures and historical fixture isolation design, freezing the three implementation paths and preserving prior task/queue/source evidence and credit0 release limits.
2. Synchronize this goal, six todos, eight gate paths and three implementation paths in Issue186/Project8 with preservation readbacks; commit/push the planning checkpoint, externally seal its actual SHA/tree, pass exact-base standalone/nested preflights and obtain independent checkpoint review plus explicit dispatch before implementation.
3. Record the exact-base failing merchant regression, add verbatim independently pinned historical embed/disabled fixtures while retaining the unchanged live Dockerfile pin and point tests at them, retaining all strict provenance/URL/byte/read-only/fail-closed tests and explicit current-source pin-mismatch rejection.
4. Prove focused red/green and full developer discovery, unchanged current Go dynamic-route and Node regressions, exact scope/fixture/evaluator/protected-source checks and honest failures/skips with no merchant or acceptance credit.
5. Commit and promptly push validated coherent milestones on the assigned branch, obtain independent exact-source review and fresh source-push plus actual-PR CI terminal required-job/live-Compose success.
6. Synchronize verified source and remaining protected configuration delivery, owner/legal/tax/secret/Firebase/Stripe, authentic TEST/runtime/staging/release blockers while retaining all authorities false, accepted_case_credit0, accepted_new_case_credit0, verified_case_ids[] and release_state:unverified.

## Frozen contract and fair verification

The merchant module remains an inert offline preparation CLI; no automated production/build caller was found in the examined source. A human may invoke it manually. The declared served URL is unchanged; it does not imply a network request or runtime recognition. Historical SOURCE remains6949eb1b1a5b93c9b2eb0579328e24c697f6f331/tree47ec54b1896c83a39b6637a6ce944d3620414f4e. Do not present archived two-file bindings as Task59 runtime provenance.

Copy both archived fixtures verbatim from b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb blobs. historical-main.go.txt is30491 bytes SHA2566a6c78c4d84604ec4e626b49dc10e20603018e9db398c709073e689723801a77; historical-disabled-purchase-config.json is168 bytes SHA256edb1d6d182c5eeee6c33885e873bc5b44ac7a3eb4465d9e92af5d1bc60d4b45f. Both modes100644. Keep current Dockerfile read and independent928-byte SHA256bd7a4d022e89c76432cd5b8e086166252303710cb8cb24a72b5eeff31fc52559 assertion. A future Dockerfile edit requires its own reviewed pin/fixture decision.

Do not edit scripts/dev/workshop_merchant_manifest.py. SOURCE/BUILD/EMBED/BASELINE, schema/output/reasons/CLI exits/prerequisites and all fail-closed protections remain byte-identical. Preserve bounded reads, regular-file/no-symlink directory descriptors and swaps, read-only tests, strict JSON, UTF-8/tax-byte checks, source/tree literals, independent hashlib calculations and provenance/URL matrices. Reserved URLs remain synthetic-only; owner_supplied_unverified still rejects reserved/local/IP/fixture URLs and proves no authenticity. No normalize/fetch/environment/subprocess/default-output/enable/approval behavior is added.

Keep prepared_offline successes deterministic with reasons=[], all authorities false, accepted_case_credit0 and every external prerequisite. Genuine historical disabled bytes remain blocked with merchant_inputs_pending. Retain all168 one-bit mutations and baseline_disabled=False checks. Rename/comment the baseline test as historical exact-byte recognition. Label both fixtures archived disabled non-deployable test inputs with source provenance; JSON must stay outside workshop embed and must never restore the removed shipped asset.

## Task1: Seal the planning boundary

- [x] Independently review this draft and exact diagnosis/scope/pins (root PASS15).
- [x] Root synchronizes literal goal/six todos/eight gate paths/three implementation paths in Issue186/Project8, retaining issue body/comments/other project fields and prior field text with fresh before/after ownership/literal preservation readbacks (comment6650911660/Project8, PASS10). Planning agent performs no GitHub write.
- [ ] Only after verified readback change standalone and nested records to synchronized identically, commit/push the eight gate paths, externally seal actual full SHA/tree; never put a checkpoint self-hash in predecessor bytes.
- [ ] Pass standalone and nested machine preflights at the actual checkpoint errors=[], independently review checkpoint, then obtain explicit coordinator three-path implementation dispatch. Empty current allowlist and false authorities remain until dispatch.

## Task2: Reproduce and repair historical inputs

Files: modify scripts/dev/test_workshop_merchant_manifest.py; add only the two listed scripts/dev fixtures.

- [ ] Record sealed exact base SHA/tree and pinned runtime paths/versions; run the focused command before editing. Save real24-failure/1-error red and nominal embed_source_binding_mismatch; a different failure requires diagnosis before edits.
- [ ] Extract exact reviewed historical git blobs, without normalization or runtime generation:

```python
import subprocess
from pathlib import Path
historical = 'b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb'
folder = Path('scripts/dev/fixtures/workshop_merchant_manifest')
folder.mkdir(parents=True, exist_ok=True)
for source, name in [('apps/api-go/main.go', 'historical-main.go.txt'), ('apps/api-go/workshop/purchase-config.json', 'historical-disabled-purchase-config.json')]:
    raw = subprocess.check_output(['git', 'show', historical+':'+source])
    target = folder/name
    target.write_bytes(raw)
    target.chmod(0o644)
```

This extraction is an implementation-time command after dispatch, never test runtime. Independently verify exact hashes/lengths against the literal spec before the tests use them.

- [ ] Define `FIXTURES = ROOT/'scripts/dev/fixtures/workshop_merchant_manifest'`. Change setUp embed read to `(FIXTURES/'historical-main.go.txt').read_bytes()` and baseline read to `(FIXTURES/'historical-disabled-purchase-config.json').read_bytes()`. Retain live Dockerfile read and existing independent hashes/lengths; add provenance comments and historical baseline test name.
- [ ] Add current-source mismatch regression within PreparationTests:

```python
def test_current_embed_cannot_self_admit_historical_binding(self):
    current = (ROOT/'apps/api-go/main.go').read_bytes()
    self.assertEqual(binding(current), {'sha256': 'fde8eac2c45e27d7fcf07fd72dcf406453009a7d92689ddd62f4521b7d7045b8', 'bytes': 30989})
    self.paths['embed_source'].write_bytes(current)
    result = self.evaluate()
    self.assertEqual(result['status'], 'blocked')
    self.assertIn('embed_source_binding_mismatch', result['reasons'])
    self.approval['embed_source'] = binding(current)
    self.paths['approval'].write_bytes(encoded(self.approval))
    result = self.evaluate()
    self.assertEqual(result['status'], 'blocked')
    self.assertIn('embed_source_binding_mismatch', result['reasons'])
```

- [ ] Rerun identical focused command to21-or-more tests green/no skips, nominal reasons=[] and explicit mismatch reason; preserve raw red/green and exact identities.

## Task3: Verify and hand off exact source

- [ ] Run all verification commands below and retain raw logs/counts/failures/skips. Full developer discovery is mandatory because it is the failing CI boundary. Runtime disabled route coverage remains current Go coverage; archival JSON is never runtime evidence.
- [ ] Inspect exact three-path implementation diff, fixture hash/length/mode, byte identity of evaluator, every Task59 application path, Dockerfile, policy/workflow/collectors/supervisor and all prior task records. Any wider diff stops for a separate amendment.
- [ ] Commit small coherent validated milestones and promptly push only the assigned branch after dispatch; retain independently reviewable commits. Obtain independent exact-source review and fresh source-push/actual-PR checkout terminal required-job/live-Compose smoke success with SHA/tree. Historical/in-progress CI cannot substitute. External deployment/check failures are reported separately.
- [ ] Root synchronizes verified source and remaining blockers; no merge/deployment/merchant/acceptance credit is inferred.

## Exact source verification commands

Record `/usr/bin/python3 --version`, `/home/corp/go-sdk/bin/go version` (go1.26.4 linux/amd64), `/home/corp/.local/bin/node --version` (v22.23.1). These paths were inspected read-only for planning; no task tests were run by planning.

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s scripts/dev -p test_workshop_merchant_manifest.py -v
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s scripts/dev -p 'test_*.py' -v
env -u AUTODATA_PURCHASE_CONFIG_GO_BRIDGE -u AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION /home/corp/go-sdk/bin/go -C apps/api-go test -count=1 -run 'Workshop|PurchaseConfig|CommerceClient' ./...
/home/corp/.local/bin/node --test apps/api-go/workshop-client.test.mjs
/home/corp/.local/bin/node --check apps/api-go/workshop/app.mjs
git diff --check
```

Dedicated Task59 integration flags remain absent during ordinary Go regression; preserve named skips/reasons and never claim acceptance from skips. Existing required integrations retain their own runbooks/dispatch and skip semantics; unavailable required integrations remain unmet. Do not replace Task59's dynamic-route or authority integration coverage with fixture tests.

## Protected remaining blockers

- Task61 planning/tracking synchronized by root with literal Issue186 comment6650911660/Project8 readback, independent draft PASS15 and preservation PASS10. Only eight-document checkpoint commit/push authorized. External actual SHA/tree seal, standalone+nested exact-checkpoint preflights errors=[], independent checkpoint review and explicit three-path implementation dispatch remain required. Execution blocked; all authorities false/current implementation allowlist empty; no predecessor self-hash.
- Owner-approved actual terms/privacy/refund/contact content and URLs, support identity and truthful single-line tax notice are absent; synthetic tests cannot approve legal content or domain ownership.
- Tax obligations and inclusion within exactly USD20 total require owner/adviser decision; adding tax on top requires separately reviewed financial-contract change.
- Production closed schema/renderer/config-hash delivery does not yet pass AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON; a separately owned synchronized deployment-config follow-up is mandatory. No hand-edited container environment or hash bypass.
- Actual Firebase project/Google provider/authorized domains, Stripe merchant/price/account/webhook and secret delivery remain owner/protected-release inputs; no real credentials belong in this gate.
- Purchase pause takes effect after coordinated commerce process replacement; fleet drain/replacement and compatible rollback must be separately proved. Old enabled binaries/replicas and issued Stripe URLs retain stated limitations.
- Authentic identity/payment/staging/restore/host/TLS, real API21/DTO120/same-candidate final180, runtime ownership/watchdog/observer/raw-capture/trace16MiB-versus8MiB proof and protected merge/deployment/release remain unverified.
- cars.tk DNS provider is Vercel by trusted coordinator/user direction; no DNS or cloud operation is authorized.

## Canonical pre-implementation record (planning synchronized; execution blocked)

```json
{
  "goal": "Isolate historical Task54 merchant-preparation fixtures from the evolving application tree, preserving the exact validator contract and Task59 server-owned configuration authority.",
  "plan_ref": "docs/superpowers/plans/2026-11-05-workshop-merchant-fixture-compatibility.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/specs/2026-11-05-workshop-merchant-fixture-compatibility.json",
    "docs/verification/2026-11-05-workshop-merchant-fixture-compatibility.md",
    "docs/architecture/workshop-commerce.md",
    "docs/verification/workshop-commerce-runbook.md"
  ],
  "todo": [
    "Independently review the exact Task59 merchant-test failures and historical fixture isolation design, freezing the three implementation paths and preserving prior task/queue/source evidence and credit0 release limits.",
    "Synchronize this goal, six todos, eight gate paths and three implementation paths in Issue186/Project8 with preservation readbacks; commit/push the planning checkpoint, externally seal its actual SHA/tree, pass exact-base standalone/nested preflights and obtain independent checkpoint review plus explicit dispatch before implementation.",
    "Record the exact-base failing merchant regression, add verbatim independently pinned historical embed/disabled fixtures while retaining the unchanged live Dockerfile pin and point tests at them, retaining all strict provenance/URL/byte/read-only/fail-closed tests and explicit current-source pin-mismatch rejection.",
    "Prove focused red/green and full developer discovery, unchanged current Go dynamic-route and Node regressions, exact scope/fixture/evaluator/protected-source checks and honest failures/skips with no merchant or acceptance credit.",
    "Commit and promptly push validated coherent milestones on the assigned branch, obtain independent exact-source review and fresh source-push plus actual-PR CI terminal required-job/live-Compose success.",
    "Synchronize verified source and remaining protected configuration delivery, owner/legal/tax/secret/Firebase/Stripe, authentic TEST/runtime/staging/release blockers while retaining all authorities false, accepted_case_credit0, accepted_new_case_credit0, verified_case_ids[] and release_state:unverified."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-05T05:56:49Z"
}
```

## Root tracking synchronization evidence

Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6650911660 and Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4 contain the literal goal/six todos/eight gate paths/three implementation paths. Root independent draft review PASS15 and before/after preservation PASS10 completed. Evidence refs/hashes and actual UTC are in spec/task tracking_sync. Prior issue body/comments, other Project fields and prior Source text were preserved. The actual checkpoint seal belongs externally after commit; current checkpoint fields remain null.
