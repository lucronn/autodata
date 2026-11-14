# Workshop Stripe test readiness: 2026-11-14

Issue: https://github.com/lucronn/autodata/issues/398
Parent: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-11-workshop-real-data-demo-entry.md`
Inspected source: `61f1939c04b41cf6082c3361f34424e0cd9c599e` (master).

This is a read-only readiness assessment and documentation checkpoint. The
existing server-verified test purchase implementation is already merged through
PR #400 (`74cc9e1e7f9cf460645c5976262fee07733066df`). No application files,
runtime configuration, orders, grants, payment settings or secrets changed in
this lane. Runtime recovery is tracked separately.

## Current public evidence

Independent curl GETs on `https://autodata.cars.tk` at
2026-11-14T23:14:25Z observed:

| Path | Status | Result |
| --- | --- | --- |
| `/readyz` | 200 | database, NATS and object storage ready |
| `/workshop/purchase-config.json` | 200 | `Cache-Control: no-store`; `enabled:false`, `terms_version:workshop-v1`, four URLs and tax notice null |
| `/workshop/demo-mode.json` | 404 | plain `404 page not found`; no ready test-demo signal |

This proves that new public purchases remain paused. It does not prove the
current live binary includes PR #400: the merged route returns a JSON enabled
boolean, whereas the observed public route is absent. No checkout, test card,
provider API call, signed settlement or licensed-data browser acceptance was
attempted. Earlier 502 observations preceded the coordinator's separate origin
recovery and are not the current readiness result. A Python urllib probe received
403; the table records the successful independent curl probes.

## Safe test origin and isolated staging path

There is no supported configuration that enables Stripe test checkout on
`https://cars.tk` or `https://autodata.cars.tk`. Both Go's
`configuredCommerceClient` and Python's `configured_commerce` reject those
production hostnames in `stripe_test` mode. Changing only `AUTODATA_ENV` cannot
remove the hostname fence. Keep the public preview purchase-disabled; do not
rename the production environment to bypass a check.

The checked-in standalone deployment path supports an explicitly configured
staging release. `infra/deploy/gce/runtime-check.py` requires host schema version
2, `environment:staging` and a different HTTPS `public_origin`; its renderer
sets `AUTODATA_COMMERCE_MODE=stripe_test` for API, ingestion HTTP and payment
reconciliation, and Firebase auth for API. This is available configuration and
code, not evidence of an already provisioned staging runtime. No staging host,
accepted manifest, audience restriction or supplier test-use authorization was
verified by this assessment.

Before any test enablement, the coordinator must establish all of these:

- An owner-approved isolated staging deployment, database/grants and storage,
  with a separate HTTPS origin, Firebase authorized domain and a restricted
  authenticated tester audience. A different hostname alone does not restrict
  who can sign in. Confirm supplier rights for the actual licensed test data.
- An exact reviewed release containing PR #400, valid deployment manifests and
  protected secret delivery. Both API and private commerce must independently
  use `stripe_test`, the same internal token and correct staging origin. Retain
  normal source rights, article/media authorization and exact vehicle/region
  checks.
- Private test-only `sk_test_` credentials, the expected merchant, an active
  one-time USD Price of exactly 2000 minor units with `livemode:false`, and the
  matching webhook signing secret. Python startup verifies merchant/Price,
  migration 040 and absence of conflicting merchant/mode orders before ready.
  Secrets belong only in private commerce/reconciler, never Go or the browser.
- Owner-approved purchase notices: enabled seven-field purchase configuration,
  fixed `workshop-v1`, four valid HTTPS policy/contact URLs and truthful tax
  notice, delivered through the validated renderer. Syntax checks do not
  supply missing owner policy decisions. Missing/malformed notices pause new
  checkout without creating an entitlement.
- Actual readiness equality: staging `/workshop/purchase-config.json` enabled,
  `/workshop/demo-mode.json` `{"enabled":true}` and no-store, Firebase sign-in,
  plus private authenticated mode `stripe_test` and purchase readiness. The
  no-real-charge banner must remain present and every checkout must assert
  `expected_mode:stripe_test`; Go and Python reject stale-tab mode drift.
- Authentic restricted browser acceptance: select an actual eligible vehicle,
  complete a Stripe test card, accept the signed webhook, verify server-owned
  exact-scope grant, library and licensed article/media reads, then wrong-owner
  and wrong-vehicle denial plus refund/revocation. Browser storage or a return
  URL cannot grant access. Report unavailable categories honestly.

## Current source checks

All checks below ran against the exact inspected source without provider calls
or test payments:

- `go test ./... -run 'Test(WorkshopRealDemo|WorkshopTestCheckout|WorkshopStaleTestTab|CommerceConfiguration|CommerceWebhook|CommercePublicTrustedOwner)' -count=1`
  from `apps/api-go`: passed. This covers fail-closed readiness, production
  origin refusal, stale-tab mode assertions, trusted owner and webhook boundary.
- Stripe adapter, commerce service and purchase configuration pytest modules:
  **23 passed, 63 subtests passed**, using the existing private virtualenv's
  official Stripe **16.1.0** package and `PYTHONPATH=workers/ingestion-python/src`.
- `python3 -m unittest test_purchase_config_delivery -q` from
  `infra/deploy/gce`: **10 tests, OK, 1 skipped**. The skipped local Compose
  phase requires its explicit integration flag; no Compose runtime credit is
  claimed. An initial repository-root unittest invocation failed to import
  sibling `test_host_runtime`; the corrected intended-directory run passed.

These unit/transport checks do not replace PostgreSQL acceptance, real signed
Stripe TEST settlement, Firebase/browser or supplier-rights evidence. #398
remains open. No additional implementation was necessary for this assessment.

## Concrete remaining todo

- [ ] Verify supplier test-use rights and restricted tester audience.
- [ ] Provision and independently verify the isolated staging prerequisites above.
- [ ] Run and retain real-data/test-settlement browser acceptance, including denial
      and revocation, on the exact staged release.
- [ ] Update #398 and Project #8 with that evidence before claiming completion.
