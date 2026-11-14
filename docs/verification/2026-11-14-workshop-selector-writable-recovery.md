# Workshop selector writable recovery verification

Goal: Diagnose and recover real Workshop selector persistence through a bounded identical-runtime replacement while preserving truthful provider completeness and disabled purchasing.

Issue https://github.com/lucronn/autodata/issues/401; Project https://github.com/users/lucronn/projects/8. Plan docs/superpowers/plans/2026-11-14-workshop-selector-writable-recovery.md; record docs/agents/records/2026-11-14-workshop-selector-writable-recovery.json.

Status: planning/read-only evidence only. No Docker/service mutation or provider call by this worker. The coordinator owns #391 origin recovery and any separately dispatched runtime execution.

Read-only evidence: public origin502 at2026-11-14T23:13Z; Docker inactive; API restart loop on DB5432 refused. Persisted serving ingestion efdda4a448db has read-only PGOPTIONS, host networking, read-only rootfs/source bind, cap-dropALL, no-new-privileges, and unless-stopped restart. Docker data-root is /mnt/openfoam/docker. Running transaction and specific #401 failure remain unverified until origin recovery. Existing catalog_service source SHA256 is5fef4cb075e2efc87067f68ae21d0110d3bf5c20dfc6b3ed5923224be17ed10a, differing from master diagnostics. No provider is blamed and no selector completion is claimed.

Concrete todo:

- [ ] Verify restored Docker/DB, exact serving ingestion/source/database identities, read-only transaction behavior, private backup and protected-table baseline before mutation.
- [ ] If the serving ingestion alone forces read-only transactions, retain the original and create an identical replacement with only PGOPTIONS removed; verify structural equality, health, and rollback-only writes.
- [ ] Observe one 2024 US makes scope through the existing bounded selector hydration path and read durable coverage/results; retain truthful partial state and safe error classes.
- [ ] Record exact runtime identities, redacted evidence and remaining catalog/article/paid-access gaps; synchronize Issue401/Project8 and keep rollback available.
