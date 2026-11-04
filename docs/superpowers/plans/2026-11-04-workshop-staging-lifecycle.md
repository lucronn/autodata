# Isolated Workshop GCE staging lifecycle implementation plan

> **For agentic workers:** Execute only a coordinator-released milestone after its own synchronized checkpoint and pinned preflight. Use superpowers:executing-plans. This document is a synchronized planning checkpoint, not implementation or live-operation authority.

**Goal:** Make the existing GCE staging topology executable through fixed bootstrap, private installation, controlled startup, no-work readiness and isolated recovery operations.

**Architecture:** Retain one dedicated staging GCE VM, a separate persistent disk, Caddy and the existing standalone Compose graph. The host consumes an independently authenticated immutable publisher release; it never builds application images. Root-owned fixed helpers manage state under a cross-operation lock, keep ingress in maintenance until checks pass, and fail closed after loss of tmpfs secrets.

**Tech stack:** Python standard library, fixed POSIX shell launchers, systemd, nftables, pinned Docker/Compose, Google Compute/IAP/OS Login/Secret Manager, PostgreSQL17, NATS and SeaweedFS.

**Spec:** `docs/superpowers/plans/2026-11-03-workshop-hosting.md` (v1 manifest/layout/secret/network/receipt contracts); `docs/operations/workshop-gcp.md`; `docs/agents/pre-implementation-gate.md`.

## Gate and scope status

Inspected source: `eddcf724028683dbb083191e4f8c42064b866bf0`, root branch `codex/production-release-orchestration`. Read-only staging-path review: `/tmp/autodata-workshop-staging-path-review.md`, dated 2026-11-04 UTC. That temporary review is supporting context, not a gate artifact.

Status: **synchronized planning checkpoint; implementation dispatch blocked pending independent exact-checkpoint review and fresh root dispatch**. Tracking references are [Issue186](https://github.com/lucronn/autodata/issues/186) and [Project8](https://github.com/users/lucronn/projects/8), read back at `2026-11-04T04:04:56.410962+00:00` after PG released the serialized slot. [M1 detail6622232881](https://github.com/lucronn/autodata/issues/186#issuecomment-6622232881) preserves the then-current complete PG CapAdd index/detail/pin and prior JS text verbatim with hashes. The dedicated lifecycle record/task and canonical notes now match the exact M1 goal, four-file scope and concrete todo below. The earlier draft was intentionally blocked at inspected base eddcf724; the new checkpoint must be committed/pushed and machine checked at its full SHA before review/dispatch. No implementation, credentials, resources or cloud operation occurs during this synchronization.

The coordinator must independently review the committed exact M1 checkpoint and verify full-SHA preflight before fresh dispatch. Each successor milestone separately requires synchronized goal/exact allowlist/concrete todo across Issue186/Project8 and canonical documentation, committed/pushed checkpoint, pinned full SHA and independent gate review. Historical hosting, catalog-only and publisher synchronization does not authorize these milestones. Changing an interface below requires a plan amendment before implementation.

## Global constraints and fixed decisions

- Environment is exactly `staging`; require an owner-selected HTTPS origin other than `https://cars.tk`. Retain the existing production-origin invariant and all production workflow blockers.
- Use dedicated staging VM, disk, database, Stripe test merchant/price/webhook and Firebase registration/authorized domain. No production DNS/Vercel changes, production secrets, production customer data or real card charging.
- Preserve v1 release schema and fixed paths: `/etc/autodata/host.json`; `/opt/autodata/releases/<SHA>`; `/opt/autodata/current`; `/opt/autodata/bin`; `/var/lib/autodata`; service-specific tmpfs `/run/autodata` directories. Retain Compose project/network literals `autodata-production*` on the isolated VM; names do not establish production authorization.
- Preserve exact service graph, image roles, commands, secret-name allowlists, static addresses, metadata/storage guards and exit/receipt contract in the hosting plan. Only Caddy publishes80/443. No VM build, source bind mount, ambient ADC, broad secret mount, mutable tag or runtime package download.
- Attached Firebase identity retains only `firebaseauth.users.get`; external deploy is the explicitly trusted host administrator. Host metadata access remains API-only plus trusted UID0 platform plumbing. No attached registry/Secret Manager/storage/monitoring role.
- Root lock is `/run/autodata/state/operation.lock`, opened no-follow in a verified root-only directory and held for every lifecycle/backup/restore transition. Lock ownership is not inferred from a PID file. Busy returns exit3/missing_dependency without mutation.
- Mutation state and redacted receipts are fsynced atomically on the verified data mount; a crash cannot turn partial work into a passed receipt. A reboot does not automatically resume writers: absent tmpfs secrets leaves maintenance and application startup blocked until explicit redelivery.
- Caddy maintenance is root-generated,503 with Retry-After/no-store, reloaded through the fixed private Unix socket. A failed maintenance reload stops the transition before any writer/stateful stop. Do not promise graceful in-flight Go request drain.
- No application SQL migration or app/browser/worker behavior change is allowed here. Preserve the catalog-only v2 collector's inability to certify schema until a separately reviewed real PG17 schema protocol is integrated.

## Mandatory inputs and dependency cut points

| Input/dependency | Required exact evidence | Blocks |
| --- | --- | --- |
| Owner resource decision | GCP host/Firebase/backup project IDs, billing owner, region/zone/residency, dedicated VPC/subnet/route review, fixed resource names, approved cost estimate and budget/alert recipient, immutable boot-image and package identities | Live bootstrap; fixture-backed local implementation may proceed after its own gate |
| Owner staging origin | Exact HTTPS hostname, DNS/TLS control authorization, Firebase app/auth domain/authorized domain, ACME contact; TLS plan for this hostname only | Any exposed service/startup acceptance |
| Owner integration decision | Separate Stripe test account/price/webhook and numeric secret versions; licensed connector/model endpoints, credentials and authorized request budget | Actual ingestion-http/reconciler/worker/API startup and product acceptance; passive probes cannot substitute fixtures |
| Publisher | Independently reviewed exact integrated source, successful authenticated candidate/finalize/independent raw readback verification, immutable manifest bytes/canonical hash, outer artifact/member hashes, run/attempt/artifact identity, image digests/platform IDs/provenance/SBOM, approved toolchain/config/numeric-secret references | Installation/pull of a real release; no ad hoc local build or tag fallback |
| PG17/schema | Native exact-image migration acceptance plus independently reviewed stable catalog-before-ledger protocol, actual effective HBA/ident/role proof and container identity checks | Schema success, services/runtime_evidence success and leaving maintenance |
| Minimum recovery | Dedicated staging synthetic-data policy, portable dump plus isolated restore proof, reboot/redelivery path, tested failure cleanup; retain named resources on failure | First creation of staging application data |
| Later production operations | Verified bounded snapshot lease/watchdog/export/restore, monitoring/heartbeat alerts and paid-product acceptance | Paid production only; this draft creates no production authority |

Publisher and schema milestones may finish independently of resource/helper development. The lifecycle implementation consumes their exact reviewed contracts only after coordinator integration/re-pin. It must not alter publisher adapters, artifact worker, toolkit lockfiles, release workflow or schema harness files to work around an unavailable dependency.

## First executable milestone: bare isolated staging resources

**Deliverable:** `cloud-bootstrap.sh plan|apply` creates and reads back only the approved dedicated regional IPv4 address, empty persistent disk and bare VM. No package installation, disk formatting, secret delivery, application process or IAM change occurs. Plan remains the default, non-mutating operation; production apply remains exit3.

**Exact implementation allowlist:**

- Modify `infra/deploy/gce/cloud-bootstrap.sh` (fixed launcher and delegation).
- Create `infra/deploy/gce/staging_bootstrap.py` (strict approval parser, fixed Google REST transport, resource request constructors, bounded operation polling/readback).
- Create `infra/deploy/gce/staging-bootstrap.schema.json` (strict approval contract below).
- Create `infra/deploy/gce/test_staging_bootstrap.py` (offline fake-transport/launcher tests).

No changes to `cloud-ops.py`, deployment/runtime helpers, Compose, workflows, IAM policies, application files or publisher/schema code are allowed. Existing offline renderer output is preserved. The first executable milestone is deliberately useful before publication: it establishes actual dedicated resource identities and a bare host, not a running application.

### Operator prerequisites and authority

Before live execution, the owner must select and approve host project/billing/region/zone/budget, exact staging origin, dedicated VPC/subnetwork and effective firewall policy, immutable Linux amd64 boot-image ID/selfLink, machine type, disk size/type, attached Firebase service account/scopes and a short-lived bootstrap identity. Relevant Compute/IAM/IAP APIs, exact service account/IAM bindings, registry and backup bucket must already exist under separately approved administration. This milestone may observe prerequisites but cannot create/change IAM, VPC/firewall, APIs, registry or bucket. It must not claim that an attached-SA name proves its effective Firebase-only permissions; actual IAM/denial review remains a required owner/live acceptance input.

The approved machine type is exactly `e2-standard-4`; data disk is exactly200GiB `pd-balanced`; boot disk is exactly20GiB `pd-balanced`. These remain proposed costs until the owner approves the exact resource set. No template project/hostname/token is a deployable input. Block apply when host config environment is not staging or origin is cars.tk. No metadata startup script, arbitrary instance metadata, SSH key, source checkout or cloud-init payload is permitted.

Use a short-lived Google OAuth token received as a bounded private descriptor3 from the operator launcher. Require descriptor to be an inherited read-only pipe, cap token16384bytes, reject empty/newline/NUL/multiple frames and never print/store it. Clear environment; fixed `/usr/bin/python3 -I`; no gcloud/developer ADC/HOME/config discovery. The operator retains responsibility for the external token's issuance and principal evidence. Token/scopes alone do not prove least privilege. Every live apply requires separately recorded owner authorization, not just possession of a token.

### Fixed approval/config input

Read root-owned regular mode0600 `/etc/autodata/host.json` through the existing bounded no-follow helper; validate exact existing v1 staging config. Read root-owned regular mode0600 `/etc/autodata/staging-bootstrap.json` by the same descriptor discipline, at most64KiB, strict UTF8 JSON, no duplicate/unknown keys, non-finite numbers, nulls or symlinks. Both parent directories are root-owned and non-writable to unprivileged users. Approval has exactly these fields:

```text
schema_version: integer1
operation: literal "create-staging-resources"
authorization_id: lowercase UUIDv4
expires_at: UTC RFC3339 seconds; must be future and no more than24hours away
service_config_sha256: canonical host.json SHA256
resource_nonce: lowercase UUIDv4 (stable for this resource set)
boot_image: {self_link: exact https://www.googleapis.com/compute/v1/projects/<project>/global/images/<name>, id: positive decimal string,
             architecture: literal "X86_64"}
network: {network_self_link: exact host-project global network selfLink,
          subnetwork_self_link: exact host-project/region subnet selfLink,
          reviewed_firewall_evidence_sha256: lowercase64hex,
          reviewed_routes_evidence_sha256: lowercase64hex}
attached_identity: {email: exact "autodata-api-firebase@<host-project>.iam.gserviceaccount.com",
                   reviewed_iam_evidence_sha256: lowercase64hex}
bootstrap_identity_evidence_sha256: lowercase64hex
owner_cost_and_region_evidence_sha256: lowercase64hex
```

Evidence hashes bind independently retained owner-reviewed records; the parser does not mistake their presence for live IAM/firewall verification. Production IDs/origin require rejection by the coordinator-reviewed owner input, not fuzzy names. All resource names/project/region/zone/disk UUID come only from existing host.json, not additional CLI paths/arguments. `resource_nonce` is a stable ownership label `autodata-stage=<UUID>` on address/disk/instance; also label `autodata-config=<first32hex-config-hash>`. Approval expiry blocks new mutations, including after a long operation. Configured filesystem UUID is expected future formatting identity, not a filesystem fact at this milestone.

### Exact Google API request inventory

Use only HTTPS `compute.googleapis.com/compute/v1/`, no redirects or caller-selected hosts; approved image may belong to another explicitly owner-selected project. Fixed REST paths and JSON bodies are constructed as objects, never shell commands. URLs must be normalized from exact selfLinks and validated identifiers before request. Allowed GETs:

- `/projects/P` to inspect inherited common instance metadata; selected image selfLink; selected machine type `/projects/P/zones/Z/machineTypes/e2-standard-4`;
- selected network/subnetwork selfLinks, subnet route range and project routes/firewalls lists with strict page/response bounds;
- `/projects/P/regions/R/addresses/ADDRESS`, `/projects/P/zones/Z/disks/DISK`, `/projects/P/zones/Z/instances/VM`;
- `/projects/P/global/networks/NETWORK/getEffectiveFirewalls`;
- `/projects/P/regions/R/firewallPolicies/getEffectiveFirewalls?network=<URL-encoded-exact-network-selfLink>`;
- `/projects/P/zones/Z/instances/VM/getEffectiveFirewalls?networkInterface=nic0` after creation;
- `/projects/P/zones/Z/disks/BOOT_DISK` before/after creation (unexpected existing derived boot disk blocks instance creation);
- matching regional/zonal operation selfLinks returned by this run only.

The exact conservative prerequisite acceptance matrix is:

- Selected image must be READY, exact approved positive numeric ID/selfLink/X86_64 architecture, not deprecated/deleted/obsolete. Project commonInstanceMetadata items must be absent/empty or contain only `enable-oslogin=TRUE`; any other inherited metadata, including startup scripts/URLs/SSH keys, fails closed. Repeat metadata/image checks immediately before instance POST; a pinned image is owner-reviewed for bare-host contents, not assumed safe from its name.
- Custom VPC only (`autoCreateSubnetworks=false`), exactly the selected subnet in `network.subnetworks`, no peerings, no network firewall policy attachment, no ULA/external IPv6. Selected subnet must belong to that network/region, be IPv4-only with no secondary ranges/overlap flag and a valid RFC1918 CIDR disjoint from172.30.10.0/24,172.30.20.0/24,172.30.30.0/24.
- Require network and regional effective-firewall endpoints available and both `firewallPolicys` collections empty. Any inherited/global/regional policy fails closed rather than attempting policy interpretation. After create require the VM effective-firewall policy collection empty too. A missing/forbidden/malformed observation is not an empty list.
- Exactly two explicit enabled ingress ALLOW rules affect the selected tag (tag is exactly instance name): one TCP80/443 from0.0.0.0/0; one TCP22 from35.235.240.0/20. Each has only that target tag, no service-account/source-tag/IPv6/other protocols/ranges/ports. No additional explicit firewall rule, including egress rule, is accepted in this dedicated VPC; implied deny-ingress/allow-egress remain the GCE defaults. Match the exact same normalized rules on post-create effective VM readback. Unrecognized rule semantics fail closed.
- Routes on this VPC may only be the selected subnet route and the exact approved default route with destination `0.0.0.0/0` and next hop `global/gateways/default-internet-gateway`. Only that exact default-destination/default-internet-gateway pair is exempt from the Docker-range overlap check; a default destination with any other next hop is rejected. Require the selected subnet destination and every additional observed destination to be disjoint from all three Docker ranges; additional destinations remain rejected even when disjoint. Reject custom/peering/VPN/router/instance/ILB next hops. Filter unrelated project routes by exact network before validation; cap the whole list before filtering.
- Network readbacks and owner-reviewed evidence are both required: a hash does not prove IAM or firewall enforcement. Re-run the fixed readbacks immediately before instance POST and after creation. Any drift after creation yields failure with resources retained and no host-start authority. Actual packets/IAP/metadata denials are a later separately authorized host acceptance gate.

The public Google Compute v1 discovery document was read without credentials during planning on2026-11-04; it confirms the network/regional/instance effective-firewall methods, regional Address labels and create fields used here. That public schema lookup is not a cloud resource or IAM observation.

Only three POST mutations exist:

1. `/projects/P/regions/R/addresses`: `{name:ADDRESS,addressType:"EXTERNAL",ipVersion:"IPV4",networkTier:"PREMIUM",labels:LABELS}`.
2. `/projects/P/zones/Z/disks`: `{name:DISK,sizeGb:"200",type:PD_BALANCED_SELF_LINK,labels:LABELS}`; no source snapshot/image, encryption key override or format action.
3. `/projects/P/zones/Z/instances`: exact name/labels; machineType selfLink; one persistent boot disk named `<instance>-boot` initialized from pinned image selfLink,20GiB pd-balanced with autoDelete:false and the same ownership labels; require instance name length<=58 to keep this derived name within63; one nonboot persistent data disk referencing the exact newly created/read-back disk ID/selfLink,modeREAD_WRITE,autoDelete:false,deviceName`autodata-data`; one selected network/subnetwork interface with exactly one IPv4 ONE_TO_ONE_NAT using the reserved address, PREMIUM tier; exact attached service account with cloud-platform,userinfo.email,identitytoolkit scopes; metadata only `enable-oslogin=TRUE`, `block-project-ssh-keys=TRUE`, `serial-port-enable=FALSE`; `canIpForward:false`; one unique tag exactly equal to instance name; deletionProtection:true; no external IPv6, startup script, project SSH key, forwarding or default service account.

Each POST uses requestId=`uuid.uuid5(uuid.UUID(resource_nonce), authorization_id + ":" + resource_type)` where resource_type is exactly address,disk orinstance; retain it in the receipt. POST retry after transport loss first polls/reads the exact owned target, never blindly issues a different requestId. GET404 is the sole create permission; matching existing resources require stable resource ID, exact ownership labels and all reviewed mutable/security/identity fields. Unowned/mismatching resources fail without patch/delete/adoption. Compare actual image ID and architecture before instance creation; after VM creation bind observed boot-disk source image ID and data-disk ID, attached account/scopes, network/IP, metadata/tags, machine type and deletion protection. Instance create is blocked if the disk is attached elsewhere or not newly owned/empty by creation provenance; it cannot claim a filesystem is empty by checking only metadata.

### Deadlines, receipts, cleanup and tests

Whole operation deadline30minutes with monotonic clock; each request at most30seconds, each JSON response at most1MiB, at most10list pages/1000items and no arbitrary nextPage URL. Poll only returned same-project matching-region/zone operation names with bounded backoff; enforce overall deadline and revalidate approval before every mutation. A cancelled/failed/expired operation stops new mutation and retains owned resources for inspection; it never deletes a VM/disk/address or revokes IAM automatically.

The one stdout JSON receipt is at most64KiB, common existing fields plus `definition_only:false`, `deployment_authorized:false`, `authorization_id`, config SHA256, resource nonce, fixed resource IDs/selfLinks, operation names, completed readback booleans and `cleanup:"resources-retained"`. No token, raw API response or arbitrary exception string is retained. Success means only exact resource readbacks passed; `schema/services/runtime_evidence` remain false. Partial progress produces failed/timed_out receipt, never success. Preserve exit0/2/3/4/5/6 meanings. Persist redacted receipts atomically with file/directory fsync under fixed operator-host `/var/lib/autodata-bootstrap/receipts/<authorization_id>.json` (root-owned directory0700/file0600, no-follow), not the unmounted VM data disk. This operator path is never accepted from argv; creation is bounded to these verified root-owned parents.

- [ ] Synchronize the exact approval JSON shape, instance/disk/address requests, network acceptance matrix, receipt contract and four-file scope above in the docs-only first-milestone checkpoint; no technical decision is deferred to an implementation agent.
- [ ] Write red tests `test_apply_production_denied`, `test_no_approval_no_token_no_requests`, `test_unknown_duplicate_or_expired_approval_denied`, `test_redirect_and_ambient_adc_denied`, `test_pin_route_policy_or_owner_drift_denied`, `test_approved_default_and_disjoint_subnet_pass`, `test_overlapping_selected_subnet_denied`, `test_default_route_custom_next_hop_denied`, `test_additional_destination_denied_even_when_disjoint`, `test_request_inventory_exact`, `test_idempotent_matching_rerun`, `test_unowned_existing_resource_not_adopted`, `test_post_transport_loss_same_request_id`, `test_timeout_retains_resources`, `test_output_bounds_and_token_redaction`, `test_bare_vm_has_no_startup_script_or_format_action` and `test_passed_receipt_has_no_runtime_authority`.
- [ ] Make route cases explicit: accept only the approved `0.0.0.0/0` default-internet-gateway route plus selected subnet `10.50.0.0/24`; reject a selected subnet `172.30.10.0/24` or a broader subnet `172.30.0.0/16`; reject `0.0.0.0/0` through a custom instance/VPN/ILB next hop; reject an extra `10.60.0.0/24` route even though it is disjoint. These are planned offline fixtures, not executed cloud tests.
- [ ] Implement only the four allowlisted files, retaining existing offline renderer tests and all production blockers; run `python3 -m unittest discover -s infra/deploy/gce -p 'test_staging_bootstrap.py' -v` and existing `test_cloud_ops.py`/`test_host_runtime.py` suites, syntax and diff/scope checks.
- [ ] Commit/push one coherent candidate and obtain independent exact-SHA review. All fake transports must be intercepted; unit tests perform no cloud, provider, credentials or runtime actions.
- [ ] After distinct owner live authorization, run plan then apply/readback on the selected isolated resource set; record actual created IDs, effective-policy/IAM evidence, denial tests and retained-resource cleanup decision. Readiness remains unavailable.

## Successor milestones: explicit future gates

These are dependency/cost decisions, not implementation allowlists or permission to dispatch. Each needs its own decision-complete plan, synchronized record, pinned passing preflight and independent review.

1. **Host installation/private delivery:** prove disk resource/device/UUID before authorized format and mount; install pinned packages/root helpers/early nft guard/systemd units; consume authenticated publisher bytes and exact cached image IDs; privately deliver manifest-bound numeric secret versions and transient registry auth into per-service tmpfs. No secret in Docker Config.Env, argv, persistent config or receipts. Reboot stays fail closed until external redelivery. Likely files are new `host_lifecycle.py`, `deliver-host.py`, their tests and `autodata.service`, plus existing deploy/systemd launchers; exact allowlist must be reviewed later. Publisher completion blocks real release install, not bare resource creation.
2. **Startup/schema/readiness:** integrate separately accepted native PG17 image/migration and stable catalog-before-ledger protocol, effective HBA/ident/least-rights provisioning, ordered PG/NATS/S3/migrations/grants/private HTTP/worker/reconciler/API startup and maintenance transitions. Preserve only-TCP nature of current API `/readyz`; require authenticated PG SELECT1, NATS health and S3 HEAD of a pre-provisioned synthetic sentinel. No-work probes never create buckets, jobs, articles, payments or provider requests. Ordinary worker concurrency is not a causal no-work proof; prove aggregate stability in a quiesced synthetic acceptance window. Missing schema leaves schema/services/runtime_evidence false. Startup's Stripe/identity/provider calls require owner-approved integration credentials/budgets.
3. **Minimum recovery before data:** under the shared lock, implement fixed UUID lease/dump/resume/watchdog and isolated restore helpers;1800second lease with300second recovery reserve. Prove interrupted backup/failed resume do not certify backup; reject live disk restore; preserve maintenance and writer/provider egress denial on replacement host. PG dump alone cannot recover S3/JetStream: actually drill a separately owner-authorized quiesced disk snapshot/copy and portable PG restore with synthetic ownership/session/order/grant/article/object records before first staging application data. Retain original disk on failures. Teardown is separate owner-approved exact-ID work.
4. **Production operations:** authenticated WIF deploy/backup/monitor adapters, snapshot/immutable bucket export and verified alert/heartbeat execution remain later gates. Minimum staging recovery is not production backup acceptance; publishing is not host startup; host readiness is not paid-product/browser acceptance. Never lift cars.tk or production workflow blockers through a staging milestone.

## Concrete todo for coordinator synchronization

- [ ] Review and approve the bare-resource milestone's strict approval/request/receipt/network acceptance contract, exact four-file allowlist, denied operations and offline/live evidence boundary; freeze owner input requirements without inventing cloud values.
- [ ] After coordinator approval and release of the active tracking slot, synchronize the selected milestone goal/references/todo in Issue186/Project8, this plan, `docs/operations/workshop-gcp.md`, `docs/architecture/infrastructure-and-dev.md`, dedicated lifecycle task/record and coordinator queue; commit/push a docs-only checkpoint, pin it and pass machine preflight before builder dispatch.
- [ ] Implement/review the bare-resource milestone only, then write/review a separate host-installation checkpoint using integrated publisher contracts and chosen staging inputs; successor descriptions are not dispatchable allowlists.
- [ ] Integrate accepted publisher and PG17/schema dependencies and independently gate/review host installation, lifecycle/readiness and recovery at exact SHAs; preserve production blockers and record every test's actual environment.
- [ ] Obtain separate owner authorization for the concrete staging resource/config/operation set after reviewable scripts/manifests exist; prove readiness, reboot/recovery and product acceptance before any production decision.

## Verification and handoff record

Planning validation is text/scope review, live tracking readback and exact committed full-SHA preflight, not execution of the future tests above. The earlier draft gate intentionally failed at eddcf724; that historical failure is not the new checkpoint result. The canonical machine record must eventually contain goal, this plan_ref, Issue186/Project8 URLs, repository_doc_refs, the selected milestone's concrete todo, `status:synchronized` and UTC updated_at. Live tracking readback and canonical updates now exist; independent exact-checkpoint review and root dispatch remain pending.

Publisher approval is neither host readiness nor permission to provision. Host readiness is neither paid-product acceptance nor production authorization. Minimum staging restore evidence does not replace production backup/snapshot/export/monitoring acceptance. No cloud, credential, deployment, DNS or runtime-readiness action is performed by this planning checkpoint.


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
