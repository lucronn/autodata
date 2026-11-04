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
