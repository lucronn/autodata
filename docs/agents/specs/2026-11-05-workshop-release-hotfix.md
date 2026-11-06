# Workshop release hotfix specification

Goal: Restore real Firebase login after startup cancellation and retain the existing card-only Stripe Checkout contract.

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-05-workshop-release-hotfix.md`
Record: `docs/agents/records/2026-11-05-workshop-release-hotfix.json`

## Confirmed defects and required behavior

At source `d123bbf3098d87bd75d234b409039ca25a8f0d3e`, the two-second startup context is passed to ADC and immediately canceled after initialization. The authorized_user token source retains that context, so first real OAuth refresh fails and login returns AUTHENTICATION_UNAVAILABLE. Controlled deployed-ADC lookup succeeds while initialization remains alive and fails after cancellation. ADC refresh must live for the verifier lifetime, keep context values/transports, and have an independent two-second HTTP bound. `VerifyLogin` and `CheckUser` retain their existing request-context deadlines, signature/issuer/audience/provider/revocation validation and denial behavior.

Stripe SDK 16.1.0 defaults to API `2026-10-28.endive`, which rejects existing `payment_method_types=['card']`. The unchanged USD 2000 card-only automatic-capture payload succeeds under explicitly configured `2025-08-27.basil`; an actual TEST session was created then expired unpaid with no PaymentIntent, and its signed expiration event reached the private listener. This is transport evidence only. Pin the composition root to that fixed API; retain SDK version, payload, idempotency, account/livemode and strict settlement checks.

## Exact implementation ownership and boundaries

Only `apps/api-go/auth_firebase.go`, `apps/api-go/auth_firebase_test.go`, `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`, and `workers/ingestion-python/tests/test_purchase_config.py` may change in implementation. No auth bypass, fake production identity, entitlement writes, policy/enabled-state changes, live credentials, public routing, schema, provider SDK upgrade, real charge, merge or production switch is authorized by this checkpoint. Do not log request bodies, Authorization headers, query strings, identity tokens or credential values. Coordinator owns subsequent private runtime acceptance in the isolated TEST stack/database; never mutate accounts in production DB candidate3017 for verification.

## Concrete todo

- [ ] Synchronize Issue #186, Project #8, combined plan, canonical spec and record; commit/push the documentation checkpoint and pass exact-SHA machine preflight before implementation.
- [ ] Add red regressions for ADC refresh after initialization cancellation/expiration and bounded refresh with preserved injected HTTP transport; implement the narrow Firebase lifetime fix while preserving request deadlines and all identity checks.
- [ ] Add a red composition regression requiring literal Stripe API 2025-08-27.basil and zero SDK retries; pin the configured StripeClient without changing the Checkout payload or financial validation.
- [ ] Run focused and full Go authentication/API and Python purchase-config/Stripe-adapter/commerce checks, review the exact four-path implementation diff, and commit/push each coherent validated hotfix.
- [ ] Independently review exact implementation SHA and CI, then let the coordinator restart the private TEST candidate and verify actual login plus no-charge card-only Checkout create/expire and signed webhook transport; keep real paid-settlement and release acceptance separately open.

## Acceptance limits

Fresh actual Google exchange and durable session, approved purchase configuration, actual paid settlement, permanent grant, duplicate handling and re-login/restart remain distinct acceptance requirements. Unit tests and unbound no-charge transport do not satisfy paid purchase or release acceptance.
