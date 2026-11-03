# Workshop Browser Wrong-Account Media Status Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after coordinator exact-checkpoint review and passing pinned preflight. This planning checkpoint authorizes no implementation before that review.

**Goal:** Align the real-API browser fixture with the existing wrong-account media404 privacy contract without changing authorization behavior.

**Architecture:** Correct one status expectation in the actual browser fixture and add a regression in its existing Python unit-test module. The authenticated principal/capability mismatch remains an early404 before grant/object reading. No production handler or browser application changes.

**Tech stack:** Existing Python unittest/AST standard library and Playwright1.64.1 fixture. Execution gpt-6.1-sol / medium / Fast(priority), no fallback.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-paid-access.md` and the bounded amendment in `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`.

Issue https://github.com/lucronn/autodata/issues/186 ; Project https://github.com/users/lucronn/projects/8 .

## Evidence and exact boundary

Inspected integration source `fa30a2204dc8a5c0907d090ec4f41fdd8bec9b4b`. At scripts/dev/workshop_browser_smoke.py:527, the second authenticated account requests the first account's contextual image and the fixture expects403. The actual handler apps/api-go/catalog_media_access.go:176–179 returns ErrCatalogNotFound404 for a capability/principal account mismatch before grant/reader work. This is the intentional paid-plan privacy contract. Six account-scope cases (three engines × two banks) encounter the mismatch. No live21 run or production regression is claimed from source inspection.

Implementation may edit exactly:

1. `scripts/dev/workshop_browser_smoke.py`
2. `scripts/dev/test_workshop_browser_smoke.py`

Planning-only checkpoint files are this plan, the new task/record and the existing customer-UI canonical plan amendment. They are not additional implementation paths. The source integration base above is historical input; the implementation base must be the committed synchronized checkpoint (or the coordinator's later reviewed integration containing it), with exact-SHA preflight rerun before edits.

Preserve same-account missing/revoked grant403, authenticated wrong-account media404, expired/logged-out/disabled-user401. Preserve source/media rights, exact21 inventory, actual application HTTP/PG/S3/SDK transports, external-only synthetic network fixtures, raw receipts and frozen runner. Do not accept403-or404, change the app to satisfy the test, add compatibility fallbacks or broaden this lane into runtime infrastructure.

## Task 1: Red regression and one expectation correction

**Files:** Modify the two exact allowed paths above. No new implementation file.

- [ ] Add `BrowserEvidenceContract.test_wrong_account_media_requires_not_found` to the existing unit-test class. Parse the actual imported smoke module source with standard-library ast; locate api_case's unique ast.Assert whose test references `denied_image.status`; assert exactly one match. Compile that actual assertion as an ast.Module and execute it with `denied_image=types.SimpleNamespace(status=404)`. It must accept404 and raise AssertionError for200,401,403,410,503. This exercises the committed fixture assertion itself, not a duplicated status helper or synthetic app-response proof. Keep the other status assertions untouched.

The extraction may be expressed directly in the test:

```python
source = ast.parse(Path(smoke.__file__).read_text())
case = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'api_case')
assertions = [node for node in ast.walk(case) if isinstance(node, ast.Assert)
              and any(isinstance(value, ast.Attribute) and value.attr == 'status'
                      and isinstance(value.value, ast.Name) and value.value.id == 'denied_image'
                      for value in ast.walk(node.test))]
self.assertEqual(len(assertions), 1)
check = compile(ast.fix_missing_locations(ast.Module(body=assertions, type_ignores=[])), smoke.__file__, 'exec')
exec(check, {'denied_image': SimpleNamespace(status=404)})
for status in (200, 401, 403, 410, 503):
    with self.subTest(status=status), self.assertRaises(AssertionError):
        exec(check, {'denied_image': SimpleNamespace(status=status)})
```

- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s scripts/dev -p test_workshop_browser_smoke.py -v`. Retain the red log proving that404 fails against the original403 assertion. AST imports are standard library; no browser or service is started.
- [ ] Change precisely `assert denied_image.status==403` to `assert denied_image.status==404` in the wrong-account branch. Keep other-owner index403, refund403 and logout/disable401 unchanged.
- [ ] Rerun the same unit command; retain green output. Parse both files with `ast.parse` without writing bytecode. Run `git diff --check`; verify only the two allowed implementation paths changed relative to the pinned gate and that the original21 parametrization and frozen supervisor bytes are unchanged.
- [ ] Commit a coherent fix and promptly push the assigned feature branch after these checks. Send exact SHA, red/green logs and two-path diff for independent coordinator review; do not self-approve or integrate.

## Task 2: Coordinator-owned actual browser acceptance

- [ ] Integrate the reviewed fixture correction with the reviewed protected-auth cache repair and required paid12 verified behavior. Pin one clean exact candidate; recheck all frozen image-input hashes. These two fixture paths and auth source/test do not themselves change the six image build inputs.
- [ ] Coordinator runs the unchanged `/tmp/autodata-workshop-browser-supervisor.py` with explicit `--mode api`, fresh run root, existing approved pinned runtime image and finite budgets; default `first` is only one pilot. Preserve isolated services/source mounts/UID, no concurrent heavy acceptance and cleanup reserve. Existing reviewed command/evidence checklist is recorded in the read-only audit `/tmp/autodata-workshop-browser-real-api-readiness-review.md` SHA256 `19d8d8b6cf585b74144204880aa2f0482e0f4bda6ce7b858e7f76113a7f78a8f`; it is diagnostic context, not a substituted canonical runtime gate.
- [ ] Require exactly3+6+6+6 case identities and zero skips/errors/failures, actual owned source/canonical/media/PG/session/checkout/restart/refund evidence, exact candidate/input/asset/SDK hashes and cleanup. Preserve failures and independently review raw receipts. Existing CI120DTO is separate and does not certify21 realAPI. Frozen wrapper labels author_run true/final_independent_acceptance false; do not overwrite that meaning or claim staging/cutover readiness.

## Concrete todo

- [ ] Synchronize Issue186/Project8 and the canonical browser amendment; commit the checkpoint, pass exact-SHA preflight and obtain coordinator review before implementation.
- [ ] Add a focused red regression executing the actual wrong-account media assertion against synthetic status404 and rejecting200/401/403/410/503; preserve sibling grant403/auth401 assertions.
- [ ] Change only the wrong-account media fixture expectation from403 to404; preserve all21 parameterized cases and frozen runner/receipts.
- [ ] Run focused Python unit tests, syntax and diff/scope checks; commit/push and request independent exact-candidate review.
- [ ] After reviewed auth-header integration and required paid12 verification, let the coordinator run the unchanged isolated21 real-API browser inventory and independently inspect retained receipts.

## Tracking/checkpoint status

Planning only. Issue186 and Project8 were saved and independently read back with the same goal, canonical plan references and concrete todo; all existing hosting/auth text was preserved. Receipt: `/tmp/autodata-browser-media-gate-tracking-synchronized.json`. Task/record status is synchronized. Commit/push this documentation checkpoint and run machine preflight pinned to its exact SHA; coordinator review is still required before implementation. No implementation is part of this checkpoint. Runtime/browser/staging/production readiness remain unverified.
