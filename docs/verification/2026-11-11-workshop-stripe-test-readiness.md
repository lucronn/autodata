# Workshop Stripe TEST readiness check — November 11, 2026

Issue [#186](https://github.com/lucronn/autodata/issues/186) and
[Project #8](https://github.com/users/lucronn/projects/8) track the $20
vehicle-configuration purchase release. This is a bounded read-only provider
and isolated-stack check, not an authenticated payment acceptance receipt.

## Observed at 18:14 UTC

- The existing isolated `autodata-checkout-test` project uses
  `AUTODATA_COMMERCE_MODE=stripe_test`. Its Stripe Price is active, one-time,
  USD 2000 minor units. The Price reports `tax_behavior=unspecified`, and its
  Product has no tax code. These observations do not determine tax obligations
  or prove the $20 customer total will be tax-compliant in any sales market.
- The TEST Stripe account reports `charges_enabled=true`, but its business
  profile has neither support email nor support address configured. This is
  not a finding about the live Stripe account or a substitute for confirming
  the seller's customer-support details.
- The isolated PostgreSQL database has migration
  `040_workshop_commerce`, an active USD 20 Workshop product row, and zero
  Workshop orders at the time of the read-only query. Its PostgreSQL, S3,
  NATS, and ingestion HTTP containers were healthy after the existing TEST
  PostgreSQL and S3 containers were restarted.
- The isolated TEST API remains stopped. Its existing Firebase ADC bind
  source `/tmp/autodata-checkout-test/firebase-adc.json` is an empty directory
  where the container expects a file; attempting to start the API failed at
  the bind mount before application startup. No credential was recreated or
  copied. The stack's former Compose override file is also absent. The API
  was bound to `127.0.0.1:3013`, not public traffic.

The TEST application containers mount source from the separate local checkout at
`36359d5e46d37387f210bc467971eef8eaa6857a`; this check does not certify
the current protected `master` source or a live deployment. No card was
charged, no order or entitlement was created, and no public purchase setting
was changed in this check. A prior direct no-charge Stripe TEST session probe
is recorded in Issue #186; it does not substitute for the customer path.

## Remaining release verification

1. Restore a legitimate TEST identity credential and the reviewed isolated
   stack definition without copying production credentials into local fixtures.
2. Run authenticated Stripe TEST checkout through the actual Workshop API and
   browser, then verify signed settlement, one permanent account-bound grant,
   duplicate delivery/retry behavior, refund revocation, and relogin recovery.
3. Confirm live merchant identity and support operations, choose sales markets,
   determine tax treatment/registrations, and configure a truthful $20-total
   checkout before any live-payment activation.
4. Finish and publish the Terms, Privacy, Refund, and Contact pages, including
   the missing privacy and seller facts, then verify their HTTPS URLs and the
   purchase configuration. Public checkout remains disabled until these and
   the repository release gates pass.
