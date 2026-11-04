# Workshop final180 CI-integration fixture-isolation specification

**Status:** Issue186/Project8 planning `synchronized` with live readback at https://github.com/lucronn/autodata/issues/186#issuecomment-6638503013. The coordinator preserved all 160 prior comments, now 161, the Issue body and unrelated Project fields, and archived the prior Project Source verbatim. Independent pre-sync five-file draft review PASS with no findings is coordinator-reported. Committed-checkpoint preflight, independent exact-checkpoint review and explicit builder dispatch remain required; none is asserted by tracking synchronization.

**Goal:** Carry the exact Stage A CI Git-metadata test-fixture isolation repair into the reviewed B2 stack without changing production behavior or earning runtime acceptance credit.

**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8

**Exact planning parent / reviewed B2 head:** `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471` on `codex/workshop-final180-stage-b2-build`, draft PR https://github.com/lucronn/autodata/pull/230. Independent exact-head review PASS with no findings is coordinator-reported; this successor requires a separate exact-checkpoint review. **Application candidate remains:** `4d82e413e04fb2401ac7bc28dc828375ac662180`. This CI integration changes tooling tests, not candidate identity.

## Scope and invariants

- Implementation allowlist is exactly `scripts/dev/test_workshop_final180_runner.py` and `docs/verification/workshop-final180-runbook.md`.
- Test repair is byte-for-byte the pinned source version of the one test file; do not cherry-pick unrelated history or broaden the patch.
- ProductionGitReader and all Stage A runner/B1/B2 adapters and their tests other than the listed Stage A test file remain byte-identical to the reviewed B2 head. Do not change workflows or configure away CI checkout credentials.
- accepted_case_credit is exact integer0; profiles_enabled=false; enabled_tiers=[]; runtime_lock=null; run_record=null.
- All nine authority flags remain false: fixture_verified, product_candidate_verified, staging_verified, deployment_authorized, cutover_verified, implementation_authorized, runtime_execution_authorized, profile_promotion_authorized, merge_authorized.
- Offline test subprocesses exercise only the fixed host Git executable and owned metadata; no fixture/application/Go/provider runtime, Docker, browser, network or payment execution is authorized by this plan. GitHub CI readback is evidence retrieval, not runtime admission.
- Complete raw validators, JUnit/result/process/environment/manifest bindings, dynamic-support inventory, genuine same-head180, source/bank attribution, real supervisor provenance, profiles, images/security/SDK/license/staging/live/release gates remain separate.

## Live tracking receipt

The coordinator is the sole serialized GitHub writer. Saved receipt `/home/corp/autodata-evidence/final180-ci-integration-tracking/receipt.json` records `synchronized_live_readback`; its saved before/after hashes were verified during checkpoint preparation. Issue after SHA256 `b52fbb3d7a7a9b8ea543984133153793b3cc7abff119d69078179e46f106a750`; Project after SHA256 `5e85f52638b718d743c567d8bdb13ae8c61c64fc08cf1850ca148232415b948d`; current Project Source SHA256 `818d5bf9c5dd574c09816cd7c93db0549b37519a78437a7ff1023409cd02f5e9`; prior Project Source SHA256 `08e8c676cd8bb03f65ef29a6209da6fd0962a8b376df1b79632eaef4d7d10e14`. Project remains In Progress. The standalone record and identical nested task record retain full receipts, references and source hashes. No checkpoint review, implementation dispatch or runtime authority follows from this receipt.

## CI evidence and diagnosis

Historical pre-sync draft verification executed the contaminated-checkout regression against unchanged B2 source and confirmed exactly ten ProductionGitTests setup `git_config` errors (exit1). No implementation patch was applied. JSON/nested-record equality, all nine false authority values, source/hash/merge-base pins, embedded Python syntax, exact five planning paths and append-only79030-byte assembler prefix were checked. `git diff --check` passed. At that draft-verification point no synchronized implementation preflight, commit, push or GitHub write had been performed; current tracking synchronization is recorded separately below.

Coordinator-reported B2 code-only completion tracking was subsequently synchronized at https://github.com/lucronn/autodata/issues/186#issuecomment-6638436396; this successor uses its own separate live receipt6638503013 and does not reuse that predecessor receipt as its synchronization.

The workflow `.github/workflows/autonomous-verification.yml`, job `Validate autonomy policy and evidence contract`, step `Run development adapter tests`, runs `python -m unittest discover -s scripts/dev -p 'test_*.py' -v`. Its normal Actions checkout may retain credential-related Git configuration. The strict production reader correctly rejects configuration outside its passive allowlist. The inherited test erroneously opens repository `ROOT` during each ProductionGitTests.setUp, before the individual test reaches its owned fixture.

- Stage A repaired source `93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a`: [run41880058587](https://github.com/lucronn/autodata/actions/runs/41880058587) completed success for both autonomy and DTO inventory jobs, verified by read-only run readback during planning. This is predecessor CI evidence only.
- B1 exact `54a7ca32eab80654310d862f0ac6957375d16e8b`: [run41881056411](https://github.com/lucronn/autodata/actions/runs/41881056411) and [run41881112326](https://github.com/lucronn/autodata/actions/runs/41881112326) failed. The first failed log was independently read during planning: 337 tests, ten errors in ProductionGitTests.setUp line258, `ProductionGitReader(ROOT)` raising `ContractError: git_config`. Coordinator reports the same ten-error pattern in the second run and passing DTO inventory. Failure is test-environment coupling; do not relax the reader.
- B2 exact `0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471`: [PR run41884839700](https://github.com/lucronn/autodata/actions/runs/41884839700) and [push run41884762336](https://github.com/lucronn/autodata/actions/runs/41884762336) were `in_progress` at planning readback. Do not state these runs passed or failed. The B2 test blob is independently verified identical to the old ancestor blob, so the same fixture coupling is inherited even while CI remains pending.

Historical local B2 handoff `/home/corp/autodata-evidence/final180-stage-b2-builder/handoff.json` reports focused100 and autonomy146 passed and developer discovery pending; it is not completed successor validation. Local B1 clean-checkout success cannot substitute for the observed CI failure. New successor exact-head CI and fresh full checks are required.

## Exact repair and source pins

Repair ancestor `2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e`; repair source `93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a`. The source commit's only changed path is `scripts/dev/test_workshop_final180_runner.py`, 11 insertions and8 deletions. The canonical binary-capable diff generated by the plan's exact git diff command is4384 bytes, SHA256 `c4567a3b03db9d8bb56af43a701f56ebaf15d68149ff6cadd326c93ecfb921eb`, stable patch-id `87df9ca6f05a0bbdf9f5c98bcc549fef1be6b3fc`. B2 and ancestor test blob are `2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3` /32981 bytes /SHA256 `2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a`; repaired test blob is `f4db092e0d1a83fce47b51f7c68021b6dc2053bd` /33237 bytes /SHA256 `c0bac62eb756d84593191e82b2b240fdd77bd5128242f212e9b508e15c1740c1`.

The fixture initializes passive metadata in self.root before constructing ProductionGitReader, replaces constructor/argv ROOT references with self.root and makes metadata directory creation idempotent. Existing strict config/helper/hook/attribute/alternate/worktree/executable/limit adversarial tests remain active.

The readable rendering below removes whitespace-only blank context markers; use the pinned git diff command to generate the exact apply input. Its canonical bytes/hash above remain authoritative.

```diff
diff --git a/scripts/dev/test_workshop_final180_runner.py b/scripts/dev/test_workshop_final180_runner.py
index 2cfa9dc..f4db092 100644
--- a/scripts/dev/test_workshop_final180_runner.py
+++ b/scripts/dev/test_workshop_final180_runner.py
@@ -255,7 +255,10 @@ class ProductionGitTests(unittest.TestCase):
         self.root=Path(self.tmp.name)
         # Production command construction is tested using a real immutable host
         # executable and intercepted read-only command output, never fixture tools.
-        self.git=r.ProductionGitReader(ROOT);self.addCleanup(self.git.close)
+        # The checkout used to run tests may have CI-only credential configuration;
+        # the metadata under test must be our owned, passive fixture instead.
+        self.metadata()
+        self.git=r.ProductionGitReader(self.root);self.addCleanup(self.git.close)

     def test_fixed_path_discovery_version_and_exact_isolated_argv(self):
         identity=self.git.tool_identity()
@@ -263,36 +266,36 @@ class ProductionGitTests(unittest.TestCase):
         with mock.patch.object(self.git,'_capture',return_value=b'blob') as capture:
             self.assertEqual(self.git.read_blob(CANDIDATE,'safe/file'),b'blob')
         argv=capture.call_args.args[0]
-        self.assertEqual(argv,(identity.path,'--no-optional-locks','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','protocol.file.allow=never','-C',str(ROOT),'cat-file','blob',CANDIDATE+':safe/file'))
+        self.assertEqual(argv,(identity.path,'--no-optional-locks','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','protocol.file.allow=never','-C',str(self.root),'cat-file','blob',CANDIDATE+':safe/file'))
         self.assertEqual(set(self.git.env),{'PATH','HOME','GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_TERMINAL_PROMPT','GIT_NO_REPLACE_OBJECTS','GIT_NO_LAZY_FETCH'})
         self.assertEqual(self.git.env['PATH'],r.FIXED_PATH)
         self.assertEqual(list(Path(self.git.env['HOME']).iterdir()),[])
         with mock.patch.object(r.shutil,'which',return_value=None) as which:
-            with self.assertRaises(r.ContractError):r.ProductionGitReader(ROOT)
+            with self.assertRaises(r.ContractError):r.ProductionGitReader(self.root)
         which.assert_called_once_with('git',path='/usr/local/bin:/usr/bin:/bin')

     def test_version_argv_is_only_special_command(self):
         with mock.patch.object(r.ProductionGitReader,'_capture',return_value=b'git version unit\n') as cap:
-            git=r.ProductionGitReader(ROOT)
+            git=r.ProductionGitReader(self.root)
             try:self.assertEqual(git.tool_identity().version,'git version unit')
             finally:git.close()
         self.assertEqual(cap.call_args.args[0],(str(Path(self.git.identity.path)),'--version'))
         for version in (b'',b'x\ny\n',b'x\r\n',b'x'*257,b'\xff'):
             with self.subTest(version=version),mock.patch.object(r.ProductionGitReader,'_capture',return_value=version),self.assertRaises(r.ContractError):
-                r.ProductionGitReader(ROOT)
+                r.ProductionGitReader(self.root)

     def test_git_executable_changed_or_symlinked_after_discovery(self):
         executable=self.root/'git';executable.write_bytes(Path(self.git.identity.path).read_bytes());executable.chmod(0o755)
         with mock.patch.object(r.shutil,'which',return_value=str(executable)),mock.patch.object(r.ProductionGitReader,'_capture',return_value=b'git version unit\n'):
-            git=r.ProductionGitReader(ROOT)
+            git=r.ProductionGitReader(self.root)
         self.addCleanup(git.close)
         executable.write_bytes(b'drift');self.assertRaises(r.ContractError,git.tool_identity)
         executable.unlink();executable.symlink_to(self.git.identity.path)
         self.assertRaises(r.ContractError,git.tool_identity)

     def metadata(self):
-        gitdir=self.root/'.git';gitdir.mkdir();(gitdir/'config').write_text('[core]\n repositoryformatversion = 0\n')
-        (gitdir/'hooks').mkdir();(gitdir/'objects/info').mkdir(parents=True)
+        gitdir=self.root/'.git';gitdir.mkdir(exist_ok=True);(gitdir/'config').write_text('[core]\n repositoryformatversion = 0\n')
+        (gitdir/'hooks').mkdir(exist_ok=True);(gitdir/'objects/info').mkdir(parents=True,exist_ok=True)
         return gitdir

     def checkout_git(self,root,command,**kw):
```

Pinned source records (assembler is the append-only baseline, not the appended result):

```json
[
  {
    "commit": "2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e",
    "path": "scripts/dev/test_workshop_final180_runner.py",
    "git_blob": "2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3",
    "bytes": 32981,
    "sha256": "2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a"
  },
  {
    "commit": "93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a",
    "path": "scripts/dev/test_workshop_final180_runner.py",
    "git_blob": "f4db092e0d1a83fce47b51f7c68021b6dc2053bd",
    "bytes": 33237,
    "sha256": "c0bac62eb756d84593191e82b2b240fdd77bd5128242f212e9b508e15c1740c1"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/test_workshop_final180_runner.py",
    "git_blob": "2cfa9dc8ea116b7aa5b0c541529712b4b5d24be3",
    "bytes": 32981,
    "sha256": "2f92614e937b5b3d6a17da7ab9f4b758b34a4a542fbe5564b29ddefd4f7b148a"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/workshop_final180_runner.py",
    "git_blob": "ca48cd988c5579a7d385dc1844b84306eae0861e",
    "bytes": 47124,
    "sha256": "693a408a73f3ccd37bf945bfc94d427f742878580932dab382ea9a244a141c91"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/workshop_final180_identity_adapter.py",
    "git_blob": "8c7fa87bab906955c145d7cc965be641aea48c5f",
    "bytes": 22290,
    "sha256": "0474a85c33d4f2722ad01d6e55e69a8080dc0f1983c856ca7caa1b94510a767d"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/test_workshop_final180_identity_adapter.py",
    "git_blob": "7391263cb874e2505f4f110df6343c8b466fc692",
    "bytes": 29838,
    "sha256": "a3f3017b1d7a85da9ae4d1883758f2494d722fb321d45c1ff758994ab6d2653c"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/workshop_final180_catalog_adapter.py",
    "git_blob": "060d1407ee5e71880cf7e441195cac4274f04937",
    "bytes": 15467,
    "sha256": "88f481104d66d9bda8bdf6c1a8038e8514b69d63db813b85c5ec13e40f0c6ddf"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "scripts/dev/test_workshop_final180_catalog_adapter.py",
    "git_blob": "86e78aef564c216ede5780dccadd56366d4d0a63",
    "bytes": 26977,
    "sha256": "978cbb594d9bc42f0cb02b3447e2afed6bb6764c155b657db6e5b3676cc319a9"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "docs/verification/workshop-final180-runbook.md",
    "git_blob": "5812377b4e1a1bd9f992f116cdd11e73c7168393",
    "bytes": 18423,
    "sha256": "23023c638cd94dd46ff7722d80a5f28a1e3e6ad2c82f417ac6485d46cabeef03"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": "docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md",
    "git_blob": "bd7d94e9c02455b229413795056bfe7a0e2e2e1d",
    "bytes": 79030,
    "sha256": "59cb096b18c57d52cdbf007521652b83c4a66636a2cc822a47d7366808e15129"
  },
  {
    "commit": "0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471",
    "path": ".github/workflows/autonomous-verification.yml",
    "git_blob": "08384431f5c6795eb83cae0ad4e8b8759d5e6fa9",
    "bytes": 9521,
    "sha256": "d38f4b1a5f414775b494ee801c83ebbc0473a7ab7e970cbf573529d08f1010aa"
  }
]
```

## Required validation contract

The reproducible environment-coupling regression changes only the imported test module's ROOT to a temporary checkout with harmless forbidden metadata. The fake helper string is never executed; production config rejection precedes command execution. Run this before and after the exact patch. Before: ten setup errors `git_config`; after: ten successes. Do not add this harness to a production module or expand the exact test patch.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PYTEST'
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
path = Path('scripts/dev/test_workshop_final180_runner.py').resolve()
spec = importlib.util.spec_from_file_location('ci_fixture_regression', path)
tests = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tests
spec.loader.exec_module(tests)
with tempfile.TemporaryDirectory() as directory:
    checkout = Path(directory)
    (checkout / '.git').mkdir()
    (checkout / '.git/config').write_text('[credential]\n helper = inert-ci-fixture-marker\n')
    tests.ROOT = checkout
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.ProductionGitTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
PYTEST
```

Fresh ordinary validation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_runner.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_identity_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts/dev/test_workshop_final180_catalog_adapter.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/dev -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/autonomy -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PYCHECK'
from pathlib import Path
compile(Path('scripts/dev/test_workshop_final180_runner.py').read_bytes(), 'scripts/dev/test_workshop_final180_runner.py', 'exec')
PYCHECK
git diff --check
```

Expected focused52 Stage A +25 B1 +23 B2 =100 tests, all passing; the contaminated-checkout run is ten tests, all passing after repair. Broad discovery must complete with zero failures/errors and its actual counts/duration recorded; do not reuse predecessor counts or a partial dots-only log. Autonomy predecessor count146 is context, not a substitute for a fresh result.

Exact-boundary verification after the two allowed changes:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'SCOPECHECK'
from pathlib import Path
import hashlib
import json
import subprocess
record = json.loads(Path('docs/agents/records/2026-11-04-workshop-final180-ci-integration.json').read_text())
base = record['planning_parent_sha']
test = record['repair_path']
source = record['repair_source_sha']
expected = subprocess.check_output(['git', 'show', f'{source}:{test}'])
assert Path(test).read_bytes() == expected
patch = subprocess.check_output(['git', 'diff', '--binary', record['repair_ancestor_sha'], source, '--', test])
assert hashlib.sha256(patch).hexdigest() == record['repair_patch_sha256']
assert subprocess.check_output(['git', 'diff', '--binary', base, '--', test]) == patch
for pin in record['source_pins']:
    if pin['commit'] == base and pin['path'] not in record['implementation_allowlist'] and pin['path'] != 'docs/superpowers/plans/2026-11-03-workshop-product-evidence-assembler.md':
        assert Path(pin['path']).read_bytes() == subprocess.check_output(['git', 'show', f"{base}:{pin['path']}"])
import os
checkpoint = os.environ['AUTODATA_CI_INTEGRATION_CHECKPOINT_SHA']
assert isinstance(checkpoint, str) and len(checkpoint) == 40, 'coordinator must pin the independently reviewed checkpoint in the dispatch record'
changed = set(subprocess.check_output(['git', 'diff', '--name-only', checkpoint], text=True).splitlines())
assert changed == set(record['implementation_allowlist']), changed
assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], text=True).strip()
print('exact source patch, unchanged predecessor pins and two-path allowlist: PASS')
SCOPECHECK
```

The coordinator supplies `AUTODATA_CI_INTEGRATION_CHECKPOINT_SHA` as the exact independently reviewed, committed planning checkpoint in the immutable dispatch. Do not infer it from HEAD after implementation or amend the record to create a self-reference. This plan asserts no self-referential implementation base SHA; the coordinator must supply the reviewed checkpoint in its dispatch.

## Runbook content required

Append a CI fixture-isolation note naming source93b0bf4, ancestor2ac8034 and reviewed B2 head0ccfe79; explain the owned passive metadata, retained production denials, regression and focused/broad commands. Record measured successor check outcomes and CI status at the exact reviewed successor SHA; distinguish predecessor evidence. A passing synthetic/tooling suite proves only test-fixture isolation and unchanged restricted diagnostic behavior. B1 fake identity rows and B2 unauthenticated bank-context rows still earn no real accepted IDs; real raw fixtures, full catalog semantics, real Go compatibility and final180 execution remain unproven.

## Gate and tracking boundary

Only the five planning paths listed in the plan may change in this planning phase. Coordinator is the sole GitHub writer: preserve Issue186 body/comments and existing Project8 fields/history, append the concrete goal/refs/todo, read back the actual Issue and Project values, then update both standalone and nested records identically to synchronized. Commit/push the planning checkpoint, run standalone and nested preflight at that exact SHA, independently review that SHA, and explicitly dispatch the exact two-path implementation allowlist. Tracking is now synchronized, while the exact committed-checkpoint preflight and independent review remain separate required steps. All nine authority fields remain false even after a code-only gate passes; dispatch authorization is recorded separately.

## Canonical todo

1. Synchronize this CI-integration plan/spec/record/task and exact two-path implementation allowlist with Issue186 and Project8, preserving history; commit/push the checkpoint descending from reviewed B2 0ccfe79345c0a1303bc6a33dfdc51ceccf8e3471 and pass exact-checkpoint standalone/nested preflight plus independent gate review before explicit builder dispatch.
2. Reproduce the ten ProductionGitTests setup failures with harmless forbidden checkout metadata, then apply only the pinned Stage A test-file patch from ancestor 2ac80344abe855d8dcbfcc6ccd309cc3c7128a3e to source 93b0bf4ed18737a7e57c0de6a8ea1fa0f5bdba0a; keep every production and adapter byte unchanged.
3. Update the final180 runbook to distinguish CI fixture isolation and code-only synthetic checks from genuine raw-fixture and runtime acceptance; preserve accepted_case_credit0, disabled profiles/tiers, null runtime lock/run record and all nine authority flags false.
4. Run the contaminated-checkout regression, 52 Stage A plus 25 B1 plus 23 B2 focused tests, complete developer/autonomy discovery, no-bytecode syntax and exact patch/two-path/unchanged-source checks; commit/push validated milestones and obtain independent exact-code-head review.
5. Read back exact-successor-head Autonomous Verification results and synchronize code-only evidence with Issue186/Project8; retain any pending or failed CI and every runtime/profile/release blocker without inferring acceptance or authority.
