# Parallel Workshop implementation and integration

User direction: use all three worker slots concurrently to finish the platform quickly. The coordinator owns integration, acceptance execution, remaining commerce fixture repair and release tracking. All workers use gpt-6.1-sol, medium reasoning, Fast/priority, no fallback. Make coherent validated milestone commits and push promptly.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Dispatch and acceptance

This amendment replaces serial *implementation-dispatch* prerequisites in the paid-access and final-UI plans. Reviewed commerce candidate9d33e1eb522b045254374a120582658688311906 and the existing reviewed paid HTTP/media contract provide a fixed development interface. The coordinator may assemble them on the development integration branch and dispatch independent implementation after the synchronized checkpoint and machine preflight. Commerce was not runtime-accepted at dispatch. The later verified candidate `d2eb70fa9b96fcebe1c33ef6cddcdad5c4a5eec7` now passes all14 commerce,5 identity and8 R3 cases, actual production-image imports and full CI41705272372. See `docs/verification/2026-11-03-workshop-commerce.md`. Original failed receipts remain retained.

Implementation against a frozen interface may proceed while its runtime acceptance continues. Dependency failures return to their owner, with a focused committed repair and consumers updated explicitly. No fabricated mocks count as API/runtime acceptance. Independent review and the separate14 commerce,5 identity,8 R3,12 paid-access and141 browser cases, actual production image checks and CI remain required before release acceptance. No launch or deployment authorization is inferred from a passing code review.

## Disjoint ownership

- Article-access worker: the existing sixteen-path paid-access envelope except four media files below (twelve paths). Owns catalog_access.go/tests, postgres_catalog_access_test.go, main.go, catalog_http.go, OpenAPI JSON/YAML, test_paid_catalog_api_integration.py, paid-access collector/tests, runbook and workshop-interface.md. Owns routing, exact scope/grant checks, observational reads, explicit prepare, real twelve-case fixtures and integration of media hooks.
- Media worker: catalog_media_access.go, catalog_media_access_test.go, catalog_media_token.go and catalog_source.go only. Owns v2 token encoding, contextual source/article image projection, current-rights/grant checks before object reads and media unit tests. No edits to the access worker's files.
- UI worker: existing thirty-three-path UI envelope except docs/architecture/workshop-interface.md, which remains the article-access worker's exclusive file (thirty-two paths). Owns sign-in, checkout, library, article reader and all planned browser fixtures/tests. Preserve the delivered SDK bytes unless a justified rebuild is needed. UI consumes the frozen HTTP DTOs; fixture integration binds actual backend helper symbols after they are committed. No business API implementation in UI.

The paid-access and UI envelopes overlap only at workshop-interface.md; the exclusive allocation removes concurrent writes. No new application file, migration, service or test inventory is added by this amendment. Existing managed worktrees are reused on separate codex/ branches. The coordinator authorizes exact-SHA dependency merges and owns final integration/review. A worker may execute an expressly authorized dependency merge in its own branch to compile or test committed shared helpers; this preserves authorship and does not confer final acceptance. Workers must not edit another owner's paths.

## Shared Go interface

Article-access owner defines `PaidArticleIdentity` with string ConfigurationID, CanonicalArticleID, VehicleID, ProviderSlug, SourceVehicleRef and SourceArticleRef plus `CurrentSourceRevisionID *string`; `paidArticleIdentityStore.PaidArticleIdentity(ctx, configurationID, canonicalArticleID)`; server helpers `paidCatalogEnabled() bool`, `resolvePaidCatalogScope(ctx, Principal, configurationID, requestedRegion) (CatalogConfiguration,error)`, `checkPaidCatalogGrant(ctx, Principal, CatalogConfiguration) error` and `writePaidCatalogError(w,r,err)`. Actual authority remains trusted account plus organization, exact configuration and region.

Media owner defines server helpers `rewritePaidCatalogArticleImages(ctx, Principal, CatalogConfiguration, PaidArticleIdentity, *CatalogArticleView) error` and `servePaidCatalogImage(w,r,Principal)`. Source rendering consumes the same paid scope/identity and uses actual current source/canonical revisions. Article-access owner calls media hooks from catalog_http.go. Keep these definitions in already allowed files; if a literal Go type differs from this handoff, coordinate a minimal documented correction before both implementations diverge. Each worker may read another branch's committed interfaces but never copy mocks into production.

## Concrete todo

- [x] Synchronize this parallel allocation in Issue186/Project8, both canonical plans/task records and repository docs, commit the checkpoint, and run both exact-base machine preflights.
- [x] Dispatch three disjoint workers at the same pinned checkpoint; publish an early shared-interface commit so branches can compile against the concrete Go seam.
- [x] Coordinator repairs the remaining commerce fixture and executes commerce/identity/R3 acceptance and production-image proof while workers implement paid access, media and UI.
- [ ] Merge meaningful reviewed worker milestones, resolve actual helper/DTO differences, execute twelve paid-access and141 browser cases, retain all failed evidence and finish independent review/CI.
- [ ] Complete actual hosting, merchant/identity configuration, staging acceptance and deliberate cars.tk deployment; keep production status unverified until demonstrated.


The coordinator also owns the bounded existing `apps/api-go/main_test.go` expectation repair described in the paid-access plan. The paid-access envelope is seventeen paths; worker allocations stay twelve plus four and the UI allocation stays thirty-two.
