# Preview automatic rewrite deployment verification

Status: planning only; no preview runtime deployment or authentic article/model probe under this gate.

Goal: Deploy the reviewed automatic permanent article rewrite to the existing purchase-disabled preview ingestion worker and verify one authentic selected article from each bank with exact rollback and no schema or API changes.

Plan: docs/superpowers/plans/2026-11-06-preview-automatic-rewrite-deployment.md. Record: docs/agents/records/2026-11-06-preview-automatic-rewrite-deployment.json. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. Planning parent36359d5e46d37387f210bc467971eef8eaa6857a.

Provisional source89b643336e47a9e2ecc9208a77552dd96d527e08 (implementation034708e8587abaf3e97cefa90cc47178f6cdfeb3, PR342) requires finalized exact-SHA review/CI before dispatch. Image sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4. Rollback target container3d9bd4410d2757e89db117847812a160d8d754d7d3cd3ec441bb57daa6aca2dc, autodata-ingestion-grant-ready-e4af862-writable. Do not substitute older read-only container or alter root/PR342.

Required evidence: synchronized full-SHA checkpoint; finalized source review/checks; private current backup and exact runtime diff; two authentic bank-bound stored-source selections with expected revisions; source readable while pending; automatic canonical content with truthful UNREVIEWED metadata and preserved protected facts; no manual approval dependency; committed permanent revisions; ten warm reads/ensures per bank with measured zero remote/model/schedule calls; exact request/model/time bounds; unchanged API/schema/business data; disabled purchase; retained exact rollback target. Specific inaccessible-source/model/access/queue/bound blockers remain explicit. Synthetic acceptance and database-only proof are separate from authentic reader proof.

Concrete todo:

- [ ] Synchronize this exact preview-only plan, verification document and concrete todos with Issue186 and Project8, commit/push the documentation checkpoint and pass full-SHA preflight before coordinator dispatch.
- [ ] Finalize review and checks for the exact pinned source, freeze the existing image/container/configuration and two authentic bank-scoped article selections, retain private backup and rollback evidence, and confirm purchase remains disabled.
- [ ] Replace only the preview ingestion source mount using the exact pinned existing image and reviewed source while preserving credentials/security/network/runtime settings, retain the original container, and run only the two selected article jobs sequentially within the probe bounds.
- [ ] Verify source fallback followed by automatic permanent canonical content with UNREVIEWED metadata, no manual review dependency and zero warm provider/model calls; report concrete blockers or execute exact runtime rollback on failure, preserving stored data and disabled commerce.

Tracking synchronized/read back at2026-11-06T07:54:11Z: Issue186 comment https://github.com/lucronn/autodata/issues/186#issuecomment-6680054946 exact body; Project8 itemPVTI_lAHOCSJ8cc4BiQ2BzhFocs4 Release hotfix reference prior prefix preserved and exact appended readback (field length523). No success, deployment, human approval, paid launch or full catalog coverage claimed.

Known deployment precondition: coordinator confirmed INCEPTION_API_KEY absent from the current preview worker and no approved env-file mount. Reviewed code may roll out with source fallback while this persists; authentic automatic canonical probes/publication claims remain blocked MODEL_KEY_MISSING until approved private secret delivery. No key is requested in chat. Record source-only and canonical outcomes separately; key absence alone does not force runtime rollback. Approved delivery may add only the model key to the replacement, preserving every other setting; model authentication failure remains explicit without manual retry.
