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
- [ ] Synchronize plan, Issue445, Project8 and canonical documentation; pass exact-base preflight
- [ ] Add server-gated TEST-only notices with route and production-mode denial tests
- [ ] Add offline isolated-stack renderer and durable JSON secret launcher; test production/live/shared-resource/empty-tester refusal
- [ ] Prepare reviewed current-source runtime inputs; hold Docker, DNS/origin and external Stripe TEST calls for coordinator review
- [ ] Run actual restricted authenticated TEST checkout/grant/read/denial/refund acceptance only after runtime prerequisites; do not substitute fixtures or claim missing licensed acceptance

## Prepared offline implementation

The unique runtime root is `/home/corp/autodata-evidence/autodata-workshop-stripe-staging-20261116`, on the offloaded filesystem. Do not use physical-home build caches without a current capacity review. The renderer fixes the project/network/storage names and loopback3043, uses cached digest-identified images, and rejects another runtime root. API and private ingestion alone receive egress; DB/S3/NATS remain internal. All cached-image provider credentials/defaults are explicitly blanked before launch and removed before child exec. Existing dev-image defaults are not deployment credentials.

The profile has exactly `origin`, `tester_uids`, `firebase`, `stripe`, `source_sha`, `binary_sha256`, `enabled`. Firebase contains `project_id`, public `api_key`, `app_id`, `auth_domain`; Stripe contains expected `account_id`, `price_id`. Use actual registered tester UIDs and a separately authorized HTTPS hostname. Default `enabled:false` starts no commerce subsystem; explicit true sets both authorities to stripe_test and enables only TEST notices. Private startup may then call Stripe to verify merchant/Price, so root must review before starting it.

Materialize the exact committed source with Git archive under `<root>/source`; record only `{"source_sha":"<exact commit>"}` in `<root>/source-identity.json`. Build a CGO-disabled Linux API binary from that source under `<root>/bin/autodata-api`, measure SHA256 and pin it in the profile. The renderer verifies every archived source file against current Git objects and rejects changed/extra files; the pinned binary hash identifies the reviewed build but is not a source-to-binary attestation.

The next offline command after those inputs exist is:

```sh
python3 scripts/dev/workshop_test_staging.py render --profile /absolute/reviewed-profile.json > /absolute/reviewed-compose.json
```

It performs no Docker or network action. `docker compose ... config --quiet` is an offline syntax check. Do not use `config` without `--quiet` on unrelated private manifests. Root reviews the exact source, binary, images, manifest, available capacity, credentials, authorized hostname and tester UIDs before any container starts. Start dependencies, run fixed migrations, then API/private ingestion in explicit phases; there is no automatic apply command.

Create a private0700 directory under the runtime root. API `api.json` and private ingestion `ingestion.json` must be regular0600 files owned by uid1000, without symlinks. Both carry fresh isolated DB/S3/internal secrets; only API carries image signing key, only ingestion carries test Stripe secret/webhook secret. The launcher accepts exact per-role key allowlists and rejects live prefixes without echoing data. Firebase `firebase-adc.json` is a separately approved durable0600 credential, read-only mounted to API; this lane did not reuse the legacy ADC. Scalar `pg-password` must be readable only by PostgreSQL uid999; scalar `s3-access`/`s3-secret` and libpq `pgpass` are0600 uid1000. The pgpass entry must name postgres:5432 and the exact `workshop_stripe_staging` database/user. Create fresh pgdata uid999 and nats/S3 work/data directories uid1000 before Compose; all binds have create_host_path:false. No secrets belong in the profile, generated Compose, shell command arguments, repository or evidence.

No payment reconciler is started by this preparatory six-service stack. Signed webhook delivery to `/v1/payments/stripe/webhook` must be explicitly bound to the correct isolated origin and TEST account before checkout acceptance; background reconciliation and periodic operation remain separate runtime work. Never count healthz as merchant/payment/auth/browser acceptance.

## Fresh authority and validation evidence

On2026-11-16 the ambient authorized gcloud account performed a narrowly scoped read-only Identity Toolkit project-config request for vehapi-torque, HTTP200. Authorized domains include localhost, project Firebase Hosting domains, three existing unrelated Cloud Run domains and autodata.cars.tk; no dedicated staging hostname. No users were listed, tokens printed, domains changed or credentials reused for runtime. Sanitized receipt: `/home/corp/autodata-evidence/stage-runtime-recovery-20261116/firebase-authority.json`.

Focused Go notice route tests passed before a capacity pause. Six Python tests pass: isolated defaults/resource boundaries, equal test enablement and notice origins, origin/tester/shared-root denial, secret-file permissions/symlink/live-key denial, inherited-provider stripping and actual source-byte tamper rejection. Full API build/tests and real Docker startup remain held for capacity/root review. Source/transport tests do not prove actual Google sign-in, settlement, supplier rights or licensed content.

Offline Compose fixture rendering also passed `docker compose ... config --quiet` without starting services. The fixture profile contains synthetic IDs and is not a startable owner-approved configuration.
