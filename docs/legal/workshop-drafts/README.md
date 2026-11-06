# Workshop policy review package

Prepared November 6, 2026 for AutoData, LLC, Georgia, USA; support@cars.tk.
These are review drafts, not approved legal advice or published policies.
No effective date is assigned. No application, payment configuration, or public
page changes are included; checkout must remain disabled pending launch review.

- [Terms](terms.md)
- [Privacy Notice](privacy.md)
- [Refund Policy](refunds.md)
- [Contact](contact.md)

## Concrete proposal and necessary owner decisions

The Terms now propose individual account use for personal vehicle work or the
purchaser's internal business workshop work, without shared credentials,
redistribution, scraping or an export/printing license. The Refund Policy now
proposes a **14-calendar-day full refund for any reason, even after viewing**,
correction of duplicate charges, and a full refund if a reported delivery or
material-description problem cannot be resolved within seven calendar days
unless the customer agrees to more time. Contact is supplied as a fourth draft.
These are proposed defaults for review, not assertions of approved practices.

Only the owner can settle the remaining launch decisions:

| Decision | Concrete review action |
| --- | --- |
| Customer use and remedies | Approve or edit the Terms' individual/internal-use license and the refund commitments above; confirm they can be honored operationally. Upstream permission to sell access does not by itself establish every customer license right. |
| Tax and markets | Name the countries/states where sales will be accepted and approve a truthful tax notice within the existing **USD $20 total**. Do not claim tax exemption, tax inclusion, tax collection or a registration status without confirmation. Adding tax on top changes the product contract. |
| Privacy facts and operations | Confirm deployed hosting/CDN, database/storage, logging, email/support and any analytics/advertising providers, processing countries, and sale/sharing practices. Supply the actual retention/deletion schedule for account, session, order/payment, support, log and backup records; identify who handles privacy requests and how account deletion affects purchased access. Confirm required legal bases, transfer disclosures, age eligibility and children's-data handling for the chosen markets. The Privacy Notice remains incomplete until these facts are supplied. |
| Seller/contact details | Confirm AutoData, LLC's legal identity, required postal/business address, and that support@cars.tk is monitored and works externally. Approve the proposed service-closure/remedy wording. The proposal adds no arbitration mandate, exclusive venue or liability cap. |
| Publication | Approve final wording, effective date and the four public HTTPS policy/contact URLs. Complete the normal implementation gate before public pages/configuration or payment activation. |

The owner has confirmed that both Bankone and Banktwo agreements allow storing,
rewriting and selling access to article content. This is owner-reported and is
not an independent review of the agreements or approval of the customer license.

Do not replace missing privacy facts with invented retention periods. A
purpose-based sentence such as "We retain purchase records while needed to
provide purchased access and meet applicable legal obligations" can explain the
reason for retention, but does not replace a verified schedule or other
required disclosure. No statement that data is never sold/shared should be
published until deployed practices have been checked.

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
