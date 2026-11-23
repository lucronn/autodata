## 1. Prepare the isolated TEST path

- [x] Verify that the available Stripe TEST account, Price and signing
  secret match the isolated application. Keep private settings outside Git.
- [x] Run local Workshop browser fixtures and reproduce any blocked or
  misleading purchase action before applying the fix.

## Temporary simulation on the main Workshop

- [x] Verify a no-charge purchase in the ordinary browser flow with the
  same selected configuration, Library, article reader and authorized media.
- [x] Exercise stale checkout, account denial, and switching simulation off.
- [ ] Verify ordinary sign-in and the same real-data flow on the public Workshop.

## 2. Apply and verify the Workshop fix

- [x] Make purchase rendering, submission and explicit retry agree on the
  approved TEST origin and notices. Keep the server-side TEST mode guard.
- [x] Verify vehicle selection, terms, Checkout transition, pending/paid
  states and article viewing/reopen in Chromium. Check cancellation
  and access denial with focused tests.

## 3. Verify real Stripe TEST settlement

- [ ] Complete a TEST card purchase in hosted Checkout from Workshop.
  Confirm signed webhook settlement and exact-scope grant on the server.
- [ ] Verify the owned Library, article body and illustrations, including
  reload and an unowned or signed-out attempt. Verify TEST refund/revocation.
- [x] Record fixture coverage, real Stripe coverage and supplier-backed
  coverage separately, including any blocked or unverified step.

## Verification on Kali

- The 120 Workshop UI fixture scenarios passed across Chromium, Firefox,
  and WebKit. Eight focused desktop and mobile Chromium checks also passed.
  The focused cases reproduced the Buy failure against the base before
  passing on the fix.
- In a separate disposable database, the private commerce service used
  the configured Stripe TEST merchant and one-time USD 20 Price. The TEST
  listener started with its own signing secret. The service created a real
  hosted TEST session, reused the order on retry, and denied unpaid access.
  Stripe presented a human verification challenge before payment. The
  unpaid session was expired and the temporary services were removed.
- On `c2f6922`, the real Workshop commerce handler created the sandbox
  Checkout session for a synthetic customer in a disposable Kali database.
  Stripe's official CLI checkout fixture completed that exact session with a
  test payment method. The signed Checkout and PaymentIntent events granted
  exact owner, vehicle and region access and a single Library item. A real
  full TEST refund delivered a signed revocation. Stripe charge and refund API
  readback, persisted verified event rows, and the server grant checks agreed.
  Replaying the stored settlement left the revocation in place.
- On `dc7c953`, Kali Chromium connected the native signed Workshop buyer
  flow to the same provider-backed method. The browser started the exact
  scoped Checkout, kept the return unpaid until the Stripe-signed event
  reached the actual public Go webhook, then opened the owned Library,
  stored article, rewritten article, and protected image. Library state
  survived a reload and app restart. A Stripe-signed full TEST refund
  revoked the order and denied the previously valid article, source, and
  image links. This connected run used the provider test fixture, a local
  signed identity fixture, and synthetic supplier content.
- A separate TEST expiry case delivered two genuine signed expiry events.
  Reusing the first idempotency key kept its session, and a new key opened a
  fresh session after expiry. Both sessions ended unpaid with zero grants.
- All 21 API fixture cases passed across Chromium, Firefox, and WebKit
  with isolated Go, Python, PostgreSQL, and object storage. They covered
  sign-in, checkout and Library persistence, both provider fixtures from
  stored source to canonical article and warm media reads, account and
  vehicle-scope denial, and signed fixture refund revocation.
- Run `scripts/dev/workshop_browser_test.sh` to repeat the full API matrix.
  It uses simulated identity, payments, and source content. The Workshop
  browser integration workflow runs the same command for relevant pull
  requests.
- The provider-backed rehearsal used synthetic identity and the official CLI
  sandbox fixture. The browser-driven hosted Checkout flow, a dedicated
  authenticated staging flow and licensed article acceptance remain open.
  A current Firebase configuration read confirmed Google sign-in is enabled
  and its authorized domains omit the candidate staging origin. The
  authenticated staging flow needs an approved Firebase environment and
  tester. Keep licensed-data checks scoped to content approved for test use.
