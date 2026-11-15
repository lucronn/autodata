# Workshop preview source release

Goal: Publish exact current Workshop source as a purchase-disabled public preview while preserving runtime dependencies and a verified binary rollback.

Issue: https://github.com/lucronn/autodata/issues/410
Project: https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhIzTRQ`.
Canonical receipt: `docs/verification/2026-11-14-workshop-preview-source-release.md`.
Record: `docs/agents/records/2026-11-14-workshop-preview-source-release.json`.

## Exact scope and compatibility

The product source is frozen at `c115dcde11bee0ecc64052e8d51d15de7e572da9`. Build a fresh git archive of this SHA, not the dirty legacy checkout. The successor checkpoint adds only release documentation; application bytes stay at this pin. The previous API is `/usr/local/libexec/autodata/selector-ui-cad924e-r1/autodata-api`, SHA256 `ca04cfc7777b1a3a58aeae7dd50f01f273e0b86223c530296eefff3c7619b3d0`. Its persistent selector override is `/etc/systemd/system/autodata-api.service.d/99-public-preview.conf`, SHA256 `c935a033cb755774f39b9121bac79f59a9b5c9da1298352a251676c443c21835`. Preserve a private byte copy before mutation.

The source delta from cad924e touches API authentication timing, commerce route support and embedded Workshop assets; there are no migration changes. New demo-mode presentation is independently guarded and rejects cars.tk/autodata.cars.tk. Existing disabled commerce authority and unchanged environment stay authoritative. Run all API/shared-contract Go tests and both Workshop Node suites; compile with local Go1.26.4, CGO_ENABLED=0 and -trimpath from the exact archive. Retain go version/build metadata, archive/binary/embedded-asset hashes and complete test logs in private evidence. Do not make application changes under this release gate.

The API environment file `/etc/autodata/preview/api-public-preview.env` currently hashes to `3c0a5d519fb055d6ef87b421abbe9dc731e20250c86606fb2987822442c7bac1`; do not disclose or copy its contents into repository evidence. Re-check hash and effective ExecStart immediately before rollout; a drift requires coordinator review. Keep port18080, environment file, database, ingestion3031, NATS, object storage, proxy and Docker dependency drop-in unchanged. No ingestion/schema/service dependency redesign, DNS, grants, secrets, checkout attempt or purchase enablement.

## Bounded coordinator rollout and rollback

After test success and exact-checkpoint preflight/readback, coordinator alone installs the hash-verified binary root-owned0755 at `/usr/local/libexec/autodata/workshop-preview-c115dcde-r1/autodata-api` (directory root-owned0755, destination previously absent). Preserve the old binary. Capture effective service identity, existing override bytes and hashes, private ingestion health, local/public readiness and purchase disabled; missing or unhealthy baseline blocks the switch.

Replace only the binary path in existing99 override, retaining exactly `/usr/bin/env AUTODATA_API_ADDR=:18080` and its existing EnvironmentFile reset/file lines. Atomic root-owned0644 override installation, daemon-reload and one API restart are allowed to coordinator. No worker/container restart, boot/reboot or dependency changes. Confirm `/proc/<MainPID>/exe` and binary hash equal the new artifact.

Use sequential bodyless GET, no redirects, verified public TLS and `User-Agent: curl/8.0.0`: local18080 `/readyz`, private3031 `/healthz`, public `https://autodata.cars.tk/readyz`, `/workshop/`, `/workshop/purchase-config.json`, `/workshop/demo-mode.json`, and embedded `/workshop/app.mjs`, `/workshop/commerce.mjs`, `/workshop/bootstrap.mjs`, `/workshop/index.html` (index uses `/workshop/`). Confirm runtime readiness200, Workshop200, purchase enabled:false and demo enabled:false, exact asset bytes, no public JS error and no horizontal overflow at390x844. Existing apex cars.tk Workshop redirect must remain unchanged; no apex readiness claim. Poll readiness/config convergence at most10 rounds over30seconds, requests bounded by2seconds and response capture16KiB (assets may be hash-streamed at most1MiB). No sign-in, account/session/customer, paid article, ensure, model/provider or payment endpoint calls.

On install/restart/identity/probe failure, restore byte-exact saved99 override, daemon-reload and restart the API once; verify old executable hash, local/public readiness, purchase disabled and private ingestion health with the same bounds. Preserve failed receipts. If rollback fails, retain artifacts and escalate to coordinator; no alternate artifact, retry release, config change or extra runtime scope follows. Binary artifact preparation alone is not a deployment or paid-release receipt.

## Concrete todo

- [ ] Pin the current source, compatibility findings, unchanged runtime configuration, previous binary and rollback drop-in.
- [ ] Synchronize and commit this plan, Issue, Project #8 and canonical receipt; pass exact-checkpoint machine preflight.
- [ ] Build the pinned API source and run API/shared-contract and Workshop regression tests; retain hashes and logs.
- [ ] Hand the verified artifact and bounded rollout/rollback to the coordinator; coordinator alone switches the API binary after gate readback.
- [ ] Verify public/local readiness, exact embedded assets and disabled purchase configuration; record final runtime identity and any rollback.
