# Staging M2A inert release-material installation plan

> **For agentic workers:** Local planning draft only. A synchronized committed checkpoint, full-SHA preflight, independent exact-checkpoint review and fresh root dispatch must precede implementation. Use superpowers:executing-plans after that dispatch.

**Goal:** Install only an owner-accepted authenticated release manifest and its exact migration runner/tree into a fixed root-owned staging release directory, without formatting disks, selecting a running release, delivering secrets or starting services.

**Architecture:** Split M2 into independently reviewable boundaries. M2A handles bounded private local release-material installation from a fixed inbox; subsequent gates handle remote/authenticated ingress, packages/guards/units, image pull and per-service secret delivery. M2A consumes trusted root-admin acceptance of independently verified publisher output; it is neither a publisher verifier nor an activation/startup path.

**Tech stack:** Python standard library, existing fixed deploy launcher and release/config validator, descriptor-relative local filesystem operations, one fixed read-only findmnt probe, fake-intercepted unittest suites.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-hosting.md`, `docs/superpowers/plans/2026-11-04-workshop-staging-lifecycle.md`, and `docs/agents/pre-implementation-gate.md`.

## Source, gate status and scope split

Source: independently reviewed M1 candidate `ef536cc24478424efc3cc084425322cfb8056145`, including explicit boot AttachedDisk.deviceName correction. Source pin identifies the inspected code, not a claim of coordinator integration, cloud execution or host readiness. No source merge/rebase is implicit in this draft.

Status: **draft; unsynchronized; implementation blocked**. [Issue186](https://github.com/lucronn/autodata/issues/186) and [Project8](https://github.com/users/lucronn/projects/8) remain untouched by this local draft. No matching synchronized M2A record exists at the source SHA. The coordinator must independently review this scope and then synchronize the exact goal/allowlist/todo and canonical notes, preserving then-current full tracking history before any implementation boundary.

The full earlier “host installation/private delivery” milestone combines unrelated authority: privileged package/unit installation, artifact authentication/remote transport, release byte installation and secret access. This plan narrows the first executable deliverable to **inert manifest+SQL installation only**. It does not claim a usable complete host, running images, secret delivery or a deployment. Exact source/package/image/secret references remain bound in the validated manifest, while their retrieval/use stays separately gated.

## Exact implementation allowlist and interfaces

Only three implementation paths may change after a new gate passes:

1. Modify `infra/deploy/gce/deploy.sh`: delegate only `install <SHA>` to fixed root-owned `/opt/autodata/bin/host_install.py`; preserve current `check` dispatch and unconditional denial of start/stop/maintenance/resume.
2. Create `infra/deploy/gce/host_install.py`: fixed-path approval/inbox/manifest validation, mount/lock checks, bounded descriptor copy, idempotent release-material installation and redacted receipt.
3. Create `infra/deploy/gce/test_host_install.py`: fake-probe and temporary-filesystem tests, launcher/denial/redaction tests, no real root paths/Docker/network/provider activity.

Exclude runtime-check.py, test_host_runtime.py, cloud-bootstrap.sh, cloud-ops.py, schemas, Compose, Dockerfiles, systemd/nft files, workflows, publisher/schema modules, SQL contents and application code. Existing release schema is unchanged. The new installation approval is a strict local JSON contract enforced by the new helper, not a modification of release.schema.json.

Frozen interfaces:

```text
deploy.sh install <40lowerhex>                # existing argv, one new delegation
host_install.py <40lowerhex>                  # internal fixed installed helper
install_cli(source_sha: str) -> (int, dict)   # called by trusted launcher
```

Neither entrypoint accepts path/config/root/command/approval/image/secret arguments or reads stdin/FD3/ambient credentials. Wrong argument count/SHA is exit2. Production config is exit3/missing_dependency before inbox or publisher acceptance bytes are read. Clear inherited environment, use fixed `/usr/bin/python3 -I`, cwd `/`, no shell sourcing/eval/PATH/HOME substitution or executable override. Install helper and current runtime helper are root-owned protected prerequisites installed by separate trusted administration; this helper never installs/replaces itself or the runtime validator.

## Required owner and publisher inputs

| Input | Required condition | M2A behavior when missing |
| --- | --- | --- |
| Staging identity | Existing strict host.json environment=staging and approved non-cars.tk HTTPS origin; exact host/Firebase/backup/resource configuration | Exit3; no receipt-directory/release writes |
| Authenticated publisher | Independently accepted candidate/finalize/independent raw readback verification binds run/attempt/artifact/outer+member hashes, canonical manifest/config hash, source, immutable images/provenance/SBOM; owner approves that exact output for installation | No root acceptance approval means exit3; no fake callbacks or bool fields count as publisher verification |
| Private local inbox | Trusted deploy administrator stages exact accepted manifest and migration runner/SQL bytes from the same verified source into the fixed root-owned inbox | Missing/drifting/extra/secret/link input fails closed; no source checkout, registry or network fallback |
| Data disk | Separately authorized host provision has already mapped the M1 disk resource to the expected local device and formatted/mounted its approved UUID at /var/lib/autodata | An M1 newly created empty disk is insufficient; M2A refuses unmounted/unformatted/wrong UUID and never formats or mounts it |
| Tmpfs/lock | /run/autodata already mounted tmpfs,nosuid,nodev,noexec; protected state directory/lock available | Exit3 before any persistent mutation; no disk-backed lock/secrets fallback |
| Installed tool/validator | Owner-provisioned reviewed Python/findmnt/runtime-check.py and hashes pinned in approval | Missing/drift fails; no apt/curl/pip/bootstrap/install action |
| Startup/recovery inputs | Native PG17/schema acceptance, actual metadata/storage isolation, images/pull credentials, numeric-version secret delivery, provider approval and minimum recovery | Still required by successor gates; installation success never substitutes these inputs |

The trusted deploy identity is already a host administrator. Root-owned acceptance is an explicit owner/admin decision following independent publisher verification; it is not an untrusted client assertion. M2A verifies exact bytes against that decision but does not authenticate GitHub, OIDC, Sigstore, registry or the original approval author. No `provenance_authenticated:true` or equivalent claim may be emitted. A hash-shaped receipt or `verified:true` field must never automatically manufacture owner acceptance. Before any real use the coordinator must establish who creates this root approval from actual independent publisher evidence; absent that completed dependency, only offline fixture tests are authorized.

## Fixed local inputs and exact inventory

Existing host configuration: `/etc/autodata/host.json`, strict v1, regular root:root0600, bounded1MiB, descriptor-pinned with protected parents. Root acceptance: `/etc/autodata/install-approval.json`, regular root:root0600, at most64KiB, no-follow strict UTF8 JSON with duplicate/unknown/null/non-finite rejection. Approval contains exactly:

```text
schema_version: integer1
operation: literal "install-inert-staging-release"
authorization_id: lowercase UUIDv4
expires_at: UTC RFC3339 seconds; future, <=24hours from now
source_sha: exact requested40lowerhex
service_config_sha256: existing canonical host.json SHA256
manifest_raw_sha256: lowercase64hex of inbox release.json bytes
manifest_canonical_sha256: lowercase64hex after strict parsing/canonical encoding
publisher_verification_receipt_sha256: lowercase64hex
owner_publisher_acceptance_evidence_sha256: lowercase64hex
owner_data_device_binding_evidence_sha256: lowercase64hex
owner_bare_host_evidence_sha256: lowercase64hex
runtime_helper_sha256: lowercase64hex
release_schema_sha256: lowercase64hex
findmnt_binary_sha256: lowercase64hex
files: sorted exact array of {path: allowlisted relative logical path,
                             bytes: positive integer<=1048576,
                             sha256: lowercase64hex}
```

The independently retained publisher verification receipt is opaque **nonsecret evidence**, staged by root at fixed `/etc/autodata/publisher-accepted/<SHA>.json`, regular root:root0600, at most64KiB; require exact hash equality to approval. Do not parse any bool inside as authority or execute embedded path/command fields. Its authenticity/meaning is accepted by the trusted owner/deploy administration, outside M2A. It must contain no credential/customer/token values; the trusted administrator is responsible for its redacted evidence classification. The helper emits only its hash.

Private inbox: `/var/lib/autodata/incoming/<SHA>/`, all directory ancestors root:root0700. Exact contents are `release.json`0600, `scripts/dev/migrate_sql.sh`0444 and `db/migrations/<manifest-filename>`0444. The only nested directories are `scripts`, `scripts/dev`, `db` and `db/migrations`; no arbitrary extra empty directory is accepted. Inputs are regular root:root files with nlink1; no symlink/hardlink/FIFO/socket/device, archive extraction or extra file/name. Approval paths exactly equal this derived inventory, sorted in bytewise ASCII order; one manifest, one runner,1–256 contiguous manifest SQL files, each<=1MiB, combined file bytes<=64MiB. File lengths/hashes in approval must match actual bytes; runner/SQL hashes also independently match manifest. Reject any secret/config/registry credential file or service-secret directory in inbox as an unexpected item; do not attempt content-based secret detection or read unrelated files.

All SHA/UUID/logical filenames are validated before use as components. No absolute/traversal/dot/empty/NUL/backslash paths; only fixed `release.json`, fixed runner path and exact v1 migration filenames resolve through trusted directory FDs. Validate the manifest using unchanged runtime-check.validate_manifest(manifest, config, rollback_manifest), including linux/amd64, exact digest image references/platform-specific image IDs/provenance/SBOM, complete migration inventory/hash, toolchain package hashes, canonical config binding and exact per-service numeric secret-version references. Require rollback_source_sha=null for this first-install-only gate; any /opt/autodata/current symlink/object or non-null rollback blocks. Future rollout/switch is separately gated. No image pull/inspect/build/run, secret fetch/read, template rendering, migration execution or SQL query occurs.

## Mount, lock, bounded filesystem operations

Only subprocess inventory is fixed read-only `/usr/bin/findmnt --json --list --mountpoint TARGET --output TARGET,UUID,FSTYPE,OPTIONS` for TARGET `/var/lib/autodata` and `/run/autodata`. Use existing strict_json and validate_mount_observations without changing their contracts: exact mountpoint/expected filesystem UUID, ext4/xfs data,rw and tmpfs,nosuid,nodev,noexec secrets mount. No ancestor mount fallback. Capture stdout<=64KiB with streaming bounds, stderr discarded,5second child timeout; one300second monotonic operation deadline includes30seconds cleanup reserve. TERM then KILL a timed-out child process group with bounded reap; never retain a live child or raw stderr/API/secret values.

Mount UUID plus local filesystem observation is not independent proof of a GCE disk selfLink; owner_data_device_binding_evidence_sha256 identifies the separately accepted host/device mapping. Prove exact mountpoint with findmnt and pin its opened directory fd/st_dev before creating any operations/incoming/release temporary path. Re-read both fixed mount observations and compare pinned data-directory identity before final promotion and receipt persistence. Missing/replaced/wrong/readonly mounts fail without creating data directories on the boot filesystem. Installer must contain no mkfs/wipefs/parted/mount/remount/resize/blkdiscard/dd/format/provision action.

Only after mounts validate, create/open root:root0700 `/run/autodata/state` and no-follow regular root:root0600 `operation.lock`, nlink1. Nonblocking flock exclusive covers all validation/mutation; busy is exit3 with no persistent mutation. Do not infer lock ownership from PID content. Same lock literal is reserved for later lifecycle/backup helpers. No service-secret subdirectory or credential file is created. A missing tmpfs prevents install; reboot recovery never substitutes a persistent lock/secret directory.

Before importing fixed `/opt/autodata/bin/runtime-check.py`, verify descriptor-opened regular root-owned helper bytes against approval.runtime_helper_sha256, non-writable to group/other and stable pre/post fstat; import the exact verified bytes through compile/exec in a private module namespace, not a pathname reopened after validation. Set the private module __file__ to the fixed verified helper path so its unchanged validator resolves the sibling schema. Before calling validate_manifest, descriptor-open fixed `/opt/autodata/bin/release.schema.json`, require regular root-owned nlink1/non-group-or-other-writable bytes<=1MiB and approval.release_schema_sha256, and verify unchanged identity/hash again after validation. The schema remains a separately trusted installed file, not inbox-controlled; trusted host root is outside the hostile-caller threat model. Review-pinned helper/schema/dependency layout must be supplied by separate administration; this gate cannot silently fetch it. Do not execute inbox runner/SQL. Validate fixed findmnt binary through a pinned descriptor/hash before use and execute that same verified descriptor using `/proc/self/fd/<fd>` with pass_fds, preventing pathname replacement between hash and exec; no caller selects the FD/executable.

## Install transaction and receipt contract

1. Require root, strict fixed approval/config/source/staging/expiry, accepted publisher evidence hash and no current-release object. Require owner_bare_host_evidence_sha256 for separately accepted bare-host state; the absence of a current link does not prove absence of processes/containers. This helper performs no runtime discovery; first-install-only authorization and that external owner evidence remain prerequisites. Check local predicates before persistent changes.
2. Validate mounts, acquire shared lock, descriptor-open inbox/approval/evidence/manifest and all exact files. Complete all file/tree/manifest/hash/length/owner/mode checks before creating a release temporary directory. Files may be streamed twice from pinned descriptors, with stable metadata/hash checks each pass; memory retention is at most1MiB per file, never64MiB aggregate.
3. `/opt/autodata/releases` must be root:root0700 and already exist, supplied by trusted admin; never use cwd/current fallback. Create sibling `.install-<authorization_id>`0700 with exclusive mkdir, refusing any preexisting temp object. Copy only the verified inventory using descriptor-relative O_EXCL|O_NOFOLLOW and bounded writes; modes release.json0600 and SQL/runner0444. Subdirectories begin0700 during construction and end0500; final release directory0500. fsync each file and directory. Existing final `<SHA>` is never overwritten: exact full-tree byte/owner/mode equality is the only idempotent pass; any drift is failure.
4. Revalidate expiry, source file metadata/hashes, no current object, locks and mount identities, then rename the newly constructed same-filesystem sibling atomically to `<SHA>` using a no-replace primitive. Python os.rename alone may replace an existing directory; use fixed libc renameat2(RENAME_NOREPLACE) through ctypes, fail missing_dependency when unsupported, never fall back to replace. Both names are validated fixed components under the same pinned release-root descriptor. fsync release parent after commit.
5. Persist a bounded redacted operation receipt under verified data mount `/var/lib/autodata/operations/<authorization_id>.json`, regular root:root0600 with atomic same-directory replace/fsync. Root parent0700 may be created only after mount verification. Same authorization replay requires exact input/source/config/manifest identity; no receipt can turn partial output into passed. If installation committed but receipt persistence fails, return exit6/recovery_incomplete with `release_material_committed:true`; retry may prove exact inert tree, not claim an earlier success.

Cleanup removes only files/directories created by this operation whose descriptor-pinned identity and exact derived inventory still match; no shutil.rmtree, recursive arbitrary removal or caller path. Unexpected inode/name/link change, failed unlink/reap or remaining owned temp yields exit6 and safe receipt, never deletes an existing final release or data. Deadline exhaustion stops new work; failure before promotion leaves /opt/autodata/current absent and no running release selected. Record fixed commit state enum `not_started|copying|material_committed|receipt_committed|incomplete`, no secret/raw input/error strings.

Stdout is one JSON object<=64KiB with existing common fields schema_version/operation/source_sha/run_id/status/started_at/finished_at/checks/failure_code plus `inert_installation_only:true`, `deployment_authorized:false`, `release_material_committed:boolean`, manifest raw/canonical hashes and publisher/owner evidence hashes. run_id is approval authorization_id; operation is literal `deploy.sh install`. Allowed checks are existing config/manifest/migration_tree/disk_uuid when genuinely observed; schema/services/secrets/cached_images/runtime_evidence stay false. Preserve exit0 success,2 invalid input,3 missing dependency,4 operation failure,5 timeout,6 incomplete recovery. Success means inert material installed only, never publisher authenticity, image cache identity, secret availability, schema/service readiness or a selected current release.

## Failure and reboot invariants with planned tests

- `test_staging_install_material_only`: synthetic accepted manifest+runner+SQL installs with exact bytes/modes, one no-replace commit, expected hashes and false runtime/secret/image checks; no current link/service/unit/Compose/secret material exists afterward.
- `test_missing_publisher_acceptance_blocks_before_write`, `test_hash_shaped_untrusted_receipt_is_not_approval`, `test_owner_approval_expiry_or_source_config_hash_drift_denied`: no new release/data paths or subprocess outside fixed probes.
- `test_wrong_or_unmounted_disk_never_initializes_boot_disk`, `test_format_mount_or_device_commands_never_invoked`, `test_mount_replacement_before_commit_denied`, `test_disk_binding_hash_is_not_cloud_observation`: strict UUID/mount checks and explicit observed-evidence limits.
- `test_image_tag_platform_id_or_provenance_drift_denied`, `test_secret_alias_unknown_name_or_secret_payload_file_denied`: unchanged manifest/schema/reference allowlists, no pull/credential read, no secrets in receipts/argv/files.
- `test_inventory_overflow_link_fifo_duplicate_or_traversal_denied`, `test_opened_input_replacement_or_postread_hash_drift_denied`, `test_existing_release_exact_rerun_only`, `test_rename_noreplace_race_preserves_existing_tree`: real temporary inode/FD operations with rootless low-level helper tests; production ownership defaults cannot be overridden via CLI/env.
- `test_lock_busy_no_write`, `test_stdout_flood_timeout_child_reaped`, `test_copy_failure_cleanup_bounded`, `test_receipt_failure_after_commit_incomplete`: stage fault injection at every copy/fsync/rename/receipt boundary; never pass partial work or change prior selected state.
- `test_reboot_missing_tmpfs_or_approval_fails_closed`: model loss of /run mount/lock and stale approval; install does not reuse persistent secret/lock state. `test_install_creates_no_auto_start_state`: /opt/autodata/current remains absent, no autodata.service/enable symlink/Docker restart configuration or secret file is created. These are inert-install invariants, not actual reboot/daemon/startup proof; the real post-reboot secret gate is a separate successor.
- `test_launcher_only_install_delegates`: exact SHA/count and fixed interpreter/helper, unchanged check path, start/stop/maintenance/resume continue exit3; production denial occurs before inbox/evidence/stdin access.

Tests use only intercepted findmnt/process probes and temporary test directories; socket/network/Docker/cloud/secret functions fail immediately if called. Filesystem tests may pass current UID explicitly to low-level test-only invocation of descriptor helpers; public CLI/install_cli always enforce UID0 and fixed root paths, with no production bypass. Keep prior M1 and host/cloud regression suites passing. No planning-time Docker command, actual secret, mount, root path or credential operation is authorized.

## Concrete todo for future synchronization and execution

- [ ] Independently review this M2A split, exact three-file scope, trusted owner-acceptance boundary, immutable file/input/receipt contract and no-replace/cleanup primitives; synchronize goal/todo/references in Issue186/Project8/canonical docs with full then-current history preservation, commit/push and full-SHA preflight before builder dispatch.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh root dispatch; establish actual authenticated publisher and separate mounted-disk/tool prerequisites before any later live installation, without inventing a verifier or owner/cloud values.
- [ ] Add failing fake-probe and temporary-inode tests for approval/publisher/mount/lock/inventory/no-replace/fault/redaction and reboot fail-closed invariants; then implement only deploy.sh, host_install.py and test_host_install.py for inert release-material installation.
- [ ] Run focused host-install tests plus existing host/cloud/bootstrap regressions, syntax/diff/scope and pinned preflight; commit/push a coherent exact candidate for independent review, preserving all startup/readiness/cloud/secret/production denials.
- [ ] Require separate decision-complete gates for authenticated remote ingress/private secret delivery, host packages/guard/units, image pull, start/schema/readiness and minimum recovery; no one may treat M2A success as completion of full M2 or live-operation authorization.

After authorized implementation, run:

```sh
python3 -m unittest discover -s infra/deploy/gce -p 'test_host_install.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_host_runtime.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_cloud_ops.py' -v
python3 -m unittest discover -s infra/deploy/gce -p 'test_staging_bootstrap.py' -v
python3 -m py_compile infra/deploy/gce/host_install.py infra/deploy/gce/test_host_install.py
git diff --check
```

## Non-dispatchable successor M2 boundaries

**M2B authenticated ingress and private secret delivery:** Needs publisher's actual independent verification/output format and exact transport composition; root-owned length-framed private stdin delivery with repeated owner/tree checks; immutable accepted payload inventory; per-service numeric-version secret allowlists and ownership; atomic tmpfs-only secret promotion; temporary registry auth cleanup; actual Docker Config.Env/no-token/no-disk redaction proof; cancelled/late-write cleanup; repeated reauthorization/redelivery after reboot. Do not invent this protocol from an untrusted verified flag or mutable artifact tag. Its exact allowlist is intentionally not authorized here.

**Host preparation/activation:** Needs separate owner-approved format/mount of M1 disk, pinned package installation without unintended daemon start, helper/guard/systemd installation and actual guard tables before Docker, exact image readback and startup secret rehydration barrier. Existing `restart:unless-stopped` containers must never restart writers after reboot without the new guard and current tmpfs secret proof; M2A creates no containers/units and cannot certify that future behavior. Actual namespace/IAP/metadata/S3 isolation, daemon restart/reboot, PG17/schema/provider startup and recovery are later separately authorized evidence.

Open blockers for live use remain owner-selected GCP projects/billing/region/VPC/HTTPS origin, independent publisher authenticated output/owner acceptance workflow, separately accepted disk mapping+format+mount, installed reviewed helper/tool identities and minimum recovery. None blocks drafting or later authorized offline fixture implementation. This local document adds no synchronized record, credentials/cloud/Docker/secret operation or readiness claim.
