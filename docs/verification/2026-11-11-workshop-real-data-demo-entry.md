# Real-data Workshop demo entry verification

Issue: https://github.com/lucronn/autodata/issues/398  
Project: https://github.com/users/lucronn/projects/8  
Plan: `docs/superpowers/plans/2026-11-11-workshop-real-data-demo-entry.md`

The requested demo must exercise the ordinary Workshop against real, authorized vehicle data. Only Stripe test-mode purchasing is fictional/no-charge. The current public purchase configuration is disabled; Draft PR #399's fictional post-purchase articles are not acceptable for this goal and must not merge as completion.

This bounded app change makes a test-mode entry honest and fail-closed. It neither enables a merchant nor provisions a test environment. The existing server-owned settled-payment grant and all real-data authorization remain authoritative. A ready signal does not grant access. Any vehicle/category without an eligible source article remains honestly absent or preparing; no data is fabricated.

Independent review of `4ecc2d7` found a checkout-time mode race, a local-auth false-ready signal, acceptance of a production public origin under a non-production label, and duplicate-field acceptance in the private mode response. Integration is held until the code and regressions address the first, second and fourth findings. Both processes must reject test checkout on the public production origin; a restricted test audience and supplier test-use rights remain an external deployment gate even on another hostname.

The fictional layout sample remains separate at `?sample=1`, marked as non-service information. It is not the real-data demo. Production `?demo=1` must refuse to label a live or disabled checkout as no-charge. Restricted audience, supplier rights for test use, real Bankone/Banktwo content, Firebase sign-in, Stripe test card/webhook, article/media reads, refunds/revocation, and an actual browser run on an authorized environment remain required for end-to-end acceptance. No production deployment, traffic or payment change is authorized by this document.

## Concrete todo and evidence

- [x] Commit plan/record/doc and synchronize Issue/Project before exact-SHA preflight. Planning checkpoint `0675a17` returned `status:synchronized`, `errors:[]`.
- [x] Red-first Go, Python and browser tests covered test-only readiness, invalid/unavailable commerce, production/live/mismatched private mode refusal, explicit demo refusal, normal app import, sample isolation and Stripe-return banner.
- [ ] Close the exact-head review findings with red-first tests and reverify; independent exact-head re-review and CI are pending.
- [ ] Obtain real licensed-data/test-settlement browser evidence on an authorized, isolated runtime; keep this unchecked until actual receipts exist.

Local code-only evidence before review: `node workshop-demo.test.mjs` passed 5/5; `node workshop-client.test.mjs` passed 258/258; full Go API `go test ./... -count=1` passed with loopback allowed; focused private Go HTTP tests passed. Python commerce/HTTP/purchase-config/Stripe adapter suite passed 36 tests and 63 subtests with 2 integration skips using the pinned Stripe 16.1.0 package. The first Python attempt lacked that package and failed two SDK imports; the rerun used the already-present pinned package and passed. `node --check` for both changed modules and `git diff --check` passed. These are local code/fixture checks only; no real test card, signed webhook, licensed article, public deployment or staging browser acceptance occurred.
