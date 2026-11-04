# Workshop PG17 Bind-Target Structural Audit Successor Plan

**Goal:** Permit only proven Docker-created empty acquisition bind-target directories in the stopped overlay diff, retain every other audit and cleanup constraint, and keep all quarantined APKs unusable.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Base: `e1ca20812dd4f037eda9d439b69cf0cb96d895dd`; adopted failed gate `7f0201cc2b26cc8fbcd0637386f5cf047320c970`.
Immutable harness `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`; implementation allowlist empty.

## Scope and actual red evidence

Planning only: no Docker invocation, container create/start/export, download/retry, install, image mutation, harness, integration or production action. Independent exact-checkpoint review and fresh coordinator dispatch are required before Task1A. This supersedes only the acquisition overlay guard's blanket rejection of added mountpoint directories, and permits two bounded read-only structural filesystem exports as described below. All other acquisition-overlay, inspected-preparation and APK-log constraints remain mandatory. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged.

Retained raw directory `/home/corp/autodata-evidence/pg17-overlay-prep-20261104-01/evidence`: task1a-blocker.json SHA256 `36ea1490633250d79fddf2f5c1f7b92abe19f043e8ab4544dc1519f3afd9ee52`; stopped-diff.txt `f644241d7c563ce99a81d3cf0ba36af3582bc221b19054fc1f509fea8cad221d`; stopped-audit.json `17c03aab7df37281f535e5e2f32d0d28c7afc88191a169087a3ec8589f2d7754`; before-start.json `0d655fcb331127f737bf9c7223e6fcb88dc139acbe60f39ae1f2ec99a86d2470`; quarantined manifest `bc44b2eb0cede2db890e8b09ffbdf673bb3ef0e98c1ffd94a9c9e0a9c7ef8c55`.

Exact removed container `102eb97013e3b69e567b0179b59dc14416a167748bbd81200d5c9fabb30d1f17` exited0, no OOM/error/overflow, stdout8898/stderr0 bytes, verified signatures for33 APKs, and all27 baseline records unchanged. Full stopped diff was exactly `A /apks` and `A /control`; the approved guard rejected both. Removal/absence and unchanged normalized volume inventory were proved. This remains a failed attempt: all33 APKs are quarantined, unaccepted and forbidden for reuse, including after this successor is reviewed. No downstream phase occurred.

Read-only inspection of retained `base-image.tar` (SHA256 `60ae29e1f3496f1ec842b48995fcc631d9c6e918b20da48a154fd7258fa3106d`) found zero `/apks`, `/control` or descendant entries in any of its10 layers. Config digest matches exact base `sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085`. This diagnoses added bind-target directories; it does not retroactively prove their underlying type/emptiness in the deleted container. The historical red rows therefore still fail the new context guard without new structural proof. Pure fixtures are synthetic and confer no retry authority.

## Fresh attempt: before-start identity and mount proof

Use the preceding acquisition overlay plan's exact create argv, private realpaths, image pins, fixed signed APK payload, four bounded tmpfs, two binds, bridge network, uid0:0, sole DAC_OVERRIDE cap, no-new-privileges, resources, deadlines, output caps and no-source/no-secret rules unchanged. In particular private PGDATA tmpfs overrides inherited VOLUME; no writable host root or additional mount is authorized. Keep all27 base hash/type/owner/mode records and full original configuration validation.

Before start, capture exact full ID, gate label, image, State.Status=created, RestartCount=0, full inspect and volume inventory. Require `/apks` bind exactly the new private `$PREP/apks`, RW=true; `/control` bind exactly new private `$PREP/control`, RW=false. No duplicate/overlapping mount destinations, anonymous volume or other bind. Inspect's source realpaths must equal the previously validated private host directories; mounts must be type bind, not volume/tmpfs. Host directory contents are not evidence that underlying mountpoint directories are empty. Record baseline target absence from the exact saved base's authenticated ordered layers (including whiteout handling); missing archive, wrong config/layer digest or ambiguous tar member fails.

Before the first created-state export/diff, complete all inherited prestart `docker cp` baseline snapshots and the unchanged27-record saved-base comparison; those existing copies materialize the bind-target directories. Only after every copy succeeds, run the bounded structural export below on that exact still-created ID, and retain full prestart `docker diff` requiring exactly `A /apks` and `A /control`. No payload runs until this audit and all prior prestart guards pass. A different base directory arrangement requires a new plan; do not generalize to arbitrary mountpoints.

## Bounded read-only underlying filesystem audit

A filesystem `docker export ID` excludes mounted volume/bind contents and exposes underlying root directories. Read-only source review of [Moby v28.5.2 daemon/export.go](https://github.com/moby/moby/blob/v28.5.2/daemon/export.go) (Git blob `ba3d98a7facb133b9359480ec03cbc6730c24f60`, source SHA256 `2f224f5a822350baa52203423f9249a4bbb03ab7fca31d0657747d285203de99`) shows `containerExport` mounts only `ctr.RWLayer`, then calls `chrootarchive.Tar(basefs, ..., basefs)`; it does not assemble container bind/volume mounts. The entry point rejects dead/removing containers but does not require a previous start. This supports created and stopped underlying-root audits on the retained Docker28.5.2+dfsg4/overlay2 engine; future operator must confirm unchanged engine/storage driver and preserve this source evidence. Any mismatch or inability to establish these semantics blocks before start. Source inspection is not an actual exporter execution. It does not execute the container or create an image. Its sole permitted purpose here is structural inspection of the exact two root-layer directories, once while created and once after stopped. This is a narrow exception to the predecessor's inspect/diff/cp-only audit restriction. Never import/commit/load/reuse/export this overlay as an image, pass its archive to an installer or use it as harness source. No Docker execution occurs while drafting this plan.

Future approved operator uses argv `['docker','export',EXACT_CAPTURED_ID]` without a shell, after ownership/state checks. Stream stdout in <=65536-byte chunks into a new exclusive mode0600 archive in private mode0700 `$PREP/evidence`; each export has a60s deadline and512MiB total stdout cap, stderr1MiB cap, with byte counts, SHA256, return code and supervision result retained. No Docker `--output` bypass of the host byte cap. Reaching/exceeding a cap, timeout, nonzero exit, short/truncated archive or parse error fails; terminate the export client and retain bounded failure receipt, then exact-owned cleanup under existing bounds. No restart/exec or unbounded retry. These caps are audit limits, not a claim of hard overlay disk quota.

Read each completed archive using host Python tarfile, never extract it. Limit to50000 logical entries and512MiB declared cumulative regular-file sizes. Validate tar completion/headers; reject duplicate normalized paths and ambiguous target names. Normalize only one optional leading `./` and a directory's trailing slash; reject absolute names, NUL, traversal, repeated separators or other aliases. For `/apks` and `/control`, require exactly one directory tar entry each (type5), uid=gid=0, mode0755, size0, empty linkname and no PAX path/linkpath or sparse override. Reject files, symlinks, hardlinks, devices/FIFO, omitted targets and any member with either target plus `/` prefix. These checks prove empty underlying directories; ignore mounted APK/control contents and timestamps only. Other root members are not executed/extracted and do not receive any new diff allowance.

Retain both export hashes/byte counts and normalized target metadata. Created and stopped target metadata must match exactly; both must pass emptiness/type checks. Re-inspect same image/ID/gate before and after export; require created/never-started for first, stopped exit0/OOMfalse/emptyerror for second, no concurrent writer/restart or changed mounts. The stopped diff and all original27 baseline audits remain mandatory. Unexpected output or inability to prove volume-exclusion semantics is a blocker, never an excuse to inspect the bind-visible directory instead. After receipts/hashes are retained, delete only these exact owned audit archive files (no import/reuse); archive deletion failure blocks acceptance.

## Context-bound stopped diff rule

Preserve all prior row/action/normalization/count/duplicate and baseline/type/hash/lock/4096-byte checks. New exception: only `A /apks` and `A /control`, each backed by saved-base absence, the exact prestart bind proof, matching valid empty created/stopped directory records and successful bounded audit receipts. This is an allowance for directory metadata only, not file content. Both directory rows must remain present, consistent with their absent base and created overlay state. `C`/`D` for these paths, any child or other added directory fails. Do not filter the full diff or catch validation failure as success.

The fixed pure row/context predicate is below; trusted context is produced only by all audit/identity/bounds checks above, not caller-supplied booleans alone. Original baseline/type/size checks remain separate and mandatory.

```python
TARGETS = {'/apks': True, '/control': False}
LOCK_PATH = '/lib/apk/db/lock'
DIRECTORIES = {'/lib', '/lib/apk', '/lib/apk/db', '/var', '/var/cache', '/var/log'}
BASELINE_FILES = {'/lib/apk/db/installed', '/lib/apk/db/triggers',
                  '/lib/apk/db/scripts.tar', '/etc/apk/world'}
EXPECTED_DIRECTORY = {'type': '5', 'uid': 0, 'gid': 0, 'mode': 0o755,
                      'size': 0, 'linkname': '', 'children': []}
def validate_acquisition_diff(rows, proof):
    assert type(proof) is dict and set(proof) == set(TARGETS)
    for path, rw in TARGETS.items():
        p = proof[path]
        assert p['base_absent'] is True and p['audit_bounds_passed'] is True
        assert p['bind_type'] == 'bind' and p['bind_rw'] is rw
        assert p['exact_private_source_verified'] is True
        assert p['created'] == p['stopped'] == EXPECTED_DIRECTORY
    assert type(rows) is list and len(rows) <= 128
    seen = set()
    for row in rows:
        assert type(row) is str and len(row) <= 256 and '\n' not in row and '\x00' not in row
        assert len(row) >= 4 and row[1] == ' ' and row[0] in ('A', 'C')
        action, path = row[0], row[2:]
        assert path.startswith('/') and '//' not in path
        assert all(part not in ('', '.', '..') for part in path.split('/')[1:])
        assert path not in seen
        seen.add(path)
        assert ((action == 'A' and path in TARGETS) or path == LOCK_PATH or
                (action == 'C' and path in DIRECTORIES | BASELINE_FILES))
    assert set(TARGETS) <= seen
```

## Cleanup, output boundary and concrete todo

All original zero-exit/signature/package/unchanged-baseline/complete-diff audits and exact-owned stop/kill/rm --volumes/absence/normalized-volume inventory checks apply. Acquisition is never restarted, committed or reused. New archive proof does not accept old quarantined APKs. Only a newly dispatched fresh attempt that passes every audit and cleanup may freeze its independently verified APK closure for separately authorized offline phases. Every runtime/harness/production/schema/grant/service/deployment readiness assertion remains false. No implementation changes or Task2 expansion.

- [ ] Synchronize exact red receipt, bounded structural audit and context-bound diff guard in Issue186/Project8/canonical docs; push exact gate and pinned preflight for independent review.
- [ ] After independent exact-gate review/adoption and fresh coordinator Task1A dispatch only, create a fresh acquisition container and collect full prestart bind inventory plus bounded underlying filesystem structural audit before start.
- [ ] Require exact empty directory metadata before/after, absent saved-base targets, unchanged 27 baseline records and original complete stopped diff/signature/exit audits; reject files, descendants, aliases, deletions and missing proof.
- [ ] Retain prior 33 quarantined APKs as failed evidence, never accept/reuse them; any future fresh output requires all audits and exact-owned removal/absence/volume proof.
- [ ] Keep acquisition commands/network/caps/mounts and offline simulation/install/image/Task2 authorities unchanged; no planning Docker/download/retry/harness action or readiness claim.

Bind-target successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621533357 and Project8 readback at `2026-11-04T03:13:58.668948+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned bind-target successor checkpoint: `016ea37722f36fa0c8b2b509884e75bef6ac41b2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-targets-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621541625. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed bind-target gate adoption and mandatory operation ordering

Adopted source gate `016ea37722f36fa0c8b2b509884e75bef6ac41b2`, receipt `c7d57a3347621c5559d5a671997142da1a1f43dc`; exact reviewed plan SHA256 `40e0591c8742a37983cf289d565c9df7d4e263c7caa5cc4e8e7f38b3b36f49ed`. Coordinator relayed independent approval of this exact plan. Adoption branch `codex/workshop-pg17-bind-target-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-target-adoption.json`. This adoption performs no Docker operation or retry and conveys no production/harness readiness.

**Mandatory future order (resolves the created-state mountpoint feasibility condition):** (1) create exact-owned fresh acquisition container under the unchanged approved argv, validate full created inspect/config/bind inventory and pinned base archive; (2) complete **all inherited prestart `docker cp` baseline snapshots** and the unchanged27-record saved-base comparison while still created/never-started; these existing copy operations materialize the bind-target directories; (3) only **after those copies finish successfully**, perform the first bounded created-state underlying filesystem export and full prestart diff, requiring the exact empty root-owned `/apks` and `/control` directories plus `A /apks` and `A /control`; (4) only after every inherited and new prestart guard passes may the coordinator-dispatched payload start; (5) after stopped exit0, perform the bounded stopped export/full diff/unchanged-baseline audits, then exact-owned cleanup and output acceptance boundary. Never run the first export/diff before the inherited copies or start merely to materialize targets. Failed copies, missing/changed/nonempty targets or any ambiguity fail closed and clean the exact owned attempt. No extra container command, mount or authority is added.

All prior export bounds/source semantics checks, acquisition payload/image/network/caps/resources/mounts, signature verification, quarantine, baseline/row/type/empty checks and cleanup remain mandatory. This ordering clarification does not accept or reuse the historical33 quarantined APKs. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged. No deployment, integration, production grant/runtime action or readiness follows.

Concrete adoption todo:

- [ ] Record independent approval of exact gate016ea377 and reviewed plan SHA256, synchronize adoption Issue186/Project8/canonical docs, then push and pin passing full-SHA preflight.
- [ ] Only after new coordinator dispatch, validate exact created acquisition ID/config/bind inventory; complete every inherited prestart docker cp baseline snapshot and unchanged27-record comparison BEFORE first created-state export/diff.
- [ ] Then require bounded created-state underlying empty-directory export and exact A /apks,A /control diff; only after all guards pass may the fixed acquisition payload start.
- [ ] Require matching stopped structural export, complete original baseline/diff/signature/exit audits and exact-owned cleanup/absence/volume proof before accepting any newly acquired APK closure.
- [ ] Never accept/reuse historical33 quarantined APKs; no Docker/download/install/harness on adoption turn; offline stages/Task2 and all production/readiness denials unchanged.

Reviewed bind-target adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621594414 and Project8 readback at `2026-11-04T03:18:09.877892+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.
