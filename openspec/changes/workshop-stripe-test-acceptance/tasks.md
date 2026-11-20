## 1. Prepare the isolated TEST path

- [ ] Verify that the available Stripe TEST account, Price and signing
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
- [ ] Record fixture coverage, real Stripe coverage and supplier-backed
  coverage separately, including any blocked or unverified step.
