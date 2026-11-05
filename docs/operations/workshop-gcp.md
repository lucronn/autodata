# Paid Workshop GCE operations

This runbook follows the [bounded hosting plan](../superpowers/plans/2026-11-03-workshop-hosting.md), [Issue186](https://github.com/lucronn/autodata/issues/186), and [Project8](https://github.com/users/lucronn/projects/8). The [canonical planning gate](../agents/pre-implementation-gate.md), synchronized [record](../agents/records/2026-11-03-workshop-hosting.json), and [task](../agents/tasks/2026-11-03-production-release/workshop-hosting.json) govern implementation. Resource creation, real credentials, providers, staging, recovery and DNS changes require separate authorization after independent review.

## Current executable boundary

`infra/deploy/gce/cloud-bootstrap.sh` is an offline resource-definition renderer. It accepts no arguments or the single verb `plan`. The sole input is root-owned regular mode0600 `/etc/autodata/host.json`, validated by the reviewed v1 helper installed at `/opt/autodata/bin/runtime-check.py`. It reads through the helper's no-follow bounded descriptor contract. The shell launcher clears its environment and uses fixed `/usr/bin/python3 -I`; caller paths, environment substitutions, credential discovery and executable overrides are unavailable.

The output is one bounded JSON receipt with `definition_only:true`, `plan.execution_enabled:false`, and explicit unresolved inputs. A passed receipt means that the nonsecret definition was rendered. It does not certify IAM, resources, a mount, a package pin, a guard or a running service. Without the installed reviewed helper or staged private configuration it fails closed. The single verb `apply` also fails closed with `missing_dependency`; there is no approval flag or live apply implementation in this milestone. Unknown verbs and additional arguments are invalid.

The renderer names the proposed VM, data disk, static address, registry and backup bucket from the exact v1 configuration. The proposed e2-standard-4/200GiB balanced disk and bucket region remain subject to owner cost, residency and recovery approval. No disk is formatted, mounted or resized. A valid filesystem UUID in the configuration is an expected identity, rather than an observed disk identity. The renderer does not choose a VPC or boot image when those inputs remain unresolved.

`cloud-ops.py` likewise has no live adapter. Its current offline parser accepts exactly two positional arguments: `publish|deploy|monitor` followed by a lowercase 40-hex source SHA, or `backup|restore` followed by a UUID. Valid arguments return exit 3 and a failed `missing_dependency` receipt; unknown verbs, malformed identifiers and extra arguments return exit 2. These are fail-closed definition entrypoints, rather than the future executable flag-based interfaces in the plan. Its fake backup evaluator marks receipts `simulation:true`. Finite timeout/output budgets in those definitions do not establish actual subprocess cancellation or IAP stream deadlines.

The pure `evaluate_published_release` function additionally compares a supplied fake read-only transcript against the reviewed manifest/configuration and a separately supplied run/artifact/digest binding. Its fixed observations are run metadata, artifact metadata, bounded manifest bytes and image observations. It rejects unknown/missing fields, mismatched source/workflow/run/artifact identity, unfinished or unsuccessful runs, expired artifacts, wrong byte counts/hashes, duplicate JSON keys, scalar-type drift and inconsistent image/platform/provenance/SBOM references. Consistency produces only `status: transcript_consistent`, `simulation:true`, `deployment_authorized:false` and `consistent_binding`; it does not produce a publish-success receipt. These untrusted fake observations cannot prove OIDC, GitHub/registry authenticity, signed provenance, SBOM contents or an actual image build/publication. Callback timeout/output budgets are definitions, not actual subprocess cancellation. The CLI and workflows do not call this evaluator and remain blocked.

## Disconnected publisher orchestration v2

The [publisher checkpoint](../superpowers/plans/2026-11-03-workshop-publisher-transport.md) at `ddce00bddda3f69c27fb6672eac5dbb1851e6cd3` separately governs the three-path B implementation. `cloud-ops.py` now provides `produce_release_archive`, `orchestrate_publication`, `evaluate_publication_v2` and `evaluate_host_check`. No function has a default real executor/transport, and neither the CLI nor the workflows invokes these APIs. All execution in this milestone is through supplied fake interfaces; existing CLI and workflow missing_dependency behavior is unchanged.

The orchestrator issues the fixed source checkout and exact SHA/committer-timestamp check, three buildx push requests in api/ingestion/migration order, immutable registry digest/config/source/configuration checks, bounded syft SPDX capture and per-image evidence publish-and-verify requests. It then produces the deterministic inner ZIP, requests upload of only release.zip, and verifies upload/readback metadata and supplied original wrapper/inner bytes. Every request carries fixed timeout/output budgets; fake callbacks establish sequencing and validation, not actual cancellation or bounded real subprocess/HTTP capture. A partial build/push failure stops later operations and yields no release binding; no registry-delete or rollback authority is introduced. The manifest contains independently reviewed expected image pins: an unexpected rebuild cannot silently replace them. Owned-image provenance fixtures cover three built roles; approved third-party dependency references remain independent inputs.

The deterministic inner archive contains exactly release.json and images.json as canonical JSON, with stored ZIP32 entries and fixed metadata. Protocol2 separates four meanings: artifact_digest/artifact_bytes bind the original outer GitHub transport archive; archive_sha256/archive_bytes bind inner release.zip; member_sha256/member_bytes bind its raw JSON members; manifest_sha256 binds canonical reviewed manifest content. The producer envelope describes generated output and cannot approve itself. The legacy raw-JSON fake transcript API retains its original artifact_digest meaning and is not accepted as a v2 binding.

Supplied fake evidence must match numeric owner/repository IDs, protected environment/workflow/ref, issuer/audience/builder/source/configuration and exact owned-image/SBOM subjects. Matching fixtures are always marked simulation:true, provenance_authenticated:false and deployment_authorized:false. `transcript_consistent` is neither authentic publication nor a deploy-success receipt. Input DTOs require exact fields and literal JSON types; unknown fields, scalar/container drift, oversize data, wrong digests, callback exceptions/timeouts and invalid evidence fail closed with redacted diagnostics.

Host checking is a separate explicit call. It accepts an internally consistent v2 publication-evaluation or publisher-orchestration result bound to the same exact release; it rejects legacy receipts and any attempted promotion of simulation/authentication/deployment flags. Its sole fake request is `/usr/bin/gcloud compute ssh INSTANCE --project PROJECT --zone ZONE --tunnel-through-iap --quiet --command 'sudo -n /opt/autodata/bin/deploy.sh check SHA'`, using only validated configuration and the selected source SHA. There is no arbitrary command/path/instance override or real credential selection. A valid host exit3/missing_dependency returns status unavailable. Schema/services/runtime_evidence must remain false, including a timed-out host reply; host exit0 or affirmative readiness is rejected. Publishing never invokes the host check automatically.

Authenticated adapters and workflow activation require the separate follow-on gate defined in the plan: actual owner identities and environment/WIF/IAM denial evidence; pinned tools/actions/BuildKit/verifier dependencies; real bounded executor and secret-free credential handling; original GitHub artifact digest semantics and a safe outer-envelope decoder; actual OCI/SBOM/signature verification and archive compatibility; separately authorized staging. No fake wrapper or signature-valid boolean proves GitHub compatibility, OIDC trust or signed provenance. Production schema/service/no-work readiness, restore/monitoring, provider/merchant verification, paid browser acceptance and cars.tk/DNS cutover remain independently gated.

## Guarded workflow definitions

The [release](../../.github/workflows/release-workshop.yml), [backup](../../.github/workflows/backup-workshop.yml) and [monitor](../../.github/workflows/monitor-workshop.yml) files define production dispatch boundaries. They are JSON-form YAML and are independently testable with the standard-library suite in [test_cloud_ops.py](../../infra/deploy/gce/test_cloud_ops.py). They contain no checkout, action invocation, OIDC-token request, cloud authentication or operation adapter. Workflow and job permissions are only `contents: read`.

Each job requires its repository-scope `WORKSHOP_<OPERATION>_ENABLED` variable to equal the literal `true`, the repository to equal `lucronn/autodata`, and the Git ref to be `refs/heads/master`. Absent or false enable variables skip the job. This milestone does not set enable variables, configure environment protection or authorize dispatch. Each enabled job names a separate environment whose required reviewers and branch rules must later be configured and verified by the owner:

| Operation | Protected environment name | Trigger definition | Job timeout |
| --- | --- | --- | --- |
| Publish | `workshop-production-publish` | Manual release dispatch with `operation=publish` | 45 minutes |
| Deploy | `workshop-production-deploy` | Separate manual release dispatch with `operation=deploy` | 30 minutes |
| Backup | `workshop-production-backup` | Manual backup dispatch or `17 3 * * *` (03:17 UTC daily) | 30 minutes |
| Monitor | `workshop-production-monitor` | Manual monitor dispatch or `*/5 * * * *` | 1 minute |

Release has no push, schedule or completed-workflow trigger. Publishing never selects the deploy job. Each workflow serializes its own runs with `cancel-in-progress:false`; this does not establish a cross-workflow host lock. GitHub scheduling can be delayed. The backup timeout is a definition budget; actual lease recovery, resume reserve and interrupted-run behavior remain unimplemented in the workflow.

Enabled jobs validate the numeric `WORKSHOP_REPOSITORY_ID` and `WORKSHOP_OWNER_ID` against the GitHub context, plus the exact workflow filename at the master ref. They require `WORKSHOP_CONFIG_SHA256`, the operation's `WORKSHOP_<OPERATION>_WIF_PROVIDER`, and all four `WORKSHOP_PUBLISH_SERVICE_ACCOUNT`, `WORKSHOP_DEPLOY_SERVICE_ACCOUNT`, `WORKSHOP_BACKUP_SERVICE_ACCOUNT` and `WORKSHOP_MONITOR_SERVICE_ACCOUNT` values. The four accounts must be valid, distinct service-account names, and the selected account must match the operation. Supply the reviewed tuple consistently to every protected environment. These string checks neither authenticate an OIDC token nor enforce Google IAM trust.

Release dispatch requires `operation` to be `publish` or `deploy`, and `source_sha` as 40 lowercase hex characters. Publish rejects nonempty deploy-only fields. Deploy requires positive numeric `published_run_id` and `artifact_id`, `artifact_digest` as `sha256:` plus 64 lowercase hex characters, and `manifest_sha256` as 64 lowercase hex characters. The job checks only their shape: it does not fetch the named run/artifact, verify successful publication, hash artifact bytes, validate provenance or bind an artifact to that source/configuration. A later reviewed adapter must establish every binding before deployment; tags or a syntactically valid digest alone are insufficient.

Backup and monitor read `WORKSHOP_RELEASE_SHA` from protected configuration. Manual backup checks `run_id` for lowercase UUIDv4 syntax; it cannot establish freshness or detect reuse. The scheduled validator generates one only in its process. It neither persists a lease nor invokes a host helper. Monitor accepts no command or path input. Input rejection exits 2 with a fixed redacted diagnostic. Even when all definition inputs validate, the final step unconditionally exits 3 with `missing_dependency`, identifying the absent reviewed WIF/operation adapter. Monitor also identifies missing external heartbeat-alert evidence. No workflow currently publishes, deploys, backs up, exports metrics or sends an alert; a skipped job or validated input message is not operation evidence.

Before promoting a live capability, independently review its pinned actions/toolchain, least-privilege token permissions and WIF trust, immutable artifact retrieval/provenance verification, fixed host-helper interface, timeouts/cancellation, redaction, recovery and safe receipts. Prove environment protection and real denial behavior under a separately authorized staging gate. The existing enable variables alone cannot make these definitions execute cloud work.

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


## Passive PostgreSQL schema collector: draft prerequisites

**Historical A v3 checkpoint.** The blocked catalog-only v2 amendment below supersedes this material for the next A milestone; earlier synchronization is not v2 authority.

This coordinator-owned runbook amendment follows the [approved v3 passive-schema contract](../superpowers/plans/2026-11-03-workshop-hosting.md#passive-schema-observation-synchronized-plan-only-checkpoint). Its task/record are `synchronized` after live Issue186/Project8 readback; commit/push, exact-SHA preflight, coordinator integration/re-pin and independent checkpoint review remain pending. It adds no executable operation today. The reviewed image/migration check remains partial: schema, services and runtime evidence are unavailable and check exits3 missing_dependency.

A future separately authorized provision operation must create the dedicated autodata_metrics LOGIN role with no superuser/createdb/createrole/replication/bypassrls/inherit powers or memberships, no database/schema/relation/sequence ownership, no CREATE/TEMP or relation/column/sequence write rights (including PostgreSQL17 MAINTAIN), and CONNECT, public schema USAGE and ledger SELECT only as required by the fixed contract. Effective rights include PUBLIC grants. Explicit database ownership compares autodata pg_database.datdba against the role OID even when CREATE/TEMP are revoked. Runtime-grants provisioning remains outside the next two-file collector milestone.

The intended socket-auth provision is the early pg_hba.conf rule `local autodata autodata_metrics peer map=autodata_metrics_probe` plus pg_ident.conf mapping `autodata_metrics_probe postgres autodata_metrics`, with the reviewed image's OS user postgres at UID999. Administration must install/protect the effective PGDATA HBA/ident files, prove rule selection under separate staging authorization, and preserve the configured PGDATA `/var/lib/postgresql/data/pgdata`. The collector does not create/edit those files, infer effective server configuration from a bind mount, read superuser-only data_directory, or obtain broad monitoring membership. No new secret mount, TCP trust broadening or admin/password fallback is permitted. Missing role/client/socket/auth/rights makes observation unavailable.

The proposed collector inspects only the fixed local Postgres container, binds the selected image/project/service/UID/data and secret mounts, executes a fixed isolated socket-only read-only query as autodata_metrics, and re-inspects the validated container ID. It accepts only the exact bounded protocol in the canonical plan: ordinary permanent non-RLS text-key ledger, full selected manifest inventory, effective least rights, rows/values bounded before aggregation and streamed subprocess output bounded before retention. Mount observation does not prove effective PostgreSQL data/config/HBA/ident paths.

Even future schema evidence cannot make service/no-work readiness pass or authorize start/resume/maintenance/deployment. All collector tests are intercepted fake-exec tests; no actual Docker/PostgreSQL/host/cloud/provider action is authorized by this draft. Require the coordinator's synchronized checkpoint, pinned preflight and independent review before implementation, followed by exact-SHA candidate review before integration.


Tracking synchronization read back: [Issue186 comment6617024444](https://github.com/lucronn/autodata/issues/186#issuecomment-6617024444) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, at `2026-11-03T22:27:57.522560+00:00`. The comment records the same v3 goal, five concrete todos, exact two-path implementation scope and offline limits; the project note indexes it. This is a plan-only synchronization checkpoint, not implementation dispatch or runtime/deployment authorization.


### B release ZIP archive reader: synchronized planning checkpoint

**Historical synchronized B checkpoint.** Its exact comment6617360191/protocol/future-publication limitations are preserved below. Offline implementation is independently approved and integrated at052bbf9; this historical checkpoint is not the current blocked A gate.

**Goal:** Implement a bounded offline release ZIP archive verifier with independent archive and member SHA256 bindings, strict ZIP32 structure and JSON/image consistency checks; keep publication authentication and deployment unavailable.

The [canonical hosting amendment](../superpowers/plans/2026-11-03-workshop-hosting.md#b-release-zip-archive-reader-synchronized-plan-only-checkpoint) proposes a pure bounded ZIP32 archive verifier at planning source base `a0eed5dce45171f5f94f72d99d2fdf694235df0d`. This is a proposed `release.json`/`images.json` producer contract with explicit local/central/EOCD agreement, signed/unsigned bounded descriptor parsing, no ZIP64 or extra fields, stored/bounded DEFLATE decoding and independent whole-archive/raw-member/canonical-manifest digest meanings. It does not claim compatibility with an actual GitHub Actions artifact: the current workflow produces none, and authenticated publisher/transport compatibility remains separately gated.

The next B implementation scope is only `infra/deploy/gce/cloud-ops.py`, `infra/deploy/gce/test_cloud_ops.py` and `docs/operations/workshop-gcp.md`. The task/record/queue are `synchronized` after live [Issue186 comment6617360191](https://github.com/lucronn/autodata/issues/186#issuecomment-6617360191) and [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` readback at `2026-11-03T22:43:36.177270+00:00`; the project preserves historical A/R6 references and indexes the exact B goal/five todos/scope/limits in that comment. Independent draft review approved SHA256 `706f5fb2326ddc9e223547b4e95951f4643ba67d6b6e6a01d538198db0f319c6`. Commit/push this seven-document checkpoint, full-SHA preflight and independent coordinator gate handoff remain required before implementation dispatch. Historical synchronized A material does not authorize B. A and R6 files and workflow execution remain outside scope. Success can report only simulated archive consistency with provenance/deployment authority false; every CLI operation remains unavailable.

Concrete todo:

- [ ] Synchronize this exact B archive-reader goal, ZIP32 producer contract, scope and todo across Issue186/Project8 and canonical documents; commit/push a plan-only checkpoint, pin its full SHA and pass machine preflight before coordinator dispatch.
- [ ] Add failing synthetic archive tests for digest separation, strict local/central/EOCD and descriptor agreement, bounded stored/DEFLATE decoding, strict JSON and exact image observations; retain existing B tests.
- [ ] Implement only cloud-ops.py and test_cloud_ops.py for explicitly supplied in-memory archive bytes and independently bound raw member digests; preserve existing fake transcript API and every fail-closed CLI operation.
- [ ] Document proposed release.json/images.json producer layout, archive/raw-member/canonical-manifest digest meanings, fixed failure receipts and the lack of actual GitHub artifact compatibility or authenticated publication evidence.
- [ ] Run focused B tests, Python syntax, diff/scope and exact-base preflight checks; commit/push a coherent candidate and obtain independent exact-SHA review before coordinator integration; cloud/provider/workflow/deployment execution stays separately gated.


### Offline release archive consistency helper

`cloud-ops.py` now exposes the pure `verify_release_archive(archive_bytes, manifest, *, expected_archive_sha256, expected_member_sha256)` definition. Callers must first validate the approved manifest/configuration/rollback using `rt.validate_manifest`. Inputs are explicitly supplied bytes and independent lowercase 64-hex digest approvals; the helper opens no file, makes no network/subprocess call, extracts nothing and has no CLI dispatch path. Existing publish/deploy/backup/monitor/restore CLI operations still return `missing_dependency`.

The proposed producer layout is exactly `release.json` followed by `images.json`, in both local and central order, with two nonempty strict JSON bodies. The archive is at most 8 MiB; each declared compressed and actual/declared uncompressed member is at most 1 MiB, combined output at most 2 MiB, and expansion ratio at most 100:1. Only stored or raw DEFLATE ZIP32 entries, optional descriptor/UTF8 flags, and regular files are accepted. ZIP64, extra fields, encryption, comments, links/special files, unexpected names, padding, overlapping records and prepended/trailing material are rejected. Local headers must agree with central metadata; descriptors are exactly 12 or 16 bytes as determined by independently checked offsets. The parser does not guess boundaries from signatures. Every DEFLATE call bounds output and input chunks; truncated, concatenated or trailing streams fail without unbounded flush. The canonical hosting plan specifies the exact subset.

The whole-archive SHA256 binds the original ZIP bytes. Each independently supplied member SHA256 binds its raw decoded bytes. The canonical manifest SHA256 uses `rt.sha256(manifest)` and can differ from raw `release.json` SHA256 when JSON formatting differs. Raw member hashes, CRC/size checks, duplicate-key rejection and canonical comparisons all remain required. `images.json` must exactly match the manifest's role/image fields plus platform; these supplied observations do not inspect a registry.

Success returns only fixed `archive_consistent` metadata with `simulation: true`, `provenance_authenticated: false` and `deployment_authorized: false`, verified digests, member byte counts and fixed consistency checks. Failure raises `ContractError('invalid release archive')` without member content or underlying exception text; partial work yields no success receipt. Standard-library and synthetic ZIP fixtures exercise structure and bounds, including both descriptor forms and 1 MiB member limits. They do not establish actual GitHub Actions archive compatibility or authenticated publication. The current workflow produces no release artifact; a separately synchronized publisher/transport gate must prove compatibility/provenance or review a protocol amendment before any real use. Runtime, staging and release readiness remain unverified.


## Catalog-only PostgreSQL v2 correction: synchronized

Status: `synchronized` after live Issue186/Project8 readback. Independent plan-only review approved correction artifact SHA256 `7971a7ec0c260237dfea3f80be2318443981ffb40f8c63a2a3300dccf78a1d22`. This seven-document planning draft starts from integrated `052bbf9ac29a9c74163162f0f91adc2f6a656e4e` and contains no implementation. Blocked candidate `c51d637708c1e2ad24719e69d32ea87654c14473` remains unintegrated and excluded. Live Issue186 comment6617521783 and Project8 readback match the A goal/five todos/seven-doc scope/limits. Coordinator commit/push/integration/re-pin, exact-SHA preflight and independent checkpoint approval remain required before A implementation. The B archive checkpoint/source062d599/integratedb4953ef was synchronized at comment6617360191 and its independently approved offline implementation is integrated at052bbf9; that historical authority and unverified future-publication gate are preserved. A22/B8 ownership and R6/browser/application acceptance remain unchanged.

Goal: Replace the unsafe passive schema ledger read with fixed catalog-only observation and adversarial fake-exec tests; keep schema, service and deploy readiness unavailable until a separately approved stable catalog-before-ledger protocol exists.

The [canonical exact v2 contract](../superpowers/plans/2026-11-03-workshop-hosting.md#exact-v2-response-and-validation-contract) fixes five response fields: integer protocol_version=2, phase=catalog, identity, rights and ledger_relation. All exact nested fields/types/ranges, duplicate/unknown/null/UTF-8/depth/member/string/numeric/capture rejection rules and unchanged exit3/exit5 behavior are normative there. AM/index metadata is explicitly deferred; no heap/index/execution safety or DDL stability is attested. v1, relabeled v1, ledger-bearing and cached/offline transcripts are rejected.

The fixed socket-only role retains SELECT-only least rights, with explicit database-owner/PUBLIC/column/MAINTAIN/type/RLS checks, future HBA/ident provisioning and no admin/password fallback. Query only built-in pg_catalog metadata, never public.schema_migrations data or application code. Valid catalog observations still leave checks.schema=false, services=false and runtime_evidence=false; deploy check exits3 missing_dependency. The catalog collector/validator return None and cannot promote schema success; offline ledger validation is disconnected from runtime dispatch. No new grants, lock helper, interactive stdin, secret mounts or readiness/start/resume/maintenance authorization.

The rejected candidate read the ledger before catalog validation. A two-SELECT ACCESS SHARE repair cannot provide complete DDL stability: SELECT-only authority cannot obtain the stronger locking needed to exclude index changes. A full snapshot/locking/privilege protocol is separately gated; read-only transaction flags alone do not prevent application code or external side effects. Docker mounts still do not attest effective PostgreSQL configuration.

Only runtime-check.py and test_host_runtime.py are the prospective A implementation scope after this committed, pinned and independently approved passing gate; no implementation is included here. Operations/runbook changes remain coordinator/B-owned. All tests are fake-exec, not actual PostgreSQL/host/cloud/provider evidence. B checkpoint062d599 and its approved offline implementation are integrated at this base; preserve its synchronized comment6617360191, future-publication gate, existing B workflow and R6/browser/application acceptance requirements.

Concrete todo (same task/record):

- [ ] Synchronize the reviewed catalog-only correction and blocked c51d637 evidence across Issue186, Project8 and seven canonical files including the coordinator queue; commit/push, independently review and pin a new passing preflight checkpoint before builder dispatch.
- [ ] Modify only runtime-check.py and test_host_runtime.py to remove all live ledger reads, implement the fixed built-in-catalog-only v2 observation, and retain fixed identity/auth/bounds/reinspection without new grants/helpers or interactive stdin.
- [ ] Add red/green fake-exec tests proving no ledger SQL is sent for any catalog fixture, including view/foreign/RLS/custom type/custom AM/expression index and concurrent-change transcripts; preserve all existing applicable offline tests.
- [ ] Run focused tests, syntax, scope/diff and pinned preflight; commit/push a coherent two-path candidate and obtain exact-SHA independent review before integration.
- [ ] Keep schema/services/runtime_evidence false and all mutation/deploy verbs blocked; any stronger lock privilege, provisioned helper, persistent interactive client, effective auth proof or real PostgreSQL/Docker/cloud execution needs separate approved scope/gate.

Coordinator integration index: [Issue186 comment6617490673](https://github.com/lucronn/autodata/issues/186#issuecomment-6617490673) records root052bbf9 and B/R6 integration. It is integration history only; A v2 goal/todos are now separately synchronized by comment6617521783 and matching Project8 readback.

Tracking receipt: [Issue186 comment6617521783](https://github.com/lucronn/autodata/issues/186#issuecomment-6617521783), [Project8](https://github.com/users/lucronn/projects/8) item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4`, field `Source or dependency reference`, read back at `2026-11-03T22:52:39.567389+00:00`. Exact comment SHA256 `a4164a5bf2dc5edf986ed95aed7b26e8ace7419f3e576fbb8e49bae3dd319df1`; Project text SHA256 `78148627386a398901d82a8b2e5577c51cd2a32958e99c43c24513572415396a`. The compact Project index retains historical A/B/R6/current integration references and points to the full exact A goal/five todos/scope. Tracking synchronization is plan-only; no builder dispatch or live operation is authorized.


## PostgreSQL17 schema observation harness successor: planning checkpoint

Goal: Prove a bounded catalog-before-ledger protocol under an explicit ledger-only MAINTAIN capability in a disposable PostgreSQL17 adversarial harness; preserve the production catalog-only v2 collector and every release/readiness denial.

Canonical decision-complete plan: `docs/superpowers/plans/2026-11-03-workshop-schema-observation-harness.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-schema-observation-harness.json`; record `docs/agents/records/2026-11-03-workshop-schema-observation-harness.json`. Source base `ee57cd13a2f4e0a15d9e1212acfd1779451a4a91`. This successor leaves integrated catalog-only v2 (`5bf59c2`, gate `3a511f1`) intact and excludes `c51d637`. It proposes only a disconnected module plus pure tests and an opt-in disposable local PG17/C-sentinel harness. Separate test-only autodata_schema_probe has ledger SELECT+MAINTAIN, no ownership/memberships/writes; trusted NOLOGIN autodata_schema_owner owns the ledger. Strong lock before first snapshot, complete catalog validation before ledger bytes, actual positive sentinel controls, concurrent DDL barriers and server idle cleanup are required. MAINTAIN is explicit maintenance authority; production autodata_metrics and provisioning remain unchanged. No production helper, grant, collector integration, Docker/cloud/provider/DNS action or readiness claim. Independent coordinator review and pinned passing preflight remain required before any builder dispatch.

Prospective implementation allowlist: `infra/deploy/gce/schema_probe.py`, `infra/deploy/gce/test_schema_probe.py`, `infra/deploy/gce/test_schema_probe_pg17.py`, `infra/deploy/gce/testdata/schema_probe_sentinel.c`, `infra/deploy/gce/testdata/schema_probe_fixtures.sql`. DTO/browser/R6 and all existing runtime/operations implementation paths are excluded.

Concrete todo:

- [ ] Synchronize this exact harness goal, privilege decision, five-path implementation allowlist, tests and release limits in Issue186/Project8 and canonical documents; commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing pure transport/state-machine tests and implement the disconnected fixed-SQL schema_probe module with lock-before-snapshot catalog validation, bounded ledger framing and rollback-only cleanup.
- [ ] Build the local-only PG17 harness and C sentinels with a non-owner SELECT+MAINTAIN probe role and trusted NOLOGIN ledger owner; demonstrate every sentinel fires in an intentional negative control before testing observer rejection.
- [ ] Run actual disposable PG17 safe/hostile relation, index, privilege, concurrent DDL, first-snapshot and abandoned-session cases; retain red/green receipts, hashes and cleanup proof without running application services or contacting providers.
- [ ] Run focused regressions, scope/diff and exact-base preflight; commit/push a coherent candidate for independent exact-SHA review, keeping production grants, collector integration, authenticated publication, services, deployment and cars.tk cutover behind later gates.

Tracking synchronized by live Issue186 body/comment6618084753 and Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference` readback at `2026-11-03T23:26:27.924126+00:00`. Exact goal, five todos and five-path scope match the full issue body/comment; the compact Project index links that comment and retains historical DTO/A/B/R6 references, with its previous text preserved verbatim there. Dedicated record stores SHA256 readback hashes. Independent checkpoint review remains pending; synchronized tracking does not authorize a builder or live operation.


## Disconnected publisher and fixed host-check successor: planning checkpoint

Goal: Implement concrete disconnected publisher orchestration for fixed checkout, three image builds/pushes, SBOM/provenance verification and release artifact upload through injected executor/transports, plus a bounded fixed IAP host check; preserve all live execution and readiness denials.

Status: synchronized after live Issue186 comment6621071257 and matching Project8 readback. Source base `eddcf724028683dbb083191e4f8c42064b866bf0`. Canonical decision-complete plan: `docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-transport.json`; record `docs/agents/records/2026-11-03-workshop-publisher-transport.json`. This additive successor preserves historical A/B/PG17 authority. It proposes concrete injected-executor checkout/build/push/SBOM/provenance/upload orchestration, deterministic inner ZIP production and one fixed IAP `deploy.sh check SHA` request. Implementation allowlist is cloud-ops.py, test_cloud_ops.py and this operations runbook. No workflow/runtime-check/deploy/grants/application edit or real image build/publication/transport/signature verification, cloud/provider/container execution or readiness promotion is authorized. Fake interfaces exercise the complete production operation order; authentic adapters remain separately gated. Actual GitHub artifact download compatibility and authenticated publication remain unverified; the historical B future_publication_gate is unchanged. Valid host replies remain unavailable with schema/services/runtime_evidence false. Owner identities and production/paid/browser acceptance remain separate requirements.

Concrete todo:

- [ ] Synchronize this exact publisher-orchestration/host-check goal, three-path allowlist, fixed checkout/build/push/evidence/upload operations, trust/DTOs and five todos in Issue186/Project8 and canonical documents; preserve prior Project index, commit/push and pass pinned preflight before independent coordinator gate review.
- [ ] Add failing fake-executor publisher sequencing tests and implement fixed source checkout, three digest-bound build/push operations and post-build registry identity verification; no real executable, network or credential discovery may run.
- [ ] Implement deterministic inner release.zip production, bounded SBOM/provenance publish/verify and artifact upload/readback through injected interfaces, with versioned independent transport/payload/member/manifest digests and adversarial identity/subject/signature fixtures.
- [ ] Add failing fixed IAP host-check tests and implement only the configured VM deploy.sh check SHA request with strict failed-readiness receipt handling; keep every mutation, schema/service/runtime readiness and CLI/workflow activation unavailable.
- [ ] Run focused B and unchanged A regressions, syntax, scope/diff and pinned preflight; commit/push coherent candidates for independent exact-SHA review, retaining red/green evidence and actual authentication/archive compatibility, owner/provider, staging and paid-product gates.

Tracking synchronization, committed pinned preflight and independent coordinator review remain required before implementation dispatch.


Publisher successor tracking readback: [Issue186 comment6621071257](https://github.com/lucronn/autodata/issues/186#issuecomment-6621071257), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:40:50.163236+00:00`. Exact issue body/comment and Project index SHA256 hashes are retained in the dedicated publisher record. Prior Project index is preserved verbatim with hash in that comment. This is synchronized planning only; committed pinned preflight and independent coordinator review still precede any builder dispatch. No implementation or actual publication evidence exists.


## Migration-only publisher build argument correction: planning checkpoint

Goal: Correct only the disconnected publisher migration build argv to pass POSTGRES_IMAGE from the reviewed immutable manifest postgres reference before --file; preserve other-role argv, fake-only execution and every authority/readiness denial.

Status: synchronized after live Issue186 comment6621206696 and matching Project8 readback. Source publisher candidate `30cab10e548a3e078055b08447253ea90cc36bdc` (draft PR189). Dedicated plan `docs/superpowers/plans/2026-11-03-workshop-migration-build-arg.md`, task `docs/agents/tasks/2026-11-03-production-release/workshop-migration-build-arg.json`, record `docs/agents/records/2026-11-03-workshop-migration-build-arg.json`. This successor changes only the previously frozen build_migration vector: insert `--build-arg`, `POSTGRES_IMAGE=` plus the already validated immutable `manifest.images.postgres.reference` immediately before `--file`. API/ingestion argv remain exact originals. Future implementation allowlist is cloud-ops.py, test_cloud_ops.py and runbook; no Dockerfile/schema/workflow/runtime/PG17/R6 edit. Exact fake-argv/digest-propagation/ambient-ignore/no-default/invalid-reference-before-callback tests are required. No real build/PG17 compatibility/publication evidence is claimed; every existing simulation, live-operation and readiness denial remains. Historical publisher/PG17/R6 checkpoints are preserved; this correction cannot authorize their expansion.

Concrete todo:

- [ ] Synchronize this exact migration-only build-argument correction, three-path future scope and five todos in Issue186/Project8 and canonical documents, preserving the full prior Project index verbatim/hash; commit/push and pass pinned preflight before independent plan review and coordinator dispatch.
- [ ] Add failing exact fake-executor argv tests proving only build_migration receives --build-arg POSTGRES_IMAGE=<manifest.images.postgres.reference> immediately before --file while api/ingestion retain their existing complete argv.
- [ ] Implement the migration-only argument in cloud-ops.py from the already validated immutable manifest; reject missing/tag-only/malformed postgres references before callbacks and ignore all ambient/default POSTGRES_IMAGE or caller build-argument overrides.
- [ ] Run fake digest-propagation, no-fallback and unchanged publisher/host regressions, document that no Docker build or PostgreSQL17 runtime compatibility is proved, and retain every red/green/failure receipt outside the checkout.
- [ ] Run focused B/A suites, syntax, diff/scope and pinned preflight; commit/push a coherent three-path candidate for independent exact-SHA review without integrating, activating workflows, accessing credentials or running any real build/cloud/provider/host operation.

Commit/push, pinned preflight, independent exact-plan review and coordinator dispatch remain required before code.


Migration-only correction tracking: [Issue186 comment6621206696](https://github.com/lucronn/autodata/issues/186#issuecomment-6621206696), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T02:50:39.563760+00:00`. The dedicated correction record stores exact body/comment/index hashes; the comment preserves the prior index verbatim/hash. This is plan-only synchronization; committed pinned preflight, independent exact-plan review and coordinator dispatch still precede implementation. No code or live execution is authorized by this checkpoint alone.

### Disconnected migration build argument correction

The injected publisher now supplies migration's required base explicitly as
`--build-arg POSTGRES_IMAGE=<manifest.images.postgres.reference>` immediately
before `--file`. The value comes only from the already validated immutable
manifest reference. API and ingestion keep their previous complete command
vectors. Ambient `POSTGRES_IMAGE`, Dockerfile defaults and caller build-argument
maps cannot select or replace this base; invalid reviewed input is rejected
before any executor or transport callback.

Fake-executor regressions verify exact placement, digest propagation, ignored
ambient values and rejection with zero callbacks. They prove the requested base
identity, not the contents of an observed image. No Docker build was run, and
PostgreSQL17 client/runtime compatibility, PG17/pgvector ABI, authenticated
publication and deployment remain unproved. CLI/workflow `missing_dependency`,
`simulation:true`, `provenance_authenticated:false`,
`deployment_authorized:false` and schema/services/runtime-evidence denials stay
unchanged. This correction follows the dedicated migration build-argument plan
at checkpoint `d1c0969b30966a75d9e08714e231d9d87cd12087`.


## Workshop authenticated publisher adapter successor: planning checkpoint

Goal: Build bounded real GitHub Actions artifact, registry/evidence and fixed IAP check adapters behind an independently controlled activation boundary, preserving all production and runtime readiness denials.

Independently approved pre-sync design SHA256 `2e17c0e153ead31ae71e67b535b5d1d46b3ec10f401b8c3883773fe8c1aa4142`. Source base `1a0e2740171e6e0a2aa0bbc97a36299ecbf2106c` (publisher candidate30cab10 plus migration correction1a0e274); branch `codex/workshop-authenticated-publisher-plan`. This is a docs-only planning checkpoint; independent exact-checkpoint review and coordinator dispatch remain required before any implementation. Issue186/Project8 serialization follows PG17 acquisition-overlay gate26989e1/receipt80d4a20; those separate authorities, blockers and queue references are preserved.

Plan: `docs/superpowers/plans/2026-11-03-workshop-authenticated-publisher.md`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-authenticated-publisher.json`. Record: `docs/agents/records/2026-11-03-workshop-authenticated-publisher.json`. Canonical refs: `docs/superpowers/plans/2026-11-03-workshop-publisher-transport.md`, `docs/superpowers/plans/2026-11-03-workshop-hosting.md`, `docs/operations/workshop-gcp.md`, `docs/architecture/infrastructure-and-dev.md`, `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`.

Concrete actual-adapter scope: real bounded HTTPS/GitHub Actions official-toolkit upload/raw download/OCI registry/WIF/process/IAP adapters; build-once signed immutable candidate from approved source/config/four dependencies, independent signed complete-v1-manifest approval, then finalize without rebuild/copy/per-image evidence regeneration. Post-upload signed binding authenticates returned artifact ID, outer digest/length and exact originating run+attempt using fresh SDK UploadSession evidence and verified attempt-bearing signer URI; current run endpoint cannot establish artifact attempt. Preserve source/workflow SHA split, actual outer ZIP one release.zip vs unchanged inner two members, terminal digestMismatch/digest/expiry failure and older-attempt artifact rejection despite identical inner bytes. Carry independently supplied bounded rollback_manifest through candidate/finalize/verify/host revalidation with unchanged v1 invariants and canonical approved hash; never invent image/evidence hashes or silently rewrite approval. Migration POSTGRES_IMAGE remains explicit immutable reviewed input.

Future implementation allowlist (exact9 paths):
- `infra/deploy/gce/publisher_adapters.py`
- `infra/deploy/gce/publisher_artifact.mjs`
- `infra/deploy/gce/publisher-toolkit/package.json`
- `infra/deploy/gce/publisher-toolkit/package-lock.json`
- `infra/deploy/gce/test_publisher_adapters.py`
- `infra/deploy/gce/test_publisher_artifact.mjs`
- `infra/deploy/gce/test_release_workshop_contract.py`
- `.github/workflows/release-workshop.yml`
- `docs/operations/workshop-gcp.md`

Owner identities/protected environments/resources/WIF/IAM, toolkit/tool/action/Sigstore pins, approved origins and actual artifact compatibility semantics, upstream evidence policy, independent manifest-approval public key and fixed host-key/remote deadline proof are prerequisites to separately authorized staging. Code/tests may implement the real paths using injected fake/local process/transport/crypto dependencies; no live credentials or operation is authorized here. Existing production publish/deploy jobs and cloud CLI remain blocked; staging definitions retain unconditional precredential blockers. No schema/services/runtime_evidence readiness, provider/cloud/registry/host/build/upload/signing/staging/production activation, integration, deployment or owner policy installation is authorized by this planning checkpoint.

Concrete todo:
- [ ] After accepted migration review and root tracking release, synchronize the authenticated adapter-only goal, v3 identity/digest contracts, exact allowlist, five todos and activation exclusions across Issue186/Project8/canonical docs; commit/push, pin and independently review a machine-passing checkpoint before implementation.
- [ ] Implement bounded authenticated I/O, strict real-wire projections, separate workflow/source identity, official-toolkit single-file upload, original outer ZIP decoding and post-upload signed originating-attempt binding with terminal digestMismatch/expiry/digest/older-attempt rejection; retain every existing v2 and CLI denial.
- [ ] Implement actual build-once registry candidate push/SBOM/provenance verification, independent manifest approval and rebuild-free finalization plus separate fixed IAP check library, preserving independently supplied bounded v1 rollback_manifest through every phase and migration POSTGRES_IMAGE, credential/issuer/audience separation, pinned trust/tooling and bounded cleanup; reject candidate/approved-manifest/rollback mismatch without rewriting approval.
- [ ] Add adversarial fake/local contract tests and a dormant protected staging workflow definition with unconditional precredential blocker; preserve unchanged production jobs, false readiness and all existing application/schema/deploy authority boundaries.
- [ ] Run focused regressions, syntax/scope/diff and pinned preflight; commit/push coherent candidates for independent exact-SHA review, document missing owner/tool/origin/host/staging evidence and stop before any activation or live operation until a separate synchronized gate authorizes it.


Tracking readback: [issuecomment-6621425159](https://github.com/lucronn/autodata/issues/186#issuecomment-6621425159), Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` field `Source or dependency reference`, verified `2026-11-04T03:06:38.051955+00:00`. Exact body/comment/Project/prior-index hashes are in the dedicated synchronized record. Full predecessor Project index SHA256 `4e26f3831956fb10f26a64e5b791e27f502a35e3ead19015622e118d22dfec20` is preserved verbatim in that comment. This synchronizes planning only; committed full-SHA preflight, independent exact-checkpoint review and coordinator dispatch still precede implementation. No staging or production activation.

### Authenticated-v3 Python library delivery boundary

`infra/deploy/gce/publisher_adapters.py` adds separate candidate, finalization,
independent verification and fixed host-check library entry points. None has an
executable activation path or obtains ambient credentials. An absent owner
policy or installed dependency implementation raises the fixed
`missing_dependency` error before credential/transport callbacks. Dependencies
are trusted Python adapter implementations supplied by reviewed control code;
they are not wire JSON, approval booleans, v2 receipts, or caller-selectable
providers. Their `prepare` operation must perform offline policy/tool/trust
checks only. No credential acquisition belongs in `prepare`.

The current delivery contains actual bounded child-process/private-file and
HTTPS download primitives, strict run/context projections, OCI byte/digest-chain
verification, the stored/deflate ZIP32 outer decoder, a pinned detached Cosign
approval-verifier contract and phase orchestration tested with local transports.
The default WIF exchange, OCI push, Syft/Sigstore signing and keyless certificate
extension/transparency verification composition is **not installed**. The
orchestration's signing and evidence operations therefore require separately
reviewed implementations; passing offline tests is not evidence that these real
provider operations are implemented, activated or accepted. Real binary/CA/root
pins, independent approval public keys, upstream evidence policy, verified
Actions origins/digest/size semantics and remote host deadline/cleanup proof
remain dependencies. No live Cosign, cloud, registry, toolkit, host, credential
or provider operation was run for this Python delivery.

Finalization constructs the source and post-upload statements itself, compares
the complete independent v1 approval, and exposes no build/copy/retag/evidence
regeneration method. It returns `uploaded_unaccepted`. Only a later verifier
with installed authenticated signature/transport adapters can return
`publication_verified`; deployment and schema/services/runtime-evidence remain
false. Test-only keyed signature fixtures exercise older-attempt rejection and
fresh-attempt acceptance; they do not authenticate GitHub or Fulcio. The pinned
Cosign command contract is separately tested against a local executable fixture
that verifies actual generated RSA signatures with OpenSSL, not a live Cosign
installation.

The outer artifact SHA256 always covers the original downloaded Actions ZIP.
The inner SHA256 covers its sole `release.zip` member, and the two member hashes
cover unchanged `release.json`/`images.json`. No extraction or independently
supplied inner bytes substitute for that envelope. A fresh official-helper
upload observation commits run ID, attempt, fixed filename/options and inner
hash/length; the signed post-upload core commits the returned artifact ID and
outer bytes. A valid old-attempt signature is rejected even when source and
inner bytes match. The separately supplied rollback manifest remains outside
the two-member archive and must match the independent canonical approval hash.


## Dormant publisher Python review correction checkpoint

Goal: Correct the dormant Python publisher library's missing upload-pin acceptance, FIFO open hang and SIGTERM child leak without adding live publication or activation authority.

Source candidate `d94b2a4a77aad1cd7f3d62514e4c20729ba4cd39` has three independently reproduced findings: P1 missing/null toolkit-lock and runtime-origin pins can yield accepted publication; P2 private_read blocks opening an owned0600 FIFO; P2 owner SIGTERM bypasses cleanup and leaves its isolated child alive. This checkpoint is docs/tracking only. Plan `docs/superpowers/plans/2026-11-04-workshop-publisher-python-review-corrections.md`; record `docs/agents/records/2026-11-04-workshop-publisher-python-review-corrections.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-python-review-corrections.json`; canonical operations notes `docs/operations/workshop-gcp.md`. Implementation allowlist is only publisher_adapters.py/test_publisher_adapters.py under infra/deploy/gce and additive operations notes. No implementation correction precedes committed full-SHA passing preflight, independent checkpoint review and fresh coordinator dispatch.

Concrete todo:

- [ ] Synchronize this three-defect correction goal, exact source/allowlist and todo across Issue186/Project8/canonical operations notes; preserve the previous Project index verbatim/hash; commit/push, pin full-SHA preflight, and stop for independent checkpoint review and fresh coordinator dispatch.
- [ ] After dispatch, add red/green regressions for missing/null/empty/malformed upload owner pins and observations; require typed canonical HTTPS origin and lowercase64 toolkit SHA before finalize/verify callbacks, preserving a valid fresh signed positive control.
- [ ] Add a subprocess-isolated FIFO red/green regression with an external test deadline; open private outputs nonblocking/no-follow and reject every nonregular output before reading, retaining existing ownership/mode/link/size/digest guards.
- [ ] Add owner-boundary SIGTERM red/green regressions for an ordinary child and a SIGTERM-ignoring child; install and restore bounded main-thread cancellation ownership around process creation through cleanup, reject unsupported thread/mask ownership before spawning, and prove owned child termination/reaping.
- [ ] Run focused and existing Python regressions, syntax, exact-scope/diff and pinned preflight; commit/push coherent verified corrections for independent exact-SHA review, retaining every no-live/default-dependency/readiness limitation.

Default WIF/OCI push/Syft/keyless Sigstore certificate/transparency composition remains uninstalled. No workflow, toolkit, cloud, registry, provider, host, Docker, credentials, activation, integration or deployment is authorized. Source/workflow/run-attempt separation, original outer/inner/archive/member identity, independent full-manifest approval and separate rollback input remain intact; all production/runtime readiness remains false. Prior Project index SHA256 `b8bca1611e3ed2563fb5ce71bfacbde542ee1f069e7ffd4c08f131fc30e4d26b` is preserved verbatim in the synchronization comment; every unrelated PG17/DTO/R6/activation history remains unchanged.

Correction tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6621647909; prior Project index SHA256 `b8bca1611e3ed2563fb5ce71bfacbde542ee1f069e7ffd4c08f131fc30e4d26b` preserved verbatim. Dedicated record stores verified Issue/comment/Project hashes. No implementation changes or activation occurred during this correction checkpoint.


## Dormant publisher SIGTERM ordering amendment checkpoint

Goal: Correct the dormant Python publisher executor's SIGTERM child leak without passing a blocked SIGTERM mask to its child or changing live-publication authority.

Source is pushed Python `f01efeea8b678fc5c16a97d759dbe4a7ae85f107`, retaining upload-pin fix `a1af0b2` and FIFO fix `f01efee` under reviewed correction gate `de57baa0f70e363227cf0c446a6aadec10ec7c59`. Coordinator technically reviewed amendment design SHA256 `a80ede2bdc08a43664b5019b48fca4316ce71d0610bca13c8ed4757d93a8d482`. Plan `docs/superpowers/plans/2026-11-04-workshop-publisher-sigterm-ordering-amendment.md`; dedicated record `docs/agents/records/2026-11-04-workshop-publisher-sigterm-ordering-amendment.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-sigterm-ordering-amendment.json`; canonical operations notes `docs/operations/workshop-gcp.md`. Scope is only publisher_adapters.py/test_publisher_adapters.py and additive ops notes; this checkpoint changes documentation/tracking only.

A local POSIX probe confirmed that blocking SIGTERM through Popen passes the blocked mask into the child. This amendment replaces only the previous plan's literal blocked-through-Popen mechanism: a temporary main-thread handler records a cancellation flag, the saved unblocked mask is restored before spawning, and pre-spawn/post-assignment/100ms I/O/final-wait checks raise fixed cancellation inside bounded cleanup. The handler never raises across Popen assignment. Cleanup blocks further SIGTERM, terminates/kills/reaps only the owned group, closes pipes, restores prior handler/ownership and restores the original mask last, so pending delivery follows the caller's policy only after cleanup. Explicit actual-child mask and pending/assignment/cleanup race tests are mandatory; no unsafe preexec hook or executable bootstrap is introduced.

Concrete todo:

- [ ] After tracking-slot release, synchronize this signal-ordering amendment, source/allowlist and todo across Issue186/Project8/canonical operations notes; preserve the previous Project index verbatim/hash; commit/push, pin full-SHA preflight, and stop for independent checkpoint review and coordinator dispatch.
- [ ] After dispatch, restore the preserved owner-boundary red tests and add cancellation-before/inside-Popen assignment, inherited child-mask, pending-signal cleanup/restoration and nested-owner regressions with bounded local probe cleanup.
- [ ] Implement main-thread cancellation-flag ownership with the exact pending-signal/Popen ordering and bounded group cleanup below; reject blocked-mask, non-main-thread and nested ownership before spawning.
- [ ] Run red/green signal tests and all focused Python regressions, syntax, exact-scope/diff and pinned preflight; commit/push the exact candidate for independent review while preserving no-live/readiness/default-dependency limits.

No signal implementation precedes full-SHA pinned preflight, independent checkpoint review and coordinator dispatch. Preserved red tests remain local evidence. No cloud/registry/provider/host/Docker/live toolkit/credential/activation/integration/deployment operation; default WIF/OCI/Syft/keyless certificate/transparency composition remains uninstalled; all runtime/production readiness false. Full current PG adoption index and detail are preserved verbatim in the synchronization comment: index SHA256 `329f8d8db203c0b00101e9244aa4514392faddf01dea720bcdbd8287207cdc08`, detail SHA256 `c30cea4816f7ae6f78edf7ab2770caf9d081e7267fa71bb635f966ab3a3f674c` (https://github.com/lucronn/autodata/issues/186#issuecomment-6621749496). PG mount-order adoption gate `3c96b04df9ff4b7929ca8955a92d89eef6cc7617`, JS artifact boundary `cb245b7aa700fee0eda1e2eb912141427cb3411e` and every unrelated authority/history remain unchanged.

Signal amendment tracking readback: https://github.com/lucronn/autodata/issues/186#issuecomment-6621768448; full CURRENT PG adoption index SHA256 `329f8d8db203c0b00101e9244aa4514392faddf01dea720bcdbd8287207cdc08` and detail SHA256 `c30cea4816f7ae6f78edf7ab2770caf9d081e7267fa71bb635f966ab3a3f674c` preserved verbatim. Exact tracking hashes are in the dedicated record. This checkpoint changes documentation only and preserves the pushed upload-pin/FIFO corrections.


## Stage0 dormant publisher integration synchronized checkpoint

Goal: Integrate the exact corrected dormant Python and Actions artifact publisher candidates while preserving reviewed implementation bytes and every activation blocker, then verify the combined offline contracts.

Planning baseline `101f7d6e2a2795206f16b4419fe561cad531071e`; artifact source `bba43a0675628db3ac90ca7c72bc47eb8c381cb0`; common ancestor `b431e548df4f379f6752e021c6fb42e8837a5311`. Plan `docs/superpowers/plans/2026-11-04-workshop-publisher-stage0-integration.md`; record `docs/agents/records/2026-11-04-workshop-publisher-stage0-integration.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage0-integration.json`. Intended references: https://github.com/lucronn/autodata/issues/186 and https://github.com/users/lucronn/projects/8. The coordinator authorized docs-only tracking synchronization after staging M1 released at receipt5bd9b82; verified readback and preservation evidence are recorded below. This checkpoint is not implementation dispatch. The only future three-way conflict is this operations guide; retain both complete source histories plus this note. All implementation blobs must retain their selected exact-source bytes. No executable factory/worker, SDK/cloud operation or activation is included.

Concrete todo:

- [ ] After the coordinator releases the serialized tracking slot, synchronize this Stage0-only goal, exact source tuple, allowlists and todo across Issue186/Project8/canonical operations notes; preserve the immediately current full PG index/details verbatim with hashes; commit the synchronized checkpoint and pass full-SHA preflight for independent review and coordinator dispatch.
- [ ] After independent exact-checkpoint review and dispatch, merge only artifact bba43a0675628db3ac90ca7c72bc47eb8c381cb0 into the checkpoint descended from Python 101f7d6e2a2795206f16b4419fe561cad531071e; resolve only docs/operations/workshop-gcp.md by retaining both source histories and the new Stage0 note.
- [ ] Prove every integrated implementation blob equals its selected source, cloud-ops.py and all other implementation files remain unchanged, production jobs and staging blockers retain their reviewed definitions, and all historical gate files retain their original bytes.
- [ ] Run the combined offline Python publisher, cloud/host/workflow and reviewed Node artifact suites plus syntax, exact-scope, diff and pinned-gate checks; record actual results without adding or modifying tests.
- [ ] Commit and push the validated dormant integration milestone for independent exact-SHA review, retaining missing dependency, owner trust, authenticated worker, dependency factory, toolkit advisory/license and staging/production activation blockers.

Record status is synchronized after verified Issue/Project readback; a committed full-SHA passing preflight is still required. Independent source/checkpoint review, serialized tracking readback, committed synchronized checkpoint, full-SHA passing preflight and coordinator dispatch precede implementation. Publication, runtime readiness and staging/production activation remain false.

Stage0 synchronization verified 2026-11-04T04:07:54.663787+00:00: https://github.com/lucronn/autodata/issues/186#issuecomment-6622268742. Prior full index SHA256 `acfd6664aec1798bf581fed620f185faf4155896ddb77674664ea7d1b2a9b33a`; complete staging M1/PG/artifact details and pins are preserved verbatim/hash in `docs/agents/records/2026-11-04-workshop-publisher-stage0-integration-evidence.json` and linked preservation comments. Current Project text SHA256 `cc28ab97ee9d02b678552c2303171b73b6e528c88d8ed5ed79d1ffc049649b07`. Issue body unchanged. Local draftc2ebdbc passed scoped independent review; committed exact-checkpoint review/dispatch pending. No implementation, SDK/cloud or activation.

Exact synchronized checkpoint `dc1ba895d5761ca8ed5d3ff19f645b654655ae3c` pushed; full-SHA preflight exit0 returned `{"status":"synchronized","errors":[]}`. Pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622281057 read back 2026-11-04T04:08:26.452850+00:00; final Project index SHA256 `2d8c4a31f378c74200ec22a5ebc0f44876c1e02b287a9ddcb5c48d15a7413e24`. Independent exact-checkpoint review and coordinator dispatch remain required; no implementation merge or activation occurred.

## Dormant staging workflow regression assertion amendment

Scope legacy cloud-workflow production assertions to production jobs while retaining strict dormant staging checks and every activation denial.

Plan: `docs/superpowers/plans/2026-11-03-workshop-staging-workflow-regression-amendment.md`; record: `docs/agents/records/2026-11-03-workshop-staging-workflow-regression.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-staging-workflow-regression.json`. Issue186/Project8 track this additive test-only amendment at candidate `e9faaf594ecd671e113190fe0c57229d9824ad04`. The143-test focused run has one retained legacy production-loop assertion failure;52 Node tests and five dedicated staging tests pass. Only the named legacy test in test_cloud_ops.py may gain an exact release-job inventory and apply its unchanged production invariants to publish/deploy. Dedicated staging checks and frozen production job hashes remain required. No workflow/CLI/runtime/credential/toolkit/deploy behavior changes or activation follows.

Concrete todo:

- [ ] Synchronize the narrow test-only amendment across Issue186, Project8 and canonical docs; commit and pass pinned preflight before correction.
- [ ] Limit legacy release-loop production invariants to publish/deploy, retain all their assertions, and reject unknown release jobs alongside dedicated dormant staging checks.
- [ ] Run retained red/green workflow, cloud and host regressions plus Node/syntax/scope checks; push for independent exact-SHA review without activation.


## Artifact helper independent-review corrections: planning only

Authenticate installed toolkit bytes and enforce an owned process-and-pipe termination boundary plus nonblocking archive preflight while preserving dormant publisher execution.

Candidate `a2453848ed596a00574d63a2ca5cc77d28464c99` remains dormant and is not accepted as a runnable authenticated publisher. Retained review proves replacement toolkit code can bypass metadata-only checks, cancelled SDK work can continue/log after return, and a FIFO can hang before deadline. Plan `docs/superpowers/plans/2026-11-03-workshop-artifact-boundary-corrections.md`; record `docs/agents/records/2026-11-03-workshop-artifact-boundary-corrections.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-boundary-corrections.json`. Only publisher_artifact.mjs and its Node test may change after a new synchronized pinned gate, independent review and coordinator dispatch. The correction binds all installed/transitive bytes to an independently approved read-only tree, owns/terminates/reaps the actual SDK child and closes private result/log pipes before return, and rejects special archive files with nonblocking bounded descriptor checks. Default CLI and staging/production blockers, lock/runtime pins, seven moderate advisories and unresolved buffers licensing remain. No real owner manifest/policy, credential, SDK network action, workflow or runtime activation follows.

Concrete todo:

- [ ] Synchronize the three review findings, exact two-file correction scope and retained red evidence across Issue186, Project8 and canonical docs; commit and pass pinned preflight for independent review before implementation.
- [ ] Bind a complete independently approved installed package-tree manifest to the exact reviewed lock and immutable toolchain; reject package or transitive file drift before import or runtime credential use.
- [ ] Replace in-process SDK callbacks and Promise-only cancellation with one fixed verified child process, private result pipe, bounded log pipes, termination and reap proof before any cancellation or upload result returns.
- [ ] Open release.zip nonblocking and no-follow, reject nonregular or replaced files, and put filesystem preflight under the same deadline and cleanup reserve.
- [ ] Run real local tamper, late-output, process-group, cancellation, deadline, overflow and FIFO red/green regressions plus existing focused suites; push exact candidates for independent review with every activation denial and audit limitation intact.


## Artifact verified-worker deadline correction: planning only

Bound verified-worker revalidation by the original operation deadline and cancellation ownership, and prohibit child spawn after expiry or cancellation while preserving dormant publisher execution.

Candidate `bf7bb67bfbdca3b8186bb56d603cf4dee7e4116b` closed the original installed-tree/process/FIFO review findings (92 Node and143 Python tests), but approval is withheld for one P2: selected-worker revalidation is outside deadline/cancel bounds and may start a child after expiry. Retained synthetic probe shows spawnedAfterDeadline=true and cleanup_failed; it establishes no live/owner/immutable-toolchain evidence. Plan `docs/superpowers/plans/2026-11-04-workshop-artifact-revalidation-deadline.md`; record `docs/agents/records/2026-11-04-workshop-artifact-revalidation-deadline.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-revalidation-deadline.json`. Only publisher_artifact.mjs and its Node test may change after synchronized pinned gate, independent review and dispatch. Bind inspection waits/traversal/handle cleanup to one original-budget cancellation scope, preserve the cleanup reserve, and recheck deadline/abort immediately before fixed spawn. No live SDK or workflow action follows. Both CLI modes stay unconditional exit3 without stdin/ambient-token reads; owner trust, immutable-toolchain and seven moderate advisory/buffers-license blockers remain. Preserve CURRENT PG adoption index/detail verbatim/hash; any later closure index follows its independent audit and tracking-slot release.

Concrete todo:

- [ ] Synchronize the single revalidation finding, exact two-file scope and retained red probe across Issue186, Project8 and canonical docs; preserve the current PG adoption index/detail, commit and pass full-SHA pinned preflight for independent review before implementation.
- [ ] Add verified-descriptor-path deadline, abort and pending-inspection regressions that prove zero spawn and zero readback after the cutoff, using only a synthetic local toolchain and harmless OS child boundary.
- [ ] Thread one original-budget inspection scope through loader and file/tree awaits, own cancellation before revalidation, drain or fail cleanup for outstanding inspection work, and recheck deadline and cancellation immediately before the fixed spawn without resetting any budget.
- [ ] Run all existing Node and Python cloud/host/workflow suites plus syntax, exact-scope and pinned-gate checks; push the bounded candidate for independent exact-SHA review while retaining every owner, immutable-toolchain, advisory, licensing and activation blocker.


## Workshop artifact inspection close-failure correction: docs-only planning

Goal: Preserve cleanup_failed when an owned inspection handle fails to close, and never treat rejected inspection settlement as proof of successful cleanup.

Docs-only planning on candidate `220d9c3099e190c3a3dc60fde11c43b7300bda7c`; PG Task1B released tracking at receipt c16f40a2730e7bc8a5fb3afd3ac2d10abf551637. Plan: `docs/superpowers/plans/2026-11-04-workshop-artifact-inspection-close-failure.md`. Record: `docs/agents/records/2026-11-04-workshop-artifact-inspection-close-failure.json`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-artifact-inspection-close-failure.json`. Issue/Project tracking is synchronized; committed full-SHA preflight, independent exact-checkpoint review and coordinator dispatch remain required before implementation. No live action is authorized.

Independent review `/tmp/autodata-artifact-220d9c3-review.md` retains the earlier boundary/deadline fixes but withholds approval for failed handle close being mistaken for drained inspection. A real-FD offline probe returned operation_cancelled while its late-opened descriptor remained open. The proposed two-file-only correction retains explicit handle ownership and sticky cleanup_failed precedence across task settlement, cancellation, timeout and loader redaction. Real-FD red/green cases must independently close fixture descriptors after observing the public failure. Original shared cleanup budgets, zero late spawn, process-group/pipe closure and both unconditional CLI exit3 denials remain required. Owner/immutable-toolchain/authenticator/readback, seven moderate advisory and buffers license blockers remain.

Concrete todo:

- [ ] Synchronize the single close-failure finding and exact two-file scope across Issue186, Project8 and canonical docs after the coordinator releases the tracking slot; preserve the then-CURRENT PG index/details verbatim with hashes, commit and pass full-SHA pinned preflight for independent review before implementation.
- [ ] Add actual-file-descriptor regressions for cancelled late-open and ordinary inspection close failure, plus timeout and successful-close controls; prove cleanup_failed precedence, zero spawn/readback and bounded independent fixture cleanup.
- [ ] Retain explicit inspection handle ownership and sticky closure failure, distinguish task settlement from proved closure, and propagate fixed cleanup_failed through loader and operation cleanup without resetting budgets or weakening earlier guards.
- [ ] Run the full existing 103 Node and 143 Python tests plus new regressions, syntax, exact-scope and pinned-gate checks; push the candidate for independent exact-SHA review with all owner, immutable-toolchain, advisory, license and activation blockers retained.

Close-failure gate tracking: https://github.com/lucronn/autodata/issues/186#issuecomment-6622115738, verified 2026-11-04T03:56:17.962371+00:00. CURRENT PG Task1B full index and details6622084338/6622103154 preserved verbatim/SHA256. Separate PG review/adoption/root verification/dispatch and all quarantine/Task2 denials remain.


## Stage0 dormant publisher integrated state

The authorized Stage0 integration retains Python source `101f7d6e2a2795206f16b4419fe561cad531071e` and artifact source `bba43a0675628db3ac90ca7c72bc47eb8c381cb0` exactly, based on synchronized gate `dc1ba895d5761ca8ed5d3ff19f645b654655ae3c` and receipt `599dd7315644503e843def1c0dc5818c86b1524e`. The coordinator dispatched implementation after independent exact-checkpoint review and passing full-SHA preflight. Both complete source document histories above remain historical evidence; their earlier planning-only and pending-dispatch statements describe their original checkpoints.

Offline integration verification passed: Python publisher45 tests; cloud/host/workflow143 tests; Node artifact110 tests. Python syntax (six modules), both Node syntax checks, the ten selected implementation blob/hash comparisons, thirteen exact historical-document additions, all four protected workflow job definitions, exact merge scope and diff checks passed. Node runtime SHA256 is `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90` (reviewed Node22.23.4); Node tests ran from the repository root and Python tests from infra/deploy/gce. The separate Stage0 verification receipt records the resulting merge SHA and final-head checks.

Both CLI modes retain unconditional exit3/missing_dependency. Missing owner trust, authenticated official upload worker, dependency factory, immutable installed-tree/runtime/helper pins, seven moderate toolkit advisories, buffers licensing and staging/production activation remain blockers. Production/staging workflow job bodies and permissions are byte-identical to the selected artifact source. No dependency installation, SDK import, live upload, cloud/registry/provider/host/Docker operation, Issue/Project write, activation or deployment occurred; runtime/production readiness remains false. Independent exact-implementation review remains required.


## Publisher Stage1A offline trust: local planning draft

Accepted dormant Stage0 receipt `dde53d745f8422ce29d6e8b3d459f4a0b91ebd04` is the baseline for a narrower offline-only proposal. Plan: `docs/superpowers/plans/2026-11-04-workshop-publisher-stage1a-offline-trust.md`; technical spec: `docs/agents/specs/2026-11-04-workshop-publisher-stage1a-offline-trust.md`; record: `docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust.json`; task: `docs/agents/tasks/2026-11-03-production-release/workshop-publisher-stage1a-offline-trust.json`. This is an additive unsynchronized local draft, with no Issue186/Project8 write or implementation authority.

The proposed four new Node module/test paths verify exact-byte Ed25519 owner envelopes and RS256 GitHub OIDC claims against bounded immutable trust files using built-in crypto. Pure fixture records cannot mint installed-policy handles. Fixed root provisioning, actual owner key/digest/epoch, numeric IDs, exact protected subject/control SHA and authenticated JWKS snapshot remain owner-selected activation inputs. `authenticateActionsRuntime` always throws `missing_dependency` without reading credentials or arguments; verified OIDC never attests the Actions Results bearer. The existing uploader, both CLI modes and every workflow job/permission remain unchanged.

Concrete todo:

- [ ] Independently review this Stage1A-only contract and exact four-file implementation allowlist; retain Stage0 source bytes and every CLI/workflow denial.
- [ ] After the coordinator releases the serialized tracking slot, synchronize this goal, plan/spec/canonical notes and concrete todo across Issue186/Project8 without overwriting current PG or other lane evidence; commit the checkpoint and pass full-SHA preflight before coordinator dispatch.
- [ ] After a passing synchronized gate and dispatch, add strict bounded trust-file/policy verification using built-in Node crypto and real local Ed25519 fixtures; commit and push the validated milestone.
- [ ] Add bounded RS256 GitHub OIDC byte verification and installed-policy wrapper with exact claim/time checks, plus unconditional missing_dependency runtime-bearer authentication; commit and push the validated milestone.
- [ ] Run new offline crypto/filesystem negative suites and unchanged Stage0 regressions, syntax, exact-scope and frozen-byte checks; obtain independent exact-SHA review with fixture-only evidence and every activation blocker retained.

Runtime-bearer protocol, real immutable toolchain installation, seven moderate toolkit advisories, `buffers` licensing, SDK worker/factory/readback/WIF and staging/production activation remain blocked. Test keys and offline verifier results are not owner installation, provider acceptance, upload or runtime readiness evidence. Canonical preflight must reject this draft's `draft_unsynchronized` status; a real synchronized committed checkpoint and coordinator dispatch are required before implementation.


### Stage1A docs-only synchronization

Independent corrected draft `9ff1a36fb5fc6837a8699dabea69287316847a9d` passed review. After staging boot release `cf407381`, Issue186 detail https://github.com/lucronn/autodata/issues/186#issuecomment-6622550358 and Project8 were synchronized and read back 2026-11-04T04:28:01.132963+00:00. Full then-current Project index SHA256 `831c9c512f574c378ca88b9129fa2305a549a9a7062f3a67afecc7c865d1882e`, twelve boot/PG offline/Stage0/earlier source details+pins and six preservation-comment readbacks are retained verbatim/hash in `docs/agents/records/2026-11-04-workshop-publisher-stage1a-offline-trust-evidence.json`. Issue body is unchanged; prior status and authority remain unchanged.

Record status is synchronized for this offline-only four-new-file proposal. JWT.environment binds the protected GitHub environment workshop-staging-publish, while the product stage remains staging; every OIDC call revalidates the exact original owner trust bytes. Unsettled filesystem work yields bounded cleanup_failed with retained late-handle quarantine, never installed authority. Runtime bearer always remains missing_dependency. Commit/push/full-SHA preflight, independent exact-checkpoint review and fresh root dispatch are still required before implementation; no SDK/cloud/workflow activation or production authority follows. Exact checkpoint pin receipt follows after commit.


Exact synchronized checkpoint `38c6ffe420498fb3be5927df58dba6051f2df6f7` committed/pushed; full-SHA preflight exit0 returned `{"status":"synchronized","errors":[]}`. Exact pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622560758 and final Project index read back 2026-11-04T04:28:33.605452+00:00; index SHA256 `b37bb75e92fbb2bf448154464782067a88b2c97d2a26e376ed2fa856c95f4ec3`. The serialized tracking slot is released. Independent exact-checkpoint review and fresh root code-only dispatch remain required. No implementation, SDK import, cloud operation or activation occurred.


## Isolated staging bare-resource bootstrap M1: synchronized planning checkpoint

Goal: Create and read back only owner-approved isolated staging IPv4 address, empty persistent data disk and bare VM; preserve all application, deployment and production denials.

Canonical plan: `docs/superpowers/plans/2026-11-04-workshop-staging-lifecycle.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-bootstrap.json`; record `docs/agents/records/2026-11-04-workshop-staging-bootstrap.json`; preservation/evidence `docs/agents/records/2026-11-04-workshop-staging-bootstrap-evidence.json`. Source root `eddcf724028683dbb083191e4f8c42064b866bf0`; independently reviewed corrected draft `fb0c6f7a92b2580ae7bc993f827cfc2596a32743`.

Status: `synchronized` after live [Issue186 detail6622232881](https://github.com/lucronn/autodata/issues/186#issuecomment-6622232881) and [Project8](https://github.com/users/lucronn/projects/8) readback at `2026-11-04T04:04:56.410962+00:00`. Commit/push, full-SHA pinned preflight, independent exact-checkpoint review and fresh coordinator dispatch still precede implementation. Synchronization does not authorize cloud or host operations.

Exact prospective implementation allowlist:

- `infra/deploy/gce/cloud-bootstrap.sh`
- `infra/deploy/gce/staging_bootstrap.py`
- `infra/deploy/gce/staging-bootstrap.schema.json`
- `infra/deploy/gce/test_staging_bootstrap.py`

Only dedicated staging address+empty data disk+bare VM against approved preexisting VPC/IAM/APIs/registry. Strict owner approval, inherited metadata/image/network/effective-policy readback, fixed Compute GET/three POST bodies, deterministic requestId, ownership/idempotency, bounds and redacted receipts are defined in the plan. Only exact default0.0.0.0/0 via default-internet-gateway is exempt from Docker overlap checking; selected subnet/additional destinations must be disjoint, and extra routes remain denied. No IAM mutation, package install, disk format, secret delivery, application startup, production apply or readiness authority. Actual owner-selected GCP/billing/region/pins/staging-origin inputs and separate live authorization remain mandatory. Publisher/schema contracts and separately reviewed installation/startup/recovery gates are still required.

Concrete todo:

- [ ] Synchronize the exact bare-resource goal, four-file allowlist, approval/request/network/receipt contract and concrete todo across Issue186/Project8 and canonical documents; preserve current PG/JS index/detail/pins verbatim with hashes, commit/push and pass full-SHA pinned preflight before independent checkpoint review.
- [ ] After independent exact-checkpoint review and fresh coordinator dispatch, add offline failing tests for strict approval/token boundaries, exact request inventory, default-route exception and disjoint-subnet acceptance, overlapping-subnet/custom-next-hop rejection, ownership/idempotency, timeout/cancellation and redaction.
- [ ] Implement only the four allowlisted bootstrap files for the fixed staging-only Compute GET and three POST operations, approved resource identity readback and bounded retained-resource failure receipts; keep production apply, IAM mutation, installation, formatting, secrets, application startup and readiness unavailable.
- [ ] Run offline staging-bootstrap and existing host/cloud regression suites, syntax/scope/diff checks and pinned preflight; commit/push a coherent candidate and obtain independent exact-SHA review before integration or live use.
- [ ] Keep all cloud execution blocked pending separate owner authorization of selected GCP projects/billing/region/VPC/IAM/pins/staging origin and concrete reviewed scripts; keep host install/readiness/recovery behind separate publisher/schema-dependent gates and preserve cars.tk/production blockers.

Preservation: then-current full PG CapAdd Project index SHA256 `a67fb47f7973811904663fd8bba35a5c8ce6ad6164eb896adae83ea4dd39100d`, detail6622201950/pin6622210398, and prior JS Project index/detail6622115738/pin6622126651 remain verbatim with individual hashes in canonical evidence and the full synchronization comment. PG gate `cde9652c0e3dce9a9083540d15cb25b3682f144d` and JS gate `d105f8ae0747faa4bf4c6254e2dd1cd45ad0a830` retain their own review/dispatch/denial boundaries; no prior status is superseded.

Pinned M1 checkpoint `52653deef3754972230801ac260875fe92e1a403` is pushed on `codex/workshop-staging-lifecycle-plan`; full-SHA preflight returned `{"status":"synchronized","errors":[]}`, exit0. [Pin/readback receipt6622247097](https://github.com/lucronn/autodata/issues/186#issuecomment-6622247097) and canonical evidence record Issue/Project/comment hashes at `2026-11-04T04:05:59.945032+00:00`. Independent exact-checkpoint review and fresh coordinator dispatch remain pending; implementation and cloud execution are unauthorized.


## Staging boot attachment deviceName: synchronized corrective planning checkpoint

Goal: Explicitly select the staging VM boot attachment deviceName and make the offline Compute fake distinguish attachment names from disk resource names, preserving strict readback and every existing authority boundary.

Plan `docs/superpowers/plans/2026-11-04-workshop-staging-boot-device.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-boot-device.json`; record `docs/agents/records/2026-11-04-workshop-staging-boot-device.json`; evidence `docs/agents/records/2026-11-04-workshop-staging-boot-device-evidence.json`. Rejected candidate `188d6e66a3edff53bb84548d78876f8c98f6aec0`; independently reviewed local draft `b31de33a7907bf295d4c69c8df13a2b15ebabd53` PASS via coordinator.

Status: `synchronized` after [Issue186 detail6622382607](https://github.com/lucronn/autodata/issues/186#issuecomment-6622382607) and [Project8](https://github.com/users/lucronn/projects/8) readback at `2026-11-04T04:15:55.867157+00:00`. Commit/push, full-SHA pinned preflight, independent exact-checkpoint review and fresh root dispatch still precede code. No implementation or cloud operation is authorized now.

Exact prospective implementation allowlist:

- `infra/deploy/gce/staging_bootstrap.py`
- `infra/deploy/gce/test_staging_bootstrap.py`

Narrow request amendment: select boot `AttachedDisk.deviceName=<instance>-boot` explicitly as a sibling of `initializeParams`; independently retain `initializeParams.diskName=<instance>-boot` for the disk resource. Preserve strict attachment-name/resource-ID/image readback and data deviceName `autodata-data`. Make fake echo explicit attachment name and choose representative `persistent-disk-0` when omitted, never derive it from diskName. Original omission must fail strict readback after3POSTs/resources retained; exact explicit request success and observed-name drift rejection are required. No launcher/schema/config/token/network/receipt/budget/authority change. Source188d6e6 remains rejected pending exact correction review; no historical gate is retroactive acceptance.

Concrete todo:

- [ ] After PG releases the serialized tracking slot and coordinator approves this draft, synchronize the exact boot-attachment correction goal, explicit POST amendment, two-file allowlist, regression cases and todo across Issue186/Project8 and canonical plan/task/record/notes; preserve then-current full PG/JS index/detail/pins verbatim with hashes, commit/push and pass full-SHA preflight before independent exact-checkpoint review.
- [ ] Obtain independent review of that exact new checkpoint and fresh root dispatch before implementation; preserve rejected source `188d6e66a3edff53bb84548d78876f8c98f6aec0` and the prior M1 gate/receipt as distinct historical records without retrospective acceptance.
- [ ] Change the fake's omitted-name behavior and add the exact request/default/drift regressions first; demonstrate a red complete-run failure on the uncorrected request, with all three POSTs and retained resources, using only intercepted transports.
- [ ] Add only the explicit boot AttachedDisk.deviceName sibling field in staging_bootstrap.py; keep strict readback and all request/approval/config/FD3/network/receipt/authority boundaries unchanged; run focused bootstrap plus existing host/cloud regressions, syntax and diff/scope checks.
- [ ] Commit/push the exact two-file candidate, retain red/green logs and independently review its full SHA before integration; no credentials/cloud/resource operations, installation, formatting, host startup, readiness, cars.tk or production authority follows from simulated success.

Preservation: full then-current PG offline Project index SHA256 `8e678c075d383d11fa9a63e3df05040a3b8e721e068d0c38e590728b6d009aa1`, detail6622351785/pin6622361427, and Stage0/staging/older PG/JS index/detail/pin texts are retained verbatim with individual SHA256 in canonical evidence and the exact preserved-comment references in the synchronization detail. Their statuses/independent review/dispatch/denial boundaries remain unchanged. No credentials/cloud/Docker/host/provider/DNS/runtime action or readiness/production claim occurs on this documentation turn.


## Staging M2A inert-install synchronized planning checkpoint

Goal: Install only an owner-accepted authenticated release manifest and its exact migration runner/tree into a fixed root-owned staging release directory, without formatting disks, selecting a running release, delivering secrets or starting services.

Plan `docs/superpowers/plans/2026-11-04-workshop-staging-m2-host-install.md`; record `docs/agents/records/2026-11-04-workshop-staging-m2-host-install.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-staging-m2-host-install.json`; evidence `docs/agents/records/2026-11-04-workshop-staging-m2-host-install-evidence.json`. Source independently reviewed M1 candidate `ef536cc24478424efc3cc084425322cfb8056145`; independently approved corrected draft `f1558d526d87b9d48180f00be41835c65d9944fc` PASS via coordinator. No source merge/rebase is implied.

Exact prospective implementation allowlist:

- `infra/deploy/gce/deploy.sh`
- `infra/deploy/gce/host_install.py`
- `infra/deploy/gce/test_host_install.py`

Fixed root-admin approval + local accepted inbox only: validate exact manifest/runner/SQL bytes with unchanged runtime validator; protect standard root-owned non-group/other-writable parents (0755 accepted), exact private0700 subtree; require already-approved mounted disk and tmpfs; bounded descriptor copy/no-replace inert install and redacted receipt. No formatting/mounting, remote ingress, package/unit changes, current-release selection, image pull, secrets or service startup. Publisher authentication and owner acceptance workflow remain external live-use dependencies; hashes never manufacture publisher authority. No activation/readiness/cloud authorization.

Concrete todo:

- [ ] Independently review this M2A split, exact three-file scope, trusted owner-acceptance boundary, immutable file/input/receipt contract and no-replace/cleanup primitives; synchronize goal/todo/references in Issue186/Project8/canonical docs with full then-current history preservation, commit/push and full-SHA preflight before builder dispatch.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh root dispatch; establish actual authenticated publisher and separate mounted-disk/tool prerequisites before any later live installation, without inventing a verifier or owner/cloud values.
- [ ] Add failing fake-probe and temporary-inode tests for approval/publisher/mount/lock/inventory/no-replace/fault/redaction and reboot fail-closed invariants; then implement only deploy.sh, host_install.py and test_host_install.py for inert release-material installation.
- [ ] Run focused host-install tests plus existing host/cloud/bootstrap regressions, syntax/diff/scope and pinned preflight; commit/push a coherent exact candidate for independent review, preserving all startup/readiness/cloud/secret/production denials.
- [ ] Require separate decision-complete gates for authenticated remote ingress/private secret delivery, host packages/guard/units, image pull, start/schema/readiness and minimum recovery; no one may treat M2A success as completion of full M2 or live-operation authorization.

Independent exact synchronized-checkpoint review and fresh root dispatch REQUIRED before any implementation. No cloud/Docker/credential/secret/runtime action. All prior Stage1A/Stage0/staging/PG/JS authorities/statuses/denials unchanged.

Status: `synchronized` after [Issue186 detail6622589651](https://github.com/lucronn/autodata/issues/186#issuecomment-6622589651) and Project8 exact readback at `2026-11-04T04:30:30.706329+00:00`. Full then-current Project index, entire prior Issue body and all111 historical comment bodies are retained verbatim with SHA256 in `docs/agents/records/2026-11-04-workshop-staging-m2-host-install-evidence.json` and verified unchanged. Independent exact-checkpoint review and fresh root dispatch remain pending. This docs-only checkpoint authorizes no implementation or live action.


## Verified docs-only integration tracking synchronization

This additive receipt supersedes only the local-draft tracking statements above. Coordinator explicitly released PG writer slot. Independent local draft review PASS pinned plan SHA256 ea42fcac66cc397482f985be8a26e6e73dc1fc22c0b4e008eec742d4e384e553 / bundle manifest ca34e3e8be70bac131aabf7b600032a9b4531f0d87b85f5a8fa5f75f03c94a63. https://github.com/lucronn/autodata/issues/186#issuecomment-6622915925 read back at 2026-11-04T04:54:35.010852+00:00. Entire current Issue body/all115 prior comment bodies and full current PG Project index preserved verbatim+hash in `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`; independent API readback confirmed Issue/prior comments unchanged. PG gate74dfe57/receiptd662cb0, Stage1A and M2A details/pins/statuses/denials preserved. Project current index SHA256 20ab190a8c0e78eb994b5e99ba133e7df2cdebd1258f29c0680d0cb32422407c.

Record/task status synchronized after actual readback. Full committed checkpoint/preflight, independent exact-checkpoint review and fresh coordinator dispatch remain required before any ordered integration. No implementation merge, provider, cloud, runtime, staging activation or deployment occurred. This synchronization alone authorizes none of them.

Goal: Integrate the three independently reviewed dormant R6, publisher and staging leaf histories into one byte-pinned offline candidate without live activation.

Refs: `docs/superpowers/plans/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json`, `docs/agents/tasks/2026-11-03-production-release/workshop-reviewed-leaves-integration.json`, `docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration-evidence.json`

Concrete todo:
- [ ] Obtain independent local-draft review; keep status unsynchronized and integration blocked until PG releases the serialized tracking slot.
- [ ] After slot release, preserve then-current Issue186/Project8 texts and hashes; synchronize exact source tuple, plan/spec/record/task/canonical notes and concrete todo; commit/push the docs-only checkpoint and pass full-SHA preflight.
- [ ] Obtain independent exact synchronized-checkpoint review and fresh coordinator code-only dispatch; create an isolated feature worktree/branch from the checkpoint.
- [ ] Merge exact R6, publisher and staging leaf histories in that deterministic order, resolving only five approved documentation/tracking conflicts and preserving all 23 implementation blob pins and historical additions.
- [ ] Run combined offline Python/Node/preflight/syntax/scope/authority checks after each milestone; commit and promptly push validated coherent merges to the assigned branch.
- [ ] Obtain independent exact-head review, freeze the combined candidate SHA and retain results; obtain separate gates before fixture/CI reruns or any live activation.


### Exact committed integration checkpoint pin

Gate `2728ac1acaf173d6f244e200e584dac7922fda1d` pushed on `codex/workshop-reviewed-leaves-integration-plan`; canonical preflight at that full SHA exit0, `status: synchronized`, `errors: []`, stderr empty. Pin https://github.com/lucronn/autodata/issues/186#issuecomment-6622928529 read back 2026-11-04T04:55:31.706681+00:00. Final Project index SHA256 `578438413fa8b6738efbf960c46e55ff7b6623772fac191b697af862d57bf0d2` (934 characters), containing every explicit predecessor reference ID including full PG gate74dfe57, receiptd662cb0 and M2A gate9a2b57d0. Complete Issue body/all115 predecessor bodies unchanged on fresh paginated readback. Evidence retains exact prior/full current index, pin hash, command/stdout/stderr and readback.

Independent exact-checkpoint review and fresh coordinator code-only dispatch remain required before any ordered integration. No code merge or activation occurred. Receipt commit records this gate without changing its pinned base.


## Task62 purchase configuration delivery — planning synchronized (Protected host delivery operations)

Task62 planning only; no source delivery capability is implemented by this amendment. Plan `docs/superpowers/plans/2026-11-05-workshop-purchase-config-delivery.md`, spec `docs/agents/specs/2026-11-05-workshop-purchase-config-delivery.json`, record `docs/agents/records/2026-11-05-workshop-purchase-config-delivery.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-purchase-config-delivery.json`, verification `docs/verification/2026-11-05-workshop-purchase-config-delivery.md`. Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8 are synchronized for Task62 by the coordinator. Parent `e200cfd6b473e9231844d133f63244f3a627a356` / tree `269bd94410df22a8718f005c1d0b0142238cdafc` preserves Task59/Task61 histories. All authorities=false, current implementation allowlist=[], accepted_case_credit=0, accepted_new_case_credit=0, verified_case_ids=[], release_state=unverified.

Required host schema_version=2 deliberately rejects host-v1/missing/null/partial/unknown purchase config; release manifest remains v1. Required seven-key `workshop_purchase_config` is original structured nonsecret data included in service_config_sha256; explicit disabled means enabled=false, terms_version=workshop-v1, all four URLs and tax_notice=null. Enabled requires unchanged Task59 syntactic URL/scalar/Unicode/UTF-8 semantics, four HTTPS URLs <=2048bytes each and single-line notice <=1024bytes. No owner content/domain/tax approval follows from syntax.

Installed validator stays self-contained. Canonical UTF-8 JSON replaces every U+0024 with six ASCII `\u0024` characters; emitted wire <=16384bytes, otherwise fixed redacted `purchase_config_transport_limit` before render. Task59-valid dollar-heavy9343byte raw/54883byte escaped data is intentionally non-deployable. No normalization, shell expansion, ambient override or runtime parser change. Derived AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON goes only to ingestion-http; Go gets authenticated Task59 HTTP projection. Existing api/ingestion-http token numeric references must be identical; actual credentials remain separate protected tmpfs file delivery, never Config.Env. Final no-dollar guard and payment-reconciler role/default remain unchanged.

Synthetic proof after a fresh gate uses actual renderer, copied wrapper with secret_root-only replacement and UID/GID1000 protections, unchanged parser, frozen enabled→disabled reconstruction and pre-factory checkout denial. Local Compose config parsing uses no daemon or production startup and required mode cannot silently skip. Existing Task59 PG/Go authority roots remain separate; synthetic transport supplies zero acceptance credit.

Pause is a new reviewed configuration/hash and process reconstruction; keep commerce mode, Stripe settlement/webhook/reconciliation and paid recovery intact. Existing objects cannot hot reload. Real maintenance/drain/fencing/bounded in-flight policy/install/all commerce replica and affected API replacement/projection equality/checkout denial/resume remain separately blocked. Issued Stripe URLs cannot be claimed retroactively canceled. Immutable same-source config generations, retention/atomic switch/recovery are missing; never overwrite installed source directories or invent empty commits. Automatic rollback requires same config hash/platform/SQL tree and independently reviewed Task59-capable source. A pause hash bars automatic return to earlier enabled config; config-changing rollback is a separate reviewed release, and failed recovery retains maintenance.

Only four future implementation paths: `infra/deploy/gce/runtime-check.py`, `infra/deploy/gce/test_host_runtime.py`, `infra/deploy/gce/test_purchase_config_delivery.py`, `infra/deploy/gce/release.env.example`. No application/DB/endpoints/frontend, runtime-entrypoint, Compose, release schema, Dockerfile/workflow/cloud adapter/protected variable changes. Task60 publication ownership and frozen evidence/acceptance ledgers remain intact.

Remaining actual owner/legal/tax/support/merchant/Firebase/token/project/resource facts, protected config-generation/install/drain/restart/rollback, authentic TEST/staging/host/TLS/restore/current-source browser/runtime/API21/DTO120/final180 and fresh source/PR CI are unmet. Cars.tk DNS is Vercel by trusted coordinator/user direction; no DNS/cloud action is authorized. Independent draft review and literal six-todo/nine+four-path Issue/Project preservation readbacks passed; committed/pushed checkpoint, external actual SHA/tree seal, standalone+nested exact-base errors=[] preflights, independent checkpoint review and explicit dispatch remain required. Any Task61 source change or CI failure blocks synchronization.


## Coordinator tracking readback — planning synchronized

Updated at 2026-11-05T06:11:06Z. Root synchronized the exact goal, six literal todos, nine gate paths and four prospective implementation paths in https://github.com/lucronn/autodata/issues/186#issuecomment-6651122921; Project8 item `PVTI_lAHOCSJ8cc4BiQ2BzhFocs4` indexes that comment. Before snapshot `/home/corp/autodata-evidence/task62-config-delivery-before-tracking.json` SHA256 185dea24ec804d096f159a9ded443477ea0cff0a8ded02c884eb037e46220044; after snapshot `/home/corp/autodata-evidence/task62-config-delivery-after-tracking.json` SHA256 c0d321f6d22bb037cd168a5b2a598372bb80219c70af47a9131f03e859e49ba5. Preservation `/home/corp/autodata-evidence/task62-config-delivery-tracking-verify.json` SHA256 739d2d0b1bacf132bd8ef144146c4d13b0811f0927cc90dfaa8dacf1433c5f7f passed10 checks; independent draft review `/home/corp/autodata-evidence/task62-config-delivery-draft-independent/REPORT.json` SHA256 e303d03951a62f6d38c82f549948f1371d8a04646bf053a228e3d927d1b0096d passed15 checks. Issue body and prior comments, other Project fields and prior Project Source were preserved. This agent performed no Issue/Project writes.

Status/planning/tracking are synchronized; execution remains blocked, current implementation allowlist=[], all authorities=false, credits0, verified_case_ids=[], release_state=unverified. Planning synchronized by root with Issue186 comment6651122921/Project8 preservation PASS10 and independent draft PASS15. Nine-document planning-only checkpoint commit/push authorized. External actual SHA/tree seal, standalone+nested exact-checkpoint errors=[] preflights, independent checkpoint review and explicit four-path dispatch remain required. Task61 PR290/full CI dependency evidence remains pending. Execution blocked; all authorities false/current implementation allowlist empty; no predecessor self-hash. Task61 PR290/full CI remains pending and supplies no inherited green. Historical draft/proposal observations above remain provenance, not fresh implementation evidence.


## Task64 GCE CI coverage — synchronized planning checkpoint

Status=synchronized; planning_status=synchronized; tracking_status=synchronized. Planning parent 4fe83b29b86411d104b1edb203e9b26fde67ad02 / tree 9364c8442e27bbcd0a38c7ffafceb5c24b7736aa. Current implementation allowlist=[]; all authorities=false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified.

Goal: Include every infra/deploy/gce change in both push and pull_request Autonomous Verification triggers and run the complete required-mode GCE delivery suite under its protected numeric UID/GID1000 fixture contract in the existing main verification job, with structural stdlib governance regressions and no deployment or acceptance authority.

Plan: `docs/superpowers/plans/2026-11-05-workshop-gce-ci-coverage.md`. Spec: `docs/agents/specs/2026-11-05-workshop-gce-ci-coverage.json`. Record: `docs/agents/records/2026-11-05-workshop-gce-ci-coverage.json`. Task: `docs/agents/tasks/2026-11-03-production-release/workshop-gce-ci-coverage.json`. Verification: `docs/verification/2026-11-05-workshop-gce-ci-coverage.md`. Tracking: https://github.com/lucronn/autodata/issues/186 and https://github.com/users/lucronn/projects/8 (root sole writer; tracking synchronized by verified saved readback).

Concrete todo:

- [ ] Independently review the approved Task64 proposal/review, exact Task62 source4fe83b29b86411d104b1edb203e9b26fde67ad02/tree9364c8442e27bbcd0a38c7ffafceb5c24b7736aa, eight gate paths/two implementation paths and UID1000 executable/environment contract; preserve all prior queue/root/history bytes and credits0.
- [ ] Synchronize this literal goal, six todos, exact eight/two-path scopes and canonical references in Issue186/Project8 using root-owned before/after preservation readbacks; only then set standalone/nested records synchronized, commit/push the planning-only checkpoint, externally seal its actual SHA/tree, pass both exact-checkpoint preflights errors=[], obtain independent checkpoint review and explicit two-path dispatch.
- [ ] Write failing structural stdlib governance tests proving separate push and pull_request GCE coverage, required complete suite/UID1000 temp ownership/flag/order and complete reviewed script identity, and negative mutation rejection; add only the two GCE filters and the preflighted sanitized numeric-identity test step without changing existing jobs, permissions, timeout or protected source.
- [ ] Run focused governance and complete required-mode GCE tests with actual executable/identity/Compose/tempfile readbacks, ordinary developer regressions and exact two-path/protected integrity checks; retain raw failures and do not weaken or skip wrapper/Unicode transport requirements.
- [ ] Commit and promptly push small coherent validated milestones to the assigned feature branch, obtain independent exact-source review, then retain fresh source-push and actual pull_request checkout SHA/tree/workflow/job receipts for all three required jobs including GCE and live Compose; manual dispatch remains supplemental.
- [ ] Synchronize verified source and honest CI coverage evidence while preserving Task61 actual-PR, owner/host/immutable-generation/activation/staging/restore/provider/identity/payment/browser/DNS release limits and acceptance credits0; no merge, deployment, publication or live-sales authority.

Exact future implementation scope: `.github/workflows/autonomous-verification.yml`, `scripts/dev/test_repository_governance.py` only. Both event filters gain GCE coverage; one mandatory main-job suite runs after dependencies and before Compose under preflighted sanitized UID/GID1000 using sudo-n/setpriv/clear-groups/env-i. Fixed executable paths/system Python alias and owned temp HOME/TMPDIR are explicit runner prerequisites. Governance uses stdlib bounded structural scopes/negative mutations. Existing jobs/permissions/timeouts and protected GCE/application/policy/Compose paths remain intact.

Task62 source review and five-lane fixture PASS are coordinator-reported source evidence, not Actions coverage. Task61 CI audit PASS_CI_AUDIT: source-push41977565019 and actual-PR41977907070 succeeded all three jobs/live Compose at source e200cfd6b473e9231844d133f63244f3a627a356/tree269bd94410df22a8718f005c1d0b0142238cdafc; PR checkout97d4d975efdb396fafa91e27c92f5a30b3a4fcc8 has equal tree. Audit /home/corp/autodata-evidence/task61-final-ci-audit/REPORT.json SHA256486e069a4a08587853b84d89a41b403ee2e95057482b453493f5166b42915681. Qualifications:210 ingestion skips in each CI run, local Go roots TestWorkshopCommercePythonIntegration/TestWorkshopPurchaseConfigAuthorityIntegration skipped, so no whole-workflow-zero-skips claim. Developer/R3/Node/DTO skips0; DTO120 remains inventory only with observer/containment/trace-admission blockers, acceptance credit0. This is Task61 evidence, not fresh Task62/64 coverage. Task62 final local source report /home/corp/autodata-evidence/task62-config-delivery-code/FINAL-SOURCE-REPORT.json SHA256d0803f8645eb08e01e5b0726b9629ef00b13f42c77c1b808f010eda138a5a802 records local/source/owned-fixture PASS at source4fe83b29b86411d104b1edb203e9b26fde67ad02/tree9364c8442e27bbcd0a38c7ffafceb5c24b7736aa; coordinator confirms complete local developer604 PASS. Supplemental workflow_dispatch41979473005 remains pending; actual source-push/pull_request GCE CI coverage remains absent. These local results provide no CI, deployment or acceptance credit.  GCE source-push/PR CI gap remains open until this separately gated change produces fresh actual event receipts. Task60 publication and external Task63 generation design retain ownership; no absent queue history is reconstructed. Root has independently reviewed the corrected draft and synchronized literal tracking. Planning checkpoint commit/push, external actual SHA/tree seal, both pinned preflights, independent checkpoint review and explicit dispatch remain required. No implementation, CI success, merge/deployment/DNS or authentic acceptance is authorized here.

Revision after independent draft REVISE: complete normalized GCE run script is SHA256-bound to literal `5adc3b0b3b56c75f8df1faed2dd461a71ac37c3622b973af185baf99941e3502` (dedent10, strip trailing LF blank lines, append one LF; UTF-8). The governance guard must reject any differing script bytes, including early exit/conditional bypass, missing private temp mkdir/numeric chown and wrong ownership. Expected hash is independently reviewed, never derived from workflow. Expanded mutation evidence and renewed independent draft review remain required.


## Root tracking readback — synchronized planning checkpoint

Root synchronized the exact goal, six literal todos, eight gate paths and two future implementation paths in [Issue186 comment6651421313](https://github.com/lucronn/autodata/issues/186#issuecomment-6651421313) and Project8 item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4. Before snapshot `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/BEFORE-TRACKING-FINAL.json` SHA2564119eec2face30558869172fb686c4480de3fc16dd878b10bc7d57197bbe1b41; after `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/AFTER-TRACKING.json` SHA25657313623e26513af3d6d6fc699290a8df8202a5bf9357c0b804b76364204a574. Preservation PASS9 `/home/corp/autodata-evidence/task64-gce-ci-coverage-design/TRACKING-VERIFY.json` SHA256b060c5d63dfcd6d4ee13816bec1121543cb78bb3f194d4fe5b1b6005f5d4680c verifies unchanged Issue body/prior comments/other Project fields and prior Source archived verbatim. Corrected exact-draft independent review PASS54 `/home/corp/autodata-evidence/task64-gate-draft-independent/REPORT-RECHECK.json` SHA2561ec2ac5d9d42053fa4cf4d99f7a74be0dbb105363555ce44044a4e7e00a5bf30. This planning lane verified saved literal/preservation readbacks and performed no tracking write. Posted comment retains reviewed draft wording as history; records now reflect completed tracking synchronization.

Status/planning/tracking=synchronized. Current implementation allowlist=[]; all authorities=false; accepted_case_credit=0; accepted_new_case_credit=0; verified_case_ids=[]; release_state=unverified. Checkpoint actual SHA/tree is sealed externally after commit/push; standalone+nested exact-checkpoint preflight, independent checkpoint review and explicit two-path dispatch remain required. No source implementation, hosted CI success, publication/deployment or authentic acceptance is authorized. Historical Task61/Task62 evidence retains its recorded qualification.

## Task65: CI binding and deterministic installer fixture checkpoint

Goal: Restore verification of the unchanged Task64 workflow by rebinding only the disabled R6 planning profile to its exact current workflow digest and ensuring the pre-promotion replacement fixture reliably exercises identity-based cleanup refusal, with every authority and acceptance credit unchanged.

Synchronized planning checkpoint on exact Task64 source `c7d1bba38c80288ab0f2e0c2a8b86e2eb5c35e4b`, tree `2119fb9d394994472b20243cfbbebe0cbba7ae25`. Plan `docs/superpowers/plans/2026-11-05-workshop-ci-binding-fixtures.md`; spec `docs/agents/specs/2026-11-05-workshop-ci-binding-fixtures.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-ci-binding-fixtures.json`; standalone record `docs/agents/records/2026-11-05-workshop-ci-binding-fixtures.json`; evidence `docs/verification/2026-11-05-workshop-ci-binding-fixtures.md`. Issue https://github.com/lucronn/autodata/issues/186#issuecomment-6651645549; Project https://github.com/users/lucronn/projects/8 / item PVTI_lAHOCSJ8cc4BiQ2BzhFocs4.

Eight coordinator gate paths and exact two future implementation paths are enumerated in plan/spec/task/record. Future R6 correction changes only `product_evidence.ci_profile.workflow_sha256` from `b7dc37359faea4cdaff29ce7b0460d2f5d289ad7d3ae4c2c0c788a8992556e4d` to `b9ccf5f8c8fc974d113f0461871e9288e30a1a61ddeff6fc67cfd8a6fb3e7418`; expected8727 bytes/mode100644/SHA256 `09562c3da23fbf1283c5276023967c97ab51d53b1133c49ddf7cd6b6f4b87be7`/Git blob `132307774cb0baabb1f320b0e2ea7bde3aae9526`. R6 itself remains byte-identical during this checkpoint. Future fixture change retains an open original inode through cleanup and asserts distinct identities plus code6/recovery_incomplete/incomplete/no promotion/preserved injection.

Task64 push41981562383 and actual PR41981617643 main failed at unchanged R6 workflow binding; GCE/live Compose skipped; R3/DTO passed. Task62 supplemental manual41979473005 passed all3 including live Compose, remains supplemental. Original R6 digest/raw bytes and Task64 failures remain historical; all existing queue/root/task/history entries remain unchanged. No inherited CI green.

Todo:

- [ ] Independently review Task64 exact source, unchanged whole-workflow trusted-loader/browser contracts, red receipts and the two-path correction; preserve historical evidence and every authority/credit limit.
- [ ] Synchronize this goal, six todos, eight gate paths, two implementation paths, exact old/new R6 metadata and canonical refs in Issue186/Project8; commit/push the checkpoint, seal its actual SHA/tree, pass both exact-base preflights and obtain independent checkpoint review before dispatch.
- [ ] Retain original browser-binding and trusted-boundary failures; replace only the single R6 ASCII workflow hash with the exact reviewed current-workflow digest, prove every other R6 byte/field unchanged and expected output hash/blob/length, run focused existing binding/trusted-boundary/disabled CLI tests, and commit/push the independently reviewable one-field milestone.
- [ ] Retain exact-wrapper inode-reuse red evidence; pin the temporary manifest with an open descriptor through installer cleanup, assert distinct identities and existing6/no-commit/preserved-injected-file outcomes, run focused repeats on disk-backed/tmpfs storage and host-install verification, then commit/push the fixture-only milestone.
- [ ] Run complete release-acceptance/browser/developer/governance checks and required-mode GCE under the unchanged UID/GID1000 wrapper, check exact two-path/protected integrity at final source, obtain independent exact-source review and retain fresh source-push plus actual-PR receipts for all three jobs/GCE/live Compose.
- [ ] Append honest exact-source local/CI results and retain the prior R6 digest/Task64 failures as historical evidence; preserve all disabled profiles, trusted-loader boundaries, owner/staging/activation/payment/browser/provider/DNS blockers, credits0 and every release authority false; perform no merge/deployment/publication.

Current implementation allowlist=[]; independent checkpoint review and explicit two-path dispatch required after actual checkpoint seal and standalone/nested exact-base preflights. Every authority false; credits0; verified_case_ids=[]; release_state=unverified. Preserve disabled profiles/trusted-loader contract and all owner/staging/activation/payment/browser/provider/DNS blockers. No merge/deployment/publication.


## Provisioned-host activation successor (Issue299)

The [activation plan](../superpowers/plans/2026-11-05-host-release-activation.md), [record](../agents/records/2026-11-05-host-release-activation.json), and [task](../agents/tasks/2026-11-03-production-release/host-release-activation.json) govern the next real host code milestone: Activate an already provisioned AutoData host using immutable local releases, maintenance-first lifecycle operations, actual PostgreSQL/service/dependency readiness, and schema-compatible rollback. Tracking: https://github.com/lucronn/autodata/issues/299, linked beneath https://github.com/lucronn/autodata/issues/186, and https://github.com/users/lucronn/projects/8 (separate activation item). The source base is `38b53eca633eee94f045fc33d9c90bb36da7618d`.

This is a synchronized implementation plan, not an implemented capability or deployment receipt. It explicitly supersedes earlier lifecycle/locked-schema code exclusions only for this bounded successor. It authorizes real fixed on-host start/stop/maintenance/resume code, a single-transaction PG17 lock-before-catalog/ledger collector, actual container and GET-only local dependency readiness, immutable current selection and one schema-compatible rollback. Already provisioned tools/storage/guards/schema/socket identity/image cache/private files are prerequisites. Cloud operations, actual production credentials, image publication, SQL migration/role provisioning, provider calls and live activation are outside implementation scope.

Concrete todo:

- [ ] Implement a fixed bounded PG17 single-transaction collector: lock before catalog validation, reject unsafe ledger/catalog/role facts before reading ledger rows, compare exact migration inventory, and prove the protocol with real disposable PostgreSQL17 adversarial tests.
- [ ] Implement real fixed-path host lifecycle execution with one host operation lock, verified immutable local Compose/Caddy material, cached images only, validated mounts/guards/secrets, and maintenance-first start/stop/maintenance/resume operations.
- [ ] Collect actual service/container/image/configuration and local GET /readyz evidence without scheduling provider/payment/model work; set schema/services/postgres/nats/s3/no_work/runtime_evidence only from their corresponding successful observations.
- [ ] Atomically select a successfully verified release and restore only the manifest-designated prior release with identical schema/configuration on activation failure; prove failure, timeout, concurrent invocation and recovery behavior with bounded executor tests.
- [ ] Run focused host regressions, real disposable PG17 protocol tests, shell/Python syntax, exact-base preflight and diff checks; commit/push coherent milestones and independently review the exact candidate before integration. Update the runbook with actual executable prerequisites and remaining launch blockers.

Implementation allowlist:

- `infra/deploy/gce/deploy.sh`
- `infra/deploy/gce/runtime-check.py`
- `infra/deploy/gce/host_activation.py`
- `infra/deploy/gce/runtime-grants.sql`
- `infra/deploy/gce/test_host_runtime.py`
- `infra/deploy/gce/test_host_activation.py`
- `infra/deploy/gce/test_host_schema_pg17.py`
- `docs/operations/workshop-gcp.md`
