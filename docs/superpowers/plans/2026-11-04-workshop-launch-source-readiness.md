# Workshop entry and purchase configuration source Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans only after fresh exact-K canonical preflight, independent checkpoint review and explicit dispatch. This planning checkpoint cannot authorize implementation before exact-K review and explicit dispatch.

**Goal:** Make Workshop the application root entry and enforce current purchase configuration readiness without enabling sales.

**Architecture:** Retain embedded JSON and pure purchaseConfiguration(config, quote). Change only exact Go root target and one current-contract predicate; add focused regression coverage.

**Tech Stack:** Go net/http/httptest; Node22 node:test and browser ECMAScript modules.

**Spec:** `docs/agents/specs/2026-11-04-workshop-launch-source-readiness.md`.

**Status:** synchronized planning only. Coordinator admitted DTO source S `0674adfb49744331b9edc430c5f556da6ee63cd5`; actual planning checkpoint K is sealed externally after commit. Inspection J is `d9be89d22ac288028d53867e56010bcca4898d64`; rendered queue source is `0674adfb49744331b9edc430c5f556da6ee63cd5`. Rendering against a SHA never admits it or grants authority.

**Tracking:** Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8, item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Literal goal/todo/path readback verified at `2026-11-04T23:12:08Z` in https://github.com/lucronn/autodata/issues/186#issuecomment-6644616654. Receipt `/home/corp/autodata-evidence/workshop-launch-source-gate-tracking/receipt.json` SHA256 `50811cf6e212bb2041de8181a28c8b7e5088f539343c7265627e3a2f10620d9c` preserves the prior Issue body/comments and other Project fields.

## Global constraints

- Exactly four implementation paths: `apps/api-go/main.go`, `apps/api-go/workshop/commerce.mjs`, `apps/api-go/workshop-client.test.mjs`, `apps/api-go/workshop_test.go`.
- Preserve USD2000 minor units, one configuration/region, workshop-v1 and entitlement/auth/checkout/return contracts.
- purchase-config.json remains byte-identical, disabled with null merchant fields. Literal helper validation is syntactic readiness only; app.mjs separately validates quotes.
- G1b approved policy/tax/immutable environment packaging, real provider/bank/model/host/DNS/runtime/staging/release operations remain separately blocked and scoped.
- No edits to DTO seven paths, workflow/R6 bindings, 120 IDs or existing queue objects/root values.
- Plan/spec/record/task/verification plus append-only queue are the only six planning checkpoint paths. Architecture documents are read-only historical context; this spec is the canonical source-task behavior amendment. No unlisted architecture change is assumed.
- All implementation and operational authorities false; accepted-case credit0. No application/fixture tests are executed by package generation.

## Literal todo

- [ ] Admit the actual DTO code successor S only after exact-source and actual merge-fixture CI/readback and independent code evidence; refresh source/tree/hash pins and preserve DTO/R6/workflow/120-ID history.
- [ ] Review this source-only six-document package, four implementation paths and literal todo; synchronize a verified real Issue and Project8 item with matching goal, refs and todos and retain live readback hashes without replacing prior history.
- [ ] Commit/push only the six-document planning checkpoint K descending from accepted S, seal actual K externally, pass standalone and extracted nested exact-K preflight using policy from K, and obtain independent exact-K review plus explicit scoped dispatch before implementation.
- [ ] Add failing root GET/HEAD302 and unknown404 tests, change only exact root redirect to /workshop/, retain explicit dashboard/slash/assets behavior, run focused/full Go checks and commit/push the validated routing milestone.
- [ ] Add supported/missing/equal-invalid/mismatched terms and merchant-field tests, add only literal workshop-v1 conjunct to purchaseConfiguration, and add served-disabled-default regression; keep purchase-config.json byte-identical and all checkout contracts unchanged.
- [ ] Run focused/full Node and Go checks and exact four-path/config invariants, independently review the exact final code SHA, commit/push validated coherent milestones and record honest exact-source and actual merge-fixture CI with no launch or accepted-case credit.

## Task G2: Workshop root entry (independently reviewable milestone)

**Files:** Modify `apps/api-go/main.go` exact `GET /{$}` handler (pinned line158); add test in `apps/api-go/workshop_test.go`. Read existing `apps/api-go/dashboard_test.go` to retain explicit dashboard and slash behavior. Canonical documentation: `docs/architecture/workshop-interface.md` states root redirects to Workshop while dashboard remains explicit.

**Interfaces:** Consumes `(*Server).Handler() http.Handler`; produces HTTP302 `Location: /workshop/` for exact GET/HEAD root. `/workshop` continues301 to `/workshop/`; `/dashboard` continues301 to `/dashboard/`; explicit dashboard200 and unknown paths404 remain.

- [ ] Add failing `TestWorkshopRootEntry` to workshop_test.go:

```go
func TestWorkshopRootEntry(t *testing.T) {
    server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
    for _, method := range []string{http.MethodGet, http.MethodHead} {
        response := httptest.NewRecorder()
        server.Handler().ServeHTTP(response, httptest.NewRequest(method, "/", nil))
        if response.Code != http.StatusFound || response.Header().Get("Location") != "/workshop/" {
            t.Fatalf("%s root redirect = %d %q", method, response.Code, response.Header().Get("Location"))
        }
    }
    missing := httptest.NewRecorder()
    server.Handler().ServeHTTP(missing, httptest.NewRequest(http.MethodGet, "/missing-root-route", nil))
    if missing.Code != http.StatusNotFound {
        t.Fatalf("unknown root route = %d, want404", missing.Code)
    }
}
```

- [ ] Run `go -C apps/api-go test -run '^TestWorkshopRootEntry$' -count=1`; confirm red because existing root Location is `/dashboard/`.
- [ ] Replace only the root handler target:

```go
mux.HandleFunc("GET /{$}", func(response http.ResponseWriter, request *http.Request) {
    http.Redirect(response, request, "/workshop/", http.StatusFound)
})
```

- [ ] Run `gofmt -w apps/api-go/workshop_test.go`, then `go -C apps/api-go test -run '^(TestWorkshopRootEntry|TestWorkshopRedirectPreservesSeparateEntryPoint|TestWorkshopAssetsAvailableWithoutCatalogCredentials|TestDashboard.*|TestSwagger.*|TestChatDashboardAssetsAreRemoved)$' -count=1`.
- [ ] Run full `go -C apps/api-go test ./...`, classify environment-gated/skipped integration tests accurately, and `git diff --check`.
- [ ] Independently review exact candidate; commit as `feat: use Workshop as the application root entry` and push only to coordinator-assigned branch. No DNS or deployment follows automatically.

## Task G1a: Current-contract purchase readiness (independently reviewable milestone)

**Files:** Modify `apps/api-go/workshop/commerce.mjs` purchaseConfiguration (pinned line95); modify `apps/api-go/workshop-client.test.mjs`; add served-disabled-config regression in `apps/api-go/workshop_test.go`. Read-only `apps/api-go/workshop/purchase-config.json`. Canonical documentation: `docs/architecture/workshop-commerce.md` and `docs/architecture/workshop-interface.md` describe exact current contract and unavailable state.

**Interfaces:** Keep exported `purchaseConfiguration(config, quote): boolean`. True requires enabled strictly true, config literal `workshop-v1` equal to quote.purchase_terms_version, nonblank string tax_notice and all four existing absolute HTTPS/no-userinfo URL validations. Retain `new URL(value)` with no base and try/catch. A true value establishes syntactic readiness only; existing `validQuote` plus scope/access/auth/agreement still guards checkout. No known checkout bypass is asserted: app.mjs already separately uses validQuote.

- [ ] Import `purchaseConfiguration` into existing commerce import; append focused tests using synthetic `.example` policy URLs. The fixture is not real merchant policy:

```javascript
const merchantFixture = () => ({
  enabled: true, terms_version: 'workshop-v1',
  terms_url: 'https://merchant.example/terms',
  privacy_url: 'https://merchant.example/privacy',
  refund_url: 'https://merchant.example/refunds',
  contact_url: 'https://merchant.example/contact',
  tax_notice: 'Synthetic fixture notice.',
});
const quoteTermsFixture = () => ({ purchase_terms_version: 'workshop-v1' });

test('purchase readiness requires the supported terms contract', () => {
  assert.equal(purchaseConfiguration(merchantFixture(), quoteTermsFixture()), true);
  for (const version of [undefined, null, '', 'workshop-v2']) {
    const config = { ...merchantFixture(), terms_version: version };
    const quote = { purchase_terms_version: version };
    assert.equal(purchaseConfiguration(config, quote), false);
  }
  assert.equal(purchaseConfiguration(merchantFixture(), { purchase_terms_version: 'workshop-v2' }), false);
  assert.equal(purchaseConfiguration(merchantFixture(), null), false);
  assert.equal(purchaseConfiguration(null, quoteTermsFixture()), false);
});

test('purchase readiness fails closed for unavailable merchant fields', () => {
  for (const enabled of [false, null, undefined, 'true', 1])
    assert.equal(purchaseConfiguration({ ...merchantFixture(), enabled }, quoteTermsFixture()), false);
  for (const tax_notice of [null, undefined, '', ' \n\t', 0])
    assert.equal(purchaseConfiguration({ ...merchantFixture(), tax_notice }, quoteTermsFixture()), false);
  for (const key of ['terms_url', 'privacy_url', 'refund_url', 'contact_url']) {
    for (const value of [null, undefined, '', '/terms', '//merchant.example/terms',
      'http://merchant.example/terms', 'javascript:alert(1)', 'data:text/plain,x',
      'https://user:pass@merchant.example/terms', 'https://merchant.example/has space',
      'https://merchant.example/line\nfeed', 'https://']) {
      assert.equal(purchaseConfiguration({ ...merchantFixture(), [key]: value }, quoteTermsFixture()), false, `${key}: ${String(value)}`);
    }
  }
});
```

- [ ] Run `node --test --test-name-pattern='purchase readiness' apps/api-go/workshop-client.test.mjs`; require red for matching undefined/null/empty/arbitrary versions in the first test. Do not characterize already-passing negative cases as new defects.
- [ ] Add exactly one conjunct after config enabled check:

```javascript
config.terms_version === 'workshop-v1' &&
```

Keep the following equality to `quote?.purchase_terms_version`, tax validation and URL parser unchanged. A new supported legal version needs a coordinated cross-layer plan.

- [ ] Add served-default regression using existing imports/helpers:

```go
func TestWorkshopPurchaseConfigDisabledByDefault(t *testing.T) {
    server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
    response := httptest.NewRecorder()
    server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/purchase-config.json", nil))
    if response.Code != http.StatusOK { t.Fatalf("purchase config status=%d", response.Code) }
    var config map[string]any
    if err := json.Unmarshal(response.Body.Bytes(), &config); err != nil { t.Fatal(err) }
    if config["enabled"] != false || config["terms_version"] != "workshop-v1" {
        t.Fatalf("default purchase config must remain disabled at workshop-v1")
    }
    for _, field := range []string{"terms_url", "privacy_url", "refund_url", "contact_url", "tax_notice"} {
        value, present := config[field]
        if !present || value != nil { t.Fatalf("default %s must be present and null", field) }
    }
}
```

- [ ] Run focused Node test, full `node --test apps/api-go/workshop-client.test.mjs`, and `go -C apps/api-go test -run '^TestWorkshop(PurchaseConfigDisabledByDefault|AssetsAvailableWithoutCatalogCredentials)$' -count=1`; run `gofmt -w apps/api-go/workshop_test.go` before Go verification.
- [ ] Run `go -C apps/api-go test ./...` once on the final combined candidate, plus `git diff --check`. If G1a and G2 land separately, each exact candidate needs applicable verification and successor gate binding.
- [ ] Independently review the candidate; commit as `fix: require supported purchase configuration terms` and push validated milestone on assigned branch.


## Canonical adoption and binding

Source admission is recorded in task.source_binding.source_admission_evidence: exact-S and actual merge-fixture Actions succeeded; independent code review and CI audit passed. PR256 remains draft and its separate Vercel deployment-rate-limit status failed. No application acceptance is inferred. Actual S descends from J. Refresh every inspected blob/mode/hash. Any of the four implementation-path changes is a source conflict, never automatically accepted. Changed app/dependency/gate/policy/docs require independent review; changed workflow/queue/DTO/R6 pins must be retained from S, never copied from J. Keep all actual S queue root values and ordered preexisting task objects verbatim as JSON values; append exactly the new stable ID once.

The coordinator supplied verified real Issue/item/UTC readback and hashes, synchronized literal goal/todo/refs/paths, and preserved tracking history. Standalone record and task.pre_implementation must be identical. Create K with exactly six documentation paths and no implementation changes; seal actual K/tree externally after commit rather than guessing a self-referential hash. K is the future implementation base; S and J are not. Run standalone and nested validators using record, policy and code from exact K and obtain independent exact-K review before explicit source-only dispatch. Preflight passing alone does not admit source, tracking, deployment or runtime.
