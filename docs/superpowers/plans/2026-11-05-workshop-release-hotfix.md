# Workshop release hotfix Implementation Plan

> **For agentic workers:** Execute inline task by task using superpowers:executing-plans after this committed synchronized checkpoint passes canonical preflight. The coordinator owns the shared worktree and dispatch; this planning worker changes no implementation files.

**Goal:** Restore real Firebase login after startup cancellation and retain the existing card-only Stripe Checkout contract.

**Architecture:** Decouple ADC credential refresh from the bounded startup context while independently bounding token HTTP requests and preserving injected transports. Freeze the tested card-only Stripe API version at the existing composition root. These are two independently testable milestones in one bounded release repair.

**Tech Stack:** Go, Firebase Admin SDK, OAuth2, Python unittest, Stripe SDK 16.1.0.

**Spec:** `docs/agents/specs/2026-11-05-workshop-release-hotfix.md`

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Record: `docs/agents/records/2026-11-05-workshop-release-hotfix.json`
Inspected source: `d123bbf3098d87bd75d234b409039ca25a8f0d3e`; coordinator pins this planning commit's full SHA after push.

## Global constraints

Implementation allowlist is exactly the four paths in the spec. Preserve all request deadlines/authentication checks, the USD 2000 card-only automatic-capture payload, SDK version, retries=0, idempotency and settlement validation. No other implementation or configuration changes. No secrets in code, tracking or evidence. Private runtime verification belongs to the coordinator after independent review; paid-settlement/release acceptance stays open.

## Concrete todo

- [ ] Synchronize Issue #186, Project #8, combined plan, canonical spec and record; commit/push the documentation checkpoint and pass exact-SHA machine preflight before implementation.
- [ ] Add red regressions for ADC refresh after initialization cancellation/expiration and bounded refresh with preserved injected HTTP transport; implement the narrow Firebase lifetime fix while preserving request deadlines and all identity checks.
- [ ] Add a red composition regression requiring literal Stripe API 2025-08-27.basil and zero SDK retries; pin the configured StripeClient without changing the Checkout payload or financial validation.
- [ ] Run focused and full Go authentication/API and Python purchase-config/Stripe-adapter/commerce checks, review the exact four-path implementation diff, and commit/push each coherent validated hotfix.
- [ ] Independently review exact implementation SHA and CI, then let the coordinator restart the private TEST candidate and verify actual login plus no-charge card-only Checkout create/expire and signed webhook transport; keep real paid-settlement and release acceptance separately open.

## Task 1: Firebase ADC lifetime and bounded refresh

Files: `apps/api-go/auth_firebase.go`, `apps/api-go/auth_firebase_test.go`.
Consumes `newFirebaseCustomerVerifier(ctx context.Context, c customerAuthConfig)`; produces the same `CustomerIdentityVerifier` contract.

- [ ] Extend existing `newFirebaseSDKFixture` with a controlled OAuth token route returning synthetic short-lived access tokens and recording refreshes. Write synthetic authorized_user ADC to `t.TempDir()`, select through `t.Setenv`, and route only oauth2.googleapis.com, www.googleapis.com, and identitytoolkit.googleapis.com through the fixture; reject every other host. Reuse signed fixture cert/JWT and count both live GetUser checks.
- [ ] Construct under a cancelable/expiring initialization context, cancel/expire it before first `VerifyLogin` using a fresh request context, and require successful OAuth refresh and identity. Force a second refresh with an expired synthetic token. Require explicitly canceled/expired request contexts to fail promptly and existing injected `oauth2.HTTPClient` transport/context values to survive. Run `cd apps/api-go && go test ./... -run 'Firebase|Customer' -count=1`; record expected red credential refresh failure before patch.
- [ ] Load ADC with a lifetime context derived from `context.WithoutCancel(ctx)`. Use an independent `http.Client` timeout of two seconds for credential-refresh HTTP, preserving the injected client's transport and relevant configuration by copying the client when present; pass that client through `oauth2.HTTPClient` on the detached context. Keep `firebase.NewApp`, `app.Auth`, VerifyLogin and CheckUser startup/request contexts unchanged. Document the credential token source as verifier-lifetime state.
- [ ] Re-run focused tests and full `cd apps/api-go && go test ./...`, then `go vet ./...`. Require cancellation, expiration, second refresh, HTTP timeout and original identity security regressions green. Run `git diff --check`, inspect only the two auth paths, commit `fix: preserve Firebase credential refresh after startup`, and promptly push.

## Task 2: Stripe card-only API compatibility

Files: `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`, `workers/ingestion-python/tests/test_purchase_config.py`.
Consumes existing `configured_commerce`; returns the same configured commerce/provider contract.

- [ ] In `test_valid_financial_startup_survives_malformed_notices_and_preserves_checks`, replace the discard-all StripeClient fixture with constructor keyword capture, then assert literal `stripe_version == '2025-08-27.basil'` and `max_network_retries == 0` for each successful configuration. Run `PYTHONPATH=workers/ingestion-python/src python -m unittest discover -s workers/ingestion-python/tests -p test_purchase_config.py`; record expected red missing-version assertion before patch.

```python
client_options = []
def stripe_client(*args, **kwargs):
    client_options.append(kwargs)
    return object()
# Keep RequestsClient fixture and other configured_commerce arguments unchanged.
# After each successful configured_commerce call:
self.assertEqual(client_options[-1]['stripe_version'], '2025-08-27.basil')
self.assertEqual(client_options[-1]['max_network_retries'], 0)
```

- [ ] Add `STRIPE_API_VERSION = '2025-08-27.basil'` beside fixed commerce constants with a card-only compatibility comment. Supply `stripe_version=STRIPE_API_VERSION` to the sole `StripeClient` constructor; preserve other options and all adapter logic.
- [ ] Re-run purchase configuration and analogous unittest discovery commands for `test_stripe_adapter.py` and `test_commerce_service.py`. Require existing exact card-only payload and settlement regressions green. Run `git diff --check`, inspect exact allowlist, commit `fix: pin Stripe API for card-only Workshop checkout`, and promptly push.

## Task 3: Exact candidate review and coordinator acceptance

- [ ] Independently review the complete four-path implementation at the exact pushed SHA; run required CI and retain failures plus final evidence. Verify the original checkpoint record against its full SHA before execution and record reviewed implementation SHA afterward.
- [ ] Coordinator rebuilds/restarts only the isolated private TEST stack with its isolated TEST database (never production DB candidate3017), verifies an authentic Google exchange creates a durable session, and repeats unbound TEST USD 2000/card-only Checkout create then immediate expire using the composed client and actual signed listener. Require livemode=false, unpaid, expired, payment_intent=null, verified durable event and no orders/entitlements from the probe. Do not attach a payment method.
- [ ] Keep actual authenticated purchase, approved policy configuration, paid settlement, durable grant, duplicate delivery, re-login/restart and release/cutover acceptance explicitly open until independently demonstrated.
