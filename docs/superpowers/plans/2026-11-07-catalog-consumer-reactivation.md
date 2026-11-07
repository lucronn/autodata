# Catalog Consumer Reactivation Implementation Plan

> **For agentic workers:** Use the executing-plans workflow for this single bounded runtime task.

**Goal:** Activate and retain the existing catalog-only consumer on the merged PR366 source after its HTTP rollout, so ordinary new configuration index jobs progress without article/model or paid-grant bypass.

**Architecture:** Reuse the installed static catalog-only service, pinned image and unchanged root-protected 14-name environment. Advance its source pointer to the same immutable merged source as the repaired HTTP process; start once and retain running only after bounded acceptance.

**Tech Stack:** systemd, Docker, Python, existing PostgreSQL catalog worker.

**Spec:** `docs/verification/2026-11-07-catalog-consumer-reactivation.md`

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8.

## Concrete todo record

- [ ] Bind the exact merged PR366 source/tree/archive and successful HTTP rollout receipt, passing CI and unchanged installed catalog unit/environment in a release checkpoint.
- [ ] Review and mock-test a private one-start operator with exact 14-name env validation, allowing only empty inherited sensitive names and rejecting any sensitive value.
- [ ] After exact synchronized gate/preflight and coordinator dispatch, atomically advance only the stopped catalog source config, start once, and retain running after bounded singleton/security/health acceptance.
- [ ] On failure or interruption stop within independent recovery budget, restore original stopped source config, preserve job history, and append truthful outcome evidence.

## Scope and exact dependencies

This is NEW authority; both starts and ensures under the November 6 activation are consumed and remain historical. No old operator rerun. Execution is blocked until PR366 is merged with required CI success and the coordinator's HTTP rollout receipt proves that exact merged source is live. A release checkpoint must pin full merged source SHA/tree/archive digest, immutable root-owned source path, exact gate SHA/record hash, new HTTP container ID and successful rollout receipt hash. Candidate PR head is never executable authority.

Existing unit `/etc/systemd/system/autodata-catalog-index-worker.service` must equal the merged unit SHA256 `91ddccea1aac8d5ad0957ab868f42b0c39c65ce6f0b3c0a5539bd72879b6951d`; no unit/dropin/image/security/boot change. Image `sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4`. Only `/etc/autodata/catalog-index-worker.conf` may be atomically advanced, after snapshotting exact old bytes privately, to `AUTODATA_CATALOG_INDEX_SOURCE=<new immutable source>`. Reuse coordinator source artifact; do not edit it, create another source, install dependencies, reset-failed, restart API/HTTP/article service, or change env. Static unit stays unenabled and Restart=no.

Catalog env `/etc/autodata/catalog-index-runtime.env` remains root0600 and contains exactly these 14 unique names with nonempty values preserved: AUTODATA_DB_ADDRESS, AUTODATA_POSTGRES_DB, AUTODATA_POSTGRES_USER, AUTODATA_POSTGRES_PASSWORD, AUTODATA_S3_ENDPOINT, AUTODATA_S3_ACCESS_KEY, AUTODATA_S3_SECRET_KEY, AUTODATA_SOURCE_BUCKET, BANKONE_BASE_URL, AUTODATA_BANKONE_API_KEY, BANKTWO_BASE_URL, AUTODATA_BANKTWO_API_KEY, PYTHONDONTWRITEBYTECODE, PYTHONPATH. Explicit valid S3 HTTP(S) URL, Python1 and fixed /app source/contracts path required. Container effective env must preserve every selected value. Image-inherited sensitive names with EMPTY values are allowed; nonempty internal token, model/API key or payment/admin credential outside this allowlist is forbidden. Never print env values or copy HTTP internal token. Compare image env plus explicit env to exact effective container env, rejecting extras/duplicates.

Existing article worker is active independently and MUST remain the identical container/payload/service configuration. It may progress authorized article work, so blanket article-table equality is not valid acceptance. Prove catalog command selects only eligible catalog_index jobs and passes model_client=None by exact merged wrapper hash and existing tests; inspect catalog container security, source, command/env and service singleton. No new article worker or article jobs, body/model calls, paid grants/session minting, checkout enabling, source refresh/reset, retry/max-attempt/lease mutation, database manual edits, migrations, ensures or proof jobs. Catalog processing may naturally add descriptors/source snapshots and complete eligible queued jobs. Existing completed/needs_review/dead_letter jobs must never be replayed. Idle consumer acceptance does not claim new article completion or paid browse.

## Operator and acceptance

Private operator/evidence under `/home/corp/autodata-evidence/catalog-consumer-reactivation-draft` and a fresh root0700 run directory. Before any runtime action require independent exact-script SHA review, root0600 immutable dispatch binding merged source/gate/record/rollout receipt/script review, expires <=300s, and exclusive attempt receipt. Root isolated Python, subprocess hard timeouts and isolated env, signal handlers route interruption through BaseException recovery. Mock tests cover wrong/duplicate env, inherited empty internal token, nonempty forbidden token/model key, wrong source/mount/security, early startup absence versus deadline, interruption after config write/start, and success retaining only exact catalog worker. No execution by preparation agent.

Preflight <=120s: verify clean pushed gate, exact source tree/archive + root ownership/no write bits and no extra files, unit/config/env modes/hashes, catalog stopped/no existing catalog container, no dropins/boot enablement, current active HTTP/API/article identities and health, public ready200/purchase.enabledfalse. Snapshot only safe catalog job status/counts and source config bytes privately. Reuse current source connector values and no repairs. Config update is atomic root0600; after it set mutation flag BEFORE start request; exclusive start-sent receipt and at most one systemctl start. Startup grace <=10s inside 60s observation; poll <=250ms, absence allowed only during grace, wrong/multiple identity fails immediately. Require at least 30s stable active catalog container and repeated unchanged exact payload/env/security, HTTP/public health, purchase disabled, unchanged existing article container/service payload. Inspect catalog status counts without claiming old descriptors as new work. On success retain service active/static and write truthful receipt, with paid browse UNVERIFIED. No boot enablement or automatic restart is authorized.

On any failure/interruption after config mutation, use independent stop<=80s and stopped/no-container verification<=15s; atomically restore exact old config bytes only after stopped proof. Never restart old catalog source, retry start, kill/recreate containers, revert DB or erase receipts/history. Capture recovery result even if stop/config restore fails; no success claim. New run cannot auto-repeat uncertain attempt.

## Verification and delivery

Planning-only checkpoint touches this plan, canonical verification and record. After synchronization/push/preflight, private operator mocks and independent review follow. Release checkpoint pins source and runtime receipt before coordinator dispatch. Append Issue186 and dedicated Project8 field preserving all prior history; commit/push outcome docs after actual dispatch.

Tracking readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6701723426 and dedicated Project8 field `Catalog consumer reactivation reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho6jS8`), item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`.

## Post-merge release checkpoint (no runtime action)

This branch descends from merged PR366 product `c9c58fcd74e67c07d7014497a6f7433f79cf2ae3`, whose tree `8e8221aac6577429da8877434679bcd573f8c3e8` exactly equals reviewed/CI-passing head `c94a27047ba5af8bcd45751aa1e63ccdb552c899`. Required verification passed at https://github.com/lucronn/autodata/actions/runs/42335140107. Source/receipt identities and private configuration hashes are pinned below. This checkpoint permits preparation/review only; runtime still requires independent exact-script+binding review and separate coordinator dispatch.

The merged product deterministic git archive digest differs from candidate archive because tar embeds commit metadata. Validate the immutable equal-tree export by merged archive file manifest and exact root-owned read-only files; do not claim the archive bytes are identical. The operator binds merged archive digest and merged product SHA while reusing the equal-tree candidate source path.

```json
{
  "product_source_sha": "c9c58fcd74e67c07d7014497a6f7433f79cf2ae3",
  "product_tree_sha": "8e8221aac6577429da8877434679bcd573f8c3e8",
  "merged_archive_sha256": "bac2e3c74dbe316a5f41553a6fe6c515b12c0e2d5b6f477307d367c8c70755a6",
  "candidate_export_sha": "c94a27047ba5af8bcd45751aa1e63ccdb552c899",
  "candidate_archive_sha256": "7a6e415ad6375922b0cec8765cdae8a61985430b81f69136a8a54598a169356f",
  "immutable_source": "/home/corp/autodata-evidence/catalog-absence-artifacts/c94a27047ba5af8bcd45751aa1e63ccdb552c899/source",
  "required_ci": "https://github.com/lucronn/autodata/actions/runs/42335140107",
  "rollout_receipt": "/home/corp/autodata-evidence/catalog-absence-release-run-c9c58fc-r1-20261107T035938Z/receipt.json",
  "rollout_receipt_sha256": "7cd555ef55d169fa5bd10c56521b540afe85f7f98673b6c57073a56783b23a4c",
  "http_id": "341116a440ee68a605f1d3d8660476a94ff65adfe90d7d887f20acb71d411355",
  "http_payload_sha256": "b86afb85e16709204b1fa5e2893f77f632949823d6f133c0451479bba0e676e2",
  "article_id": "f5f91096e8943a5340074f2838cab6a05c9e24a323375de4d3d0d57a3169270c",
  "article_payload_sha256": "28112836b32789534c7043cccbccbdcc60d4aabe558f638e89318c1cfb280fa0",
  "old_conf_sha256": "e7425e4553e01dc3106223e46b22b19c7894459922cc7bdcda6ad80bea9ad6a3",
  "env_sha256": "3e1f9aa46ac20bcf1cf3c16099307a7fde193c935fd7353c847aa826e17b63b7",
  "operator_sha256": "3e81a72224a2deb8a9bb7ea1e79898e28a9500a858bba3433f91ebd9efbcbe56"
}
```

The HTTP rollout receipt was read back with status passed and exact product_sha/product_tree/replacement_id above. Existing HTTP and article containers were independently inspected running; payload fingerprints cover Id/Image/Config/HostConfig/Mounts without exposing env values. No config/env/service/container/DB was changed. Independent final operator review remains pending. Twenty-four mocked tests passed; no operator execution or approval/dispatch created.

Release tracking readback verified: https://github.com/lucronn/autodata/issues/186#issuecomment-6701984970 and Project8 dedicated field `Catalog consumer reactivation reference` (`PVTF_lAHOCSJ8cc4BiQ2Bzho6jS8`). Todo: exact committed/pushed preflight; independent binding review; later coordinator dispatch one start/retain or stop+restore; truthful outcome sync.
