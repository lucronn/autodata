# Workshop preview source release verification

Status: exact-source artifact verified; public deployment BLOCKED by current source/host commerce-mode incompatibility. No live release performed.

Goal: Publish exact current Workshop source as a purchase-disabled public preview while preserving runtime dependencies and a verified binary rollback.

Plan: `docs/superpowers/plans/2026-11-14-workshop-preview-source-release.md`. Record: `docs/agents/records/2026-11-14-workshop-preview-source-release.json`.
Issue: https://github.com/lucronn/autodata/issues/410. Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzTRQ`.

Exact product source: `c115dcde11bee0ecc64052e8d51d15de7e572da9`. Previous serving binary and rollback hashes, unchanged configuration requirements, compatibility findings, validation, bounded coordinator rollout and rollback are pinned in the plan. This checkpoint does not modify application source or live service state.

Concrete todo:

- [ ] Pin the current source, compatibility findings, unchanged runtime configuration, previous binary and rollback drop-in.
- [ ] Synchronize and commit this plan, Issue, Project #8 and canonical receipt; pass exact-checkpoint machine preflight.
- [ ] Build the pinned API source and run API/shared-contract and Workshop regression tests; retain hashes and logs.
- [ ] Hand the verified artifact and bounded rollout/rollback to the coordinator; coordinator alone switches the API binary after gate readback.
- [ ] Verify public/local readiness, exact embedded assets and disabled purchase configuration; record final runtime identity and any rollback.

## Exact-source artifact receipt

Planning checkpoint `be44de35682489f4f0d189598461c0a582c71178` was committed/pushed after Issue410 and Project8 readback; canonical machine preflight returned `{"status":"synchronized","errors":[]}` before build/testing. Exact product archive SHA256 `d11db71acf3ef4636cee7947f074a0d76f1154b7fade6a80985819bd523938ed`. API and shared-contract `go test ./...` both passed; Workshop Node suites passed267 tests with0 failures. Build used Go1.26.4 linux/amd64, CGO_ENABLED=0, `go build -trimpath` from the archive. No application file was modified.

Binary SHA256 `d5fea4d91d289e244b2d09cfe7bfb9563d38a1eed719b54090b2b1cee579f506` (61395149 bytes). Private binary: `/home/corp/autodata-evidence/preview-source-release-c115dcde/autodata-api`; manifest, complete logs and build metadata are in the same evidence directory. This binary has not been installed or started against serving dependencies.

The public environment's non-secret mode fields are production + public autodata.cars.tk origin + stripe_test. Current source refuses this combination at commerce initialization. Disabled API commerce also removes required grant-check transport. The binary-only rollout is blocked; no service, DNS, database, ingestion, purchase, grant or secret state was changed. Coordinator received the exact finding before any installation. A later decision must preserve grant checks and disabled purchase while respecting the newly merged non-production-only test checkout boundary.
