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

- Chromium passed 40 Workshop fixture scenarios and eight focused checks
  covering desktop and mobile Checkout, cancellation, the pending-to-paid UI
  transition, and search, article reopen, and reload. The focused cases
  reproduced the Buy failure against the base before passing on the fix.
  These browser runs substitute synthetic provider responses and articles.
- In a separate disposable database, the private commerce service used
  the configured Stripe TEST merchant and one-time USD 20 Price. The TEST
  listener started with its own signing secret. The service created a real
  hosted TEST session, reused the order on retry, and denied unpaid access.
  Stripe presented a human verification challenge before payment. The
  unpaid session was expired and the temporary services were removed.
- A Chromium run against isolated Go, Python and PostgreSQL passed the
  checkout, signed fixture event, and Library case using synthetic
  identity and payment transports. The fixture now serializes UUID and
  timestamp values in its final database snapshot so a completed run can
  publish its result. A separate Bankone fixture displayed stored source,
  its image, and source review, then timed out waiting for canonical
  content after releasing the fixture model. The full API browser suite
  remains unverified.
- Real hosted settlement, webhook-driven grant and refund, and licensed
  article acceptance remain open. The prior local Firebase verifier file is
  missing. Use an approved Firebase test environment and tester for the
  authenticated Workshop flow and complete hosted Checkout interactively.
  Keep licensed-data checks scoped to content approved for test use.
