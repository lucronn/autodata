# Public preview read-only rollout verification

Status: merged-source artifact sealed; synchronized gate before private-helper preparation and root execution. No live mutation.

Goal: Publish merged Workshop source with API-only read_only commerce, preserving existing Firebase identity, paid access reads and all private runtime dependencies.

Issue: https://github.com/lucronn/autodata/issues/410
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzTRQ`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-preview-read-only-rollout.md`. Canonical receipt: `docs/verification/2026-11-14-workshop-preview-read-only-rollout.md`. Record: `docs/agents/records/2026-11-14-workshop-preview-read-only-rollout.json`.

Source compatibility finding: serving old private quote/library/grant methods and supporting owner/scope/readability helpers are AST-identical to PR412; unchanged paid article/media transport can retain old ingestion. The new API-only mode does not propagate to Python. No authenticated live content or payment acceptance is claimed.

The canonical plan freezes existing runtime hashes, exact one-field API env output hash, persistent backup and rollback, final merged-source rebuild, bounded endpoint/asset checks and real public browser sign-in readiness. Old live sign-in race evidence is retained privately; final receipt must record source, build, checkpoint, service/config/ingestion identities, phase timestamps/results and rollback if exercised.

Concrete todo:

- [x] Confirm protected merge of PR412, pin merged full source SHA/tree and exact git archive, run source suites and rebuild/hash the API artifact.
- [x] Seal exact source/binary/asset pins in this plan and verification; synchronize Issue410/Project8, commit checkpoint and pass canonical preflight before runtime execution.
- [ ] Capture hash-verified private rollback copies of the existing API env and99 override; install the new binary and atomically change only the API env commerce mode and override binary path.
- [ ] Restart only the API once and verify process identity, dependency/readiness convergence, disabled purchase/demo, exact embedded assets and real browser sign-in readiness/navigation layout.
- [ ] On any failure restore both exact previous files and old executable once; retain bounded rollback probes and report final state without changing private ingestion or payments.

Merged source `3a18d9c7ca51606a1dfb6d7691d3039d6d27c9f3`, tree `56ea54898aeb351ae25f44b8a6b376ad03e30efa`, archive SHA256 `d9dc79f53776137d43f7175504e03818d1eadac4cdcce2c371707febcb48fdf4`. Binary SHA256 `0b17821ca4892d7776126c349db5fe70d5292c893a9acdca2ae5e27c3f0f9f93` (61400205 bytes), rebuilt from exact extracted archive with Go1.26.4 CGO0 -trimpath. API Go16.956s/shared-contract suites passed; Workshop Node267/267 passed.13 embedded asset hashes and full logs/build metadata are sealed in private release-manifest.json under `/home/corp/autodata-evidence/preview-release-3a18d9c7/`. Source merged under protection at00:53:33Z from reviewed PR412 head ee2c2be. No pre-merge binary substitution.

Fresh pre-seal inventory confirms old API PID375924/executable selector-ui-cad924e-r1 and prior binary/env/99 hashes unchanged,10-Docker dependency hash493beef2c5d9fe2190995c1b63ab9c3f094f58f3cda3930048031b6a57c5ecd3. Private ingestion7ce6c5a98bec69f57d2e1c53ac584f5c9a97e74eb3da0a474c8719b81e8c0d72 remains same old source/image/security. Target env SHA25674a93e2198fe8b024fadce9a26845990f3c15cbc9681ddd873a704e13a16aa03; target99 SHA2561172a455bfb2cea79a0f01112e467c37301cac4bc083c1bcee00632d0301f878. Full exact runtime and rollout/rollback boundary are in the plan. Route correction5ecd01c is preserved.

## Private helper seal and read-only baseline

Source-seal checkpoint `15806f8cc3cee7d9515feee96770bf2a027afd05` passed canonical machine preflight (`status:synchronized`, `errors:[]`) after literal Issue410/Project8 readback and before private helper preparation. No repository implementation or live configuration was edited by helper preparation.

- `release-manifest.json` SHA256 `b72ab1d1928cb4e958d8576ae173aefe8c990c27f1bdd81ae6f53cbcb064b50d`.
- `release_probe.py` SHA256 `56d843a9fceff78c497aab6926075216e2d4095117f8652d83db60f929c84c7c`.
- `rollback_helper.py` SHA256 `93c3073a8549dc90613ee45674dc1480833156c509abc1fbc465e18d081b6366`.
- `verify_rollback_fixture.py` SHA256 `5ff208370ef5988d79e806cba177c23fe8b86f8e3ce367e14c82ecfb60b567b7`.
- `rollback-fixture.log` SHA256 `80c63fe7309035fa1dac2c3a59c18607b18ed3fe64ffb70fa334693a943c487b`.

Both executable helpers are private0500 files. Source compilation and help succeeded. `rollback_helper.py check` verified current old API/file/artifact/ingestion identities without mutation. `release_probe.py baseline` passed8 checks and retained `baseline-probes-1794704147142218822.json`; this includes the observed public308/local200 route distinction. It did not call demo-mode on old source or account/payment/article endpoints.

Offline rollback fixture passed: backup preparation leaves simulated live files unchanged; unexpected drift is refused before write/attempt reservation; exact both-file bytes and metadata restore; one inert restart; repeated restore refused. The first fixture attempt exposed missing old-binary metadata in the test fixture; the real sealed manifest already contained that field. The corrected fixture schema passed. No real prepare/restore/apply/restart was executed. Actual root rollback remains unexercised; fixture success is not runtime recovery evidence.

Precise root commands are retained privately in `ROOT-COMMANDS.md` under the evidence root, with hash-verified backup preparation, destination artifact install, same-filesystem temporary target staging and atomic env/99 replacements, one API restart, candidate probes and explicit restore on failure. Root performs independent final review and browser QA. Existing Node Playwright1.62.1 package at `/home/corp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`, Chromium `/usr/bin/chromium`, args `--no-sandbox --disable-dev-shm-usage` require no package installation. No System Python Playwright usage.
