# Workshop policy review package

Prepared November 6, 2026 for AutoData, LLC, Georgia, USA; support@cars.tk.
These are review drafts, not approved legal advice or published policies.
No effective date is assigned. No application, payment configuration, or public
page changes are included; checkout must remain disabled pending launch review.

- [Terms](terms.md)
- [Privacy Notice](privacy.md)
- [Refund Policy](refunds.md)

## Owner decisions before publication

1. **License:** approve the proposed use for the purchaser's own work or own
   business's workshop work; decide whether multiple employees may use one
   account, and whether any customer copying/export is permitted. The owner has
   confirmed that both Bankone and Banktwo agreements allow storing, rewriting,
   and selling access to article content; this is an owner-reported fact, not
   an independent review of those agreements.
2. **Refund discretion:** decide eligibility, request window, handling after
   content is accessed, and treatment of incorrect selection/change of mind.
   Approve the support-led investigation process and choose any response target.
   Mandatory consumer remedies remain available regardless of that decision.
3. **Tax and selling territory:** confirm where sales will be offered and the
   tax treatment of the USD $20 total, registration/collection obligations, and
   exact customer-facing tax notice. Do not add tax on top of the current total.
4. **Privacy operations:** verify all launch providers and data flows, including
   hosting/CDN, operational logs, email/support, cookies, analytics, and payment
   data received; determine any sale/sharing/advertising disclosures, processing
   locations, legal bases and transfer mechanisms required for target markets.
   Set retention/deletion periods for account, session, purchase, support, log,
   and backup records; assign a workable rights-request process and explain how
   deletion affects continuing access. Decide age eligibility and handling of
   children's information. Do not publish the incomplete privacy draft.
5. **Seller and terms:** confirm the legal entity details and any business/postal
   address disclosure required for target markets; approve warranty language,
   any desired liability cap or governing-law/dispute terms, and the treatment
   of lost source rights or service closure for existing purchasers. This draft
   includes no arbitration mandate, exclusive venue, or liability cap.
6. **Publication:** approve final wording and effective date; choose public HTTPS
   Terms, Privacy, Refund, and Contact URLs with a functioning support path.
   The purchase configuration requires all four URLs plus an approved tax
   notice. Publish and verify them through the normal implementation gate;
   policy approval alone does not enable payments or authorize deployment.

## Basis and boundaries

The seller identity, support address, jurisdiction and price were supplied by
the owner. The owner also confirmed that both Bankone and Banktwo agreements
permit storing, rewriting, and selling access to article content. No independent
contract review is claimed. Product scope and durable access follow
[the canonical commerce contract](../../architecture/workshop-commerce.md).
The drafts do not claim an immutable download, all future content, uninterrupted
availability, a retention period, a tax exemption, a blanket no-refunds rule,
or a verified absence of tracking/data sharing.

Source reviewed at `eb920f85459ddd075034dad5d2cb573a75a7f75b` and rechecked
against the PR base `ddf7801151abf314f747a0b80eafcbb43ca3f108` for the factual
privacy inventory:

- `apps/api-go/workshop/auth.mjs` and `apps/api-go/postgres_auth_sessions.go`:
  Google/Firebase identity, account mapping and sessions. Email retention by
  the application is not inferred from Google sign-in.
- `db/migrations/039_production_identity_sessions.sql` and
  `apps/api-go/auth_session.go`: Firebase project/UID and internal account/
  organization mapping, status/timestamps, hashed session tokens, revocation,
  and the Secure, HttpOnly, SameSite=Lax session cookie lasting at most 12 hours.
  Browser Firebase persistence is in-memory; session expiry is not row deletion.
- `apps/api-go/workshop/commerce.mjs`: selected scope, USD 2000 minor units,
  Stripe hosted checkout, checkout-attempt browser session storage, four policy
  URLs and tax notice required for a valid enabled purchase configuration.
- `workers/ingestion-python/src/autodata_ingestion/commerce_service.py`:
  durable account-bound orders and provider payment references/status.
- `db/migrations/040_workshop_commerce.sql` and
  `workers/ingestion-python/src/autodata_ingestion/stripe_adapter.py`: order,
  scope, amount/currency and access records; hosted card Checkout receives
  configured price and order metadata. Stored signed event facts are normalized
  payment identifiers/status/amounts, rather than the complete raw webhook.
  A verified full refund or lost chargeback revokes purchased access; this
  mechanism does not define discretionary refund eligibility.
- `apps/api-go/catalog_image_storage.go`: catalog images are served from
  S3-compatible object storage. This does not establish the launch storage vendor
  or region, or imply a customer-upload feature.
- `apps/api-go/main.go` and `infra/deploy/gce/Caddyfile`: API operational-error
  and request-ID logging exists; the checked-in Caddy definition disables access
  logs and discards its logs. Deployed logging and retention need confirmation.

No automated customer-account deletion endpoint or account/session purge was
established by this bounded identity/commerce review. The owner must specify
an executable request process and appropriate account, transaction, support,
log and backup retention. Do not treat the 12-hour cookie limit as a deletion
schedule or publish an immediate-erasure promise. No first-party analytics
integration was found in the examined Workshop modules; that is not proof
about the entire deployed site or third-party sign-in/payment surfaces.

These observations establish source behavior, not the exact deployed provider
inventory or a complete privacy/security audit. Customer-facing pages, policy
links, runtime configuration and payment activation remain outside this PR.
The repository pre-implementation gate remains required for those changes.
