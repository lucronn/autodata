# Workshop preview source release verification

Status: synchronized planning checkpoint; no live release performed.

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
