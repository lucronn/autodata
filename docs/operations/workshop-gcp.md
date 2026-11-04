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
