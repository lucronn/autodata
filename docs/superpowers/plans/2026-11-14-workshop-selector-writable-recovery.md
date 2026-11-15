# Bounded Workshop selector writable-runtime recovery

Goal: Diagnose and recover real Workshop selector persistence through a bounded identical-runtime replacement while preserving truthful provider completeness and disabled purchasing.

Issue: https://github.com/lucronn/autodata/issues/401
Project: https://github.com/users/lucronn/projects/8
Canonical receipt: docs/verification/2026-11-14-workshop-selector-writable-recovery.md
Record: docs/agents/records/2026-11-14-workshop-selector-writable-recovery.json
Source checkpoint: 61f1939c04b41cf6082c3361f34424e0cd9c599e. No application code or schema change is planned. The coordinator owns all Docker and service mutations; this worker prepares planning and read-only evidence.

## Evidence before dispatch

On 2026-11-14 23:13 UTC the public selector returned Cloudflare502; Docker was inactive and API startup failed connecting to loopback5432. Origin recovery is separately owned under #391. Persisted Docker metadata identifies serving ingestion efdda4a448db at 127.0.0.1:3031, source mount /home/corp/autodata-candidate/grant-ready-e4af862/source, DB127.0.0.1:5432, and PGOPTIONS=-c default_transaction_read_only=on. This configuration suggests a persistence failure but is not proof of a running transaction or the full #401 cause. daemon.json selects /mnt/openfoam/docker; the historically documented writable replacement is absent. The serving source predates #405 stage diagnostics.

## Decision-complete execution

1. Wait for coordinator's #391 restoration and verify ingestion3031 and DB5432 identities without exposing credentials. Read both default_transaction_read_only and transaction_read_only plus pg_is_in_recovery; perform a temporary-table INSERT in a rollback-only transaction. Capture only exception class on failure. Do not change database settings. Verify public purchase config remains disabled.
2. Before a replacement, retain private mode0600 complete inspect/configuration and a custom-format serving DB backup, verify pg_restore --list, hash backup and fingerprint protected commerce/customer/article-lifecycle tables. Confirm the currently serving original is exactly the read-only configured container and API points to it. Stop if the DB itself is in recovery or read-only without client PGOPTIONS, if identities differ, if purchasing is enabled, or if backup fails.
3. Stop and retain the original. Create one replacement with identical image ID, command, user, working directory, entrypoint, environment, mounts/read-only settings, host network, restart policy, rootfs/capabilities/security and all other effective container settings. Only container name and removal of exactly one PGOPTIONS entry may differ. Do not publish additional ports or alter source. Validate complete Config/HostConfig comparison privately before start; reject unexplained drift. Start only the replacement, verify health and rollback-only temporary write. On health/identity/write failure stop replacement and restart retained original; do not restore/delete database data.
4. Observe one public 2024 US makes request after successful health, letting the existing API schedule its existing bounded hydration. Do not invoke connectors directly, sweep years, manually retry providers, prepare articles, call models or start an article worker. Keep foreground monitoring below180seconds, one selected scope and one foreground request at a time. Existing deepening can issue background provider calls; record available aggregate request evidence and do not claim an unmeasured total ceiling. Read durable scope rows independently, compare actual public choices/complete/hydrating, and report any remaining provider or persistence failures without marking partial coverage complete. A changed data row alone does not prove both banks.
5. Recheck protected table fingerprints, disabled purchase and service health. Record selected runtime IDs, configuration diff and safe counts/digests. Stop on unexpected protected-state changes; preserve evidence and original/backup for explicit recovery, never auto-restore paid data. Keep #401 open unless the representative selector cascade truly completes. Article preparation/publication, source-rights determinations, paid/test-settlement browser acceptance, DNS and source/model configuration changes remain outside this runtime gate.

## Concrete todo

- [ ] Verify restored Docker/DB, exact serving ingestion/source/database identities, read-only transaction behavior, private backup and protected-table baseline before mutation.
- [ ] If the serving ingestion alone forces read-only transactions, retain the original and create an identical replacement with only PGOPTIONS removed; verify structural equality, health, and rollback-only writes.
- [ ] Observe one 2024 US makes scope through the existing bounded selector hydration path and read durable coverage/results; retain truthful partial state and safe error classes.
- [ ] Record exact runtime identities, redacted evidence and remaining catalog/article/paid-access gaps; synchronize Issue401/Project8 and keep rollback available.

## Bounded Docker default-normalization amendment

The first coordinator replacement attempt failed closed before start: exact staged container7ce6c5a98bec was retained in Created state, and original efdda4a448db was restarted healthy. Complete comparison found only HostConfig.OomKillDisable null in original/payload versus false in daemon-created inspect. Config, image and mounts matched. Local Docker is28.5.2 on cgroup2 with OomKillDisable support false. Exact [Moby v28.5.2 daemon adaptation](https://github.com/moby/moby/blob/v28.5.2/daemon/daemon_unix.go#L377) explicitly defaults a nil OomKillDisable pointer to false.

Only this documented normalization may be accepted: require original and unchanged payload field both null, new field literally false, and no other raw HostConfig differences. Keep raw comparison evidence plus a separate normalization receipt. Do not change payload, ignore arbitrary keys, accept true, or relax any Config/image/mount comparison. Reuse only the exact Created container ID from retained created.json after verifying its exact name, never-started state, and complete raw/effective structure again; do not remove/recreate original or staged evidence. A separate resume-created helper phase may stop the original/start this exact staged replacement only after all checks and current protected fingerprints/purchase checks pass. It must restart the retained original if start fails. Health/write verification and rollback requirements remain unchanged. Synchronize this amendment and pass new committed-base preflight before modifying the helper or dispatching resume.

Additional concrete todo:
- [ ] Record the fail-closed first attempt and exact upstream normalization evidence.
- [ ] Permit only null→false OomKillDisable daemon normalization and exact staged-container resume after new pinned preflight.
- [ ] Reverify health, rollback-only write, protected fingerprints and one bounded real selector scope.
