# Firebase identity migration039 and R3 runtime handoff

**Authority:** [Firebase identity plan](2026-11-03-workshop-firebase-identity.md), exact35-path R5 task and synchronized `docs/agents/records/2026-11-03-workshop-firebase-identity.json`. Actual Issue186/Project8 amendment is confirmed; commit/re-pin this checkpoint and pass machine preflight before implementation. Execution stays gpt-6.1-sol, medium, Fast/priority, no fallback.

**Supersession:** The former OIDC login-transaction/callback inventory is historical.039 now creates customer_accounts and auth_sessions only. No PKCE transaction, client secret, callback route, optional customer bearer or15-minute session policy survives as an active requirement. Paid catalog/media enforcement is a separate synchronized lane.

**Dependency:** R3 verified integration31ffe7e, current planning root521385f. The actual R3 Dockerfile already supplies Go1.26/git/PostgreSQL client and prefetches exact candidate module manifests into /opt/go-module-cache; its go-test-runner uses private PostgreSQL/NATS/S3, internal network, read-only source and executable/tmp. Consume this actual tooling without adding fixture Dockerfile/Compose paths. Reinspect the final pinned checkpoint before execution; no live acceptance is claimed by this planning amendment.

## Finding and decision

The shared driver from e401a54, integrated through f264dae, accepts exactly SQL001–038. Merely adding `039_production_identity_sessions.sql` causes default generation to fail before output. `SharedDriverTests.test_fixed_transaction_contract_is_audited` already requires every file numbered >=036 to contain exactly one outer BEGIN/COMMIT and its own version marker. Therefore039 must use that complete-transaction contract; do not choose a runner-wrapped alternative or edit001–038.

The driver’s no-ledger/empty-ledger safeguard enumerates known application tables. Append both new auth tables to that safeguard so an untracked auth-only database cannot be silently adopted. The lifecycle real-PostgreSQL test module has current-head assertions hardcoded to038; it must be updated together with039 while retaining explicit original038/prefix regressions.

## Exact bounded ownership

The authoritative Firebase plan and r5-access task contain exactly35 paths (14 create,21 modify). Shared-runner work uses existing allowed scripts/dev/migrate_sql.sh, scripts/dev/test_migrations.py, workers/ingestion-python/tests/test_article_lifecycle_migrations.py and docs/operations/migration-runner.md. The allowed catalog integration bridge adapts039/16-table evidence and retains all eight R3 content cases. The auth collector and its existing planned test module remain scoped. No fixture Dockerfile/Compose tooling, lifecycle_support.py, production Python discovery helper, historical SQL or CI workflow modification is authorized. Production Python migration_files already discovers039 automatically.

## Exact039 runner contract

- Append `039_production_identity_sessions.sql` after038 in the shell `canonical` manifest and Python test’s expected ordered filename list.
- Append `039_*` at all FOUR explicit `036_*|037_*|038_*` case sites: (1) static complete-transaction audit; (2) synthetic BEGIN suppression; (3) synthetic marker INSERT suppression; and (4) synthetic COMMIT suppression. The marker and COMMIT suppression cases are separate sites. Each becomes exactly `036_*|037_*|038_*|039_*`; do not broaden to an unchecked numeric wildcard. Static acceptance counts four matching039-inclusive sites and confirms none of the old three-pattern sites remains.
- Include `customer_accounts` and `auth_sessions` in `emit_known_tables_check`.
- 039’s first nonblank line is `BEGIN;`, last nonblank line `COMMIT;`; exactly two standalone outer delimiters. Its own final DML before COMMIT includes `INSERT INTO schema_migrations(version) VALUES('039_production_identity_sessions') ON CONFLICT DO NOTHING;`.
- Preserve the existing advisory lock `(186,3738)`, psql flags, pre-output manifest validation, missing033 exception, marker-only provenance and legacy033 adoption behavior. No checksum/adoption redesign.
- 039 creates only customer_accounts and auth_sessions with the exact constraints in the Firebase plan: unique project+UID, generated account/personal-org UUIDs, active/blocked status,32-byte session hash, account FK, positive verified auth_time, expires_at after creation and at most12hours, nullable revoked_at, account/expiry indexes. No role/org authority is copied from customer tokens. Atomic account provisioning/session rotation/revocation uses committed PostgreSQL writes; failed rotation preserves the old session. No raw Firebase/app token or credential is persisted, and no checkout/grant table or application superuser privilege is added.
- Update the runbook to001–039, with036–039 self-contained transactions; retain the statement that historical001–038 bytes are immutable and Kubernetes external migration-image certification remains separately blocked.

## Migration acceptance updates

Use current-head filenames derived from the actual canonical files where a test means “all migrations”; keep literal038 where the test deliberately represents historical038. Do not replace every38 blindly.

In `scripts/dev/test_migrations.py`, append039 to the expected filename list. Add static assertions that039 has the audited complete transaction and marker, and emitted SQL inserts039 exactly once with no nested transaction wrappers. Add fail-before-output tests for a missing/renamed039 in the default manifest and for malformed039 BEGIN/COMMIT/marker. Existing unsafe-name/symlink/backslash/prefix and transaction audit tests must remain.

In `test_article_lifecycle_migrations.py`:

- Full restart now skips39 and preserves complete schema, rows and every ledger timestamp. Fresh complete bootstrap records39 markers. Known-table rejection includes each auth table with an absent or empty ledger.
- Genuine036 upgrade expects033 adoption,037,038,039 and matches a fresh039 schema while preserving legacy job identity/status/retry links. A037 restart applies038 and039; rename the test to describe both. A recorded001 path applies38 remaining versions; its connection-death recovery also applies38.
- Current-head native adapter, full-chain concurrency and marker-count assertions use39. Concurrency’s copied complete fixture must include039 so both participants actually run the same full chain. Preserve advisory-wait proof and once-only application assertions.
- Extend failure/rollback parameterization with039. Inject failure before039’s version marker inside its own transaction; assert both auth tables and marker roll back, earlier038 ledger/schema/data remain, and corrected039 retry applies once then skips.
- Preserve `raw_chain(... through=38)` as historical setup. Keep the original038/markerless033 schema-preservation test explicitly running a copied canonical prefix through038; this preserves its original assertion rather than comparing a pre039 schema with a post039 schema. Add a separate populated038→039 test asserting only039 applies, existing application rows/ledger timestamps are unchanged, new auth objects exist, and the full rerun is a no-op. Existing explicit prefix038 markerless033 failure test remains prefix038.
- Add populated039 restart with customer accounts and active/expired/revoked sessions, including a blocked account; compare all auth rows and ledger timestamps before/after full driver replay. Session creation/revocation behavior itself is verified by Go below.

The complete migration test module must execute with real PostgreSQL, not merely static Python unit checks. SQL001–038 must be byte-identical to this integration base and reviewed R3 base; compare `git diff <pinned-base> -- db/migrations/0{01..38}_*.sql` using a non-expanding explicit Python file list if the shell lacks brace support.

## Frozen R5 fixture executable interface

Implement the already-scoped collector CLI:

```text
python scripts/dev/production_access_smoke.py --mode fixture \
  --candidate-sha <40-character host git HEAD> --output /artifacts/r5-access.json
```

The collector requires `AUTODATA_LIFECYCLE_TEST=1`, rejects inherited BANKONE/BANKTWO/model/Firebase/Google-credential/production database configuration, uses the R3 plain-clone provenance contract: independently observe runner Git SHA/status/remotes, verify the complete mounted-input manifest plus host-before evidence and reject unavailable/mismatched observation. A supplied SHA alone cannot pass required acceptance. It runs only against the existing private fixture services, never a supplied production DSN. It sets `AUTODATA_REQUIRE_AUTH_INTEGRATION=1` for the pytest child before fixture collection and executes:

```text
python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/r5-access-migrations.xml \
  scripts/dev/test_migrations.py \
  workers/ingestion-python/tests/test_article_lifecycle_migrations.py \
  scripts/dev/test_production_access_smoke.py
```

The already-scoped `scripts/dev/test_production_access_smoke.py` retains collector unit tests and adds exactly one fixture bridge test named `test_required_postgres_auth_sessions`; this preserves collection by the frozen command. The separately allowed catalog bridge owns039/auth-table adaptation for the eight R3 cases. Import `fresh_database` from `lifecycle_support`; no support-file modification is needed. The bridge creates one full039 database and another database through038, then launches this exact command from `/workspace/apps/api-go`:

```text
go test -json -count=1 -run '^TestPostgresAuthSessionsIntegration$' .
```

Set only generated test configuration for the child:

```text
AUTODATA_REQUIRE_AUTH_INTEGRATION=1
AUTODATA_LIFECYCLE_TEST=1
AUTODATA_AUTH_TEST_DATABASE_URL=<DSN for fresh lifecycle_test_<uuid> database>
AUTODATA_AUTH_TEST_UNMIGRATED_DATABASE_URL=<DSN for separate through038 fixture>
GOCACHE=/tmp/autodata-r5-go-cache
GOTMPDIR=/tmp/autodata-r5-go-tmp
GOMODCACHE=/opt/go-module-cache
GOPROXY=off
GOTOOLCHAIN=local
GOFLAGS=-mod=readonly
CGO_ENABLED=0
```

Create both private Go cache/tmp directories before the Go child. Only the fixture bridge constructs DSNs using the existing committed fixture-only user/password and `postgres:5432`; never take these URLs from the caller’s ambient application environment. Do not print DSNs. In Go, validate required flag, lifecycle flag, host/user and `lifecycle_test_` database prefix before connecting. Missing flags/DSNs/tables in required mode fail the test; they cannot call `t.Skip`. The ordinary unit invocation may skip this integration root only outside required mode, and that skip cannot satisfy acceptance.

The Go entrypoint lives in existing-allowed `postgres_auth_sessions_test.go`. Require these exact five subtest IDs beneath `TestPostgresAuthSessionsIntegration`:

1. `ConcurrentCustomerProvisionAndRotation`: two independent pools concurrently provision the same project+UID; exactly one account/personal org survives; sessions reference that account; a committed rotation revokes the old cookie; rollback leaves old session valid and no orphan new row. Different project/UID cannot adopt its account.
2. `SharedSessionRevocation`: two actual API/store instances sharing PostgreSQL; B accepts A's session, then rejects after A's logout commit or account block. No fake SQL rows.
3. `ExpiryAndPersistedSecrecy`: expiry boundary/absolute lifetime, hashed32-byte token, allowed identity fields, no raw Firebase/app tokens in persisted rows; stable account survives expiry and restart. Emit assertion outcomes only.
4. `FirebaseExchangeAndUserRevocation`: run real exchange/session HTTP handlers with real PostgreSQL and the actual SDK using the local certificate/user transport; fresh Google token creates session, old app cookie rotates, altered/wrong-project token fails, live fixture user disabled/revoked denies subsequent protected request, lookup outage returns503 with no stale acceptance. Same still-fresh valid ID token re-exchange is allowed; do not mislabel it a failed callback replay.
5. `FirebaseStartupRequiresMigratedPostgres`: full039 starts;038/unavailable pool/memory or missing persistence fail; never auto-migrate the038 database. Local mode remains explicit login-unavailable with no created account/session.

Use official Firebase Admin SDK verification with the serial local generated-RS256 certificate/user fixture transport specified by the authoritative plan, not a custom JWT parser or emulator. Reject FIREBASE_AUTH_EMULATOR_HOST at startup; no actual project or ambient credential is needed in deterministic fixtures. The SDK checks iat revocation; additionally check verified auth_time before exchange commit and every protected request. Current account/session state, no positive Firebase-user cache, two-second total context and sanitized401/403/503 apply. Fresh valid Firebase tokens can be re-exchanged; do not restore callback one-time consumption. External HTTP APIs are /auth/config, /auth/firebase/session, /auth/session and /auth/logout with exact origin/exchange/CSRF/no-store behavior and explicit local unavailability. Ordinary Firebase-mode customer APIs reject Authorization bearer presence.

The Python bridge parses Go JSON events, requires the root and all five exact subtests to pass, rejects any skip/build/error/no-tests result and writes the JSON stream only to its isolated artifact directory. The collector requires nonzero pytest count, zero skips/failures/errors, a fresh Go-event artifact with exactly those successful subtest IDs, measured migration head039 and matching candidate SHA; a natural-language pass or process exit0 without executed subtests fails acceptance. Evidence includes argv, timing, process status, actual IDs/counts, migration-head assertion and artifact hashes, never cookies/tokens/provider bodies. Freshness is per run, not the presence of an older file.

## R3 tooling consumption and exact host invocation

Consume only the verified R3 `go-test-runner` service/image. Reinspect Go1.26, `/opt/go-module-cache`, writable tmp paths, environment flags, image provenance and module-download build steps at its actual integrated SHA before the R5 gate. R5 adds the pinned official Firebase SDK dependencies to its allowed go.mod/go.sum; rebuild the same R3-defined image so its existing module prefetch reads those candidate manifests. Do not add another Go stage, cache location, service, compiler or Dockerfile path. Required session tests run with `GOPROXY=off`, `GOTOOLCHAIN=local` and the existing internal network, with no network-enable workaround. Keep the source mounted read-only and caches under/tmp. Existing R5 full-suite race validation remains separate; this PostgreSQL collector command makes no unsupported fixture C-compiler assumption. Any missing R3 tool/cache/service binding blocks dispatch pending a separately reviewed and synchronized amendment.

After the implementation is committed and reviewed, these are the exact functional build/start/collector arguments, run by the bounded coordinator supervisor from an immutable reviewed candidate checkout. The coordinator owns a scratch `/tmp/autodata-r5-access-supervisor.py`, independently reviewed before running, which adapts R3’s supervisor phase/deadline/ownership implementation to this R5 collector command and five mandatory Go subtests (not R3’s hardcoded eight-case validator). It accepts `--source-repo`, `--candidate-sha` and exclusive-new `--run-root` as in R3. R3’s ownership, phase deadlines, source-before/after checks, retained runner/container ID, bounded stop/kill/finally handling and evidence validation apply; bare unbounded shell execution cannot certify acceptance. Use an owned plain clone with source input manifest and exact candidate provenance as that plan requires:

```sh
# Component illustration executed by the bounded supervisor, from its owned plain clone.
# The supervisor supplies candidate SHA, checkout/artifacts paths and unique project name.
r5_builder_name="$r5_project-builder"
r5_image_tag="$r5_project-go-test-runner:acceptance"
export AUTODATA_LIFECYCLE_ARTIFACT_DIR="$r5_evidence_dir"
export AUTODATA_R3_TEST_IMAGE="$r5_image_tag"
export AUTODATA_R3_CANDIDATE_SHA="$r5_candidate_sha"
docker buildx create --name "$r5_builder_name" --driver docker-container
docker buildx inspect "$r5_builder_name" --bootstrap
docker buildx build --builder "$r5_builder_name" --load --tag "$r5_image_tag" --file "$r5_checkout_dir/infra/compose/article-lifecycle-test.Dockerfile" "$r5_checkout_dir"
docker image inspect "$r5_image_tag"
docker compose -p "$r5_project" -f infra/compose/compose.article-lifecycle-test.yaml config --format json
docker compose -p "$r5_project" -f infra/compose/compose.article-lifecycle-test.yaml up -d --wait --wait-timeout 150 postgres nats minio
docker compose -p "$r5_project" -f infra/compose/compose.article-lifecycle-test.yaml run -d --pull never --no-deps --name "$r5_project-runner" go-test-runner python scripts/dev/production_access_smoke.py --mode fixture --candidate-sha "$r5_candidate_sha" --output /artifacts/r5-access.json
```

Before these component commands, the supervisor refuses any preexisting exact builder/backend name, project-labelled container, runner name or image tag and records its unique ownership token. Record the new builder node and exact `buildx_buildkit_<builder_name>0` backend ID after bounded bootstrap. The explicit owned buildx phase must succeed within R3’s build deadline; no `docker compose build` or shared-builder fallback is permitted. Save the built image ID from `docker image inspect`, require resolved `go-test-runner.image` to equal `AUTODATA_R3_TEST_IMAGE`, and after start require the runner’s inspected Image ID to equal that saved ID. Missing image, an implicit build/pull, service/image mismatch or unsupported required flag is failure. `--no-deps` prevents a one-off runner from starting additional services after the bounded explicit service-start phase.

The detached run command only dispatches work; success requires the actual owned runner to exit0 within the R3-plan container deadline1320s, fresh complete artifacts and all measured checks above. Retain its exact container ID, verify image/name/project labels, retain logs/inspect and inspect the measured collector output before claiming success. Do not use `--no-build`: installed Compose2.40.3 does not support that run flag. Use the owned buildx flow above first and omit `--build` on run; require the supported `--pull never --no-deps` arguments. The image is built for the exact candidate manifests; a missing image/pull fallback fails provenance validation. Clean up only the uniquely owned project after retaining evidence:

```sh
docker compose -p "$r5_project" -f infra/compose/compose.article-lifecycle-test.yaml down --volumes --remove-orphans --timeout 5
docker buildx rm "$r5_builder_name"
```

Cleanup first captures logs/inspect/artifacts, verifies exclusive project ownership before `--remove-orphans`, and bounds each CLI call. On timeout stop/kill only the saved owned runner and newly created backend IDs, confirm stopped state, remove the owned builder and preserve primary plus cleanup failures; never stop a shared builder. Remove the unique fixture image only after saving its image-ID provenance and confirming the tag still points to that owned image.

No host test credentials are required. Run each step only after its predecessor succeeds; preserve failure artifacts and perform owned-project cleanup on failure too. The collector command becomes executable only after the authorized R5 files are implemented; it is a frozen acceptance specification, not a claim that this currently absent script/test exists.

## Coordinator acceptance and caveats

The task's concrete acceptance/todo must match the Firebase plan and exact five IDs above, preserve the full039/038 migration matrix and all eight R3 content cases, and require measured candidate/input/Git provenance, zero skips and no stale artifacts. Adapt R3 catalog bridge evidence from001_038 to001_039 and include customer_accounts/auth_sessions alongside the original14 tables. The scratch R3 regression validator needs separately reviewed039 adaptation; the R5 supervisor separately validates its five new tests. Neither is approved by this document.

Root must confirm amended real tracking, finalize the actual integrated tool/cache/service bindings, commit/re-pin and require exact-base preflight before dispatch. Tracking is synchronized; only a committed exact-base machine preflight authorizes dispatch. Real Firebase project/provider/domain/IAM configuration, live staging sign-in/revocation/two-replica/TLS checks and separately gated commerce/media enforcement remain release prerequisites. No containers, migrations, provider calls or implementation are run by this planning update.

## Historical amendment evidence (superseded identity inventory)

The pre-Firebase handoff is retained in Git blob `7451ed4339a7da953e9570bb281a7a856d372dd0`. Its transaction-dispatch, owned buildx/image provenance and bounded cleanup reasoning remains relevant; its OIDC tables, protocol, callbacks, test IDs and wider fixture path permissions are superseded. The following old planning hashes/approval are historical evidence only and do not authorize this amended Firebase task.

## Revision history

- Initial planning artifact SHA256: `1b7115829f3b0455c77a5c255608faa01e98c40983656b93a30f62588d7886bf` (reported before independent review; retained as history, not current approval).
- Revision1 resolves independent planning findings: four separate039 transaction-dispatch sites; explicit mandatory `AUTODATA_R3_TEST_IMAGE`; uniquely owned R3-compatible buildx backend/tag with saved image-ID checks; supported Compose `run --pull never --no-deps`; bounded backend/project cleanup. That historical revision awaited independent re-review and had no implementation authority.

## Historical independent planning approval and canonical incorporation

Independent review approved revised source SHA256 `ae28f75bcba7f7f2ae3563501eb33cee10b4155e5d6c505a3eb34a5341e1fde8` after correcting all four transaction cases and the owned image/buildx launch contract. The review and original findings remain in `/tmp/autodata-r5-postmigration-independent-review.md`. That historical incorporation changed status/location wording only.

Tracking: https://github.com/lucronn/autodata/issues/186 ; https://github.com/users/lucronn/projects/8

Historical coordinator todo (replaced by the synchronized Firebase record): verify R3 integration; reinspect its actual image/cache/service and Go bridge interfaces; reconcile this frozen R5 collector command; synchronize matching task, Issue186/Project8 and canonical docs; commit a new R5 checkpoint; require exact-base machine preflight before implementation. R5 remains blocked until those steps. The three migration-related paths are added narrowly to its task; no additional fixture-tooling changes are authorized by this amendment.
