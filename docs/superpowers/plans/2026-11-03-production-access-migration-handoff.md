# R5 post-migration planning amendment

Planning inspection: integration `1d07ce28b5cc4cb7fb95ab41db8c178eff0d3c4d`, 2026-11-03. This independently reviewed amendment is incorporated as planning only: it grants no implementation authorization, live identity certification or deployment. Implementers/reviewers remain `gpt-6.1-sol`, medium, Fast/priority, no fallback. R5 remains blocked until reviewed R3 integration, synchronized plan/task/tracking and exact-base preflight.

## Finding and decision

The shared driver from e401a54, integrated through f264dae, accepts exactly SQL001–038. Merely adding `039_production_identity_sessions.sql` causes default generation to fail before output. `SharedDriverTests.test_fixed_transaction_contract_is_audited` already requires every file numbered >=036 to contain exactly one outer BEGIN/COMMIT and its own version marker. Therefore039 must use that complete-transaction contract; do not choose a runner-wrapped alternative or edit001–038.

The driver’s no-ledger/empty-ledger safeguard enumerates known application tables. Append both new auth tables to that safeguard so an untracked auth-only database cannot be silently adopted. The lifecycle real-PostgreSQL test module has current-head assertions hardcoded to038; it must be updated together with039 while retaining explicit original038/prefix regressions.

At this exact inspection base, `compose.article-lifecycle-test.yaml` has private PostgreSQL/NATS/S3 services, a read-only source mount, an internal network and no host ports. `article-lifecycle-test.Dockerfile` has Python, PostgreSQL client and Python dependencies, but no Go toolchain. `article_lifecycle_smoke.py` currently executes Python suites only. No Go/Python acceptance runner or required Go integration flag exists at this base. The committed `docs/superpowers/plans/2026-11-03-catalog-runtime-integration.md` specifies that R3 will add Go1.26, `/opt/go-module-cache` and a `go-test-runner` service. R5 must wait for that implementation, independently verified SHA and actual tool/cache/service reinspection; it must consume that image/service without duplicating or silently diverging tooling. The R5 fixture command below freezes its own collector protocol within existing scope; its R3 service/tool bindings remain a required pre-gate reinspection, not a claim that the planned service already exists.

## Minimal additional allowed paths

Add exactly these three paths to `r5-access.json.allowed_paths`:

1. `scripts/dev/migrate_sql.sh` — reviewed039 manifest addition, complete-transaction recognition and auth-only baseline rejection.
2. `workers/ingestion-python/tests/test_article_lifecycle_migrations.py` — current-head039 acceptance and preserved historical-prefix matrix.
3. `docs/operations/migration-runner.md` — default001–039 manifest and039 transaction/recovery contract.

Existing R5 scope already includes `scripts/dev/test_migrations.py`, `db/migrations/039_production_identity_sessions.sql`, `apps/api-go/postgres_auth_sessions_test.go`, `scripts/dev/production_access_smoke.py`, `scripts/dev/test_production_access_smoke.py`, `infra/compose/compose.article-lifecycle-test.yaml`, `infra/compose/article-lifecycle-test.Dockerfile`, the identity implementation/test files and the production-access runbook. No new test file is needed. Do not add globs, edit `lifecycle_support.py`, `article_lifecycle_smoke.py`, `migration_plan.py`, `migrate.py`, historical SQL, R3’s tests/collectors or CI workflows for this amendment. The generic prefix fixture and Python migration adapter already work with the appended manifest.

Coordinator-only tracking changes accompany acceptance: synchronize the R5 plan, task `acceptance_tests` and `pre_implementation.todo`, corresponding release tracking and canonical documentation; commit and re-pin before execution. Those tracking changes are not application-builder permissions and are not made by this planning activity.

## Exact039 runner contract

- Append `039_production_identity_sessions.sql` after038 in the shell `canonical` manifest and Python test’s expected ordered filename list.
- Append `039_*` at all FOUR explicit `036_*|037_*|038_*` case sites: (1) static complete-transaction audit; (2) synthetic BEGIN suppression; (3) synthetic marker INSERT suppression; and (4) synthetic COMMIT suppression. The marker and COMMIT suppression cases are separate sites. Each becomes exactly `036_*|037_*|038_*|039_*`; do not broaden to an unchecked numeric wildcard. Static acceptance counts four matching039-inclusive sites and confirms none of the old three-pattern sites remains.
- Include `auth_login_transactions` and `auth_sessions` in `emit_known_tables_check`.
-039’s first nonblank line is `BEGIN;`, last nonblank line `COMMIT;`; exactly two standalone outer delimiters. Its own final DML before COMMIT includes `INSERT INTO schema_migrations(version) VALUES('039_production_identity_sessions') ON CONFLICT DO NOTHING;`.
- Preserve the existing advisory lock `(186,3738)`, psql flags, pre-output manifest validation, missing033 exception, marker-only provenance and legacy033 adoption behavior. No checksum/adoption redesign.
-039 creates only the two planned auth tables and their checks/indexes. Session tokens and cookie/state binding identifiers use32-byte SHA-256 values; organization IDs are UUIDs; roles are JSON arrays or text arrays validated by the selected Go store; expiry must be later than creation, with lifetime caps enforced in Go. Transaction consumption/rotation and revocation use committed PostgreSQL writes. No access/refresh/raw ID tokens are persisted. No application role needs new superuser privileges or a new billing/user table.
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
- Add populated039 restart with both a login transaction and a session, including consumed/revoked rows; compare all auth rows and ledger timestamps before/after full driver replay. Session creation/revocation behavior itself is verified by Go below.

The complete migration test module must execute with real PostgreSQL, not merely static Python unit checks. SQL001–038 must be byte-identical to this integration base and reviewed R3 base; compare `git diff <pinned-base> -- db/migrations/0{01..38}_*.sql` using a non-expanding explicit Python file list if the shell lacks brace support.

## Frozen R5 fixture executable interface

Implement the already-scoped collector CLI:

```text
python scripts/dev/production_access_smoke.py --mode fixture \
  --candidate-sha <40-character host git HEAD> --output /artifacts/r5-access.json
```

The collector requires `AUTODATA_LIFECYCLE_TEST=1`, rejects inherited BANKONE/BANKTWO/model/OIDC production configuration, uses the R3 plain-clone provenance contract: independently observe runner Git SHA/status/remotes, verify the complete mounted-input manifest plus host-before evidence and reject unavailable/mismatched observation. A supplied SHA alone cannot pass required acceptance. It runs only against the existing private fixture services, never a supplied production DSN. It sets `AUTODATA_REQUIRE_AUTH_INTEGRATION=1` for the pytest child before fixture collection and executes:

```text
python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/r5-access-migrations.xml \
  scripts/dev/test_migrations.py \
  workers/ingestion-python/tests/test_article_lifecycle_migrations.py \
  scripts/dev/test_production_access_smoke.py
```

The already-scoped `scripts/dev/test_production_access_smoke.py` retains collector unit tests and adds exactly one fixture bridge test named `test_required_postgres_auth_sessions`. Import `fresh_database` from `lifecycle_support`; no support-file modification is needed. The bridge creates one full039 database and another database through038, then launches this exact command from `/workspace/apps/api-go`:

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
```

Create both private Go cache/tmp directories before the Go child. Only the fixture bridge constructs DSNs using the existing committed fixture-only user/password and `postgres:5432`; never take these URLs from the caller’s ambient application environment. Do not print DSNs. In Go, validate required flag, lifecycle flag, host/user and `lifecycle_test_` database prefix before connecting. Missing flags/DSNs/tables in required mode fail the test; they cannot call `t.Skip`. The ordinary unit invocation may skip this integration root only outside required mode, and that skip cannot satisfy acceptance.

The Go entrypoint lives in existing-allowed `postgres_auth_sessions_test.go`. Require these exact five subtest IDs beneath `TestPostgresAuthSessionsIntegration`:

1. `OneTimeConcurrentConsume`: two independent pools/stores compete to consume one bound, unexpired login transaction; exactly one succeeds, wrong binding does not consume it and replay fails.
2. `SharedSessionRevocation`: two actual server/store instances share PostgreSQL; instanceB authenticates a session minted byA, then rejects it afterA’s committed logout/revocation.
3. `ExpiryAndPersistedSecrecy`: expired transaction/session rejection; verify persisted identity/role/hash fields and absence of raw session, raw ID/access/refresh tokens in DB rows. Query contents privately and emit only assertion outcomes.
4. `CallbackRotationAndReplay`: in-process generated-key OIDC issuer with real loopback HTTP/TLS, code+PKCE, nonce/state/binding checks, one callback acceptance, old-session revocation, cookie flags and callback replay rejection; both API instances use real PostgreSQL stores. No mocked SQL-row substitute.
5. `OidcStartupRequiresMigratedPostgres`: full039 starts with required session tables; through038, unavailable pool and memory/unset OIDC persistence each fail closed. These negative cases must not migrate or modify the038 database to make startup succeed.

Use narrow existing/new identity store methods from the R5 implementation. Atomic consumption must condition the UPDATE on matching state/cookie-binding hashes, unconsumed state and `expires_at > now`, returning one record; separate select-then-update is insufficient. Session lookup must check expiry and revocation at every authentication. External HTTP APIs remain the frozen `/auth/session`, `/auth/login`, `/auth/callback`, `/auth/logout` contracts, including local-mode401 `login_available:false` and login503. Optional API bearer stays disabled by default and its audience distinct from web client ID.

The Python bridge parses Go JSON events, requires the root and all five exact subtests to pass, rejects any skip/build/error/no-tests result and writes the JSON stream only to its isolated artifact directory. The collector requires nonzero pytest count, zero skips/failures/errors, a fresh Go-event artifact with exactly those successful subtest IDs, measured migration head039 and matching candidate SHA; a natural-language pass or process exit0 without executed subtests fails acceptance. Evidence includes argv, timing, process status, actual IDs/counts, migration-head assertion and artifact hashes, never cookies/tokens/provider bodies. Freshness is per run, not the presence of an older file.

## R3 tooling consumption and exact host invocation

Consume only the verified R3 `go-test-runner` service/image. Reinspect Go1.26, `/opt/go-module-cache`, writable tmp paths, environment flags, image provenance and module-download build steps at its actual integrated SHA before the R5 gate. R5 adds OIDC dependencies to its allowed go.mod/go.sum; rebuild the same R3-defined image so its existing module prefetch reads those candidate manifests. Do not add another Go stage, cache location, service, compiler or Dockerfile path. Required session tests run with `GOPROXY=off`, `GOTOOLCHAIN=local` and the existing internal network, with no network-enable workaround. Keep the source mounted read-only and caches under/tmp. Existing R5 full-suite race validation remains separate; this PostgreSQL collector command makes no unsupported fixture C-compiler assumption. Any missing R3 tool/cache/service binding blocks dispatch pending a separately reviewed and synchronized amendment.

After the implementation is committed and reviewed, these are the exact functional build/start/collector arguments, run by the bounded coordinator supervisor from an immutable reviewed candidate checkout. The coordinator owns a scratch `/tmp/autodata-r5-access-supervisor.py`, independently reviewed before running, which adapts R3’s supervisor phase/deadline/ownership implementation to this R5 collector command and five mandatory Go subtests (not R3’s hardcoded eight-case validator). It accepts `--source-repo`, `--candidate-sha` and exclusive-new `--run-root` as in R3. R3’s ownership, phase deadlines, source-before/after checks, retained runner/container ID, bounded stop/kill/finally handling and evidence validation apply; bare unbounded shell execution cannot certify acceptance. Use an owned plain clone with source input manifest and exact candidate provenance as that plan requires:

```sh
# Component illustration executed by the bounded supervisor, from its owned plain clone.
# The supervisor supplies candidate SHA, checkout/artifacts paths and unique project name.
r5_builder_name="$r5_project-builder"
r5_image_tag="$r5_project-go-test-runner:acceptance"
export AUTODATA_LIFECYCLE_ARTIFACT_DIR="$r5_evidence_dir"
export AUTODATA_R3_TEST_IMAGE="$r5_image_tag"
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

Add these acceptance/todo clauses to the synchronized R5 task before dispatch: “039 is accepted by the complete shared manifest and transaction audit; known untracked auth tables fail closed; historical001–038 unchanged; full039 and populated038 upgrade/restart/rollback matrix passes.” And: “The exact private fixture collector command executes real PostgreSQL session tests with the five mandatory Go IDs, required-mode failure on missing dependencies/configuration, zero skipped acceptance tests, head039 and exact candidate evidence.” Add the three allowed paths above and references to this accepted amendment’s committed repository plan text.

Reinspect after R3 merges. R3 must supply the verified Go/cache/service fixture toolchain first; consume it without duplicating layers. If its committed required-integration/tooling interface differs, the coordinator must reconcile and synchronize the exact command before R5 starts; do not silently widen scope or rely on an unavailable runner. No R5 fixture tooling modification is authorized by this amendment. This proposed scope/acceptance expansion requires independent planning review before the coordinator synchronizes it or dispatches implementation.

This planning run did not execute migrations/tests, start containers or contact external services. The real issuer/client/origin/claims/account prerequisites remain pending the existing user reply; do not re-ask. Passing generated-key issuer/PostgreSQL tests is deterministic implementation evidence only. Staging login, external-provider behavior, production secrets, real membership lifecycle and external Kubernetes migration-image compatibility retain separate acceptance gates.

## Revision history

- Initial planning artifact SHA256: `1b7115829f3b0455c77a5c255608faa01e98c40983656b93a30f62588d7886bf` (reported before independent review; retained as history, not current approval).
- Revision1 resolves independent planning findings: four separate039 transaction-dispatch sites; explicit mandatory `AUTODATA_R3_TEST_IMAGE`; uniquely owned R3-compatible buildx backend/tag with saved image-ID checks; supported Compose `run --pull never --no-deps`; bounded backend/project cleanup. Current revision awaits independent re-review and has no implementation authority.

## Independent planning approval and canonical incorporation

Independent review approved revised source SHA256 `ae28f75bcba7f7f2ae3563501eb33cee10b4155e5d6c505a3eb34a5341e1fde8` after correcting all four transaction cases and the owned image/buildx launch contract. The review and original findings remain in `/tmp/autodata-r5-postmigration-independent-review.md`. This incorporation changes status/location wording only.

Tracking: https://github.com/lucronn/autodata/issues/186 ; https://github.com/users/lucronn/projects/8

Concrete coordinator todo: verify R3 integration; reinspect its actual image/cache/service and Go bridge interfaces; reconcile this frozen R5 collector command; synchronize matching task, Issue186/Project8 and canonical docs; commit a new R5 checkpoint; require exact-base machine preflight before implementation. R5 remains blocked until those steps. The three migration-related paths are added narrowly to its task; no additional fixture-tooling changes are authorized by this amendment.
