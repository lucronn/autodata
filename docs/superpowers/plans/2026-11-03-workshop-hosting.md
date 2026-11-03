# Workshop at cars.tk: bounded GCE hosting implementation proposal

Offline implementation gate preparation, 2026-11-03. This successor consolidates the reviewed application interfaces, Firebase ADC isolation design and local pinned-image findings. It supersedes the prior hosting proposal (SHA256 `1cf908ab0e2b1eb678710d37809a7838051a8e4375d9d7e25a69de0cfd5c9a2f` in Git history), including its broad attached-identity/Secret Manager assumption and Ops Agent monitoring. Inputs: ADC isolation design SHA256 `91dd17b493d4c71e0632ac64b36136fec433a4d3d09529820ca4fefc009bcb32`, bounded amendment SHA256 `5d040259ab579bf6801a1839a0bbfa5eddfa4cd0d08790b856e36e81334c9d37`, and reviewed commerce040 plus paid candidate `a90613a76b3f2c5f5c14606384bf1d9cdcca0a6e`. The latter's full runtime acceptance and UI integration remain coordinator-owned. This offline definitions gate pins source integration3b551c992263f74e3ebdc6e4fa2c4ffda3b979a6; re-pin the final verified integrated release before real staging or deployment.

The synchronized record for this offline implementation scope is `docs/agents/records/2026-11-03-workshop-hosting.json`. The coordinator must review the committed checkpoint and passing machine preflight before dispatch; synchronization does not authorize deployment. No cloud resource, billing, real credential, provider API or DNS change is authorized by it. Local read-only image inspection and explicitly authorized synthetic S3 probes are the only new runtime observations. Actual project, cost, region, licensed providers and cutover decisions remain owner inputs.

## Decisions that supersede the old hosting draft

Keep one GCE VM, a separate persistent data disk, standalone production Compose and Caddy, same-origin `https://cars.tk`. Keep the proposed initial e2-standard-4/200GiB balanced data disk, nightly maintenance, proposed RPO24h/RTO4h, pending actual owner cost/region/recovery decisions and restore evidence. Keep Vercel until an explicitly approved cutover. Do not introduce Kubernetes, another identity broker or another hosting platform.

Attach only `autodata-api-firebase@<HOST_PROJECT_ID>.iam.gserviceaccount.com`, with custom permission `firebaseauth.users.get` on `<FIREBASE_PROJECT_ID>`. No Secret Manager, registry, storage, snapshots, Monitoring, Logging, impersonation or IAM administration on this identity. Preserve the ADC design's explicit Compute access-scope ceiling and require a real SDK refresh/GetUser/revocation staging proof. The actual Go initializer uses cloud-platform and identitytoolkit scopes; configure the VM access-scope ceiling explicitly as cloud-platform, userinfo.email and identitytoolkit, and verify actual SDK refresh/GetUser in staging. IAM remains the one-permission boundary. `firebaseauth.users.get` permits account-read/list operations and is not IAM-restrictable to the requested UID; no user mutation or token signing permission is granted. The API has no credential-file mount, no developer ADC/home mount, no GOOGLE_APPLICATION_CREDENTIALS, and no emulator. Metadata access is exclusive to the API's designated network address; workers never get Google ADC.

External GitHub OIDC/WIF principals perform publishing, deployment/secret delivery, backups and monitoring separately. Restrict each trust binding to numeric repository/owner identity, exact approved workflow/ref and protected environment. No service-account JSON key; no external cloud bearer token is persisted on the VM or mounted into containers. The deploy identity is a trusted host administrator; backup and monitor identities are not.

Replace the old attached-SA Ops Agent proposal. Do not install an Ops Agent that obtains VM ADC. Use native Compute metrics and an external HTTPS uptime check, plus a protected scheduled external WIF monitoring job. That job reads only aggregate measurements through one fixed non-admin IAP/OS Login helper and writes Cloud Monitoring metrics with its own metricWriter identity. It has no secret, backup, deploy, registry or arbitrary sudo authority. Cloud Monitoring alert policies/notification channels are bootstrap-owned, not API-owned. Container logs stay bounded and rotated locally; the monitor receives no arbitrary logs or request payloads. This is coarse five-minute scheduled telemetry with scheduler jitter, plus native uptime/Compute signals, not a promised one-minute worker SLO. Missing monitor heartbeat is itself an alert. If the owner requires finer continuous telemetry, amend this scope explicitly before implementation; do not widen VM IAM silently.

## Thirty implementation paths and two disjoint owners

This is the exact thirty-path offline implementation scope. Execution is staged by the milestone restrictions below; only a coordinator-reviewed checkpoint and pinned preflight authorize dispatch. Coordinator separately owns the canonical plan/task/record/Issue186/Project8 synchronization. Existing application SQL001–040, paid/auth/commerce code, base/CI/Base44 Compose, UI and existing CI workflows are excluded.

Runtime builder A owns these22 paths:

1. `infra/compose/compose.production.yaml` — standalone complete service graph; never merge base/CI Compose.
2. `infra/deploy/gce/Caddyfile` — TLS, same-origin proxy, safe access logging, fixed maintenance include, root-only Unix admin socket.
3. `infra/deploy/gce/nats.conf.template` — private JetStream and explicit users/permissions.
4. `infra/deploy/gce/seaweedfs-s3.json.template` — explicit S3 identities/actions, no committed keys.
5. `infra/deploy/gce/release.env.example` — nonsecret required variables only.
6. `infra/deploy/gce/release.schema.json` — image/source/migration/config-reference manifest validation.
7. `infra/deploy/gce/migration.Dockerfile` — released runner+SQL tree and pinned PG17 client.
8. `infra/deploy/gce/runtime-entrypoint.sh` — fixed per-service secret-name allowlist, file-to-process-env loading, then exec.
9. `infra/deploy/gce/deploy.sh` — fixed root operations install/check/start/stop/maintenance/resume, release switch and rollback.
10. `infra/deploy/gce/backup-host.sh` — fixed begin/status/export/resume operations, UUID lease, no cloud credential.
11. `infra/deploy/gce/restore.sh` — explicit isolated restore/validate only, refuses live data directory.
12. `infra/deploy/gce/runtime-check.py` — passive aggregate health/rights/config checks; structured redacted receipt.
13. `infra/deploy/gce/metadata-guard.nft` — own early forwarding table only; never flush Docker's tables.
14. `infra/deploy/gce/autodata-metadata-guard.service` — load/verify guard before Docker.
15. `infra/deploy/gce/autodata.service` — mount/guard/secrets/digest dependency checks; selected release service control.
16. `infra/deploy/gce/autodata-backup-resume.service` — fixed expired-maintenance recovery.
17. `infra/deploy/gce/autodata-backup-resume.timer` — local lease watchdog, no Google identity.
18. `infra/deploy/gce/docker-autodata.conf` — Docker systemd dependency on data mount and metadata guard.
19. `infra/deploy/gce/runtime-grants.sql` — idempotent infrastructure role grants/aggregate monitoring views; not an application migration.
20. `infra/deploy/gce/test_host_runtime.py` — pure/script/render negative tests and explicitly opted-in disposable runtime tests.
21. `apps/api-go/Dockerfile` — COPY the small shared secret-entrypoint wrapper; retain actual API binary command.
22. `workers/ingestion-python/Dockerfile` — COPY same wrapper; retain actual installed dependencies/source/commands.

External-operations builder B owns these8 paths:

23. `.github/workflows/release-workshop.yml` — tested immutable build/publish and protected explicit deploy dispatch.
24. `.github/workflows/backup-workshop.yml` — separate WIF backup principal and bounded nightly/manual run.
25. `.github/workflows/monitor-workshop.yml` — separate WIF metric writer; fixed read-only helper and missing-heartbeat signal.
26. `infra/deploy/gce/cloud-bootstrap.sh` — explicit reviewed APIs/IAM/firewall/disk/IP/bucket setup; plan/render by default, apply only with operator authorization.
27. `infra/deploy/gce/cloud-ops.py` — fixed external publish/deploy/backup/monitor/restore operations, finite subprocess bounds and safe receipts.
28. `infra/deploy/gce/test_cloud_ops.py` — fake CLI/stream tests; no implicit cloud/provider calls.
29. `docs/operations/workshop-gcp.md` — exact bootstrap/rollout/reboot/rotation/recovery/cutover runbook and evidence locations.
30. `docs/architecture/infrastructure-and-dev.md` — chosen topology, actual limitations and later verified evidence.

A implements the release schema, fixed helper subcommands/exit codes and service/network names specified below in its first reviewed milestone; any schema-field refinement must be reviewed before B consumes it. B can implement against that literal contract without Docker/cloud access; merge only coordinator-approved dependencies. Builders do not self-approve one another's IAM/runtime work. Both remain Sol6.1 medium Fast/priority. A third independent reviewer evaluates combined rendered config and failure injection before staging authorization.

## Exact runtime graph and entrypoints

Production Compose is standalone. It includes only caddy, api, ingestion-http, article-worker, payment-reconciler, postgres, nats, minio, plus explicitly invoked one-shot migration/bootstrap/metrics-probe services. No legacy ingestion consumer, enrichment, outbox relay, demo, fixture, smoke or build service is enabled initially. The purchased catalog uses durable PG article/index jobs; generic customer dataset/work bypass routes are denied. If later enabling legacy lanes/outbox/enrichment, prove their consumers and NATS permissions in a separate scope.

Use these existing application commands, after the file-to-env wrapper:

- API: `/usr/local/bin/autodata-api`.
- Private HTTP: `python -m autodata_ingestion.http_service`.
- Article worker: `python -c 'from autodata_ingestion.worker import article_worker_main; raise SystemExit(article_worker_main())'`.
- Reconciler: `python /app/scripts/reconcile_payments.py --poll-seconds 15 --batch-size 50`.
- Migration: `sh /release/scripts/dev/migrate_sql.sh --migrations-dir /release/db/migrations` with PGHOST/PGPORT/PGDATABASE/PGUSER from nonsecret config and PGPASSWORD loaded from its temporary secret file. Keep runner and SQL tree packaged from the same release; manifest currently001–040, discovered and hashed rather than permanently hardcoded.
- Passive metrics: `python /app/scripts/operational_metrics.py --address postgres:5432` with its dedicated read-only DB credential. Add fixed host/queue/lease/backup and commerce aggregate queries in runtime-check.py where the existing renderer does not cover them; never call worker.run_once, ensure, bank/model, checkout or reconciliation from a health probe.

Freeze commands/interfaces for the future scripts:

```text
cloud-ops.py publish --release <40hex> --config <nonsecret-json>
cloud-ops.py deploy --release-manifest <json> --config <nonsecret-json>
cloud-ops.py backup --config <nonsecret-json> --run-id <uuid>
cloud-ops.py monitor --config <nonsecret-json>
cloud-ops.py restore --config <isolated-restore-json> --backup-receipt <json>
deploy.sh install|check|start|stop|maintenance|resume <40hex>
backup-host.sh begin|status|export|resume <uuid>
restore.sh restore|validate <uuid>
runtime-check.py check|metrics --release <40hex>
```

Shared helper exit codes are frozen:0 success,2 invalid input/configuration,3 missing dependency/guard/mount/secrets,4 operation failure,5 timeout,6 incomplete recovery/backup. Receipts distinguish failure from timeout and never certify partial work. External publish is bounded45 minutes; deploy30 minutes; each monitor run60 seconds; backup maintenance30 minutes including safe-resume reserve; isolated restore validation4 hours including cleanup reserve, subject to the accepted measured RTO. Subcommands receive only the fixed manifest/config/run IDs above; commands do not accept caller-supplied shell fragments.

No arbitrary command/path argument is accepted by backup/monitor sudo rules. Host helper paths and release directories are root-owned; unprivileged logins cannot change symlinks, configs, wrappers, current release or Docker membership. Deploy/helper unit tests must reject unknown subcommands, malformed UUID/SHA, traversal, substituted environment, missing/extra manifest fields and unexpected disk/network/service identities. No eval, shell sourcing of delivered secret content, shell command interpolation of secret values, HOME rewrite or implicit current-directory config lookup.

## Required nonsecret configuration

Root config JSON/release.env contains: HOST_PROJECT_ID, FIREBASE_PROJECT_ID, BACKUP_PROJECT_ID, REGION, ZONE, INSTANCE_NAME, DATA_DISK_NAME, DATA_DISK_FILESYSTEM_UUID, STATIC_IP_NAME, ARTIFACT_REPOSITORY, BACKUP_BUCKET, DEPLOY_ENVIRONMENT, PUBLIC_ORIGIN, RELEASE_SHA, ACME_EMAIL and pinned numeric secret-version references per service. Retain `<...>` project/owner inputs in this planning document; deterministic implementation rejects unresolved placeholders at apply/start. The owner still must choose project/billing/region, cost budget, recovery window, notification destination, Firebase registration and authorized staging hostname.

Release manifest requires exact source SHA; every selected image as `registry/repository/name@sha256:<64hex>`; platform; image IDs/SBOM/provenance references; exact SQL filename inventory/combined hash and runner hash; tested Docker Engine/Compose package versions and package hashes; nonsecret service config hash; secret resource+numeric version references without values; and last compatible rollback manifest. Resolve/package-pin versions during implementation and record them; no tag-only runtime images or floating apt/tool downloads at host startup. CI action revisions are full reviewed commit IDs. Initial third-party images include reviewed PG17+pgvector, NATS2.10, Caddy and the existing exact SeaweedFS digest. No production image build on the VM or source bind mount.

Actual app variables, not invented *_FILE support:

- API: AUTODATA_ENV=production; AUTODATA_AUTH_MODE=firebase; AUTODATA_PUBLIC_ORIGIN=https://cars.tk; AUTODATA_FIREBASE_PROJECT_ID, AUTODATA_FIREBASE_WEB_API_KEY, AUTODATA_FIREBASE_WEB_APP_ID, AUTODATA_FIREBASE_AUTH_DOMAIN; AUTODATA_PROJECTION_STORE=postgres; AUTODATA_API_ADDR=:8080; AUTODATA_DB_ADDRESS=postgres:5432; AUTODATA_POSTGRES_DB/USER/PASSWORD; AUTODATA_NATS_ADDRESS=nats:4222; AUTODATA_S3_ADDRESS and AUTODATA_S3_ENDPOINT=minio:9000; AUTODATA_S3_ACCESS_KEY/SECRET_KEY; AUTODATA_SOURCE_BUCKET=autodata-sources; AUTODATA_INGESTION_URL=http://ingestion-http:8081; AUTODATA_INGESTION_INTERNAL_TOKEN; explicit strong AUTODATA_IMAGE_URL_KEY; AUTODATA_COMMERCE_MODE=stripe_live only after live-payment approval (stripe_test only in separate staging DB).
- Ingestion HTTP: AUTODATA_ENV/PUBLIC_ORIGIN/COMMERCE_MODE; AUTODATA_INGESTION_HTTP_ADDR=:8081; DB and S3 writer variables; same internal token; AUTODATA_STRIPE_ACCOUNT_ID/PRICE_ID/SECRET_KEY/WEBHOOK_SECRET; approved BANKONE_BASE_URL/BANKTWO_BASE_URL and BANKONE_API_TOKEN/BANKTWO_API_TOKEN for actual bounded public-selector hydration. The HTTP catalog service itself fetches selector scopes, so these credentials cannot be assigned only to the article worker. No model key is required for this HTTP selector/commerce lane. Preserve exact configured price/merchant startup verification; do not bypass it for readiness.
- Reconciler: DB writer variables; ENV/PUBLIC_ORIGIN/COMMERCE_MODE; Stripe ACCOUNT_ID/PRICE_ID/SECRET_KEY/WEBHOOK_SECRET and internal token because actual configured_commerce requires all of them. The current code cannot omit its webhook secret. No bank/model credentials are required for preparation scheduling itself.
- Article worker: DB writer/S3 writer variables, explicit authorized BANKONE_BASE_URL/BANKTWO_BASE_URL and BANKONE_API_TOKEN/BANKTWO_API_TOKEN, INCEPTION_API_KEY/BASE_URL/MODEL/TIMEOUT_SECONDS as approved production configuration. No Stripe, Firebase, Google cloud or host credentials. Do not inherit example provider defaults. Both HTTP and worker explicitly set only the one supported bank credential name per provider; reject conflicting AUTODATA_BANKONE_API_KEY/AUTODATA_BANKTWO_API_KEY ambient aliases rather than relying on their precedence.
- Metrics: separate DB role read-only on only the fixed operational query tables/aggregate views. No API DB secret, S3 write key, Stripe, bank/model, internal token or ADC. Runtime-check emits numbers/allowlisted states only, never query rows or raw exception strings.

AUTODATA_READINESS_MODE=static, local auth, emulator settings, fixture flags, ambient Google credential file variables and cloud/payment environment inherited from an operator shell are forbidden. Staging ENV=staging requires its own approved HTTPS origin; configured return paths remain `<origin>/workshop/?order=<stored UUID>`. Browser prices, client return URLs and query payment-success flags never grant ownership. Paid access is unconditional in Firebase mode, requires PG/session/commerce/media dependencies, and has no deployment flag that turns it off.

## Secret delivery without Docker metadata persistence

Important correction: Compose env_file/environment stores resolved secret values in persistent Docker Config.Env, even when the original file is tmpfs. Therefore do not deliver secret values as Compose environment entries. The two application image changes above add the same tiny entrypoint that reads an allowlisted service's individual read-only `/run/autodata/<service>/<NAME>` files immediately before exec and exports only that process environment. Delivered values must match the documented single-line/no-NUL form; reject malformed files, symlinks, unknown names, wrong UID/mode, missing or empty required values. Do not source/eval file contents. Test that `docker inspect`/container configuration and disk release/config files contain no secret values. Host root and same-container process authority remain trusted; process env is not a defense against those administrators.

Use image-supported POSTGRES_PASSWORD_FILE for the DB bootstrap password and direct root-private files for NATS/S3 configuration. Root delivers files into tmpfs; service-specific ownership/modes permit only the intended runtime UID/GID. Mount only that service's directory read-only. No broad /run/autodata, host home, Docker config/socket, kubeconfig or gcloud credential mount. Numeric secret versions are fetched by the external deploy principal, streamed over IAP stdin without tracing, and atomically installed root-owned on tmpfs. No secret values in argv/stdout/receipts. Registry pull authentication uses separate tmpfs Docker config and is removed after exact-digest pulls.

API receives only DB, read-only S3, internal token and media key secrets. Private HTTP receives its necessary DB/S3/internal/Stripe and selector-connector bundle, without a model key. Article worker receives only DB/S3/bank/model. Reconciler receives its actual required DB/internal/Stripe bundle. Migrator/admin/S3-bootstrap secrets are mounted only into explicit temporary bootstrap jobs and removed after success. Regular app DB roles get required DML but no superuser, role administration, DDL ownership, filesystem/program execution or migration credential; the separate released migrator owns DDL. runtime-grants.sql verifies this on every new schema head.

## Static network and metadata policy

Only Caddy publishes80/443. SSH22 is IAP-source-only with OS Login; no public DB/S3/NATS/API/metrics ports. No host networking, privileged containers, Docker socket, NET_ADMIN/NET_RAW or host PID namespace. Drop capabilities, set no-new-privileges, read-only roots and only required tmpfs/data mounts. Pin/test container UID, writable directories and image capability needs rather than breaking stateful entrypoints by assertion.

Use explicit bridge/IPAM names and addresses in the standalone Compose:

- edge: bridge br-ad-edge,172.30.10.0/24; api172.30.10.10, caddy172.30.10.20; API default gateway is this network.
- backend: br-ad-back,172.30.20.0/24,internal:true; app and stateful service traffic only; minio has fixed address172.30.20.40.
- workers-egress: br-ad-work,172.30.30.0/24; private HTTP/reconciler/article worker outbound approved HTTPS; no metadata exception.

Reserve these ranges only after bootstrap rejects overlap with host/VPC/Docker routes. API may also join backend with another fixed address but only its edge address may reach metadata. Disable container IPv6 for this launch. Verify the chosen pinned Compose supports explicit gateway priority; do not rely on network-name ordering.

Before Docker starts, own nftables FORWARD hook at an explicitly tested priority earlier than Docker forwarding accepts. Allow only packets from172.30.10.10 on br-ad-edge to169.254.169.254 TCP80; drop every other forwarded destination169.254.169.254 on every port, plus fd20:ce::254 IPv6. Destination-address matching covers metadata.google.internal. Also restrict host OUTPUT to169.254.169.254 and fd20:ce::254: permit TCP80 only for trusted UID0 platform/root processes, then deny every other host UID/port/protocol. The GCE guest agent and OS Login platform plumbing may require metadata; test those actual functions rather than promising that all host metadata can be disabled. Ordinary non-admin OS Login shells used by backup/monitor principals are denied; their fixed helper access must not confer Firebase account-read credentials. The designated API exception is forwarded traffic only and must not exempt unprivileged host OUTPUT. Match source and ingress interface, not a source address alone. Do not flush Docker/VPC rules. Test real namespace requests and spoof prevention with dropped capabilities after Docker restart and VM reboot. Require actual non-admin host IPv4/IPv6/metadata-hostname denial, all other-container metadata denial, and successful API ADC refresh/GetUser through its designated forwarding exception, and functioning guest-agent/OS Login operations with the explicit trusted UID0 exception. Local root/Docker administrators remain trusted and can administer the guard; API-only ADC is a boundary for untrusted workloads and host users, not a claim that trusted root cannot obtain the attached identity.

The same `metadata-guard.nft` artifact must also enforce a separate storage boundary: from application namespaces, permit only TCP9000 to172.30.20.40; deny every other destination port/protocol to that storage address, including same-bridge traffic. Use an nftables bridge-family forward hook for bridged packets and the early inet FORWARD guard for routed packets; do not assume an inet hook alone sees same-bridge traffic or rely only on unpublished ports. Disable IPv6 and reject unexpected storage addresses/networks. Internal mini component traffic remains within its own namespace. Actual network-namespace tests must prove API/worker/HTTP cannot access filer8888/18888, master9333/19333, volume8080/18080, admin23646/33646 or other storage ports while authenticated S3 works. A missing storage boundary blocks protected application startup. These are deterministic host rules within the existing30 paths, not a new proxy/service or a claim that the S3 config authenticates every mini listener.

Docker's systemd drop-in Requires/After the data mount and early guard. autodata.service requires actual expected filesystem UUID/mount, exact guard and static route, verified cached images and newly delivered tmpfs secret files before any app start. Missing data mount must not create boot-disk data directories. Missing secrets after reboot must not restart apps with stale credential env. The wrapper ensures old container metadata does not provide a fallback. No boot-time registry/Secret Manager access using VM ADC. Guard/config tampering by trusted root is outside workload isolation; runtime checks must detect configuration drift and stop protected applications rather than silently switching routes.

## SeaweedFS and durable state

Keep image `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d` (local image ID `sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5`, version4.48), service name minio, private port9000 and persisted `/data`. The exact image's `mini -h` confirms `-s3.config`; do not use MINIO_ROOT_USER/PASSWORD as SeaweedFS configuration. Freeze this supported command, with capacity flags chosen/tested separately from the tiny probe:

```text
mini -dir=/data -s3.port=9000 -s3.config=/run/autodata/minio/s3.json
  -admin.ui=false -webdav=false -s3.iam=false
  -s3.port.iceberg=0 -s3.port.lance=0 -master.telemetry=false
```

Use `user: "1000:1000"` after explicitly initializing only the new owned data directory to UID/GID1000; read-only config files must be readable by that UID. The image's root entrypoint invokes su-exec/setgroups, so starting it as root with cap-drop ALL fails before S3. No routine capability addition is needed when the regular service starts directly as UID1000. State initialization is a separate bounded root-owned operation, never a recursive chown of an unchecked mount.

The actual JSON schema is `identities:[{name,credentials:[{accessKey,secretKey}],actions:[...]}]`. Normal runtime config has two identities: worker with `Read:autodata-sources`, `Write:autodata-sources`, `List:autodata-sources`; API with `Read:autodata-sources` only. Distinct strong keys, no anonymous identity, global runtime action, Admin or List-all. Bootstrap adds a separate short-lived identity with Admin/Read/Write/List/Tagging to create the required bucket through the ingestion image's existing Minio client. Before normal application start, remove the bootstrap identity from the mounted config and restart mini; verify retired credentials fail and worker/API still function. Do not rely on a config rewrite being reloaded without restart. Temporary bootstrap files/clients are unmounted and removed; no admin key reaches API/worker. S3 admin is not a Google cloud credential.

**S3 authentication does not protect mini's other listeners.** Local logs show filer and admin control planes still start with unauthenticated interfaces despite `-admin.ui=false`/`-s3.iam=false`. The authorized local probe directly retrieved the synthetic source object from filer8888 without S3 credentials. Thus the storage port boundary above is mandatory. Do not connect apps to an unrestricted mini backend and claim API read-only isolation from the S3 policy alone. No cloud deployment is approved until the actual host bridge/routed guards are tested.

Local probe receipts are retained under `/tmp/autodata-seaweedfs-auth-probe-2` and `/tmp/autodata-seaweedfs-auth-probe-3`, with exact command, script/log hashes, outcomes and cleanup. These synthetic probes use an owned internal Docker network/volume, no published ports, UID1000,256MiB/0.5CPU, cap-drop ALL, no-new-privileges. Probe2 proved admin bucket bootstrap; worker put/get; API get; API put/delete/bucket-create denial; worker bucket-create denial; anonymous bucket/object list/get/put denial, all403; persisted object read after restart. No OOM occurred and all owned resources were removed. The earlier interrupted attempt is retained separately under `/tmp/autodata-seaweedfs-auth-probe`; it never reached S3 and is not a pass. Probe3 completed in16.64 seconds with `passed:true`, no failures/OOM, and all three cleanup flags true. It additionally proved unauthenticated filer retrieval200 with the same object SHA; after removing the Admin identity and restarting, its old list/create requests failed403 InvalidAccessKeyId, worker/API still read, and worker foreign-bucket write failed403. Probe3 result SHA256: `9629bae70f911415fe02b6e958fab5016bcfe3626b87760086be1e08fca7c0da`; script: `4460e87625325c6897447c6919e9f43edf0461654d33c45ccf5ba74ac1568e67`; redacted log: `c63c654b6a0cb19e5c6316f783bf71e24baac63658dbf1b60aecf53d313f0eb7`; mini help: `84c173814f61dcff3259a0eb014040020f57dece08da4037a46651cbc995d815`. Synthetic configuration was removed and no matching container, volume or network remained. Exact rerun command used `PYTHONPATH=/tmp/autodata-commerce-python-deps python /tmp/autodata-seaweedfs-auth-probe-3/probe.py`; the script records the separate ownership-initialization command and all finite client/Docker timeouts. These local results prove only the pinned S3 policy behavior and small-object persistence, not full production capacity, host network isolation, backup restoration or cloud readiness.

Do not run current object_storage_health.py as a passive check: it creates/version-enables buckets. Bootstrap only the bucket/features the actual application uses. Persistent disk subdirectories contain PG, SeaweedFS, JetStream and Caddy ACME state. Check ownership and filesystem UUID before Compose. Secret files and registry tokens remain off persistent disks. Docker/container metadata must contain no secret values. Ordinary process restarts use cached exact images/current tmpfs secrets; full reboot intentionally remains unavailable until external rehydration.

## IAM, monitoring and backup authority

Publish principal: registry writer for the one repository, no VM/secret/backup access. Deploy principal: named-secret-version accessor, repository reader and explicitly trusted IAP/OS Login host administration for this VM; no account-key creation or general IAM administration. Bootstrap operator separately creates/reviews resources and bindings.

Backup principal: no secret accessor, no deploy/Docker/root shell. Non-admin OS Login/IAP to the one VM and fixed backup-host.sh sudo verbs only; bucket object-create on unique owned names; a reviewed custom Compute snapshot role for the named disk and owned snapshot prefix: compute.disks.get/createSnapshot, compute.snapshots.create/get/list and compute.globalOperations.get, with per-resource conditions where supported and every unavoidable project-level permission explicitly reviewed. No delete authority in the routine backup principal. Separate bootstrap retention policy/lifecycle and separately authorized prune authority handle7daily/4weekly retention; do not give every backup run broad bucket delete or project Compute Admin. Restore operator is separate and explicitly approved, with backup read/restore and host-administration authority. Service Account User on only the attached Firebase-reader account is granted only where actual OS Login access requires it, never Token Creator.

Monitor principal: non-admin OS Login/IAP and exactly runtime-check metrics, plus Cloud Monitoring metricWriter. OS Login permits ordinary unprivileged shell commands; it must confer no Docker membership, arbitrary privileged command, SQL credential, log export or ability to read /run secrets. Only the fixed root-owned metrics helper is sudo-allowlisted. Fixed helper exports only bounded valid metric names/number values and allowlisted state labels; reject unexpected output. Native Compute/HTTPS uptime metrics plus those aggregates cover disk space, service restart/unavailable state, PG connectivity, oldest article/index/rewrite lease/retry age, preparation/reconciliation/outbox lag/count, NATS state, S3 error count, last verified backup time, last restore-drill time and exporter heartbeat. Expose API latency/error aggregates only when actually measured from sanitized Caddy metrics/log fields; do not relabel missing values as zero. Never include URL/token/source/customer/order IDs in metric labels. Configure queue/backup/disk/uptime/heartbeat alerts to an owner-selected destination and prove a real test alert reaches it in staging. Budget alerts remain bootstrap-owned and are not spending caps.

## Ordered deploy, reboot, failure and restore

Fresh provision: apply approved resource/IAM plan; format only an explicitly new empty data disk after identity checks; mount by UUID; install reviewed Docker/packages, early guard and root helpers; external deploy pulls exact images through transient registry auth and rehydrates per-service secrets. Start PG/NATS/S3; provision scoped DB roles and S3 identities/bucket with temporary admin credentials; run released shared migrations once; apply/check runtime grants; start private HTTP and verify enabled merchant/price/schema startup; start one article worker and reconciler, then API. Only then Caddy leaves maintenance after actual readiness plus no-work authenticated S3/private-service checks. Startup external provider probes are explicit authorized staging/live rollout actions, not part of offline config rendering.

Maintenance uses a fixed root-generated Caddy include switched/reloaded through a root-only Unix admin socket, not a network-accessible admin endpoint. Maintenance responses503 with Retry-After, no-store and no application details. Stop accepting new requests before bounded application stop. The current Go server does not establish a graceful signal-drain protocol; do not claim in-flight requests are guaranteed completed. Idempotent client retry and actual durable DB state govern interrupted work. Stop API/private HTTP/reconciler/article worker, then perform migration/backup operations. Retain maintenance on validation/migration failure; preserve receipts and request a forward fix. No blind down migration or starting old images against unverified incompatible schema.

Nightly backup: external run creates UUID lease; fixed host helper enters maintenance/stops writers; produce and verify custom PG dump while PG remains up; stop PG/NATS/S3; sync; external principal requests/awaits the named data-disk cold snapshot. Finish snapshot within the valid30minute maintenance lease, then fixed resume helper starts stateful services and applications in the proven order. Local watchdog attempts bounded safe resume if the external job disappears and marks that run incomplete. If timeout/resume races an unfinished snapshot, that snapshot is not a verified recovery point. After service recovery, stream the fixed UUID dump/nonsecret release manifest over IAP to external runner; upload with external bucket credential and verify immutable object generation/hash. Receipt succeeds only when snapshot, verified upload, resume and no-work readiness checks all succeed. Failures alert and never advance last_verified_backup. No raw secret/archive of/run/autodata. Actual first-snapshot/dump time must prove the maintenance window on representative data; the plan does not promise30minutes is sufficient merely because it is a timeout.

Reboot: Docker cannot precede mount/guard; no app may become healthy before secret redelivery. External deploy/bootstrap verifies selected release and pinned secret versions, then resumes. Losing runner/WIF/Secret Manager availability therefore extends recovery; accepted RTO must include that dependency. Secret rotation installs a new numeric version on tmpfs and restarts only affected services; no dual-key acceptance is invented. Media key rotation invalidates old image references, renewed by authorized projection refresh; persistent039 session tokens are DB-hashed and do not depend on a new invented server signing key.

Restore: only an isolated replacement disk/VM, production ingress in maintenance and bank/model/payment writer egress disabled. Stage1 validates snapshot UUID/cutoff, released image/SQL manifests, exact ledger/schema, account/session/grant/order ownership relations, article/source/canonical rows and every referenced S3 object, JetStream state and PG portable restore on a fresh compatible instance. No payment replay or provider fetch. Do not start configured_commerce processes and claim an offline API restore: actual startup intentionally contacts Stripe to verify merchant and price. Stage2, after separate authorization, selectively enables necessary real identity/merchant/price read checks with writers/reconciliation still stopped and maintenance retained, then uses the approved synthetic/test identity and authorized observational read procedure to prove source/canonical/media. This requires a real safe identity/project/payment configuration; it is not accomplished by setting production local auth, mixing test/live orders or using the return URL as ownership. Only after recovery ownership/data validation and operator approval may writers and live ingress resume. Record measured cutoff/RPO/RTO and failed attempts; never overwrite newer paid live activity as a routine image rollback.

## Verification and remaining owner decisions

Before this offline infrastructure implementation: independently review this bounded amendment and the measured SeaweedFS S3/control-plane boundary; synchronize canonical docs/todo/Issue186/Project8 and task/record at the committed checkpoint; pass pinned machine preflight. Root then authorizes the staged disjoint builder milestones below. Freeze reviewed release toolchain/image pins before any deployable release is produced or runtime operation is authorized; the first pure schema tests require exact pins and reject unresolved ones without obtaining or executing them. Deterministic implementation/tests can proceed with fixture project identifiers once gated; pending real project/cost choices block apply/deployment, not all local development.

Required implementation tests include rendered Compose service/port/image/env/mount allowlists; no secret in Config.Env or image metadata; startup refuses wrong/missing disk/guard/secrets; API-only metadata from every service namespace after daemon/reboot, plus actual non-admin host OUTPUT denial for IPv4/IPv6/metadata-hostname requests and successful designated API ADC refresh/GetUser and functioning actual guest-agent/OS Login under the explicit trusted UID0 metadata exception; no external-principal cloud credential on host; least-role Google deny proofs; real SeaweedFS auth/read-only/anonymous denial/durability; actual image commands/dependency imports; migration failure keeps maintenance; provider outage has no local fallback; interrupted backup/watchdog/failed upload do not certify recovery; portable and disk restore; previous compatible image rollback preserves newer ownership. Fake CLI unit tests alone cannot establish IAM/network/TLS/backup behavior. Required staging calls and billable actions require explicit owner authorization after concrete scripts/manifests/receipts are reviewable.

Owner inputs still pending: chosen GCP/Firebase/backup projects and billing/region/residency; cost estimate/budget and operator alert destination; commercial acceptance of nightly maintenance/RPO/RTO; Firebase Google app/domain registration and approved staging hostname; Stripe test/live merchant/price/terms/refund/tax configuration; licensed connector/model credentials and permitted use; final DNS/TLS cutover approval. Preserve these as deploy prerequisites, not invented values or claims of readiness.

## Final release, DNS and TLS approval

1. Select the GCP project, billing owner, region, operator, identity registration and product/payment contract. Review costs. Satisfy the repository's synchronized implementation gate, then build and verify the immutable integrated release. Existing application CI and the already planned product acceptance remain the checks; no new Kubernetes or autonomy-runtime certification is required for this VM topology.
2. Bring up an isolated staging instance using test identities and synthetic/licensed test fixtures. Exercise auth, protected media, article cold/source/canonical/warm paths, worker restart recovery, selected payment behavior, backup/restore and VM reboot with the persistent disk. External identity/provider verification, if needed, is a separately authorized staging action; infrastructure smoke must not call banks/models by default.
3. Deploy production while Vercel still serves `cars.tk`. A dedicated staging hostname requires approved DNS/certificate ownership; do not invent or change a hostname now. Keep final-origin production login/traffic disabled until its Firebase domain configuration and certificate are ready. ACME DNS-01 can provision the final certificate ahead of apex cutover only with an explicitly authorized DNS integration; otherwise use approved HTTP-01 cutover sequencing and allow an honest certificate-issuance maintenance interval. Do not promise that Caddy can complete HTTP-01 for an apex still pointed at Vercel.
4. Record current DNS records, TTLs and Vercel configuration. After owner approval, reduce TTL in advance, confirm final TLS/Firebase authorized-domain and popup-helper readiness, then change the apex A to the reserved VM address. Update/remove conflicting AAAA only if present and approved; retain unrelated mail/TXT records. Do not claim universal propagation within the TTL. Keep Vercel configured and reversible during the agreed observation period.
5. For each later application rollout, retain previous digests and config references, take a verified pre-migration backup, enter a bounded maintenance/drain window, run the exact released shared migration runner once, and start the selected release only on success. Validate actual database/schema head from that manifest, not a permanently hardcoded 038. A migration failure keeps writes stopped until diagnosed; no blind down-migration.
6. Application rollback selects the prior compatible image manifest without replacing live data. Schema changes must be backward compatible with that prior version or require an explicit recovery/forward-fix decision. DNS rollback to the preserved Vercel page can restore an informational/maintenance landing page; it cannot provide the new paid application's data/access functionality. A VM failure recovery uses the persistent disk on a replacement or the tested backup restore, not stale Vercel application state.


## Planning tracking and authoritative next gate

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Concrete todo and bounded dispatch are recorded below and in `docs/agents/tasks/2026-11-03-production-release/workshop-hosting.json`. Owner project/cost/recovery/operator inputs and final verified product/runtime evidence remain prerequisites for actual staging/apply, rather than blockers for these pure offline tests. Passing this gate alone never authorizes cloud resources, real secrets, DNS, provider calls or a runtime acceptance claim.

## Documentation references

- [ADC and attached service accounts](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Firebase Admin setup and GCE scopes](https://firebase.google.com/docs/admin/setup)
- [Identity Platform permissions](https://cloud.google.com/identity-platform/docs/access-control)
- [Compute service account scopes](https://cloud.google.com/compute/docs/access/service-accounts)
- [Metadata endpoints](https://cloud.google.com/compute/docs/metadata/querying-metadata)
- [Docker forwarding rule ordering](https://docs.docker.com/engine/network/firewall-iptables/)
- [GitHub WIF deployment pipelines](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
- [Secret-level access control](https://cloud.google.com/secret-manager/docs/access-control)
- [OS Login requirements](https://cloud.google.com/compute/docs/oslogin/set-up-oslogin)
- [Disk snapshots](https://cloud.google.com/compute/docs/disks/snapshots)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)


## Offline implementation checkpoint and first execution milestones

Source integration base: `3b551c992263f74e3ebdc6e4fa2c4ffda3b979a6`. Issue186 and its existing Project8 item are the shared tracking authority; the coordinator owns integration and independent review. No implementation file is changed by this planning checkpoint. Both builders use gpt-6.1-sol, medium reasoning, Fast/priority, no fallback.

The thirty allowed paths above remain exclusive: runtime A owns1–22 and operations B owns23–30. This gate permits implementation definitions and pure tests only after coordinator authorization. It does not permit invoking Docker/Compose, nft/systemd changes, packaging/building/pulling images, cloud/gcloud/SSH/IAP calls, DNS, secrets, provider endpoints, actual deployment or restore. Tests use standard-library unittest with inline fixture manifests and fake executable transcripts in temporary directories. No new dependency or fixture file is necessary. Existing policy, historical SQL001–040, application auth/payment/catalog/UI, base/CI/Base44 Compose and other CI workflows remain out of scope.

### First A milestone: exact schema, parser and render boundary

Only these eight A paths are executable in the first dispatch:

- `infra/deploy/gce/release.schema.json`
- `infra/deploy/gce/runtime-check.py`
- `infra/deploy/gce/test_host_runtime.py`
- `infra/deploy/gce/release.env.example`
- `infra/compose/compose.production.yaml`
- `infra/deploy/gce/Caddyfile`
- `infra/deploy/gce/nats.conf.template`
- `infra/deploy/gce/seaweedfs-s3.json.template`

Write failing tests first for strict duplicate/unknown-field rejection, image/digest/platform/source/migration/config/secret-version binding, fixed service and network graph, Caddy-only published ports, metadata/storage guard prerequisites, no ambient/local fallback, and fake secret values absent from rendered Docker environment. Implement the literal shared v1 contract below. `runtime-check.py` in this milestone provides a passive parser/validator and receipt renderer; it must not start services or probe real endpoints. Tests intercept every attempted subprocess and reject any executable outside their owned fake paths. `release.env.example` contains nonsecret names only; it must not advertise unresolved values as deployable.

Run `python -m unittest discover -s infra/deploy/gce -p test_host_runtime.py -v` with no Docker daemon or provider access. Retain red/green stdout and exact input hashes outside the checkout, run `git diff --check`, commit and push this coherent milestone. Coordinator independently reviews and pins the manifest fields, nonsecret service-config object, per-service secret allowlists, allowed metrics/receipt names and render output before B consumes it. The service-config object must include exactly environment/origin/Firebase public configuration, resource names, fixed service commands/network addresses, expected disk UUID, topology and nonsecret runtime tuning; it contains no credential values. Environment is `production|staging`, and every origin/config field is validated rather than inferred from the shell.

### First B milestone: consume reviewed A contract with fake CLI only

Only after coordinator-approved exact A dependency integration, B initially implements `infra/deploy/gce/cloud-ops.py` and `infra/deploy/gce/test_cloud_ops.py` from its existing eight paths. Consume the same v1 schema/layout/helper verbs without speculative aliases or a second manifest model. Write failing tests for bounded argv/timeouts, exact WIF/environment/repository/ref restrictions in planned operation definitions, wrong owner/disk/image/lease/snapshot, failed upload/resume and duplicate/escaping tar members. Fixed fake CLI transcripts cover success, command error, timeout, interrupted stream and cleanup failure; tests assert no real executable or network can run. The production helper remains fail-closed when real approved configuration, reviewed pins or required receipts are absent.

Run `python -m unittest discover -s infra/deploy/gce -p test_cloud_ops.py -v`; retain exact inputs/red-green logs, then commit/push for independent review. Remaining A/B files, executable operations and later runtime verification require coordinator authorization after these first contract milestones. A reviewed contract change uses the existing affected paths and a visible amendment; it cannot silently expand the thirty paths.

### Concrete todo and verification separation

- [ ] Synchronize actual Issue186/Project8 and canonical docs/task/record; commit the checkpoint and pass machine preflight at that full checkpoint SHA before dispatch.
- [ ] Coordinator reviews this exact gate and separately authorizes first A eight-path schema/parser/render milestone.
- [ ] A produces retained red/green pure tests and exact commit; coordinator independently freezes the literal shared contract before B's two-path fake-CLI milestone.
- [ ] B produces retained red/green pure tests and exact commit without running real CLIs; coordinator reviews both milestones and authorizes remaining same-scope implementation only when concrete.
- [ ] Resolve reviewed image/toolchain pins, actual project/cost/recovery/operator/provider choices and exact integrated product evidence before any separately authorized staging action.
- [ ] Obtain actual host/container IPv4/IPv6 metadata and storage denials, API SDK refresh/GetUser/platform success, mounted-disk/reboot/secrets behavior, signed/test commerce, backup/restore/alert delivery and final-origin TLS evidence; fake tests never certify these.
- [ ] Keep cars.tk/Vercel and live data untouched until a concrete reviewed cutover and appropriate existing authorization apply.

## Shared v1 interface frozen for first milestones

## Fixed local layout and names

- Root-owned host config: `/etc/autodata/host.json`, mode0600; nonsecret settings only. No implicit cwd lookup. Bootstrap alone installs it; helpers reject symlinks and wrong owner/mode.
- Root-owned immutable release: `/opt/autodata/releases/<40lowerhex>/`; manifest `release.json`, standalone `compose.production.yaml`, Caddy/config/templates and released helper inputs. `/opt/autodata/current` is a root-owned symlink resolving exactly to one validated release directory; do not follow caller paths.
- Fixed installed root helpers: `/opt/autodata/bin/deploy.sh`, `backup-host.sh`, `restore.sh`, `runtime-check.py`; only reviewed bootstrap/deploy administration replaces them. External backup/monitor callers cannot select an alternate executable or config path.
- Data mount `/var/lib/autodata`, verified by configured filesystem UUID before any mkdir/start; owned subdirectories `postgres`, `seaweedfs`, `nats`, `caddy`, `backups`. New-directory ownership is initialized per service, not recursively across an unchecked mount.
- Tmpfs `/run/autodata`: per-service secret subdirectories already specified in canonical plan; `registry/` for transient pull configuration; `state/` for root-only operation lock/lease. No service receives the whole tmpfs.
- Persistent safe receipts `/var/lib/autodata/operations/<uuid>.json`,0600. Never put credentials/raw requests in receipts. Backup output directory `/var/lib/autodata/backups/<uuid>/`,0700, with `postgres.dump`, `release.json`, `backup.json`. Portable DB dumps are private customer data, not public artifacts.
- Compose project `autodata-production`; service names exactly caddy/api/ingestion-http/article-worker/payment-reconciler/postgres/nats/minio plus profiles `migration`, `bootstrap`, `metrics` containing migration/bootstrap/metrics-probe one-shots. Normal start explicitly names only the eight normal services. Runtime images and service commands remain those in the canonical plan.

All modes/paths above are shared literals, not caller-supplied values. A owns creation/validation and B consumes them. No path is added to the30 implementation files; these are runtime destinations generated by the existing scripts.

## release.schema.json v1

Strict JSON object, additionalProperties:false at every declared object. UTF-8 size<=1MiB, no duplicates, finite numbers only. References never carry secret values. Required fields:

```
schema_version: 1
source_sha: <40lowerhex>
platform: "linux/amd64"
images: {api, ingestion, migration, caddy, postgres, nats, minio:
  {reference:<registry/repository/name@sha256:64lowerhex>,
   image_id:<sha256:64lowerhex>,
   provenance_uri:<immutable artifact reference>,
   sbom_uri:<immutable artifact reference>}}
migrations: {runner_sha256:<64hex>,
  files:[{name:<NNN_lower_snake.sql>,sha256:<64hex>}],
  inventory_sha256:<64hex>}
toolchain: {
  docker_engine:{version:<exact string>,package_sha256:<64hex>},
  docker_compose:{version:<exact string>,package_sha256:<64hex>}}
service_config_sha256: <64hex>
secret_versions: {<allowlisted SERVICE>:
  {<allowlisted NAME>:"projects/<project>/secrets/<name>/versions/<positive decimal>"}}
rollback_source_sha: <40lowerhex or null>
```

One ingestion image intentionally serves HTTP/article-worker/reconciler/metrics; service roles still have disjoint commands/mounts/secret-name allowlists. The release manifest contains images by image role, not duplicate worker image labels that could silently diverge. Image IDs are platform-specific locally inspectable identities; registry references are immutable content digests, not assumed equal to image IDs.

Manifest digest = SHA256 of canonical JSON (UTF-8, sort_keys=true, separators=(',',':'), no trailing newline). Migration inventory digest = SHA256 of canonical JSON array `files` in filename order using the same encoding. The released shared runner and exact migration file tree are independently checked against those hashes. Require contiguous unique migration versions beginning001 and final manifest version matching actual schema; current application has040. Do not assume future count040 in generic release tooling. All references must be fully resolved and no `<...>`, `latest`, secret version alias, tag-only image or unknown field may reach apply/start.

`service_config_sha256` binds canonical nonsecret service configuration JSON (the fixed application and topology settings), not secret bytes. A defines the literal settings object and exact service secret-name allowlists in its first reviewed schema milestone; B must consume that version unchanged. PUBLIC_ORIGIN must match the reviewed environment exactly. Record the fixed platform choice in cloud-bootstrap validation before applying a VM architecture.

`rollback_source_sha=null` is allowed only for first installation. Otherwise its manifest must already exist and pass schema/image/config compatibility validation. A migration failure never implies permission to start an old image against a new schema.

## Host operations and receipt/stream contract

Freeze existing helper argv exactly as in canonical plan. Validate argument count as well as UUID/SHA shape. Helpers clear inherited environment, use absolute executables/pinned config, no shell sourcing/eval, no caller-selected command or path. Operation receipts on stdout are one JSON object (<=64KiB); bounded operational diagnostics go to stderr with no raw exceptions/secret content. Exit codes remain0 success/2 invalid input/3 missing dependency or guard/4 operation failure/5 timeout/6 incomplete recovery. A nonzero receipt must never contain passed:true.

Common receipt fields: `schema_version:1`, `operation:<literal helper+verb>`, `run_id:<uuid or null for release check>`, `source_sha:<40hex or null before install>`, `status:passed|failed|timed_out|incomplete`, `started_at`, `finished_at` (UTC RFC3339), `checks:{<fixed allowlisted name>:boolean}`, `failure_code:<allowlisted code or null>`. Add only the operation-specific fields below; no raw command environment, customer IDs, tokens or query rows.

- `deploy.sh check SHA`: passive local validation; reports manifest digest, disk UUID match, guard/config/secrets state, cached image identity, actual schema version. It must not migrate, contact providers, reconcile or hydrate. `start`/`resume` use the canonical ordered startup and no-work readiness; `maintenance` cannot silently stop Caddy maintenance on failure. `install` accepts only an already staged root-owned exact release and fixed host config, not an uploaded shell command.
- `runtime-check.py check --release SHA`: receipt with service/DB/NATS/S3 allowlisted states and no-work counters. `metrics` emits a JSON object `{schema_version:1,source_sha,observed_at,metrics:[{name,value,unit,state}]}`; unique allowlisted names, finite numeric values, fixed unit/state enums, no dynamic labels. B maps these reviewed names to Cloud Monitoring descriptors; missing measurement is absent/unavailable, not zero. A and B review the exact metrics list in A's first milestone.
- `backup-host.sh begin UUID`: serializes with a root-only lock, rejects a different active lease, enters maintenance/stops writers, creates the PG custom dump, stops stateful services, syncs and returns `state:quiesced`, `lease_expires_at`, `dump_sha256`, `dump_bytes`, `source_sha`, `manifest_sha256`, `disk_uuid`. Lease total<=1800s including resume reserve. Repeated same UUID returns its existing state without repeating a dump/snapshot; a completed UUID cannot start a new run.
- `status UUID`: reports only that lease's state, expiry, dump/manifest identity and whether writers/stateful services resumed. Allowed monotonic states `preparing→quiesced→resuming→resumed`, with `failed|expired|incomplete` terminal evidence. An expired quiesced lease triggers the existing watchdog's bounded resume; it never becomes verified backup merely because services recover.
- External B snapshots only after an unexpired quiesced receipt identifies the exact configured disk. B records snapshot resource/selfLink, operation identity, completion/cutoff timestamps and fixed manifest/dump hashes in its external receipt. No cloud token reaches host.
- `resume UUID`: idempotently resumes only the matching lease/release, validates normal startup, records resumed or incomplete. A newer active lease cannot be resumed by an older UUID. Snapshot completion after lease expiry/resume is not a verified recovery point.
- `export UUID` is the sole binary stdout exception: after successful resume, emit a tar stream with exactly regular `postgres.dump`, `release.json`, `backup.json`, no directories/symlinks/extra members, from that UUID directory. Status/manifest bytes and the independently verified dump hash remain available via status. B checks member paths/types/sizes/hash and stores the three objects under immutable `<UUID>/...` backup names; no general path export. Stream/client subprocess deadlines remain within canonical backup bounds. Routine backup principal has no delete permission.
- `restore.sh restore|validate UUID`: only a separately staged root-owned isolated restore config/directory. Reject current/live data UUID/path and production writer egress before copying. Validate exact released manifests/schema/data/object references; no bank/model/payment calls. Cloud-ops stages the fixed receipt/input locations; no caller-selected root path or shell command reaches sudo.

B's external final backup receipt additionally binds immutable bucket generations, dump SHA/bytes, snapshot identity/cutoff, source/manifest/schema, successful resume/readiness and cleanup. `last_verified_backup` advances only after all pass. A host receipt alone cannot certify the external upload/snapshot. Snapshot/restore permissions and platform bootstrap remain explicit owner-approved actions.

## First integration checkpoint before builders diverge

A first authors schema/constants/render tests and fixed helper parsers within its22 paths, with fake inputs only. Root independent review freezes schema version, config/secret-name maps, receipt fields, metrics list and installed paths. B develops its8 paths against those exact files via a coordinator-approved dependency merge. Breaking a field later requires a reviewed same-scope plan amendment, not accepting speculative aliases. Negative tests cover unknown fields/verbs/args, path/symlink/env substitution, stale lease resume, duplicate export members, secret/version aliases, wrong image/input/schema and malformed metric values.

Actual toolchain/image pins and every unavoidable project-level snapshot IAM permission must be resolved/reviewed before apply/start. Actual unprivileged host+container metadata denial, API SDK refresh/GetUser, storage bridged/routed restrictions, OS Login/guest-agent operation, reboot, backup/restore and final-origin TLS remain real staging evidence; mocks cannot certify them. The trusted UID0 metadata exception and untrusted host/worker denial in62a47c remain mandatory. This proposal does not authorize new cloud scope or replace the canonical pre-implementation gate.
