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

## Configuration completion safeguard before PR #366 release

The coordinator found an additional completion failure before deployment: a
complete empty Banktwo parent-absence contribution could mask a Bankone 502 for
2020 Honda Accord configurations. The configuration scope previously accepted
completion from any provider, unlike makes and models.

Implementation `6b163e24f1f9318a0b7455eb863bc9927f5d2b49`
(tree `9299213d373c4138352e4d671d2c07ac6ae47bbc`) extends the existing
all-provider completion rule to configurations. Every configured provider must
finish successfully before the scope becomes complete. Available cached/provider
rows and missing scopes survive an incomplete or failed contribution. This is
covered by a real client/provider regression combining Bankone 502 with typed
Banktwo model absence, and service regressions for both incomplete rows and a
failed provider alongside completed empty coverage. All three cases failed
before the one-line safeguard and passed afterward.

The synchronized preflight passed again at pinned base `b360c1e` with
`status: synchronized` and no errors. Focused connector, catalog service,
persistence, coverage, and index tests passed: **82 passed, 45 skipped,
38 subtests passed**. The dependency-complete full ingestion suite passed:
**1,173 passed, 475 skipped, 178 subtests passed** in 127.89 seconds. Independent
safeguard review passed with no findings at the exact implementation commit;
the reviewer independently confirmed **54 passed, 13 skipped, 38 subtests
passed** and a clean diff check. Required CI must apply to the updated PR head;
deployment remains paused pending coordinator release checks.

The coordinator's bounded pre-release audit also found an older F150 scope
`configurations|2027|ford|f 150|US` with single-provider provenance and
`completion_version: 0`. The public API reports it partial and schedules
hydration; an old ingestion process can replay a completed result from its
in-memory `_HYDRATION_RESULTS`. Replacing that process clears the memory cache,
and version 0 permits natural rehydration. After deployment, use a bounded
public GET/recheck to confirm the scope retries and remains incomplete until all
providers finish. No manual database deletion or invalidation is recommended or
authorized by this change. Existing cache records were not modified.
