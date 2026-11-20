# AutoData Workshop Privacy Notice

**Draft for owner review — November 6, 2026. Incomplete until the privacy
inventory and decisions in README.md are verified. Not effective or published.**

AutoData, LLC, based in Georgia, USA, provides AutoData Workshop. For privacy
questions or requests, contact [support@cars.tk](mailto:support@cars.tk).

## Information used to provide Workshop

When you sign in, Google/Firebase handles authentication. Workshop uses the
verified Firebase project and user identifiers to associate you with an internal
account and organization. Account records include account status and creation
time. Sign-in records include a hash of the session token, authentication,
creation and expiry times, and revocation status. These Workshop account and
session tables do not store your Google display name or email address;
Google/Firebase processes sign-in information under its own privacy notice.

When you select a vehicle or purchase a dataset, Workshop uses the selected
vehicle configuration and region, account and order identifiers, purchase
amount and currency, payment status, and access records to provide the right
dataset and recover purchases. Stripe hosts the payment form and processes
payment details. Card details are entered on Stripe's hosted form. Workshop
stores order and access records, Stripe checkout-session and payment-intent
references, payment and refund status, timestamps, and selected signed payment
event facts such as amounts, currency, and event identifiers. Workshop sends
Stripe the configured price and an order identifier to connect payment to the
purchase. Do not send full card details or sign-in credentials to support.

If you contact support, we receive the information you include in your message
and use it to respond and investigate your request.

## Purposes and service providers

We use this information to authenticate customers, provide purchased access,
process and reconcile payments and refunds, support customers, and protect the
service from misuse. Google/Firebase and Stripe process information to provide
sign-in and payment services under their applicable terms and privacy notices.
Workshop stores account, session, purchase, and access records in a PostgreSQL
database and serves catalog images and source artifacts from S3-compatible
object storage. The API records operational errors and request identifiers.
The current Workshop preview is delivered through Vercel at
`https://autodata.cars.tk/workshop/`. The final notice must identify the
application-hosting, logging, and support providers and processing locations
actually used for launch, including any changes from this preview.

## Cookies and browser storage

Workshop uses the essential `__Host-autodata_session` cookie for authenticated
access. It is Secure, HttpOnly, and SameSite=Lax, with a maximum lifetime of
12 hours. Signing out revokes the session and clears the cookie. The Firebase
browser sign-in client uses in-memory persistence. The payment flow uses browser
session storage for the selected configuration and region, a checkout retry
identifier, and an order identifier when available, to recover a checkout
attempt and help avoid duplicate requests. Blocking these mechanisms can prevent
sign-in or checkout from working. The final notice must describe any additional cookies, analytics,
or advertising technologies used on the deployed site.

## Retention, requests, and location

Account and purchase records support continuing access and payment recovery.
Session expiry or sign-out ends authenticated access; it does not by itself
delete the account, stored session record, or purchase history.
Before publication, AutoData must specify how long account, session, payment,
support, and operational records are retained, including backup handling and
any legally required retention.

Email [support@cars.tk](mailto:support@cars.tk) to request access to, correction
of, or deletion of your personal information. We may need to verify your
identity. Available rights and exceptions depend on applicable law; deletion
can affect the ability to maintain or recover purchased access.

Before publication, AutoData must confirm the countries where its providers
process information, any required transfer disclosures and legal bases, how it
handles children's information, and whether any data sale, sharing, advertising,
or tracking disclosures or choices are required. This draft makes no claim
that those practices have been audited or ruled out.

Use [Contact](contact.md) for help reaching us. Read the [Terms](terms.md) and
[Refund Policy](refunds.md) before purchasing. We will date the final notice and
describe material changes when required.
