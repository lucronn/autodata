# R3 Runtime Integration Handoff Refinement Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after the repository gate passes at the new committed R3 checkpoint. This independently reviewed handoff remains blocked until the migration dependency is verified and a fresh R3 checkpoint passes preflight.

**Goal:** Certify the actual Go catalog handler → R2 internal HTTP durable scheduling → real worker → PostgreSQL/S3 publication path, including readable source during a blocked model HTTP response and zero warm scheduling/provider/model calls.

**Architecture:** A Python bridge owns an isolated R2 LifecycleRuntime and loopback servers. Named Go tests use real PostgreSQL and real HTTPIngestionClient through the production handler. Test-owned model proxy/control code lives entirely in the already authorized Python integration file; it neither replaces scheduling nor adds an application runtime API.

**Tech Stack:** Existing Python3.14 fixture image, Go1.26, pgvector/PG17, SeaweedFS S3, NATS JetStream, psycopg, pytest, Go JSON test events.

**Spec:** docs/superpowers/specs/2026-11-03-source-fallback-web-design.md
**Plan to refine:** docs/superpowers/plans/2026-11-03-source-fallback-web.md, section “R3 isolated Go/Python verification boundary” and Tasks1–3.
**Tracking:** https://github.com/lucronn/autodata/issues/186 ; https://github.com/users/lucronn/projects/8
**R2 inspected candidate:** dba2d96170db5694052bd36dc7fca645fdf0a51d, independently approved by coordinator. All R2 API descriptions below were read using git show at that exact SHA, not from another agent's worktree.
**Status:** independently reviewed planning refinement; R3 remains blocked until verified R2 and migration-runner integration, tracking/document synchronization, committed checkpoint and fresh exact-base preflight. Existing r3-fallback-api.json has32 allowed paths and status blocked. This document does not change either.

## Constraints and concrete todo

- [ ] Coordinator integrates verified R2 and independently reviewed migration replay implementation, preserving historical037/038 SQL and helper APIs.
- [ ] Coordinator incorporates this refinement in the canonical R3 plan, synchronizes Issue186/Project8/canonical documents/task, commits and pins a new R3 base, and retains passing machine preflight output.
- [ ] Builder extends only the existing fixture Compose/Dockerfile and creates the Python/Go integration files inside R3's existing32 paths.
- [ ] Builder writes and observes the named lifecycle integration tests fail before implementing R3 behavior, then makes them pass against actual R2 HTTP/worker/migrations.
- [ ] Required acceptance validates executed test identities, exits, counters, snapshots and migration provenance; missing infrastructure or skipped/zero Go coverage fails.
- [ ] Independent exact-SHA review and repeat required acceptance precede any R3 completion statement.

Execution/review profile remains gpt-6.1-sol / medium / Fast(priority), no fallback. No provider-agent spawn, live banks, host credentials, deployment, new runtime test hook, changes to R2 source/helpers, production Compose or CI workflow are authorized by this refinement.

## Verified R2 bindings

These signatures are existing code at the candidate, not proposed APIs:

- `from lifecycle_support import fresh_database, LifecycleRuntime`. Import the pytest fixture into the new test module. `fresh_database` yields a callable accepting `through=None`; `fresh_database(through=0)` creates an empty `lifecycle_test_<uuidhex>` and returns `Repository(database_name)`. Required R3 acceptance uses that empty database and the explicit captured shared-driver recipe in the post-migration refinement below. `Repository.connect()` accepts only AUTODATA_LIFECYCLE_TEST=1 and that prefix, and hardcodes postgres/lifecycle_test/lifecycle_test_only. The migrated helper delegates chain execution to shared migrate_sql.sh. Do not substitute raw SQL loops or claim the helper retained its internally captured first-application output.
- `LifecycleRuntime(repo, stack)` receives a contextlib.ExitStack. It starts `serve_connector('bankone')`, `serve_connector('banktwo')`, `serve_model()`, creates real S3 bucket `lifecycle-<uuidhex>`, seeds one vehicle, executes both real catalog-index jobs and exposes `vehicle`, `articles[provider]`, `article_id`, `repo`, `registry`, `objects`, `bucket`, `servers`, `model`, and `env`. Both descriptors deliberately use provider-local `same/article` but retain different canonical UUIDs/provider identity. Existing source fixture body is `<ol><li>Remove the pump.</li></ol>`.
- Set `runtime.article_id = runtime.articles[provider]` before scenario setup. `runtime.start_workers(count=2)` launches actual scripts/dev/article_worker.py processes unless an explicit R2 barrier is installed. Use ordinary workers for this harness, not monkeypatched worker entrypoints. `stop_workers()`, `read_current()`, `await_publication()`, `wait_for(predicate)`, `record_evidence(test_id)`, `close()` are available. The existing wait_for deadline is10s and checks early CLI worker exit.
- `runtime.env` is explicit and passed to worker processes. Set only its existing `INCEPTION_API_BASE_URL` to the model proxy `/v1` URL and `INCEPTION_API_TIMEOUT_SECONDS` to `60` before starting workers. This is per-test fixture composition, not a helper edit. Fixture API key remains `fixture-model`.
- `runtime.pause('after_model_dispatch')` fires after the durable dispatch marker but BEFORE `rewrite_ordered_document` calls the model. It cannot prove a model HTTP request arrived. Do not use it for this acceptance claim.
- `serve_model()` exposes `.url` ending `/v1`, `.calls`, `.mode`, `.delay`, `.prompts`. There is no block/release Event. Keep `.mode='valid'`, `.delay=0`. Model emits “Take off the pump.” for the fixture's “Remove the pump.” prompt.
- `runtime.ensure()` invokes source_job_persistence directly; `ingest_to_publication()` also calls that direct method. Neither is permissible as the scheduling trigger for the required R3 HTTP scenarios. Setup may use the constructor's real catalog-index work, but all subsequent article scheduling must enter `/v1/catalog/ensure` via the actual Go client/handler.
- `http_service.make_handler(internal_token='fixture-r3-internal')` produces the real ingestion HTTP handler. Its `do_POST` calls the real dispatch_request → catalog_service.ensure_catalog_hydration → `_ensure_lifecycle_catalog`. Do not replace dispatch_request, supply a fake catalog_runner, or call private scheduling helpers instead.
- Actual article scheduling JSON requires nonempty idempotency_key, scope='article', vehicle_id=runtime.vehicle, canonical_article_id=runtime.article_id (article_id is an accepted alternative). Optional provider/source_vehicle_ref/source_article_ref only narrow identity and must match. The default runtime descriptors are unconfigured (vehicle_configuration_id NULL), so omit that field; preserve the actual requested route scope. Do not invent a configuration UUID or translate the request through unrelated legacy configuration rows. Scoped identities remain covered by R3's scope tests.
- Successful internal acknowledgment fields are job_id, state, canonical_article_id, source_revision_id, retry_after_seconds. Cold accepted=202; an existing source/canonical result can be200; review/dead-letter=409; scheduling unavailable=503. Internal state maps pending→queued, dead_letter→failed, processing→the durable phase. Completion comes from a final PG read, never HTTP200 alone.
- Existing Go bindings are verified at the R2 candidate. Constructor: `func NewHTTPIngestionClient(baseURL, token string, timeout time.Duration) (*HTTPIngestionClient, error)`. The method belongs to the returned client, not the constructor: `func (c *HTTPIngestionClient) Do(incoming *http.Request, path string, body []byte, idempotencyKey string) (int, []byte, error)`. There is no public Ensure/Schedule method. Check constructor errors, then use the actual returned client's Do method for deliberate internal HTTP races. This valid Go setup uses existing test-only authentication while keeping database, handlers, HTTP client and worker real:

```go
pool, err := pgxpool.New(ctx, fixtureDSN)
if err != nil { t.Fatal(err) }
if err := pool.Ping(ctx); err != nil { t.Fatal(err) }
t.Cleanup(pool.Close)
store := newPostgresCatalogStore(pool)
server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
    principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
}, newMemoryRequestStore(), store)
client, err := NewHTTPIngestionClient(ensureURL, "fixture-r3-internal", 2*time.Second)
if err != nil { t.Fatal(err) }
server.ingestionClient = client
api := httptest.NewServer(server.Handler())
t.Cleanup(api.Close)
// payloadBytes is encoded actual scheduling JSON and incoming has a bounded context.
status, responseBytes, err := client.Do(incoming, "/v1/catalog/ensure", payloadBytes, idempotencyKey)
```

Create two Server/httptest server instances sharing the same actual PG pool for cold races. The returned client method executes POST and forwards the fixture internal token; do not call the private newInternalRequest method or invent a public scheduling helper.
- Public paths are `/v1/catalog/vehicles/{vehicle_id}/articles`, detail suffix `/{article_id}`, source suffix `/{article_id}/source`; source JSON uses Accept: application/json. Source revision query is the planned `source_revision_id`; alternatively follow the exact source_review URL generated by the implemented R3 DTO and assert it pins the captured revision.

## Changes within existing R3 ownership

1. `infra/compose/article-lifecycle-test.Dockerfile`: preserve migration repair's postgresql-client and existing Python/OCR dependencies. Add a Go1.26 toolchain stage and copy /usr/local/go to the Python runner; add it to PATH. Copy Go api and local contracts module manifests at build time and run module download with both local module directory relationships intact. Prefetch all required modules before the internal runtime network. Keep the checkout source bind mounted read-only at runtime; do not bake stale application source into the running command. Preserve existing test-runner behavior.
2. `infra/compose/compose.article-lifecycle-test.yaml`: add go-test-runner using this image, working_dir /workspace, same internal lifecycle network, existing private services/volumes, read-only `/workspace` and explicit `/artifacts`. Keep the image's existing user identity and default home path unchanged. Do not assign, relocate or repurpose HOME in Compose, shell setup or subprocess env. Use private writable `/tmp` paths explicitly for GOCACHE, GOTMPDIR and Python temporary data; use a prepopulated read-only Go module cache from the image. If the image's existing default home needs writable storage, mount private storage at that same existing path with matching ownership; never select another home or expose host home contents. Set GOTOOLCHAIN=local and GOPROXY=off at runtime to expose missing build-time dependencies. No published ports or credential mounts. Health dependencies or explicit bounded probes must start PG/NATS/S3; Compose run alone is not proof services are ready.
3. `workers/ingestion-python/tests/test_catalog_api_integration.py`: owns loopback ensure server/counters, model proxy/Event, control server, fixture setup/cleanup, exact Go subprocess invocation and JSON/evidence validation. No new helper files.
4. `apps/api-go/postgres_catalog_lifecycle_test.go`: owns required-env guard, strict DSN validation, actual PG pool, two actual Go HTTP servers, control client, named assertions and public DTO consistency checks. No production test route.

All model/control/ensure servers bind 127.0.0.1:0 and run on ThreadingHTTPServer threads in the same go-test-runner container as Python and Go. Container-to-loopback access therefore works without host networking.

## Test-owned proxy and control composition

Define context managers/classes in the new Python integration file only. Use an ExitStack. The Python control server is distinct from the ingestion and model servers. All control responses are bounded safe JSON and no source prompts/credentials are recorded in general logs.

The ingestion counting handler subclasses `make_handler(internal_token='fixture-r3-internal')`. Override do_POST only to count `/v1/catalog/ensure`, then call `super().do_POST()` unchanged. Under one lock record monotonic entered/active/max_active/completed counters and request scopes; classify source/article ensures versus list scopes. Increment completed in finally. Do not treat runtime.counters()['schedule'] as this count. Health probes are not ensures.

The model proxy accepts only POST `/v1/chat/completions`, bounds Content-Length, and forwards the exact request bytes and content/auth headers to `runtime.model.url + '/chat/completions'` with redirects disabled and explicit timeout. Upstream is an immutable closure URL validated as loopback, never supplied by the caller. After the upstream response has been fully read, require status200, increment upstream_completed and set `response_captured` Event. Then wait for a separate `release_response` Event before sending status/headers/body back to the real worker connection. While holding, expose downstream_waiting=1 and downstream_completed=0. Record a monotonic event trace: request_received, upstream_completed, response_held, release_requested, downstream_completed. Do not return model payloads from control endpoints.

This proves the actual worker's model HTTP operation is in flight: the proxy received its request, the actual R2 serve_model handled it (model.calls==1), and the worker has received no model response. The upstream fixture has already completed its part; describe the evidence as “worker model HTTP response held after actual model execution,” not “serve_model itself blocked on an Event.” This deliberately retains the existing R2 model implementation.

Each proxy wait has a25s timeout that records a harness failure and returns502; worker timeout60s exceeds the whole held interval. Tests keep held work below15s. Go has a90s test timeout, Python subprocess120s. Cleanup unconditionally sets release_response before stopping workers and shutting servers down, so a failed assertion cannot strand a response thread. A timeout or broken connection is a failed scenario, never a release fallback. Counters/events are thread-safe.

Test-only loopback control routes (implemented only in the Python test module):

- GET `/r3-fixture/snapshot`: counters, selected immutable IDs, safe DB state, proxy flags/events, worker process status. Does not mutate/reset anything.
- POST `/r3-fixture/start-workers`: exactly once invokes runtime.start_workers(2), or runtime.start_workers(1) for the Python-parametrized atomic scenario whose existing inside_publication barrier was installed before Go starts; rejects duplicate starts. Runtime must already have the proxy URL/timeout env set. The scenario is an immutable bridge parameter, not arbitrary control-request code.
- GET `/r3-fixture/model-held`: immediate JSON with captured/waiting/completed/error booleans; Go polls with a deadline, not an indefinitely blocked control request.
- POST `/r3-fixture/release-model`: sets the response release Event, idempotently; rejection/failure is fatal.
- GET `/r3-fixture/publication`: immediate safe load_article_state result metadata and database counts; Go polls with a deadline.
- GET `/r3-fixture/publication-barrier`: only in the atomic scenario, returns runtime.barrier[1].is_set() immediately. POST `/r3-fixture/release-publication`: only there, calls existing runtime.release('inside_publication'). Go polls and releases through these routes; no blocking await_barrier call occupies a control request. Cleanup also releases this Event before stopping its hooked worker.

Control calls require `X-R3-Fixture-Token` with a new per-runtime random fixture token (not a platform secret). Reject unexpected paths/methods/body and foreign origin targets; disable client redirects. No exposed ports and no invocation of these routes from production Go code. The Go tests call these routes directly as orchestration helpers.

For atomic-publication testing use existing R2 hook composition without modifying it: in that scenario only, runtime.pause('inside_publication'), start_workers(1), await_barrier(), then release('inside_publication') through control. The existing hook waits10s; perform precommit checks promptly and release within that bound. This barrier proves the transaction has not committed, not that an HTTP model request is blocked. Use the existing inside_publication hook for deterministic precommit evidence and one observer request in a separate connection. Timing alone around proxy release does not establish observation of a partially executed SQL transaction and cannot substitute for this atomic-publication case. Keep model-response blocking in its separate ordinary-worker test.

## Environment, isolation and provenance

Compose go-test-runner sets `AUTODATA_LIFECYCLE_TEST=1`, `AUTODATA_CATALOG_INTEGRATION_REQUIRED=1`, PYTHONDONTWRITEBYTECODE=1 and the existing PYTHONPATH roots. It does not load any env_file. The bridge validates required flag and lifecycle flag before requesting fresh_database; missing flag under the required run fails collection/setup before any fixture can pytest.skip. Ordinary broad suites may explicitly skip this module only when required mode was not requested; that result cannot certify this acceptance.

Python creates a fresh database/runtime for EACH (named Go case, provider) pair, using pytest parametrization. It applies only runtime.env's explicit keys to actual `os.environ` for the duration of the ingestion HTTP thread using monkeypatch.setenv; it does not clear the environment or rewrite the image's existing HOME. Workers receive the existing R2 helper's explicit environment separately. Do not mutate env while a previous runtime is alive. Run cases sequentially, no pytest-xdist/t.Parallel.

Go receives only explicit fixture env plus necessary toolchain/cache variables; preserve the image-provided HOME value unchanged when present in the runner environment, and do not synthesize or rewrite it:

```
AUTODATA_CATALOG_INTEGRATION_REQUIRED=1
AUTODATA_LIFECYCLE_TEST=1
AUTODATA_CATALOG_TEST_DSN=postgres://lifecycle_test:lifecycle_test_only@postgres:5432/lifecycle_test_<32hex>?sslmode=disable
AUTODATA_CATALOG_TEST_ENSURE_URL=http://127.0.0.1:<ephemeral>
AUTODATA_CATALOG_TEST_CONTROL_URL=http://127.0.0.1:<ephemeral>
AUTODATA_CATALOG_TEST_CONTROL_TOKEN=<ephemeral fixture token>
AUTODATA_CATALOG_TEST_VEHICLE_ID=<runtime.vehicle>
AUTODATA_CATALOG_TEST_ARTICLE_ID=<runtime.articles[provider]>
AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=<runtime.articles[other provider]>
AUTODATA_CATALOG_TEST_PROVIDER=bankone|banktwo
AUTODATA_CATALOG_TEST_CANDIDATE_SHA=<coordinator-host observed candidate SHA, verified against input manifest>
GOTOOLCHAIN=local
GOPROXY=off
GOMODCACHE=/opt/go-module-cache
GOCACHE=/tmp/go-cache
GOTMPDIR=/tmp/go-tmp
```

Use explicit subprocess env, preserving only the existing image HOME without assignment to a new path; strip DATABASE_URL, PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD/PGSERVICE/PGSERVICEFILE/PGPASSFILE and all host/provider/model secrets. Do not use DSN fallback. Parse DSN in both languages; require host postgres, port5432, user lifecycle_test, fixture-only password, database matching `^lifecycle_test_[0-9a-f]{32}$`, sslmode=disable, no additional credential or connection-routing parameters. Go URLs must be plain http loopback with no userinfo/query/fragment and expected ports. Pass the internal fixture token as a fixed test-only literal to NewHTTPIngestionClient; it is not a host/platform credential. Validate UUIDs and provider enum. Do not log full DSN/token. Required mode uses t.Fatal on any missing/invalid value or unavailable service, never t.Skip.

Before Go, require `server_version_num` in PG17 range, database/user matching fixture, S3 put/read/delete round trip inside runtime.bucket, and NATS JetStream account_info over nats://nats:4222. Probe with bounded deadlines; a compose healthcheck alone is insufficient. R3's NATS check establishes a real required dependency; R2's separate outbox suite certifies delivery semantics, which this suite must not claim from account_info.

### Exact candidate provenance and mounted-input identity

Do not assume a managed linked worktree's `.git` is usable inside `/workspace`: its gitdir can point outside the container. A candidate SHA environment variable is a coordinator assertion, never independent runner Git evidence.

Required certification uses a coordinator-owned disposable **plain clone** created from the clean committed implementation candidate after preflight/review, outside the development worktree. It has its own readable `.git` directory; remove its origin before running, mount no host Git config, auth, credential helper or agent socket, and run no fetch/push. Its application checkout remains read-only in the runner. This clone is an acceptance artifact, adds no repository paths, and does not expand the existing32path implementation scope. The coordinator owns creation, before/after observation and cleanup; Python bridge owns in-container comparison. Do not create the clone or run these commands during this planning task.

Invoke from the coordinator's chosen committed candidate checkout (not another agent's active worktree). Shell variables below are task-specific and exported only to convey nonsecret artifact/source identity; no HOME or global Git config changes:

```sh
export AUTODATA_R3_SOURCE_REPO="$(pwd -P)"
export AUTODATA_R3_CANDIDATE_SHA="$(git -C "$AUTODATA_R3_SOURCE_REPO" rev-parse HEAD)"
export AUTODATA_R3_ACCEPTANCE_ROOT="$(mktemp -d /tmp/autodata-r3-acceptance.XXXXXX)"
mkdir -p "$AUTODATA_R3_ACCEPTANCE_ROOT/artifacts"
git -C "$AUTODATA_R3_SOURCE_REPO" status --porcelain=v1 --untracked-files=all > "$AUTODATA_R3_ACCEPTANCE_ROOT/artifacts/source-before.status"
test ! -s "$AUTODATA_R3_ACCEPTANCE_ROOT/artifacts/source-before.status"
git clone --no-hardlinks --no-checkout "$AUTODATA_R3_SOURCE_REPO" "$AUTODATA_R3_ACCEPTANCE_ROOT/checkout"
git -C "$AUTODATA_R3_ACCEPTANCE_ROOT/checkout" remote remove origin
git -C "$AUTODATA_R3_ACCEPTANCE_ROOT/checkout" -c core.hooksPath=/dev/null checkout --detach "$AUTODATA_R3_CANDIDATE_SHA"
test -d "$AUTODATA_R3_ACCEPTANCE_ROOT/checkout/.git"
test -z "$(git -C "$AUTODATA_R3_ACCEPTANCE_ROOT/checkout" remote)"
```

Before Compose build/run, the coordinator creates `artifacts/host-before.json` and `artifacts/inputs.sha256.json` from this clone using host-observed `git rev-parse HEAD`, `git status --porcelain=v1 --untracked-files=all` (must be empty), `git ls-tree -r --full-tree -z HEAD`, and filesystem SHA256 of each tracked file. The manifest is complete for all tracked mounted files, not just a handpicked list. JSON schema is fixed:

```
inputs.sha256.json = {
  "schema_version": 1,
  "candidate_sha": "<host-observed 40-hex SHA>",
  "candidate_origin": "coordinator-host-plain-clone",
  "files": [{"path":"<repository-relative path>","git_mode":"100644|100755",
             "git_blob_oid":"<ls-tree oid>","sha256":"<filesystem SHA256>"}]
}
host-before.json = {
  "schema_version": 1, "phase": "before", "candidate_sha":"<host-observed SHA>",
  "git_observation_origin":"coordinator-host", "git_status_porcelain":"",
  "checkout_kind":"plain-clone", "remotes":[], "observed_at":"<UTC>",
  "input_manifest_sha256":"<SHA256 of exact inputs.sha256.json bytes>"
}
```

Paths must be unique sorted repository-relative POSIX paths, without absolute or traversal components. At the inspected R2 candidate all tracked entries are regular files. Fail manifest construction on symlinks, submodules or unsupported modes until their provenance is explicitly reviewed; never dereference an outside symlink silently. Require clone filesystem content/modes to match the committed tree (clean status), and record complete manifest bytes/hash before building. Compose/Dockerfile, Go manifests/local contract module, Python sources/tests, lifecycle helper, fixture server, migrations and migration driver are therefore included automatically. The manifest is outside the clone/build context so evidence creation does not dirty the mounted checkout. Build stages copy only explicit committed inputs; no host credentials or environment files enter the image.

The new Python integration module, before fixture setup, reads these artifacts from `/artifacts`, validates manifest format/candidate identity and recomputes each SHA256 and executable-mode bit from `/workspace`. It also enumerates regular checkout inputs while excluding the `.git` directory and rejects unexpected files (except any explicit non-input evidence mount, which is outside `/workspace` here). It fails on missing/changed/additional files. Repeat comparison after Go and at module/session completion; no test writes to source. Record `runner-input-before.json` and `runner-input-after.json` containing manifest hash, complete comparison outcome and origin `runner-filesystem-hash-comparison`.

For this plain-clone required mode, additionally execute these bounded, read-only commands inside the runner, each with invocation-local Git safety settings:

```sh
git -c safe.directory=/workspace -c core.hooksPath=/dev/null -C /workspace rev-parse HEAD
git -c safe.directory=/workspace -c core.hooksPath=/dev/null -C /workspace status --porcelain=v1 --untracked-files=all
git -c safe.directory=/workspace -C /workspace remote
```

Require actual stdout SHA equals manifest/coordinator SHA, status and remotes empty. Record this as `runner-git-observed` separately from the supplied candidate field; fail required plain-clone acceptance if Git observation is unavailable. Read-only Git may be unable to refresh its index; invoke with `--no-optional-locks` immediately after `git` if necessary, preserving the same safety options and command semantics. Include a Git executable in the existing authorized test Dockerfile's dependency list if the inherited image lacks it. No global `git config`, HOME rewrite or writable checkout is required.

After the runner exits, the coordinator repeats host clone HEAD/status/hash observations to `host-after.json`, requires the same SHA, empty status/remotes and identical input manifest hash, and verifies complete runner evidence. A nonzero test exit still produces after-evidence before reporting failure. Artifacts embed `candidate_origin`, host observations, independent runner observation and input manifest hash; never relabel a supplied SHA as an observed value. Use a fresh acceptance root for each candidate/run so stale artifacts cannot satisfy checks.

A noncertifying diagnostic run may use the existing linked-worktree mount with host before/after observations plus the same full manifest/hash checks. It must record `runner_git_observation: unavailable-linked-worktree` when appropriate, `candidate_origin: coordinator-host-attested-hash-verified`, and must not report a supplied SHA as independently Git observed. The required acceptance command below uses the plain clone, so this diagnostic alternative cannot silently substitute for its Git requirements.

Record emitted migration-driver SHA256, exact migration marker set and PG/Go/Python versions. Current expected head is038_article_transform_publication; after migration repair fresh DB must contain all38 markers, including runner-owned033. Do not hardcode a false marker count at unintegrated R2, whose old fixture leaves033 absent. Refuse a migration set different from the newly pinned checkpoint rather than silently accepting an unexpected039. Record database schema/migration head once before and once after each case; no arbitrary R3 handwritten schema or ALTER repair.

## Named tests and assertions

Use these four exact top-level Go names, each separately invoked for bankone and banktwo (eight Python bridge cases). Python case name is `test_required_go_catalog_lifecycle[<GoName>-<provider>]`.

1. `TestPostgresCatalogLifecycleColdHTTPRaceOneJob`
   - Initial selected article has no source/canonical/current article job. Snapshot records the constructor's two index jobs as baseline.
   - Start20 concurrent GET detail requests across two real Go HTTP servers with a common start channel; no worker started. Each request has a bounded client deadline (3s), each server scheduling context remains2s. Assert202 pending, same nonempty durable job_id and canonical UUID, no body/document, complete=false, safe retry information/no-store. Capture each elapsed time; do not assert eventual readability on this no-content phase.
   - Also send20 concurrent actual internal HTTP ensure requests through the returned HTTPIngestionClient's `client.Do(incoming, "/v1/catalog/ensure", payloadBytes, idempotencyKey)` against the counting real R2 endpoint with the same proven identity. This explicitly proves cross-request SQL idempotence even if Go coalesces its own cold requests. Assert acknowledgments all reference the same existing job. Do not call runtime.ensure or a fake client.
   - PG query scoped by canonical_article_id and job_kind='article' must return exactly one durable job; its ID equals every returned ID. Both index jobs remain intact, no source/revision/event rows for selected article, source/asset/model counters0, actual ensure counter>=21 (at least one Go request plus20 direct real ensures). Record Go-origin requests and deliberate internal race requests separately so this number is honest.

2. `TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP`
   - A Go detail GET first creates the sole durable article job via actual HTTP and returns202. Capture ID; start two ordinary real workers through control.
   - Wait until model proxy reports upstream_completed=1, response_captured=true, downstream_waiting=1, downstream_completed=0, no proxy errors, and actual runtime.model.calls=1. Read real DB: selected source_revision_id nonnull, canonical_revision_id null, processing_state=rewriting.
   - Perform20 detail reads (including concurrent reads on both servers), source-review JSON and list. All source detail reads return200 within bounded deadline while response remains held; assert source origin, available, complete=false, identical source/job IDs and source view_revision, readable ordered pump text, safe source-review projection, no mixed canonical metadata. Confirm held flag still true AFTER reads. Source source_revision_id and document refer to the same immutable source.
   - Since the active job exists, delta of actual HTTP ensures is0 for these reads; bankone+banktwo whole request-list deltas0, model delta0. Absolute selected-provider source body fetch count1, other bank resource fetch0, asset0 with this no-image fixture. Exactly one rewrite attempt is dispatched and no canonical publication/event yet.
   - Release model response, await published canonical via real DB/control, assert one validated published canonical revision/event and same durable job ID, detail canonical/completed/complete=true with “Take off the pump.” Run final evidence snapshot before shutdown.

3. `TestPostgresCatalogLifecycleAtomicPublication`
   - Schedule via Go detail HTTP, use existing inside_publication R2 barrier as described above, with an unblocked ordinary model proxy (release Event already set). Its one actual model request must complete.
   - At inside_publication barrier, another PG connection and Go detail handler must still observe the complete source tuple: source origin/source revision/job, canonical_revision_id null, source document/body/steps/images. An uncommitted publisher must not block this normal read. No newly published canonical row/event is visible outside the transaction.
   - Release promptly. Poll detail over HTTP during commit and collect at least one known-before and one known-after response. Each response is one allowed full tuple; source tuple contains only source projection/metadata, canonical tuple contains canonical projection/metadata with source revision relationship intact. No source content paired with canonical origin/complete or canonical revision paired with wrong source. Compare canonical document/body/steps/images to the committed revision in one PG transaction; view_revision changes exactly from captured source revision identity to captured canonical revision identity.
   - The public state cannot return from the committed canonical tuple to the old source tuple. Assert exactly one published canonical revision/event and one article durable job. This tests the immutable projection switch, not transient processing timestamps.

4. `TestPostgresCatalogLifecycleWarmReadsNoExternalCalls`
   - Produce canonical solely by Go cold scheduling plus real workers and unblocked proxy; await publication; keep workers alive and idle. Prime source-review/list once if necessary only before the baseline; baseline must then show no outstanding ensure/proxy requests or worker stage.
   - Capture monotonic snapshots (do not reset an active fixture). Repeat100 detail/source/list cycles across two Go servers, source JSON and at least one HTML source request. All return200, same revision IDs, correct source pinned independently of canonical body, safe no-store headers. List retains both provider identities and distinct public UUIDs for identical provider-local IDs. For every list item exercised, read its UUID detail only after it has separately been completed; never count cold detail work as warm list evidence.
   - For the main warm cycle exercise the selected completed article; list itself must do no work for the other still-cold descriptor. Do not prewarm the other article just to hide an unwanted list scheduler. Catalog-index coverage was already completed by constructor for both providers.
   - Compare final-baseline: counting HTTP ensure entered/completed0, every connector path count0 for BOTH banks (not merely /resources/body), actual model.calls0, proxy model request0, article job count0, source/revision/event counts0. Keep an idle observation interval after cycles (at least250ms, bounded) then snapshot again to catch incorrectly detached Go scheduling. All asynchronous tasks created by requests must finish before the final assertion; expose errors/active counts and fail if nonzero. Assert each selected immutable row/pointer unchanged.

Use cumulative snapshots and subtract them at explicitly recorded phase boundaries. Do not call reset_counters during active IO. Existing runtime.counters() is supplemental: source/asset count resource paths only, model is fixture count, schedule is total job row delta since its explicit reset. It cannot prove zero actual ensure calls or zero provider list/resolution calls. Counter ownership: ensure handler owns scheduling HTTP counters; connector fixtures own complete request traces; serve_model owns actual model invocations; proxy owns forwarded/held/completed transport counters; PG owns durable job/revision/event counts. Record them as separate fields.

## Required subprocess and acceptance validation

For each case run exactly, cwd=/workspace/apps/api-go:

```
go test -json -count=1 -timeout=90s -run '^<one exact Go name>$' .
```

Python retains complete JSONL stdout, stderr, exit and a per-case manifest that explicitly includes candidate_origin, host-before evidence hash, runner Git observation and mounted-input manifest hash under `/artifacts/r3/<provider>/<GoName>/`. Stream to artifacts while waiting; Python timeout120s kills and reaps Go, records timeout and fails. No shell interpolation of test names; pass subprocess argv. Required validation after exit must:

- require exit0 and parse every stdout line as Go JSON (package output is an Output string within JSON);
- require the expected package and exact top-level test Run and Pass events, matching one completed top-level case; forbid unexpected top-level integration names and every Skip/Fail event at any depth;
- require at least one actual test Run and Pass; a package-only pass, cached/zero-tests output, missing named case, missing EOF/package Pass, build failure, interrupted stream or timeout fails;
- require post-run fixture evidence matching THIS database/provider/test/SHA and the invariant assertions/counter deltas above, not an old artifact;
- require all eight parametrized bridge cases pass and none skip. Pytest no-collection exit5 is failure. Save JUnit; the explicitly owned scratch supervisor defined below validates its exact eight testcases/no skips after pytest. Ordinary exit0 alone cannot certify skipped fixtures.

## Coordinator-owned scratch acceptance supervisor

The coordinator implements and owns `/tmp/autodata-r3-acceptance-supervisor.py` as a **scratch acceptance artifact**, reviewed against this contract before execution. It is outside the repository, is hashed into the acceptance evidence, and is not a proposed33rd repository file. No future unplanned repository driver, workflow, R2 helper edit or extra application path is required. The supervisor uses Python standard library subprocess/JSON/XML/hashlib, the already available Docker/Compose/buildx tools, host Git and the existing32path implementation. It creates the plain clone, complete host-before manifest, private project and artifacts described above; callers do not have to construct an unnamed surrounding driver. All shell examples in the earlier provenance section are the supervisor's equivalent preparation operations, not extra required manual acceptance steps.

**Exact future invocation** from the coordinator-host chosen candidate checkout, after fresh committed preflight and review:

```sh
python3 /tmp/autodata-r3-acceptance-supervisor.py \
  --source-repo /home/corp/Documents/ChatGPT/autodata \
  --candidate-sha "$(git -C /home/corp/Documents/ChatGPT/autodata rev-parse HEAD)" \
  --run-root /tmp/autodata-r3-required-acceptance \
  --prepare-timeout-seconds 120 \
  --build-timeout-seconds 720 \
  --start-timeout-seconds 180 \
  --test-timeout-seconds 1320 \
  --finalize-timeout-seconds 180 \
  --total-timeout-seconds 2700
```

`--source-repo` may instead name the coordinator's selected clean managed implementation worktree containing the committed candidate; it may not name another agent's active checkout. The supervisor checks actual host HEAD equals the explicit40hex SHA and clean status before cloning. `--run-root` must not exist; create it exclusively with0700 permissions, with `checkout/` and `artifacts/` children. Never reuse stale evidence or delete a caller-owned existing root. No HOME assignment or global Git config. Preserve all artifacts and clone until coordinator review, then remove only these owned scratch paths.

### Finite lifecycle and resource ownership

Use monotonic deadlines, argv subprocess calls and process groups. Set a global45minute deadline at supervisor entry; phases below have their own shorter limits and never extend the global deadline. Reserve the final180s before the global deadline for cleanup/local provenance. The nominal phase maxima total42minutes, leaving3minutes global slack. Child CLI shutdown is bounded and accounted within the phase/global deadline. A phase timeout is a recorded acceptance failure and cannot become success after late completion.

| Phase | Limit | Required bounded operation |
|---|---:|---|
| Preparation |120s| Host checks, plain clone/no remotes, manifests; verify Docker/Compose/buildx availability and create owned names |
| Build |720s| Build existing authorized lifecycle Dockerfile with Go1.26 and required dependencies; record full stdout/stderr/image ID |
| Services/start |180s| Start only owned PG/NATS/S3 and named runner; preserve service status and readiness observations |
| Entire test container |1320s| Covers pytest collection, all8 fresh fixture setups, Go runs, blocked predicates/IO, evidence writes and all fixture teardown |
| Finalize |180s reserved| Stop/kill owned resources as needed, retain partial evidence/logs, host-after Git/hash checks, validate complete results and write final JSON |

Go90s/Python Go-subprocess120s remain useful inner bounds but do **not** bound R2 `Repository.connect()` or a blocked `runtime.wait_for` predicate. The authoritative fixture-setup/teardown bound is the supervisor's1320s wall-clock deadline for the actual runner container. Do not claim those helper calls acquire a connect timeout or become interruptible. No change to R2 is needed: at outer timeout the whole owned container is terminated, including blocked Python and worker descendants, regardless of whether pytest has entered a test body or its teardown. Twenty-two minutes permits eight sequential cases with their120s Go ceilings plus360s aggregate fixture/setup/teardown overhead. Any resource stall that exceeds this budget fails required acceptance.

Generate one run token from UUID hex and persist ownership before starting anything:

```
project = autodata-r3-<first12hex>
runner_name = <project>-go-test-runner
builder_name = <project>-builder
image_tag = <project>-go-test-runner:acceptance
```

Refuse a preexisting project-labelled container, exact runner/builder name or image tag. Ownership evidence records the token, exact container IDs, Compose project labels, run-root, image ID and build backend. Never stop resources based only on a broad name prefix. Do not operate other agents' projects, host/live databases or published ports.

Build with a uniquely owned buildx docker-container builder, not an unowned shared backend:

```
docker buildx create --name <builder_name> --driver docker-container
docker buildx build --builder <builder_name> --load --tag <image_tag> \
  --file <run-root>/checkout/infra/compose/article-lifecycle-test.Dockerfile \
  <run-root>/checkout
```

The new go-test-runner service, within its already authorized Compose file, sets `image: ${AUTODATA_R3_TEST_IMAGE:?set owned fixture image}` alongside its existing build settings. The supervisor sets AUTODATA_R3_TEST_IMAGE to this owned tag and AUTODATA_LIFECYCLE_ARTIFACT_DIR to its owned artifacts directory. This prevents a build/run image mismatch without another Compose override file. No platform credentials or env_file are read. After creation, run `docker buildx inspect <builder_name> --bootstrap` within the build deadline. Record the returned node name and verify its exact backend container name `buildx_buildkit_<builder_name>0` was absent before creation, then save its Docker container ID/inspection. Record/verify that owned backend ID before accepting the build. If build times out, terminate the build CLI process group, then stop/kill only that newly created backend container and remove the owned builder with bounded calls; do not leave a timed-out backend running or kill a shared builder. Missing buildx capability is a failed prerequisite, not an implicit unbounded fallback.

Start with Compose arguments always explicit, cwd at the plain clone:

```
docker compose -p <project> -f infra/compose/compose.article-lifecycle-test.yaml \
  up -d --wait --wait-timeout 150 postgres nats minio

docker compose -p <project> -f infra/compose/compose.article-lifecycle-test.yaml \
  run -d --pull never --no-deps --name <runner_name> go-test-runner \
  python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/r3-pytest.xml \
  workers/ingestion-python/tests/test_catalog_api_integration.py
```

Do not pass --rm: retain the runner for inspect/log evidence on failure. The supervisor captures its exact Docker container ID, verifies name/image/project label, starts a bounded log follower to artifacts/runner.log, and waits for actual container state using bounded `docker wait <container-id>` or inspected state polling. The1320s deadline starts when the runner is created, includes any wait CLI overhead, and is enforced independently of the Docker CLI process. The required source/migration/S3/NATS probes remain inside the Python bridge before Go. Compose running/healthy state is not substituted for those probes.

Preserve the existing pinned S3 image; do not invent a healthcheck utility it lacks. Compose --wait can establish running state for a service lacking a healthcheck; the bridge's S3 round trip establishes readiness. If the installed Compose rejects that startup form, use owned PG/NATS `up -d --wait --wait-timeout 150` then owned minio `up -d`, all within the same180s startup deadline. No service is skipped. Build/pull/start failures are nonzero acceptance failures.

### Failure, timeout and finally behavior

All preparation/build/start/test operations run under try/finally. Handle SIGINT/SIGTERM as recorded failure and enter the same bounded finalizer. On runner timeout or any subsequent nonzero/error, **stop the actual owned container**, not just `docker wait`, logs or Compose client processes:

1. Inspect the saved runner container ID and verify saved name/image/project ownership. Attempt `docker stop --time 5 <id>` with a10s CLI deadline; if still running or stop times out, issue `docker kill --signal KILL <id>` with a10s CLI deadline. Reinspect within10s and record final Running/ExitCode/OOMKilled/Error. Kill/reap only the supervisor's local CLI process groups as well. Refuse success if the container cannot be confirmed stopped; record any daemon failure explicitly.
2. Export `docker logs <id>`, inspect JSON and owned service logs/status with per-command10s deadlines. Artifacts are already bind-mounted on host, so keep partial worker logs/Go JSON/test manifests/JUnit even when runtime teardown never completes. Missing or truncated expected artifacts fail, rather than being deleted or synthesized.
3. Attempt bounded `docker compose ... down --volumes --remove-orphans --timeout 5` for the saved exact private project, and remove only its saved owned runner/backend/builder resources. Before --remove-orphans require that project ownership is exclusive to this run. If CLI cleanup stalls, stop/kill the saved owned service IDs individually, with the same ownership checks and bounded CLI calls. Keep evidence before removal; never delete an unrelated volume or container. Cleanup failure is retained and blocks a passing certificate.
4. **Always attempt local host-after HEAD/status/full input-hash comparison even if Docker is unavailable, pytest failed, JUnit is absent or runner stop failed.** This uses host-only bounded operations and writes host-after.json plus comparison failure details. Arrange it ahead of optional lengthy Docker log collection if remaining finalization time is low. Require clone identity/hash equality with host-before. Record current candidate/source observation separately; do not change the asserted SHA to fit a changed checkout.
5. Write artifacts/acceptance-result.json atomically with phase timestamps/deadlines, command exits/timeouts, actual runner/container state, ownership, supervisor script SHA256, candidate provenance, manifest hashes, host-after outcome, checks present/missing and primary/cleanup failures. Finalization is bounded; any evidence command that cannot finish records unavailable/failure. Preserve the run-root on every outcome. A stopped-but-unvalidated runner is failure.

### Exact evidence validation before exit0

The scratch supervisor is the named owner of these post-pytest checks. It performs them within finalization after host-after observation and before a success result. It must not invoke an unnamed future repository driver. Parse untrusted JSON/XML without executing artifact content; no fallback to summary strings.

- Actual saved runner exits0, no timeout/OOM/runtime error; all phase processes exit0 and no cleanup/ownership failure. Pytest collection/setup/teardown failures and its no-collection exit5 fail.
- Parse artifacts/r3-pytest.xml. Require exactly this eight-element multiset of testcase `name` values (the bridge sets parametrization IDs explicitly), one occurrence each, classname `workers.ingestion-python.tests.test_catalog_api_integration`, no extra testcases, and no failure/error/skipped descendant elements at testcase or suite level:

```
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleAtomicPublication-bankone]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleAtomicPublication-banktwo]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone]
test_required_go_catalog_lifecycle[TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo]
```

- For each artifacts/r3/<provider>/<GoName>/ directory require a complete result.json, go-events.jsonl, go-stderr.log and measured-runtime.json. The bridge writes result.json only after its own assertions/evidence collection. Required fields are schema_version=1, provider, go_test_name, fixture_database, candidate_sha, candidate_origin, host_before_sha256, input_manifest_sha256, go_exit_code, timed_out, started_at, finished_at, phase_snapshots, assertion_results. `assertion_results` uses exactly the invariant keys assigned to its case below, each passed=true; missing/unknown/false invariants fail. measured-runtime.json contains actual PG counts/IDs and complete counter snapshots used for each asserted delta, not just asserted conclusions. Keep original worker/runtime evidence alongside it.

Required assertion_results keys (each case also retains its actual measurements): every case additionally requires `fresh_manifest_applied_001_038`, `empty_replay_noop_001_038` and `populated_replay_noop_001_038`, with the complete captured migration proof specified below. The supervisor validates these in addition to the scenario keys:

```
ColdHTTPRaceOneJob: cold_public_202, cold_same_job_id, one_durable_article_job,
  twenty_real_internal_ensures, zero_cold_external_calls
SourceReadableDuringActualModelHTTP: actual_model_response_held,
  readable_source_during_hold, active_read_zero_ensure_provider_model_delta,
  validated_canonical_after_release
AtomicPublication: precommit_source_visible, atomic_projection_tuples,
  monotonic_canonical_after_commit, one_publication
WarmReadsNoExternalCalls: warm_http_reads_complete, distinct_provider_descriptor_ids,
  warm_zero_ensure_provider_model_delta, warm_immutable_rows_unchanged
```

- Independently reparse all eight Go event streams: exact expected module package `github.com/lucronn/autodata/apps/api-go`; one `Action=run` and one `Action=pass` for that exact top-level Test; final package `Action=pass`; no `Action=skip` or `Action=fail` anywhere. Go action values are lowercase. Require exit0, timed_out=false, complete JSONL, no unrelated top-level integration test and executed-test count1 per case/eight total. A package-only pass or a “no tests to run” result fails.
- Recompute the cold one-job ID equality/count, source-held flags and model/ensure/provider deltas, atomic before/after source/canonical tuple bindings, and warm zero deltas from phase_snapshots/actual measured PG and counter evidence according to each named case. Require same unique fixture database for a case's artifacts and eight distinct database names across all cases. Go response assertions remain witnessed by the executed exact named tests; the supervisor additionally rejects contradictory or incomplete retained measurements.
- Recompute all artifact file hashes recorded by result.json. Require candidate/provider/GoName/fixture identities agree across JUnit, case result, runtime evidence and Go test output. Require all eight cases share this run's host-before hash and mounted-input manifest hash, never a prior run's files.
- Require complete host-before/host-after equality checks, runner-input-before/runner-input-after comparisons and independently runner-git-observed SHA/status/remotes for required plain-clone mode. Recompute manifest SHA256 and host checkout input hashes once more. Reject missing observations or supplied-SHA-only provenance. Required service probes must show PG17, actual S3 round trip and actual NATS JetStream response for each fixture environment; migration marker set/head and emitted-driver hash match the pinned checkpoint.

Supervisor exit0 means **all** phase, ownership, cleanup, exact-eight JUnit, exact-eight Go execution, scenario measurement and provenance checks passed; acceptance-result.json must say status=passed and list every checked invariant. Exit124 identifies any supervisor phase/global/container timeout; exit1 identifies failed assertions, infrastructure, incomplete/invalid evidence or provenance/cleanup mismatch; argparse invalid invocation exits2. Preserve the earliest primary failure plus subsequent failures, never mask them with cleanup or host-after failure. The outer coordinator checks both supervisor exit and acceptance-result.json; neither a bare pytest exit0 nor stale success JSON can certify acceptance.

The supervisor's full container deadline is the explicit answer to uninterruptible R2 setup/teardown IO. It supplies finite failed evidence without claiming helper-level cancellation or modifying helper code. Ordinary go test ./... without required fixture env remains supplemental unit evidence only.

## Re-pin after migration integration

The independently reviewed migration candidate e401a54342ec0f201728f95cdfc1ea32841d517c is integrated at f264dae2fb222b7a7c90e4ab79e2b04aa8589ccc. The post-migration refinement below pins the actual shared driver, helper delegation and retained postgresql-client dependency. Actual integrated CI, final tracking synchronization and a fresh committed-base preflight remain required before dispatch. Re-read exact integrated helpers/image/Compose and hash them; adjust this handoff only for actual verified interfaces, then commit the canonical plan/task update before implementation.

Confirm fresh migration ledger includes033 and038, repeat migration driver skips all without changing applied_at/schema/data, and helper constructor still provides the APIs listed here. Record the migration-runner candidate and integrated SHA separately. Re-pin all R3 tasks/record plan_ref/docs at that new committed base and run `python3 scripts/autonomy/pre_implementation.py --record "$AUTODATA_RELEASE_RECORD" --base-sha "$AUTODATA_IMPLEMENTATION_BASE" --repo-root .` with nonempty variables. Keep task blocked if any dependency, synchronization or preflight result is unavailable. Later R5 migration039 requires a newly reviewed driver manifest and new pin; it must not be silently included in an038-certified R3 run.

The resulting certificate covers deterministic R3 runtime acceptance and shared infrastructure. It does not certify live banks, production credentials, browser acceptance, production identity, outbox delivery semantics beyond separately verified R2 evidence, deployment or release completion.

## Independent planning review

The source refinement passed independent planning review at SHA256 `a7188c9d352666dd9d61c7e92af5459fe850ea007a05507d3fd707cbc359e7c6`; review retained at `/tmp/autodata-r3-runtime-plan-review-final.md`. This canonical incorporation changes only status/location wording. Ownership, runtime composition, bounded supervisor, exact-eight-case validation and provenance requirements are unchanged. Migration integration and reinspection remain prerequisites.

## Post-migration refinement, independently reviewed

The following bounded amendments were inspected against integration `1d07ce28b5cc4cb7fb95ab41db8c178eff0d3c4d`. Independent review approved source report SHA256 `13f5c409eee33249379a5be0b1d989b10ce51c77b64db78a02675be6277cd135` with no blocking findings; retained review is `/tmp/autodata-r3-postmigration-independent-review.md`. These clarify the preceding implementation contract and control where older illustrative language differs. They add no repository implementation paths and preserve the exact four named Go cases across both banks. R3 remains blocked until its dependency and fresh gate requirements are satisfied.

## 1. Correct the actual Compose run command

Coordinator observed installed Compose2.40.3-3 rejects `run --no-build`. I independently inspected `docker compose run --help`: --pull accepts never, --no-deps is supported, --build is optional, and --no-build does not exist.

The formerly proposed unsupported invocation is shown only as a rejected form:

```
run -d --no-build --name <runner_name> go-test-runner
```

Use the supported invocation:

```
docker compose -p <project> -f infra/compose/compose.article-lifecycle-test.yaml \
  run -d --pull never --no-deps --name <runner_name> go-test-runner \
  python -m pytest -q -p no:cacheprovider \
  --junitxml=/artifacts/r3-pytest.xml \
  workers/ingestion-python/tests/test_catalog_api_integration.py
```

Do not pass --build. The supervisor's preceding owned buildx phase must succeed and `docker image inspect <image_tag>` must return the saved built image ID. AUTODATA_R3_TEST_IMAGE fixes this exact tag in the new service. Resolve/record Compose service configuration before start, require its image to equal that tag, and require the new container's inspected Image field to equal the saved image ID after start. Missing image, unexpected implicit build/pull, mismatched image, service failure or unsupported required flag fails before success; do not fall back to an unverified image. --no-deps prevents the one-off runner from starting additional services after the supervisor's bounded explicit PG/NATS/S3 start phase. No host ports or credential change is involved.

The source-fallback plan already labels its older raw component command noncertifying. Prefer changing its adjacent “future required command” wording to “component illustration; required acceptance is the bounded supervisor” so --build/--rm cannot be mistaken for the final acceptance command. This is a documentation change, not another implementation path.

## 2. Freeze the migrated helper and fresh/replay-through038 proof method

Actual migrated fixture signatures:

- `fresh_database` remains a pytest fixture yielding callable `fresh(through=None)`. `fresh_database()` runs the shared runner over a temporary copied canonical prefix; `fresh_database(through=0)` creates an empty uniquely named DB without applying SQL; a positive through value copies that prefix and calls the shared runner with --migrations-dir.
- Its migration subprocess captures stdout/stderr internally and asserts returncode0 but returns only Repository. Consequently R3 cannot honestly claim to have retained the first38 AUTODATA_APPLIED lines merely by calling fresh_database() and examining the returned object.
- `Repository.connect()` remains unchanged, with fixed fixture host/user/password/prefix guard and no connect_timeout. Fresh DB creation/destruction psycopg calls likewise have no timeout. The reviewed outer supervisor deadline remains authoritative for a blocked setup/teardown; do not claim wait_for or subprocess Go deadlines solve this.
- `apply_migration(repo, number)` explicitly remains raw original SQL for intentional upgrade/failure tests, not an operational chain. Do not use it for R3 lifecycle installation/replay.

Decision-complete R3 bridge recipe, entirely inside its already owned test_catalog_api_integration.py:

1. Validate required flags and strict fixture target before requesting the fixture. Obtain `repo = fresh_database(through=0)`. Do not instantiate LifecycleRuntime until the full fresh/replay proof succeeds.
2. Prepare a minimal **test-owned** subprocess env: preserve image PATH/default home unchanged, remove inherited PG*/DATABASE_URL/service/password-file routing, then set PGHOST=postgres, PGPORT=5432, PGDATABASE=repo.database_name, PGUSER=lifecycle_test, PGPASSWORD=lifecycle_test_only, PGSSLMODE=disable and PGCONNECT_TIMEOUT=3. All values are fixture-only; no DSN fallback. Keep the previously specified required flags/Python paths where needed. Do not edit lifecycle_support.py or clear/relocate HOME.
3. Run argv `['sh', str(ROOT/'scripts/dev/migrate_sql.sh'), '--emit']` with a30s subprocess deadline. Retain the exact driver bytes/SHA256 and stderr/exit. This default invocation validates the complete canonical38-file manifest; do not supply a copied prefix or --migrations-dir for this R3 certification.
4. Run argv `['sh', str(ROOT/'scripts/dev/migrate_sql.sh')]` with the explicit fixture env and a90s subprocess deadline. Retain stdout/stderr/exit as migration-fresh.*. Require exit0 and the exact ordered AUTODATA_APPLIED filename vector equal to the pinned001..038 manifest, with no AUTODATA_SKIPPED lines. Check all38 exact schema_migrations version strings, including033_catalog_scope_coverage and038_article_transform_publication. No cardinality-only proof.
5. Snapshot ordered complete ledger rows (including applied_at) and normalized full schema. Run `pg_dump --schema-only --no-owner --no-privileges` against the same fixture env with a30s deadline; remove only lines beginning literal `\restrict ` and `\unrestrict `, as the integrated migration tests already do. Record pg_dump/psql/server versions. Preserve all constraint/index/function/trigger/view definitions, including catalog_article_current and content_partial constraint; do not compare object names alone.
6. Run the same default shared driver again, deadline90s, retain migration-replay-empty.*. Require exit0, exact ordered38 AUTODATA_SKIPPED filenames, no AUTODATA_APPLIED lines, exact unchanged ledger rows/applied_at and normalized schema.
7. Only now construct `LifecycleRuntime(repo, stack)` and run the named Go case. The constructor's two actual catalog-index jobs remain the case counter baseline. All article scheduling still crosses real Go→R2 HTTP; the migration proof does not use runtime.ensure or ingest_to_publication.
8. After the Go case completes successfully and after its final live-worker/counter assertions, record runtime evidence, release any owned Events and stop the captured worker handles. Verify worker termination using the adapter below before taking a populated replay snapshot. Do not replay while a worker or publication hook is live.
9. Snapshot complete rows from schema_migrations, catalog_articles, canonical_articles, canonical_article_source_revisions, canonical_article_source_observations, canonical_article_revisions, canonical_article_reviews, canonical_article_rewrite_attempts, source_fetch_jobs, publication_events, source_snapshots, catalog_article_provider_scopes, catalog_article_index_pages and canonical_article_aliases. Query each allowlisted table as `SELECT to_jsonb(t) AS record FROM <fixed table> t ORDER BY to_jsonb(t)::text`; preserve full values, not a few pointers/counts. Snapshot normalized schema too. Do not compare time-derived retry-after values from the dynamic read view as immutable data.
10. Run the same default driver a third time, deadline90s, retain migration-replay-populated.*. Require38 exact skips/no applies, unchanged full rows, ledger timestamps and schema. The cold-race case proves pending-job preservation; the other three cases prove published canonical/source/job/event preservation. This yields actual populated replay evidence without another pytest testcase or R2 helper edit.
11. Put ordered applied/skipped filenames, driver hash, marker rows, schema/data before/after hashes and subprocess exits/timeouts in each existing per-case measured-runtime.json/result.json. Add required invariant keys `fresh_manifest_applied_001_038`, `empty_replay_noop_001_038` and `populated_replay_noop_001_038` to EACH case's existing assertion_results map and supervisor validation. Preserve exactly four Go names×two providers/eight JUnit cases. A subprocess timeout or missing replay evidence fails the case and required acceptance; the outer container deadline still covers fixture connection/teardown stalls.

The integrated runner is a fixed full001–038 manifest, accepts only explicit canonical contiguous prefixes when --migrations-dir is used, uses one session advisory lock(186,3738), transactional legacy files, exact existing036–038 transaction blocks, explicit033 marker adoption and psql -X/ON_ERROR_STOP. New R3 fresh DBs start empty, so first apply has no legacy033 adoption side effects. Do not modify historical SQL or extend to039. R5's future039 needs a separately reviewed runner manifest/pin.

The integrated migration tests already implement and verify the relevant fresh/restart, markerless033, actual036 upgrade, partial-content restart, connection failure and populated-publication restart methods. Reuse their *method*, not their runtime.ensure scheduling trigger, for R3. No R3 need to import private helpers from another test module.

## 3. Make actual image packaging precise within the existing Dockerfile

At f264 the image is still Python3.14-slim with poppler-utils, tesseract-ocr and **postgresql-client**; it does not yet contain Go or an explicit Git install. Preserve all of those migration additions and the existing pip setup. Ingestion dependencies already include nats-py/psycopg/minio and cover the required enrichment fixture dependencies; preserve existing PYTHONPATH including both worker sources, contracts/python and ingestion tests. No new pip runtime provider package is needed for this harness.

The Go local replace is `../../packages/contracts/go` from apps/api-go. Existing Go manifests are:

```
apps/api-go/go.mod
apps/api-go/go.sum
packages/contracts/go/go.mod
```

There is **no packages/contracts/go/go.sum**. A COPY that requires one would fail the build. Concrete build-time layout:

```dockerfile
FROM golang:1.26 AS go-toolchain
# Existing Python final stage and apt/pip setup follow, preserving postgresql-client.
# Add git to that existing apt list if not otherwise available for runner Git observation.
COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOTOOLCHAIN=local CGO_ENABLED=0 GOMODCACHE=/opt/go-module-cache
COPY apps/api-go/go.mod apps/api-go/go.sum /opt/prefetch/apps/api-go/
COPY packages/contracts/go/go.mod /opt/prefetch/packages/contracts/go/
RUN cd /opt/prefetch/apps/api-go && go mod download
```

Keep module-prefetch directory relationships exactly as shown; this lets Go resolve the existing relative replace during download. The scratch prefetch paths contain manifests only and are not a runtime application source checkout. At runtime use the actual read-only /workspace modules, explicit GOCACHE/GOTMPDIR, GOMODCACHE=/opt/go-module-cache, GOTOOLCHAIN=local, GOPROXY=off, GOFLAGS=-mod=readonly and CGO_ENABLED=0. No compiler installation is needed for the Go pgx/minio tests, and runtime must not attempt dependency/toolchain downloads or manifest writes. Build-time verification checks go version1.26, psql/pg_dump/git availability and downloaded module cache. No HOME assignment. The new owned image tag/service remains in the already authorized Compose file; the existing test-runner's command and isolation behavior remain usable.

This packaging is proposed R3 implementation, not a claim that Go is already installed or that the future image has been built. The current migration image additions are independently inspected, not modified.

## 4. Preserve the actual worker/process/hook distinctions

The migration changed only fresh_database chain execution and imports/docstring in lifecycle_support; runtime/helper APIs are otherwise byte-for-byte unchanged from approved R2. The real client constructor and returned-client Do signature are unchanged. The model proxy design therefore remains valid.

Record these process distinctions in the canonical harness instructions to prevent impossible assumptions:

- Ordinary runtime.start_workers(2) yields subprocess.Popen CLI workers: inspect with poll(); a worker exiting before intentional stop fails; intentionally terminated CLI exit codes are recorded separately.
- With runtime.pause('inside_publication'), start_workers(1) yields multiprocessing.Process running the existing top-level _hooked_worker ONCE; it is not a CLI polling worker. Inspect with is_alive()/exitcode/join(), not poll(). Normal exit0 after released publication is expected. runtime.wait_for only explicitly checks early Popen exits; do not claim it checks spawned child exit status.
- Before runtime.stop_workers(), retain `owned_workers = list(runtime.workers)`; that helper clears its list. After it returns, inspect saved handles, kill/join any still-live owned spawned process with a bounded3s wait and record failure if stop/kill/reap cannot be confirmed. The existing spawned stop branch terminates+joins but has no kill escalation. Implement this adapter only in R3's Python file; outer owned-container termination remains the final bound.
- The inside_publication hook is real and occurs after setting a candidate row's status to published **inside an uncommitted transaction**, before current_canonical_revision_id/job completion/outbox insert. Outside observers can still see the validated candidate row; assert zero *published* rows/events and the old source projection, not zero canonical candidate rows. Do not use a locking observer query.
- The hook's released.wait bound is10s, not the model proxy's25s. Once the barrier is observed, perform the precommit Go detail/PG read promptly (bounded2s calls) and release within3s. If that budget cannot be met, fail and release in finally rather than extending/changing the helper. The actual model response blocking case uses ordinary CLI workers and the separate test-owned proxy; after_model_dispatch remains before model IO.
- Since the atomic worker is a one-job process, do not require it to remain alive after publication or call restart_workers to prove warm behavior. Its normal exit0 must be retained before helper cleanup. The warm case uses ordinary idle CLI workers until its zero-call observations complete.

The supervisor already bounds all setup/teardown blocking IO by terminating the actual owned runner and retains host-after/partial evidence. These adaptations require no new runtime API and no modification of R2 helper/process/lease behavior.


## Exact inspected input hashes

SHA256 at f264, obtained from git show of exact committed bytes:

```
affd63093ce694b5ed58979352bc23051e7ab0d4ce2e9a81fbb70c8404b85eff scripts/dev/migrate_sql.sh
746eba57bfffb760e2f779d0d0494125f8b559b07de5ff6ec11099d517bf76dc workers/ingestion-python/tests/lifecycle_support.py
ec0de35803d56bf185f7bbd8f90bf9c104391ad6e2a85041e11dab9baa0257fb infra/compose/article-lifecycle-test.Dockerfile
9c1db10bad1d9cb8db3cc7a56c5cc43280e326c013207f1fb351d4928bd39b32 infra/compose/compose.article-lifecycle-test.yaml
8d783ab4615db4dcc720d15a67db2731c2038c365cbee1df183afc6605de0ef7 workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py
22087935412e90b17f28e746e46d454d6fb5ff65c22cf61c13c83ae39a151268 workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py
49f26ef87596ac046debeae6bdd53da89a09e1f7f41045919bef061fe69f2b95 scripts/dev/source_connector_fixture_server.py
307b1c06e45eb93adc0366e5640cd7cef1a58c384e1d7b165f97f570473e4a66 apps/api-go/ingestion_http.go
```

Verification performed for this planning report: read exact Git objects, compared e401/f264 runner/helper/image bytes (no diff), compared approved R2 runtime/source/model/client bytes (unchanged outside the migrated fixture chain), inspected actual Compose run help and task count/status. No fixture stack, provider/model call, test image build, runtime acceptance test or production operation was executed for this review.

## Dispatch checkpoint status

Migration/discovery integration1d07ce28b5cc4cb7fb95ab41db8c178eff0d3c4d has
passed809 fixture tests plus32 subtests and actual GitHub run41627289946, including
live Compose smoke. The reviewed refinements above are now incorporated. R3's
task record is synchronized for this fresh committed checkpoint; no implementation
is permitted until exact-base machine preflight passes. The implementation agent
then owns only the32 listed paths. Earlier blocked status statements record the
order of planning and do not waive this final gate.
