# Isolated Workshop Stripe TEST staging

Issue https://github.com/lucronn/autodata/issues/445; parent https://github.com/lucronn/autodata/issues/398.
Project https://github.com/users/lucronn/projects/8.
Source base: a82b31dc8850aa3956972928b8c720969765a972.

Goal: Prepare current-source isolated Workshop Stripe TEST staging with truthful TEST-only notices and durable secret delivery.

Plan: `docs/superpowers/plans/2026-11-16-workshop-isolated-test-staging.md`. Record: `docs/agents/records/2026-11-16-workshop-isolated-test-staging.json`.

This lane prepares an isolated runtime and test-only notices; no production purchase policy is approved. No new runtime is running. Historical local stage recovery restored its disabled-commerce API but is not this staging deployment.

Existing checkout-test credentials are private configuration inventory, not proof of current authenticated merchant readiness. Its API cannot start because transient ADC/config files disappeared; current-source staging uses new durable per-service secret files after explicit review. Legacy authorized-user ADC belongs to the existing gcloud account, has no offline verified scopes and must not be silently reused.

The selected API origin must be separate HTTPS and Firebase-authorized, with exact registered tester UIDs. Existing public aliases are forbidden. Cloudflare local authority currently consists of a run token, not verified DNS/account-management authority; cars.tk DNS uses Vercel. No stable staging route has been established. Root reviews DNS/origin and Docker starts separately. No real bank/model content enters without source authorization.

TEST-only pages describe simulated charges, temporary test grants, diagnostic handling and maintainer feedback without production seller, privacy-retention or final tax promises. They do not approve PR348. Enabled test purchase config points all four URLs at the same reviewed staging origin; no real tax is collected in TEST mode. Live purchase configuration remains disabled.

## Concrete todo
- [x] Synchronize plan, Issue445, Project8 and canonical documentation; pass exact-base preflight
- [x] Add server-gated TEST-only notices with route and production-mode denial tests
- [x] Add offline isolated-stack renderer and durable JSON secret launcher; test production/live/shared-resource/empty-tester refusal
- [ ] Prepare reviewed current-source runtime inputs; hold Docker, DNS/origin and external Stripe TEST calls for coordinator review
- [ ] Run actual restricted authenticated TEST checkout/grant/read/denial/refund acceptance only after runtime prerequisites; do not substitute fixtures or claim missing licensed acceptance

## Prepared offline implementation

The unique runtime root is `/home/corp/autodata-evidence/autodata-workshop-stripe-staging-20261116`, on the offloaded filesystem. Do not use physical-home build caches without a current capacity review. The renderer fixes the project/network/storage names and loopback3043, uses cached digest-identified images, and rejects another runtime root. API, private ingestion and the enabled TEST-only reconciler receive egress; DB/S3/NATS remain internal. All cached-image provider credentials/defaults are explicitly blanked before launch and removed before child exec. Existing dev-image defaults are not deployment credentials.

The profile has exactly `origin`, `tester_uids`, `firebase`, `stripe`, `source_sha`, `binary_sha256`, `enabled`. Firebase contains `project_id`, public `api_key`, `app_id`, `auth_domain`; Stripe contains expected `account_id`, `price_id`. Use actual registered tester UIDs and a separately authorized HTTPS hostname. Default `enabled:false` starts no commerce subsystem; explicit true sets both authorities to stripe_test and enables only TEST notices. Private startup may then call Stripe to verify merchant/Price, so root must review before starting it.

Materialize the exact committed source with Git archive under `<root>/source`; record only `{"source_sha":"<exact commit>"}` in `<root>/source-identity.json`. Build a CGO-disabled Linux API binary from that source under `<root>/bin/autodata-api`, measure SHA256 and pin it in the profile. The renderer verifies every archived source file against current Git objects and rejects changed/extra files; the pinned binary hash identifies the reviewed build but is not a source-to-binary attestation.

The next offline command after those inputs exist is:

```sh
python3 scripts/dev/workshop_test_staging.py render --profile /absolute/reviewed-profile.json > /absolute/reviewed-compose.json
```

It performs no Docker or network action. `docker compose ... config --quiet` is an offline syntax check. Do not use `config` without `--quiet` on unrelated private manifests. Root reviews the exact source, binary, images, manifest, available capacity, credentials, authorized hostname and tester UIDs before any container starts. Start dependencies, run fixed migrations, then API/private ingestion in explicit phases; there is no automatic apply command.

Create a private0700 directory under the runtime root. API `api.json` and private ingestion `ingestion.json` must be regular0600 files owned by uid1000, without symlinks. Both carry fresh isolated DB/S3/internal secrets; only API carries image signing key. Enabled TEST ingestion and the separate reconciler.json role receive reviewed TEST Stripe secret/webhook material; disabled ingestion must contain neither Stripe key. Reconciler JSON follows the same0600/uid1000/no-symlink rules and has no Firebase, bank, image or model credential names. The launcher accepts exact per-role key allowlists and rejects live prefixes without echoing data. Firebase `firebase-adc.json` is a separately approved durable0600 credential, read-only mounted to API; this lane did not reuse the legacy ADC. Scalar `pg-password` must be readable only by PostgreSQL uid999; scalar `s3-access`/`s3-secret` and libpq `pgpass` are0600 uid1000. The pgpass entry must name postgres:5432 and the exact `workshop_stripe_staging` database/user. Create fresh pgdata uid999 and nats/S3 work/data directories uid1000 before Compose; all binds have create_host_path:false. No secrets belong in the profile, generated Compose, shell command arguments, repository or evidence.

Disabled profiles have six services and no reconciler. Explicitly enabled TEST profiles add a bounded payment-reconciler service; rendering never starts it. Signed webhook delivery to `/v1/payments/stripe/webhook` must be explicitly bound to the correct isolated origin and TEST account before checkout acceptance; root reviews the reconciler start separately. Never count healthz as merchant/payment/auth/browser acceptance.

## Fresh authority and validation evidence

On2026-11-16 the ambient authorized gcloud account performed a narrowly scoped read-only Identity Toolkit project-config request for vehapi-torque, HTTP200. Authorized domains include localhost, project Firebase Hosting domains, three existing unrelated Cloud Run domains and autodata.cars.tk; no dedicated staging hostname. No users were listed, tokens printed, domains changed or credentials reused for runtime. Sanitized receipt: `/home/corp/autodata-evidence/stage-runtime-recovery-20261116/firebase-authority.json`.

Focused Go notice route tests passed before a capacity pause. At the initial implementation checkpoint, six Python tests passed: isolated defaults/resource boundaries, equal test enablement and notice origins, origin/tester/shared-root denial, secret-file permissions/symlink/live-key denial, inherited-provider stripping and actual source-byte tamper rejection. Full API build/tests and real Docker startup remain held for capacity/root review. Source/transport tests do not prove actual Google sign-in, settlement, supplier rights or licensed content.

Offline Compose fixture rendering also passed `docker compose ... config --quiet` without starting services. The fixture profile contains synthetic IDs and is not a startable owner-approved configuration.

## Root review correction: inherited environment and disabled credentials

The key-only audit of all six selected cached service images is retained in `/home/corp/autodata-evidence/stage-runtime-recovery-20261116/cached-image-env-key-audit.json`. No Config.Env values were emitted by that audit. The actual Python image has bank, local DB/S3 and image-key defaults; every sensitive default is explicitly overridden. INCEPTION_API_KEY and Firebase/Google/Stripe credential keys were not present in that exact image but are explicitly cleared in the generated manifest as well. Do not infer safe inheritance from those absences.

Child processes now receive only a per-role public configuration allowlist plus validated private-file keys. Unknown credentials, model keys, unprefixed Stripe keys and LD_PRELOAD do not cross into the child. Firebase public client config and the explicit ADC filename are allowed only for API; private ingestion receives neither Firebase nor Google credentials. Disabled ingestion rejects a private JSON file containing either Stripe secret key or webhook secret, even if test-prefixed; those keys must be absent. Disabled child environments also omit expected Stripe merchant/Price IDs. At the inherited-environment correction checkpoint, seven offline tests passed, including red-first regressions that failed before that correction.

## Exact webhook and reconciler behavior

At the unchanged current commerce source, `CommerceService.webhook` verifies the supplied signature through the configured provider, ignores unsupported events and immediately calls `reconcile_event` for a supported verified event. This is synchronous request processing. `reconcile_event` commits the verified sanitized event as pending, checks test/live equality and order/merchant binding, retrieves authoritative Checkout/PaymentIntent facts and validates settlement. For a settled non-revoked order, its final scope-locked transaction creates the purchased dataset request, active exact-owner/configuration/region entitlement and projection; updates the order to paid with preparation_state=pending; and marks the event fulfilled. A duplicate already fulfilled event returns accepted without granting again. The background reconciler is not required for that successful webhook-to-grant transaction.

A supported event can instead remain pending: for example, no matching order or no Checkout session identifier. That path can return pending successfully, so a retained event needs `reconcile_pending_payments` to retry later even if the provider does not redeliver it. A transient provider lookup failure raises PAYMENT_DEPENDENCY_UNAVAILABLE503; later provider redelivery or background retry is needed. Financial conflicts are marked failed/quarantined. Full verified TEST refund/revocation also runs synchronously in this path; an old settlement does not resurrect revoked access.

Separately, payment settlement sets preparation pending and does not run article-index scheduling. `scripts/dev/reconcile_payments.py` calls `reconcile_pending_payments` and `reconcile_workshop_preparation`; that preparation function leases paid work and schedules shared index work. Without that process, an already readable source can still appear viewable, but newly needed content preparation can remain preparing. The disabled six-service stack supplies no recovery process. The enabled seventh service below supplies a finite recovery window; it does not establish continuous operation or complete source-worker work. Root must review its actual start and separately authorized source workers before claiming eventual preparation in a running demo. This assessment is source-based; no Stripe call, order, webhook, grant or runtime was created for it.

## Bounded TEST reconciler operational contract

The amended checkpoint31421bd passed preflight before implementation. Issue445/Project8 and the canonical plan authorize this offline implementation: retain six disabled-mode services, add an explicit seventh TEST-only payment-reconciler when purchases are reviewed enabled. It uses its own read-only private/reconciler.json, the same fresh isolated DB/S3/internal secrets, TEST Stripe only, and no Firebase/bank/model/image credentials or listener. The role refuses disabled/live/production mode, a production origin, and any database address/name/user outside postgres:5432/workshop_stripe_staging before launching the existing runner. An outer wrapper invokes the existing runner --once --batch-size10 for at most10 passes with45seconds per child,15second intervals and600second global budget; timeout/nonzero/drift fail closed. Existing runner/source/schema remain unchanged. It schedules/observes durable article jobs but supplies no bank/model worker or licensed-content acceptance. Root still holds all runtime/provider/IAM/DNS/Auth actions.

The container is uid1000, read-only, all capabilities dropped, no-new-privileges, with384MiB memory/0.5CPU, tmpfs64MiB, init:true, restart:no, no health listener or published port, and10second stop grace. It has only archived source and its private JSON binds; cached-image credentials are blanked and unknown inherited credentials removed before either child exec. It attaches only the isolated internal/egress bridges.

Each pass starts a new unchanged configured_commerce instance, which verifies the expected TEST merchant/Price through Stripe before database work. That is an external TEST request requiring root review at runtime. Child stdout/stderr are discarded because runner results may contain order identifiers; only fixed pass/stop messages are logged. Nonzero or timeout exits2 immediately without another pass. A successful pass log means the runner exited0, not that every event settled or every preparation job completed. Pending/blocked business outcomes must be inspected through approved isolated DB/API evidence. At most10 passes run, each at most45seconds, separated by15seconds, within600seconds overall. The service exits after its budget and does not auto-restart; a later explicit root-reviewed run is required for further retry windows. Stopping/timing out can leave the existing30second preparation lease; the unchanged scheduler retries after lease expiry.

Red-first service/role/budget/negative tests failed before this amendment and all12 staging-helper tests pass after it. Both disabled6-service and enabled7-service fixture manifests pass offline Compose syntax validation. No database/provider/container was invoked by those tests, no credentials were provisioned/copied, and the existing runner/commerce/schema remain unchanged. Focused Go notice tests were already green; no Go code changed in this amendment and builds remain held for capacity. No service is started by this amendment.

After root approves the exact enabled manifest and prerequisites, dependencies/migrations/ingestion must already be ready before the explicit foreground reconciliation command below. This command is documentation, not executed acceptance:

```sh
docker compose -f /absolute/reviewed-compose.json up --no-deps --no-build --pull never payment-reconciler
```

Retain the exit code and fixed logs; verify expected isolated DB transitions separately. Do not add a restart policy, cron or unbounded loop to extend this reviewed window. The next actual step remains root review of source/binary, TEST credentials, registered tester UIDs, origin/Firebase authorization and available capacity; no runtime acceptance has occurred.
