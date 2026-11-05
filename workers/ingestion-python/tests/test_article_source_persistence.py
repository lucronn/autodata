from dataclasses import replace
import uuid
import pytest
import psycopg
from lifecycle_support import (
    fresh_database,
    insert_descriptor,
    seed_vehicle,
    seed_snapshot,
)
from test_source_article_capture import capture_fixture
from autodata_ingestion.article_lifecycle_types import (
    ArticleKey,
    SourceArticleContext,
    article_id,
    NORMALIZATION_VERSION,
    REWRITE_PROFILE_VERSION,
)
from autodata_ingestion.source_article_capture import capture_source_article
from autodata_ingestion.source_job_persistence import (
    ensure_article_job,
    claim_source_job,
    refresh_article_job,
    fail_source_job,
    LeaseLost,
)


def prepare(repo, fixture, provider="bankone"):
    context = fixture.context(provider)
    context = replace(
        context,
        key=replace(context.key, vehicle_id=seed_vehicle(repo)),
        descriptor_snapshot_id=seed_snapshot(repo),
        resolution_snapshot_id=seed_snapshot(repo),
    )
    insert_descriptor(repo, context.key, descriptor=context.descriptor)
    job = ensure_article_job(
        repo,
        article_id(context.key),
        normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=REWRITE_PROFILE_VERSION,
    )
    lease = claim_source_job(repo, worker_id=uuid.uuid4())
    fixture.body(provider, b"<p>Remove the pump.</p>")
    captured = capture_source_article(
        context, registry=fixture.registry, object_store=fixture.objects
    )
    return context, lease, captured


def test_source_commit_is_atomic_and_immutable(fresh_database, capture_fixture):
    from autodata_ingestion.article_lifecycle_store import (
        store_captured_source,
        load_article_state,
        load_source_revision,
    )

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    before = load_article_state(repo, article_id(context.key))
    assert before["document"] is None
    revision = store_captured_source(repo, lease, captured)
    state = load_article_state(repo, article_id(context.key))
    assert state["source_revision_id"] == revision
    assert (
        state["job_id"] == lease.job_id and state["processing_state"] == "normalizing"
    )
    assert state["content_origin"] == "source" and "Remove the pump." in state["body"]
    assert (
        load_source_revision(repo, revision).as_article()["normalized_document"]
        == captured.source_document
    )
    with pytest.raises(psycopg.Error), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_article_source_revisions SET source_body='changed' WHERE source_revision_id=%s",
            (revision,),
        )
    with repo.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM canonical_article_source_observations"
            ).fetchone()["n"]
            == 1
        )


def test_stale_source_commit_has_no_effect(fresh_database, capture_fixture):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    with repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        )
    with pytest.raises(LeaseLost):
        store_captured_source(repo, lease, captured)
    with repo.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM canonical_article_source_revisions"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("terminal", ["needs_review", "dead_letter", "rejected"])
def test_unchanged_terminal_refresh_reuses_original_budget(
    fresh_database, capture_fixture, terminal
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    revision = store_captured_source(repo, lease, captured)
    if terminal == "rejected":
        insert_transform(repo, lease, revision, status="rejected")
        terminal_status = "needs_review"
        code = "REWRITE_UNCHANGED"
    else:
        terminal_status = terminal
        code = "MODEL_UNAVAILABLE" if terminal == "dead_letter" else "REWRITE_UNCHANGED"
    with repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET status=%s,error_code=%s,retry_count=3,retryable=false,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL WHERE source_fetch_job_id=%s",
            (terminal_status, code, lease.job_id),
        )
        before = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        ).fetchone()
    refresh = refresh_article_job(
        repo, article_id(context.key), actor="fixture", reason="refresh source"
    )
    inspection = claim_source_job(repo, worker_id=uuid.uuid4())
    refreshed = replace(
        captured,
        resource_provenance=[
            {**r, "source_revision": "revision-2"} for r in captured.resource_provenance
        ],
    )
    assert store_captured_source(repo, inspection, refreshed) == revision
    current = ensure_article_job(
        repo,
        article_id(context.key),
        normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=REWRITE_PROFILE_VERSION,
    )
    assert current.job_id == lease.job_id
    with repo.connect() as conn:
        after = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        ).fetchone()
        assert after == before
        row = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (refresh.job_id,),
        ).fetchone()
        assert row["status"] == "completed" and row["transformation_key"] is None
        assert row["checkpoint"]["reused_terminal_result"] is True
        assert row["checkpoint"]["reused_transformation_job_id"] == str(lease.job_id)
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM canonical_article_source_observations"
            ).fetchone()["n"]
            == 2
        )


def test_blob_dedupe_preserves_bank_specific_provenance(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    ids = []
    for provider in ("bankone", "banktwo"):
        context, lease, captured = prepare(repo, capture_fixture, provider)
        ids.append(store_captured_source(repo, lease, captured))
        fail_source_job(repo, lease, code="MODEL_NOT_CONFIGURED", retryable=False)
    assert ids[0] != ids[1]
    with repo.connect() as conn:
        rows = conn.execute(
            "SELECT body_source_snapshot_id FROM canonical_article_source_revisions"
        ).fetchall()
        assert rows[0] == rows[1]
        observations = conn.execute(
            "SELECT resource_provenance FROM canonical_article_source_observations"
        ).fetchall()
        assert {r["resource_provenance"][0]["provider"] for r in observations} == {
            "bankone",
            "banktwo",
        }


def test_legacy_blob_dedupe_remaps_all_evidence_snapshot_references(
    fresh_database, capture_fixture
):
    from copy import deepcopy
    from autodata_ingestion.article_lifecycle_store import (
        store_captured_source,
        load_source_revision,
    )

    repo = fresh_database()
    legacy_body = seed_snapshot(repo, b"<p>Remove the pump.</p>")
    legacy_asset = seed_snapshot(repo, b"shared fixture figure")
    for provider in ("bankone", "banktwo"):
        context, lease, _ = prepare(repo, capture_fixture, provider)
        context = replace(
            context,
            descriptor={**context.descriptor, "asset_resource_refs": ["figure"]},
        )
        capture_fixture.body(
            provider, b"shared fixture figure", "image/png", ref="figure", kind="asset"
        )
        captured = capture_source_article(
            context,
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )
        assert captured.body_source_snapshot_id != legacy_body
        asset_snapshot = next(
            r["source_snapshot_id"] for r in captured.resources if r["role"] == "asset"
        )
        evidence = deepcopy(captured.evidence_manifest)
        evidence[0]["resources"] = [{"source_snapshot_id": asset_snapshot}]
        evidence[0]["source_snapshot_ids"] = [
            str(captured.body_source_snapshot_id),
            asset_snapshot,
        ]
        captured = replace(captured, evidence_manifest=evidence)
        original_evidence = deepcopy(captured.evidence_manifest)
        original_document = deepcopy(captured.source_document)
        revision = store_captured_source(repo, lease, captured)
        saved = load_source_revision(repo, revision)
        assert saved.body_source_snapshot_id == legacy_body
        assert saved.evidence_manifest[0]["body_source_snapshot_id"] == str(legacy_body)
        assert saved.evidence_manifest[0]["resources"][0]["source_snapshot_id"] == str(
            legacy_asset
        )
        assert saved.evidence_manifest[0]["source_snapshot_ids"] == [
            str(legacy_body),
            str(legacy_asset),
        ]
        assert (
            saved.evidence_manifest[0]["evidence_id"]
            == original_evidence[0]["evidence_id"]
        )
        assert saved.source_document == original_document
        assert captured.evidence_manifest == original_evidence
        with repo.connect() as conn:
            observation = conn.execute(
                "SELECT resource_provenance FROM canonical_article_source_observations WHERE source_revision_id=%s",
                (revision,),
            ).fetchone()["resource_provenance"]
            assert {r["provider"] for r in observation} == {provider}
            assert {r["source_snapshot_id"] for r in observation} == {
                str(legacy_body),
                str(legacy_asset),
            }
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM source_snapshots WHERE source_snapshot_id=ANY(%s)",
                    ([legacy_body, legacy_asset],),
                ).fetchone()["n"]
                == 2
            )
        fail_source_job(repo, lease, code="MODEL_NOT_CONFIGURED", retryable=False)


def test_loaded_source_context_is_immutable_after_descriptor_changes(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import (
        store_captured_source,
        load_source_revision,
        upsert_article_descriptor,
    )

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    revision = store_captured_source(repo, lease, captured)
    upsert_article_descriptor(
        repo,
        context.key,
        {"title": "Changed title", "resource_ref": "different"},
        context.descriptor_snapshot_id,
        1,
    )
    stored = load_source_revision(repo, revision)
    assert stored.context.descriptor == context.descriptor
    assert stored.context.resolution_snapshot_id == context.resolution_snapshot_id
    assert stored.vehicle == context.vehicle


class InjectedFailure(RuntimeError):
    pass


class FailingCursor:
    def __init__(self, cursor, owner):
        self.cursor = cursor
        self.owner = owner

    def execute(self, *args, **kwargs):
        self.owner.count += 1
        if self.owner.count == self.owner.fail_at:
            raise InjectedFailure()
        self.cursor.execute(*args, **kwargs)
        return self

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)


class FailingConnection:
    def __init__(self, conn, owner):
        self.conn = conn
        self.owner = owner

    def cursor(self, *args, **kwargs):
        return FailingCursor(self.conn.cursor(*args, **kwargs), self.owner)

    def __enter__(self):
        self.conn.__enter__()
        return self

    def __exit__(self, *args):
        return self.conn.__exit__(*args)


class FailingRepository:
    def __init__(self, repo, fail_at):
        self.repo = repo
        self.fail_at = fail_at
        self.count = 0

    def connect(self):
        return FailingConnection(self.repo.connect(), self)


def test_every_source_sql_boundary_rolls_back_as_one_unit(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    for boundary in range(1, 30):
        try:
            store_captured_source(FailingRepository(repo, boundary), lease, captured)
        except InjectedFailure:
            with repo.connect() as conn:
                assert (
                    conn.execute(
                        "SELECT count(*) AS n FROM canonical_article_source_revisions"
                    ).fetchone()["n"]
                    == 0
                )
                assert (
                    conn.execute(
                        "SELECT count(*) AS n FROM canonical_article_source_observations"
                    ).fetchone()["n"]
                    == 0
                )
                assert (
                    conn.execute(
                        "SELECT current_source_revision_id FROM canonical_articles WHERE canonical_article_id=%s",
                        (article_id(context.key),),
                    ).fetchone()["current_source_revision_id"]
                    is None
                )
                assert (
                    conn.execute(
                        "SELECT phase FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                        (lease.job_id,),
                    ).fetchone()["phase"]
                    == "fetching_source"
                )
        else:
            assert boundary > 8
            break
    else:
        pytest.fail("all source transaction boundaries were not reached")


def insert_transform(
    repo, lease, source, *, status="validated", article=None, key=None
):
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import digest_json

    with repo.connect() as conn:
        job = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        ).fetchone()
        revision = uuid.uuid4()
        conn.execute(
            """INSERT INTO canonical_article_revisions(canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,status,normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata,published_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Take off the pump.','[]','[]',%s,%s,%s,%s,CASE WHEN %s='published' THEN now() ELSE NULL END)""",
            (
                revision,
                article or lease.canonical_article_id,
                source,
                key or job["transformation_key"],
                NORMALIZATION_VERSION,
                REWRITE_PROFILE_VERSION,
                status,
                Jsonb({"blocks": [{"text": "Remove pump."}]}),
                "1" * 64,
                Jsonb({"blocks": [{"text": "Take off pump."}]}),
                Jsonb(
                    {
                        "passed": True,
                        "changed_slots": ["b1"],
                        "evidence_ids": ["fixture"],
                    }
                ),
                "2" * 64,
                "3" * 64,
                Jsonb({"model": "fixture", "profile_version": REWRITE_PROFILE_VERSION}),
                status,
            ),
        )
        return revision


def test_cross_article_pointers_and_transformation_ownership_are_rejected(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    other = insert_descriptor(repo, replace(context.key, source_article_ref="other"))
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET current_source_revision_id=%s WHERE canonical_article_id=%s",
            (source, other),
        )
    with pytest.raises(psycopg.IntegrityError):
        insert_transform(repo, lease, source, key="4" * 64)
    revision = insert_transform(repo, lease, source, status="published")
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET current_canonical_revision_id=%s WHERE canonical_article_id=%s",
            (revision, other),
        )


def test_published_content_and_reviews_are_immutable(fresh_database, capture_fixture):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    revision = insert_transform(repo, lease, source, status="published")
    for sql in (
        "UPDATE canonical_article_revisions SET canonical_body='changed' WHERE canonical_article_revision_id=%s",
        "DELETE FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
    ):
        with pytest.raises(psycopg.Error), repo.connect() as conn:
            conn.execute(sql, (revision,))
    review = uuid.uuid4()
    with repo.connect() as conn:
        conn.execute(
            "INSERT INTO canonical_article_reviews VALUES (%s,%s,'authorized-fixture','REJECTED','incorrect output',now())",
            (review, revision),
        )
        conn.execute(
            "UPDATE canonical_articles SET current_canonical_revision_id=%s WHERE canonical_article_id=%s",
            (revision, lease.canonical_article_id),
        )
        state = conn.execute(
            "SELECT * FROM catalog_article_current WHERE canonical_article_id=%s",
            (lease.canonical_article_id,),
        ).fetchone()
        assert (
            state["content_origin"] == "source"
            and state["processing_error_code"] == "CANONICAL_REVIEW_REJECTED"
        )
    with pytest.raises(psycopg.Error), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_article_reviews SET decision='APPROVED' WHERE canonical_article_review_id=%s",
            (review,),
        )


def test_malformed_publication_and_attempt_ownership_are_rejected(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    revision = insert_transform(repo, lease, source)
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_article_revisions SET status='published',published_at=now(),validation_report='{}' WHERE canonical_article_revision_id=%s",
            (revision,),
        )
    other_context, other_lease, other_captured = prepare(
        repo, capture_fixture, "banktwo"
    )
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "INSERT INTO canonical_article_rewrite_attempts(rewrite_attempt_id,source_fetch_job_id,canonical_article_revision_id,lease_token,attempt_number,provider,model,profile_version,prompt_hash,input_hash,status) VALUES (%s,%s,%s,1,1,'fixture','fixture','technical-prose-v1',%s,%s,'prepared')",
            (uuid.uuid4(), other_lease.job_id, revision, "1" * 64, "2" * 64),
        )


def test_asset_availability_change_creates_new_source_revision(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, _ = prepare(repo, capture_fixture)
    context = replace(
        context, descriptor={**context.descriptor, "asset_resource_refs": ["figure"]}
    )
    first = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    old = store_captured_source(repo, lease, first)
    fail_source_job(repo, lease, code="MODEL_NOT_CONFIGURED", retryable=False)
    refresh_article_job(
        repo, article_id(context.key), actor="fixture", reason="inspect"
    )
    second_lease = claim_source_job(repo, worker_id=uuid.uuid4())
    capture_fixture.body(
        "bankone", b"image-bytes", "image/png", ref="figure", kind="asset"
    )
    second = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects
    )
    new = store_captured_source(repo, second_lease, second)
    assert old != new and first.source_fingerprint != second.source_fingerprint
    assert (
        first.projection_status == "partial" and second.projection_status == "readable"
    )


def test_new_jobs_require_leases_and_catalog_events_are_unique(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET lease_owner=NULL WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        )
    revision = insert_transform(repo, lease, source, status="published")

    def event(conn, key):
        return conn.execute(
            "INSERT INTO publication_events(event_type,event_version,canonical_article_id,canonical_article_revision_id,correlation_id,idempotency_key,payload) VALUES ('catalog.article.published',1,%s,%s,%s,%s,'{}')",
            (lease.canonical_article_id, revision, uuid.uuid4(), key),
        )

    with repo.connect() as conn:
        event(conn, "first")
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        event(conn, "second")
    with pytest.raises(psycopg.IntegrityError), repo.connect() as conn:
        conn.execute(
            "INSERT INTO publication_events(event_type,event_version,canonical_article_id,correlation_id,idempotency_key,payload) VALUES ('catalog.article.published',1,%s,%s,'bad','{}')",
            (lease.canonical_article_id, uuid.uuid4()),
        )


def test_rejected_publication_is_never_returned_as_completed_ensure(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import store_captured_source
    from autodata_ingestion.source_job_persistence import advance_source_job

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    revision = insert_transform(repo, lease, source, status="published")
    advance_source_job(repo, lease, phase="completed", checkpoint={})
    with repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET current_canonical_revision_id=%s WHERE canonical_article_id=%s",
            (revision, lease.canonical_article_id),
        )
        conn.execute(
            "INSERT INTO canonical_article_reviews VALUES (%s,%s,'authorized-fixture','REJECTED','incorrect output',now())",
            (uuid.uuid4(), revision),
        )
    result = ensure_article_job(
        repo,
        lease.canonical_article_id,
        normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=REWRITE_PROFILE_VERSION,
    )
    assert result.state == "needs_review" and result.published_revision_id is None


def test_view_source_version_uses_issuing_bank_observation(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import (
        store_captured_source,
        load_article_state,
    )

    repo = fresh_database()
    for provider in ("bankone", "banktwo"):
        context, lease, captured = prepare(repo, capture_fixture, provider)
        captured = replace(
            captured,
            resources=tuple(
                {**r, "source_revision": provider + "-revision"}
                for r in captured.resources
            ),
            resource_provenance=[
                {**r, "source_revision": provider + "-revision"}
                for r in captured.resource_provenance
            ],
        )
        store_captured_source(repo, lease, captured)
        state = load_article_state(repo, lease.canonical_article_id)
        assert state["source_version"] == provider + "-revision"
        fail_source_job(repo, lease, code="MODEL_NOT_CONFIGURED", retryable=False)


def test_unchanged_published_refresh_reuses_revision_and_observes_new_revision_string(
    fresh_database, capture_fixture
):
    from autodata_ingestion.article_lifecycle_store import (
        store_captured_source,
        load_article_state,
    )
    from autodata_ingestion.source_job_persistence import advance_source_job

    repo = fresh_database()
    context, lease, captured = prepare(repo, capture_fixture)
    source = store_captured_source(repo, lease, captured)
    revision = insert_transform(repo, lease, source, status="published")
    advance_source_job(repo, lease, phase="completed", checkpoint={})
    with repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET current_canonical_revision_id=%s WHERE canonical_article_id=%s",
            (revision, lease.canonical_article_id),
        )
        old = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (lease.job_id,),
        ).fetchone()
    refresh = refresh_article_job(
        repo, lease.canonical_article_id, actor="fixture", reason="inspect"
    )
    inspection = claim_source_job(repo, worker_id=uuid.uuid4())
    captured = replace(
        captured,
        resource_provenance=[
            {**r, "source_revision": "revision-2"} for r in captured.resource_provenance
        ],
    )
    assert store_captured_source(repo, inspection, captured) == source
    state = load_article_state(repo, lease.canonical_article_id)
    assert (
        state["canonical_revision_id"] == revision
        and state["content_origin"] == "canonical"
    )
    assert state["source_version"] == "revision-2"
    assert state["processing_state"] == "completed"
    with repo.connect() as conn:
        assert (
            conn.execute(
                "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                (lease.job_id,),
            ).fetchone()
            == old
        )
        current = conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
            (refresh.job_id,),
        ).fetchone()
        assert current["transformation_key"] is None
        assert current["checkpoint"]["reused_published_revision_id"] == str(revision)
