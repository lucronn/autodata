# Canonical Article Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. The coordinator dispatches only after the repository planning gate passes at each pinned implementation base.

**Goal:** Use both banks independently, publish one validated rewritten revision per source item and transformation version, and retain readable source content throughout pending or failed processing.

**Architecture:** Extend the existing source blob store and `source_fetch_jobs` queue with provider-scoped canonical identities, immutable source/canonical revisions, leased work, and atomic publication/outbox writes. The API reads one PostgreSQL view; it schedules durable work without waiting for source or model IO. Both banks independently populate catalog coverage, with no cross-bank article deduplication or substitution.

**Tech Stack:** Python 3.12+, PostgreSQL 17/pgvector, psycopg 3, existing Mercury-2 client, NATS JetStream, S3-compatible storage, existing ordered article JSON, pytest, Docker Compose.

**Spec:** [Canonical article lifecycle design](../specs/2026-11-03-canonical-article-lifecycle-design.md)

**Parent plan:** [Production release orchestration](2026-11-03-production-release-orchestration.md)  
**Project:** https://github.com/users/lucronn/projects/8

**Issue:** https://github.com/lucronn/autodata/issues/186  
**Inspected baseline:** `0ed449fe5119484f8dd8f40b40607aa3beb11e49`

## Global Constraints

- Implementation and review agents use **GPT-6.1 Sol**, **medium** reasoning, **Fast / priority** service, as explicitly requested by the user.
- One canonical article per provider, exact opaque source vehicle/article refs and canonical vehicle/configuration scope; no title/suffix guessing or cross-bank content deduplication.
- Both banks independently contribute catalog rows and coverage. One successful bank cannot mark the other complete.
- Source projection/media and published canonical content are immutable; body/steps/images are projections of the ordered document.
- Keep technical facts, warnings, applicability, block IDs/order, tables, image positions and evidence intact; unchanged or unsafe rewrite remains source with explicit review state.
- Use PostgreSQL leases/fencing and unique keys, with one winning revision/event and honest ambiguous external-call accounting.
- Source projection persistence and transition of the same durable job to transformation commit atomically.
- Completed warm reads/ensures perform zero source, asset, model and scheduling calls. Source refresh is explicit and versioned.
- Generated canonical content remains `UNREVIEWED` until authorized review; validation does not approve it.
- Do not edit migrations 001–036, remove legacy observations, call live services in deterministic tests, expose secrets, or deploy production.
- Plans are not execution authority. R1 tasks 1–4 are independently verified and integrated at `c3b7a46d1233a1af8c0f0cba19a2f169d5a9a4b4`. R2 tasks 5–8 require this fresh synchronized checkpoint and committed-base preflight before implementation; later dependencies remain blocked.

## Concrete todo

- [x] Coordinator creates/verifies the actual release Issue, adds Project #8 item, updates canonical docs/task records with the same goal and work list, commits the checkpoint, and records successful preflight.
- [x] Deliver additive lifecycle schema, deterministic identity and isolated PostgreSQL fixture harness.
- [x] Implement provider-bound capture, both-bank catalog coverage and durable job leases.
- [ ] Integrate conservative Mercury rewriting with recursive preservation validation and durable model-result recovery.
- [ ] Publish canonical revision/current pointer/job/outbox atomically with fenced delivery.
- [ ] Connect scheduling-only ensure, background worker and legacy mapping paths; freeze the SQL read view for R3.
- [ ] Pass the exact race, restart, warm-call, source-refresh and migration matrix; record independent review at one implementation SHA.

## Verified R1 handoff and R2 dispatch boundary

R1 exact candidate `330c29c0a1b2b7d43745dd9b2ba93cf1f9055e09` is integrated
at `c3b7a46d1233a1af8c0f0cba19a2f169d5a9a4b4`, with independent review and
644 ingestion tests plus 25 subtests. The
[verification record](../../verification/2026-11-03-canonical-article-lifecycle.md)
records scope and retained evidence. Tasks 1–4 are complete; their checklist
examples below remain implementation and regression references.

R2 consumes `load_source_revision`, `load_article_state`, and
`source_job_persistence.lock_live_lease`. Source capture uses
`put_object(key, bytes, media_type)`. It retains captured context, resolution
snapshot identity, provider ownership, and persisted snapshot references.
Unchanged terminal transforms retain their original owner and exhausted budget.
Configure the real S3 adapter with connect timeout 2 seconds, read timeout
5 seconds, and zero SDK retries, as required in Task 7. Late content-addressed
blob writes must never carry database mutations after a lease expires.
Migrations 037/038 are frozen. Any schema defect requires a separately reviewed
new migration and a refreshed dependency checkpoint.

R2 is dispatched directly by the coordinator after its committed task record
passes `pre_implementation.validate_record`; it does not invoke an uncertified
local CLI or receive release authority. Its exact allowed paths are in
`docs/agents/tasks/2026-11-03-production-release/r2-rewrite.json`. Complete tasks
5–8 and independently review the resulting SHA before R3 begins.

## File ownership and dependency order

All paths below are repository-relative. The coordinator gives each builder only
its listed files. Tasks 1–4 comprise R1; Tasks 5–8 comprise R2. Task 1 precedes
all schema consumers. Tasks 2 and 3 may proceed in separate worktrees after Task
1, then Task 4 integrates their interfaces. Task 5 follows Task 4; Task 6 follows
Task 5. Task 7 owns shared dispatchers after those producers land. Task 8 verifies
the integrated SHA. If a path must change in two tasks, integrate the producer
first and re-pin the consumer; do not run concurrent edits to that path.

R3 consumes the exact `catalog_article_current` columns and ensure response in
the spec. R3 owns public OpenAPI and Go routes. R2 adds the shared lifecycle enum
definitions in `packages/contracts/catalog/v1/article-lifecycle.schema.json`;
R3 subsequently adds public projection fixtures against that committed contract.

Every task uses a real failing regression before implementation, the focused
passing command afterward, and an independent review before integration. Commit
commands below are execution instructions for the authorized builder, not actions
taken while preparing this plan.

## Task 1: Add lifecycle schema and an isolated PostgreSQL test boundary

**Files**

- Create `db/migrations/037_article_source_lifecycle.sql`.
- Create `db/migrations/038_article_transform_publication.sql` with the complete revision/attempt/review/outbox schema, ownership/immutability constraints and final `catalog_article_current` view specified in the design. Serialize both migrations in this task before any consumer.
- Create `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_types.py`.
- Create `workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py` for identity/descriptor/source operations only.
- Create `workers/ingestion-python/tests/lifecycle_support.py` and `workers/ingestion-python/tests/test_article_lifecycle_schema.py`.
- Create `infra/compose/compose.article-lifecycle-test.yaml` and `infra/compose/article-lifecycle-test.Dockerfile`.
- Modify `scripts/dev/test_migrations.py` to enumerate 037/038, and add schema assertions.

**Consumes:** Existing migrations 001–036 and the spec's exact 037/038 table/column definitions.  
**Produces:** `ArticleKey`, `ResourceRef`, `SourceArticleContext`, `CapturedSource`, `JobLease`, `EnsureResult`, `RewriteResult`, `ValidationResult`; deterministic identity helpers; the additive schema; and test fixture `fresh_database(through: int | None = None)` yielding a repository connection factory with `.connect()` and `.database_name`.

- [ ] Write `test_article_lifecycle_schema.py` with real PostgreSQL constraints and preservation checks:

```python
def test_provider_identity_is_unique_without_cross_bank_merging(fresh_database):
    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    first = ArticleKey("bankone", vehicle, None, "same:vehicle", "same/article")
    second = dataclasses.replace(first, provider="banktwo")
    assert article_id(first) == article_id(first)
    assert article_id(first) != article_id(second)
    assert insert_descriptor(repo, first) == insert_descriptor(repo, first)
    assert insert_descriptor(repo, first) != insert_descriptor(repo, second)

def test_upgrade_preserves_imported_legacy_jobs(fresh_database):
    repo = fresh_database(through=35)
    before = seed_legacy_jobs_and_read_invariants(repo)
    apply_migration(repo, 36)
    apply_migration(repo, 37)
    apply_migration(repo, 38)
    apply_migration(repo, 36)
    assert read_imported_job_invariants(repo) == before
```

Define `seed_vehicle`, `insert_descriptor`, `seed_legacy_jobs_and_read_invariants`,
`apply_migration`, and `read_imported_job_invariants` in `lifecycle_support.py`.
The invariant tuple is `(UUID, idempotency_key, vehicle_id, retry_count, status,
selector_snapshot_id, source_snapshot_id, source_locator)`. Fixtures create a
unique database named `lifecycle_test_<uuid>` inside the isolated Compose cluster,
apply sorted migrations through the requested boundary using psycopg in autocommit
mode, and close/drop only their own test database. Refuse any database host or
name outside the fixture configuration.

- [ ] Create a standalone Compose file with only `postgres`, `nats`, `minio`, and
  `test-runner`, a named internal network, private project volumes and no host
  ports. Use `pgvector/pgvector:pg17`, `nats:2.10-alpine`, and the existing pinned
  SeaweedFS image `ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`
  with `mini -dir=/data -s3.port=9000`. Test-only credentials are fixed local
  fixture values, never host environment fallbacks. No application volumes or
  `/run/base44/app.env` mount. Build the runner on Python 3.14 slim with the current
  worker dependencies plus `pytest>=8,<10`; mount the repository read-only at
  `/workspace`, set both worker sources/contracts on `PYTHONPATH`, and mount
  `${AUTODATA_LIFECYCLE_ARTIFACT_DIR}` at `/artifacts`. Runtime external networking
  is blocked; dependency/image downloads occur only during build/pull.
  Set `PYTHONDONTWRITEBYTECODE=1` and use `-p no:cacheprovider` so tests do not
  require writes to the read-only checkout.

- [ ] Start the isolated services and run the new schema test, expecting missing
  module/table failure before implementation:

```bash
export AUTODATA_LIFECYCLE_ARTIFACT_DIR="$(mktemp -d /tmp/autodata-article-lifecycle.XXXXXX)"
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml up -d --build --wait postgres nats minio
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml run --build --rm test-runner python -m pytest -q -p no:cacheprovider workers/ingestion-python/tests/test_article_lifecycle_schema.py
```

- [ ] Implement the spec's 037/038 schemas, identity/descriptor store, and immutable
  types. The identity implementation must preserve opaque strings exactly:

```python
def identity_payload(key: ArticleKey) -> dict:
    return {
        "provider": key.provider,
        "vehicle_id": str(key.vehicle_id),
        "vehicle_configuration_id": (
            str(key.vehicle_configuration_id) if key.vehicle_configuration_id else None
        ),
        "source_vehicle_ref": key.source_vehicle_ref,
        "source_article_ref": key.source_article_ref,
    }

def article_id(key: ArticleKey) -> UUID:
    encoded = json.dumps(identity_payload(key), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:article:v1:{digest}")
```

Include negative SQL tests for wrong configuration ownership, duplicate identity,
cross-article source pointer, malformed hashes, source mutation and lease checks
on new jobs. Imported `legacy_batch` rows remain outside new execution checks.

- [ ] Run the schema test above and
  `python3 -m unittest discover -s scripts/dev -p 'test_migrations.py' -v`.
  Expected: clean/upgrade/rerun assertions pass; no legacy row rewritten.
- [ ] Review and commit only the Task 1 files with message
  `feat: add provider-scoped article lifecycle schema`.

## Task 2: Bind connector resources and source projection to the issuing bank

**Files**

- Create `workers/ingestion-python/src/autodata_ingestion/source_article_capture.py`.
- Modify `source_connector_client.py`, `source_adapters.py`, `procedure_images.py` in the same source directory.
- Create `workers/ingestion-python/tests/test_source_article_capture.py`.
- Modify `workers/ingestion-python/tests/test_source_connector_client.py` and `test_procedure_images.py`.
- Create `scripts/dev/source_connector_fixture_server.py`.

**Consumes:** Task 1 types. `SourceArticleContext` contains `ArticleKey`, exact
descriptor and raw descriptor/resolution snapshot/evidence bindings.  
**Produces:** `capture_source_article(context, *, registry, object_store,
deadline_seconds=30.0) -> CapturedSource`; explicit `ResourceRef` localization;
`SourceEnvelopeV1.raw_envelope` preserving exact list/resolution JSON bytes.

- [ ] Add a real adapter test for vehicle-free HTML and provider ref collisions:

```python
def test_banktwo_plain_html_uses_resolved_descriptor_context(capture_fixture):
    context = capture_fixture.context("banktwo", article_ref="same/article")
    capture_fixture.body("banktwo", b"<ol><li>Remove the pump.</li></ol>", "text/html")
    captured = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    assert captured.context.key == context.key
    assert captured.source_document["blocks"]
    assert "Remove the pump." in captured.source_body
    assert capture_fixture.calls("bankone") == []

def test_same_asset_ref_never_crosses_provider(capture_fixture):
    for provider in ("bankone", "banktwo"):
        context = capture_fixture.context(provider, asset_ref="opaque:shared/asset")
        capture_source_article(context, registry=capture_fixture.registry,
                               object_store=capture_fixture.objects)
        assert capture_fixture.resource_calls(provider, "opaque:shared/asset") == 1
```

`capture_fixture` is a pytest fixture using two real loopback HTTP servers with
different bearer tokens and different byte responses for the same opaque ref.
It exposes `context`, `body`, `registry`, `objects`, `calls`, and `resource_calls`
as used above. Use the actual connector/parser/hash-validation code. Only the
object store is an in-memory byte sink in unit tests; Task 8 uses real S3.

- [ ] Run `python3 -m pytest -q -p no:cacheprovider workers/ingestion-python/tests/test_source_article_capture.py`.
  Expected before implementation: missing capture function or rejected Banktwo
  vehicle-free body; preserve the failure output.
- [ ] Implement provider-bound cached resource reads and a shared typed adapter
  path. The minimum resource cache algorithm is:

```python
def read_bound(ref: ResourceRef):
    if ref not in resources:
        envelope = registry[ref.provider].read_resource(ref.opaque_ref)
        resources[ref] = envelope.to_source_resource()
    return resources[ref]
```

Pass captured bytes into image localization; remove default-Banktwo routing and
prefix inference. Do not refetch descriptor assets during localization. Treat
inline HTML/PDF raw bytes as source data; add descriptor/resolution context
outside the raw blob. Explicit contradictory vehicle identity fails review.
Merge descriptor and body-declared asset refs in source order, dedupe exact
provider/ref pairs, preserve media placeholders and evidence. Enforce a 30-second
whole capture deadline, at most four asset requests and remaining-time per-call
timeouts. Optional labor failure does not discard a readable article.

- [ ] Store exact raw body/index envelopes and produce immutable source document,
  images/body/steps, evidence manifest and fingerprint with explicit failed asset
  entries. Reject title-only/empty content. Test scripts/unsafe links/provider URLs
  are not present in the public source projection. Original raw bytes and their
  hash remain unchanged. Do not enable arbitrary-URL identity bypass.
- [ ] Run the capture, connector and image tests, including corrupt hash,
  malformed envelope, duplicate refs, asset deadline, plain text, HTML, JSON and
  fixture PDF. Expected: both providers use their own tokens/origins and one fetch
  per unique resource on success.
- [ ] Review and commit the Task 2 paths with message
  `feat: capture provider-bound source articles and immutable source views`.

## Task 3: Implement durable article and catalog job leases

**Files**

- Create `workers/ingestion-python/src/autodata_ingestion/source_job_persistence.py`.
- Create `workers/ingestion-python/tests/test_source_job_persistence.py`.
- Extend `workers/ingestion-python/tests/lifecycle_support.py` with process barriers.

**Consumes:** Task 1 queue schema and typed `JobLease`/`EnsureResult`.  
**Produces:** Exact job functions in the spec: `ensure_article_job`,
`refresh_article_job`, `claim_source_job`, `heartbeat_source_job`,
`advance_source_job`, `fail_source_job`; `LeaseLost` on all stale-owner mutations.

- [ ] Add real PostgreSQL tests for same-key ensure and stale publication fencing:

```python
def test_twenty_ensures_create_one_active_job(article_repo):
    article = article_repo.seed_article()
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(article_repo.ensure_in_child, [article] * 20))
    assert len({result["job_id"] for result in results}) == 1
    assert article_repo.count_active_jobs(article) == 1

def test_expired_lease_cannot_advance(article_repo):
    article_repo.ensure_seed_article()
    first = claim_source_job(article_repo, worker_id=uuid.uuid4())
    article_repo.expire_lease(first.job_id)
    second = claim_source_job(article_repo, worker_id=uuid.uuid4())
    assert second.token == first.token + 1
    with pytest.raises(LeaseLost):
        advance_source_job(article_repo, first, phase="normalizing", checkpoint={})
```

`article_repo` wraps the test repository plus deterministic seed/count helpers;
`ensure_in_child` reconnects using an explicit fixture DB configuration, never a
shared psycopg connection. `expire_lease` updates only the isolated test row's
lease timestamp, avoiding sleeps. Add a separate barrier test where lease expiry
happens while a worker is paused immediately before its SQL write.

- [ ] Run the new DB test in the isolated runner. Expected: absent module/functions.
- [ ] Implement spec SQL claim with `FOR UPDATE SKIP LOCKED`, database timestamps,
  90-second leases, 10-second heartbeats, monotonic tokens and status/owner/token/
  expiry checks on every mutation. Use a canonical-row lock for ensures and a
  short transaction for claims. Return an existing completed current revision
  before creating work. Use this guard in the write transaction:

```sql
SELECT source_fetch_job_id FROM source_fetch_jobs
WHERE source_fetch_job_id = %s AND status = 'processing'
  AND lease_owner = %s AND lease_token = %s
  AND lease_expires_at > clock_timestamp()
FOR UPDATE;
```

No matching row raises `LeaseLost`; callers cannot continue with an unfenced
checkpoint. Clear lease fields on terminal transition. Increment `retry_count`
once per claim, preserve it on heartbeat, and keep imported `legacy_batch` rows
unclaimable. Reclaimed dispatched model attempts become ambiguous in Task 5.

- [ ] Implement retry deadlines 5/30 seconds and max three total attempts,
  bounded by the frozen policy and existing persistence default;
  clamp Retry-After to 1–900 seconds. Write explicit tests for each claim count,
  nonretryable auth/ambiguity/hash errors, dead-letter transition, restart and
  completed warm ensure with no writes. Worker polling owns retries; HTTP/browser
  retry must not create a new terminal job.
- [ ] Add the expired-final-attempt sweep and its regression. A processing job
  whose third lease expires must become dead-letter without another claim; a
  renewed lease must survive the competing sweep. Test explicit unchanged-source
  reuse for rejected, needs-review and dead-letter transformations, including an
  exhausted model transport job with no revision row. Source inspection preserves
  the new observation but completes with `reused_terminal_result` and
  `reused_transformation_job_id`; its transformation key stays null. The original
  job retains the unique key, error, status and attempt budget. The canonical
  current-job pointer returns to that terminal owner; ensure must reuse it even
  though its generation precedes the inspection generation. A new fingerprint or
  explicit new profile is required for another transformation. Do not add an
  operator retry/reset endpoint or silently increase its attempt budget.
- [ ] Run the DB tests and existing `test_bankone_job_persistence.py`. Expected:
  new lease protocol passes and legacy behavior is preserved until Task 7 wrapper
  integration.
- [ ] Review and commit with message `feat: lease and fence durable source jobs`.

## Task 4: Persist source capture and both-bank catalog coverage

**Files**

- Create `workers/ingestion-python/src/autodata_ingestion/catalog_coverage.py`.
- Extend `article_lifecycle_store.py` for source revisions/observations and atomic job transition.
- Create `workers/ingestion-python/tests/test_catalog_coverage.py` and `test_article_source_persistence.py`.

**Consumes:** Tasks 1–3 types, capture, storage and lease functions.  
**Produces:** `ensure_article_catalog_jobs`, `run_catalog_index_job`, and
`store_captured_source(repo, lease, captured) -> source_revision_id`; union metadata
and durable source-first state without altering shared HTTP dispatchers yet.

- [ ] Add tests proving independent coverage and atomic source/job state:

```python
def test_bankone_success_cannot_hide_banktwo_failure(catalog_runtime):
    catalog_runtime.provider("bankone").set_pages([complete_page("one")])
    catalog_runtime.provider("banktwo").set_error(503)
    catalog_runtime.run_catalog()
    state = catalog_runtime.read_catalog()
    assert [row["source_article_ref"] for row in state["items"]] == ["one"]
    assert state["coverage"]["bankone"]["status"] == "complete"
    assert state["coverage"]["banktwo"]["status"] == "failed"
    assert state["complete"] is False
    assert catalog_runtime.body_and_asset_call_count() == 0

def test_source_commit_never_exposes_a_missing_transform_job(source_runtime):
    source_runtime.pause("before_source_commit")
    assert source_runtime.read_current()["source_revision_id"] is None
    source_runtime.release("before_source_commit")
    source_runtime.await_phase("normalizing")
    state = source_runtime.read_current()
    assert state["content_origin"] == "source"
    assert state["job_id"] is not None
    assert state["document"]["blocks"]
```

`complete_page(ref)` constructs a versioned fixture article page; fixtures use
the actual server from Task 2, DB from Task 1, and lease functions from Task 3.
`read_current` in this task joins source/job tables directly; Task 6 replaces its
SQL with the final view without changing assertions.

- [ ] Run the new tests in the isolated runner; preserve the initial missing
  coverage/source store failures.
- [ ] Implement independent two-bank scheduling, verified scope/ref resolution,
  exact page capture, per-page provenance, idempotent descriptor upsert and
  partial index persistence. Stop at 1,000 pages; repeated/stalled cursors fail.
  `complete=true` requires both bank scopes complete, including complete-empty.
  No body/model reads. Retire absent rows only after that provider completes a
  newer generation. Never retire rows from a failed/partial scan.
- [ ] Implement source storage and fenced atomic transition. Upload verified
  content-hash blobs before the DB transaction; in the transaction lock job and
  canonical identity, check current generation, upsert/select immutable source
  fingerprint, insert the observation, set source/current-job pointers and
  phase `normalizing`. Record exact resource provenance independently of shared
  snapshot adapter metadata. Add rollback injection before every SQL boundary.
- [ ] Test same bytes from two banks share only blob storage, not canonical
  identity/provenance; revision-string-only recapture reuses the source fingerprint;
  asset availability change creates another immutable source revision. Test
  contradictory vehicle data, title-only and missing body fail before readable
  source commit; partial media has positioned explicit placeholders.
- [ ] Run coverage, source persistence, capture and job tests. Expected: each
  source row always has a matching durable job, and either bank's complete list
  remains usable independently.
- [ ] Review and commit with message
  `feat: persist immutable source views and independent bank coverage`.

## Task 5: Integrate Mercury with strict ordered-document validation

**Files**

- Modify `workers/ingestion-python/src/autodata_ingestion/procedure_rewrite.py`, `procedure_normalize.py`, `article_document.py`, and `mercury2.py` for bounded model response reads.
- Create `workers/ingestion-python/src/autodata_ingestion/article_lifecycle.py` for transform stages.
- Consume Task 1's frozen migration 038; this task does not create or edit schema.
- Extend `article_lifecycle_store.py` for candidate/attempt/result writes; `article_lifecycle_types.py` only for the already-specified type fields.
- Modify `workers/ingestion-python/tests/test_procedure_rewrite.py`, `test_article_document.py`, `test_mercury2.py`.
- Create `workers/ingestion-python/tests/test_article_transform.py`.

**Consumes:** Persisted immutable source revision and current fenced lease.  
**Produces:** `rewrite_ordered_document`, `validate_article_rewrite`, enhanced
`rewrite_procedure_article`, durable attempts/results, `run_article_job` stages
through validation, and bounded response reads in the existing Mercury client.

- [ ] Add source-shape and strict-validator tests:

```python
@pytest.mark.parametrize("mutation", [
    "torque", "unit", "tool_id", "part_id", "warning", "negation",
    "applicability", "table_cell", "block_order", "image_position", "evidence",
])
def test_technical_or_structure_mutation_never_validates(document_fixture, mutation):
    candidate = document_fixture.mutate(mutation)
    result = validate_article_rewrite(document_fixture.source, candidate,
                                      profile_version="technical-prose-v1")
    assert result.passed is False

def test_valid_phrase_change_preserves_full_document(document_fixture, model_fixture):
    model_fixture.replace("Remove the pump.", "Take off the pump.")
    result = rewrite_ordered_document(document_fixture.source,
        client=model_fixture.client, context={}, profile_version="technical-prose-v1")
    assert result.changed_slots
    assert protected_projection(result.document) == protected_projection(document_fixture.source)
    assert result.document["blocks"][2]["type"] == "table"
```

`document_fixture` includes headings, plain paragraphs, ordered/unordered lists,
steps, nested table cells, captions, warning, links, local images and evidence.
`protected_projection` is the validator's canonical projection of protected text,
all noneditable fields and recursive block skeleton. Unit-test its output against
literal expected JSON so the mutation tests do not merely repeat implementation.

- [ ] Run transform/document/rewrite/Mercury tests before changes. Expected: new
  document-slot integration and recursive validation tests fail on current code.
- [ ] Implement the spec's exact editable-slot schema and reuse conservative
  phrase validation. Preserve `rewrite_steps_for_diy` compatibility, but make
  `rewrite_procedure_article` delegate to the authoritative ordered document path.
  Reject extra/missing/duplicate paths, unknown blocks, absent evidence, reordered
  content, unsafe mutations, unchanged output and no-editable-slot input with
  stable review codes. Regenerate body/steps/images from the accepted document;
  never flatten tables or detached images into compatibility steps.
- [ ] Bound source prompt at 200 KiB and model response at 1 MiB; no truncation.
  Write tests with actual byte streams exceeding the limit. Store provider/model/
  profile/prompt hashes and validation report. The transform stage is:

```python
source = store.load_source_revision(lease.source_revision_id)
normalized = normalize_procedure_article(source.as_article())
store.save_normalized_input(lease, normalized)
attempt = store.prepare_rewrite_attempt(lease, normalized)
store.mark_rewrite_dispatched(lease, attempt)
result = rewrite_ordered_document(normalized["normalized_document"],
    client=model_client, context=source.vehicle,
    profile_version=lease.rewrite_profile_version)
store.store_rewrite_result(lease, result)
validation = validate_article_rewrite(normalized["normalized_document"],
    result.document, profile_version=lease.rewrite_profile_version)
store.store_validation(lease, validation)
```

The `store` methods above are private operations within `article_lifecycle_store.py`
with the same `JobLease` guard as its public functions. Extend `JobLease` with
the versions specified in the schema; do not derive versions from environment
after a job is claimed. Missing configuration/unsafe/unchanged results become
`needs_review`; transient transport errors use the bounded retry policy. Successful
result and validation checkpoints are reused on restart.

R2 also owns `source_job_persistence.py` and
`tests/test_source_job_persistence.py` for recovery accounting after R1 is
integrated. Before reclaiming an expired lease or sweeping an exhausted job to
`dead_letter`, mark its dispatched attempt without a persisted result as
`ambiguous` in the same recovery transaction. Cover a crash on the final allowed
claim as well as a retryable claim. This recovery path must work after lease
expiry; it cannot depend on the expired worker's live-lease store operations or
reset the job's retry budget.

- [ ] Kill a child process after model dispatch before result commit and assert
  an ambiguous attempt record on recovery; kill after result commit and assert
  zero additional model requests. Publish is still disabled until Task 6.
- [ ] Run focused unit/DB transform suites and migration tests. Review and commit
  with message `feat: persist validated ordered article rewrites`.

## Task 6: Publish atomically and freeze the R3 read contract

**Files**

- Complete `article_lifecycle_store.py` publication and `article_lifecycle.py` orchestration.
- Consume migration 038's frozen view and constraints from Task 1; do not revise an integrated migration. If testing reveals a schema defect, stop integration, add a new numbered migration through the coordinator and re-pin consumers before continuing.
- Modify `workers/enrichment-python/src/autodata_enrichment/outbox.py` and `workers/enrichment-python/tests/test_outbox.py`.
- Modify `packages/contracts/contract.json`, `scripts/contracts/generate.py`, and `scripts/contracts/test_contracts.py` for the separate `catalog.article.published` envelope. Regenerate `packages/contracts/python/autodata_contracts/contracts.py` and `packages/contracts/go/contracts.go`; extend `packages/contracts/go/contracts_test.go`. Preserve dataset-specific requirements and pass generator-drift checks rather than hand-editing generated bindings alone.
- Create `packages/contracts/catalog/v1/article-lifecycle.schema.json` with shared state/origin/review enums; R3 extends public response definitions after this interface commit.
- Create `workers/ingestion-python/tests/test_article_publication.py`.

**Consumes:** Validated candidate, immutable source, fenced lease and 038 tables.  
**Produces:** `publish_article_revision(repo, lease, revision_id) -> UUID`, exact SQL
view columns listed in the spec, stable catalog event envelope/subject and fenced
at-least-once outbox delivery. No changes to Go HTTP or Workshop in this task.

- [ ] Add publication rollback and uniqueness tests:

```python
@pytest.mark.parametrize("point", ["revision", "pointer", "job", "outbox"])
def test_publication_failure_rolls_back_every_effect(validated_runtime, point):
    validated_runtime.fail_transaction_after(point)
    with pytest.raises(InjectedFailure):
        validated_runtime.publish()
    assert validated_runtime.published_revision_count() == 0
    assert validated_runtime.current_origin() == "source"
    assert validated_runtime.publication_event_count() == 0

def test_publication_replay_is_one_revision_and_one_event(validated_runtime):
    first = validated_runtime.publish()
    second = validated_runtime.replay_completed_job()
    assert first == second
    assert validated_runtime.published_revision_count() == 1
    assert validated_runtime.publication_event_count() == 1
```

`validated_runtime` uses a genuine completed validation row and two independent
connections; injection points raise immediately after the named SQL statement
inside the publication transaction. Add stale-token and older-generation tests
that release a paused worker after a new owner/source generation exists.

- [ ] Run the new DB tests, expecting absence of publication/view behavior.
- [ ] Implement the single transaction in the spec: lock job then canonical row,
  assert lease/generation/source/profile/candidate hashes, publish immutable
  revision, move pointer, complete job and insert event. Use the unique event key
  and select the existing revision on replay. Set `UNREVIEWED`, never `APPROVED`.
  Publication content mutations must fail in PostgreSQL, not only Python.
- [ ] Verify `catalog_article_current` exactly as agreed with R3. Add literal
  expected-row tests for source pending, source failed/review, canonical complete,
  updated source pending, cold queued/no content, retryable no content, terminal
  no content, rejected canonical review, retired membership and takedown. Expose
  no fake completed state when the job only captured source.
- [ ] Extend the outbox envelope by event type, preserving dataset requirements.
  Catalog event shape is:

```json
{
  "event_id": "UUID", "event_type": "catalog.article.published", "event_version": 1,
  "occurred_at": "UTC timestamp", "producer": "ingestion-worker",
  "correlation_id": "UUID", "idempotency_key": "catalog.article.published:SHA256",
  "canonical_article_id": "UUID", "source_revision_id": "UUID",
  "canonical_revision_id": "UUID", "review_status": "UNREVIEWED"
}
```

This is a shape example, not fixture values; tests generate actual valid UUIDs,
hashes and timestamps. Add `AUTODATA_CATALOG` stream with `catalog.>` subjects;
existing `AUTODATA` dataset stream stays unchanged. Lease/fence outbox claims and
delivery updates, use stable `Nats-Msg-Id`, and recover an expired delivery claim.
Broker outage cannot undo a published DB revision. A test subscriber records
idempotency keys under a unique constraint and counts one logical event after
ACK-before-mark crash/redelivery.

- [ ] Run publication DB tests, enrichment outbox tests and contract tests. Record
  the finalized view/enum/interface SHA for R3 before consumers start.
- [ ] Review and commit with message
  `feat: publish article revisions and lifecycle events atomically`.

## Task 7: Connect scheduling-only ensure, worker loop and legacy mappings

**Files**

- Modify `workers/ingestion-python/src/autodata_ingestion/catalog_service.py`, `worker.py`, `http_service.py`, `bankone_batch.py`, `bankone_job_persistence.py`.
- Create `scripts/dev/backfill_article_lifecycle.py` and `scripts/dev/article_worker.py`.
- Modify corresponding existing ingestion tests; create `workers/ingestion-python/tests/test_article_worker.py` and `scripts/dev/test_backfill_article_lifecycle.py`.
- Update `docs/architecture/independent-bank-connectors.md`, `article-catalog-list-only-hydration.md`, and `normalized-article-document.md` after verified implementation.
- Runtime service deployment changes are owned by R6; publish the required worker command/env contract here so R6 cannot omit the worker.

**Consumes:** Tasks 1–6 public functions and SQL view.  
**Produces:** Scheduling-only internal ensure; `run_article_worker_once`; continuous
`python scripts/dev/article_worker.py` (one-second polling); generic batch
compatibility; offline alias/backfill tool with explicit reviewed mappings.

The R1 capture boundary bounds caller waiting, but an already-running upload
cannot be forcibly cancelled. R2's real object-store adapter must configure
bounded connection/read timeouts and disable unbounded SDK retries (initial
limits: two-second connect, five-second read, zero automatic retries). Keep
all upload effects content-addressed and outside database transactions. Exercise
actual SDK storage exceptions and delayed responses: optional image failures
retain partial readable source, required body failure is fatal, and a timed-out
or stale worker cannot commit observations or publish. Do not treat the caller
deadline alone as a bound on background network/thread lifetime.

- [ ] Add an internal HTTP regression that blocks all provider/model functions
  and asserts durable acceptance completes before they are invoked:

```python
def test_ensure_only_schedules(internal_service, runtime):
    runtime.block_all_external_calls()
    response = internal_service.ensure_article(runtime.article_id, timeout=2)
    assert response.status_code == 202
    assert response.json()["job_id"] == runtime.current_job_id()
    assert response.json()["state"] == "queued"
    assert runtime.external_call_count() == 0
```

`internal_service` starts the actual existing `http_service.make_handler` with a
fixture internal token. `runtime` is the process/DB fixture described in Task 8.
Add a completed warm ensure test asserting it returns the persisted job/revision
and performs no new scheduling/write. Existing raw URL and noncatalog routes
retain their separately tested behavior.

- [ ] Run HTTP/catalog tests and retain the expected blocking/current synchronous
  behavior failure before replacing the dispatcher.
- [ ] Route `scope=articles` to two provider coverage jobs and `scope=article` to
  exact canonical/alias resolution plus `ensure_article_job`. Return this wire
  shape; do not return provider content or infer success from HTTP status alone:

```json
{
  "job_id": "durable job UUID",
  "state": "queued",
  "canonical_article_id": "canonical UUID",
  "source_revision_id": null,
  "retry_after_seconds": 1
}
```

Return 202 for accepted pending work, 200 for existing readable/complete state,
409 for terminal identity/review failures and 503 for scheduling dependency
failure. A 202 always has a real committed job. R3 rereads the DB after this
acknowledgement. Remove complete-result process cache authority and primary-first
selected-article substitution; preserve selector behavior outside article scope
until its own tests prove a replacement.

- [ ] Implement worker dispatch by `job_kind` and persisted phase. Capture once,
  resume normalization/rewrite/validation/publication from checkpoints, heartbeat
  during IO, and stop on `LeaseLost`. CLI options are `--once`, `--poll-seconds`
  (default 1), and `--worker-id` (generated UUID if omitted). Configuration uses
  existing DB/S3/bank/Mercury variables; no defaults that enable live providers in
  fixture mode. R6 adds a distinct `article-worker` process to production Compose
  and Kubernetes; it must not depend on an HTTP request remaining open.
- [ ] Stop legacy table writes. Keep `bankone_job_persistence.py` as compatibility
  functions delegating valid new work to the generic store; imported legacy jobs
  without explicit refs return a binding-review result without mutation. Do not
  quietly restart a historical `processing` row as new article work.
- [ ] Implement offline backfill (`--mapping-file`, `--dry-run` default, `--apply`)
  with exact provider/refs/scope proof, source snapshot projection and queued job
  creation in one transaction. Write literal tests for wrong vehicle, duplicate
  mapping, equal-title different-bank, missing proof and replay. Emit counts of
  mapped, already mapped, quarantined and unresolved rows with no source text or
  credentials. Never use fuzzy matching or fetch live sources in the tool.
- [ ] Run the worker/HTTP/catalog/backfill tests and the previously passing focused
  ingestion suites. Update architecture docs with actual verified commands/SHA,
  then review and commit with message `feat: run durable article ingestion from catalog requests`.

## Task 8: Prove races, restart recovery, warm reuse and source refresh

**Files**

- Create `workers/ingestion-python/tests/test_article_lifecycle_integration.py`.
- Extend `workers/ingestion-python/tests/lifecycle_support.py` with the complete runtime fixture.
- Create `scripts/dev/article_lifecycle_smoke.py` and `scripts/dev/test_article_lifecycle_smoke.py`.
- Extend `scripts/dev/source_connector_fixture_server.py` and the isolated Compose runner only as required by the matrix.
- Create `docs/verification/2026-11-03-canonical-article-lifecycle.md` after execution; record real results, not planned passes.

**Consumes:** Integrated R1/R2 SHA.  
**Produces:** JUnit/JSON evidence with exact SHA, test IDs, resource/model call
counts, lifecycle transitions, DB invariants and outbox keys; no live credentials
or real source bodies. An independent reviewer evaluates this exact SHA.

The `runtime` fixture creates a unique test database, two real loopback connector
HTTP servers, a Mercury-compatible loopback server, S3 client and NATS client.
`start_workers(2)` launches two `article_worker.py` subprocesses with an explicit
environment containing only test endpoints/tokens. Its control surface is
`pause(point)`, `release(point)`, `kill_worker(worker_id)`, `expire_lease(job_id)`,
`await_phase(phase)`, `read_current()`, `refresh(actor,reason)`, and `counters()`.
Barriers exist at `before_source_commit`, `after_source_commit`,
`after_model_dispatch`, `after_model_result_commit`, `inside_publication`,
`after_publication_commit`, and `after_outbox_ack`. They are dependency-injected
test hooks, not production environment flags allowing arbitrary code execution.
All waits have ten-second local deadlines and diagnostic dumps on failure;
deadline/backoff tests alter isolated DB timestamps rather than sleep for minutes.

- [ ] Add the 10 acceptance groups from the spec as individually named tests.
  A concrete warm/revision test is:

```python
def test_warm_restart_is_provider_and_model_free(runtime):
    runtime.start_workers(2)
    first = runtime.ingest_to_publication("bankone")
    runtime.restart_workers()
    runtime.reset_counters()
    for _ in range(100):
        assert runtime.read_current()["canonical_revision_id"] == first
        assert runtime.ensure()["job_id"] == runtime.current_job_id()
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}

def test_changed_source_keeps_identity_and_old_revision_immutable(runtime):
    original = runtime.ingest_to_publication("banktwo")
    identity = runtime.article_id
    runtime.change_fixture_body(b"<ol><li>Remove the cover.</li></ol>")
    runtime.pause("after_source_commit")
    runtime.refresh(actor="fixture-operator", reason="changed source")
    runtime.await_phase("normalizing")
    assert runtime.read_current()["content_origin"] == "source"
    assert runtime.article_id == identity
    runtime.release("after_source_commit")
    updated = runtime.await_publication()
    assert updated != original
    assert runtime.original_revision_unchanged(original)
```

Add the explicit revision-string-only refresh case: same source fingerprint and
canonical revision, extra provenance observation, zero additional model requests.
The 20-request race requires one successful source/model invocation under a valid
lease; ambiguous model-dispatch crash permits another call but requires an
`ambiguous` attempt and exactly one revision/event.

- [ ] Add the real-PostgreSQL regression
  `test_unchanged_refresh_reuses_exhausted_transform_without_reset`. Start two
  worker processes, capture a readable Banktwo source, and make the fixture model
  return 503 for three claimed attempts. Advance only this fixture job's DB retry
  timestamps to make each next claim due. Assert `dead_letter`, `retry_count=3`,
  `max_attempts=3`, a nonnull unique transformation key, no published revision and
  no publication event. Record source/observation counts and the terminal job ID.
  Make the model fixture healthy, reset call counters, and explicitly refresh the
  same source/profile. Wait for that inspection job to complete; assert its
  transformation key is null and checkpoint names the original terminal owner.
  Assert exactly one new provenance observation, the same source revision,
  original key/status/error/attempt values, zero model requests, no new transform
  revision/event, and readable `content_origin=source` with processing
  `failed/retryable=false`. Restart both workers and perform 100 ensures; they
  return the original terminal job with zero provider/asset/model/schedule calls.
  Separately refresh changed source and a new explicit profile to prove only a
  different transformation key can start new transform work. Run the targeted
  regression before the complete integration suite:

```bash
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml run --build --rm test-runner python -m pytest -q -p no:cacheprovider workers/ingestion-python/tests/test_article_lifecycle_integration.py::test_unchanged_refresh_reuses_exhausted_transform_without_reset
```

- [ ] Run isolated commands from the repository root:

```bash
export AUTODATA_LIFECYCLE_ARTIFACT_DIR="$(mktemp -d /tmp/autodata-article-lifecycle.XXXXXX)"
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml config --quiet
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml up -d --build --wait postgres nats minio
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml run --build --rm test-runner python -m pytest -q -p no:cacheprovider workers/ingestion-python/tests/test_article_lifecycle_schema.py workers/ingestion-python/tests/test_source_job_persistence.py workers/ingestion-python/tests/test_article_source_persistence.py workers/ingestion-python/tests/test_article_transform.py workers/ingestion-python/tests/test_article_publication.py workers/ingestion-python/tests/test_article_lifecycle_integration.py --junitxml=/artifacts/lifecycle.xml
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml run --rm test-runner python scripts/dev/article_lifecycle_smoke.py --mode fixture --output /artifacts/lifecycle-smoke.json
```

The smoke command has no live mode or live URL option. It asserts all required
fixture origins are loopback and tests clean+upgrade databases independently.
Evidence includes `git rev-parse HEAD`, fixture identifier, command argv, start/end
time, exit status, expected/measured counts and artifact SHA-256. Any unavailable
DB/S3/NATS/worker makes the run fail rather than silently skip acceptance.
In R2's direct-worker tests `schedule` counts newly created jobs. R3 additionally
proves that a warm public detail read makes zero internal ensure HTTP calls;
calling the ensure API itself during this worker test is not presented as a
DB-only public read.

- [ ] Run bounded regressions and contract checks:

```bash
python3 -m pytest -q -p no:cacheprovider workers/ingestion-python/tests/test_source_connector_client.py workers/ingestion-python/tests/test_catalog_service.py workers/ingestion-python/tests/test_worker.py workers/ingestion-python/tests/test_bundle_persistence.py workers/ingestion-python/tests/test_article_identity.py workers/ingestion-python/tests/test_article_document.py workers/ingestion-python/tests/test_procedure_rewrite.py workers/ingestion-python/tests/test_procedure_images.py workers/ingestion-python/tests/test_bankone_job_persistence.py
python3 -m pytest -q -p no:cacheprovider workers/enrichment-python/tests/test_outbox.py
python3 -m unittest discover -s scripts/dev -p 'test_migrations.py' -v
git diff --check
```

Run Go contract tests from `packages/contracts/go` with `go test ./...`; run the
existing repository contract verifier selected by the parent release plan.
If the host Python lacks runtime dependencies, use the same isolated runner;
do not downgrade a mandatory integration result to a skipped unit test.

- [ ] Capture DB race and kill-point evidence, update architecture/verification
  documents, and request an independent review using GPT-6.1 Sol / medium / Fast
  priority at the exact tested SHA. Resolve substantive findings with a new
  focused test and rerun affected acceptance, then update SHA evidence.
- [ ] Clean only the dedicated fixture project after evidence is retained:

```bash
docker compose -p autodata-article-lifecycle -f infra/compose/compose.article-lifecycle-test.yaml down --volumes --remove-orphans
```

- [ ] Commit only planned test/evidence paths with message
  `test: verify dual-bank article lifecycle recovery and replay`.

## Handoff and release boundary

R1/R2 is ready for R3 integration when migrations 037/038, SQL view, shared enums,
ensure response and all required fixture acceptance are committed and independently
reviewed at one SHA. The coordinator updates the actual Issue/Project item,
canonical docs and machine record; then re-pins R3 and R6 task contracts. Do not
claim success based on the audit's earlier 150 tests or public health probes.

R6 must deploy the dedicated article worker/outbox relay, verify production
configuration and identity policy, exercise authenticated Bankone and Banktwo
canaries and real Mercury behavior, and collect recovery/rollout evidence. Fixture
success and planned commands are not production readiness or deployment approval.

## Migration-runner restart repair dependency

The [reviewed migration-runner plan](2026-11-03-lifecycle-migration-replay.md)
addresses the actual second-run037 failure and031 constraint regression without
editing SQL001–038. Its concrete todo is one shared POSIX/psql driver with a
session advisory lock, existing-version skips, transactional application and
marker checks; delegation from Compose/Base44/native/container/fixture paths;
real fresh/replay/upgrade/concurrent/crash tests; independent exact-SHA review
and actual CI confirmation. Markerless033 is explicitly replayed once using
its unchanged semantics and recorded atomically; the coordinator accepts the
documented reviewer-state/timestamp effects for isolated implementation
acceptance. Production migration remains outside current authority.

This writer waits for verified R2 because the fixture helper is shared, and R3
waits for the verified migration repair. R5 must audit planned039 against the
shared driver at its own scope checkpoint. The external Kubernetes migrator
image has no build source here and remains an explicit R6 certification
prerequisite. No fixture or local pass certifies that external image.

## Verified R2 checkpoint and next runner task

R2 candidate `dba2d96170db5694052bd36dc7fca645fdf0a51d` is independently approved and integrated at `9fd3f9142ee22c47810765130cbc36d6284994a3`. Candidate and integration pass762 tests plus25 subtests without skips; mandatory smoke passes267 tests and35 measured runtime records. See the canonical verification record for exact artifacts and review scope. The shared migration-runner task is now synchronized for a fresh committed-base preflight; it preserves all SQL001–038, explicitly records the reviewed one-time033 adoption and integrates before R3. Production/staging acceptance remains outstanding.
