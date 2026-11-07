# Authoritative catalog absence verification

**Goal:** Finish merged selector scopes when a complete bank parent catalog proves that a make or model is absent.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-11-06-catalog-authoritative-absence.md`

**Status:** implementation verified; required CI and live release pending.

## Concrete todo

- [x] Failing client test for complete parent absence, retaining validated source pages.
- [x] Failing merge test for Bankone rows plus Banktwo proven absence and real provenance.
- [x] Minimal typed absence conversion at the source provider boundary, preserving all other failure semantics.
- [ ] Focused/full tests, required CI, and bounded live 2027 Ford canary with no article/checkout changes.

The live trigger before implementation is US 2027 Ford models: 13 Bankone rows, `complete:false`; Banktwo's complete 2027 makes page has 34 rows and no Ford. The current Banktwo client returns generic `NOT_FOUND` after proving absence, leaving the all-provider completion marker at version 0. Authenticated article access and payment remain separate acceptance boundaries.

## Exact implementation verification

The implementation head is `72bc2fa6b7d245e8a1d087ecf1e4572c7f5e1071` on `codex/catalog-authoritative-absence`, after the synchronized planning checkpoint `b360c1e`. Test-first milestones `213bebf`, `58853a4`, and `72bc2fa` preserve validated parent pages and convert only proven absence into an empty completed contribution. No child source envelope is fabricated. Missing structured labels, malformed or incomplete pagination, ambiguity, auth/rate/server errors, timeout, and child failure after a matched parent remain incomplete. Independent review found no actionable issue.

The dependency-complete ingestion suite passed: **1,171 passed, 475 skipped, 176 subtests passed**. The coordinator independently reran focused connector/catalog tests: **52 passed, 13 skipped, 36 subtests passed**; `git diff --check` passed. [Issue #186 implementation comment](https://github.com/lucronn/autodata/issues/186#issuecomment-6701625518) and the dedicated Project #8 field record the same head and todo. Required PR CI, merged-source binding and bounded live 2027 Ford acceptance are pending.
