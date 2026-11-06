# Public preview durability verification

Status: creation-failure correction planning synchronized; successor exact-checkpoint preflight and dispatch precede recreation.

Goal: Restore the purchase-disabled public preview after the observed host reboot and prepare restart persistence using the exact e4af862 API/configuration and saved grant-ready ingestion runtime, without another reboot or enabling payments.

Canonical plan: `docs/superpowers/plans/2026-11-06-public-preview-durability.md`. Record: `docs/agents/records/2026-11-06-public-preview-durability.json`. Source master parent `4513c387c900add7138330555ccfca92f74b9894`; serving product `e4af8621c12352e465ee28e87a67f78e67ab9091`.

Tracking: https://github.com/lucronn/autodata/issues/186; https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

Coordinator observation before planning: API unit autodata-api.service selects candidate e4af862 binary using volatile90 drop-ins under /run; config is api-public-preview.env owned corp:corp0600 beneath directory0700. Binary SHA256 d76aa21ccb4ec13556e5cd2f0ea2b78443c8805612244fa83dc92e65effa9246. Existing ingestion container autodata-ingestion-grant-ready-e4af862 serves127.0.0.1:3031 with restart policy no. Public readiness200, purchase enabled:false and quote200 USD2000. These are coordinator observations, not fresh restart evidence.

Required execution receipts: synchronized exact-checkpoint preflight errors=[]; source/copy hashes and protected permissions; persistent filesystem/config/mount inputs; effective99 override, enabled existing API/Docker units; new attempt-owned container ID with exact retained image/config/security/mounts and unless-stopped; ingestion recreation/start and API restart exits and fresh readiness/purchase-disabled/quote checks; private rollback bytes and rollback outcome if exercised. No raw environment or credential values belong in repository evidence.

Concrete todo:

- [ ] Verify surviving persistent API binary/configuration copies and the private saved ingestion argv, environment, source bind and exact image against retained pre-reboot evidence.
- [ ] Securely recreate only autodata-ingestion-grant-ready-e4af862 from the verified saved argv with --restart unless-stopped and an exclusive private --cidfile, capture and verify the attempt-owned container ID even on nonzero exit, then install the persistent corrected99 API override using /usr/bin/env AUTODATA_API_ADDR=:18080; retain rollback evidence.
- [ ] Start and verify ingestion/API runtime identities, security flags, readiness, disabled purchase configuration and USD2000 quote; restore pre-attempt API configuration and remove only this attempt's recreated container on failure.
- [ ] Record reboot observations, recreation/probe/rollback evidence and remaining boot-verification limits; perform no further reboot or payment enablement.

The host rebooted at2026-11-05 21:43 EST before this plan was merged. No further reboot is authorized. Successful process recovery does not prove boot durability of the successor configuration. Payment enablement and product changes remain outside scope.

Tracking readback recorded at2026-11-06T02:27:23Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6675203960; Project8 item Release hotfix reference links that comment, status In Progress. Coordinator verified exact goal/todos/paths/SHAs, retained previous links and shortened descriptive labels. Full checkpoint SHA and validator evidence are sealed externally after commit; no self-hash is asserted.

## First attempt and rollback — coordinator evidence

The first attempt used the original plan's bare API binary plus systemd `Environment=AUTODATA_API_ADDR=:18080`. The exact copied environment file contains `AUTODATA_API_ADDR=127.0.0.1:3025`; systemd EnvironmentFile precedence replaced the intended address, and the API failed with a bind collision. This was a plan error; successful durability is not claimed.

Coordinator immediately removed the new99 drop-in, daemon-reloaded, restored the existing ingestion container restart policy to `no`, and restarted the prior API. Coordinator observed public readiness200, purchase configuration still disabled and unchanged financial fingerprints after rollback. These are coordinator-reported rollback observations; this docs lane did not execute or independently repeat runtime checks.

The corrected exact command is `ExecStart=/usr/bin/env AUTODATA_API_ADDR=:18080 /opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api`; remove the systemd `Environment=` line. This preserves the working command's exec-time address override while leaving copied environment bytes unchanged. Retry and boot durability remain unverified.

Correction synchronized by coordinator at 2026-11-06T02:31:28Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6675258622; Project8 preserves prior gate/checkpoint links and appends this correction, status In Progress, descriptive labels shortened only. A successor committed checkpoint and its exact-head preflight are required before retry.

## Observed reboot and narrow recreation successor

Coordinator reports host reboot at2026-11-05 21:43 EST (2026-11-06T02:43:00Z) before merge. Volatile API overrides vanished and autodata-ingestion-grant-ready-e4af862 no longer exists. Persistent exact API binary/env copies survive. This event does not verify the uninstalled persistent99 configuration.

Restore audit retained private ingestion.env0600 with every key/value matching saved inspect, launch-command.json with complete original argv and no secret literals, source:/app:ro and exact local image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4. The plan now permits only same-name secure recreation by parsed subprocess argv with --restart unless-stopped and an exclusive private --cidfile inserted; host networking, read-only root/source, cap-drop ALL and no-new-privileges remain required. Existing container-ID preservation is impossible and superseded by recording the attempt-owned recreated ID. No recreation, successful recovery or boot durability is claimed by this docs update.

Reboot-successor synchronized/read back at 2026-11-06T07:34:29Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6679732670; Project8 latest reference/status verified by coordinator. Saved argv audit: starts docker run, argc21, no --rm or --restart, so adding restart unless-stopped is compatible. No runtime action by this docs lane.

## Creation-failure rollback correction

Independent exact-head review identified that Docker may create the named container and return nonzero before stdout supplies its ID. The successor plan adds a fresh exclusive private cidfile alongside restart unless-stopped, reads/verifies its ID even on nonzero and verifies the attempt's creation time/name/image/config/security/mounts. If cidfile is absent, exact-name inspection must establish pre-attempt absence and matching creation time/image/config before cleanup. Ambiguous ownership stops/escalates; only a verified attempt-owned ID may be removed. This is a planning correction, not an exercised runtime-failure or cleanup receipt.

Creation-failure correction synchronized/read back by coordinator at 2026-11-06T07:37:07Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6679758175; Project8 Release hotfix reference contains correction link, field length997. Successor exact-head preflight is required before runtime.

## Coordinator runtime recovery receipt

The docs-only successor checkpoint `ce3c2490209974b4aad5ff96930c06c1751e2e8d` passed exact-head preflight (`status: synchronized`, `errors: []`) and independent review before the coordinator attempted host recovery. The surviving API binary, API environment file and private ingestion environment file matched their pinned SHA-256 digests. The named container was absent; the saved local image, argv, source bind and retained inspect security settings matched the narrow plan. Docker and the existing API service were enabled.

At 2026-11-06T07:38Z the coordinator recreated `autodata-ingestion-grant-ready-e4af862` from the saved argv with only `--restart unless-stopped` and an exclusive cidfile added. The attempt's private0700 directory is `/home/corp/autodata-evidence/durable-preview-20261106/attempt-1fehjd5i`; cidfile ID `de98e97b33f00d5c38fa85aa2143123ebbe2aa30755a247e648b141e9a657a89` was independently verified by exact name, image digest, creation window, read-only root and `/app` source bind, host networking, ALL capability drop, no-new-privileges and restart policy. A coordinator-side assertion initially assumed the cidfile itself had mode0600/0644; Docker created it as0664 within the private0700 directory. The assertion stopped before API changes; the coordinator recovered and verified the attempt-owned ID, so no second container was created. Ingestion `/healthz` then returned200 on loopback3031.

The coordinator installed the byte-exact corrected root-owned0644 persistent99 drop-in, SHA-256 `7c5c885dd90066bb71bda580f51a375be3d8b2c74859abc15a8b0e9e3f42c376`, daemon-reloaded and restarted `autodata-api.service` successfully. Effective service state is active with the99 drop-in, `/usr/bin/env AUTODATA_API_ADDR=:18080`, and process executable `/opt/autodata/preview/e4af8621c12352e465ee28e87a67f78e67ab9091/autodata-api` at pinned SHA-256 `d76aa21ccb4ec13556e5cd2f0ea2b78443c8805612244fa83dc92e65effa9246`. Local readiness returned200. After transient upstream errors during restart, public `https://autodata.cars.tk/readyz` and `/workshop/purchase-config.json` returned200; purchase `enabled:false`, and `/workshop` followed its308 canonical redirect to200. Public catalog years returned items. The 2015 make index was still `items:[]`, `complete:false`, `hydrating:true`; source/article acceptance remains pending. Financial serving-table row counts remained workshop_orders0, payment_events2, entitlements1 after recovery; payment was not enabled. No quote200 evidence or boot-survival claim is made here. No further reboot was performed.
