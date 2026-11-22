# Offline Workshop Stripe TEST staging

The isolated staging helper prepares a private Workshop stack with Firebase tester access and optional Stripe TEST checkout. Issue #445 tracks runtime readiness and hosted checkout acceptance. [Staging issue](https://github.com/lucronn/autodata/issues/445)

## Prepare the inputs

Use the fixed Kali runtime root `/home/corp/autodata-evidence/autodata-workshop-stripe-staging-20261116`. Put the Git archive of the exact selected revision under `source/`, with its `source_sha` in `source-identity.json`. Build the Linux API binary from that revision at `bin/autodata-api` and record its SHA-256. The renderer compares the archived files with the Git tree and validates the binary hash against the profile.

Build the Python runtime from `workers/ingestion-python/Dockerfile` using that same archive as the build context. Use the locally installed image ID from `docker image inspect --format '{{.Id}}' IMAGE`. Check that its image configuration has no embedded credentials before running a service with egress. The renderer rejects the known credential-bearing development image and leaves image pulls disabled.

The profile contains these fields.

- `origin` is the separate HTTPS origin authorized in Firebase.
- `tester_uids` lists the registered Firebase UIDs approved for this instance.
- `firebase` contains `project_id`, `api_key`, `app_id`, and `auth_domain` from the Firebase web app.
- `stripe` contains the expected TEST `account_id` and `price_id`. Use `null` when commerce is disabled and no Stripe account is needed.
- `source_sha` and `binary_sha256` bind the profile to the prepared source and binary.
- `runtime_image_id` pins the installed Python runtime by its full `sha256:` image ID.
- `enabled` defaults operationally to `false`. Set it to `true` only for an approved Stripe TEST run.

Keep `api.json`, `ingestion.json` and the optional `reconciler.json` in the runtime root's `private/` directory. The launcher checks ownership and file mode `0600` and restricts the keys each child receives. API and ingestion use fresh database, object-store and internal settings. The API alone receives its image signing key and the separately approved durable `firebase-adc.json` mount. Enabled TEST ingestion and reconciliation each receive their reviewed TEST Stripe key and signing secret in separate role files. The disabled profile rejects those Stripe secrets. PostgreSQL reads `pg-password` as UID 999. The isolated object store reads `s3-access` and `s3-secret` from private files. The migration runner uses `pgpass` for `postgres:5432` and database and user `workshop_stripe_staging`.

## Render and validate

With the exact reviewed source, binary and profile available, render the Compose manifest and check its syntax.

```sh
python3 scripts/dev/workshop_test_staging.py render --profile /absolute/reviewed-profile.json > /absolute/reviewed-compose.json
docker compose -f /absolute/reviewed-compose.json config --quiet
```

These commands work offline. The rendered manifest binds only the API to host loopback port `3043`. PostgreSQL, object storage and NATS stay on the internal network. API and private ingestion receive egress for their configured services. The six-service disabled profile requires the configured Firebase tester list and keeps commerce off. The seven-service TEST profile points all four purchase notices at the same staging origin and adds the bounded reconciliation service.

Once the HTTPS origin, Firebase settings, image and private role files are approved for runtime use, `docker compose -f /absolute/reviewed-compose.json up -d api` starts the isolated stores, applies migrations, waits for ingestion health and then starts the API. Verify `/readyz` before routing the approved HTTPS origin. The same command targets `api` in both profiles, so it leaves the reconciliation window available for the test order.

For an enabled TEST run, start reconciliation when an authorized order is ready using `docker compose -f /absolute/reviewed-compose.json run --rm payment-reconciler`. The wrapper retries pending events and schedules paid preparation as eligible for up to ten passes, with a 45-second limit per pass and a ten-minute overall budget. Check order, entitlement and source-job states independently. An authorized source worker or separately seeded fixture is needed to verify the article reader against this stack.

Run the offline regression suite with `python3 scripts/dev/test_workshop_test_staging.py`. It covers both manifest profiles, isolated files and networks, the TEST key and origin checks, environment filtering, reconciliation bounds, and rejection of altered source files. The API notice checks are in `TestWorkshopTestNotices`.
