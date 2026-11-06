# Serving catalog writable runtime repair verification

Status: planning only; runtime replacement has not been dispatched under this gate.

Goal: Restore bounded dual-bank vehicle catalog hydration by replacing the serving grant-ready ingestion container with an identical writable runtime while retaining the exact original container for rollback and keeping purchase disabled.

Contract: docs/superpowers/plans/2026-11-06-serving-catalog-writable-runtime.md. Record: docs/agents/records/2026-11-06-serving-catalog-writable-runtime.json. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Planning parent4513c387c900add7138330555ccfca92f74b9894; source producte4af8621c12352e465ee28e87a67f78e67ab9091.

Read-only defect evidence: authenticated Bankone34 and Banktwo57 makes for2015, merged62; serving makes empty/hydrating; ingestion PGOPTIONS explicitly enables transaction read-only; a rollback-only scope INSERT raises ReadOnlySqlTransaction at catalog_service.py:1162. pg_settings source is client, pg_is_in_recovery false. This finding does not establish source/artifact tables are empty.

Required execution evidence: full-SHA synchronized preflight and coordinator dispatch; private original container inspect/configuration and database backup hashes; exact source/image/database identity; stopped retained original; sanitized replacement diff limited to name and removed PGOPTIONS; health; writable transaction rollback probe; bounded authentic per-bank configuration rows and provider mappings; committed rows read separately; nonempty public selector reads; request/deadline bounds; unchanged protected business and article lifecycle data; purchase remains disabled. Retain rollback evidence on any failure; never restore/delete serving data automatically.

Concrete todo:

- [ ] Synchronize this goal, plan, canonical verification document and four todos with Issue186 and Project8, commit/push the documentation checkpoint and pass full-SHA machine preflight before runtime dispatch.
- [ ] Freeze the original grant-ready container identity, source/image, private effective configuration and serving database identity; retain a private database backup and exact rollback procedure, and verify purchase remains disabled before replacement.
- [ ] Stop and retain the original container, create its controlled replacement with identical image/source/credentials/security/restart/network settings and only PGOPTIONS removed, then verify private health and writable database transactions before bounded selector hydration.
- [ ] Verify authentic Bankone and Banktwo selector results become durable and usable through the public catalog with purchase disabled, record exact counts/hashes and runtime differences, and roll back to the retained original container on failed verification without restoring or deleting serving database data.

Tracking synchronized/read back by coordinator at2026-11-06T07:43:12Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6679871493; Project8 itemPVTI_lAHOCSJ8cc4BiQ2BzhFocs4 Release hotfix reference retains prior history and exact gate link (field length975). No success, paid-browser readiness, article persistence or full catalog coverage is claimed.
