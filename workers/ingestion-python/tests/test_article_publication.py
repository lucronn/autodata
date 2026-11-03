"""Real PostgreSQL publication rollback, fencing, and stable read contract."""
from uuid import uuid4
import pytest
from lifecycle_support import fresh_database
from test_source_article_capture import capture_fixture
from test_article_transform import prepare_transform, Model
from test_article_source_persistence import FailingRepository, InjectedFailure
from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.procedure_rewrite import rewrite_ordered_document, validate_article_rewrite
from autodata_ingestion.source_job_persistence import claim_source_job, LeaseLost


def validated(repo,fixture):
    lease,source=prepare_transform(repo,fixture)
    store.save_normalized_input(repo,lease,source.as_article())
    attempt=store.prepare_rewrite_attempt(repo,lease,source.source_document,context=source.vehicle,model="fixture")
    store.mark_rewrite_dispatched(repo,lease,attempt)
    result=rewrite_ordered_document(source.source_document,client=Model(),context=source.vehicle)
    revision=store.store_rewrite_result(repo,lease,result)
    store.store_validation(repo,lease,validate_article_rewrite(source.source_document,result.document,profile_version=lease.rewrite_profile_version))
    return lease,source,revision


def test_publication_rollback_at_every_statement_then_idempotent_replay(fresh_database,capture_fixture):
    repo=fresh_database();lease,source,revision=validated(repo,capture_fixture)
    for boundary in range(1,20):
        try:
            result=store.publish_article_revision(FailingRepository(repo,boundary),lease,revision)
        except InjectedFailure:
            state=store.load_article_state(repo,lease.canonical_article_id)
            assert state["content_origin"]=="source" and state["canonical_revision_id"] is None
            with repo.connect() as conn:
                assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==0
                assert conn.execute("SELECT status FROM canonical_article_revisions").fetchone()["status"]=="validated"
        else:
            assert boundary>5
            break
    else: pytest.fail("publication transaction never completed")
    assert result==revision
    assert store.publish_article_revision(repo,lease,revision)==revision
    state=store.load_article_state(repo,lease.canonical_article_id)
    assert state["content_origin"]=="canonical" and state["processing_state"]=="completed"
    assert state["review_status"]=="UNREVIEWED" and state["body"]=="Take off the pump."
    with repo.connect() as conn:
        event=conn.execute("SELECT * FROM publication_events").fetchall()
        assert len(event)==1 and event[0]["idempotency_key"].startswith("catalog.article.published:")
        assert event[0]["dataset_request_id"] is None


def test_expired_publisher_cannot_move_pointer_or_emit_event(fresh_database,capture_fixture):
    repo=fresh_database();lease,source,revision=validated(repo,capture_fixture)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(lease.job_id,))
    current=claim_source_job(repo,worker_id=uuid4())
    with pytest.raises(LeaseLost):store.publish_article_revision(repo,lease,revision)
    assert store.load_article_state(repo,lease.canonical_article_id)["content_origin"]=="source"
    store.publish_article_revision(repo,current,revision)
    with pytest.raises(LeaseLost):store.publish_article_revision(repo,lease,revision)


def test_publication_revalidates_tampered_candidate(fresh_database,capture_fixture):
    repo=fresh_database();lease,source,revision=validated(repo,capture_fixture)
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_article_revisions SET canonical_body='invented' WHERE canonical_article_revision_id=%s",(revision,))
    with pytest.raises(ValueError,match="binding"):
        store.publish_article_revision(repo,lease,revision)
