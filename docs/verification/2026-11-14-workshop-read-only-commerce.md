# Read-only Workshop commerce verification

Status: synchronized planning; implementation pending exact checkpoint preflight. No runtime action.

Goal: Preserve authenticated public Workshop preview reads through an explicit API-only read_only commerce transport while disabling every payment-capable operation and purchase/demo presentation.

Issue: https://github.com/lucronn/autodata/issues/411
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzUf0`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-read-only-commerce.md`. Canonical specification: `docs/architecture/workshop-read-only-commerce.md`. Verification: `docs/verification/2026-11-14-workshop-read-only-commerce.md`. Record: `docs/agents/records/2026-11-14-workshop-read-only-commerce.json`.

Concrete todo:

- [ ] Commit the synchronized plan, Issue/Project index and canonical documents; pass machine preflight at the exact checkpoint before code edits.
- [ ] Add API-only read_only commerce configuration with a private-operation allowlist that preserves quote, library and exact grant checks.
- [ ] Disable purchase configuration locally and reject checkout/webhook/order-status/demo-mode transport before any private request; keep stripe_test public-origin rejection intact.
- [ ] Verify forwarding, authenticated ownership, missing/revoked grants, private-enabled drift and zero payment-network calls; run complete Go API/contracts and Workshop suites and build/hash the artifact.
- [ ] Push a coherent candidate PR and hand exact-source review/merge to coordinator; leave live release/configuration changes behind a later synchronized rollout gate.
