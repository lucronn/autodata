# Public preview read-only rollout verification

Status: DRAFT; PR412 protected merge and final source/build pins pending. No live mutation.

Goal: Publish merged Workshop source with API-only read_only commerce, preserving existing Firebase identity, paid access reads and all private runtime dependencies.

Issue: https://github.com/lucronn/autodata/issues/410
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzTRQ`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-preview-read-only-rollout.md`. Canonical receipt: `docs/verification/2026-11-14-workshop-preview-read-only-rollout.md`. Record: `docs/agents/records/2026-11-14-workshop-preview-read-only-rollout.json`.

Source compatibility finding: serving old private quote/library/grant methods and supporting owner/scope/readability helpers are AST-identical to PR412; unchanged paid article/media transport can retain old ingestion. The new API-only mode does not propagate to Python. No authenticated live content or payment acceptance is claimed.

The canonical plan freezes existing runtime hashes, exact one-field API env output hash, persistent backup and rollback, final merged-source rebuild, bounded endpoint/asset checks and real public browser sign-in readiness. Old live sign-in race evidence is retained privately; final receipt must record source, build, checkpoint, service/config/ingestion identities, phase timestamps/results and rollback if exercised.

Concrete todo:

- [ ] Confirm protected merge of PR412, pin merged full source SHA/tree and exact git archive, run source suites and rebuild/hash the API artifact.
- [ ] Seal exact source/binary/asset pins in this plan and verification; synchronize Issue410/Project8, commit checkpoint and pass canonical preflight before runtime execution.
- [ ] Capture hash-verified private rollback copies of the existing API env and99 override; install the new binary and atomically change only the API env commerce mode and override binary path.
- [ ] Restart only the API once and verify process identity, dependency/readiness convergence, disabled purchase/demo, exact embedded assets and real browser sign-in readiness/navigation layout.
- [ ] On any failure restore both exact previous files and old executable once; retain bounded rollback probes and report final state without changing private ingestion or payments.
