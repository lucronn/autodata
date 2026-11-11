# Real-data Workshop demo entry verification

Issue: https://github.com/lucronn/autodata/issues/398  
Project: https://github.com/users/lucronn/projects/8  
Plan: `docs/superpowers/plans/2026-11-11-workshop-real-data-demo-entry.md`

The requested demo must exercise the ordinary Workshop against real, authorized vehicle data. Only Stripe test-mode purchasing is fictional/no-charge. The current public purchase configuration is disabled; Draft PR #399's fictional post-purchase articles are not acceptable for this goal and must not merge as completion.

This bounded app change makes a test-mode entry honest and fail-closed. It neither enables a merchant nor provisions a test environment. The existing server-owned settled-payment grant and all real-data authorization remain authoritative. A ready signal does not grant access. Any vehicle/category without an eligible source article remains honestly absent or preparing; no data is fabricated.

The fictional layout sample remains separate at `?sample=1`, marked as non-service information. It is not the real-data demo. Production `?demo=1` must refuse to label a live or disabled checkout as no-charge. Restricted audience, supplier rights for test use, real Bankone/Banktwo content, Firebase sign-in, Stripe test card/webhook, article/media reads, refunds/revocation, and an actual browser run on an authorized environment remain required for end-to-end acceptance. No production deployment, traffic or payment change is authorized by this document.

## Concrete todo and evidence

- [ ] Commit plan/record/doc and synchronize Issue/Project before exact-SHA preflight.
- [ ] Red-first Go and browser tests covering test-only readiness, invalid/unavailable commerce, production/live refusal, explicit demo refusal, normal app import, sample isolation and Stripe-return banner.
- [ ] Implement and verify the bounded Workshop entry; report exact tests and review/CI.
- [ ] Obtain real licensed-data/test-settlement browser evidence on an authorized, isolated runtime; keep this unchecked until actual receipts exist.

