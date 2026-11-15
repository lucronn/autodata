# Stripe Checkout URL compatibility verification

Issue: https://github.com/lucronn/autodata/issues/420
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-stripe-checkout-url-compat.md`
Canonical: `docs/architecture/stripe-checkout-url-compat.md`

Planning checkpoint `6be6f163bd44a99f969261947caeacb349fe9738` was committed/pushed before implementation; machine preflight returned synchronized/errors[] and Issue/Project state was read back. Application base was c115dcde11bee0ecc64052e8d51d15de7e572da9. This branch remains unmerged while coordinator integration proceeds.

## Observed issue and safe rehearsal boundary

An authenticated official Stripe SDK16.1 response for a newly created synthetic loopback order returned `https://checkout.stripe.com/g/pay/[redacted]`. Trusted HTTPS host, test livemode, one-time active USD2000 Price, merchant and server order metadata all matched. The old Python URL validator rejected the path; HTTP202/processing followed provider allocation. Three bounded diagnostic unpaid sessions were allocated across disposable attempts. All three were expired unpaid through Stripe, including the first recovered using a unique private creation-time window and loopback callback/order binding. No TEST payment was made. Each owned app container/database and official CLI listener was removed/stopped; retained checkout database article/revision/snapshot/artifact/order/entitlement fingerprints stayed unchanged and public purchase-config stayed disabled. This proves neither Firebase login nor licensed content/browser acceptance.

Official reference: https://docs.stripe.com/api/checkout/sessions/object#checkout_session_object-url currently illustrates `/c/pay/`. It describes the Session URL; it does not explicitly guarantee `/g/pay/`. The additional form comes from direct current authenticated TEST response evidence. Raw URLs, session/order IDs, keys, signatures and customer identities are excluded from repository evidence.

## Regression verification

Observed red-first Python authority, Go validator, browser client, API browser harness and raw receipt consumer tests. Python raised PAYMENT_DEPENDENCY_UNAVAILABLE; Go rejected g path and exposed pre-existing empty-path acceptance; Node returned null; harness rejected trusted opaque g URL; receipt consumer raised api21_v2_checkout_url. All focused cases now pass. Both c/g forms preserve opaque tokens/fragments and reject foreign/spoofed host, insecure scheme, userinfo, explicit port, empty suffix and whitespace/control characters.

Full Go API suite passed16.837s; subsequent full Commerce-focused checks passed after the HTTP checkout fixture was changed to an opaque g/pay URL. All262 Workshop Node tests passed. Complete browser harness unit suite passed139 tests and311 subtests in8.18s. All19 contract tests passed; OpenAPI YAML and JSON equality plus two-path positive/negative patterns passed. Full ingestion worker and release-evidence suites are in progress at this checkpoint; final results and exact-head independent review/CI will be appended before integration.

The host has a pre-existing /tmp/.git directory. Private-path guard tests correctly reject files under it; verification uses owned /var/tmp test roots instead, without modifying that unrelated directory. An initial default-temp worker attempt failed that guard and was superseded. An initial harness run using old in-memory fixture rows was stopped after the durable URL check required updated test snapshots; corrected browser suite passes.

## Authority and audit

Production validators now permit only c/pay and g/pay path families on the same trusted HTTPS authority. Go additionally rejects an empty provider suffix, aligning with Python/browser behavior. Hosted paths never supply session identity. API browser fixtures use their server-stored TEST session ID, exact stored URL, order/config/region and retry identity conservation; raw receipt checks conserve the same durable session across response loss/retry. The end-to-end synthetic receipt corpus passes with a g/pay opaque token deliberately different from its stored session ID. Fixture-only cs_test lowercase32hex identities remain a fixture contract and do not claim real Stripe ID structure.

Tracked c/pay occurrences were audited. Remaining literal `/c/pay/fixture` route/redirect checks are the deterministic DTO fixture and intentionally unchanged. Historical evidence and c/pay positive/negative fixtures remain. OpenAPI and every production/runtime validator plus API harness redirect check now recognize both path forms. No commerce_client.go, auth, runtime configuration, public DNS, deployment, licensed content or production grants were changed.
