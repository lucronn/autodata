# Workshop commerce verification

This lane adds durable $20 USD ownership of one canonical vehicle configuration
and region. A verified Stripe payment grants permanent ownership; current source
availability and content preparation remain separate. UI and paid catalog/media
enforcement are later gated lanes. This document does not approve deployment.

## Configuration

`AUTODATA_COMMERCE_MODE` is explicitly `disabled`, `stripe_test` or `stripe_live`.
The committed manifests keep it disabled. Disabled routes return 503 and never
construct a Stripe client. Enabled ingestion HTTP and the existing payment
reconciler require the Stripe 16.1.0 production image and secret-managed
`AUTODATA_STRIPE_SECRET_KEY`, `AUTODATA_STRIPE_WEBHOOK_SECRET`,
`AUTODATA_INGESTION_INTERNAL_TOKEN`; expected `AUTODATA_STRIPE_ACCOUNT_ID` and
`AUTODATA_STRIPE_PRICE_ID` are server configuration. Keep test/live databases
separate. No secret key or webhook secret belongs in the Go API or browser.

Enabled startup verifies the actual merchant, active one-time Price for exactly
2000 minor USD units, mode, migration 040, product and existing order merchant/mode.
Missing configuration or conflicting database ownership prevents readiness.
`AUTODATA_ENV` and `AUTODATA_PUBLIC_ORIGIN` must match identity configuration:
production exactly `https://cars.tk`; staging/development HTTPS; test may use
HTTP on localhost or a parsed loopback IP. Return origins forbid credentials,
path, query, fragment and malformed ports. Both Checkout returns are the fixed
`<origin>/workshop/?order=<stored UUID>`; returns never grant access.

The Base44 dependency-only image does not include Stripe and remains explicitly
commerce-disabled in this lane. Enabling commerce there requires a separately
gated dependency-image change. No runtime pip installation is introduced.
The legacy fake payment smoke is accepted only while commerce is disabled and
is not payment readiness evidence.

## Required isolated acceptance

The coordinator creates an immutable plain clone, exact input manifest, private
fixture network and owned PostgreSQL/S3/NATS resources using the existing
lifecycle fixture. No host ports, Docker socket mounts, external credentials,
Firebase emulator or live provider calls are needed. The fixture image installs
its dependencies from ingestion pyproject, including Stripe 16.1.0. The official
SDK's HTTP transport is replaced by a deterministic local fixture; HMAC webhook
verification still runs through the actual SDK.

Run the committed collector inside that owned fixture:

```text
python scripts/dev/workshop_commerce_smoke.py --mode fixture --candidate-sha <exact40hex> --output /artifacts/workshop-commerce.json
```

Its child runs exactly the approved three pytest modules, setting
`AUTODATA_LIFECYCLE_TEST=1` and `AUTODATA_REQUIRE_COMMERCE_INTEGRATION=1`.
All fourteen exact unparameterized commerce cases and the migration cases must
execute without skips, failures or timeouts. Missing required fixtures fail.
The first case also executes the exact required Go client root against its actual
Python HTTP server and PostgreSQL rows, validating quote, existing checkout,
status, empty library and missing grant without adding an order. Raw Go JSON
and stderr are required in the ten-file evidence inventory.
The raw JUnit, stdout/stderr, safe synthetic PostgreSQL rows, actual SDK transport
observations and before/after input/Git provenance are retained and hashed in an
allowlisted inventory. A result with missing evidence cannot report success.
The coordinator independently validates these files, runs the current040 R3
and identity regression supervisors, and separately builds/probes the exact
production ingestion image with `import stripe; assert stripe.VERSION ==
'16.1.0'`. Fixture-image proof alone is insufficient for the production image.

## Runtime operations

The existing payment reconciler retries immutable pending signed facts and
leases paid preparation intents. It schedules the actual shared two-provider
catalog index outside financial transactions. A crash or local scheduling
outage retains ownership and retries with bounded backoff. Index acknowledgement
does not fetch every article or promise completed content. A paid library item
can remain `paid` without a requested body. Library readiness checks exact
configuration/region, identity review, membership, descriptor/body/resource
rights and quarantine before reporting a readable current article.

Do not manufacture a replacement Checkout after a local timeout or elapsed
one-hour timer. Unknown creation is replayed with the same stored provider key
only within 23 hours; later ambiguity requires reconciliation. An old session and
intent need authoritative nonchargeable proof before a fresh explicit client key
can allocate a replacement. Paid scopes always return owned without another
provider create. Full refunds/lost full disputes revoke monotonically; an early
refund creates an owner-visible tombstone even before any grant exists.

Live merchant configuration, webhook routing/signing secret, independent final
acceptance, UI, paid-reader/media authorization and release/deployment approvals
remain separate prerequisites. Never put actual tokens, raw provider payloads,
customer email or real payment identifiers in verification artifacts.
