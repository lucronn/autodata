# Banktwo selector casing verification

**Goal:** Make public Workshop make/model IDs resolve to exact provider labels and persist/query complete configurations so the real vehicle cascade works for Banktwo.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-11-06-banktwo-selector-casing.md`

**Status:** implementation merged; live release acceptance pending.

## Concrete todo

- [x] Reproduce the make/model case and punctuation mismatch with both configured source scopes and public IDs; pin the exact implementation base.
- [x] Add bounded Python source-label resolution for make and model selector calls, with focused exact/slug/ambiguous/error tests.
- [x] Add Go slug-aware scoped vehicle/configuration lookup with focused mixed-case and punctuation tests.
- [ ] Verify CI and a bounded live Ford / Figo (MEXICO) vehicle cascade, then record the exact release result without changing article or payment access.

Live diagnostic before implementation: Banktwo `models(year=2020, make=Ford)` returned nine rows, while `make=ford` returned 404. Banktwo `configurations(year=2020, make=Ford, model=Figo (MEXICO))` returned one row; normalized lowercase values returned 404. Public Ford models returned 29 options with `complete:false` after the first catalog deployment. The article reader and paid access remain separate acceptance boundaries.

## Exact merged release checkpoint

[PR #364](https://github.com/lucronn/autodata/pull/364) merged at `814a1c26e893fe181327516cfa4b48a800978c43`. Its tree is `60803944e30c87e98f5d85fd3e177d44e6a99696`, identical to the reviewed head and staged source/API artifact. Required [CI run 42330770348](https://github.com/lucronn/autodata/actions/runs/42330770348) passed all jobs, including Go API, ingestion, development adapters, GCE host delivery, and live Compose smoke. Independent cross-review of the Python and Go changes found no blocking issues. The release checkpoint is synchronized in [Issue #186 comment 6701459940](https://github.com/lucronn/autodata/issues/186#issuecomment-6701459940) and the dedicated Project #8 field.

The live release is still pending bounded Ford/Figo selector acceptance. The payment/reader grant path is outside this hotfix; production checkout remains disabled.
