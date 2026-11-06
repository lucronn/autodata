# Public preview durability implementation plan

> **For agentic workers:** Use superpowers:executing-plans after the synchronized checkpoint preflight passes and coordinator dispatches this exact scope.

**Goal:** Make the existing purchase-disabled public preview restart-persistent using the exact e4af862 API binary and configuration, without rebooting or enabling payments.

**Architecture:** Copy the current binary and environment bytes to persistent protected paths and select them with one persistent systemd drop-in. Add the existing ingestion container's restart policy and verify reversible process restarts.

**Tech Stack:** Existing Linux systemd and Docker; unchanged Go API binary.

**Spec:** `docs/verification/2026-11-06-public-preview-durability.md`.

**Planning parent:** `4513c387c900add7138330555ccfca92f74b9894` (docs-only master). Product remains `e4af8621c12352e465ee28e87a67f78e67ab9091`. The eventual committed planning checkpoint is the implementation preflight base; this parent cannot authorize new documents absent from it.

**Tracking:** https://github.com/lucronn/autodata/issues/186; https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Status: correction planning synchronized; runtime retry awaits corrected exact-checkpoint preflight and coordinator dispatch.

## Global constraints

No source rebuild, product/configuration value change, migration, credentials/secret output, new service/container, payment enablement or reboot. Preserve `enabled:false`, current merchant/recovery configuration, bind addresses and existing network/dependency wiring. This prepares restart persistence; actual boot durability requires separate reboot evidence.

## Exact scope

Planning paths: this plan, `docs/verification/2026-11-06-public-preview-durability.md`, `docs/agents/records/2026-11-06-public-preview-durability.json` only.

Runtime writes after dispatch only:
- `/opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api`: exact copy from `/home/corp/autodata-candidate/runtime-e4af862/bin/autodata-api`, root-owned executable0755 beneath root-owned0755 directories; SHA256 `d76aa21ccb4ec13556e5cd2f0ea2b78443c8805612244fa83dc92e65effa9246`.
- `/etc/autodata/preview/api-public-preview.env`: exact copy from `/home/corp/autodata-candidate/grant-ready-e4af862/api-public-preview.env`; parent root:corp0750, file corp:corp0600 so existing `User=corp` keeps access. Preserve source and reject a preexisting conflicting destination; do not print configuration contents.
- `/etc/systemd/system/autodata-api.service.d/99-public-preview.conf`: root:root0644; exact content below. Retain original unit/drop-ins and private rollback evidence.
- Existing container `autodata-ingestion-grant-ready-e4af862`: only restart-policy change from `no` to `unless-stopped` and one controlled restart. Do not recreate it or change its configuration/mounts.

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/env AUTODATA_API_ADDR=:18080 /opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api
EnvironmentFile=
EnvironmentFile=/etc/autodata/preview/api-public-preview.env
```

The `/usr/bin/env` assignment preserves the current working command semantics: it overrides the copied environment file's `AUTODATA_API_ADDR=127.0.0.1:3025` at exec time. A systemd `Environment=` assignment loses to `EnvironmentFile=` and caused the failed first attempt; do not use that form. Configuration bytes remain unchanged.

The existing `/etc/systemd/system/autodata-api.service` retains `User=corp`, `Restart=always`, `After=docker.service` and enabled boot selection. The 99 drop-in sorts after both observed `/run/systemd/system/autodata-api.service.d/90-e4af862-preview*.conf`; they remain intact for rollback. Both observed90 drop-ins reset EnvironmentFile before selecting the single grant-ready environment file; the99 reset preserves those effective inputs.

## Concrete todo

- [ ] Copy and hash-verify the exact serving API binary and configuration into persistent protected preview paths; preserve current values and secret-file access.
- [ ] Install a persistent 99-public-preview.conf API override and set only the existing grant-ready ingestion container restart policy to unless-stopped; retain rollback copies.
- [ ] Restart the existing ingestion container and API, verify exact runtime identity, readiness, disabled purchase configuration and USD2000 quote, and restore the prior state on failure.
- [ ] Record hashes, permissions, effective unit, restart policy, restart checks and rollback evidence; leave boot durability unverified until a separately authorized reboot.

## Execution and verification

1. Before mutations, privately snapshot unit/drop-in bytes, effective properties, unit enabled state, binary/config hashes and permissions, current API process identity, container ID/mounts/config hash/restart policy, and successful local/public readiness, purchase-config and quote responses. Verify the exact hash above and existing ingestion container identity. Confirm config/mount inputs are on persistent filesystems and no required external input is under `/run` or `/tmp`; if not, stop for scope review rather than claiming durability.
2. Copy files without changing bytes, verify source/destination hashes and paths/ownership/modes, atomically install the drop-in, `systemctl daemon-reload`, and inspect effective ExecStart/EnvironmentFiles/address. Verify `systemctl is-enabled autodata-api.service` and `docker.service`; if disabled, stop for coordinator disposition because new boot enablement is outside this scope. Set `docker update --restart unless-stopped autodata-ingestion-grant-ready-e4af862` and inspect the exact resulting policy.
3. Run `docker restart autodata-ingestion-grant-ready-e4af862`, wait boundedly for its existing readiness on127.0.0.1:3031, then `systemctl restart autodata-api.service`. Verify active PID `/proc/PID/exe` digest equals the exact binary, protected env path is effective, container ID/config/mounts unchanged and policy remains unless-stopped. Re-run prior local/public endpoint checks with fresh responses: readiness200; purchase `enabled:false`; quote200, USD2000. Do not create checkout/payment objects. Retain command exit statuses, UTC timestamps and redacted observations.
4. On any failure, restore only this task's prior drop-in state (remove newly created99 file or restore its saved bytes), daemon-reload, restore container policy `no`, restart the previous processes in dependency order, and re-run baseline checks. Keep source binary/env and both90 drop-ins intact throughout. Record rollback result honestly; no successful recovery claim without endpoint proof.
5. Update canonical verification with exact hashes, effective unit/policy and restart results; commit/push the small docs evidence milestone. Report restart persistence prepared, actual reboot untested. No host reboot follows from this gate.

## Gate command

After coordinator tracking readback, set the record status synchronized, commit/push exactly the three planning paths, externally pin that full checkpoint SHA, then run:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-06-public-preview-durability.json --base-sha CHECKPOINT_SHA --repo-root .
git diff --check
```

`CHECKPOINT_SHA` is the external full SHA of the resulting checkpoint, never the earlier master parent. Require validator errors=[] before dispatch. No implementation or runtime mutation is performed by this planning lane.

## Coordinator tracking readback

Coordinator verified https://github.com/lucronn/autodata/issues/186#issuecomment-6675203960 contains the exact goal, four literal todos, three planning paths and parent/product SHAs. Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` Release hotfix reference links that comment, status In Progress; previous links preserved and descriptive labels shortened. Recorded at2026-11-06T02:27:23Z. This lane performed no GitHub Issue/Project writes or runtime mutations.

Correction tracking readback at 2026-11-06T02:31:28Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6675258622 records the failed attempt/rollback, corrected exact ExecStart and successor checkpoint requirement. Coordinator verified Project8 retains prior gate/checkpoint links and appends the correction comment, status In Progress; only descriptive labels shortened. No runtime retry is claimed.
