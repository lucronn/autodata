# Workshop PG17 Acquisition Diagnostics and Structured Volume Receipt Plan

**Goal:** Correct only acquisition diagnostic false positives and volume inventory serialization by anchored status checks and bounded structured complete-volume inspection, retaining all existing guards and failed-output quarantine.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Base: `9a0ea7e89915d72a9fd98eb963b52b8749801dc4`; prior adopted gate `3c96b04df9ff4b7929ca8955a92d89eef6cc7617`.
Original immutable harness `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`; implementation allowlist empty.

## Scope and retained actual failure

Planning only: no Docker/create/start/export/retry/download/install/image/harness operation. Independent exact-checkpoint review/adoption, root pinned-gate verification and fresh Task1A dispatch are mandatory. Two corrections only: replace broad substring diagnostic detection with the fixed status/anchored-line guard, and replace incomplete CSV volume normalization with bounded complete structured metadata collection/comparison. Additional future `docker volume inspect` metadata reads are an explicit plan authority change requiring this gate/review/adoption; they are not performed while planning. No other acquisition command, source/image pin, mount/cap/network/resource authority, baseline/diff/export/cleanup rule or offline/Task2 boundary changes.

Raw directory `/home/corp/autodata-evidence/pg17-bind-target-prep-20261104-02/evidence`:

- `task1a-result.json` SHA256 `22e9fc0135d17df0848d2e868f0b5cdaf795ea801d27dfbb49bf0e4a140aaf26`.
- `task1a-diagnosis.json` SHA256 `38c51447e793b52ff4c59ba22d2ed42e14f3ba7197280838db6d39aff3d615f9`.
- `quarantined-apk-manifest.json` SHA256 `b2a1b285d37ec23195b410e23fd1617fb7ab839aef6eb86aca2cac9db20175ec`.
- `attach.stdout` SHA256 `e3fefb66656dac54d848ba5b734f508f6402e1e6772dd7d242bd3e523d4cb398`; stderr empty SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `volumes-before.stdout` SHA256 `cc4a3fb48cd1143087d1da51091213bd1afcf18bfcac344fe7f6d8e0852755da`; `volumes-after.stdout` SHA256 `f7f7184a636e5ce901dbe39a0a1e885f92c26ce1010d7a79f1beae2f8789afb6`.

Exact container `56acf7e94938be8b124defe2b6cb6ce94fc1c472075b862af851c7b1b3a08211` ran only fixed acquisition payload, exited0/OOMfalse/empty State.Error, stdout8898/stderr0, no supervisor overflow/timeout. Mandatory prestart copies preceded export/diff and all27 baseline records stayed identical. Both bounded underlying filesystem exports passed empty root-owned target checks, identical export SHA256 `f943bb8a9e0a44e85ee2d9f0dbc2f75497bfd8a4186b92dc1f0338465549fe4d`/299682304bytes each; complete-record Mounts comparisons and stopped full diff/context passed. All33 APKs have fixed-payload signature OK and matching host SHA256 lines.

The host substring check rejected `libcom_err-1.47.4-r0 - Common error description library`, an unchanged installed-baseline description. Cleanup `rm --volumes` exited0 and exact absence was verified; its inventory comparator rejected only Labels CSV order in one pre-existing volume. All10 fields in each complete retained ls record are equivalent after Labels CSV item ordering; no Name/Driver/Scope/Mountpoint or other field changed. That diagnostic replay does not prove a structured label map was collected. The raw result remains failed with33 fresh APKs quarantined and forbidden for reuse. Prior33 quarantined APKs also remain forbidden. No offline simulation/install/image/PG/harness action occurred. Never rewrite either failed result as accepted.

## Fixed acquisition diagnostic predicate

Preserve the complete fixed payload, official repository/signature/key/index checks, stdout source/arch/package/hash verification, supervisor bounds and independent stopped inspect. Do not substitute a return code for those checks. Replace only unanchored substring matching: require empty stderr bytes, supervised attach returncode0/no supervisor failure, stopped exited/not-running/exit0/OOMfalse/empty State.Error, and reject anchored case-insensitive diagnostic line forms `WARNING:`, `ERROR:`, `UNTRUSTED`, `BAD SIGNATURE` (optional leading spaces/tabs). A package description containing ordinary word error is allowed by this predicate, but still must satisfy all original baseline/source-output checks. No output is suppressed, filtered or edited. Nonempty stderr, including whitespace, fails; malformed UTF8/NUL/control ambiguity fails. Retain exact raw bytes/hash/byte counts and classifier result. Unknown source/index/package verification behavior remains a blocker; no new fallback flags or permissive signature rule.

```python
import json
import hashlib
import re
import unicodedata
DIAGNOSTIC = re.compile(r'^[ \t]*(?:WARNING[ \t]*:|ERROR[ \t]*:|UNTRUSTED(?:\b|:)|BAD[ \t]+SIGNATURE(?:\b|:))',
                        re.IGNORECASE | re.MULTILINE | re.ASCII)
def validate_acquisition_status(stdout, stderr, attach, state):
    assert type(stdout) is bytes and type(stderr) is bytes
    assert len(stdout) < 1048576 and stderr == b''
    text = stdout.decode('utf-8')
    assert all(c in '\n\t' or unicodedata.category(c) != 'Cc' for c in text)
    assert attach['returncode'] == 0 and attach['supervisor_failure'] is None
    assert state['Status'] == 'exited' and state['Running'] is False
    assert state['ExitCode'] == 0 and state['OOMKilled'] is False and state['Error'] == ''
    assert DIAGNOSTIC.search(text) is None
    return True
```

## Bounded structured volume metadata collection

Retain the original full raw bounded volume ls inventory for before/after, but never use its Labels CSV string as authoritative metadata. Before create and after exact-owned container removal/absence, run bounded argv `['docker','volume','ls','--format','{{json .}}']`: deadline10s, stdout256KiB, stderr64KiB, <=32 records. Parse complete JSON records with duplicate-key rejection; require unique Name strings matching Docker's restricted `[A-Za-z0-9][A-Za-z0-9_.-]{0,254}` grammar. Keep every ls field in its raw receipt; do not silently truncate or compare a selected subset. Nonzero exit, malformed/ambiguous input, duplicate names or any cap reached fails. Names before/after must match exactly.

For each captured exact name, sorted only for determinism, run argv `['docker','volume','inspect',EXACT_NAME]` as a read-only metadata operation. Never infer ownership or delete a volume from this name list. Each inspect has <=10s deadline, stdout512KiB/stderr64KiB caps and <=65536-byte chunks. Each whole inventory (ls plus all inspect operations) has60s total deadline, <=32 inspect calls, <=16MiB cumulative stdout and <=2MiB cumulative stderr. Use the tighter remaining deadline at each call; reaching any limit, nonempty stderr, nonzero exit or disappearing/changed/ambiguous volume fails. No shell, parallel unbounded subprocesses, fallback format or metadata retry. Existing exact-owned cleanup rules still apply; never mutate/delete unrelated volumes to force equality.

Each inspect result must be one complete JSON object inside a one-element array, Name exactly requested, with required Name/Driver/Scope/Mountpoint/CreatedAt/Labels/Options fields. Retain every extra field unchanged. Labels and Options must be null or actual JSON objects of string keys/values; CSV text is forbidden. Validate duplicate JSON object keys recursively before conversion. Compare complete objects keyed by unique Name; same exact Name set and every field/value must match, including Driver, Scope, Mountpoint, CreatedAt, Options, Labels and unfamiliar fields. Only JSON object key ordering is irrelevant; do not drop fields, default missing values, trim values, sort nested arrays, ignore labels/options or normalize away a genuine metadata change. Bind/anonymous-volume rejection and exact-owned volume cleanup remain separate mandatory guards. A foreign concurrent metadata change blocks acceptance without authorizing mutation of the foreign object.

Retain full raw ls/inspect bytes and SHA256, inventory Name set, per-object complete canonical JSON/hash, complete inventory canonical hash and before/after equality result. This fixes both the CSV ordering false positive and the former four-field projection, which omitted valid raw ls fields. It is not a claim that the previous failed attempt had structured before/after inspect evidence.

```python
def unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        assert key not in value
        value[key] = item
    return value

def parse_json(raw):
    def reject_constant(value):
        raise ValueError('non-JSON constant: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_json_object,
                      parse_constant=reject_constant)

VOLUME_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,254}', re.ASCII)
REQUIRED_VOLUME_FIELDS = {'Name', 'Driver', 'Scope', 'Mountpoint', 'CreatedAt', 'Labels', 'Options'}
def canonical_volume_inventory(raw_inspect_results, expected_names):
    assert type(expected_names) is list and len(expected_names) <= 32
    assert len(set(expected_names)) == len(expected_names)
    assert all(type(n) is str and VOLUME_NAME.fullmatch(n) for n in expected_names)
    assert type(raw_inspect_results) is list and len(raw_inspect_results) == len(expected_names)
    objects = {}
    for raw in raw_inspect_results:
        result = parse_json(raw)
        assert type(result) is list and len(result) == 1 and type(result[0]) is dict
        value = result[0]
        assert REQUIRED_VOLUME_FIELDS <= set(value)
        name = value['Name']
        assert type(name) is str and name in expected_names and name not in objects
        for field in ('Driver', 'Scope', 'Mountpoint', 'CreatedAt'):
            assert type(value[field]) is str
        for field in ('Labels', 'Options'):
            item = value[field]
            assert item is None or (type(item) is dict and
                all(type(k) is str and type(v) is str for k, v in item.items()))
        objects[name] = value
    assert set(objects) == set(expected_names)
    return json.dumps(objects, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')

def compare_volume_inventory(before, before_names, after, after_names):
    assert set(before_names) == set(after_names)
    left = canonical_volume_inventory(before, before_names)
    right = canonical_volume_inventory(after, after_names)
    assert left == right
    return hashlib.sha256(left).hexdigest()
```

## Offline replay before any further runtime dispatch

During planning, hash and read complete retained raw second-attempt evidence offline. Exercise the exact revised classifier on its full stdout/stderr/attach/stopped State: new predicate passes while old substring predicate fails. Replay both raw complete volume ls records with a diagnostic-only, duplicate-rejecting CSV item-order comparison preserving all10 fields; report equivalence but do not feed CSV into the new structured-volume acceptance guard. The latter must reject missing structured inspect proof. Replay all existing valid/negative Mounts and diff/context fixtures, and read/verify the27 baseline files, source/key/repository hashes, created/stopped audit receipts, full diff, output signatures/hash lines, bounds and cleanup/absence receipts. No container/package is executed to replay evidence; reading quarantined files/hashes is evidence inspection only, never accepted input reuse.

New negative fixtures must cover nonempty stderr/whitespace, every anchored diagnostic form/case/indentation, nonzero attach/status/OOM/error/supervisor failure, malformed/control output, and legitimate baseline error description as a positive. Structured inventory fixtures must accept pure object/Labels key order changes and reject any Name/set/field/value/type/Options/Labels/Mountpoint/Driver/Scope/CreatedAt/extra-field change, duplicates, omissions, malformed/duplicate-key/nonfinite JSON, CSV Labels and >32 records. Pure fixture success and diagnostic replay cannot retroactively accept the second attempt's33APKs. A future fresh attempt must collect actual structured inventories under this newly reviewed authority and pass every unchanged original guard. No arbitrary retry on another discrepancy.

## Concrete todo and unchanged boundary

- [ ] Replay the revised fixed pure predicates against complete retained second-attempt evidence and all existing positive/negative fixtures; synchronize goal/plan/todo/red evidence/structured inventory authority with Issue186/Project8/canonical docs after coordinator slot release; commit/push and pin full-SHA preflight.
- [ ] Require independent exact-gate review/adoption and root verification/fresh Task1A dispatch before any Docker/retry; use a new private exact-owned run, never historical quarantined APKs or failed containers.
- [ ] Use unchanged bounded fixed acquisition payload and source/signature/index/hash checks; classify only empty stderr plus successful supervised attach/stopped status and reject anchored diagnostic forms, preserving full raw output and hashes.
- [ ] Before create and after exact-owned removal, capture bounded volume ls names and one bounded read-only structured volume inspect per exact name; compare complete objects by unique Name preserving every field/value and ignoring JSON object key order only.
- [ ] Keep mandatory27 prestart copies BEFORE first created export/diff, complete Mounts canonical guard, empty underlying target audits, full stopped diff/context/baseline/exit checks and owned cleanup unchanged; no offline/install/image/PG/harness/production readiness follows.

Acquisition-receipts successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621817348 and Project8 readback at `2026-11-04T03:33:51.920926+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned acquisition-receipts successor checkpoint: `4bc40e26ca12521be8f20282b897f5af68d0195e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621820832. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 diagnostic Unicode Cc review correction: plan only

Correct only the blocked acquisition diagnostic character filter to reject Unicode Cc controls except LF/tab; preserve all existing receipt guards, quarantine and runtime denials.

Corrected plan `docs/superpowers/plans/2026-11-04-workshop-pg17-control-filter.md`; record `docs/agents/records/2026-11-04-workshop-pg17-control-filter.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-control-filter.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.json`. Prior4bc40e26 remains independently BLOCKED for DEL/C1 acceptance. Only diagnostic unicodedata import/Cc predicate changed, LF/tab sole control exceptions; complete83-case offline replay plus65 Cc probes pass (148total/0fail). All structured-volume and predecessor constraints unchanged; both33APK sets quarantined NEVER reusable. Independent exact-corrected-checkpoint re-review/adoption/root dispatch required; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Preserve exact blocked gate/plan hash and reproduced DEL/C1 negatives; update only diagnostic Cc filter/import, rerun complete83-case pure/replay suite plus65 Cc probes, then synchronize Issue186/Project8/canonical docs after coordinator tracking-slot release.
- [ ] Commit/push docs-only corrected checkpoint, pin passing full-SHA preflight and exact tracking readback while preserving CURRENT Python SIGTERM and PG predecessor index verbatim/hash.
- [ ] Require independent exact-corrected-checkpoint re-review/adoption, root verification and fresh Task1A dispatch before any Docker/retry/download/harness; previous blocked gate grants no adoption authority.
- [ ] Keep structured complete volume metadata collection/comparison and every original source/payload/config/mount/copy/export/diff/baseline/signature/cleanup bound unchanged; both33APK sets remain quarantined NEVER reusable.
- [ ] Retain all red receipts as failed and offline replay as predicate evidence only; no retrospective acceptance, offline install/image commit/PG startup/harness/production action or readiness claim.

Unicode Cc corrected successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621857074 and Project8 readback at `2026-11-04T03:36:44.664156+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.
