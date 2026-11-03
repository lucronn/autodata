# Paid Workshop GCE operations

This runbook follows the [bounded hosting plan](../superpowers/plans/2026-11-03-workshop-hosting.md), [Issue186](https://github.com/lucronn/autodata/issues/186), and [Project8](https://github.com/users/lucronn/projects/8). The [canonical planning gate](../agents/pre-implementation-gate.md), synchronized [record](../agents/records/2026-11-03-workshop-hosting.json), and [task](../agents/tasks/2026-11-03-production-release/workshop-hosting.json) govern implementation. Resource creation, real credentials, providers, staging, recovery and DNS changes require separate authorization after independent review.

## Current executable boundary

`infra/deploy/gce/cloud-bootstrap.sh` is an offline resource-definition renderer. It accepts no arguments or the single verb `plan`. The sole input is root-owned regular mode0600 `/etc/autodata/host.json`, validated by the reviewed v1 helper installed at `/opt/autodata/bin/runtime-check.py`. It reads through the helper's no-follow bounded descriptor contract. The shell launcher clears its environment and uses fixed `/usr/bin/python3 -I`; caller paths, environment substitutions, credential discovery and executable overrides are unavailable.

The output is one bounded JSON receipt with `definition_only:true`, `plan.execution_enabled:false`, and explicit unresolved inputs. A passed receipt means that the nonsecret definition was rendered. It does not certify IAM, resources, a mount, a package pin, a guard or a running service. Without the installed reviewed helper or staged private configuration it fails closed. The single verb `apply` also fails closed with `missing_dependency`; there is no approval flag or live apply implementation in this milestone. Unknown verbs and additional arguments are invalid.

The renderer names the proposed VM, data disk, static address, registry and backup bucket from the exact v1 configuration. The proposed e2-standard-4/200GiB balanced disk and bucket region remain subject to owner cost, residency and recovery approval. No disk is formatted, mounted or resized. A valid filesystem UUID in the configuration is an expected identity, rather than an observed disk identity. The renderer does not choose a VPC or boot image when those inputs remain unresolved.

`cloud-ops.py` likewise has no live adapter: valid publish/deploy/backup/monitor/restore arguments return `missing_dependency`. Its fake backup evaluator marks receipts `simulation:true`. Finite timeout/output budgets in those definitions do not establish actual subprocess cancellation or IAP stream deadlines. The release, backup and monitor workflow files are separate milestones; no scheduled cloud job is delivered by this bootstrap milestone.

## Owner inputs before bootstrap authorization

Record the chosen host, Firebase and backup projects; billing ownership; region/residency; accepted costs; operator and alert destination; maintenance window; and proposed RPO24h/RTO4h acceptance. Restore measurements must later establish achievable recovery, rather than treating these targets as observations. Approve the intended staging hostname and the final `https://cars.tk` origin separately. Preserve the existing Vercel and DNS configuration.

Pin the integrated release SHA, exact `linux/amd64` image references and local image IDs, image provenance/SBOM references, complete migration inventory/runner hashes, service-configuration digest, numeric secret versions, and Docker/Compose/boot-image/CLI package identities. Retain the reviewed configuration and release manifests by digest. Do not use `latest`, tag-only images, secret-version aliases, shell-generated configuration or an automatically selected developer account.

Record the numeric GitHub repository and owner IDs, exact repository/ref/workflow tuples, protected environment rules and distinct external principal identities. A matching set of JSON claims is only a definition check; real OIDC signature/audience validation, WIF trust, environment protection and denial tests are later evidence. The restore operator and any prune/retention authority require separate approval.

Review all permissions that cannot be restricted to the named disk/snapshot/instance. In particular, snapshot creation/listing and operation polling may require project-level authority. Retain that exception review explicitly; a resource-name check in a local script does not impose an IAM condition on a Google API. No external identity receives account-key creation or Token Creator on the attached Firebase account. Grant Service Account User only on that exact account if an actual OS Login path demonstrably requires it, after review.

## Reviewed resource and authority definition

Enable only the reviewed project APIs needed for Compute, registry, IAM/WIF, IAP/OS Login, named secret delivery and external monitoring in the host project; Compute/storage in the backup project; and Identity Toolkit in the Firebase project. The renderer merges API sets when project IDs coincide. Enabling an API does not grant the VM service account permission to use it.

Attach only `autodata-api-firebase@HOST_PROJECT_ID.iam.gserviceaccount.com`. Its custom Firebase permission is exactly `firebaseauth.users.get` on the selected Firebase project, with no other attached roles. The explicit VM access-scope ceiling is cloud-platform, userinfo.email and identitytoolkit, matching the SDK initialization. IAM is the permission boundary: the read permission includes account-read/list behavior and cannot be restricted to a single requested UID. Staging must prove actual SDK refresh, GetUser and revocation behavior.

Use separate external identities:

| Identity | Required boundary |
| --- | --- |
| Publish | Writer for the one Artifact Registry repository; no VM, secret or backup access. |
| Deploy | Reader for the repository, accessor for named manifest-bound numeric secret versions, trusted IAP/OS Login host administration for the one VM. |
| Backup | Non-admin IAP/OS Login; only fixed backup helper sudo verbs; named-disk snapshot permissions and reviewed owned-snapshot/project exceptions; unique bucket object-create; no delete, secret or Docker/root authority. |
| Monitor | Non-admin IAP/OS Login; fixed metrics helper only; external `roles/monitoring.metricWriter`; no deploy, secret, backup or registry authority. |
| Restore | Separate explicit operator approval for backup reads and isolated replacement-host administration. |

Only Caddy publishes80/443. Proposed IPv4 ingress permits TCP80/443 and restricts SSH22 to IAP `35.235.240.0/20`, scoped to the selected VM. Review actual VPC/firewall targeting and effective rules; the renderer grants no live ingress. Do not expose PostgreSQL, NATS, S3, worker, API or metrics ports. Use OS Login, block project SSH keys, and remove any unintended default service-account grants.

Before Docker starts, verify the exact expected data-disk filesystem UUID mounted at `/var/lib/autodata`, no overlapping VPC/host/Docker routes, and the reviewed metadata/storage guards. Forwarded metadata is permitted only from API172.30.10.10 on br-ad-edge; other containers and unprivileged host users must be denied on IPv4, IPv6 and the metadata hostname. Trusted host UID0 platform plumbing remains explicitly trusted. Storage172.30.20.40 permits only TCP9000 from application namespaces; both bridge and routed paths require enforcement. Actual namespace, OS Login/guest-agent, daemon restart and reboot probes are mandatory evidence.

Create no data directory on an unmounted boot disk. Format only an explicitly approved new empty disk after recording observed identity. Keep secrets and registry authentication in service-specific tmpfs paths; the attached VM identity cannot fetch them. Retain the one-permission attached account even when later external delivery fails.

## First installation and later rollout

After separate bootstrap authorization and verified host/package installation, stage the exact root-owned release and configuration at the fixed v1 paths. Validate the release, configuration, migration runner/tree, guards, disk and cached images. Fetch only the manifest-bound secret versions through the external deploy identity and deliver them privately into tmpfs. Keep cloud bearer tokens out of host disks, containers, argv, logs and receipts. Use transient registry authentication, pull exact digests, verify actual image identities, then remove that authentication.

Keep Caddy in maintenance while bringing up PostgreSQL/NATS/S3. Provision scoped database roles and the S3 bucket using separate temporary administrative inputs; remove those inputs and retire the S3 bootstrap identity before normal application startup. Run the released shared migration runner once and verify the resulting ledger against the manifest inventory. Apply the reviewed runtime grants. A failed migration retains maintenance and stops promotion; it does not authorize an old image against a changed schema.

Start private HTTP, one article worker, payment reconciler, then API in the canonical sequence. Actual merchant/price verification and any bank/model/identity call are separately authorized provider actions. The no-work readiness check must not fetch providers, hydrate an article or reconcile payments. Leave maintenance only after real required startup and readiness evidence passes. The current Go server does not guarantee graceful in-flight request drain; durable state and idempotent client retries govern interrupted work.

For subsequent changes, retain the previous compatible manifest and exact cached images, obtain a verified pre-migration backup, then enter bounded maintenance. An application rollback selects a validated compatible release without overwriting paid live data. A changed/incompatible schema requires a reviewed forward fix or recovery decision; no automatic down-migration is authorized.

## Reboot and rotation

After a reboot, missing tmpfs secrets intentionally prevent application startup. Verify mount/guard dependencies and selected release, then use the external deploy identity to redeliver exact approved secret versions before resuming. Do not fall back to VM ADC, old container environment metadata or developer credentials. Recovery time includes external runner/WIF/Secret Manager availability.

Rotate a secret by approving a new numeric version, delivering it atomically to only the intended service directory, and restarting the affected service through the fixed reviewed helper. Verify intended access and retired-credential denial. Remove temporary migration/bootstrap/registry credentials. Media-key rotation invalidates old image references; an authorized projection refresh renews them. Durable039 session tokens are database-hashed and require no invented server signing key.

## Backup, failure and isolated restore

Use a fresh UUID and the fixed host lease operations `begin UUID`, `status UUID`, `resume UUID`, and `export UUID`. Helpers own their paths and accept no caller command/root directory. A different active lease or completed UUID cannot be reused. The host enters maintenance, stops writers, creates/verifies the portable PG dump, stops stateful services and syncs. Only a matching unexpired quiesced receipt permits a snapshot of the exact configured disk.

The external snapshot receipt must bind resource/operation identities and cutoff/completion times within the lease, leaving a resume reserve. Lease total is at most1800seconds including recovery. A late snapshot, lease expiry, interrupted runner or watchdog resume cannot certify a backup. Attempt bounded resume for the matching lease even when snapshot creation fails. A stale UUID cannot resume a newer lease. Verify stateful services, writers and no-work readiness; retain incomplete recovery evidence if any step fails.

Export only after successful resume. Inspect the binary tar without extracting arbitrary paths: exactly regular `postgres.dump`, `release.json`, `backup.json`; no duplicates, extensions, directory/link/sparse entries or escaping names. Verify dump size/hash, manifest bytes/digest and type-strict archived receipt identity. Upload only immutable `UUID/postgres.dump`, `UUID/release.json`, `UUID/backup.json` objects in the configured private bucket; bind each exact bucket/name/generation/hash/byte count. A failed upload, resume or cleanup leaves `last_verified_backup` unchanged. Routine backup has no delete permission; owner-approved bootstrap lifecycle/prune authority manages proposed7daily/4weekly retention.

Restore only into a separately staged root-owned isolated replacement configuration/disk/VM. Refuse the live data UUID/path, disable bank/model/payment writer egress and keep ingress in maintenance. Validate snapshot cutoff, exact release/images/SQL inventory, ledger and schema, durable ownership/account/session/grant/order relations, article/source/canonical rows, every referenced S3 object and JetStream state. Prove portable PG restore on a fresh compatible instance. Do not replay payments or fetch a provider to fill missing objects.

The second restore stage requires distinct authorization for necessary live identity/merchant/price read checks with writers/reconciliation still stopped. Configured-commerce startup contacts Stripe; it is not an offline restore test. Use approved synthetic identities and authorized observations before an operator re-enables writers and ingress. Record actual cutoff, RPO/RTO, failed attempts and cleanup; never replace newer paid activity as routine rollback.

## Monitoring, final origin and evidence

Use native Compute metrics, an external HTTPS uptime check and a protected external five-minute scheduled metrics job. Its fixed helper exports only the reviewed aggregate names, units and states, with no dynamic customer/request/source/token labels. Missing measurements remain absent rather than becoming zero. Missing exporter heartbeat is an alert. The monitor has no Ops Agent or VM-ADC path. Bootstrap owns alert policies/notification channels; prove a test alert reaches the owner-selected destination. This coarse scheduler has jitter and does not promise a one-minute worker SLO.

Before any `cars.tk` cutover, separately approve actual final TLS/Firebase authorized-domain and popup-helper readiness. Keep Vercel during observation. Record existing DNS/TTL/Vercel state, preserve unrelated mail/TXT records, and change only approved apex A/conflicting AAAA records. HTTP-01 cannot issue for an apex still routed to Vercel; use separately approved DNS-01 integration or an honest certificate-issuance maintenance interval. DNS propagation is not guaranteed by the TTL. DNS rollback can restore an informational page, rather than the new paid application's current data/access.

For each later authorized operation, retain the exact integrated commit; input/config/manifest/tool hashes; principal and environment identifiers without tokens; bounded redacted stdout/stderr; guard/denial results; receipt hashes; timing/cutoff/lease identities; immutable snapshot/object generations; readiness and cleanup results. Link durable evidence from Issue186/Project8 and canonical documentation after coordinator verification. Temporary `/tmp` evidence from pure tests is review support, not durable backup storage or production evidence. Never store secret bytes, credential files, raw customer rows or source payloads in these receipts.
