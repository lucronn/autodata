# Paid Workshop GCE operations

This runbook follows the [bounded hosting plan](../superpowers/plans/2026-11-03-workshop-hosting.md), [Issue186](https://github.com/lucronn/autodata/issues/186), and [Project8](https://github.com/users/lucronn/projects/8). The [canonical planning gate](../agents/pre-implementation-gate.md), synchronized [record](../agents/records/2026-11-03-workshop-hosting.json), and [task](../agents/tasks/2026-11-03-production-release/workshop-hosting.json) govern implementation. Resource creation, real credentials, providers, staging, recovery and DNS changes require separate authorization after independent review.

## Current executable boundary

`infra/deploy/gce/cloud-bootstrap.sh` is an offline resource-definition renderer. It accepts no arguments or the single verb `plan`. The sole input is root-owned regular mode0600 `/etc/autodata/host.json`, validated by the reviewed v1 helper installed at `/opt/autodata/bin/runtime-check.py`. It reads through the helper's no-follow bounded descriptor contract. The shell launcher clears its environment and uses fixed `/usr/bin/python3 -I`; caller paths, environment substitutions, credential discovery and executable overrides are unavailable.

The output is one bounded JSON receipt with `definition_only:true`, `plan.execution_enabled:false`, and explicit unresolved inputs. A passed receipt means that the nonsecret definition was rendered. It does not certify IAM, resources, a mount, a package pin, a guard or a running service. Without the installed reviewed helper or staged private configuration it fails closed. The single verb `apply` also fails closed with `missing_dependency`; there is no approval flag or live apply implementation in this milestone. Unknown verbs and additional arguments are invalid.

The renderer names the proposed VM, data disk, static address, registry and backup bucket from the exact v1 configuration. The proposed e2-standard-4/200GiB balanced disk and bucket region remain subject to owner cost, residency and recovery approval. No disk is formatted, mounted or resized. A valid filesystem UUID in the configuration is an expected identity, rather than an observed disk identity. The renderer does not choose a VPC or boot image when those inputs remain unresolved.

`cloud-ops.py` likewise has no live adapter. Its current offline parser accepts exactly two positional arguments: `publish|deploy|monitor` followed by a lowercase 40-hex source SHA, or `backup|restore` followed by a UUID. Valid arguments return exit 3 and a failed `missing_dependency` receipt; unknown verbs, malformed identifiers and extra arguments return exit 2. These are fail-closed definition entrypoints, rather than the future executable flag-based interfaces in the plan. Its fake backup evaluator marks receipts `simulation:true`. Finite timeout/output budgets in those definitions do not establish actual subprocess cancellation or IAP stream deadlines.

The pure `evaluate_published_release` function additionally compares a supplied fake read-only transcript against the reviewed manifest/configuration and a separately supplied run/artifact/digest binding. Its fixed observations are run metadata, artifact metadata, bounded manifest bytes and image observations. It rejects unknown/missing fields, mismatched source/workflow/run/artifact identity, unfinished or unsuccessful runs, expired artifacts, wrong byte counts/hashes, duplicate JSON keys, scalar-type drift and inconsistent image/platform/provenance/SBOM references. Consistency produces only `status: transcript_consistent`, `simulation:true`, `deployment_authorized:false` and `consistent_binding`; it does not produce a publish-success receipt. These untrusted fake observations cannot prove OIDC, GitHub/registry authenticity, signed provenance, SBOM contents or an actual image build/publication. Callback timeout/output budgets are definitions, not actual subprocess cancellation. The CLI and workflows do not call this evaluator and remain blocked.

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


## PG17 disposable runner route successor: plan-only

Goal: Prepare and independently freeze a disposable PostgreSQL17 Alpine runner for the exact disconnected schema-probe candidate, then permit only separately approved actual harness execution; preserve production runtime, grants and all readiness denials.

Canonical route plan: `docs/superpowers/plans/2026-11-03-workshop-schema-pg17-route.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-schema-pg17-route.json`; record `docs/agents/records/2026-11-03-workshop-schema-pg17-route.json`. Planning root `eddcf724028683dbb083191e4f8c42064b866bf0`; immutable harness source `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa` on `codex/workshop-schema-probe`. The route plan supersedes only the earlier native-only/no-Docker/no-download test prerequisite: a cached official PG17.11 Alpine derivative may later acquire Python3/C toolchain in a bounded preparation stage after exact-gate independent review and coordinator approval. Source-image history/cache is insufficient; exact toolchain/package/image/source identities require independent artifact review before a separately authorized network-disabled disposable harness run. No tracked implementation changes or integration are allowed by this route. Native hostPG18 cannot replace PG17. Preparation and actual harness are unexecuted; production grants/collector/services/readiness remain unchanged and unavailable.

Concrete todo:

- [ ] Synchronize the PG17 route decision, exact source/base pins, staged authority and concrete todo in Issue186/Project8 and canonical documentation; commit/push and pass exact-checkpoint preflight for independent review.
- [ ] After coordinator approval only, prepare the cached-digest Alpine derivative with Python3 and a C compiler; retain package versions, APK hashes, build inputs, base identity and immutable image identity with private tmpfs covering inherited PGDATA, verified mount inventory and exact-owned cleanup; do not start PostgreSQL.
- [ ] Independently inspect the frozen runner artifact and exact harness54ab source archive, verify matching PG17 tools/headers, ICU and non-root identity, then obtain separate exact-image execution authorization and re-pin the adopted gate.
- [ ] Only after the execution boundary is approved, run the unchanged complete PG17 adversarial harness in one network-disabled disposable container with private PGDATA tmpfs and verified mount inventory; retain every failure, sentinel control, case inventory and server/session/lock/container cleanup receipt.
- [ ] Independently review exact source/image/raw evidence before accepting any disposable-harness result; fail closed on missing prerequisites or cases and keep production grants, runtime integration, services, deployment and readiness unavailable.

Tracking synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6619358812 and Project8 readback at `2026-11-04T00:44:26.593707+00:00`; dedicated record retains SHA256 hashes and the complete prior Project index is preserved verbatim in that comment. Independent plan review pending; preparation and actual harness remain unexecuted and unauthorized.


PG17 route inherited-volume review correction (plan-only): the pinned official base declares `VOLUME /var/lib/postgresql/data`. Every later preparation/acquisition/inspection/execution container must override that exact path with private bounded tmpfs (`rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700`), retain complete mount inventory before payload start and cleanup/absence proof afterward, reject unexpected anonymous/named volumes, and remove only exact-owned containers/volumes. Build sandbox cleanup must also be demonstrated; inability blocks preparation. The harness cluster remains under private `/tmp`; Docker cleanup does not substitute for server/session/lock cleanup evidence. Canonical corrected plan/task/record: `docs/superpowers/plans/2026-11-03-workshop-schema-pg17-route.md`, `docs/agents/tasks/2026-11-03-production-release/workshop-schema-pg17-route.json`, `docs/agents/records/2026-11-03-workshop-schema-pg17-route.json`. Independent corrected-checkpoint review remains pending; no preparation, image build, PostgreSQL/container execution, implementation modification or readiness claim.

Corrected PGDATA route tracking synchronized by https://github.com/lucronn/autodata/issues/186#issuecomment-6621014641 and Project8 readback at `2026-11-04T02:36:36.976288+00:00`; exact hashes in dedicated record. Independent review pending; all execution remains unexecuted.


PG17 route adoption checkpoint: corrected plan `7988c7de30e6de930d36a3b8d907cdb4e90264ba` independently reviewed and approved by coordinator (receipt `79d5f089acbdcd09d490c5ca56f582da8bc24be6`); clean documentation adoption `80bec2bbb1b012ae311c6fed58accd8c97e5c395` is a direct successor of exact harness `54ab7dce19c36ce7ea3403259dd1ecc66bf323aa`. Five harness paths are byte-identical; source archive SHA256 `4666eec4f3575fcc4f12ec6956af41fe055c740f53430e0057d7163b85096b80`. Issue186/Project8 adoption synchronization: https://github.com/lucronn/autodata/issues/186#issuecomment-6621086102; live readback 2026-11-04T02:41:59.189499+00:00 (dedicated record retains hashes and prior Project index preservation). Preparation remains unexecuted and held for this adopted full-SHA preflight plus root verification/go-ahead. Actual PostgreSQL/harness execution remains unexecuted and separately unauthorized; production schema/services/runtime_evidence/production_ready/deployment_authorized remain false.


## PG17 inspected preparation amendment: plan-only

Goal: Replace the blocked opaque-builder PG17 preparation step with inspected exact-ID acquisition and offline-install containers plus a stopped-container commit; preserve the separate exact-image harness authorization and every production/readiness denial.

Decision-complete successor: `docs/superpowers/plans/2026-11-04-workshop-pg17-inspected-preparation.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-inspected-preparation.json`; record `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation.json`. Planning base `79ce883458c1ac41e385cabc8d1f582b0b28cab1`; exact harness54ab and historical builder blocker preserved. This supersedes only prior route Task1 Dockerfile/build handling: later approved preparation uses exact-ID `docker create --pull=never`, full pre-start mount/network/capability inspection and bounded private PGDATA tmpfs; signed official APK acquisition; offline installation in an isolated inspected container root layer; then exact stopped-container `docker commit --change` with explicit non-root configuration, ancestry/input/package/file-delta provenance and exact-owned cleanup. No BuildKit, image pull, package upgrade, tracked implementation edit, integration or current Docker execution is allowed. Original Task2 remains unchanged and separately unauthorized; image/toolchain/harness/readiness remain unverified.

Concrete todo:

- [ ] Synchronize the inspected-create/offline-install/commit amendment, exact source/base pins, mount and cleanup contracts in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent plan review.
- [ ] After separate coordinator approval, create and inspect the exact cached-base acquisition container with bounded private PGDATA tmpfs, signed official APK-only networking and one private output mount; freeze the signed dependency closure and clean only its exact owned resources.
- [ ] Create and inspect a network-disabled offline installer with read-only frozen inputs, private PGDATA tmpfs and an isolated writable root layer; reject package upgrades, untrusted signatures, unexpected mounts or file changes before committing its stopped state.
- [ ] Commit only the reviewed exited-zero installer ID with explicit non-root image configuration and provenance labels; inspect exact base-layer ancestry, configuration, package/toolchain/source hashes and cleanup, then request independent frozen-image review.
- [ ] Keep actual PostgreSQL startup and harness Task2 unexecuted and unauthorized until separate exact-image/source dispatch; preserve all blocker/failure receipts and production runtime/grants/services/deployment/readiness denials.

Inspected-preparation amendment synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621173398 and Project8 readback at `2026-11-04T02:48:06.281627+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned inspected-preparation amendment checkpoint: `2cf545157ed299b8424bbebe1b01ce9c85ab3a3c`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621179539. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


Inspected PG17 preparation ICU review correction (plan-only): the fixed Python inspection script now parses pg_config --configure with `shlex.split(..., comments=False, posix=True)`, requires exactly one `--with-icu` argument and rejects `--without-icu`. A pure local fixture executes only that exact extracted AST fragment: quoted/unquoted ICU and quoted spaces pass; missing/disabled/contradictory/duplicate/substring/empty/malformed quoting reject (10 passed,0 failed). The prior whitespace split fails the quoted positive fixture. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-fixture.json` records inputs/results/fragment hash. No container, toolchain, download or harness execution is implied; independent corrected-checkpoint review/new preparation dispatch remain pending and original Task2 stays separately unauthorized.

Narrow ICU correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621225616 and Project8 readback at `2026-11-04T02:51:55.028338+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned ICU-corrected inspected-preparation checkpoint: `6d65a512172f28a9f7f0960ecf41409db78455c2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-inspected-preparation-icu-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621229238. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 APK default-log correction: plan-only

Goal: Permit only an independently reviewed PG17 preparation retry with an explicit bounded private APK log tmpfs and pre-start guard, preserving the actual exit99 blocker, exact-owned cleanup, offline provenance and separate harness authority.

Correction plan `docs/superpowers/plans/2026-11-04-workshop-pg17-apk-log.md`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-apk-log.json`; record `docs/agents/records/2026-11-04-workshop-pg17-apk-log.json`. Preserved red: approved Task1A under6d65a5 exited99 at apk update with read-only log error,0 APKs; exact-owned container removed and volume inventory unchanged (base65772079). Read-only cached libapk3.0.8 identifies default `/var/log/apk.log`. Later approved APK acquisition/simulation/install creates add only private `/var/log` tmpfs4MiB (`rw,noexec,nosuid,nodev,uid=0,gid=0,mode=0700`) and exact pre-start guard; acquisition root stays read-only, no capability/command/repository/host-volume expansion, logs cannot enter committed added layer. Original full mount/cleanup/provenance/Task2 boundaries remain. Guard fixtures are synthetic/pure and not retry evidence. Independent review/new coordinator Task1A dispatch pending; this planner creates/starts/downloads/retries nothing.

Concrete todo:

- [ ] Synchronize the exact APK log-path diagnosis, retained red proof, bounded tmpfs guard and unchanged preparation/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent corrected-checkpoint review and a new coordinator Task1A dispatch only, create a fresh exact-base acquisition container with the additional private4MiB /var/log tmpfs and validate the complete original mount contract plus exact new log guard before start.
- [ ] Execute only the unchanged approved signed-APK acquisition payload after its inspected log guard passes; preserve the previous exit99 and every new failure, bounded attach/log metadata and exact-owned stop/removal/volume-absence evidence.
- [ ] Require the same private log tmpfs and guard for later approved offline simulation/install containers, with no log bytes entering the committed added layer; preserve no-upgrade/signature/package/file/layer/configuration and frozen-image review requirements.
- [ ] Keep image/toolchain/sentinel/harness outcomes unverified until actually observed under their separate approved steps; preserve original Task2 authority and every production/runtime/grant/service/deployment/readiness denial.

APK-log correction synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621303386 and Project8 readback at `2026-11-04T02:57:35.939965+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


APK-log correction adoption: independently approved checkpoint `bd59558a78a11448f89e35ef34f910bbb64cedbe` (receipt `9db69a7758228fb8997b7c1ca5f5d90c1cc7c32f`) adopted at `cc0945fb841459c68b7a6e4ced8dcb802640b979`, directly after retained failed evidence `6577207980f24e61c51ab0fcc8198ded18c0d1a4`. Five harness54ab files and raw blocker receipt remain unchanged. Live Issue186/Project8 synchronization https://github.com/lucronn/autodata/issues/186#issuecomment-6621339347 read back 2026-11-04T03:00:29.931234+00:00; exact hashes in dedicated APK-log record and predecessor Project index preserved verbatim in comment. Adoption only: no Docker/create/start/download/retry; full adopted-SHA preflight and root verification/new Task1A dispatch still required. Original Task2 and all runtime/production/readiness outcomes remain unauthorized/unverified.


## PG17 acquisition-only writable overlay successor: plan-only

Goal: Replace only the blocked read-only PG17 APK acquisition root with a disposable inspected writable overlay, require stopped overlay/baseline audits before accepting APK output, and preserve offline installation, separate harness authority and every production/readiness denial.

Successor plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-overlay.md`; dedicated task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-overlay.json`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-overlay.json`. Base226cb50f preserves both actual Task1A exit99/0APK/cleanup attempts. Only acquisition drops `--read-only` and requires explicit isolated writable root overlay; exact image, unchanged signed APK payload/official bridge scope/caps/resources/two binds/four private tmpfs remain. Require stopped complete docker diff with lock/baseline-only allowlist and unchanged package/keys/repos/PG hashes before any APK output acceptance; acquisition overlay/container is never committed, restarted, reused or passed to offline stages. Exact-owned cleanup/absence/volume inventory mandatory. Offline simulation/install/final-image/Task2 authority unchanged; independent exact-gate review/new Task1A dispatch required. No planning container/download/retry/image/harness action.

Concrete todo:

- [ ] Synchronize both preserved exit99 attempts, acquisition-only overlay decision, exact create/audit/cleanup contracts and unchanged offline/harness limits in Issue186/Project8 and canonical docs; commit/push and pass pinned preflight for independent review.
- [ ] After independent exact-checkpoint review and fresh coordinator Task1A dispatch only, create a new exact-base acquisition container with one disposable writable root overlay and unchanged private mounts/caps/network/commands; inspect its full created configuration and record baseline file hashes before start.
- [ ] Run only the unchanged signed official APK acquisition payload under the existing bounded supervisor; require zero exit, unchanged baseline package/key/repository/PG data and an exact stopped docker diff audit before freezing any APK output.
- [ ] Never commit, restart or reuse acquisition containers; retain every failure/audit/cleanup receipt, remove only the captured exact-owned ID/volumes and verify absence/unchanged volume inventory before downstream use.
- [ ] Keep offline simulation/install/commit configuration and original Task2 separately authorized and unchanged; no image/toolchain/harness/runtime/production readiness follows from plan synchronization or synthetic guard fixtures.

Acquisition-overlay successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621400986 and Project8 readback at `2026-11-04T03:04:46.045770+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.


Acquisition-overlay adoption: approved checkpoint `26989e1de7a71ac4f7c23da043dd367548e2ba45` (receipt `80d4a20dcd7603a81d1ef96307e94fafe32caafe`) adopted at `1fe22c943143d8955624ed75c0f378bdb2dc0439`, directly after actual second failed evidence `226cb50fabfbc53c9f674dd72fae9b42aa3775d0`. Five harness54ab files and both raw exit99 receipts unchanged. Issue186/Project8 live readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621449880 at 2026-11-04T03:08:28.641173+00:00; exact hashes in dedicated overlay record and full predecessor Project index preserved verbatim in comment. This is adoption only: no Docker/create/start/download/retry/install/image commit; adopted full-SHA preflight and root verification/new Task1A dispatch required. Offline stages/Task2 remain separately unauthorized; runtime/production/readiness unverified.


## PG17 empty bind-target diff successor: plan only

Permit only proven Docker-created empty acquisition bind-target directories in the stopped overlay diff, retain every other audit and cleanup constraint, and keep all quarantined APKs unusable.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-bind-targets.md`; record `docs/agents/records/2026-11-04-workshop-pg17-bind-targets.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-targets.json`. Retained e1ca208 attempt exited0/signatures33 but failed strict diff on A /apks and A /control;33 APKs remain quarantined and never reusable. Only exact added empty root-owned directories may pass after absent saved-base targets, exact prestart binds and bounded created/stopped underlying filesystem export audits. Files/children/other paths/missing proof reject. All original constraints, offline/Task2 authority and cleanup unchanged. No planning Docker/download/retry/harness; independent exact-gate review/new dispatch pending.

Concrete todo:

- [ ] Synchronize exact red receipt, bounded structural audit and context-bound diff guard in Issue186/Project8/canonical docs; push exact gate and pinned preflight for independent review.
- [ ] After independent exact-gate review/adoption and fresh coordinator Task1A dispatch only, create a fresh acquisition container and collect full prestart bind inventory plus bounded underlying filesystem structural audit before start.
- [ ] Require exact empty directory metadata before/after, absent saved-base targets, unchanged 27 baseline records and original complete stopped diff/signature/exit audits; reject files, descendants, aliases, deletions and missing proof.
- [ ] Retain prior 33 quarantined APKs as failed evidence, never accept/reuse them; any future fresh output requires all audits and exact-owned removal/absence/volume proof.
- [ ] Keep acquisition commands/network/caps/mounts and offline simulation/install/image/Task2 authorities unchanged; no planning Docker/download/retry/harness action or readiness claim.

Bind-target successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621533357 and Project8 readback at `2026-11-04T03:13:58.668948+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned bind-target successor checkpoint: `016ea37722f36fa0c8b2b509884e75bef6ac41b2`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-targets-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621541625. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed bind-target gate adoption and mandatory operation ordering

Adopted source gate `016ea37722f36fa0c8b2b509884e75bef6ac41b2`, receipt `c7d57a3347621c5559d5a671997142da1a1f43dc`; exact reviewed plan SHA256 `40e0591c8742a37983cf289d565c9df7d4e263c7caa5cc4e8e7f38b3b36f49ed`. Coordinator relayed independent approval of this exact plan. Adoption branch `codex/workshop-pg17-bind-target-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-bind-target-adoption.json`. This adoption performs no Docker operation or retry and conveys no production/harness readiness.

**Mandatory future order (resolves the created-state mountpoint feasibility condition):** (1) create exact-owned fresh acquisition container under the unchanged approved argv, validate full created inspect/config/bind inventory and pinned base archive; (2) complete **all inherited prestart `docker cp` baseline snapshots** and the unchanged27-record saved-base comparison while still created/never-started; these existing copy operations materialize the bind-target directories; (3) only **after those copies finish successfully**, perform the first bounded created-state underlying filesystem export and full prestart diff, requiring the exact empty root-owned `/apks` and `/control` directories plus `A /apks` and `A /control`; (4) only after every inherited and new prestart guard passes may the coordinator-dispatched payload start; (5) after stopped exit0, perform the bounded stopped export/full diff/unchanged-baseline audits, then exact-owned cleanup and output acceptance boundary. Never run the first export/diff before the inherited copies or start merely to materialize targets. Failed copies, missing/changed/nonempty targets or any ambiguity fail closed and clean the exact owned attempt. No extra container command, mount or authority is added.

All prior export bounds/source semantics checks, acquisition payload/image/network/caps/resources/mounts, signature verification, quarantine, baseline/row/type/empty checks and cleanup remain mandatory. This ordering clarification does not accept or reuse the historical33 quarantined APKs. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged. No deployment, integration, production grant/runtime action or readiness follows.

Concrete adoption todo:

- [ ] Record independent approval of exact gate016ea377 and reviewed plan SHA256, synchronize adoption Issue186/Project8/canonical docs, then push and pin passing full-SHA preflight.
- [ ] Only after new coordinator dispatch, validate exact created acquisition ID/config/bind inventory; complete every inherited prestart docker cp baseline snapshot and unchanged27-record comparison BEFORE first created-state export/diff.
- [ ] Then require bounded created-state underlying empty-directory export and exact A /apks,A /control diff; only after all guards pass may the fixed acquisition payload start.
- [ ] Require matching stopped structural export, complete original baseline/diff/signature/exit audits and exact-owned cleanup/absence/volume proof before accepting any newly acquired APK closure.
- [ ] Never accept/reuse historical33 quarantined APKs; no Docker/download/install/harness on adoption turn; offline stages/Task2 and all production/readiness denials unchanged.

Reviewed bind-target adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621594414 and Project8 readback at `2026-11-04T03:18:09.877892+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed bind-target adoption checkpoint: `76fd86e5a356ae611d643e621f9ae03660d50206`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-bind-target-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621597936. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 complete mount-record ordering successor: plan only

Correct only order-sensitive acquisition Mounts inspection comparison using complete records keyed by unique exact Destination, retaining all raw/canonical hashes, red receipts and unchanged acquisition guards.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-mount-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-mount-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order.json`. Base da1f42a; actual fresh acquisition attempt stopped before startup on inspect Mounts array order only,0 APKs, exact-owned cleanup/absence and unchanged volume inventory. Preserve red result/diagnosis exact hashes in dedicated evidence. Replace only top-level Mounts array order-sensitive equality with complete-record canonical JSON by unique exact Destination; duplicates/missing/extra paths or any field drift reject. All original config/structural/baseline/signature/diff/payload/cleanup and offline/Task2 limits unchanged. Live tracking synchronized; independent exact-checkpoint review/root dispatch remain pending. No retry authority. No planning Docker/retry/download/harness.

Concrete todo:

- [ ] Synchronize the narrow mount-order plan, exact red receipts and complete-record fixtures with Issue186/Project8/canonical docs only after coordinator releases tracking slot; commit/push and pin passing full-SHA preflight for independent review.
- [ ] Require independent exact-checkpoint review/adoption and fresh coordinator Task1A dispatch before any new Docker operation; use a new private run and never restart/reuse prior failed containers or APKs.
- [ ] Retain raw before/after inspect bytes and SHA256; canonicalize only top-level Mounts array record order by unique exact Destination, require exactly /apks and /control and preserve every complete record field/value.
- [ ] Require original complete config/mount predicates plus canonical equality at every acquisition Mounts comparison; duplicate/missing/extra destinations, field/type/value drift, invalid JSON or ambiguous input fail closed.
- [ ] Keep all predecessor created-copy/export/diff ordering, structural/exit/signature/baseline/resource/network/payload/cleanup bounds and offline/Task2 separation unchanged; no planning Docker/retry/download/harness or readiness claim.

Mount-order successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621665171 and Project8 readback at `2026-11-04T03:23:07.931845+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned mount-order successor checkpoint: `cdbedc871104484d931113ce74c84be0b8ba449e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621669759. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed complete mount-record ordering adoption: plan only

Adopt independently approved source gate `cdbedc871104484d931113ce74c84be0b8ba449e`, receipt `1e43e64a9b1b8237bbc9656aa311d0c7d13d5698`; exact reviewed plan SHA256 `8eb158a7101959b23a096487366692b6f8990c73e6ad4b79c303eb4cae5a302b`. Source review evidence `/tmp/autodata-pg17-mount-order-cdbedc87-review.json` retained as `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-review.json` with original hash. Adoption branch `codex/workshop-pg17-mount-order-adoption`; dedicated record `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-mount-order-adoption.json`. Live tracking synchronized after coordinator slot release. Root must verify the full adopted-SHA preflight and issue fresh Task1A dispatch before any runtime action.

The sole correction is top-level Mounts array comparison by complete records keyed/sorted by unique exact Destination. Retain every record field and raw before/after inspect hashes plus canonical hash; missing/extra/duplicate destinations, field additions/removals/type/value drift or malformed/duplicate-key JSON fail closed. All original config predicates and HostConfig equality remain. No extra Docker command, mount, capability, source, network or retry authority. All inherited created-copy27-baseline-before-export/diff ordering, exact empty underlying-target proof, bounded exports, full stopped diff/context/baseline/signature/exit audits and exact-owned removal/absence/volume inventory remain mandatory.

The prior created-state attempt remains failed with0 APKs; result SHA256 `6db4e39f3b01adb90b42985b44a6949b6670774fc8fc9e0f84ab7be96c4f5c4d`, diagnosis SHA256 `5654ed1637e63f2facb6ee2b52a8589fb685e7996bac0e44498b130db2376695`. Missing structural metadata is not inferred retroactively. Historical33APKs remain quarantined and never reusable. Root must verify full adopted-SHA preflight and separately dispatch any new Task1A. No adoption Docker/create/start/export/retry/download/install/image commit/PG startup/harness action; offline stages/Task2 and production/provider/cloud/runtime authority unchanged. All readiness remains false.

Concrete adoption todo:

- [ ] After coordinator tracking-slot release, synchronize exact independent approval/plan hash and unchanged Task1A scope in Issue186/Project8/canonical docs, preserve CURRENT prior Project index verbatim/hash, commit/push and pin full-SHA preflight.
- [ ] Only after root verifies adopted pinned preflight and dispatches fresh Task1A, use a new exact-owned private run; compare complete Mounts records by unique exact Destination, retaining raw before/after/canonical hashes and rejecting any missing/extra/duplicate destination or field drift.
- [ ] Keep all inherited complete config checks, mandatory prestart cp27 baseline comparison BEFORE created export/diff, bounded created/stopped empty-target proof, full stopped diff/signature/exit audits and exact-owned cleanup/absence/volume inventory unchanged.
- [ ] Preserve all prior failed/quarantined outputs and red receipts; never reuse historical33APKs or restart/reuse failed containers; no offline simulation/install/image commit/PG startup/harness on this adoption turn.
- [ ] Keep Task2/production/provider/cloud/runtime actions separately unauthorized and all readiness unverified; adoption alone is not a fresh retry dispatch.

Reviewed mount-order adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621749496 and Project8 readback at `2026-11-04T03:28:59.162164+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed mount-order adoption checkpoint: `3c96b04df9ff4b7929ca8955a92d89eef6cc7617`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-mount-order-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621754534. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 acquisition diagnostics and structured volume receipts: plan only

Correct only acquisition diagnostic false positives and volume inventory serialization by anchored status checks and bounded structured complete-volume inspection, retaining all existing guards and failed-output quarantine.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-acquisition-receipts.md`; record `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-acquisition-receipts.json`. Retained second-attempt result/diagnosis hashes and full offline replay in `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-evidence.json`. Attempt exited0 and passed structural/context/baseline guards, then failed host substring/Labels CSV order checks; all33 fresh APKs quarantined NEVER reusable, prior33 also never reusable. Correct only anchored status/empty-stderr diagnostics and bounded read-only complete structured volume inspect metadata by unique Name; every field/value retained, only JSON key order ignored. Explicit new metadata-read authority requires reviewed/adopted gate/root dispatch. All other Task1A/Task2 constraints unchanged; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Replay the revised fixed pure predicates against complete retained second-attempt evidence and all existing positive/negative fixtures; synchronize goal/plan/todo/red evidence/structured inventory authority with Issue186/Project8/canonical docs after coordinator slot release; commit/push and pin full-SHA preflight.
- [ ] Require independent exact-gate review/adoption and root verification/fresh Task1A dispatch before any Docker/retry; use a new private exact-owned run, never historical quarantined APKs or failed containers.
- [ ] Use unchanged bounded fixed acquisition payload and source/signature/index/hash checks; classify only empty stderr plus successful supervised attach/stopped status and reject anchored diagnostic forms, preserving full raw output and hashes.
- [ ] Before create and after exact-owned removal, capture bounded volume ls names and one bounded read-only structured volume inspect per exact name; compare complete objects by unique Name preserving every field/value and ignoring JSON object key order only.
- [ ] Keep mandatory27 prestart copies BEFORE first created export/diff, complete Mounts canonical guard, empty underlying target audits, full stopped diff/context/baseline/exit checks and owned cleanup unchanged; no offline/install/image/PG/harness/production readiness follows.

Acquisition-receipts successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621817348 and Project8 readback at `2026-11-04T03:33:51.920926+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned acquisition-receipts successor checkpoint: `4bc40e26ca12521be8f20282b897f5af68d0195e`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-acquisition-receipts-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621820832. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## PG17 diagnostic Unicode Cc review correction: plan only

Correct only the blocked acquisition diagnostic character filter to reject Unicode Cc controls except LF/tab; preserve all existing receipt guards, quarantine and runtime denials.

Corrected plan `docs/superpowers/plans/2026-11-04-workshop-pg17-control-filter.md`; record `docs/agents/records/2026-11-04-workshop-pg17-control-filter.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-control-filter.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-control-filter-evidence.json`. Prior4bc40e26 remains independently BLOCKED for DEL/C1 acceptance. Only diagnostic unicodedata import/Cc predicate changed, LF/tab sole control exceptions; complete83-case offline replay plus65 Cc probes pass (148total/0fail). All structured-volume and predecessor constraints unchanged; both33APK sets quarantined NEVER reusable. Independent exact-corrected-checkpoint re-review/adoption/root dispatch required; no planning Docker/retry/download/harness.

Concrete todo:

- [ ] Preserve exact blocked gate/plan hash and reproduced DEL/C1 negatives; update only diagnostic Cc filter/import, rerun complete83-case pure/replay suite plus65 Cc probes, then synchronize Issue186/Project8/canonical docs after coordinator tracking-slot release.
- [ ] Commit/push docs-only corrected checkpoint, pin passing full-SHA preflight and exact tracking readback while preserving CURRENT Python SIGTERM and PG predecessor index verbatim/hash.
- [ ] Require independent exact-corrected-checkpoint re-review/adoption, root verification and fresh Task1A dispatch before any Docker/retry/download/harness; previous blocked gate grants no adoption authority.
- [ ] Keep structured complete volume metadata collection/comparison and every original source/payload/config/mount/copy/export/diff/baseline/signature/cleanup bound unchanged; both33APK sets remain quarantined NEVER reusable.
- [ ] Retain all red receipts as failed and offline replay as predicate evidence only; no retrospective acceptance, offline install/image commit/PG startup/harness/production action or readiness claim.

Unicode Cc corrected successor synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621857074 and Project8 readback at `2026-11-04T03:36:44.664156+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Independent exact-checkpoint review/new preparation dispatch pending; all Docker/download/install/image/harness actions remain unexecuted.

Pinned Unicode Cc corrected successor checkpoint: `b96a68e59a370314a207e67b98d67a9949584432`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-control-filter-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621859742. Independent review/new preparation dispatch pending. No container/image/package/harness action or readiness claim.


## Reviewed Cc-safe acquisition receipt adoption

Adopt independently approved corrected gate `b96a68e59a370314a207e67b98d67a9949584432`, receipt `eee037dd1857cec1d0817b1b3421c7280c9284f6`; exact reviewed control-filter plan SHA256 `ad2a433f532e1b7b8000588d126d9789392f6e593a5c460681b900bff403420e`. Approval was relayed directly by coordinator after independent re-review. Historical predecessor4bc40e26 remains a blocked superseded checkpoint; this adoption consumes only the corrected approved chain. Adoption branch `codex/workshop-pg17-receipts-adoption`; record `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption.json`, task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-receipts-adoption.json`.

The fixed classifier requires empty stderr and zero successful supervised/stopped status, rejects anchored diagnostic forms, and rejects every UnicodeCc character except LF/tab. All original source-output/index/key/signature/package/hash checks remain mandatory. Structured volume metadata uses bounded read-only ls names plus one complete inspect object per exactName: <=32names,60s total inventory,10s each inspect,512KiBstdout/64KiBstderr each,16MiB totalstdout/2MiBstderr. Exact same Name set; compare COMPLETE objects including all fields/values and null/map distinctions, ignore only JSON object key order; duplicate/missing/extra names/fields or any drift fail. Raw/hash/canonical receipts are mandatory. No CSV Labels substitution or four-field projection.

Full predecessor chain retained: exact cached image/payload/repositories; no source/secret bind; private inherited PGDATA override plus original tmpfs/binds; original network/caps/security/resources/output/deadline bounds; complete config and uniqueDestination Mounts records; ALL27 inherited prestart cp snapshots+unchanged comparison BEFORE first created export/diff; bounded created/stopped underlying empty target proof; complete stopped diff/context/baseline/signature/exit audits; exact-owned stop/rm--volumes/absence/structured inventory proof. No acquisition commit/restart/reuse; no arbitrary retry/guard change. Offline simulation/install/image review and original Task2 remain separately authorized and unchanged.

Both historical33APK sets (overlay first and bound-target second payload attempts) remain quarantined, unaccepted and NEVER reusable. Red result/diagnosis and missing prior structured proof are not rewritten. Pure148-case/replay success is predicate evidence only. Root must independently verify full adopted-SHA preflight and issue a FRESH Task1A dispatch before any new Docker operation. This docs-only adoption performs no Docker/create/start/export/retry/download/install/image/PG/harness/implementation or production action; no readiness follows.

Concrete adoption todo:

- [ ] Synchronize exact corrected independent approval/plan hash and full Task1A guard chain in Issue186/Project8/canonical docs while preserving CURRENT prior Project index/detail verbatim/hash; commit/push and pin full-SHA passing preflight.
- [ ] Require root independent adopted-gate verification and FRESH Task1A dispatch before any Docker/retry; use a new private exact-owned run and never historical failed containers/APKs.
- [ ] Use the fixed anchored diagnostic/status classifier rejecting all UnicodeCc except LF/tab, empty stderr and successful supervised/stopped status; retain complete raw outputs/hashes and all original source/index/signature/hash checks.
- [ ] Collect complete structured volume inspect objects for exact boundedls names before create/after owned removal:32names/60s inventory/10s perinspect/512KiBstdout64KiBstderr perinspect/16MiB totalstdout2MiBstderr; compare complete objects by uniqueName, all fields/values preserved and only JSON key order ignored.
- [ ] Keep all inherited image/payload/network/caps/resources/private mount guards,27 prestart copies BEFORE first export/diff, complete Mounts comparison, bounded empty underlying target exports, full stopped diff/context/baseline/exit and owned cleanup/absence checks; both33APK sets remain quarantined NEVER reusable.
- [ ] No adoption Docker/retry/download/install/image commit/PG startup/harness/implementation/integration/production/provider/cloud action; offline stages/Task2 separate and all readiness remains unverified.

Reviewed Cc-safe acquisition receipt adoption synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621879747 and Project8 readback at `2026-11-04T03:38:22.919883+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Source exact-plan independent review approved; new coordinator preparation dispatch required; all adoption Docker/download/install/image/harness actions remain unexecuted.

Pinned reviewed Cc-safe acquisition receipt adoption checkpoint: `691f187302440509c23da99f4fb9e1adb9cd52a4`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-receipts-adoption-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621883014. Reviewed source plan approved; fresh coordinator preparation dispatch required. No container/image/package/harness action or readiness claim.


## PG17 independently approved frozen closure: docs-only index

Record independent acceptance of the exact Task1A frozen signed33APK closure as input only, preserve acquisition/cleanup evidence and keep Task1B/image/Task2 unauthorized pending a new gate/review/root dispatch.

Acceptance plan `docs/superpowers/plans/2026-11-04-workshop-pg17-closure-acceptance.md`; record `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-closure-acceptance.json`; exact evidence index `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-evidence.json`. Executed691f187 result SHA19002cbf07ce2879e277e1a3e7bc1d69ac28ae8e919e29a85bc4d7a415ee3d43; frozen33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238. Independent audit approval saved at `/tmp/autodata-pg17-task1a-closure-review.md`, SHA256 `bb0173a6f7a46f52fd7a4c3bfbcfcf00d2db5714f179abfe1124675a69616b5b`, and relayed directly by coordinator; all174receipt refs/33host hashes verified, exact cleanup/absence/four-volume equality passed. Accepted as frozen input only; raw pending-review status remains immutable. NEW Task1B gate/review/root dispatch required; offline simulation/install/image/Task2 remain unauthorized/unexecuted, both prior33APK quarantines NEVER reusable. JS deadline slot released; frozen-input acceptance index synchronized. No Docker/install/harness.

Concrete todo:

- [ ] After JS deadline coordinator releases Issue186/Project8 slot, synchronize exact reviewed closure/result/manifest/hash acceptance in Issue186/Project8 and canonical docs, preserving CURRENT full index/detail verbatim/hash; commit/push and pin docs-only full-SHA preflight.
- [ ] Keep raw Task1A receipts and accepted-apk-manifest bytes immutable; use this adjacent acceptance index to record independent review without rewriting the original pending-review manifest status or either failed/quarantined attempt.
- [ ] Accept only exact33APK filenames/versions/architectures/hashes in the pinned manifest as future input; verify all host hashes again before any later authorized consumer and reject mutation or substitution.
- [ ] Require a NEW decision-complete synchronized Task1B gate, independent review, root verification and fresh dispatch before offline simulation/install/image commit or toolchain inspection; no execution authority follows from closure acceptance.
- [ ] Keep original Task2 PG startup/harness separately unauthorized, all runtime/production/grants/services/deployment readiness unverified, and both historical33APK sets quarantined NEVER reusable.

Frozen-input closure acceptance synchronized by live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6621963547 and Project8 readback at `2026-11-04T03:44:34.583302+00:00`; exact hashes in dedicated record. Full prior Project index preserved verbatim. Input closure independent approval recorded; NEW Task1B synchronized gate/review/root dispatch required; no Docker/install/image/PG/harness actions.

Pinned frozen-input closure acceptance index checkpoint: `04093a5e176499e7d8de18e9573f9fea3abe9d3a`; full-SHA preflight `status: synchronized`, `errors: []`, exit0. Receipt `docs/agents/records/2026-11-04-workshop-pg17-closure-acceptance-preflight.json`; exact-pin Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6621970383. Frozen input independently accepted only; NEW Task1B gate/review/root dispatch required. No container/image/package/harness action or readiness claim.


## PG17 Task1B offline simulation-only successor

Gate one bounded offline Task1B simulation of the immutable independently accepted33APK closure using exact20 new-package inputs, unchanged baseline and complete cleanup; installation/image/Task2 remain separately unauthorized.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-task1b-simulation.md`; record `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-task1b-simulation.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-evidence.json`. Independent feasibility report SHA256e82b42d46639d0149b7cf644cb0bbdd29f86bb020cf5410fcdfcea007779ab88. Accepted33APK manifest SHAcfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238 remains immutable; exact20 add operands/all33 verification, created/stopped empty bind targets, exact inherited0600zero lock, deterministic Cc-safe parser/unchanged45+27 baseline, pinned BusyBox trigger.58 metadata dependencies (36base/22new) and 95 pure parser fixtures are NOT solver success. Docs only; simulation denied until independent review/adoption/root verification/fresh dispatch. Installation/image/Task2/production remain unauthorized/unverified, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only simulation successor in Issue186/Project8/canonical notes, preserving CURRENT full prior index/detail verbatim and SHA256; commit/push and pin full-SHA passing preflight.
- [ ] Obtain independent review of this exact simulation-only checkpoint; require coordinator adoption/root verification and fresh one-attempt dispatch before any Docker command.
- [ ] On authorized fresh simulation only, reverify all33 immutable APK hashes/signatures, use exact20 literal apk-add paths, inspect complete offline resources/mounts and mandatory prestart27 copies before created export/diff.
- [ ] Require deterministic bounded parser with exactly20 additions and no baseline actions, complete unchanged27/package45/world/keys/PG/scripts/trigger/lock state and created/stopped empty bind-target proof; fail closed/quarantine/no retry.
- [ ] After exact-owned removal/absence/complete-volume equality, independently review simulation receipts; a NEW installation gate must pin same20 APK argv and audit BusyBox-trigger effects. No installation/image commit/PG/harness/readiness is authorized now.

Task1B simulation-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622084338 and Project8 readback at `2026-11-04T03:53:46.055147+00:00`; full prior closure index/detail preserved verbatim/hash in comment and dedicated record. Independent exact-checkpoint review/adoption/root verification/fresh dispatch required; no Docker/retry/install/image/harness operation or solver success.

Pinned Task1B simulation-only successor gate: `808225f5fa14ca0c7dc308a5d39cd65396c694f7`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622095482. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.

Pinned Task1B simulation-only successor gate: `dafbdea85477437e8cf20969b3c6571aa59c2c50`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-task1b-simulation-corrected-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622103154. Independent review/adoption/root verification/fresh dispatch required before simulation. No Docker/solver/install/image/PG/harness or readiness claim.


## PG17 Task1B CapAdd-only ordering successor: plan only

Correct only full HostConfig.CapAdd array order comparison while preserving exact three approved unique capabilities and all other simulation guards; gate ONE fresh offline Task1B simulation after exact review/adoption/root dispatch.

Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-cap-order.md`; record `docs/agents/records/2026-11-04-workshop-pg17-cap-order.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-cap-order.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-cap-order-evidence.json`. Failed resultSHAf870e36f11b4eea70478f0932ea446aa904631bcda8f89b28e65dbbc6bea8224/diagnosisSHA067a4cb3284da093479301eada2519a7944a07c36839e9262a2e241f8218e37d: never started, exact cleanup/absence/all33 inputs/full4volumes unchanged; independent diagnosis/cleanup acceptance ONLY. Only HostConfig.CapAdd order may normalize after proving exact3unique approved strings; all other complete comparisons/95+148 guards unchanged. 123 new pure cases pass incl6 permutations and negative field/type/duplication drift. NEW empty PREP/container and exact review/adoption/root preflight/fresh ONE-attempt dispatch required. No planning Docker/simulation/install/image/PG/harness; all readiness false, both prior33APK quarantines NEVER reusable.

Concrete todo:

- [ ] Synchronize this docs-only CapAdd successor with Issue186/Project8/canonical notes and preserve CURRENT complete prior index/detail verbatim plus SHA256; commit/push then pin full-SHA passing preflight.
- [ ] Obtain independent exact-checkpoint review, coordinator adoption/root full-SHA preflight and fresh ONE-attempt simulation-only dispatch before Docker; use NEW empty private PREP, unique name/cidfile and newly created exact-owned container.
- [ ] Compare only HostConfig.CapAdd order-insensitively with exactly three unique strings CAP_CHOWN/CAP_FOWNER/CAP_DAC_OVERRIDE; retain all complete raw objects/hashes and reject any missing/extra/duplicate/type or non-CapAdd field drift.
- [ ] Retain and rerun all95 simulation parser plus148 predecessor fixtures and the new six-permutation/negative suite; preserve immutable failed-run result/diagnosis and all accepted/quarantined APK boundaries.
- [ ] On separately dispatched simulation, retain unchanged exact script/hash,33 verification/20 selection, offline caps/resources, created-copy-before-export/diff, stopped baseline/lock/trigger/mount/diff, cleanup/absence/full-volume proofs; any discrepancy stops with no retry, installation/image/PG/harness unauthorized.

CapAdd-only successor synchronized by exact live Issue186 body/comment https://github.com/lucronn/autodata/issues/186#issuecomment-6622201950 and Project8 readback at `2026-11-04T04:02:37.852702+00:00`; full CURRENT JS index/detail/pin retained verbatim/hash in comment and record. Independent exact-checkpoint review/adoption/root preflight/fresh dispatch required; no Docker/simulation/install/image/PG/harness and no retrospective acceptance.

Pinned CapAdd-only successor checkpoint `cde9652c0e3dce9a9083540d15cb25b3682f144d`; full-SHA preflight `status: synchronized`, `errors: []`, exit0; receipt `docs/agents/records/2026-11-04-workshop-pg17-cap-order-preflight.json`; exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622210398. Independent exact review/adoption/root preflight/fresh ONE-attempt dispatch still required. Historical run blocked; no Docker/simulation/install/image/harness or readiness authority.


## PG17 explicit offline APK/OOM lifecycle successor: LOCAL DRAFT ONLY

Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

Draft plan `docs/superpowers/plans/2026-11-04-workshop-pg17-offline.md`; record `docs/agents/records/2026-11-04-workshop-pg17-offline.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-offline.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`. Failed resultc1f6af1f/diagnosis0660472e remain immutable FAILED; cleanup accepted only. Exact3.0.8 global no-network+empty repositories file on all5 invocations; original repositories cmp/keys/signatures and empty stderr unchanged. ExactEngine GitCommit source plus retained raw supports ONLY OomKillDisable false-created/null-stopped on pinned unsupported cgroupv2 context; CapAdd rule/other full fields unchanged. 107 new+366prior pure checks passed; no runtime. LOCAL UNSYNCHRONIZED pending draft review and later coordinator tracking slot; no Docker/retry/install/image/PG/harness or readiness.

Concrete todo:

- [ ] Keep this draft LOCAL/UNSYNCHRONIZED pending independent draft review; do not mutate Issue186/Project8 while publisher owns tracking and do not run Docker/retry/install/image/PG/harness.
- [ ] Independently review exact new script/argv/zero-byte override/source proof and phase-bound OomKillDisable predicate plus all pure negative fixtures; preserve failed result/diagnosis as failed, no retrospective acceptance.
- [ ] Only after coordinator authorizes tracking: preserve full CURRENT Project index/detail verbatim/hash, synchronize Issue186/Project8/canonical docs/task, commit/push a new gate and pin full-SHA passing preflight.
- [ ] Only after independent exact synchronized-gate review/adoption/root verification/fresh dispatch: one NEW empty PREP/container, exact33 verification/20 selected simulation, every apk invocation explicitly offline with pinned empty override, unchanged original repositories/keys, empty stderr.
- [ ] Require created/stopped empty bind target/export/diff/27+45 baseline/lock/BusyBox/Config/Mounts/CapAdd/cleanup/volume proofs; normalize only exact false-created to null-stopped on exact unsupported engine context; any other discrepancy stops/no retry. Installation/image/Task2 remain unauthorized.


## PG17 offline/OOM successor synchronized planning checkpoint

Propose one fresh offline Task1B simulation with explicit no-network/empty-repository APK argv and only source-proven created-false to stopped-null OomKillDisable lifecycle comparison; preserve all stderr/signature/state/cleanup guards.

Reviewed local draft `d3edce5094896dc4c11cc6e186ce4738418ac6c2`: coordinator relayed independent read-only draft PASS, all473 pure checks, no blockers. This is not runtime approval. Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-offline.md`; record `docs/agents/records/2026-11-04-workshop-pg17-offline.json`; evidence `docs/agents/records/2026-11-04-workshop-pg17-offline-evidence.json`; branch `codex/workshop-pg17-offline-plan`. Failed result `c1f6af1f8242eff80da993cef370e8bdd7cbd47da2a7f4fc5c2731bbf36d9c29`/diagnosis `0660472e7f2a2a72403cd609ce60ef615e0e301c830e4c08f5e2e2c279edf4ab` immutable FAILED; diagnosis/cleanup only accepted. One NEW empty PREP/container is conditional on independent exact-checkpoint review, root preflight/adoption and fresh dispatch. All five apk invocations explicitly no-network with pinned zero-byte repository override; original repositories cmp/keys/all33 signatures and empty stderr unchanged. Only exact-source-proven OomKillDisable created false/stopped null on pinned unsupported engine context, plus prior CapAdd-order rule; all other complete fields and lifecycle/source/mount/export/baseline/cleanup/volume guards unchanged. Historical results cannot be accepted retrospectively; both33 APK quarantines remain forbidden. No Docker/retry/install/image/PG/harness/production/readiness authority.

Concrete todo:

- [ ] Independent local draft review PASS at d3edce5094896dc4c11cc6e186ce4738418ac6c2 (473 pure checks); synchronize only this reviewed docs-only scope, preserving all prior histories and denials.
- [ ] Obtain independent exact synchronized-checkpoint review, root full-SHA preflight/adoption and fresh ONE-attempt simulation dispatch before any Docker operation.
- [ ] Preserve CURRENT Stage0/staging/PG/JS Project index and all detail/pin bodies verbatim/hash; verify exact Issue186/Project8 readback and pin committed full-SHA passing preflight.
- [ ] Only after independent exact synchronized-gate review/adoption/root verification/fresh dispatch: one NEW empty PREP/container, exact33 verification/20 selected simulation, every apk invocation explicitly offline with pinned empty override, unchanged original repositories/keys, empty stderr.
- [ ] Require created/stopped empty bind target/export/diff/27+45 baseline/lock/BusyBox/Config/Mounts/CapAdd/cleanup/volume proofs; normalize only exact false-created to null-stopped on exact unsupported engine context; any other discrepancy stops/no retry. Installation/image/Task2 remain unauthorized.

Exact live Issue186 body/detail https://github.com/lucronn/autodata/issues/186#issuecomment-6622351785 and Project8 readback verified at `2026-11-04T04:13:41.594272+00:00`; source preservation/index/detail/pin bodies and hashes in `docs/agents/records/2026-11-04-workshop-pg17-offline-tracking.json`. This supersedes earlier LOCAL DRAFT/UNSYNCHRONIZED lifecycle text only; technical predicates unchanged. Exact committed checkpoint/full-SHA preflight follows; no runtime authority.

Pinned explicit-offline/OOM successor checkpoint `3e4d1b0b728c81ce8dd1ae84d207df645e6bfbf1`; full-SHA preflight `status: synchronized`, `errors: []`, exit0/empty stderr; receipt `docs/agents/records/2026-11-04-workshop-pg17-offline-preflight.json`; exact Issue186/Project8 full-SHA readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622361427. All nine prior index/detail/pin preservation comments verified verbatim/hash. Independent exact synchronized-checkpoint review/adoption/root verification/fresh ONE-attempt dispatch still required; no Docker/retry/install/image/PG/harness/readiness.


## PG17 offline installation-only successor: synchronized planning gate

Goal: Design one fresh offline actual installation of the accepted33 closure/exact20 selection with a finite source-derived stopped-state audit and exact cleanup; image/PG/harness remain unauthorized.

Corrected local draft independently reviewed PASS (coordinator relayed), exact plan SHA256 `a0a0ce8ac827d60b86f087d305b3a3fdc689edea8f91fb4404bc8a7bf2049387`, evidence SHA256 `d49597e41cf6a65e43d51b84955212a0e8ed4d41974bc8c883ea4db6f411540c`; all584 host-only checks replayed. This is docs-only synchronization, not installation approval. Plan `docs/superpowers/plans/2026-11-04-workshop-pg17-install.md`; record `docs/agents/records/2026-11-04-workshop-pg17-install.json`; task `docs/agents/tasks/2026-11-03-production-release/workshop-pg17-install.json`; frozen technical evidence `docs/agents/records/2026-11-04-workshop-pg17-install-evidence.json`; branch `codex/workshop-pg17-install-plan`, base receipt `3b67536c17db53064c79fc1f63d2cbda1d0fe935`. Accepted simulation result `ac093352ec670acff88fa28df1712d623fe268a38c30b32b0e623eeb11bb8565` under gate3e4d1b0 is SIMULATION ONLY. Frozen33 manifest `cfdcb2b2c2fd4d4c449397a8c7c3c38f1cc8247d891d8aa89effb6039ca31238` unchanged; both historical33 APK quarantines remain forbidden.

Proposed future ONE actual installation uses NEW empty private PREP/new exact-owned cached-base container; exact same20 operands/all33 signature checks, five explicit no-network+empty repository argv and original repositories/keys preserved; only remove --simulate. Source-derived BusyBox304 preexisting targets/EEXIST no-op, exact strings replacement, unchanged45 plus20 full FDB records/27-line checksum world, original10 scripts/exact trigger/zero-byte0600 lock, finite complete payload/hardlink/tree/diff projection. Raw512-byte physical TAR headers must all be counted/preserved/correlated; GNU L/K and PAX x/g/unsupported types reject, including scripts database. New tighter prestart299700000-byte ceiling and conditional stopped535610656-byte bound retain inherited512MiB/50000physical-header/60s limits. Full source/mount/resource/engine/CapAdd/OOM/context/copy/export/cleanup/complete-volume guards remain. Source-derived expected state is not installation success.

Independent exact synchronized-checkpoint review, root preflight/adoption and fresh ONE-attempt dispatch remain mandatory. No Docker, install, image commit/reuse, PG startup, harness/Task2, production/provider/cloud/activation/readiness or implementation-file authority follows. Existing Stage1A/M2A/Stage0/staging/PG/JS authorities/statuses/denials remain unchanged.

Concrete todo:

- [ ] Independent corrected local draft review PASS for exact planSHA a0a0ce8ac827d60b86f087d305b3a3fdc689edea8f91fb4404bc8a7bf2049387/evidenceSHA d49597e41cf6a65e43d51b84955212a0e8ed4d41974bc8c883ea4db6f411540c; retain all584 pure/replay checks and exact reviewed source/predicates.
- [ ] Synchronize docs-only gate preserving COMPLETE current Issue body/all113 comments and full Project index plus Stage1A/M2A/Stage0/staging/PG/JS details/pins verbatim/hash; commit/push, pin full-SHA passing preflight and verify exact full tracking readback.
- [ ] Obtain independent exact synchronized-checkpoint review, coordinator adoption/root full-SHA preflight and fresh ONE-attempt installation-only dispatch before any Docker operation.
- [ ] Only after fresh dispatch: new empty PREP/new exact-owned container, same immutable33/exact20 offline add without --simulate, full prestart/stopped/database/world/script/payload/physical-header/diff/bounds/cleanup proofs; any discrepancy stops/quarantines/no retry/image/PG/harness.

Exact Issue186/Project8 readback https://github.com/lucronn/autodata/issues/186#issuecomment-6622859754 at `2026-11-04T04:50:23.730780+00:00`; COMPLETE original Issue body/all113 comments/Project index (including Stage1A/M2A histories) retained verbatim+hash in `docs/agents/records/2026-11-04-workshop-pg17-install-tracking.json`. Prior authorities/statuses remain unchanged. Exact committed full-SHA pin follows; no installation authority.
