# Banktwo selector casing verification

**Goal:** Make public Workshop make/model IDs resolve to exact provider labels and persist/query complete configurations so the real vehicle cascade works for Banktwo.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-11-06-banktwo-selector-casing.md`

**Status:** selector hotfix live; broader catalog and paid-reader release pending.

## Concrete todo

- [x] Reproduce the make/model case and punctuation mismatch with both configured source scopes and public IDs; pin the exact implementation base.
- [x] Add bounded Python source-label resolution for make and model selector calls, with focused exact/slug/ambiguous/error tests.
- [x] Add Go slug-aware scoped vehicle/configuration lookup with focused mixed-case and punctuation tests.
- [x] Verify CI and a bounded live Ford / Figo (MEXICO) vehicle cascade, then record the exact release result without changing article or payment access.

Live diagnostic before implementation: Banktwo `models(year=2020, make=Ford)` returned nine rows, while `make=ford` returned 404. Banktwo `configurations(year=2020, make=Ford, model=Figo (MEXICO))` returned one row; normalized lowercase values returned 404. Public Ford models returned 29 options with `complete:false` after the first catalog deployment. The article reader and paid access remain separate acceptance boundaries.

## Exact merged release checkpoint

[PR #364](https://github.com/lucronn/autodata/pull/364) merged at `814a1c26e893fe181327516cfa4b48a800978c43`. Its tree is `60803944e30c87e98f5d85fd3e177d44e6a99696`, identical to the reviewed head and staged source/API artifact. Required [CI run 42330770348](https://github.com/lucronn/autodata/actions/runs/42330770348) passed all jobs, including Go API, ingestion, development adapters, GCE host delivery, and live Compose smoke. Independent cross-review of the Python and Go changes found no blocking issues. The release checkpoint is synchronized in [Issue #186 comment 6701459940](https://github.com/lucronn/autodata/issues/186#issuecomment-6701459940) and the dedicated Project #8 field.

## Live selector outcome

The first operator attempt stopped before its public canary on a strict Docker inspection comparison. Its receipt reports recovery incomplete, while independent read-only checks confirmed the original ingestion container, API binary, article worker and public readiness were healthy. Docker had normalized `OomKillDisable` from false to null for the replacement container and returned the same worker mounts in a different list order. The failed container and evidence were retained. A narrowly revised, independently reviewed operator used a distinct retry name and fresh evidence directory. Its private retry receipt at `/home/corp/autodata-evidence/banktwo-hotfix-release-run-814a1c2-r2-20261107T0313Z/receipt.json` reports `status: passed`, no migration, no worker stop, and the same article worker.

Public US canary: 2020 Ford models returned 29 options with `complete:true`, including `figo-mexico`; Figo (MEXICO) returned one scoped configuration and then `complete:true`. Additional samples returned 61 complete makes for 2014, 32 complete Toyota models, three complete Camry configurations, and 49 complete makes for 2027. The main Workshop browser reached a 2014 Toyota Camry 2.5 configuration. Public `/readyz` returned 200 and checkout remained disabled. [Issue #186 outcome comment](https://github.com/lucronn/autodata/issues/186#issuecomment-6701533809) and the Project #8 field contain the same bounded result.

A 2027 Ford sample returned 13 model options but remained `complete:false` and `hydrating:true` during bounded observation, so this hotfix does not establish complete coverage for every provider/year/make. The live app still requires Google login and an exact paid grant before a real article can open; production purchasing is disabled in Stripe test mode and no paid-grant acceptance was performed. Eight existing article projections are available behind the grant check, four through source fallback. Paid release and broader source coverage remain separate work.
