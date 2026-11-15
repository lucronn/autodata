# Stripe hosted Checkout URL authority

Issue: https://github.com/lucronn/autodata/issues/420
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-stripe-checkout-url-compat.md`

Only exact HTTPS checkout.stripe.com authority with `/c/pay/` or `/g/pay/` and a nonempty opaque suffix is eligible for a hosted checkout redirect. Existing userinfo, explicit-port and whitespace/control rejection stays enforced. Each runtime layer validates independently. URLs and fragments remain opaque; provider identity is server-stored checkout_session_id/order metadata, never inferred from a hosted URL path. Contracts and real acceptance checks must agree. Deterministic fixture checks may additionally restrict their known fixture IDs without claiming they describe real Stripe URL structure.

A November15 authenticated SDK16.1 TEST response returned `/g/pay/` and the old Python validator returned202 processing after successful allocation. Safe evidence includes matching merchant/test/USD2000/order metadata, expected trusted HTTPS host and observed path family. No raw URLs/IDs/secrets are recorded here. All three diagnostic sessions were expired unpaid; owned runtime/database resources were removed and retained data/public disabled state were verified unchanged. Official docs currently show `/c/pay/`: https://docs.stripe.com/api/checkout/sessions/object#checkout_session_object-url ; `/g/pay/` is current live response evidence, not an asserted explicit docs guarantee.

Concrete todo: synchronize/pin/preflight; observe failing multi-layer regressions; implement exact two-path compatibility and opaque identity handling; full relevant tests, exact-head independent review and CI. No public runtime, DNS, secrets, licensed content or production grants change.
