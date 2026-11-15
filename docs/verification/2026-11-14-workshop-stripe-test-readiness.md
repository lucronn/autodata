# Workshop Stripe test readiness: 2026-11-14

> **Archived report (2026-11-14), preserved from PR #408 at `6037c9af34cf41e92cffd67ceaf26f65d5991a44`.** Runtime, source, health and acceptance statements describe that dated checkpoint only, not present service state. Operational steps and old planning records are historical/non-replayable; this import creates no execution authority. See the [consolidated evidence and corrections](2026-11-15-historical-evidence-consolidation.md).

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

## Historical public evidence (2026-11-14T23:14:25Z)

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

## Supersession and interpretation corrections (2026-11-15 consolidation)

The reported `/workshop/demo-mode.json`404 belongs only to the dated public probe,
not current public behavior. Later source-only release/canary receipts are
preserved in `2026-11-14-workshop-preview-read-only-rollout.md` and
`2026-11-15-workshop-preview-canary-5981b97.md`; they supersede this checkpoint's
absence-of-route observation without proving current TEST purchase acceptance.
The later staging UID allowlist and Checkout URL compatibility changes are
recorded in `2026-11-14-workshop-staging-tester-allowlist.md` and
`2026-11-14-stripe-checkout-url-compat.md`. This report does not establish present
container/ADC/credential validity or the absence of later isolated local stages.
No fresh infrastructure, identity, account or payment inspection is claimed.

The saved AutoData tunnel YAML was configuration evidence only. It was not proof
of the active token-managed tunnel's routing or account/zone management rights.
Do not infer a usable external staging origin from that file, DNS resolution,
or the credential names listed below. A stable segregated external TEST origin,
approved actual Firebase tester/ADC and truthful owner purchase notices remain
separate admission requirements. Historical supplier metadata gaps do not
independently establish contractual permission or prohibition.

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

## Historical source checks (61f1939)

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

## Remaining todo recorded at that checkpoint

- [ ] Verify supplier test-use rights and restricted tester audience.
- [ ] Provision and independently verify the isolated staging prerequisites above.
- [ ] Run and retain real-data/test-settlement browser acceptance, including denial
      and revocation, on the exact staged release.
- [ ] Update #398 and Project #8 with that evidence before claiming completion.

## Read-only staging infrastructure inventory

The follow-up inventory found no existing segregated Workshop staging runtime:

- `https://staging.cars.tk/` completed HTTPS and returned Vercel **404
  DEPLOYMENT_NOT_FOUND** at 2026-11-14T23:16:26Z. Public A answers were
  `64.29.17.1` and `216.198.79.1`, with no CNAME answer. This identifies edge
  routing, not an application, reserved VM address or proof of alias ownership.
- Authenticated read-only inventory of the historical candidate GCP project
  `vehapi-torque` returned no Compute instances, static addresses or Cloud DNS
  zones. Its three existing Cloud Run services were unrelated to Workshop;
  none was a staging application. The ambient gcloud default project differed;
  every inventory command selected the candidate explicitly, without changing
  defaults. The candidate remains an owner decision, not an approved target.
- Secret Manager name inventory included `stripe-secret-key` and
  `stripe-webhook-secret`. Subsequent describe/version-list calls failed with
  **BILLING_DISABLED**. No secret payload, active version, merchant, key mode or
  webhook binding was established. A billing project readback separately
  failed **SERVICE_DISABLED** for the Cloud Billing API. No API, billing account
  or secret setting was changed; listed names are not usable-credential proof.
- The saved local AutoData YAML describes both public hostnames targeting
  the same localhost API port, without a separate staging listener/audience.
  This is inactive/saved configuration, not verified active routing. The active
  token-managed cloudflared process cannot be identified with that YAML from
  these observations. No token was extracted and no route was repointed.
  Actual edge/tunnel ownership and external-stage routing remain unverified by
  this historical inventory.
- Existing Vercel CLI credentials were rejected. Subsequent read-only CLI
  commands opened device-authentication waits; those were stopped without
  completing login. No authenticated alias/zone ownership readback or Vercel
  change occurred. Reauthentication or another authorized account route is
  needed before any eventual staging alias/DNS work.
- GitHub environment inventory exposed only `Preview` and `Production`, both
  without protection rules. Repository secret/variable inventories were empty.
  The separately protected staging publisher/operator identities and explicit
  accepted manifests described in #312 were not established here.

The useful next steps before supplier/tester answers are to review the exact
staging topology and cost/configuration choices, restore authenticated DNS
account visibility, resolve the candidate cloud billing/API prerequisite,
prepare the restricted-access mechanism and obtain a reviewed deployment gate.
None requires importing licensed content or granting access. Provisioning,
changing DNS/tunnel routes, enabling APIs/billing, supplying credentials and
starting a staged service each remain concrete coordinator decisions; this
inventory did not perform them. A new local fixture runtime can test code but
cannot establish an existing stable HTTPS origin or real-data acceptance.

Manual full Autonomous Verification run
[43652359524](https://github.com/lucronn/autodata/actions/runs/43652359524)
passed policy, DTO browser inventory and R3 preparation jobs at documentation
checkpoint `3694ec9ef240de31eab4db6b51776b25a61a2fd7`. This was a source/fixture
CI result, not Stripe settlement or staging acceptance. The PR-associated
required check and independent exact-head review are rechecked after each
subsequent documentation commit.

## Existing private Stripe acceptance and Docker configuration

A follow-up inventory after Docker recovery found merchant configuration key
names in both `autodata-ingestion-grant-ready-e4af862` and
`autodata-checkout-test-ingestion-http-1`: commerce mode, environment, public
origin, Stripe account, Price, secret key, webhook secret and purchase notices.
Only key names were emitted from current Docker inspection; current secret
values, validity, live/test prefix, account and Price were not disclosed or
revalidated. Empty local environment-file searches and inaccessible cloud
Secret Manager do **not** establish that credentials are missing: Docker has
an existing private configuration source that must be assessed through the
approved operator path before requesting replacements.

Retained sanitized private evidence already exists at
`/home/corp/autodata-evidence/stripe-test-2026-11-06/`. Its preflight records
source `36359d5e46d37387f210bc467971eef8eaa6857a`, official Stripe16.1.0,
API2025-08-27.basil, test key, matching merchant and active USD2000 test Price.
The named checkout/webhook/grant/refund-restart/cleanup receipts report:

- Actual test Checkout creation and idempotent order/session, card only,
  quantity one, fixed USD2000, followed by genuine CLI settlement delivery.
- Owner paid grant/library and wrong-owner, adjacent-configuration,
  other-region and bad-signature denials.
- Full test refund, genuine refund delivery and monotone revocation surviving
  service reconstruction and database restart, without resurrection or duplicate
  grant. The separate settlement replay is explicitly described as an
  authentic SDK-retrieved event signed locally, not another genuine delivery.
- Test payment fully refunded, no open Checkout, temporary owned acceptance
  resources/listener removed, no Stripe endpoint created, and public purchase
  configuration untouched. The historical external config probe was403;
  it did not directly prove public readiness.

These are historical retained summaries, not a fresh rerun against current
master or proof of available supplier rights. The historical configuration
booleans recorded test keys present and live keys absent in two private
containers. Preserve this commerce milestone while keeping the outstanding
Firebase/tester/HTTPS staging/licensed article-media browser acceptance under
#398 separate. No current key was used, checkout allocated, webhook delivered,
refund issued or grant changed by this readiness lane.
