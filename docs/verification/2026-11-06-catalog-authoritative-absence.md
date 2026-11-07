# Authoritative catalog absence verification

**Goal:** Finish merged selector scopes when a complete bank parent catalog proves that a make or model is absent.

**Issue:** https://github.com/lucronn/autodata/issues/186

**Project:** https://github.com/users/lucronn/projects/8

**Plan:** `docs/superpowers/plans/2026-11-06-catalog-authoritative-absence.md`

**Status:** planning checkpoint; implementation and live verification pending.

## Concrete todo

- [ ] Failing client test for complete parent absence, retaining validated source pages.
- [ ] Failing merge test for Bankone rows plus Banktwo proven absence and real provenance.
- [ ] Minimal typed absence conversion at the source provider boundary, preserving all other failure semantics.
- [ ] Focused/full tests, required CI, and bounded live 2027 Ford canary with no article/checkout changes.

The live trigger before implementation is US 2027 Ford models: 13 Bankone rows, `complete:false`; Banktwo's complete 2027 makes page has 34 rows and no Ford. The current Banktwo client returns generic `NOT_FOUND` after proving absence, leaving the all-provider completion marker at version 0. Authenticated article access and payment remain separate acceptance boundaries.
