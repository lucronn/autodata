# Public preview durability implementation plan

> **For agentic workers:** Use superpowers:executing-plans after the synchronized checkpoint preflight passes and coordinator dispatches this exact scope.

**Goal:** Restore the purchase-disabled public preview after the observed host reboot and prepare restart persistence using the exact e4af862 API/configuration and saved grant-ready ingestion runtime, without another reboot or enabling payments.

**Architecture:** Reuse verified persistent API/configuration copies, recreate the lost same-name ingestion container from retained exact private launch inputs, and select the corrected persistent API drop-in. Verify recovery and restart configuration without another reboot.

**Tech Stack:** Existing Linux systemd and Docker; unchanged Go API binary.

**Spec:** `docs/verification/2026-11-06-public-preview-durability.md`.

**Planning parent:** `4513c387c900add7138330555ccfca92f74b9894` (docs-only master). Product remains `e4af8621c12352e465ee28e87a67f78e67ab9091`. The eventual committed planning checkpoint is the implementation preflight base; this parent cannot authorize new documents absent from it.

**Tracking:** https://github.com/lucronn/autodata/issues/186; https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`. Status: reboot-successor planning synchronized; recreation awaits a new exact-checkpoint preflight and dispatch.

## Global constraints

No source rebuild, product/configuration value change, migration, credentials/secret output, additional service/container identity, payment enablement or further reboot. Only recreation of the absent same-name grant-ready ingestion container is allowed. Preserve `enabled:false`, current merchant/recovery configuration, bind addresses and existing network/dependency wiring. This prepares restart persistence; actual boot durability requires separate reboot evidence.

## Exact scope

Planning paths: this plan, `docs/verification/2026-11-06-public-preview-durability.md`, `docs/agents/records/2026-11-06-public-preview-durability.json` only.

Runtime writes after dispatch only:
- `/opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api`: exact copy from `/home/corp/autodata-candidate/runtime-e4af862/bin/autodata-api`, root-owned executable0755 beneath root-owned0755 directories; SHA256 `d76aa21ccb4ec13556e5cd2f0ea2b78443c8805612244fa83dc92e65effa9246`.
- `/etc/autodata/preview/api-public-preview.env`: exact copy from `/home/corp/autodata-candidate/grant-ready-e4af862/api-public-preview.env`; parent root:corp0750, file corp:corp0600 so existing `User=corp` keeps access. Preserve source and reject a preexisting conflicting destination; do not print configuration contents.
- `/etc/systemd/system/autodata-api.service.d/99-public-preview.conf`: root:root0644; exact content below. Retain original unit/drop-ins and private rollback evidence.
- Recreate absent `autodata-ingestion-grant-ready-e4af862` from private `/home/corp/autodata-candidate/grant-ready-e4af862/launch-command.json` only, adding `--restart unless-stopped`. Verify saved argv/env/source/image against retained inspect evidence before executing. Required image ID `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`; private `/home/corp/autodata-candidate/grant-ready-e4af862/ingestion.env`0600 exact keys/values; bind `/home/corp/autodata-candidate/grant-ready-e4af862/source:/app:ro`; `--network host`, `--read-only`, `--cap-drop=ALL`, `--security-opt no-new-privileges`; workdir `/app/workers/ingestion-python`; command `python -m autodata_ingestion.http_service`. No other argv or configuration change. Stop if the named container already exists; never remove an unowned container.

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/env AUTODATA_API_ADDR=:18080 /opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api
EnvironmentFile=
EnvironmentFile=/etc/autodata/preview/api-public-preview.env
```

The `/usr/bin/env` assignment preserves the current working command semantics: it overrides the copied environment file's `AUTODATA_API_ADDR=127.0.0.1:3025` at exec time. A systemd `Environment=` assignment loses to `EnvironmentFile=` and caused the failed first attempt; do not use that form. Configuration bytes remain unchanged.

The existing `/etc/systemd/system/autodata-api.service` retains `User=corp`, `Restart=always`, `After=docker.service` and enabled boot selection. The observed host reboot removed the volatile90 drop-ins. The99 drop-in restores the prior preview command/environment semantics persistently; retain the actual post-reboot unit state for rollback. The coordinator retained the corrected drop-in privately at `/home/corp/autodata-evidence/durable-preview-20261106/99-public-preview.conf`; verify its bytes match the exact block above before installation.

## Concrete todo

- [ ] Verify surviving persistent API binary/configuration copies and the private saved ingestion argv, environment, source bind and exact image against retained pre-reboot evidence.
- [ ] Securely recreate only autodata-ingestion-grant-ready-e4af862 from the verified saved argv with --restart unless-stopped, then install the persistent corrected99 API override using /usr/bin/env AUTODATA_API_ADDR=:18080; retain rollback evidence.
- [ ] Start and verify ingestion/API runtime identities, security flags, readiness, disabled purchase configuration and USD2000 quote; restore pre-attempt API configuration and remove only this attempt's recreated container on failure.
- [ ] Record reboot observations, recreation/probe/rollback evidence and remaining boot-verification limits; perform no further reboot or payment enablement.

## Execution and verification

1. Privately snapshot the actual post-reboot API unit/drop-ins, enabled state and process identity; record endpoint success/failure honestly. Confirm the named ingestion container is absent. Verify surviving binary/config source/copy hashes and ownership/modes, exact local image ID, saved argv with no secret literals, private environment0600 byte/key/value equality against saved inspect, and read-only source identity against retained pre-reboot evidence. Inputs must be persistent; reject drift, missing inputs or changed security/network settings before writes. Do not require an already-working public baseline after this observed outage.
2. Parse the saved launch JSON as an argv list; require its initial executable/verb be the retained Docker `run` command, no `--rm` or existing restart option, and exact name/image/env/bind/security/workdir/command above. Execute with Python `subprocess.run(argv, check=True)`, inserting only `['--restart','unless-stopped']` immediately after the Docker executable and `run` verb. Never shell-evaluate JSON, print argv/env contents or read secrets into logs. Record the new container ID for ownership of this attempt. Inspect exact image, read-only source mount, security flags and restart policy; wait boundedly for existing readiness on127.0.0.1:3031.
3. Reuse only hash-matching persistent API/env copies; never overwrite a conflicting destination. Install the exact corrected99 drop-in, daemon-reload and inspect effective ExecStart/EnvironmentFiles. Verify API/Docker existing enabled state; stop for disposition if disabled. Restart API, verify active PID executable digest and intended :18080 listener, then require fresh local/public readiness200, purchase `enabled:false`, quote200 USD2000 and unchanged financial fingerprints. No checkout/payment objects. Retain UTC times, command exits and redacted observations.
4. On failure restore this attempt's saved post-reboot API drop-in state, daemon-reload and restart the prior API configuration. Stop/remove only the newly created container whose ID was recorded by this attempt; the pre-attempt state had no grant-ready container. Preserve binary/env/source/image/private launch inputs. Report the actual resulting endpoint state; rollback restores pre-attempt configuration and does not imply public availability.
5. Update canonical verification with exact identities, permissions, security/restart settings and recovery/probe/rollback results; commit/push the small docs evidence milestone. The observed reboot predates installation of the final persistent configuration and is failure evidence, not successful boot verification. Perform no additional reboot.

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

Reboot-successor tracking readback at 2026-11-06T07:34:29Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6679732670 contains the revised goal, four literal todos, three paths and same-name recreation/security limits. Project8 Release hotfix reference points to this comment, status In Progress; previous history remains in Issue and earlier Project links. Coordinator boolean-only argv audit confirms initial `["docker","run"]`, argc21, no `--rm` or `--restart`. No host mutation by this docs lane.
