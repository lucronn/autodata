# Source Fallback API and Workshop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Follow the repository planning gate before modifying implementation files. Steps use checkboxes for actual execution tracking.

**Goal:** Serve readable source articles while one durable rewrite job prepares their canonical revision, and let Workshop transition without losing selection or source access.

**Architecture:** R2 owns immutable source/canonical revisions and one durable job. The Go API reads its selected ordered-document projection and performs only bounded durable scheduling. Workshop uses the same renderer for both origins, with sequential cancellable polling.

**Tech Stack:** Go 1.26, Python 3.12+, PostgreSQL, ordered-document v1 DTO, native browser modules, Python Playwright for deterministic browser acceptance.

**Spec:** `docs/superpowers/specs/2026-11-03-source-fallback-web-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-03-production-release-orchestration.md`

**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186

**Planning status:** reviewed plan linked to Issue #186 / Project #8. R3/R4 remain blocked until their dependency checkpoints and synchronized task preflights pass. No implementation or release completion is asserted.

## Global Constraints

- All execution and review agents use `gpt-6.1-sol`, `medium` reasoning, and Fast/`priority` service. Current planning is separate from that execution profile.
- Keep `schema_version: 1` and `normalization_version: ordered-article-v1`; source and canonical content use one ordered-document renderer.
- Both banks retain their own provider/resource identity; never infer identity from titles or provider-local IDs alone.
- R2 owns source fetching, durable jobs, rewriting, migrations, leases, retry scheduling, and publication. Go and JavaScript never call a provider or model directly.
- Preserve article aliases and compatibility fields. Structural source normalization does not imply canonical rewrite completion.
- Source/media revisions are immutable; a later media recapture creates a new source revision.
- Apply existing access, vehicle scope, quarantine, and takedown policy equally to source and canonical content. No new billing requirement is introduced.
- Implementation requires actual Issue/Project synchronization, committed plan/docs, and a machine-checked synchronized record at the pinned base.
- R4 completion depends on R3 and the R5 identity/backend contract. Fixture-only preparation may precede them without overlapping application edits.
- R5 selects production identity and verifies access. R6 owns staging and release certification. This plan cannot declare either complete.
- Independent reviewers inspect the exact resulting implementation SHA using the execution profile above.

## Concrete todo and ownership

- [ ] Coordinator synchronizes real release tracking, canonical documentation, and the exact-base gate record.
- [ ] R2 publishes the agreed schema/view/ensure contract and fixtures.
- [ ] R3 implements public lifecycle DTOs, local read projection, bounded scheduling, and truthful index completion.
- [ ] R3 migrates descriptor listing to canonical records with scoped legacy compatibility and preserves distinct bank identities.
- [ ] R3 implements safe source-review/media presentation and complete public contracts.
- [ ] R5 publishes the production identity/backend contract before Workshop completion work.
- [ ] R4 implements selection-safe rendering, polling, cancellation, and recovery.
- [ ] R3/R4 record deterministic API/browser evidence and obtain independent review.
- [ ] Coordinator carries production identity/media policy and live release evidence into R5/R6 acceptance.

R3 owns `apps/api-go/{catalog*.go,ingestion_http.go,openapi.json,openapi.yaml}` and
related tests. R4 owns `apps/api-go/workshop/`, Workshop tests, and its browser
runner. R2 owns migrations, ingestion, and the initial shared-contract checkpoint;
R3 extends that contract only after integration and fresh preflight. R5 owns
identity/session backend wiring and final media policy. Integrate R5's backend
contract before R4 changes Workshop authentication consumption; do not let R5
and R4 edit the same assets concurrently. Serialize `main.go` and contract edits.

Each implementation/review task runs in its own managed worktree with a bounded
path list. The inspection baseline `0ed449fe5119484f8dd8f40b40607aa3beb11e49` is
not the future authorized implementation base.

## Task 0: Establish the implementation boundary

**Owner:** coordinator. **Produces:** A committed synchronized record and exact
base for each downstream assignment; this is a prerequisite, not builder work.

- [ ] Record the actual Issue URL, Project item, canonical docs, goal, and concrete
  work list. Do not fabricate an Issue reference or mark synchronized early.
- [ ] Integrate the R2 checkpoint containing `catalog_article_current`, scoped
  aliases, durable scheduling, and the agreed lifecycle enum.
- [ ] Supply nonempty task-specific variables and run the machine gate:

```sh
test -n "$AUTODATA_RELEASE_RECORD"
test -n "$AUTODATA_IMPLEMENTATION_BASE"
python3 scripts/autonomy/pre_implementation.py --record "$AUTODATA_RELEASE_RECORD" --base-sha "$AUTODATA_IMPLEMENTATION_BASE" --repo-root .
```

- [ ] Preserve the actual validator output. A failure blocks implementation; it
  is not repaired by implementing first. Re-run after each integrated dependency
  changes the authorized base.

## R3 isolated Go/Python verification boundary

The independently reviewed [exact runtime handoff](2026-11-03-catalog-runtime-integration.md) is part of this R3 plan. It freezes actual R2 helper/Go signatures, the real model-response proxy, four named Go cases for both banks, counter ownership and truthful clone provenance. Its coordinator-owned `/tmp` supervisor bounds setup/testing/cleanup and requires all eight cases and host-after evidence; the raw commands below are component commands, not standalone acceptance. R3 remains blocked until the migration driver is integrated and these exact dependencies are re-inspected at the fresh checkpoint.

The narrowed R3 task lists every Go/test/contract/fixture path explicitly. It
additionally owns `infra/compose/compose.article-lifecycle-test.yaml`,
`infra/compose/article-lifecycle-test.Dockerfile`, and new
`workers/ingestion-python/tests/test_catalog_api_integration.py`, only after R2
integrates. No production Compose or workflow change belongs to this harness.

Extend the existing fixture image with Go 1.26 and prefetch module dependencies
at build time. Keep Python and Go in the same test container so R2's loopback
connector/model/HTTP fixtures remain reachable. Add a `go-test-runner` service
using that image, read-only checkout, writable temporary Go/cache/artifact
locations, the existing internal network and private project volumes. Never
mount host credentials, `/run/base44/app.env`, production env files or host ports.

The Python bridge creates a unique `lifecycle_test_*` database through the real
migrations, starts the committed R2 `http_service.make_handler` with deterministic
connector/model controls, and invokes the named Go PostgreSQL/scheduling tests
against that exact database and loopback ensure endpoint. Freeze actual R2
fixture helper bindings in the dependency checkpoint after R2 review, before R3
preflight; do not invent an alternate scheduling implementation. The test-only
connection must accept only the explicit fixture host/database/user and never a
host application DSN. Run with an explicit required-integration flag. Missing
services/DSN, skipped cases or zero executed integration tests fail this run.
Capture candidate SHA, migration head, Go JSON output and process exit.

The component illustration; required acceptance is the bounded supervisor (not yet implemented) is:

```sh
AUTODATA_LIFECYCLE_ARTIFACT_DIR=/tmp/autodata-r3-lifecycle-artifacts \
docker compose -p autodata-r3-lifecycle \
  -f infra/compose/compose.article-lifecycle-test.yaml run --build --rm \
  go-test-runner python -m pytest -q -p no:cacheprovider \
  workers/ingestion-python/tests/test_catalog_api_integration.py
```

Prove concurrent cold reads create one actual R2 durable job; source remains
readable while the model is blocked; publication switches atomically; and warm
completed detail/source/list reads make zero actual ensure/provider/model calls.
Ordinary `go test ./...` without the required fixture flag cannot certify these
properties. R5 reuses this runner for migrated sessions and two-server revocation
instead of creating another isolated stack.

## Task 1: Freeze public lifecycle DTOs and local reads

**Owner:** R3 Go/contract builder, after R2 contract integration.

**Files:** Create `apps/api-go/catalog_lifecycle.go`,
`catalog_lifecycle_test.go`, and `postgres_catalog_lifecycle_test.go`; modify
`catalog_store.go`. Extend the R2-owned
`packages/contracts/catalog/v1/article-lifecycle.schema.json` serially; create
`packages/contracts/catalog/v1/fixtures/` and
`scripts/contracts/test_catalog_lifecycle_contract.py`. Update
`docs/architecture/{provider-neutral-catalog-api,normalized-article-document}.md`.

**Interfaces:** Consume the R2 view columns listed in the spec. Add the following
read boundary to `CatalogStore`; retain existing methods until callers migrate:

```go
type CatalogProcessing struct {
    JobID string `json:"job_id"`
    State string `json:"state"`
    Retryable bool `json:"retryable"`
    RetryAfterSeconds *int `json:"retry_after_seconds"`
    ErrorCode *string `json:"error_code"`
    UpdatedAt string `json:"updated_at"`
}
type CatalogArticleView struct {
    Article CatalogArticle
    CanSchedule bool
    Withdrawn bool
}
// New CatalogStore method; Principal and vehicle scope are not discarded.
ArticleView(context.Context, Principal, string, string) (CatalogArticleView, error)
```

`CatalogArticle` receives the exact nullable identity/revision fields, origin,
availability, `view_revision`, review status, and processing object in the spec.
The public document contains no storage keys or upstream resource references.

- [ ] Add fixtures `source-rewriting.json`, `pending-source.json`,
  `canonical-completed.json`, `source-needs-review.json`, and
  `legacy-unmanaged.json`. Add rejected fixtures for title-only completion,
  unknown state, private object keys, and mismatched revision metadata, named
  `rejected-title-only-complete.json`, `rejected-unknown-state.json`,
  `rejected-private-object-key.json`, and `rejected-mismatched-revision.json`.
  Validate public fixtures with the existing verification dependency:

```python
schema = json.loads((ROOT / "packages/contracts/catalog/v1/article-lifecycle.schema.json").read_text())
validator = jsonschema.Draft202012Validator(schema)
validator.validate(json.loads((ROOT / "packages/contracts/catalog/v1/fixtures/source-rewriting.json").read_text()))
validator.validate(json.loads((ROOT / "packages/contracts/catalog/v1/fixtures/canonical-completed.json").read_text()))
```

- [ ] Run the new contract and Go lifecycle tests; observe the missing DTO/read
  behavior fail before implementation.
- [ ] Implement the scoped view read and public projection. Select all document,
  media, lifecycle, and provenance fields from one database snapshot. Derive
  `view_revision` without randomized image tokens. Map dead-letter/review states
  exactly; Go must not create a second worker state machine.
- [ ] Migrate `CatalogStore.Articles` from its legacy-only query to canonical
  descriptors, including list-only rows. Union eligible unmapped legacy rows;
  suppress a legacy duplicate only by its proven in-scope canonical alias.
  Apply Principal, vehicle/configuration, review, and withdrawal filters to both
  query branches. Use canonical UUIDs for managed rows and legacy UUIDs for
  unmapped rows; remove cross-bank `DISTINCT ON (article_id)` deduplication.
  Sort managed rows by R1 bank order, persisted source order, then canonical UUID;
  append unmapped legacy rows by title under `C` collation, then legacy UUID.
  List/search projects metadata only and never schedules article detail work.
- [ ] Add PostgreSQL fixtures for equal provider-local IDs across banks, wrong
  vehicle aliases, a newer source replacing an older canonical view, revision
  pinning, and quarantined/withdrawn rows. Compare real R2 view output with the
  public fixtures; memory-only coverage is insufficient.
- [ ] Add real PostgreSQL list-to-detail regressions: canonical-only descriptors
  before source capture; two banks sharing the same local ID/title both remain
  selectable; mapped legacy rows appear once and old UUIDs still resolve;
  unmapped legacy rows remain eligible; wrong-scope, quarantined, and withdrawn
  aliases do not leak through the union. Assert deterministic ordering and
  zero provider-body/model/article-ensure calls during list/search. Assert
  list-generated UUIDs resolve to the matching bank's detail and raw ambiguous
  provider-local aliases fail closed.
- [ ] Run `python3 -m unittest discover -s scripts/contracts -p 'test_catalog_lifecycle_contract.py' -v` and, from `apps/api-go`,
  `go test ./... -run 'TestCatalogLifecycle|TestPostgresCatalogLifecycle' -count=1`.
- [ ] Commit the scoped change after checks pass; record SHA/results and obtain
  independent contract/source review before Task 2.

## Task 2: Deliver bounded source-first HTTP behavior

**Owner:** R3 Go builder.

**Files:** Modify `apps/api-go/{catalog_http.go,ingestion_http.go,catalog_test.go,ingestion_http_test.go}` and extend `catalog_lifecycle_test.go`.

**Interfaces:** `getCatalogArticle` consumes `CatalogStore.ArticleView`.
`ensureCatalogArticleScheduled` calls existing `/v1/catalog/ensure` with
`scope:article`, R2's durable identity/idempotency fields, and a two-second
context deadline. Its agreed response is:

```go
type CatalogScheduleResult struct {
    JobID string `json:"job_id"`
    State string `json:"state"`
    CanonicalArticleID *string `json:"canonical_article_id"`
    SourceRevisionID *string `json:"source_revision_id"`
    RetryAfterSeconds *int `json:"retry_after_seconds"`
}
func (s *Server) ensureCatalogArticleScheduled(
    request *http.Request, payload map[string]any,
) (CatalogScheduleResult, error)
```

A final store read constructs the public response; upstream `2xx` alone never
proves content completeness. Existing methods used by other scopes remain.
Use a catalog-specific error writer with the existing error envelope and the
safe `details` keys from the spec; no unrelated `main.go` error behavior changes.

- [ ] Add table-driven handler cases before changing behavior: readable source
  active/failed/review `200`; canonical `200`; accepted no-content `202`;
  acceptance outage `503`; terminal no-content `409`; withdrawal `410`;
  wrong-scope `404`; and denied identity `401/403`. Assert origin, complete,
  availability, retryability, IDs, `Retry-After`, and `private, no-store`.
- [ ] Block the fake model/source behind durable scheduling and assert the API
  returns without releasing it. Repeat concurrent reads against R2's real
  PostgreSQL job fixture and assert one durable job, not merely one Go goroutine.
- [ ] Run `go test ./... -run 'TestCatalogDetailLifecycle|TestCatalogScheduling' -count=1` and observe the old synchronous behavior fail.
- [ ] Replace detail hydration with scoped read → serve readable view, or cold
  known-descriptor durable schedule → reread → documented HTTP result. Do not
  schedule completed or already-active work. Worker HTTP failure cannot discard
  existing source with an existing durable job.
- [ ] Correct index completion to use R1 coverage for every required bank scope.
  Test nonempty failed/partial progress, one successfully empty bank, both banks
  completed, and one unavailable bank. Keep usable rows; never fetch detail on
  list/search. R1 remains responsible for coverage proof and retry scheduling.
- [ ] Run focused tests then `go test ./...`. Exercise the actual R2 scheduling
  boundary and record call counters; warm completed reads require zero provider,
  model, and ensure calls.
- [ ] Commit, record actual evidence, and obtain exact-SHA API/reliability review.

## Task 3: Make source review and media revision-correct

**Owner:** R3 Go/source builder; final production access mechanism remains R5.

**Files:** Modify `apps/api-go/{catalog_source.go,catalog_media_token.go,catalog_image_storage.go}`, catalog/media tests, and
`docs/architecture/catalog-source-review.md`. Coordinate `main.go` serially if
R5's approved media mechanism needs route wiring.

**Interfaces:** Add optional `document`, `images`, and `view_revision` to
`CatalogSourceContentResponse`; retain metadata and sanitized `content`.
`ArticleSource` resolves `source_revision_id` only within the requested
article/vehicle. Direct HTML renders the immutable ordered projection with
escaped text and local media; it does not trigger hydration.

- [ ] Add tests for pinned versus newer source, mismatched/unknown revision,
  withdrawn content, and both bank source shapes. Assert main source view and
  source review preserve the same blocks/evidence/media, without an ensure call.
- [ ] Add synthetic resource-isolation fixtures covering preserved tables/warnings,
  unsafe external/active content, direct media navigation, missing images, and
  invalid media types. Do not include payload-level details in public issues.
- [ ] Run `go test ./... -run 'TestCatalogSource|TestCatalogMediaIsolation' -count=1` to confirm the relevant current failures.
- [ ] Implement pinned source projection and allowlisted compatibility content.
  Set the exact sandboxed media CSP and response headers in the spec, including
  direct SVG navigation. Validate supported media types against actual content.
  Keep localized bytes immutable; unsupported/unsafe formats remain unavailable.
  Do not add runtime rasterization or a remote image proxy/fallback.
- [ ] Preserve unavailable media at its original document/table position.
  Consume immutable materialization metadata from R2 instead of rewriting stored
  source or rerunning extraction during a read.
- [ ] Run catalog/media tests and Task 5 isolation scenarios. R5 must separately
  prove revoked/unauthorized media access fails; opaque tokens alone are not
  access-control evidence.
- [ ] Commit and record exact-SHA source/security review, including unresolved
  R5 dependencies.

## Task 4: Implement selection-safe Workshop transitions

**Owner:** R4 web builder, after R3 and R5 contract integration/preflight.

**Files:** Create `apps/api-go/workshop/article-read.mjs`; modify
`workshop/{app.mjs,catalog.mjs,index.html,styles.css}`,
`apps/api-go/workshop-client.test.mjs`, and
`docs/architecture/{workshop-interface,workshop-loading-progress}.md`.

**Interfaces:** Preserve `requestJSON` for collections. Export
`requestArticleJSON` from `catalog.mjs` and `readArticle` from `article-read.mjs`;
the latter imports `delay` from `catalog.mjs`:

```js
export async function requestArticleJSON(path, options = {}) {
  // Returns { status, data, retryAfterSeconds }; accepts signal/token/fetcher.
}
export async function readArticle(read, {
  signal, onUpdate = () => {}, wait = delay,
  now = () => Date.now(), budgetMs = 120000,
} = {}) {
  // Returns { latest, timedOut }; read receives { signal, timeoutMs }.
}
```

Use sequential delays `[1000, 2000, 4000, 8000, 10000]` ms, repeating the final
delay within the absolute budget. Requests last at most 10000 ms and no longer
than the remaining budget. Honor longer server retry intervals; stop if the
interval exceeds the budget. Terminal/unmanaged states stop immediately.
Non-200/202 transport responses throw `CatalogRequestError` with public `status`,
`code`, `retryable`, `retryAfterSeconds`, and `requestId`; only transient network
errors or retryable `429`/`503` are retried inside the remaining budget.

- [ ] Add fake-clock tests for source → canonical, `202` → source, due retry,
  terminal review, no-content errors, `Retry-After`, budget expiry, abort during
  wait/read, and one outstanding request. Add document-only readability and
  unchanged `view_revision` despite new image tokens. The core assertion is:

```js
const source = { status: 200, data: { article: {
  content_origin: 'source', availability: 'available', view_revision: 'source-1',
  processing: { job_id: 'job-1', state: 'rewriting', retryable: true },
  document: { blocks: [{ type: 'paragraph', text: 'Remove the cover.' }] },
} } };
const canonical = { status: 200, data: { article: {
  ...source.data.article, content_origin: 'canonical', view_revision: 'canonical-1',
  complete: true, processing: { job_id: 'job-1', state: 'completed', retryable: false },
} } };
const queue = [source, canonical], updates = [];
await readArticle(async () => queue.shift(), {
  onUpdate: value => updates.push(value.data.article.content_origin),
  wait: async () => {},
});
assert.deepEqual(updates, ['source', 'canonical']);
```

- [ ] Run `node --test apps/api-go/workshop-client.test.mjs` and confirm the new
  behavior fails before implementation.
- [ ] Implement transport status parsing and bounded coordinator. Preserve source
  on transient polling failure; stop/clear denied or withdrawn content. Only safe
  error enums map to fixed copy. A `202` descriptor cannot enable Print.
- [ ] Integrate selection generation + abort controller across article and source
  review. Every async callback, including `finally`, checks vehicle/article/
  generation before DOM writes. Vehicle/article/history/back/cancel invalidate
  all related work. Source-review callbacks also check pinned source revision;
  a new source revision invalidates the prior review request. Consume the R5
  session contract; remove demo assumptions
  without independently choosing an identity provider. The R5 session 401 has
  `error.details.login_available`: offer sign-in only for explicit true. False,
  missing or invalid values stop all related work, clear protected content and
  show sign-in-unavailable copy without redirect/retry loops. Local login503 uses
  the fixed AUTHENTICATION_UNAVAILABLE contract; no local cookie login is added.
  Include separate unavailable-local-login and expired-OIDC-session browser
  fixtures, asserting no stale protected content or repeated login requests.
- [ ] Render both origins through ordered blocks. Construct a complete detached
  fragment and replace atomically only when origin/view revision changes. Update
  processing copy independently; preserve focus, scroll/anchor, selection, and
  source-panel state. New source-review DTOs do not require a raw HTML sink.
- [ ] Implement the spec's bounded media renewal: one coalesced automatic detail
  refetch per selection/view revision after media load failure, with its existing
  generation/abort guard and request deadline. For unchanged content, update
  only URLs matched by stable asset ID, preserving DOM/focus/scroll. Consume the
  budget on failure and expose manual refresh; denial/withdrawal stops work and
  clears protected content. Test expired URL → unchanged revision/new URL →
  successful image, multiple simultaneous image errors, cancellation/selection
  switch, and repeated failed replacements producing no retry loop. Assert warm
  detail renewal performs no ingestion scheduling, bank or model calls.
- [ ] Add accessible status/origin/review labels and source printing. Preserve
  table/callout/image order, explicit unavailable blocks, native controls,
  keyboard use, local font, reduced motion, and mobile layout.
- [ ] Run helper tests, `go test ./... -run TestWorkshop -count=1` from
  `apps/api-go`, and Task 5 browser checks; commit only after actual passing
  results and obtain independent consumer review.

## Task 5: Publish complete contracts and browser acceptance

**Owner:** R3 contract builder then R4 test builder; serialize shared contracts.

**Files:** Modify `apps/api-go/openapi.{json,yaml}`, `catalog_media_test.go`, and
`scripts/contracts/test_catalog_lifecycle_contract.py`; create
`scripts/dev/workshop_browser_smoke.py`,
`scripts/dev/fixtures/workshop_catalog/`, and
`scripts/dev/test_workshop_browser_smoke.py`. Use Python Playwright in the test
environment; Workshop gains no runtime dependency. R6 owns later CI wiring.

**Interfaces:** Runner flags are `--base-url`,
`--browser chromium|firefox|webkit|all`, and `--output`. Load actual embedded UI
assets; intercept catalog calls with versioned synthetic fixtures; reject
unexpected external origins. Record SHA, browser version, scenario, request
order, assertions, failure screenshots, and command outcome. This suite is
browser/DTO acceptance, not a live-bank or database canary.
Use the deterministic identity fixture and exact bootstrap paths from the R5
checkpoint; do not invent an auth endpoint or authenticate against a live account.

- [ ] Add all existing selector routes to JSON/YAML OpenAPI. Include lifecycle,
  document/table/image schemas, every specified HTTP outcome, retry headers,
  aliases, pinned source review, and examples. Test normalized JSON/YAML agreement
  against the shared catalog schema.
- [ ] Validate R2 producer, Go response, and browser fixtures against that schema.
  Include old responses without additive fields and explicit tightened-complete
  semantics. Do not modify unrelated dataset/payment contracts.
- [ ] Implement individually named scenarios: `bankone-cascade`, `banktwo-cascade`,
  `dual-bank-coverage`, `one-bank-unavailable`, `pending-no-content`,
  `source-to-canonical`, `source-rewrite-failure`, `review-required`, `warm-reload`,
  `selection-change-in-flight`, `source-review-change-in-flight`,
  `cancel-and-retry`, `history-restore`, `document-only`, `missing-media`,
  `withdrawal`, `keyboard-print-mobile`, and `source-media-isolation`.
- [ ] Assert source appears before canonical release, one atomic replacement,
  unchanged selection/focus, and no invented progress. Deliver A after navigating
  to B in both stale-response scenarios and assert no A content/status reaches B.
  Fixtures retain ordered warnings, numeric/tool values, tables, and image slots.
- [ ] Run contract/Go/helper checks and every browser engine. Missing engines or
  dependencies are unavailable evidence, not successful skipped coverage.
- [ ] Commit scoped contract/fixture work. Obtain exact-SHA contract, consumer,
  source, and security reviews. Carry any failed/unavailable requirement into the
  parent release gate without claiming completion.

## Acceptance commands and evidence

These are future implementation commands, not results of this planning task.
Use isolated deterministic services and the R2 fixture DSN, never a live provider
credential file. From the repository root:

```sh
python3 scripts/contracts/generate.py --check
python3 -m unittest discover -s scripts/contracts -p 'test_*.py' -v
node --test apps/api-go/workshop-client.test.mjs
python3 -m unittest discover -s scripts/dev -p 'test_workshop_browser_smoke.py' -v
git diff --check
```

From `apps/api-go`:

```sh
go test ./...
go vet ./...
```

The R2 PostgreSQL fixture must enable `TestPostgresCatalogLifecycle`; a skipped
database suite is insufficient. Record migration head and results without
secrets. Tests use R2 migrations, not an approximate hand-written R3 schema.

Start the real embedded UI in a separate verification process from
`apps/api-go`, disabling ingestion for the browser interception suite:

```sh
AUTODATA_ENV=test AUTODATA_AUTH_MODE=local AUTODATA_READINESS_MODE=static AUTODATA_PROJECTION_STORE=memory AUTODATA_INGESTION_URL= AUTODATA_API_ADDR=127.0.0.1:18080 go run .
```

After installing the documented Playwright/browser versions in the verification
environment, run from repository root:

```sh
python3 scripts/dev/workshop_browser_smoke.py --base-url http://127.0.0.1:18080 --browser all --output /tmp/autodata-workshop-browser
```

Intercept `/auth/session`, `/auth/login`, `/auth/callback`, `/auth/logout` and
catalog/media requests before opening Workshop using the R5 deterministic
contract. Use only synthetic fixture credentials. R6 separately runs Go →
ingestion → database/object-store acceptance
and authenticated two-bank canaries. Embedded asset changes require a rebuilt
binary/container or API restart under Base44.

## Handoff, risks, and incomplete release requirements

Record actual SHAs, commands/exits, fixture hashes, coverage, review findings,
and R5/R6 dependencies. Never combine results from different heads or mark the
parent release complete on helper/browser fixtures alone.

R5's [access plan](2026-11-03-production-access.md) defines the OIDC server-session
contract; R4 consumes its exact routes and removes browser demo authentication.
R5 verifies existing access/media withdrawal rules. R3/R4 neither choose an
external identity vendor nor introduce
billing policy. Public tracking describes security outcomes; detailed findings
follow `SECURITY.md`.

Review risks include changed completeness semantics for old clients, unresolved
legacy aliases, source/asset policy consistency, cross-replica durable scheduling,
and mixed content/revision responses. Temporary source failure, rejected rewrite,
missing media, or unavailable browser coverage remain explicit; none is converted
into fabricated completion.

### Post-migration R3 binding refinement

The independently reviewed [runtime handoff refinement](2026-11-03-catalog-runtime-integration.md#post-migration-refinement-independently-reviewed) now specifies actual captured fresh/empty/populated replay through038, supported Compose invocation, existing module manifests/cache packaging and actual CLI versus one-shot publication-hook process handling. It preserves R3's32-path scope and exact eight required cases. Older raw component commands are illustrations; only the bounded supervisor with complete no-skip/provenance checks certifies required acceptance. Actual CI and fresh synchronized preflight remain prerequisites.

### R3 synchronized dispatch record

This record applies only to R3. R4 and R5 retain their own dependency gates.

```json
{
  "goal": "Serve immediate readable source fallback with honest processing state until a canonical rewrite is published.",
  "plan_ref": "docs/superpowers/plans/2026-11-03-source-fallback-web.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/superpowers/specs/2026-11-03-production-release-orchestration-design.md",
    "docs/superpowers/plans/2026-11-03-production-release-orchestration.md"
  ],
  "todo": [
    "A cold read returns available sanitized source while model processing is blocked.",
    "Repeated reads join the same durable job and transition atomically at publication.",
    "Canonical-only descriptors and scoped legacy rows are listed without collapsing equal provider-local IDs across banks; each public UUID resolves to the correct detail, with zero detail work during list/search.",
    "Nonempty partial/failed indexes remain explicitly incomplete and retryable.",
    "Both-bank source views retain ordered tables, warnings and local media or unavailable placeholders.",
    "Canonical/source/job/media paths preserve vehicle scope, access rules and takedown behavior.",
    "OpenAPI JSON and YAML describe the complete selection cascade and additive lifecycle fields.",
    "Required Go/Python integration captures full shared-runner fresh001\u2013038 application and empty/populated no-op replay, uses the actual migrated R2 HTTP/worker fixture and owned Go/Python image, and passes the bounded supervisor exact-eight/no-skip JUnit/Go/provenance checks; missing infrastructure, timeout, partial evidence or image/hash mismatch fails."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-03T11:30:36.636100+00:00"
}
```


### Unified paid customer UI planning checkpoint

The canonical `docs/superpowers/plans/2026-11-03-workshop-customer-ui.md`
replaces the future auth-only R4 dispatch with one33-path customer lane after
verified identity039, commerce040 and paid-access integration. It preserves the
original18 browser scenarios and ordered reader/source/media requirements,
adding Google cookie sessions, server-priced checkout and permanent library.
Its120 DTO/browser and21 real API/browser cases are distinct evidence.
Actual production assets, pinned official SDK storage, real settlement/grants
and source/media access must be verified; no browser redirect or local state
grants ownership. Task/record remain waiting for dependencies and a fresh gate.
