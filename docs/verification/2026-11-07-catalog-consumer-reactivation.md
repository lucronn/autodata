# Catalog Consumer Reactivation

Status: synchronized planning; no runtime action authorized until exact release binding, independent script review and coordinator dispatch.

 Activate and retain the existing catalog-only consumer on the merged PR366 source after its HTTP rollout, so ordinary new configuration index jobs progress without article/model or paid-grant bypass.


Plan `docs/superpowers/plans/2026-11-07-catalog-consumer-reactivation.md`; record `docs/agents/records/2026-11-07-catalog-consumer-reactivation.json`.

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
