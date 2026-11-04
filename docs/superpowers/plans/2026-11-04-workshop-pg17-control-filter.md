# Workshop PG17 Diagnostic Unicode Control Filter Correction Plan

**Goal:** Correct only the blocked acquisition diagnostic character filter to reject Unicode Cc controls except LF/tab; preserve all existing receipt guards, quarantine and runtime denials.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8; item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.
Base receipt `0950bbd5cea6c23e6d64944fac2b59cbc725f571`; blocked predecessor gate `4bc40e26ca12521be8f20282b897f5af68d0195e`, reviewed plan SHA256 `6de537cf729d612bd0d19d520a777350477d8e382dbbfe5ca050f8ebea2a5cf3`.

Planning only. No Docker/create/start/export/retry/download/install/image/PG/harness operation. The predecessor remains blocked by independent review and must not be adopted. Exact corrected-checkpoint re-review/adoption plus root verification/fresh dispatch remain mandatory. Implementation allowlist is empty; no integration or production authority.

## Reproduced blocker and only correction

Independent P2: `ord(c) >= 32` accepted DEL U+007F and C1 U+0085 although both are Unicode category Cc. Pure probes against the exact blocked fragment reproduce acceptance of both appended to complete retained second-attempt stdout. Those are red negative probes, not successful runtime observations. Dedicated evidence `docs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.json` retains exact blocked plan hash, probe outcomes, fixed fragment hashes and complete offline replay.

The only operative change in `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-receipts.md` is adding `import unicodedata` and replacing the character predicate with `c in '\n\t' or unicodedata.category(c) != 'Cc'`. This rejects every Unicode Cc control (C0, DEL, C1), with exactly LF U+000A and tab U+0009 permitted. CR U+000D is rejected. UTF8 decoding, all status/anchored diagnostic checks and limits remain unchanged. No normalization or removal of input characters. No expanded character-policy change beyond the requested Cc correction.

The complete fixed diagnostic fragment, byte-identical to the operative plan, is:

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

## Verification and unchanged authority

Complete retained second-attempt raw replay and all existing41 diagnostic/volume,18 Mounts,24 context fixtures pass offline. Add exhaustive65 Cc probes:63 negatives reject; LF/tab positives pass, including explicit DEL U+007F and C1 U+0080/U+0085/U+009F negatives. Total148 pure cases pass,0 fail. Old DEL/C1 predicates fail the negative expectation. Raw hashes/actual failures remain immutable; the historical missing structured-volume proof still rejects and all33 fresh APKs plus prior33 remain quarantined Ndocs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.jsonER reusable.

Structured complete volume inspect authority/bounds, source-output/signature/index/hash checks, exact image/payload/network/caps/resources/mounts, mandatory27 prestart copies BEFORE export/diff, full complete Mounts comparison, underlying target proof, stopped diff/context/baseline/exit audits, exact-owned cleanup/absence/volume comparison and offline/Task2 separation are unchanged. Pure tests and synchronization do not authorize retry or retrospectively accept either APK set. No runtime/production/schema/grant/service/deployment readiness follows.

## Concrete todo

- [ ] Preserve exact blocked gate/plan hash and reproduced DEL/C1 negatives; update only diagnostic Cc filter/import, rerun complete83-case pure/replay suite plus65 Cc probes, then synchronize Issue186/Project8/canonical docs after coordinator tracking-slot release.
- [ ] Commit/push docs-only corrected checkpoint, pin passing full-SHA preflight and exact tracking readback while preserving CURRENT Python SIGTERM and PG predecessor index verbatim/hash.
- [ ] Require independent exact-corrected-checkpoint re-review/adoption, root verification and fresh Task1A dispatch before any Docker/retry/download/harness; previous blocked gate grants no adoption authority.
- [ ] Keep structured complete volume metadata collection/comparison and every original source/payload/config/mount/copy/export/diff/baseline/signature/cleanup bound unchanged; both33APK sets remain quarantined NEVER reusable.
- [ ] Retain all red receipts as failed and offline replay as predicate evidence only; no retrospective acceptance, offline install/image commit/PG startup/harness/production action or readiness claim.

Unicode Cc corrected successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621857074 and Project8 readback at `2026-11-04T03:36:44.664156+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned Unicode Cc corrected successor checkpoint: `b96a68e59a370314a207e67b98d67a9949584432`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-control-filter-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621859742. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed Cc-safe acquisition receipt adoption

Adopt independently approved corrected gate `b96a68e59a370314a207e67b98d67a9949584432`, receipt `eee037dd1857cec1d0817b1b3421c7280c9284f6`; exact reviewed control-filter plan SHA256 `ad2a433f532e1b7b8000588d126d9789392f6e593a5c460681b900bff403420e`. Approval was relayed directly by coordinator after independent re-review. Historical predecessor4bc40e26 remains a blocked superseded checkpoint; this adoption consumes only the corrected approved chain. Adoption branch `codex/workshop-pg17-receipts-adoption`; record `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-receipts-adoption.json`.

The fixed classifier requires empty stderr and zero successful supervised/stopped status, rejects anchored diagnostic forms, and rejects every UnicodeCc character except LF/tab. All original source-output/index/key/signature/package/hash checks remain mandatory. Structured volume metadata uses bounded read-only ls names plus one complete inspect object per exactName: <=32names,60s total inventory,10s each inspect,512KiBstdout/64KiBstderr each,16MiB totalstdout/2MiBstderr. Exact same Name set; compare COMPLETE objects including all fields/values and null/map distinctions, ignore only JSON object key order; duplicate/missing/extra names/fields or any drift fail. Raw/hash/canonical receipts are mandatory. No CSV Labels substitution or four-field projection.

Full predecessor chain retained: exact cached image/payload/repositories; no source/secret bind; private inherited PGDATA override plus original tmpfs/binds; original network/caps/security/resources/output/deadline bounds; complete config and uniqueDestination Mounts records; ALL27 inherited prestart cp snapshots+unchanged comparison BEFORE first created export/diff; bounded created/stopped underlying empty target proof; complete stopped diff/context/baseline/signature/exit audits; exact-owned stop/rm--volumes/absence/structured inventory proof. No acquisition commit/restart/reuse; no arbitrary retry/guard change. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged.

Both historical33APK sets (overlay first and bound-target second payload attempts) remain quarantined, unaccepted and NEVER reusable. Red result/diagnosis and missing prior structured proof are not rewritten. Pure148-case/replay success is predicate evidence only. Root must independently verify full adopted-SHA preflight and issue a FRESH Task1A dispatch before any new Docker operation. This docs-only adoption performs no Docker/create/start/export/retry/download/install/image/PG/harness/implementation or production action; no readiness follows.

Concrete adoption todo:

- [ ] Synchronize exact corrected independent approval/plan hash and full Task1A guard chain in Issue186/Project8/canonical docs while preserving CURRENT prior Project index/detail verbatim/hash; commit/push and pin full-SHA passing preflight.
- [ ] Require root independent adopted-gate verification and FRESH Task1A dispatch before any Docker/retry; use a new private exact-owned run and never historical failed containers/APKs.
- [ ] Use the fixed anchored diagnostic/status classifier rejecting all UnicodeCc except LF/tab, empty stderr and successful supervised/stopped status; retain complete raw outputs/hashes and all original source/index/signature/hash checks.
- [ ] Collect complete structured volume inspect objects for exact boundedls names before create/after owned removal:32names/60s inventory/10s perinspect/512KiBstdout64KiBstderr perinspect/16MiB totalstdout2MiBstderr; compare complete objects by uniqueName, all fields/values preserved and only JSON key order ignored.
- [ ] Keep all inherited image/payload/network/caps/resources/private mount guards,27 prestart copies BEFORE first export/diff, complete Mounts comparison, bounded empty underlying target exports, full stopped diff/context/baseline/exit and owned cleanup/absence checks; both33APK sets remain quarantined NEVER reusable.
- [ ] No adoption Docker/retry/download/install/image commit/PG startup/harness/implementation/integration/production/provider/cloud action; offline stages/Task2 separate and all readiness remains unverified.

Reviewed Cc-safe acquisition receipt adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621879747 and Project8 readback at `2026-11-04T03:38:22.919883+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed Cc-safe acquisition receipt adoption checkpoint: `691f187302440509c23da99f4fb9e1adb9cd52a4`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621883014. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 independently approved frozen closure: docs-only index

Record independent acceptance of the exact Task1A frozen signed33APK closure as input only, preserve acquisition/cleanup evidence and keep Task1B/image/Task2 unauthorized pending a new gate/review/root dispatch.

Acceptance plan `docs/superpowers/plans/2026-11-04-workshop-pg17-closure-acceptance.md`; record `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-closure-acceptance.json`; exact evidence index `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-evidence.json`. Executed691f187 result SHA19002cbf07ce2879e277e1a3e7bc1d69ac28ae8e919e29a85bc4d7a415ee3d43; frozen33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238. Independent audit approval saved at `/tmp/autodata-pg17-task1a-closure-review.md`, SHA256 `bb0173a6f7a46f52fd7a4c3bfbcfcf00d2db5714f179abfe1124675a69616b5b`, and relayed directly by coordinator; all174receipt refs/33host hashes verified, exact cleanup/absence/four-volume equality passed. Accepted as frozen input only; raw pending-review status remains immutable. NEW Task1B gate/review/root dispatch required; offline simulation/install/image/Task2 remain unauthorized/unexecuted, both prior33APK quarantines NEVER reusable. JS deadline slot released; frozen-input acceptance index synchronized. No Docker/install/harness.

Concrete todo:

- [ ] After JS deadline coordinator releases Issue186/Project8 slot, synchronize exact reviewed closure/result/manifest/hash acceptance in Issue186/Project8 and canonical docs, preserving CURRENT full index/detail verbatim/hash; commit/push and pin docs-only full-SHA preflight.
- [ ] Keep raw Task1A receipts and accepted-apk-manifest bytes immutable; use this adjacent acceptance index to record independent review without rewriting the original pending-review manifest status or either failed/quarantined attempt.
- [ ] Accept only exact33APK filenames/versions/architectures/hashes in the pinned manifest as future input; verify all host hashes again before any later authorized consumer and reject mutation or substitution.
- [ ] Require a NEW decision-complete synchronized Task1B gate, independent review, root verification and fresh dispatch before offline simulation/install/image commit or toolchain inspection; no execution authority follows from closure acceptance.
- [ ] Keep original Task2 PG startup/harness separately unauthorized, all runtime/production/grants/services/deployment readiness unverified, and both historical33APK sets quarantined NEVER reusable.

Frozen-input closure acceptance synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621963547 and Project8 readback at `2026-11-04T03:44:34.583302+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Input closure independent approval recorded; NEW Task1B synchronized gate/review/root dispatch required; no Docker/install/image/PG/harness actions.

Pinned frozen-input closure acceptance index checkpoint: `04093a5e176499e7d8de18e9573f9fea3abe9d3a`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621970383. Frozen input independently accepted only; NEW Task1B gate/review/root dispatch required. No container/image/package/harness action or readiness claim.


## PG17 Task1B offline simulation-only successor

Gate one bounded offline Task1B simulation of the immutable independently accepted33APK closure using exact20 new-package inputs, unchanged baseline and complete cleanup; installation/image/Task2 remain separately unauthorized.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`; record `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-task1b-simulation.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`. Independent feasibility report SHA256e82b42d46639d0149b7cf644cb0bbdd29f86bb020cf5410fcdfcea007779ab88. Accepted33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238 remains immutable; exact20 add operands/all33 verification, created/stopped empty bind targets, exact inherited0600zero lock, deterministic Cc-safe parser/unchanged45+27 baseline, pinned BusyBox trigger.58 metadata dependencies (36base/22new) and 95 pure parser fixtures are NOT solver success. Docs only; simulation denied until independent review/adoption/root verification/fresh dispatch. Installation/image/Task2/production remain unauthorized/unverified, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only simulation successor in Issue186/Project8/canonical notes, preserving CURRENT full prior index/detail verbatim and SHA256; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent review of this exact simulation-only checkpoint; require coordinator adoption/root verification and fresh one-attempt dispatch before any Docker command.
- [ ] On authorized fresh simulation only, reverify all33 immutable APK hashes/signatures, use exact20 literal apk-add paths, inspect complete offline resources/mounts and mandatory prestart27 copies before created export/diff.
- [ ] Require deterministic bounded parser with exactly20 additions and no baseline actions, complete unchanged27/package45/world/keys/PG/scripts/trigger/lock state and created/stopped empty bind-target proof; fail closed/quarantine/no retry.
- [ ] After exact-owned removal/absence/complete-volume equality, independently review simulation receipts; a NEW installation gate must pin same20 APK argv and audit BusyBox-trigger effects. No installation/image commit/PG/harness/readiness is authorized now.

Task1B simulation-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622084338 and Project8 readback at `2026-11-04T03:53:46.055147+00:00`; full prior closure index/detail preserved verbatim/hash in comment and dedicated record. Independent exact-checkpoint review/adoption/root verification/fresh dispatch required; no Docker/retry/install/image/harness operation or solver success.

Pinned Task1B simulation-only successor gate: `808225f5fa14ca0c7dc308a5d39cd65396c694f7`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622095482. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.
