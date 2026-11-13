# Workshop preview Docker boot dependency verification

Status: source candidate verified locally; independent review, PR CI, merge, and host rollout pending. No production change.

Goal: prevent the purchase-disabled Workshop API from racing an inactive Docker-hosted PostgreSQL dependency after a host reboot. Plan: `docs/superpowers/plans/2026-11-13-workshop-preview-docker-boot.md`. Record: `docs/agents/records/2026-11-13-workshop-preview-docker-boot.json`. Tracking: [Issue #391](https://github.com/lucronn/autodata/issues/391), [Project #8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhHfSQM`.

At 2026-11-13 21:33 UTC, public `/readyz` returned HTTP 502. The origin had rebooted at 16:29:40 EST. The enabled `autodata-api.service` was restarting after refused PostgreSQL connections to `127.0.0.1:5432`; `docker.service` was disabled and inactive. The API unit ordered itself after Docker but did not pull it in. These read-only observations identify the current reboot gap, not the reason Docker was disabled or the cause of earlier public failures. No service, DNS, payment, grant, or traffic state was changed.

Concrete todo:

- [x] Commit and preflight the synchronized plan, Issue #391, Project #8, and this document at an exact base SHA.
- [x] Test the preview-only drop-in for Docker pull-in and ordering without changing service command, environment, payment, or grants.
- [ ] Obtain independent exact-head review and required CI, and merge only under live branch protection.
- [ ] In a separately authorized host rollout, inventory Docker restart-policy blast radius, capture rollback state, install the exact reviewed drop-in, and verify the effective unit and endpoints.
- [ ] Retain a cold-boot acceptance receipt for local/public readiness, Workshop rendering, and purchase `enabled:false`; do not claim release completion from unit tests or warm probes.

The candidate is a source-controlled release artifact only. It is not installed on the live host by this task. Even after merge, Issue #391 remains open until an authorized rollout and cold-boot verification demonstrate durable user-facing recovery.

## Local candidate receipt

The planning checkpoint is `33ffd1ffbcd55da2d742960703b937d46595429d`; `scripts/autonomy/pre_implementation.py` returned `{"status":"synchronized","errors":[]}` at that exact base. Source/test milestone `236710376fe2ca72000a111606250a3596438f82` adds only `infra/deploy/preview/autodata-api-docker-dependency.conf` and `scripts/dev/test_preview_api_docker_dependency.py`.

The two focused tests first failed with the missing drop-in, then passed after the drop-in was added. `git diff --cached --check` passed. A temporary non-installed systemd fixture with byte-identical drop-in passed `systemd-analyze verify` using `SYSTEMD_UNIT_PATH`; debug output listed the fixture drop-in and a `docker.service/start` job in the API start transaction. The verifier also printed an unrelated existing `localdashboard.service` warning. These checks validate the candidate on this host, not live installation, container health, cold-boot durability, or paid access.
