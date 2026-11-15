# Read-only Workshop commerce transport

Goal: Preserve authenticated public Workshop preview reads through an explicit API-only read_only commerce transport while disabling every payment-capable operation and purchase/demo presentation.

Issue: https://github.com/lucronn/autodata/issues/411
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzUf0`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-read-only-commerce.md`. Canonical specification: `docs/architecture/workshop-read-only-commerce.md`. Verification: `docs/verification/2026-11-14-workshop-read-only-commerce.md`. Record: `docs/agents/records/2026-11-14-workshop-read-only-commerce.json`.

`AUTODATA_COMMERCE_MODE=read_only` is a Go API configuration only. It constructs the existing authenticated HTTPCommerceClient with the same validated private ingestion URL and internal token and applies an operation allowlist before any HTTP request. The private Python commerce authority keeps its own existing mode/configuration. Read_only does not label test payments live, change grants, bypass Firebase sessions or accept a browser authority claim. Existing stripe_test rejection on public production origins remains intact. Existing disabled/stripe_test/stripe_live semantics stay unchanged. No new secrets, DB migration or environment default is added.

Only `quote`, `library` and `grants/check` may reach the private commerce service. Grant transport retains CheckVehicleGrant and existing exact account, organization, configuration and region checks, required/revoked/unavailable behavior, private authentication, timeout/redirect/body bounds and safe errors. Library retains Firebase-authenticated ownership and sanitization; quote retains validated configuration/region. Order-status is refused: its apparently read-shaped private handler may reconcile expired checkout sessions with Stripe and write order state.

`purchase-config` returns the existing complete disabled configuration locally (terms_version workshop-v1, URLs/tax notice null) without consulting private authority. Private enabled config, private unavailability or later merchant drift cannot enable purchasing. `demo-mode`, `checkouts`, `stripe/webhook`, `orders/status` and unknown operations fail closed before HTTP; public demo mode remains enabled:false because read_only is not stripe_test, including if a test-readiness flag is accidentally set. Valid public checkout/webhook requests receive the existing generic503 COMMERCE_UNAVAILABLE. Malformed/unauthenticated requests retain current validation/authentication errors. No private payment-side operation is dispatched.

This mode permits existing authorized content access and preparation exactly as already governed by paid catalog code. It does not promise a globally read-only application or suppress authorized source preparation; its boundary is commerce transport. New payment/grant creation, test purchasing on public domains and paid release acceptance remain disallowed.

Only a later synchronized coordinator rollout may select read_only for the live API; source merge alone does not change service state. Issue410 exact-c115 release remains blocked until this source is merged and a new product pin, artifact and rollout checkpoint replace the obsolete candidate.
