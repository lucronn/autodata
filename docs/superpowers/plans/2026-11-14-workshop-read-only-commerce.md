# Read-only Workshop commerce implementation plan

Goal: Preserve authenticated public Workshop preview reads through an explicit API-only read_only commerce transport while disabling every payment-capable operation and purchase/demo presentation.

Issue: https://github.com/lucronn/autodata/issues/411
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzUf0`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-read-only-commerce.md`. Canonical specification: `docs/architecture/workshop-read-only-commerce.md`. Verification: `docs/verification/2026-11-14-workshop-read-only-commerce.md`. Record: `docs/agents/records/2026-11-14-workshop-read-only-commerce.json`.

Base product source: `c115dcde11bee0ecc64052e8d51d15de7e572da9`. Implement on isolated branch codex/workshop-preview-read-only-commerce after this checkpoint is committed and canonical preflight passes. No live configuration or process changes. Parent/coordinator owns independent review, integration and rollout.

The implementation uses an unexported readOnly flag on HTTPCommerceClient, set only by explicit configuredCommerceClient read_only selection. Do validates receiver/limits, then applies the allowlist from the canonical specification before constructing the outbound request. Because CheckVehicleGrant calls Do on the same client, no embedded wrapper can accidentally bypass the restriction and the client still implements VehicleGrantChecker. purchase-config marshals the existing disabledWorkshopPurchaseConfig result locally. No Server or frontend flag is needed; existing workshopTestCheckoutMode excludes read_only. Tests must verify actual configured client and public handler paths, not a permissive test double for the restricted boundary.

Implementation allowlist: `apps/api-go/commerce_client.go`, new `apps/api-go/commerce_read_only_test.go`, and focused configuration wording in `docs/verification/workshop-commerce-runbook.md`. Canonical plan/spec/record/verification may be updated for evidence. No Python, schema, UI, workflow, service or environment implementation edits. If verification identifies a necessary scope change, synchronize a successor gate before those edits.

Verification: first add regressions exercising the absent read_only configuration and observe failure. Cover production origins, invalid endpoint/token, allowlisted reads with identical private headers/payload, missing/revoked/wrong-scope/unavailable grants, locally forced disabled purchase config despite a would-be enabled private authority, demo false, valid public checkout/webhook/order-status blocked with zero private calls, unknown operations, and retained stripe_test/public-origin rejection. Run complete API/shared-contract Go suites, both Workshop Node suites, diff/scope check, and CGO_ENABLED=0 go build -trimpath. Retain complete local logs, exact candidate SHA/tree and artifact hash in private evidence; do not claim external acceptance from fixtures. Push small coherent milestones and create PR for coordinator's independent exact-head review/CI/merge.

Concrete todo:

- [ ] Commit the synchronized plan, Issue/Project index and canonical documents; pass machine preflight at the exact checkpoint before code edits.
- [ ] Add API-only read_only commerce configuration with a private-operation allowlist that preserves quote, library and exact grant checks.
- [ ] Disable purchase configuration locally and reject checkout/webhook/order-status/demo-mode transport before any private request; keep stripe_test public-origin rejection intact.
- [ ] Verify forwarding, authenticated ownership, missing/revoked grants, private-enabled drift and zero payment-network calls; run complete Go API/contracts and Workshop suites and build/hash the artifact.
- [ ] Push a coherent candidate PR and hand exact-source review/merge to coordinator; leave live release/configuration changes behind a later synchronized rollout gate.

Implementation and local verification receipt: `docs/verification/2026-11-14-workshop-read-only-commerce.md` records checkpoint b326781a99147bd96f13e263ba1832db00d58a41 preflight PASS, source milestone10ab1d8673e9f066a853373fdadcd6b538ab6344, complete Go/Workshop suite PASS and artifact hash. Coordinator independent review, CI, merge and a later live rollout remain pending.

## Quote availability successor gate

Coordinator finding: private Python read_only PR417 must return explicit `purchasable:false`. The original Go validator required true and would turn that response into503. Prior fdf2d23 exact-head review is superseded by this source correction. Base for successor work is fdf2d23dba79a6485fbba10656211fba3fbdb0fc; this checkpoint must be synchronized/committed/preflighted before editing implementation.

Expanded implementation allowlist for this correction: `apps/api-go/commerce.go`, `apps/api-go/commerce_http.go`, `apps/api-go/commerce_client_test.go` (existing helper call adaptation), `apps/api-go/commerce_read_only_test.go`. Pass the actual server CommerceClient to the public DTO validator. Only a nonnil concrete HTTPCommerceClient with its configured unexported readOnly flag may accept a quote whose explicit JSON boolean purchasable is false; nil/default/ordinary stripe_test/stripe_live clients retain true-only validation. Read_only accepts legacy private true while old ingestion remains in service and forwards either boolean without invention. All other quote validation (version/product/scope/label/amount/currency/terms) remains unchanged; missing/null/nonboolean availability remains rejected, including in read_only mode. No browser field, private response field or environment read inside DTO validation supplies mode authority. No changes to checkout, grants or purchase-config behavior.

Successor todo:

- [ ] Synchronize Issue411/Project8 and canonical spec with this quote correction, commit checkpoint and pass exact-base preflight before code edits.
- [ ] Retain red-first public quote regressions; accept and forward explicit false only for actual read_only client while preserving legacy true and rejecting missing/null/malformed/scope-invalid results and false in ordinary Stripe modes.
- [ ] Run complete API/shared-contract Go and Workshop Node suites, rebuild/hash the candidate and update exact source evidence/PR412 for renewed independent review. Do not deploy.
