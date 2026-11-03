# Paid Workshop launch contract

Issue: https://github.com/lucronn/autodata/issues/186

Project: https://github.com/users/lucronn/projects/8

This records the current product direction. It is not an implementation
authorization or a production-readiness claim. Each implementation lane still
requires the committed planning gate and an exact-base preflight.

## Product and ownership

The Workshop launch is a one-time purchase of one vehicle dataset for **$20**.
USD is the coordinator's stated currency assumption. The customer-facing domain
is **https://cars.tk**, with DNS managed through Cloudflare.

The initial purchasable unit is the selected normalized vehicle configuration
and region. The server resolves this scope from the catalog; clients cannot
invent vehicle keys or substitute a broader vehicle-family ID at checkout.
Eligible articles from both banks belong to that scope through existing
verified vehicle associations. Similar titles or provider IDs do not establish
cross-bank identity. Selection and price are shown before payment.

A purchase belongs to a durable customer account. Its entitlement has no normal
expiry and needs no subscription or renewal payment. Logging out, changing
devices, deploying the app, or retrying ingestion does not remove ownership.
Existing source-rights withdrawal and explicit, auditable refund/revocation
remain separate policy transitions. The launch does not promise offline export
or a fixed immutable copy of all future content.

The same shared canonical article is rewritten once per source/transformation
identity and reused by entitled customers. Readable source content remains
available while rewriting completes. Source, canonical content and media obey
the same purchased-scope and current-rights checks.

## Customer flow

1. Browse safe vehicle selectors and see the selected configuration, region
   and one-time price.
2. Sign in with Firebase. Google sign-in is the proposed initial provider.
   Map the verified Firebase project and UID to a server-owned account and
   personal organization; email and browser-supplied claims cannot assign
   ownership or staff privileges.
3. Create or reuse a server-owned order, then enter hosted Stripe Checkout.
   A success redirect cannot grant access. Only verified settled payment
   matching the stored order, session, scope, amount and currency may do so.
4. Show payment processing until the durable grant exists. Keep payment state
   separate from content preparation; retrying preparation never charges again.
5. Open the purchased configuration from a persistent **My vehicles** library.
   Unpaid or adjacent scopes remain locked, including direct API/media calls.

Production authentication will use secure same-origin sessions rather than the
current local demo bearer. Full article, source, processing and media reads
must check entitlement before hydration or storage access. Public browsing
exposes selectors and a safe quote, with bounded catalog hydration.

## Reuse and implementation sequence

The repository already has a Stripe adapter, durable payment reconciliation,
non-expiring organization entitlements and protected dataset projections.
Customer accounts, checkout/webhook HTTP wiring, library reads and purchased
Workshop catalog authorization still need implementation.

The customer design supersedes the generic OIDC-only assumptions and
role-only shared-catalog rule in the earlier R5 plan. That older plan does not
authorize the expanded commerce implementation unchanged.

Concrete todo:

- [ ] Freeze and verify Firebase account/session contracts and additive
  migration 039 against the integrated R3 interfaces and shared migration runner.
- [ ] Freeze server-owned orders, authoritative USD 2000 pricing, idempotent
  Stripe settlement, durable grants and explicit refund/revocation handling.
- [ ] Add safe browse/quote and owned-library APIs; enforce purchased scope
  across article, source, processing and media access.
- [ ] Build sign-in, checkout return, My vehicles and source/canonical reader
  states, with browser and accessibility acceptance.
- [ ] Verify configured identity, Stripe test payment/webhook, both banks,
  persistence, backup/restore, monitoring and the exact release candidate.
- [ ] Deploy the verified candidate to the selected host and validate cars.tk.

## Hosting decisions still to resolve

The user has Google Cloud/Firebase and Vercel available and permits self hosting.
Firebase identity with Google Cloud hosting is the proposed deployment. The
specific project is awaiting the user's selection. No resources, DNS changes,
live payments or production deployment have been made for this plan.

The current runtime includes persistent PostgreSQL, NATS, S3-compatible storage
and long-running workers, so hosting must support those dependencies. A static
Vercel deployment alone is insufficient. The deployment plan must freeze service
placement, region, capacity, secret delivery and operating cost before creation.
The user's launch goal authorizes preparing and executing a concrete release;
earlier orchestration-only deployment restrictions are historical scope, not a
reason to abandon the launch request. No code or infrastructure gate is waived.


### Concurrent Workshop delivery

The user requested three concurrent builders. The canonical parallel plan is `docs/superpowers/plans/2026-11-03-workshop-parallel-delivery.md`: twelve article-access paths, four protected-media paths and thirty-two UI paths have exclusive owners. Reviewed interfaces permit parallel implementation after synchronized preflight while the coordinator completes dependency/runtime acceptance. This replaces serial dispatch timing, not production acceptance requirements. Commerce candidate9d33e1e remains unverified pending its remaining fixture repair and runtime/image/CI checks.
