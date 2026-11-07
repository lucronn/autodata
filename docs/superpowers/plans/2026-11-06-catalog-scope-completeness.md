# Catalog scope completeness implementation plan

**Goal:** Persist sparse make/model selectors and require all-provider completeness, healing legacy partial scopes on bounded catalog GETs.
**Architecture:** Store source-enumerated selector rows in the existing hydration scope row. A versioned completion marker certifies that both persistence and all configured providers completed. Existing legacy markers remain preserved but cannot suppress the next makes/models GET hydration. API reads union sparse selectors with full identities, so bounded configuration deepening is optional for selector visibility.
**Tech stack:** Python ingestion, PostgreSQL JSONB, Go API.
**Issue:** https://github.com/lucronn/autodata/issues/186
**Project:** https://github.com/users/lucronn/projects/8
**Canonical document:** docs/architecture/provider-neutral-catalog-api.md

## Diagnosis and constraints

`_persist_resolved_catalog_rows` drops makes/models without a full vehicle identity, while `_persist_hydration_scope` marks their scopes complete. Background deepening is deliberately bounded, so only a fraction becomes visible. `CacheFirstCatalogService.resolve` additionally treats any successful provider as complete and clears other failures. No connector-client edits, production mutation, deployment or fleet crawl is authorized in this implementation. Preserve generic non-selector service behavior and article lifecycle semantics. Limit new all-provider completeness semantics to makes/models.

## Concrete todo
- [ ] Add failing regressions for sparse selector persistence, mixed provider outcomes, and legacy marker recovery.
- [ ] Add migration 042 with selector_rows JSONB and completion_version; persist scoped selector rows and all-provider completion atomically.
- [ ] Union durable sparse selectors into scoped API reads and ignore legacy completeness markers for makes/models.
- [ ] Preserve existing single-flight and incomplete replay TTL; run focused Python/Go and isolated PostgreSQL checks.
- [ ] Commit/push validated milestones, open PR, and record deployment order: connector fix, migration, worker/API restart, bounded GET healing.

## Task 1: durable sparse selectors and completeness

Files: new db/migrations/042_catalog_selector_rows.sql; workers/ingestion-python/src/autodata_ingestion/catalog_service.py; workers/ingestion-python/tests/test_catalog_service.py; new workers/ingestion-python/tests/test_catalog_selector_persistence.py; apps/api-go/catalog_store.go; apps/api-go/catalog_http.go; apps/api-go/catalog_test.go; new apps/api-go/catalog_selector_store_test.go.

1. Add failing tests: both provider orders with one failed/incomplete provider must retain usable rows and report incomplete; sparse makes/models must persist only requested year/make/region values without synthetic vehicles. Empty complete enumeration remains complete. Partial enumerations persist usable rows without trusted completion.
2. Run regressions and capture failures before implementation.
3. Migration adds `selector_rows jsonb NOT NULL DEFAULT '[]'` with an array check and `completion_version integer NOT NULL DEFAULT 0`; do not upgrade old rows. No destructive rewrite.
4. For makes/models, complete only when every configured provider completes; clear stale cache missing scopes only after all sources succeed. Save sparse selectors in hydration scope upsert, with version 1 only on complete reads; partial reads retain previous selector choices through JSONB set union and version 0. Rows carry only year/make/model/region, validated against requested selectors; provenance remains separate.
5. API makes/models queries union matching `selector_rows` entries with existing nonrejected full identities. ScopeComplete requires completion_version=1 for makes/models, and legacy fleet-sync fallback cannot certify these scopes. Keep configurations behavior unchanged. For makes/models, trust complete empty enumerations and stop scheduling repeated hydration merely because item count is zero.
6. Run focused Python catalog/deepening tests and Go catalog tests. Run isolated PostgreSQL migration upgrade and real sparse query/persistence tests, including legacy completed row -> incomplete -> completed after one successful refresh, cross-year/make/region isolation and complete empty scope.
7. Commit coherent implementation milestone and push promptly after checks.

## Task 2: verification and delivery

Record exact checks, migration compatibility and operational limits in canonical doc and this plan. Existing API single-flight and worker 20-second incomplete replay TTL remain the request bounds; no broad backfill is introduced. Open a PR and synchronize exact SHA/evidence in the dedicated Project field and Issue comment. Deployment order is connector OSError fix first, migration 042, then worker/API with new queries; restart both to clear legacy process caches. A single ordinary GET for each affected scope heals that scope and subsequent reads use stored results. Root coordinator owns deployment and live verification.
