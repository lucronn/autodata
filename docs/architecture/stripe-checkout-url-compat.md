# Stripe hosted Checkout URL authority

Issue: https://github.com/lucronn/autodata/issues/420
Project: https://github.com/users/lucronn/projects/8
Plan: `docs/superpowers/plans/2026-11-14-stripe-checkout-url-compat.md`

Only exact HTTPS checkout.stripe.com authority with `/c/pay/` or `/g/pay/` and a nonempty opaque suffix is eligible for a hosted checkout redirect. Existing userinfo, explicit-port and whitespace/control rejection stays enforced. Each runtime layer validates independently. URLs and fragments remain opaque; provider identity is server-stored checkout_session_id/order metadata, never inferred from a hosted URL path. Contracts and real acceptance checks must agree. Deterministic fixture checks may additionally restrict their known fixture IDs without claiming they describe real Stripe URL structure.

A November15 authenticated SDK16.1 TEST response returned `/g/pay/` and the old Python validator returned202 processing after successful allocation. Safe evidence includes matching merchant/test/USD2000/order metadata, expected trusted HTTPS host and observed path family. No raw URLs/IDs/secrets are recorded here. All three diagnostic sessions were expired unpaid; owned runtime/database resources were removed and retained data/public disabled state were verified unchanged. Official docs currently show `/c/pay/`: https://docs.stripe.com/api/checkout/sessions/object#checkout_session_object-url ; `/g/pay/` is current live response evidence, not an asserted explicit docs guarantee.

Concrete todo: synchronize/pin/preflight; observe failing multi-layer regressions; implement exact two-path compatibility and opaque identity handling; full relevant tests, exact-head independent review and CI. No public runtime, DNS, secrets, licensed content or production grants change.

## Protected-base integration checkpoint

Protected master: `92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a`, tree `0e4038a6bd506fd1349caa0bfa320813106ce5ad` (#412 then #417). Published PR421 source: `3aaa904304d613852761b0d787407190eeaa9779`, implementation `282954f0deea35a154c385104044b671a1c64971`. No reimplementation, provider sessions, runtime changes or deployment. Prepare this docs-only checkpoint directly on protected master and pass its exact-SHA preflight before merging it into the published PR branch; preserve both published histories. Resolve documentation-only overlap in favor of combined historical evidence and this current checkpoint; stop for coordinator if application conflicts alter reviewed behavior. Revalidate all relevant suites and required strict CI, then request independent exact-head review and hold merge.

Integration record: `docs/agents/records/2026-11-14-stripe-checkout-url-protected-base.json`

- [x] Synchronize Issue420, Project8, plan and canonical architecture at protected master92d81a1 and pass checkpoint preflight
- [x] Merge the synchronized checkpoint into PR421 preserving reviewed implementation282954f and exact master ancestry
- [ ] Run focused and full relevant Go, Node, worker, browser, release-evidence and contract checks on the integrated source
- [ ] Push the protected-base candidate, rerun strict required CI, hand off independent exact-head review and hold merge; no provider sessions or deployment
