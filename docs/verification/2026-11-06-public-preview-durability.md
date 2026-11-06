# Public preview durability verification

Status: planning synchronized; runtime unchanged by this gate. Exact-checkpoint preflight and coordinator dispatch precede execution.

Goal: Make the existing purchase-disabled public preview restart-persistent using the exact e4af862 API binary and configuration, without rebooting or enabling payments.

Canonical plan: `docs/superpowers/plans/2026-11-06-public-preview-durability.md`. Record: `docs/agents/records/2026-11-06-public-preview-durability.json`. Source master parent `4513c387c900add7138330555ccfca92f74b9894`; serving product `e4af8621c12352e465ee28e87a67f78e67ab9091`.

Tracking: https://github.com/lucronn/autodata/issues/186; https://github.com/users/lucronn/projects/8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

Coordinator observation before planning: API unit autodata-api.service selects candidate e4af862 binary using volatile90 drop-ins under /run; config is api-public-preview.env owned corp:corp0600 beneath directory0700. Binary SHA256 d76aa21ccb4ec13556e5cd2f0ea2b78443c8805612244fa83dc92e65effa9246. Existing ingestion container autodata-ingestion-grant-ready-e4af862 serves127.0.0.1:3031 with restart policy no. Public readiness200, purchase enabled:false and quote200 USD2000. These are coordinator observations, not fresh restart evidence.

Required execution receipts: synchronized exact-checkpoint preflight errors=[]; source/copy hashes and protected permissions; persistent filesystem/config/mount inputs; effective99 override, enabled existing API/Docker units; unchanged ingestion container ID/config/mounts with unless-stopped; controlled ingestion/API restart exits and fresh readiness/purchase-disabled/quote checks; private rollback bytes and rollback outcome if exercised. No raw environment or credential values belong in repository evidence.

Concrete todo:

- [ ] Copy and hash-verify the exact serving API binary and configuration into persistent protected preview paths; preserve current values and secret-file access.
- [ ] Install a persistent 99-public-preview.conf API override and set only the existing grant-ready ingestion container restart policy to unless-stopped; retain rollback copies.
- [ ] Restart the existing ingestion container and API, verify exact runtime identity, readiness, disabled purchase configuration and USD2000 quote, and restore the prior state on failure.
- [ ] Record hashes, permissions, effective unit, restart policy, restart checks and rollback evidence; leave boot durability unverified until a separately authorized reboot.

No reboot has been performed or authorized by this plan. Successful service restarts do not prove boot durability. Payment enablement and product changes remain outside scope.

Tracking readback recorded at2026-11-06T02:27:23Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6675203960; Project8 item Release hotfix reference links that comment, status In Progress. Coordinator verified exact goal/todos/paths/SHAs, retained previous links and shortened descriptive labels. Full checkpoint SHA and validator evidence are sealed externally after commit; no self-hash is asserted.
