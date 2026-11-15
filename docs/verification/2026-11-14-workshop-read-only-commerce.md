# Read-only Workshop commerce verification

Status: source implementation and local verification complete; coordinator independent review, CI and merge pending. No runtime action.

Goal: Preserve authenticated public Workshop preview reads through an explicit API-only read_only commerce transport while disabling every payment-capable operation and purchase/demo presentation.

Issue: https://github.com/lucronn/autodata/issues/411
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzUf0`.
Plan: `docs/superpowers/plans/2026-11-14-workshop-read-only-commerce.md`. Canonical specification: `docs/architecture/workshop-read-only-commerce.md`. Verification: `docs/verification/2026-11-14-workshop-read-only-commerce.md`. Record: `docs/agents/records/2026-11-14-workshop-read-only-commerce.json`.

Concrete todo:

- [x] Commit the synchronized plan, Issue/Project index and canonical documents; pass machine preflight at the exact checkpoint before code edits.
- [x] Add API-only read_only commerce configuration with a private-operation allowlist that preserves quote, library and exact grant checks.
- [x] Disable purchase configuration locally and reject checkout/webhook/order-status/demo-mode transport before any private request; keep stripe_test public-origin rejection intact.
- [x] Verify forwarding, authenticated ownership, missing/revoked grants, private-enabled drift and zero payment-network calls; run complete Go API/contracts and Workshop suites and build/hash the artifact.
- [ ] Push a coherent candidate PR and hand exact-source review/merge to coordinator; leave live release/configuration changes behind a later synchronized rollout gate.

## Local source receipt

Checkpoint `b326781a99147bd96f13e263ba1832db00d58a41` was committed and pushed after literal Issue411/Project8 readback. Canonical `pre_implementation.py` returned `{"status":"synchronized","errors":[]}` before tests or code edits.

Implementation milestone `10ab1d8673e9f066a853373fdadcd6b538ab6344`, tree `5167e10815ffee50617f283b17f81dfa0ca421eb`, adds the read_only operation allowlist and existing disabled purchase configuration response inside HTTPCommerceClient.Do. The configured client retains VehicleGrantChecker. Existing public-origin stripe_test rejection is unchanged. No Server, frontend, Python, schema, service or environment implementation file changed.

The new regression suite first failed on absent read_only configuration, then passed. It covers production-origin configuration and endpoint/token validation; actual authenticated public quote/library forwarding; private token and trusted owner/scope; typed missing/revoked/unavailable/wrong-configuration/wrong-region grants; disabled GET/HEAD purchase config despite a would-be enabled private authority and private outage; false demo even if the test-ready field drifts true; valid authenticated checkout, signed webhook and order-status blocked503; and direct forbidden/unknown private operations with zero outbound calls.

Full API `go test ./...` passed17.045s; shared contracts passed. Both Workshop Node suites passed267 tests with0 failures/skips. `git diff --check` passed. Go1.26.4 linux/amd64 CGO_ENABLED=0 `go build -trimpath` produced binary SHA256 `86a7f4c904978f722aafc63de53cb468a94b669ef5449d7f0b133f6b6ac7d6a4`. Binary, source/artifact manifest, red/green/full test logs and build metadata are retained privately under `/home/corp/autodata-evidence/workshop-read-only-commerce/`.

These local fixture/suite results do not demonstrate Firebase/Stripe/supplier live acceptance or deployment. Existing optional integration fixtures require their separately provisioned services. Issue410's exact-c115 binary remains blocked. A future live release must pin merged source, rebuild and synchronize a new binary/configuration rollout checkpoint selecting read_only explicitly on the Go API. No live service/configuration, grant, secret, DNS or private merchant mode was changed here.
