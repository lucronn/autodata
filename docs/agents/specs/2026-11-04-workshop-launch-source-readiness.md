# Workshop source readiness contract

Status: synchronized planning only; source S admitted and tracking read back at 2026-11-04T23:12:08Z. Checkpoint K is sealed externally after commit; independent exact-K review and explicit implementation dispatch remain pending. Goal: Make Workshop the application root entry and enforce current purchase configuration readiness without enabling sales.

The source change has two coherent milestones. Exact GET/HEAD / returns302 Location /workshop/; unknown paths remain404, /workshop and /dashboard retain301 slash redirects, explicit dashboard and Workshop assets remain available without catalog credentials. No claim is made about live cars.tk routing.

purchaseConfiguration(config, quote) returns true only for strict enabled:true, literal config.terms_version workshop-v1 equal to quote.purchase_terms_version, nonblank string tax_notice and all four existing absolute HTTPS URLs without whitespace or userinfo. Retain URL parsing, quote equality, checkout/access/auth/agreement checks. This corrects equal missing/unsupported terms at the helper boundary; it is not demonstrated checkout bypass remediation.

Read-only invariant: apps/api-go/workshop/purchase-config.json retains exact source bytes, disabled workshop-v1 and all five present-null fields. The only implementation paths are:

- `apps/api-go/main.go`
- `apps/api-go/workshop/commerce.mjs`
- `apps/api-go/workshop-client.test.mjs`
- `apps/api-go/workshop_test.go`

The full executable test sketches and two milestone commit/push steps are in `docs/superpowers/plans/2026-11-04-workshop-launch-source-readiness.md`. No new dependencies, API/schema/worker/SDK/DTO contract changes, environment packaging or merchant-policy invention are permitted. G1a does not complete G1/T1–T3. G1b requires approved published terms/privacy/refund/contact URLs, accurate tax notice/final USD20 treatment, approved workshop-v1 policy bytes and immutable environment/config/image design with its own gate.

Canonical source-task scope is these six proposed checkpoint documents. Read-only architecture context remains descriptive of previously delivered source until new implementation is verified; this proposed spec does not assert new behavior exists. All operational authorities false and accepted-case credit0. Root source selection follows existing Workshop-at-cars.tk intent; deployment and live cutover need separate authorization.
