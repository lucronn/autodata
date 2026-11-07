# Banktwo selector casing verification

**Goal:** Make public Workshop make/model IDs resolve to exact provider labels and persist/query complete configurations so the real vehicle cascade works for Banktwo.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-11-06-banktwo-selector-casing.md`

**Status:** planning checkpoint; implementation and live acceptance pending.

## Concrete todo

- [ ] Reproduce the make/model case and punctuation mismatch with both configured source scopes and public IDs; pin the exact implementation base.
- [ ] Add bounded Python source-label resolution for make and model selector calls, with focused exact/slug/ambiguous/error tests.
- [ ] Add Go slug-aware scoped vehicle/configuration lookup with focused mixed-case and punctuation tests.
- [ ] Verify CI and a bounded live Ford / Figo (MEXICO) vehicle cascade, then record the exact release result without changing article or payment access.

Live diagnostic before implementation: Banktwo `models(year=2020, make=Ford)` returned nine rows, while `make=ford` returned 404. Banktwo `configurations(year=2020, make=Ford, model=Figo (MEXICO))` returned one row; normalized lowercase values returned 404. Public Ford models returned 29 options with `complete:false` after the first catalog deployment. The article reader and paid access remain separate acceptance boundaries.
