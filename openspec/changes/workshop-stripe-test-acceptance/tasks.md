## 1. Prepare the isolated TEST path

- [x] Verify that the available Stripe TEST account, Price and signing
  secret match the isolated application. Keep private settings outside Git.
- [x] Run local Workshop browser fixtures and reproduce any blocked or
  misleading purchase action before applying the fix.

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
- All 21 API fixture cases passed across Chromium, Firefox, and WebKit
  with isolated Go, Python, PostgreSQL, and object storage. They covered
  sign-in, checkout and Library persistence, both provider fixtures from
  stored source to canonical article and warm media reads, account and
  vehicle-scope denial, and signed fixture refund revocation.
- Run `scripts/dev/workshop_browser_test.sh` to repeat the full API matrix.
  It uses simulated identity, payments, and source content. The Workshop
  browser integration workflow runs the same command for relevant pull
  requests.
- Real hosted settlement, webhook-driven grant and refund, and licensed
  article acceptance remain open. The former local Firebase verifier file is
  missing and no dedicated TEST project is configured on Kali. Use a
  dedicated Firebase test environment and tester for the
  authenticated Workshop flow and complete hosted Checkout interactively.
  Keep licensed-data checks scoped to content approved for test use.
