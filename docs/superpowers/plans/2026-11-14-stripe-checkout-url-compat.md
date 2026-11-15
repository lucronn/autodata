# Stripe hosted Checkout URL compatibility

Issue: https://github.com/lucronn/autodata/issues/420
Parent: https://github.com/lucronn/autodata/issues/398
Project: https://github.com/users/lucronn/projects/8
Canonical: `docs/architecture/stripe-checkout-url-compat.md`

## Goal and decision

Accept exactly the current Stripe hosted `/c/pay/` and `/g/pay/` URL path families on `https://checkout.stripe.com`, with a nonempty opaque path suffix. A genuine authenticated SDK16.1 TEST response in a fresh synthetic loopback database returned `/g/pay/`; its expected merchant/test/USD2000/order metadata all matched but Python's old validator rejected the URL and returned202 processing after provider allocation. All three attempted diagnostic sessions were expired unpaid, disposable resources removed, retained checkout data fingerprint unchanged and public purchase disabled. No Firebase/real licensed browser acceptance is claimed.

Official source: https://docs.stripe.com/api/checkout/sessions/object#checkout_session_object-url documents redirecting to the returned Session URL and currently shows `/c/pay/`. It does not explicitly document `/g/pay/`; direct authenticated TEST response evidence supports that additional exact form. Preserve opaque URL bytes and fragments. Never derive provider identity from a hosted path; use stored checkout_session_id or verified provider metadata. No arbitrary host, alternate path family, production enablement, credentials, DB/schema, DNS or deployment change.

## Implementation scope

Update Python commerce_service.py, Go commerce.go and browser workshop/commerce.mjs URL validators; synchronized OpenAPI yaml/json; narrowly necessary scripts/dev/workshop_browser_smoke.py and release_acceptance.py hosted validation/redirect logic. Corresponding existing Python/Go/Node and harness test files plus docs are allowed. Coordinate with #412 by leaving commerce_client.go untouched and #415 auth files untouched. Preserve exact TLS/authority/userinfo/no whitespace/control constraints; add `/g/pay/` parity including nonempty suffix and negative alternate prefixes, spoofed host, userinfo, port, malformed/blank suffix. Fixture-specific provider/session evidence remains constrained to its fixture contracts; preserve existing `/c/pay/` fixtures. Audit every tracked `/c/pay/` occurrence and document any intentionally fixture-only restrictions. Do not imply fixture harnesses are genuine real provider acceptance.

## Verification

Commit/push this synchronized planning checkpoint and run machine preflight at its exact SHA before implementation. Observe red-first Python, Go and browser URL regressions and relevant harness cases, then implement. Run full worker unit tests, full Go API tests, full Workshop Node tests, relevant complete harness unit suites, OpenAPI consistency checks and diff/preflight. Obtain independent exact-head review and required CI, leave PR unmerged for coordinator sequencing. No provider calls are necessary for unit verification. A subsequent separately authorized isolated TEST rehearsal may use the reviewed source with its own DB and real TEST listener; it cannot prove Firebase, production or licensed article readiness.

## Concrete todo

- [x] Synchronize plan, Issue420, Project8 and canonical documentation; pass pinned-base preflight
- [x] Observe red-first Python, Go, browser and acceptance-harness g/pay regressions while retaining strict negative cases
- [x] Implement the narrow two-form URL compatibility change, synchronized OpenAPI and real harness parsing without URL-derived session identity
- [ ] Run relevant full tests, independent exact-head review and required CI; retain separate isolated TEST/runtime and licensed browser acceptance evidence

## Protected-base integration checkpoint

Protected master: `92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a`, tree `0e4038a6bd506fd1349caa0bfa320813106ce5ad` (#412 then #417). Published PR421 source: `3aaa904304d613852761b0d787407190eeaa9779`, implementation `282954f0deea35a154c385104044b671a1c64971`. No reimplementation, provider sessions, runtime changes or deployment. Prepare this docs-only checkpoint directly on protected master and pass its exact-SHA preflight before merging it into the published PR branch; preserve both published histories. Resolve documentation-only overlap in favor of combined historical evidence and this current checkpoint; stop for coordinator if application conflicts alter reviewed behavior. Revalidate all relevant suites and required strict CI, then request independent exact-head review and hold merge.

Integration record: `docs/agents/records/2026-11-14-stripe-checkout-url-protected-base.json`

- [x] Synchronize Issue420, Project8, plan and canonical architecture at protected master92d81a1 and pass checkpoint preflight
- [x] Merge the synchronized checkpoint into PR421 preserving reviewed implementation282954f and exact master ancestry
- [ ] Run focused and full relevant Go, Node, worker, browser, release-evidence and contract checks on the integrated source
- [ ] Push the protected-base candidate, rerun strict required CI, hand off independent exact-head review and hold merge; no provider sessions or deployment
