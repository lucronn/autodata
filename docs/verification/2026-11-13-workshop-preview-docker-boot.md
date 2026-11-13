# Workshop preview Docker boot dependency verification

Status: planning; no production change.

Goal: prevent the purchase-disabled Workshop API from racing an inactive Docker-hosted PostgreSQL dependency after a host reboot. Plan: `docs/superpowers/plans/2026-11-13-workshop-preview-docker-boot.md`. Record: `docs/agents/records/2026-11-13-workshop-preview-docker-boot.json`. Tracking: [Issue #391](https://github.com/lucronn/autodata/issues/391), [Project #8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhHfSQM`.

At 2026-11-13 21:33 UTC, public `/readyz` returned HTTP 502. The origin had rebooted at 16:29:40 EST. The enabled `autodata-api.service` was restarting after refused PostgreSQL connections to `127.0.0.1:5432`; `docker.service` was disabled and inactive. The API unit ordered itself after Docker but did not pull it in. These read-only observations identify the current reboot gap, not the reason Docker was disabled or the cause of earlier public failures. No service, DNS, payment, grant, or traffic state was changed.

Concrete todo:

- [ ] Commit and preflight the synchronized plan, Issue #391, Project #8, and this document at an exact base SHA.
- [ ] Test the preview-only drop-in for Docker pull-in and ordering without changing service command, environment, payment, or grants.
- [ ] Validate the systemd syntax, obtain independent exact-head review and required CI, and merge only under live branch protection.
- [ ] In a separately authorized host rollout, inventory Docker restart-policy blast radius, capture rollback state, install the exact reviewed drop-in, and verify the effective unit and endpoints.
- [ ] Retain a cold-boot acceptance receipt for local/public readiness, Workshop rendering, and purchase `enabled:false`; do not claim release completion from unit tests or warm probes.

The candidate is a source-controlled release artifact only. It is not installed on the live host by this task. Even after merge, Issue #391 remains open until an authorized rollout and cold-boot verification demonstrate durable user-facing recovery.
