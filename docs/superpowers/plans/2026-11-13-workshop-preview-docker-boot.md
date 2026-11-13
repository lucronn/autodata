# Workshop preview Docker boot dependency

**Goal:** Prevent the purchase-disabled Workshop preview API from starting before its Docker-hosted PostgreSQL dependency after a host reboot.

**Tracking:** [Issue #391](https://github.com/lucronn/autodata/issues/391); [Project #8](https://github.com/users/lucronn/projects/8), item `PVTI_lAHOCSJ8cc4BiQ2BzhHfSQM`.

**Canonical verification:** `docs/verification/2026-11-13-workshop-preview-docker-boot.md`.

**Base:** `85a0fd7dbf2af894f0beadbeb6dd409a5941af2d` (master before this planning checkpoint). The committed planning checkpoint SHA, not this parent, is the implementation preflight base.

## Evidence and boundary

At 2026-11-13 16:29:40 EST the origin host rebooted. At 16:33, `autodata-api.service` was enabled and restarting because PostgreSQL on `127.0.0.1:5432` refused connections; `docker.service` was disabled and inactive. Public `/readyz` returned 502. The API unit has `After=docker.service` but no `Wants=` or `Requires=` pull-in, so ordering does not start Docker. This establishes the current reboot outage, not the cause of earlier 502/530 episodes or why Docker was disabled. Do not infer a successful live recovery from local unit tests.

## Design

Version one small preview-only systemd drop-in at `infra/deploy/preview/autodata-api-docker-dependency.conf` with `Requires=docker.service` and `After=docker.service`. The existing enabled API unit will then pull Docker into the same boot transaction. Its existing `Restart=always` handles the short interval before the Docker-managed PostgreSQL container is healthy. Do not edit the API executable, Docker unit, payment configuration, grants, DNS, tunnel, or traffic. Do not install the drop-in or start/enable any host service in this code task.

`Requires=` is intentionally stronger than `Wants=`: an API that cannot reach its required database must not appear started when Docker itself failed. The drop-in is independent of the existing `99-public-preview.conf` command and environment override. A separate authorized release step must inventory the Docker containers and restart policies before applying any runtime change; starting Docker can bring up more than the Workshop database.

## Concrete todo

- [ ] Synchronize this plan, Issue #391, Project #8, the canonical verification document, and a committed exact-base preflight record.
- [ ] Add a failing structural test for the preview API drop-in: Docker pull-in and ordering are present, and no service command, environment, checkout, or grant setting is changed.
- [ ] Add only the preview API Docker dependency drop-in, then pass the focused test, systemd syntax verification, and `git diff --check`.
- [ ] Obtain an independent exact-head review and required PR CI; merge only if live branch protection and the review gates pass.
- [ ] Keep host installation/restart/enabling and reboot acceptance as separate release work. Record exact before/after unit and container identities, rollback, local/public `/readyz`, `/workshop/`, and literal purchase `enabled:false` only when separately authorized and executed.

## Test and rollout boundaries

The structural test should load the committed drop-in from disk and reject missing Docker `Requires=` or `After=`, or any `[Service]` and payment/grant directive. Verify the candidate with `systemd-analyze verify` against a temporary unit fixture, without touching `/etc/systemd/system`. Run the relevant repository tests/CI. A passing test proves only the candidate bytes and syntax, not live boot durability.

For a later host rollout, capture the preexisting base unit and all drop-ins, `systemctl is-enabled` state, Docker container names/restart policies, and API/database health without printing secrets. Install only the reviewed drop-in with root ownership, `daemon-reload`, and inspect the effective `Requires=`/`After=`. The rollback removes only this new drop-in and reloads systemd, preserving the existing `99-public-preview.conf`. Do not reboot as part of this implementation. Any service start/restart, Docker enablement, or reboot requires its own scope decision and acceptance receipt.

## Gate

After Issue and Project synchronization, commit the plan, verification document, and `docs/agents/records/2026-11-13-workshop-preview-docker-boot.json` as a planning-only checkpoint. Pin its full SHA, then run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-13-workshop-preview-docker-boot.json --base-sha CHECKPOINT_SHA --repo-root .
```

Only `errors: []` at the actual committed checkpoint permits implementation-file edits. No production authority is conferred by this preflight.
