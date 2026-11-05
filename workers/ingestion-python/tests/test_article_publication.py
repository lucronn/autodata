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


def test_sql_read_contract_has_exact_frozen_named_columns(fresh_database,capture_fixture):
    repo=fresh_database();lease,source,revision=validated(repo,capture_fixture)
    expected="canonical_article_id vehicle_id vehicle_configuration_id title kind component provider_slug source_vehicle_ref source_article_ref source_revision_id canonical_revision_id content_origin availability document images body steps job_id processing_state retryable retry_after_seconds processing_error_code review_status updated_at takedown_status source_snapshot_id source_content_sha256 source_version source_media_type source_captured_at".split()
    assert list(store.load_article_state(repo,lease.canonical_article_id))==expected


def test_postgres_connection_loss_inside_publication_rolls_back(runtime):
    import psycopg
    runtime.ensure();runtime.pause("after_model_result_commit");runtime.start_workers(1);runtime.await_barrier()
    runtime.kill_worker();job=runtime.current_job_id();runtime.expire_lease(job)
    from autodata_ingestion.source_job_persistence import claim_source_job
    lease=claim_source_job(runtime.repo,worker_id=uuid4())
    candidate=store.load_candidate(runtime.repo,lease)
    store.store_validation(runtime.repo,lease,validate_article_rewrite(candidate["normalized_source_document"],candidate["canonical_document"],profile_version=lease.rewrite_profile_version))
    def terminate(point):
        # Find only this fixture's transaction after its revision status write.
        with runtime.repo.connect() as conn:
            rows=conn.execute("SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state='idle in transaction'").fetchall()
            assert len(rows)==1
            conn.execute("SELECT pg_terminate_backend(%s)",(rows[0]["pid"],))
    with pytest.raises(psycopg.Error):store.publish_article_revision(runtime.repo,lease,candidate["canonical_article_revision_id"],hooks=terminate)
    assert runtime.read_current()["content_origin"]=="source"
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==0
        assert conn.execute("SELECT status FROM canonical_article_revisions").fetchone()["status"]=="validated"
    runtime.expire_lease(job);runtime.barrier=None;runtime.start_workers(2);runtime.await_publication()


from lifecycle_support import runtime


def test_literal_cold_retryable_and_terminal_read_rows(fresh_database):
    from test_source_job_persistence import seed_article,ensure
    repo=fresh_database();article=seed_article(repo);job=ensure(repo,article)
    def row():
        state=store.load_article_state(repo,article)
        return {key:state[key] for key in ("content_origin","availability","processing_state","retryable","processing_error_code","review_status","document","canonical_revision_id","source_revision_id")}
    common={"content_origin":None,"retryable":False,"processing_error_code":None,"review_status":"UNREVIEWED","document":None,"canonical_revision_id":None,"source_revision_id":None}
    assert row()=={**common,"availability":"pending","processing_state":"queued"}
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='failed',retryable=true,error_code='SOURCE_UNAVAILABLE',next_attempt_at=clock_timestamp()+interval '1 minute' WHERE source_fetch_job_id=%s",(job.job_id,))
    assert row()=={**common,"availability":"pending","processing_state":"failed","retryable":True,"processing_error_code":"SOURCE_UNAVAILABLE"}
    assert 0<store.load_article_state(repo,article)["retry_after_seconds"]<=60
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='dead_letter',retryable=false,error_code='LEASE_ATTEMPTS_EXHAUSTED',next_attempt_at=NULL WHERE source_fetch_job_id=%s",(job.job_id,))
    assert row()=={**common,"availability":"unavailable","processing_state":"failed","processing_error_code":"LEASE_ATTEMPTS_EXHAUSTED"}


@pytest.mark.parametrize("case,expected",[
    ("source_pending",("source","available","publishing",False,None,"UNREVIEWED","Remove the pump.")),
    ("source_failed",("source","available","failed",True,"SOURCE_UNAVAILABLE","UNREVIEWED","Remove the pump.")),
    ("source_review",("source","available","needs_review",False,"REWRITE_UNCHANGED","UNREVIEWED","Remove the pump.")),
    ("canonical",("canonical","available","completed",False,None,"UNREVIEWED","Take off the pump.")),
    ("rejected",("source","available","needs_review",False,"CANONICAL_REVIEW_REJECTED","UNREVIEWED","Remove the pump.")),
    ("retired",("canonical","available","completed",False,None,"UNREVIEWED","Take off the pump.")),
    ("takedown",(None,"unavailable","completed",False,None,"UNREVIEWED",None)),
    ("updated_version",("source","available","queued",False,None,"UNREVIEWED","Remove the pump.")),
])
def test_literal_source_and_canonical_read_rows(fresh_database,capture_fixture,case,expected):
    repo=fresh_database();lease,source,revision=validated(repo,capture_fixture)
    if case in {"canonical","rejected","retired","takedown","updated_version"}:
        store.publish_article_revision(repo,lease,revision)
    with repo.connect() as conn:
        if case in {"source_failed","source_review"}:
            conn.execute("UPDATE source_fetch_jobs SET status=%s,retryable=%s,error_code=%s,next_attempt_at=CASE WHEN %s THEN clock_timestamp()+interval '1 minute' ELSE NULL END,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL WHERE source_fetch_job_id=%s",("failed" if case=="source_failed" else "needs_review",case=="source_failed","SOURCE_UNAVAILABLE" if case=="source_failed" else "REWRITE_UNCHANGED",case=="source_failed",lease.job_id))
        if case=="rejected":
            conn.execute("INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,decision,authorized_reviewer_id,reason) VALUES (%s,%s,'REJECTED','fixture','literal rejection')",(uuid4(),revision))
        if case=="retired":conn.execute("UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=%s",(lease.canonical_article_id,))
        if case=="takedown":conn.execute("UPDATE canonical_articles SET takedown_status='takedown' WHERE canonical_article_id=%s",(lease.canonical_article_id,))
    if case=="updated_version":
        from autodata_ingestion.source_job_persistence import refresh_article_job
        refresh_article_job(repo,lease.canonical_article_id,actor="fixture",reason="explicit new version",rewrite_profile_version="technical-prose-v2")
    state=store.load_article_state(repo,lease.canonical_article_id)
    keys=("content_origin","availability","processing_state","retryable","processing_error_code","review_status","body")
    assert tuple(state[key] for key in keys)==expected
    assert state["canonical_revision_id"]==(revision if case in {"canonical","retired"} else None)
    if case=="takedown":assert state["document"] is None and state["images"] is None and state["steps"] is None


def test_v2_publication_rebinds_saved_operation_response_even_with_rehashed_attempt(runtime):
    from test_article_lifecycle_integration import target_v2
    from autodata_ingestion.article_lifecycle_types import digest_json
    from psycopg.types.json import Jsonb
    target_v2(runtime)
    runtime.pause("after_model_result_commit"); runtime.start_workers(1); runtime.await_barrier()
    job = runtime.current_job_id(); runtime.kill_worker(); runtime.expire_lease(job)
    lease = claim_source_job(runtime.repo, worker_id=uuid4())
    candidate = store.load_candidate(runtime.repo, lease)
    validation = validate_article_rewrite(candidate["normalized_source_document"], candidate["canonical_document"], profile_version=lease.rewrite_profile_version)
    from dataclasses import replace
    forged = replace(validation, report={**validation.report, "changed_clauses": 1000})
    with pytest.raises(ValueError, match="binding"):
        store.store_validation(runtime.repo, lease, forged)
    store.store_validation(runtime.repo, lease, validation)
    with runtime.repo.connect() as conn:
        response = conn.execute("SELECT response FROM canonical_article_rewrite_attempts WHERE canonical_article_revision_id=%s", (candidate["canonical_article_revision_id"],)).fetchone()["response"]
        response["operations"][0]["operation_id"] = "unbound"
        conn.execute("UPDATE canonical_article_rewrite_attempts SET response=%s,response_hash=%s WHERE canonical_article_revision_id=%s", (Jsonb(response), digest_json(response), candidate["canonical_article_revision_id"]))
    with pytest.raises(ValueError, match="binding"):
        store.store_validation(runtime.repo, lease, validation)
    with pytest.raises(ValueError, match="binding"):
        store.publish_article_revision(runtime.repo, lease, candidate["canonical_article_revision_id"])
    assert runtime.read_current()["content_origin"] == "source"
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 0
