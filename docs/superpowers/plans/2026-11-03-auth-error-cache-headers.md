# Preserve protected auth error cache headers

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

## Observed failure and exact decision

The actual twelve-case paid acceptance against integrated `3b551c992263f74e3ebdc6e4fa2c4ffda3b979a6` exposed four protected-route401/403 cache-header assertion failures. `paidCatalogAuthenticated` correctly establishes `Cache-Control: private, no-store` before identity/CSRF checks, but the shared `customerAuthService.writeError` replaces it unconditionally with `no-store`. Paid plan Frozen HTTP policy§6 requires the private directive on all protected responses and errors. Both directives already prevent storage; this bounded fix restores the stronger exact protected-route contract without changing authorization or pretending the failed run passed.

This planning lane is based on `fa30a2204dc8a5c0907d090ec4f41fdd8bec9b4b`. Root and hosting-builder checkouts remain untouched. Execution/review uses gpt-6.1-sol medium Fast/priority, no fallback.

The only production change is inside `customerAuthService.writeError`: preserve an already established exact trusted `private, no-store` header; otherwise set `no-store`. Do not preserve arbitrary nonempty cache policies such as `public, max-age=3600`. Do not infer policy from URL substrings, request headers or client input. All existing `/auth/config`, `/auth/session`, `/auth/firebase/session`, `/auth/logout` handlers continue to establish `no-store` themselves and retain their current successes/errors. Preserve statuses, safe JSON, retryability, request IDs, cookie clearing/preservation, CSRF/origin checks, session freshness and deadlines. No new wrapper, middleware, store, provider behavior or other implementation path.

## Exclusive two-file scope

- `apps/api-go/auth_http.go`
- `apps/api-go/auth_http_test.go`

This is a separately gated narrow amendment to the paid plan; it does not widen another builder's active allowed paths. No historical SQL, catalog wrapper/media, auth/session policy, OpenAPI, UI, fixture collector/supervisor, cloud or deployment files change.

## Concrete todo and test boundaries

- [ ] Save/read back Issue186 and Project8 after the hosting tracking update; commit this canonical plan, synchronized record and paid-plan amendment; pass machine preflight at that full checkpoint SHA. Coordinator reviews and authorizes implementation separately.
- [ ] Add failing table-driven `TestCustomerAuthErrorCachePolicy` in auth_http_test.go. For ErrUnauthenticated401, ErrCustomerBlocked403, ErrCustomerCSRF403 and ErrCustomerDependency503, assert that exact preinstalled `private, no-store` survives; empty, existing `no-store` and unsafe `public, max-age=3600` resolve to `no-store`. Check the existing error code/status/retryability and expected Firebase cookie behavior are unchanged.
- [ ] Add failing `TestCustomerAuthProtectedCachePolicy` in the same file, invoking the actual `paidCatalogAuthenticated` handler with a Firebase-mode customerAuthService and its actual Authenticate boundary. GET without session must return401, POST with invalid Origin/CSRF must return403, both retain `private, no-store` and `nosniff`, and protected next handler must not run. This requires no PostgreSQL/provider: use the existing in-process auth fixtures and empty cookie/invalid origin paths.
- [ ] Retain the strict existing `customerHTTP` helper assertion of exactly `no-store` for all actual `/auth/*` route tests, including successes, invalid exchange/logout and dependency failure. Add relevant cases if a route/error combination is currently uncovered; do not loosen the helper to accept either policy.
- [ ] Observe red against current production code, apply only the safe exact-header preservation inside writeError, then run green focused tests. Run `go test -count=1 -run '^(TestCustomerAuthErrorCachePolicy|TestCustomerAuthProtectedCachePolicy|TestCustomerAuthHTTPBoundaries|TestCustomerLocalLoginUnavailable|TestConfiguredCustomerAuthRequiresPersistenceAndWiresServer)$' .` from apps/api-go; retain stdout and exact input hashes outside the checkout. Use existing Go1.26 toolchain/caches without Docker/build/provider calls.
- [ ] Run normal `go test -count=1 ./...` and `go vet ./...` in apps/api-go, plus `git diff --check`; keep any optional integration skips distinguished from actual acceptance. Commit/push the two-file validated change and obtain independent exact-commit review.
- [ ] Coordinator integrates the reviewed fix, preserves the failed paid-run evidence and reruns the existing full twelve-case paid inventory under the frozen supervisor on an exact integrated candidate. This plan adds no logical case and does not weaken any raw header assertion. Identity5/catalog8/commerce14/browser120+21 and finalCI remain their own required release evidence.

No real credentials, Firebase, Stripe, bank/model, Docker, cloud/DNS or live application operation is authorized or needed for this bounded implementation. Planning/preflight/unit tests do not establish actual paid runtime or production readiness.
