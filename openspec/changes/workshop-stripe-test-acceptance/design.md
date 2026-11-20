## Context

Go serves the Workshop under `/workshop/` and forwards commerce calls to
the existing private Python service. That service creates hosted Checkout
sessions, validates merchant and Price, verifies Stripe signatures and
records scoped grants. Existing fixtures cover browser UI independently of
the real Stripe and provider integrations.

## Decisions

- Reuse the existing session, webhook, reconciliation, and protected reader
  routes. Keep a TEST key and the matching signing secret in the isolated
  private service and reconciler. Verify the matching account and Price
  with `livemode: false`. Supply the approved TEST notices for the origin.
- Read and validate purchase configuration consistently when rendering the
  offer, enabling a retry, and submitting Checkout. The existing TEST
  banner and origin are inputs to each validation. The server retains
  final authority over payment mode and order ownership.
- Run the existing Chromium browser fixture against actual Workshop assets,
  then repeat the supported flow against isolated Stripe TEST services.
  Use an authorized tester and owned fixtures for repeated GUI runs. Use
  actual supplier content only where test use is permitted.
- Freeze the acceptance boundary at the application: verified webhook,
  persisted order and scoped grant, owned Library and reader access, and
  denial for unowned or refunded scopes. Direct provider checkout probes
  are useful diagnostics but do not cover the Workshop browser path.

## TEST run setup

1. Use a disposable database, object storage, and an approved tester. On
   loopback use the exact configured origin. External staging requires HTTPS
   and the restricted Firebase tester configuration.
2. Set `AUTODATA_COMMERCE_MODE=stripe_test` for Go, private commerce, and
   the reconciler. Configure `AUTODATA_PUBLIC_ORIGIN` consistently and
   deliver the private service token through the runtime's secret mechanism.
   Use Firebase for the Go customer session. The normal development Compose
   defaults use local auth and do not enable the TEST checkout banner.
3. In private commerce and the reconciler, configure
   `AUTODATA_STRIPE_SECRET_KEY`, `AUTODATA_STRIPE_WEBHOOK_SECRET`,
   `AUTODATA_STRIPE_ACCOUNT_ID`, and `AUTODATA_STRIPE_PRICE_ID`.
   For a loopback run, forward TEST events with the Stripe CLI to
   `/v1/payments/stripe/webhook` and use that listener's signing secret.
   Start with purchases paused if the merchant, price, or signing setup is
   incomplete. Set the seven purchase notice fields for the test origin.
4. Confirm the TEST banner and quote before clicking Buy. Complete hosted
   payment with a Stripe test card in an interactive browser. Confirm
   order status, payment event, and the matching persisted grant before
   treating the Library or article read as paid acceptance. Repeat the
   entitlement check after a signed TEST refund.

## Risks and rollback

Stop the isolated test services and discard their disposable state when a
test fails or completes. Keep TEST resources and credentials separate from
production. If a browser fix regresses the purchase flow, revert that
implementation and rerun the fixture. Keep the order and webhook records
needed to reconcile a test purchase until settlement or refund is verified.
