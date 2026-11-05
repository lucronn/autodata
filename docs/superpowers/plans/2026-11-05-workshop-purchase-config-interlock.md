# Workshop Purchase Configuration and Checkout Interlock Implementation Plan

> **For agentic workers:** Use the approved coordinator dispatch and `superpowers:executing-plans` only after the canonical gate passes. This planning gate is synchronized and grants no implementation execution authority.

**Goal:** Serve frozen server-owned Workshop purchase/legal configuration from Python through the strict public Go projection, and reject every new or resumed checkout POST before financial side effects whenever purchase configuration is missing, malformed or disabled; preserve USD20 one-time vehicle ownership and recovery.

**Architecture:** Python CommerceService owns one validated immutable startup value. A strict Go proxy exposes the existing seven-key public contract without cached enabled state. Every Python checkout POST checks that value before transactions and financial side effects while settlement/access recovery remains available.

**Tech Stack:** Python 3.12+, Go 1.26, existing private HTTP token authentication, PostgreSQL lifecycle fixtures, Stripe 16.1.0 and unchanged browser assets.

**Spec:** `docs/agents/specs/2026-11-05-workshop-purchase-config-interlock.json`. Normative input: external approved proposal SHA256 `e0dac5daa8948aa10c282a4bb34acb54a10d57b40c56d0e54925f59a8dde5798`, independent approval SHA256 `a0f46f46482429418431fc1958b47c7c4b9646c0b1c5827dbb78dece3032a869`. The full approved runtime/test contract is retained below and in the spec.

## Synchronized planning boundary and references

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8, existing item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Tracking and standalone/nested records are **synchronized** after independent corrected-draft PASS29 and root literal Issue186/Project8 readback. Implementation base/checkpoint fields remain **null** in predecessor bytes, current implementation allowlist **[]**, every authority **false**, implementation_dispatch **false**. Root authorized only the eight-document planning checkpoint commit/push. Externally seal its actual SHA/tree, pass both exact-checkpoint preflights, obtain independent synchronized-checkpoint review and explicit coordinator dispatch before code. This synchronized plan alone grants no implementation authority.

Planning parent `b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb` tree `3f354a8da546141125d2c00d0adcb2431c72511e` was selected by the coordinator. Task58 planning dependency `c4a042304637a9103fb9feee998df2a94865f6b5`/tree `a4a0b9539adad9226a6d3b3514c1375fb3e0b64e` is retained without certifying active Task58 code. Task57 verified source `ea3797717599c27362eb78a94888762ca598239b`/tree `f5fb201b70bc6b9b836b8cc38c0b146899c657d1` and source/PR runs41969316863/41969338446 are historical source evidence only. Preserve application/product `6949eb1b1a5b93c9b2eb0579328e24c697f6f331`/tree `47ec54b1896c83a39b6637a6ce944d3620414f4e` and all previous58 queue objects/root bytes. No future checkpoint self-hash is embedded in predecessor bytes.

## Global constraints

- Exactly USD20 total, one-time purchase of one normalized vehicle configuration and region; no subscription, additional fee/tax, alternate price, quantity, scope or owner control.
- Firebase login and hosted Stripe Checkout remain the approved product direction. `https://cars.tk` uses **Vercel DNS** by current trusted user direction; documentation fact only.
- No migration041, schema/financial/quote/terms-version/SDK/frontend/Firebase bundle/production renderer/workflow/policy/supervisor/frozen collector changes.
- Only fifteen future implementation paths below; this draft edits only the eight planning paths. All other changes require scope amendment/review/tracking before edits.
- accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Source regression success cannot confer product/live/release acceptance.

## Concrete todo (literal tracking record)

- [ ] Independently review the approved Task59 proposal, its SHA256-bound approval, exact fifteen implementation paths/eight gate paths, coordinator-selected b6388596cf4419559fc6a8a5fbcd0b4fc33cc7cb planning parent and retained Task57/Task58 evidence; preserve all prior58 queue objects/root bytes and unchanged product/source pins, credit0 and release limits.
- [ ] Synchronize the literal goal, these six todos, exact paths, canonical references and explicit production-config-delivery blocker in Issue186/Project8 with fresh ownership and before/after preservation readbacks; only then set standalone and nested records synchronized, commit/push the planning-only checkpoint, externally seal its actual SHA/tree, pass both exact-checkpoint machine preflights errors=[], obtain independent checkpoint review and explicit coordinator dispatch.
- [ ] Implement the strict immutable seven-key Python configuration parser/factory, default-disabled service composition, token-authenticated exact-object private operation and pre-transaction checkout interlock; preserve strict merchant/mode/origin/migration checks and all financial recovery, with genuine red/green authority tests and validated synthetic enabled fixture inputs.
- [ ] Implement the two-second strict no-store public Go projection and exact GET/HEAD/405/query/conditional behavior; remove the competing embedded JSON, preserve UI/quote contracts and add strict malformed-input, actual-network HEAD and stale-config authenticated/CSRF authority regressions within the fifteen-path scope.
- [ ] Run focused red/green, frozen source/regression commands and the separately required three-case PG plus named Go authority bridge in the coordinator-owned lifecycle fixture; retain raw failures/no-skip/event/SQL/provider/provenance evidence separately from frozen collectors, inspect exact scope and promptly commit/push small validated milestones, then obtain independent exact-source review and fresh source-push/actual-PR CI required-job/live-Compose success.
- [ ] Synchronize verified source and remaining owner legal/tax/support, secret/merchant/Firebase, protected deployment-config delivery, restart/drain/rollback, authentic identity/payment/staging/restore/host/TLS and Vercel DNS blockers; retain accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[] and release_state=unverified with no merge/deployment/live-sales authority.

## Eight planning paths

- `docs/superpowers/plans/2026-11-05-workshop-purchase-config-interlock.md`
- `docs/agents/specs/2026-11-05-workshop-purchase-config-interlock.json`
- `docs/agents/records/2026-11-05-workshop-purchase-config-interlock.json`
- `docs/agents/tasks/2026-11-03-production-release/workshop-purchase-config-interlock.json`
- `docs/verification/2026-11-05-workshop-purchase-config-interlock.md`
- `docs/agents/tasks/2026-11-03-production-release/queue.json`
- `docs/architecture/workshop-commerce.md`
- `docs/verification/workshop-commerce-runbook.md`

## Frozen implementation interfaces and composition detail

These interfaces make the implementation handoff concrete; their bodies must enforce the complete contract below, rather than treating annotations as validation.

```python
# purchase_config.py: public creation is always validating and immutable.
# Strings are immutable; enabled constructor/factory checks exact schema and URL rules.
class PurchaseConfig:
    @classmethod
    def from_public(cls, value: object) -> "PurchaseConfig": ...  # raises ValueError on invalid input
    @classmethod
    def disabled(cls) -> "PurchaseConfig": ...
    @property
    def enabled(self) -> bool: ...
    def public(self) -> dict: ...  # fresh exact seven-key projection

def parse_purchase_config(raw: str | None) -> tuple[PurchaseConfig, bool]: ...
# bool means malformed nonempty input; omitted/canonical false => False.
# Parser returns disabled/True rather than logging or throwing for malformed raw input.

# commerce_service.py: preserve all existing positional and clock callers.
# __init__(connection_factory, config, provider, *, clock=None, purchase_config=None)
# None => PurchaseConfig.disabled(); reject non-PurchaseConfig injection.
# Store in private readonly authority; no setter or mutable alias.
# purchase_configuration(self) -> CommerceResult: CommerceResult(config.public())
# checkout keeps current shape/scope/key/terms validation, then:
# if not self._purchase_config.enabled:
#     raise CommerceError('COMMERCE_UNAVAILABLE', 503)
# This check precedes canonical request persistence, transaction entry and provider methods.
```

`configured_commerce` calls the parser once per enabled composition attempt and emits exactly one fixed redacted diagnostic, `Workshop purchase configuration invalid; new checkout disabled`, if malformed. No input, URL, notice or exception is attached. It still performs all existing mode/secret/origin/merchant/price/migration/database-ownership checks. `AUTODATA_COMMERCE_MODE=disabled` still returns None, no Stripe client. No server endpoint mutates configuration.

```go
// purchase_config.go, package main; only these seven json keys leave the boundary.
type workshopPurchaseConfig struct {
    Enabled bool `json:"enabled"`
    TermsVersion string `json:"terms_version"`
    TermsURL *string `json:"terms_url"`
    PrivacyURL *string `json:"privacy_url"`
    RefundURL *string `json:"refund_url"`
    ContactURL *string `json:"contact_url"`
    TaxNotice *string `json:"tax_notice"`
}
// disabledWorkshopPurchaseConfig() workshopPurchaseConfig
// decodeWorkshopPurchaseConfig([]byte) (workshopPurchaseConfig, error)
// (*Server).workshopPurchaseConfig(http.ResponseWriter, *http.Request)
```

The Go decoder must validate raw UTF-8, paired JSON surrogate escapes and duplicate occurrences before unmarshalling into this DTO; recursively scan strict JSON tokens rather than relying on map/struct overwrites. Consume one full object with precisely seven required fields, then EOF. A JSON grammar-aware precheck must distinguish escaped backslashes from Unicode escapes. Even a disabled private object validates the complete schema and canonical null branch. No arbitrary internal response is forwarded.

Existing `GET /workshop/` and method-unqualified `/workshop/purchase-config.json` overlap with method/path specificity in opposing directions. In `main.go`, convert the generic static mount to method-unqualified `/workshop/` with an explicit GET/HEAD guard retaining existing static method rejection behavior; register the method-unqualified exact config handler adjacent to it. Both routes then use path specificity without conflict. Also retain the existing `GET /workshop` redirect and register a method-unqualified exact `/workshop` fallback with a method guard: POST, OPTIONS and every other unsupported method return405 with `Allow: GET, HEAD` and no `Location`; GET and HEAD continue through the existing301 redirect to `/workshop/`. The exact slashless fallback prevents ServeMux from adding a slash and redirecting unsupported methods before the subtree guard executes. Config's own handler owns JSON/no-store/Allow for all methods. Actual-network tests must build the complete `Server.Handler()` behind `httptest.Server` with automatic redirects disabled: POST/OPTIONS `/workshop` =>405/Allow GET, HEAD/no Location; GET/HEAD `/workshop` =>301/Location `/workshop/`; GET/HEAD `/workshop/` and an ordinary existing asset =>unchanged serving, while POST/OPTIONS at those static paths =>405/Allow GET, HEAD/no Location. Preserve the exact config route's JSON/no-store/Allow/HEAD matrix. No frontend asset is modified except deleting obsolete JSON; all route and test changes fit the existing main.go and purchase_config_test.go allowlist.

## Canonical projection and equivalent URL vectors

Canonical disabled object is exactly:

```json
{
  "enabled": false,
  "terms_version": "workshop-v1",
  "terms_url": null,
  "privacy_url": null,
  "refund_url": null,
  "contact_url": null,
  "tax_notice": null
}
```

The following literal vectors are frozen in `spec.contract.url_vectors`. Python and Go tests each embed this identical inventory because adding a shared fixture path is outside the fifteen-path allowlist. Compare ID/URL/result inventories in review, and prove valid output preserves the original URL bytes. In addition, loop over every code point in these raw forbidden ranges at each URL boundary/interior: U+0000–U+0020, U+007F–U+00A0, U+1680, U+2000–U+200A, U+2028–U+2029, U+202F, U+205F, U+3000, U+FEFF. This is the union required by the approved contract, not a language whitespace predicate. Include exact 2048/2049 URL UTF-8 byte, 1024/1025 notice byte, 16384/16385 raw input byte boundaries and 1/63/64 label/2/63/64 final-label/253/254 hostname boundaries.

```json
[
  {
    "id": "plain_https",
    "url": "https://legal.example.test/terms",
    "valid": true
  },
  {
    "id": "explicit_443",
    "url": "https://legal.example.test:443/terms",
    "valid": true
  },
  {
    "id": "mixed_ascii",
    "url": "https://Legal.Example.TEST/terms",
    "valid": true
  },
  {
    "id": "punycode",
    "url": "https://xn--bcher-kva.example/terms",
    "valid": true
  },
  {
    "id": "encoded_space",
    "url": "https://legal.example.test/terms%20v1",
    "valid": true
  },
  {
    "id": "encoded_octets",
    "url": "https://legal.example.test/a%2Fb%FF",
    "valid": true
  },
  {
    "id": "wrong_scheme",
    "url": "http://legal.example.test/terms",
    "valid": false
  },
  {
    "id": "upper_scheme",
    "url": "HTTPS://legal.example.test/terms",
    "valid": false
  },
  {
    "id": "credentials",
    "url": "https://user:pass@legal.example.test/terms",
    "valid": false
  },
  {
    "id": "empty_query",
    "url": "https://legal.example.test/terms?",
    "valid": false
  },
  {
    "id": "query",
    "url": "https://legal.example.test/terms?v=1",
    "valid": false
  },
  {
    "id": "empty_fragment",
    "url": "https://legal.example.test/terms#",
    "valid": false
  },
  {
    "id": "fragment",
    "url": "https://legal.example.test/terms#v1",
    "valid": false
  },
  {
    "id": "wrong_port",
    "url": "https://legal.example.test:444/terms",
    "valid": false
  },
  {
    "id": "padded_port",
    "url": "https://legal.example.test:0443/terms",
    "valid": false
  },
  {
    "id": "empty_port",
    "url": "https://legal.example.test:/terms",
    "valid": false
  },
  {
    "id": "ipv4",
    "url": "https://127.0.0.1/terms",
    "valid": false
  },
  {
    "id": "ipv6",
    "url": "https://[::1]/terms",
    "valid": false
  },
  {
    "id": "localhost",
    "url": "https://localhost/terms",
    "valid": false
  },
  {
    "id": "trailing_dot",
    "url": "https://legal.example.test./terms",
    "valid": false
  },
  {
    "id": "empty_label",
    "url": "https://legal..test/terms",
    "valid": false
  },
  {
    "id": "leading_hyphen",
    "url": "https://-legal.example.test/terms",
    "valid": false
  },
  {
    "id": "trailing_hyphen",
    "url": "https://legal-.example.test/terms",
    "valid": false
  },
  {
    "id": "underscore",
    "url": "https://legal_site.example.test/terms",
    "valid": false
  },
  {
    "id": "numeric_tld",
    "url": "https://legal.example.123/terms",
    "valid": false
  },
  {
    "id": "unicode_host",
    "url": "https://b\u00fccher.example/terms",
    "valid": false
  },
  {
    "id": "host_escape",
    "url": "https://legal%2Eexample.test/terms",
    "valid": false
  },
  {
    "id": "incomplete_escape",
    "url": "https://legal.example.test/a%2",
    "valid": false
  },
  {
    "id": "bad_escape",
    "url": "https://legal.example.test/a%G0",
    "valid": false
  },
  {
    "id": "bare_percent",
    "url": "https://legal.example.test/a%",
    "valid": false
  },
  {
    "id": "space",
    "url": "https://legal.example.test/terms v1",
    "valid": false
  },
  {
    "id": "tab",
    "url": "https://legal.example.test/terms\tv1",
    "valid": false
  },
  {
    "id": "nbsp",
    "url": "https://legal.example.test/terms\u00a0v1",
    "valid": false
  },
  {
    "id": "line_separator",
    "url": "https://legal.example.test/terms\u2028v1",
    "valid": false
  },
  {
    "id": "feff",
    "url": "https://legal.example.test/terms\ufeffv1",
    "valid": false
  },
  {
    "id": "c0",
    "url": "https://legal.example.test/terms\u0001v1",
    "valid": false
  },
  {
    "id": "del",
    "url": "https://legal.example.test/terms\u007fv1",
    "valid": false
  },
  {
    "id": "c1",
    "url": "https://legal.example.test/terms\u009fv1",
    "valid": false
  }
]
```

## Task 1: Gate checkpoint, owned by coordinator

- [ ] Review exact eight-path draft, approved hashes and preservation report; resolve any review finding before synchronization.
- [ ] Fresh-read Issue186/Project8 ownership and state; preserve Issue body/prior comments/Project other fields and retain prior Source field verbatim in the new comment; publish literal external PROPOSED-TRACKING.md and verify readback. This draft agent performs no GitHub writes.
- [ ] Only after literal readback, set standalone/nested records and Task59 metadata synchronized, commit/push the planning-only eight-path checkpoint; retain actual full SHA/tree externally.
- [ ] Run both exact-checkpoint preflights described in verification, obtain independent checkpoint review and explicit fifteen-path dispatch. No implementation path may change until all pass. There is no Task59 implementation base before that actual checkpoint exists.

## Task 2: Frozen config, private read and checkout authority

**Files:** create purchase_config.py and test_purchase_config.py; modify commerce_service.py, http_service.py, test_commerce_service.py and test_http_service.py at the exact allowlisted paths below.

**Consumes:** raw optional startup string and existing immutable commerce merchant config; **produces:** validated frozen PurchaseConfig, fresh projection and pre-transaction 503 boundary.

- [ ] Write pure parser vectors, direct-construction/mutation tests, composition redaction test, and default-disabled checkout spy tests first. The spy connection factory and provider both raise AssertionError if touched; a syntactically valid scope/key/terms request must raise COMMERCE_UNAVAILABLE503 with zero calls under default/false/malformed input. Current code must fail these authority assertions before implementation. Invalid scope/key/terms retain existing prior errors.
- [ ] Record focused red run using the exact Python focused command in verification; retain failure reason and source SHA. Add enabled fixtures through the validating factory for every current checkout-positive test.
- [ ] Implement parser/frozen factory and canonical disabled output; explicit enabled factory rejects invalid schema, strict types, duplicate/unknown keys, malformed Unicode/URLs and all size/control cases. `public()` returns fresh dictionaries whose mutation cannot change future outputs or authority. No direct constructor can fabricate malformed enabled instances; `enabled` cannot be assigned after construction.
- [ ] Parse once at composition with fixed diagnostic and no startup abort solely for purchase input. Keep all existing merchant/startup checks mandatory. Inject keyword-only purchase_config; deny checkout before transaction/idempotency/order/provider action after existing request validation. Add private exact-{} read in dispatch before owner-field dispatch; retain existing token and request-limit checks.
- [ ] Run focused tests green, then complete HTTP/commerce/payment-reconciliation regression command. Compare raw signed webhook path unchanged. Commit/promptly push this coherent validated milestone only after authorized dispatch; no production config input is delivered.

## Task 3: Strict public proxy and static-source removal

**Files:** create purchase_config.go and purchase_config_test.go; modify commerce_client.go, commerce_client_test.go, main.go; delete workshop/purchase-config.json, all under apps/api-go.

**Consumes:** token-authenticated private operation; **produces:** anonymous strict JSON/no-store config response at existing URL.

- [ ] Add full-handler routing tests using actual-network httptest.Server with redirect following disabled: POST/OPTIONS slashless `/workshop` must405 with Allow GET, HEAD and no Location; GET/HEAD slashless must301 to `/workshop/`; `/workshop/` and an ordinary asset preserve GET/HEAD serving and unsupported-method405/Allow/no Location. Add the config GET/HEAD/error/conditional/query/405 matrix first. Freeze Python-equivalent URL vectors and strict raw JSON failures. Prove nil client returns canonical disabled and makes zero calls. Record red failures under focused Go command.
- [ ] Add `purchase-config` to existing client operation allowlist and two-second deadline switch; send exact `{}` with existing token/redirect prohibition/bounded reader. Test operation/path/body/token/deadline/redirect; no second env enable value or cache.
- [ ] Implement strict raw JSON validator and projection. Fail unknown/duplicate/trailing/nonfinite/malformed UTF-8/unpaired-surrogate/schema/null/URL/notice values with sanitized503; no leakage. Keep private-response bounds; reject oversized config instead of accepting truncated input.
- [ ] Compose exact method-unqualified config handler and compatible generic static guard as specified; retain `GET /workshop` and add the method-unqualified exact slashless fallback guard preserving unsupported-method405/Allow GET, HEAD/no Location and GET/HEAD301. Set JSON/no-store headers first, reject all methods besides GET/HEAD with405/Allow GET, HEAD; RawQuery/ForceQuery gives400. Use explicit HEAD-aware response writing for success and errors; never ETag/Last-Modified/304. Delete obsolete static JSON and prove no competing served copy. Run unchanged Workshop asset/client tests and all Go tests.
- [ ] Run focused Go green and complete Go/Node commands. Commit/promptly push the validated application milestone with no incidental DTO/quote/UI or financial changes.

## Task 4: Real authority and paused financial recovery regression

**Files:** new test_purchase_config_postgres.py and existing new purchase_config_test.go bridge; only fixture-construction/import edits in test_commerce_postgres.py and test_paid_catalog_api_integration.py.

**Consumes:** coordinator-owned immutable lifecycle fixture, actual private Python HTTP and PostgreSQL; **produces:** separate three-case required-mode evidence and named actual Go HTTP bridge.

- [ ] Inject a validated synthetic enabled PurchaseConfig at the two frozen fixture construction sites. Do not rename/reparameterize/remove existing cases or change collectors/assertions/schema/timing. Confirm ordinary discovery skips only the dedicated new required-mode cases/root when the dedicated flags are absent.
- [ ] Add exactly the three named PG roots and named Go authority root below. Define explicit missing-fixture flag failures. Use owned UUID lifecycle_test_ databases and synthetic lifecycle credentials; no live providers or host ports. Add tests before code and retain failure evidence.
- [ ] Implement enabled purchase/settlement then same-DB/provider reconstructed-disabled tests for direct private denial, unchanged SQL/order/idempotency/grant rows and zero provider-create delta; durable library/grant/status, late settlement, duplicate webhook, refund/dispute monotonic revocation, pending replay/preparation reconciliation and safe re-enable original-key replay must remain correct.
- [ ] In the stale-config root read enabled config through actual Go public HTTP, then replace only fixture-local Python authority on the same DB/provider and send valid auth+CSRF Go checkout new/creating/open-key POSTs. Verify503 and independently captured SQL/provider deltas. No production mutability endpoint or mocked checkout authority.
- [ ] Bound Go child150 seconds including compile, dedicated process group TERM/KILL<=5seconds/reap, actual `go test -json` root command and sanitized fixture env; preserve exact named-root run/pass/package-pass/no-skip events plus SQL/provider/log/JUnit/provenance artifacts. Required skip, timeout124/137, missing artifact, missing fixture or mismatch is unmet/failed.
- [ ] Coordinator runs the separate900-second required command and independent artifact inspection; frozen commerce/identity/paid suites remain separately required and unchanged. Ordinary source tests cannot substitute for this fixture run. Commit/promptly push validated regression milestone after green evidence.

## Task 5: Exact-source verification and handoff

- [ ] Run frozen source commands and exact allowlist/migration/SDK/policy/source pin checks from verification; report collection/execution/skip counts and real exits, preserve failed raw artifacts.
- [ ] Seal exact source SHA/tree and fifteen changed blobs; obtain independent exact-source review. Fresh source-push and actual PR-checkout CI must complete required jobs/live Compose with exact source/checkout SHA/tree evidence before claiming CI success. No future test or historical Task57/58 run is Task59 evidence.
- [ ] Root updates canonical verification/tracking with actual results and remaining blockers under a separately authorized documentation handoff; this draft does not permit implementation agent scope expansion. Leave credit0/IDs[]/release unverified. No merge/deploy/DNS/secrets/live-sales authority follows.

## Fixed architecture

Python `CommerceService` is the sole purchase-launch authority. Go exposes a public strict projection of its configuration through the existing `/workshop/purchase-config.json` URL. Go does not read a second copy of environment configuration and does not independently authorize purchases from a cached result. The final checkout decision occurs inside Python `CommerceService.checkout` on every invocation, including direct private authenticated requests. Existing browser code can retain its URL and JSON shape.

Separate the new purchase switch from `AUTODATA_COMMERCE_MODE`: commerce mode still controls whether the payment/grant subsystem exists and verifies its existing merchant/schema dependencies. To pause new purchase requests without losing access/webhooks/reconciliation, retain stripe_test/live mode and set purchase enabled false. Disabling the entire commerce mode is not a purchase-only pause.

Task59 is an application configuration/interlock lane. It accepts a documented nonsecret runtime environment input but does not modify production renderer/schema/workflows, deliver actual config, enable a deployed merchant or change frontend assets. Production's closed configuration renderer must receive this new input through a separately owned, synchronized deployment-config follow-up before anyone claims this feature is deliverable by the production pipeline. This is an explicit remaining blocker, not an implied operational workaround. Do not edit container env by hand or bypass release config hashes.

## Runtime configuration contract

Add one optional environment variable, `AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON`, consumed only by the private commerce composition. Maximum UTF-8 length16KiB. No path lookup, file read, network URL fetch, environment expansion or shell interpretation. Parse at process startup into a frozen value; no hot reload, mutable global defaults or process-local enable endpoint. Direct `CommerceService` construction also defaults to the frozen disabled value; tests must explicitly inject enabled fixture configuration. Enabled values must be produced by the same validating constructor/factory: no publicly constructible invalid enabled instance, aliased mutable dict or setter may bypass validation. Return a fresh seven-key public projection on every call.

The JSON object has exactly these seven keys, matching the shipped public shape:

- enabled: strict JSON boolean.
- terms_version: exactly workshop-v1; no new terms version or schema migration in this task.
- terms_url, privacy_url, refund_url, contact_url: enabled configuration requires all four strings, each1–2048 UTF-8 bytes.
- tax_notice: enabled configuration requires a nonblank single-line string of at most1024 UTF-8 bytes.

Reject duplicate or unknown keys, non-object roots, nonfinite values, invalid Unicode and incorrect types. URLs must use the literal https scheme, a nonempty ASCII DNS hostname, no username/password, no query/fragment delimiters (including empty ? or #), and no port other than absent or the literal443; paths are permitted. Reject every unescaped whitespace character anywhere in a URL, including interior ASCII spaces, tabs, nonbreaking spaces and Unicode line separators. Define whitespace as the union of Unicode White_Space and ECMAScript WhiteSpace/LineTerminator (including U+FEFF); additionally reject C0/C1 controls and DEL. Freeze identical Python/Go vectors rather than trusting URL-parser normalization or language-specific whitespace predicates.

DNS syntax is conservative and purely syntactic: total hostname length<=253 ASCII characters, at least two nonempty labels, each1–63 characters, each label starts/ends alphanumeric and otherwise contains only ASCII alphanumeric/hyphen, final label2–63 ASCII letters. Case-insensitive ASCII labels and valid xn-- labels are permitted; raw Unicode hostnames, IP literals (IPv4/IPv6), localhost/single-label names, trailing dots, empty labels and host percent escapes are rejected. Reject a percent sign in the path unless followed by exactly two hexadecimal digits; preserve valid percent-encoded path octets, including %20, without decoding or rewriting. Percent-encoded path bytes do not bypass the raw host/scheme/control constraints. Do not resolve or fetch URLs. This is syntactic validation, not approval of legal content or domain ownership. tax_notice is rendered as text, not HTML; reject control characters. Disabled input must use the same complete seven-key set, terms_version workshop-v1, and null notice/URL fields; canonical disabled output equals today's embedded placeholder. This deliberately avoids retaining a misleading partial legal configuration.

Validation precedence is fixed. Only an unset variable or the exactly empty string is an omitted-input shortcut, producing canonical disabled without a diagnostic. A nonempty value is first checked for UTF-8/size/JSON validity and the complete strict seven-key schema, and then for the enabled/disabled branch constraints. A complete valid enabled:false object with workshop-v1 and five null notice/URL fields is canonical disabled without a diagnostic. {"enabled":false}, a complete false object with any non-null notice/URL field, extra/missing/mistyped fields, and whitespace-only input are malformed. Every malformed nonempty input produces canonical disabled and exactly one fixed redacted diagnostic per composition attempt; never log raw input, URLs, notice text or parser exceptions. The parser reports validity to composition without performing logging itself, preventing duplicate diagnostics. **Do not abort otherwise valid commerce service startup because purchase notices are malformed**: that would also remove webhook/status/grant recovery. This is fail-closed for new checkout, while preserving the financial subsystem. The public route returns the disabled object; no secret/internal error fields appear. Existing merchant, mode, origin, migration and account-ownership startup checks remain strict and unchanged. New invalid purchase input never bypasses those checks.

A configuration change takes effect only after a coordinated process replacement/restart. There is no instantaneous fleet-wide kill switch. During rolling replacement an old enabled replica may still accept requests; production follow-up must enter maintenance/drain and replace all commerce replicas before advertising an effective pause. An already issued Stripe Checkout URL can still settle after a pause; webhook/reconciliation must honor that payment. Task59 neither expires existing sessions nor promises to prevent payment through previously issued URLs.

## HTTP/API behavior

1. New private token-authenticated `POST /internal/commerce/purchase-config`, body exactly `{}`. No customer account/session is required at this internal operation, but the existing X-Autodata-Internal-Token check is mandatory. No DB transaction, Stripe call, bank/model call or customer data read. Successful response200 is exactly the seven-field frozen enabled/disabled object. Existing private handler request limits/authentication apply.
2. Register one method-unqualified exact-path handler for `/workshop/purchase-config.json` adjacent to the generic embedded asset mount; ServeMux path specificity, not registration order, chooses it. The handler sets Content-Type application/json and Cache-Control:no-store before every branch, including405. Only GET/HEAD are accepted; other methods (including OPTIONS) return405 with `Allow: GET, HEAD` and a sanitized JSON error body using the existing error envelope. For GET/HEAD reject any query syntax, including a bare ?, using RawQuery or ForceQuery, with400 JSON INVALID_REQUEST. HEAD executes the same status/header/validation logic but explicitly writes no body on success or error, including conditional requests. Verify suppression with actual httptest.Server network requests; recorder-only calls are insufficient. Do not emit ETag or Last-Modified or produce304 from conditional headers.
3. With commerceClient=nil (explicit disabled mode), public route returns200 canonical disabled without contacting Python. With enabled commerce client, fetch the new private operation with the existing internal token and a2-second total timeout, existing bounded response reader and redirects prohibited. Validate every key/type/URL/notice using the same seven-key/disabled-precedence contract, and reject duplicate keys, unknown fields, trailing JSON values, invalid UTF-8 and escaped unpaired surrogates before Go decoding can replace text or discard duplicate occurrences. Go struct decoding/DisallowUnknownFields alone is insufficient. Serialize only a fresh strict public projection; never copy arbitrary private fields. Dependency outage, timeout, redirects or invalid private success =>503 COMMERCE_UNAVAILABLE, no-store; no fallback to embedded enabled data, cached config or browser state.
4. `CommerceService.checkout` validates request shape/scope/key/terms as today, then requires enabled purchase configuration before opening a transaction, recording idempotency mappings, allocating an order or invoking any provider method. Disabled/invalid/missing configuration =>503 COMMERCE_UNAVAILABLE using the existing sanitized error envelope. This blocks all checkout POSTs, including attempts to resume an existing creating/open order through POST. Owner-scoped GET order status remains the recovery path. No new error-code family is needed and current Go/client error handling remains compatible.
5. Do not put an authoritative enable check only in Go or in the browser. A previously fetched enabled response never authorizes a later checkout against a paused Python process. No request parameter/header can select a different configuration, price, merchant, owner or enable state.
6. Keep quote financial fields and current purchasable:true semantics unchanged in this bounded task: that field describes product/scope eligibility; the separate runtime purchase-config controls launch availability. Avoid changing `validQuote`, existing frozen quote fixtures or DTO inventories incidentally. Disabled config continues to show browsing plus purchase-unavailable copy through current UI behavior.
7. Remove the embedded purchase-config.json from the delivered asset set so no alternative static path can expose a competing configuration. The exact route supplies canonical disabled config when appropriate. Retain no second enabled fallback. Existing source UI fetch/validation contract stays intact.


## Exact proposed implementation allowlist

New files:

1. workers/ingestion-python/src/autodata_ingestion/purchase_config.py — frozen config value, bounded strict parser, canonical disabled/default factory and public projection.
2. workers/ingestion-python/tests/test_purchase_config.py — pure parser, composition/default and fail-closed tests.
3. workers/ingestion-python/tests/test_purchase_config_postgres.py — separately named opt-in PG authority/pause/recovery tests; no additions to the frozen fourteen-case evidence inventory.
4. apps/api-go/purchase_config.go — strict public DTO validation, canonical disabled result and exact HTTP handler.
5. apps/api-go/purchase_config_test.go — public route/proxy/strict validation/no-store tests.

Existing modified files:

6. workers/ingestion-python/src/autodata_ingestion/commerce_service.py — constructor accepts an explicit frozen purchase config defaulting disabled; runtime composition parses the env input; checkout enforces gate and service exposes public projection. Preserve constructor compatibility via a keyword-only optional parameter.
7. workers/ingestion-python/src/autodata_ingestion/http_service.py — dispatch exact private purchase-config operation; retain mandatory internal authentication.
8. workers/ingestion-python/tests/test_http_service.py — private operation exact-fields/auth/side-effect regressions.
9. workers/ingestion-python/tests/test_commerce_service.py — test direct default-disabled authority and explicit fixture enablement where checkout behavior is exercised.
10. workers/ingestion-python/tests/test_commerce_postgres.py — change only existing commerce fixture construction/import to inject a validated enabled synthetic config. Preserve all fourteen case IDs, assertions, export schema, collector inventories and timings.
11. workers/ingestion-python/tests/test_paid_catalog_api_integration.py — change only existing real-service fixture construction/import to inject enabled synthetic config. Preserve all paid-case semantics, IDs and producer evidence contracts.
12. apps/api-go/commerce_client.go — allow purchase-config operation and bound timeout at2seconds.
13. apps/api-go/commerce_client_test.go — operation path/token/payload/timeout/redirect tests.
14. apps/api-go/main.go — mount method-unqualified exact public config path adjacent to static handler, keeping existing service and paid dependency startup behavior; exact path specificity supplies GET/HEAD and local no-store405 handling.
15. apps/api-go/workshop/purchase-config.json — delete obsolete embedded placeholder, replacing its behavior through the exact handler.

No changes to DB SQL, payment_reconciliation.py, Stripe adapter, frontend JS/HTML, Firebase SDK artifacts, frozen collectors, supervisor/contract modules, workflow/policy/evaluator, production renderer or shared package contracts. If actual implementation requires another file, stop to amend/review/synchronize the allowlist before editing it. In particular, production-config delivery is not silently added to runtime-check.py.


## Preservation and migration compatibility

No migration041 or application table change. Preserve001–040 inventory, workshop-v1 terms constraint, USD2000 orders, canonical request hashes/provider keys, existing merchant/mode verification and database ownership. Existing rows do not need backfilling. Immutable constructor config is not added to historical order rows and does not rewrite historical terms.

Purchase-disabled service must continue current behavior for authenticated library/grant checks, paid catalog/media, order/status, signed webhook ingestion/replay, full refund/lost-dispute revocation and preparation/reconciliation. Previously paid ownership remains durable and another purchase is unnecessary. A valid pending signed payment that settles after pause may still issue its exact existing grant. Blocking checkout must not call create_order_checkout, allocate replacement sessions or alter stored expiry/status. Existing reconciliation may perform already authorized settlement/expiry recovery; preserve those semantics rather than relabeling a pause as revocation. Existing checkout UI remains disabled by the returned config while My vehicles and order return flows remain available.

Older application binaries do not enforce this new interlock. After deployment, do not roll back to an old enabled-commerce binary and assume purchase pause remains effective; a compatible operational rollback must remain in maintenance or otherwise enforce the pause through an approved plan. No migration means data compatibility, not equivalent old-binary behavior.

## Required tests and evidence

Pure Python: unset/exact-empty defaults; valid complete false schema; malformed false-shortcut/non-null/unknown-field and whitespace-only inputs with exactly one redacted composition diagnostic; valid enabled synthetic object; duplicates/unknown/missing fields, non-object root, strict bool, null notice, bad terms, UTF-8/control/length limits and unsafe URL cases. Run shared-equivalent Python/Go URL vectors for interior ASCII/NBSP/line-separator/U+FEFF whitespace, invalid host labels/IP/localhost/trailing dots, malformed percent escapes and accepted percent-encoded paths. Reject direct construction of a malformed enabled value and prove mutation of an input/projection dict cannot change the frozen authority. Capture logs and prove config content is not echoed. Prove default direct construction is disabled. Spy provider/transaction factories must remain untouched on denied checkout, including existing idempotency-key requests; valid enabled configuration reaches unchanged request/financial logic.

Private HTTP: missing configured token and absent/wrong request token401 before operation; exact{} accepted; extra/null/array input400; valid config read calls no DB/provider; no merchant keys/tokens/internal state leak. Existing raw signed webhook handling remains byte-identical.

Go HTTP: anonymous enabled and disabled200; nil client200 disabled and zero private calls; strict malformed/unknown/duplicate/trailing-value/invalid-UTF8/unpaired-surrogate/oversize config rejection503; private auth/operation/payload, redirects, timeout, errors and no data leakage; success/error/HEAD/405 Cache-Control:no-store and JSON MIME; method405 Allow GET, HEAD; no ETag/Last-Modified/304; query rejection including bare ?; actual httptest.Server HEAD and conditional HEAD requests with zero response body on success, dependency503 and query400; exact dynamic routing and absence of a deleted static fallback. Run existing Workshop asset test unchanged except naturally receiving dynamic disabled config.

Owned PG integration: start enabled service, create/settle an exact USD2000 fixture order and assert one durable grant. Reconstruct service on the same database/provider with disabled config; direct private checkout POST must503, with unchanged before/after order/idempotency/grant rows and zero provider-create delta. Library, grant check and order status continue. A pre-pause open session that settles after pause still verifies/grants exactly once; duplicate signed webhook no duplicate grant. Apply full refund/lost-dispute fixture after pause and retain existing monotonic revocation. Pending replay and preparation reconciliation still complete using existing routines. Re-enable and replay the original client key without allocating/charging a second order. Keep test/live isolation, entitlement-before-hydration and USD2000 checks intact.

Stale frontend proof: successfully read enabled public config through the actual public Go route, then replace/reconstruct the authoritative fixture service as disabled on the same fixture DB/provider. Send fully valid authenticated/CSRF checkout requests through actual Go→Python HTTP for both a new key and previously stored creating/open keys. Each must503; capture before/after SQL rows and provider-create deltas outside the HTTP bridge and prove no changes. The dedicated Go test bridge lives only in purchase_config_test.go; fixture service swapping is implemented only by the new Python test module's local fixture control, never a production mutable-config endpoint. This is an authority integration test, not an expansion of API21/DTO120 case credit. Do not change frozen producer selectors/inventories to absorb it.

### Concrete separate required-mode runner

Inside the coordinator-owned immutable lifecycle fixture, from repository root, the coordinator creates the dedicated artifact directory `/artifacts/task59-purchase-config` outside source, preflights the exact source SHA/tree and pinned Python/Go binaries, and executes this separate command (not the frozen fourteen-case collector):

```sh
env AUTODATA_LIFECYCLE_TEST=1 AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR=/artifacts/task59-purchase-config timeout --signal=TERM --kill-after=15s 900s python -m pytest -q -p no:cacheprovider --junitxml=/artifacts/task59-purchase-config/tests.xml workers/ingestion-python/tests/test_purchase_config_postgres.py > /artifacts/task59-purchase-config/pytest.stdout.log 2> /artifacts/task59-purchase-config/pytest.stderr.log
```

The fixture uses only the existing private `postgres` service and synthetic lifecycle_fixture/lifecycle_test credentials from lifecycle_support.py, no host ports/live credentials/providers, and creates fresh UUID databases with the existing lifecycle_test_ prefix. The new module's owned cases are exactly `test_pause_preserves_paid_access_and_no_new_charge`, `test_late_settlement_refund_and_reconciliation_while_paused`, and `test_stale_public_config_rejected_through_go_authority_bridge`; all three must execute/pass, with zero skips. Without the dedicated required flag, this PG module is explicitly skipped during ordinary source discovery. With required flag1, missing lifecycle flag, PG/migrations, Go binary, fixture server or artifact directory causes a test failure/error, never a skip. Its own guard/fixture namespace is separate from AUTODATA_REQUIRE_COMMERCE_INTEGRATION and frozen collectors. Do not set the new flag in existing collector commands.

The third case starts its real Python private HTTP authority on an owned loopback ephemeral port; prepares synthetic customer/session fixtures; and launches exactly `go test -json -count=1 -timeout=120s -run ^TestWorkshopPurchaseConfigAuthorityIntegration$ .` from apps/api-go. Pass only a sanitized env containing pinned PATH/Go cache settings, `AUTODATA_PURCHASE_CONFIG_GO_BRIDGE=1`, `AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION=1`, `AUTODATA_PURCHASE_CONFIG_FIXTURE_URL`, `AUTODATA_PURCHASE_CONFIG_FIXTURE_TOKEN` and the dedicated artifact directory. URL/token are synthetic fixture values, never live/internal production credentials. The Go test must validate required fixture env and run its actual auth+CSRF public requests; missing required inputs fails. With neither dedicated flag the Go root skips, keeping ordinary/frozen Go discovery separate. Mismatched flags fail whenever the required flag is set.

Python bounds the Go subprocess at150seconds including compilation/test exit, creates a process group, records timeout/nonzero as failure, sends TERM then KILL after at most5seconds if needed, waits/reaps it, and captures raw `go-events.jsonl` and `go-stderr.log` in the dedicated artifact directory. Require exactly one run/pass and no skip/fail event for the named Go root plus package pass and exit0. Capture `authority-before.json`, `authority-after.json` and `provider-trace.json` with synthetic rows/counters and no raw sessions/tokens. Require before/after evidence to corroborate the Go observations; assertions alone are insufficient. Retain stdout/stderr/JUnit/raw files on failure, verify new-module case IDs/no-skips and Go events independently, and retain coordinator input/source before/after provenance. Outer exit124/137 or a missing artifact is a failed/incomplete run, never success. Existing fixture teardown removes only owned servers/databases/processes. These separate artifacts carry Task59 regression evidence only; do not hash or add them into frozen fourteen-case collector inventories.

Run focused red-before/green-after tests, Go ./... and existing Node suite, Python commerce/HTTP/payment reconciliation suites and existing isolated fourteen-commerce/five-identity/paid regressions when available under the coordinator-owned lifecycle fixture. Any required integration skip is an unmet check, not a pass. Retain failed artifacts. Run git diff --check and exact allowlist/migration/SDK/policy diff checks. Independently review exact source commit, push small validated milestones promptly, and collect fresh source-push plus actual PR-checkout CI with SHA/tree/required-job/live-Compose evidence. Tests added here are Task59 source regression evidence; existing product acceptance remains0 until separately accepted.


## Remaining owner and release decisions

- Independent corrected-draft PASS29 and literal Issue186 comment6650475758/Project8 synchronization completed with preserved readbacks; planning-only checkpoint commit/push, external actual SHA/tree seal, dual exact-checkpoint errors=[] preflights, independent checkpoint review and explicit coordinator fifteen-path dispatch remain required before code.
- Actual planning-checkpoint SHA/tree seal, standalone/nested exact-base preflights, independent checkpoint review and explicit fifteen-path dispatch remain required before code.
- Owner-approved actual terms/privacy/refund/contact content and URLs, support identity and truthful single-line tax notice are absent; synthetic tests cannot approve legal content or domain ownership.
- Tax obligations and inclusion within exactly USD20 total require owner/adviser decision; adding tax on top requires separately reviewed financial-contract change.
- Production closed schema/renderer/config-hash delivery does not yet pass AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON; a separately owned synchronized deployment-config follow-up is mandatory. No hand-edited container environment or hash bypass.
- Actual Firebase project/Google provider/authorized domains, Stripe merchant/price/account/webhook and secret delivery remain owner/protected-release inputs; no real credentials belong in this gate.
- Purchase pause takes effect after coordinated commerce process replacement; fleet drain/replacement and compatible rollback must be separately proved. Old enabled binaries/replicas and issued Stripe URLs retain stated limitations.
- Authentic identity/payment/staging/restore/host/TLS, real API21/DTO120/same-candidate final180, runtime ownership/watchdog/observer/raw-capture/trace16MiB-versus8MiB proof and protected merge/deployment/release remain unverified.
- cars.tk DNS provider is Vercel by trusted coordinator/user direction; no DNS or cloud operation is authorized.

## Coordinator tracking readback — planning synchronized

Issue comment https://github.com/lucronn/autodata/issues/186#issuecomment-6650475758, created 2026-11-05T05:24:57Z, and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` retain the literal goal, six todos, eight gate paths, fifteen future implementation paths and canonical references. Fresh before snapshot `/home/corp/autodata-evidence/task59-before-tracking.json` SHA256 `4dc68f829e038886b114c2d79daabd27c505b6c2e1dbc40c7646ed0a71a6448d`; after snapshot `/home/corp/autodata-evidence/task59-after-tracking.json` SHA256 `f32db5549893ecba8e2f36d2fd920d86b6b391cc653066e7df4c1cababa56f64`. The Issue body and all262 prior comments are unchanged; other Project fields are unchanged and the previous Project Source text is preserved verbatim in the comment. Source before SHA256 `27c5c9fc62dfa3274e966cc04d63c0e10e071134248962cbd744c7c4f2355f7f`, after SHA256 `0b6a39a6cc2c1872c38014c65e4d2131c45b98026745d0e53be8d330fb2d0d2a`. Root completed synchronization; this planning agent verified the saved literal/preservation readbacks without additional GitHub writes.

Independent corrected-draft review `/home/corp/autodata-evidence/task59-gate-draft-review/REPORT.md` SHA256 `ce210040dbe65be7c2add415dfa8b8f8a01d032f6736aec485bccc942d20e751` passed29 checks after the slashless method-guard correction. Reviewed draft bytes are retained externally under `/home/corp/autodata-evidence/task59-purchase-config-checkpoint/reviewed-draft/`. Synchronization changes only tracking/envelope/canonical status bytes, preserving approved application contract, URL vectors, routing matrix, financial/preservation limits and fifteen-path future scope.

Standalone/nested records and Task59 spec/task/queue planning/tracking status are synchronized at 2026-11-05T05:25:42Z; execution remains blocked, current implementation allowlist=[], all authorities=false, implementation_dispatch:false, accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified. Root authorized only the eight-document planning checkpoint commit/push. Externally seal the actual checkpoint SHA/tree and require both exact-checkpoint errors=[] preflights, independent synchronized-checkpoint review and explicit coordinator fifteen-path dispatch before implementation. Future checkpoint/source hashes remain external to these predecessor bytes. No implementation, Issue/Project/PR, live-config, merchant, secret, merge/deploy/DNS action is authorized here.
