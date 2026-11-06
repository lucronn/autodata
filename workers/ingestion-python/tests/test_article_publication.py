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
    forged_type = replace(validation, report={**validation.report, "changed_clauses": True})
    with pytest.raises(ValueError, match="binding"):
        store.store_validation(runtime.repo, lease, forged_type)
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


def awaiting_full(repo,fixture,*,provider="bankone",body=None,model=None):
    from test_article_worker import prepare_full,FullModel
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.article_content_review import bindings_for
    lease,source = prepare_full(repo,fixture,provider=provider,body=body)
    run_article_job(repo,lease,registry={},object_store=None,model_client=model or FullModel())
    with repo.connect() as conn:
        job = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(lease.job_id,)).fetchone()
        article = conn.execute('SELECT * FROM canonical_articles WHERE canonical_article_id=%s',(lease.canonical_article_id,)).fetchone()
        candidate = conn.execute('SELECT * FROM canonical_article_revisions WHERE transformation_key=%s',(job['transformation_key'],)).fetchone()
    expected = bindings_for(job,article,candidate,source.source_fingerprint)
    return lease,candidate,expected


def approve_full(repo,expected,tmp_path,*,retention_reviews=None):
    import json
    from autodata_ingestion.article_content_review import record_review
    allowlist = tmp_path / 'reviewers.json'
    allowlist.write_text(json.dumps({'version':1,'drafting_identities':['fixture'], 'reviewers':{'independent-human':{'kind':'human'}}}))
    allowlist.chmod(0o600)
    return record_review(repo,expected=expected,reviewer_id='independent-human',allowlist=allowlist,decision='APPROVED',
        rationale='Compared every complete sentence with the original source.',full_content_reviewed=True,retention_reviews=retention_reviews or {})


@pytest.mark.parametrize("provider",["bankone","banktwo"])
def test_full_review_resume_exhausted_budget_reclaims_without_redraft(fresh_database,capture_fixture,tmp_path,provider):
    from concurrent.futures import ThreadPoolExecutor
    from autodata_ingestion.article_lifecycle import run_article_job,run_article_worker_once
    from autodata_ingestion.source_job_persistence import ensure_article_job
    repo = fresh_database();old,candidate,expected = awaiting_full(repo,capture_fixture,provider=provider)
    source_calls = len(capture_fixture.calls(provider))
    with repo.connect() as conn:
        conn.execute('UPDATE source_fetch_jobs SET retry_count=3 WHERE source_fetch_job_id=%s',(old.job_id,))
    approve_full(repo,expected,tmp_path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        claimed = list(workers.map(lambda _:claim_source_job(repo,worker_id=uuid4()),range(2)))
    leases = [lease for lease in claimed if lease is not None]
    assert len(leases) == 1
    lease = leases[0]
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(lease.job_id,))
    current = claim_source_job(repo,worker_id=uuid4())
    assert current.token > lease.token > old.token
    with pytest.raises(LeaseLost):store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id'])
    class Never:
        def complete_json(self,prompt):pytest.fail('review resume repeated model call')
    run_article_job(repo,current,registry={},object_store=None,model_client=Never())
    state = store.load_article_state(repo,old.canonical_article_id)
    assert state['content_origin'] == 'canonical' and state['review_status'] == 'APPROVED'
    for _ in range(100):
        assert not ensure_article_job(repo,old.canonical_article_id,normalization_version=old.normalization_version,rewrite_profile_version=old.rewrite_profile_version).created
        assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=Never())
    with repo.connect() as conn:
        job = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(old.job_id,)).fetchone()
        assert job['retry_count'] == 3 and job['status'] == 'completed'
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n'] == 1
        events = conn.execute('SELECT * FROM publication_events').fetchall()
        assert len(events) == 1 and events[0]['payload']['review_status'] == 'APPROVED'
    assert len(capture_fixture.calls(provider)) == source_calls


def test_full_publication_requires_approval_even_for_live_saved_draft(fresh_database,capture_fixture):
    repo = fresh_database();lease,candidate,_ = awaiting_full(repo,capture_fixture)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='processing',heartbeat_at=clock_timestamp(),lease_owner=%s,lease_expires_at=clock_timestamp()+interval '90 seconds' WHERE source_fetch_job_id=%s",(lease.worker_id,lease.job_id))
    with pytest.raises(ValueError,match='CONTENT_REVIEW_REQUIRED'):
        store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id'])
    assert store.load_article_state(repo,lease.canonical_article_id)['content_origin'] == 'source'


@pytest.mark.parametrize('mutation',['review_binding','latest_rejection','identity','generation','document','raw_response','retentions','reviewer'])
def test_full_publication_rechecks_approval_and_saved_response(fresh_database,capture_fixture,tmp_path,mutation):
    import json
    from copy import deepcopy
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import digest_json
    repo = fresh_database();old,candidate,expected = awaiting_full(repo,capture_fixture)
    approve_full(repo,expected,tmp_path)
    lease = claim_source_job(repo,worker_id=uuid4())
    assert lease is not None
    with repo.connect() as conn:
        review = conn.execute('SELECT * FROM canonical_article_reviews').fetchone()
        reason = json.loads(review['reason'])
        if mutation == 'latest_rejection':
            conn.execute("INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,decision,authorized_reviewer_id,reason,reviewed_at) VALUES (%s,%s,'REJECTED','independent-human',%s,clock_timestamp())",(uuid4(),candidate['canonical_article_revision_id'],review['reason']))
        elif mutation in {'review_binding','retentions','reviewer','identity'}:
            if mutation == 'review_binding':reason['bindings']['source_hash'] = 'f'*64
            elif mutation == 'retentions':reason['retention_reviews'] = {'/invented/path':'This retention has no corresponding source prose slot.'}
            elif mutation == 'identity':reason['bindings']['identity_key'] += ':tampered'
            review_id = uuid4()
            conn.execute("INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,decision,authorized_reviewer_id,reason,reviewed_at) VALUES (%s,%s,'APPROVED',%s,%s,clock_timestamp())",(review_id,candidate['canonical_article_revision_id'],'fixture' if mutation == 'reviewer' else 'independent-human',json.dumps(reason)))
            conn.execute("UPDATE source_fetch_jobs SET checkpoint=jsonb_set(checkpoint,'{content_review,review_id}',%s) WHERE source_fetch_job_id=%s",(Jsonb(str(review_id)),lease.job_id))
        elif mutation == 'generation':
            conn.execute('UPDATE canonical_articles SET request_generation=request_generation+1 WHERE canonical_article_id=%s',(lease.canonical_article_id,))
        elif mutation == 'raw_response':
            response = conn.execute('SELECT response FROM canonical_article_rewrite_attempts').fetchone()['response']
            response['introduction'] = 'This article describes the pump.'
            conn.execute('UPDATE canonical_article_rewrite_attempts SET response=%s,response_hash=%s',(Jsonb(response),digest_json(response)))
        else:
            from autodata_ingestion.article_document import project_ordered_document
            from autodata_ingestion.procedure_rewrite_full import validate_full
            document = deepcopy(candidate['canonical_document'])
            document['blocks'][0]['text'] = 'This article describes the pump.'
            projection = project_ordered_document(document)
            report = validate_full(candidate['normalized_source_document'],document).report
            conn.execute('UPDATE canonical_article_revisions SET canonical_document=%s,canonical_body=%s,canonical_steps=%s,canonical_images=%s,rewrite_result_hash=%s,validation_report=%s,validation_hash=%s',
                (Jsonb(document),projection['body'],Jsonb(projection['steps']),Jsonb(projection['images']),digest_json(document),Jsonb(report),digest_json(report)))
    with pytest.raises((ValueError,LeaseLost)):
        store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id'])
    assert store.load_article_state(repo,lease.canonical_article_id)['content_origin'] == 'source'
    with repo.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n'] == 0


def test_full_publication_rollback_then_replay_emits_one_event(fresh_database,capture_fixture,tmp_path):
    repo = fresh_database();_,candidate,expected = awaiting_full(repo,capture_fixture)
    approve_full(repo,expected,tmp_path)
    lease = claim_source_job(repo,worker_id=uuid4())
    def crash(point):
        assert point == 'inside_publication'
        raise InjectedFailure()
    with pytest.raises(InjectedFailure):
        store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id'],hooks=crash)
    assert store.load_article_state(repo,lease.canonical_article_id)['content_origin'] == 'source'
    with repo.connect() as conn:
        assert conn.execute('SELECT status FROM canonical_article_revisions').fetchone()['status'] == 'validated'
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n'] == 0
    assert store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id']) == candidate['canonical_article_revision_id']
    assert store.publish_article_revision(repo,lease,candidate['canonical_article_revision_id']) == candidate['canonical_article_revision_id']
    with repo.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n'] == 1


def test_full_resume_claim_revalidates_saved_report_and_projection(fresh_database,capture_fixture,tmp_path):
    repo = fresh_database();old,_,expected = awaiting_full(repo,capture_fixture)
    approve_full(repo,expected,tmp_path)
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_article_revisions SET canonical_body='tampered saved projection'")
    assert claim_source_job(repo,worker_id=uuid4()) is None
    assert store.load_article_state(repo,old.canonical_article_id)['content_origin'] == 'source'


@pytest.mark.parametrize("provider",["bankone","banktwo"])
@pytest.mark.parametrize("content",["table_only","all_retained"])
def test_full_introduction_only_candidate_approved_publish_recovery(fresh_database,capture_fixture,tmp_path,provider,content):
    import json
    from copy import deepcopy
    from autodata_ingestion.article_lifecycle import run_article_job,run_article_worker_once
    from autodata_ingestion.source_job_persistence import ensure_article_job
    from test_article_worker import FullModel
    class RetainingModel(FullModel):
        def complete_json(self,prompt):
            self.calls += 1
            return {'introduction':'This article presents pump specifications.', 'replacements':[
                {**slot,'action':'retain','reason':'Exact technical label retained for human comparison.'} for slot in json.loads(prompt)['slots']]}
    body = (b'<table><tr><td>Pump</td><td>10 Nm</td></tr></table>' if content == 'table_only' else b'<p>Pump specifications.</p>')
    model = RetainingModel()
    repo = fresh_database()
    old,candidate,expected = awaiting_full(repo,capture_fixture,provider=provider,body=body,model=model)
    assert store.load_article_state(repo,old.canonical_article_id)['content_origin'] == 'source'
    original_blocks = deepcopy(candidate['normalized_source_document']['blocks'])
    for block in original_blocks:block['source_order'] += 1
    assert candidate['canonical_document']['blocks'][1:] == original_blocks
    assert candidate['validation_report']['changed_slots'] == ['/introduction']
    assert candidate['validation_report']['changed_prose_slots'] == []
    assert candidate['validation_report']['complete_rewrite'] is False
    reasons = {path:'Compared this exact technical label against the complete source.' for path in candidate['validation_report']['retained_paths']}
    approve_full(repo,expected,tmp_path,retention_reviews=reasons)
    with repo.connect() as conn:
        conn.execute('UPDATE source_fetch_jobs SET retry_count=3 WHERE source_fetch_job_id=%s',(old.job_id,))
    first = claim_source_job(repo,worker_id=uuid4())
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(old.job_id,))
    current = claim_source_job(repo,worker_id=uuid4())
    assert current.token > first.token
    class Never:
        def complete_json(self,prompt):pytest.fail('saved approved introduction was redrafted')
    run_article_job(repo,current,registry={},object_store=None,model_client=Never())
    state = store.load_article_state(repo,old.canonical_article_id)
    assert state['content_origin'] == 'canonical' and state['review_status'] == 'APPROVED'
    assert state['canonical_revision_id'] == candidate['canonical_article_revision_id']
    with pytest.raises(LeaseLost):store.publish_article_revision(repo,first,candidate['canonical_article_revision_id'])
    assert store.publish_article_revision(repo,current,candidate['canonical_article_revision_id']) == state['canonical_revision_id']
    source_calls = len(capture_fixture.calls(provider))
    for _ in range(100):
        assert not ensure_article_job(repo,old.canonical_article_id,normalization_version=old.normalization_version,rewrite_profile_version=old.rewrite_profile_version).created
        assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=Never())
        assert store.load_article_state(repo,old.canonical_article_id)['canonical_revision_id'] == state['canonical_revision_id']
    assert len(capture_fixture.calls(provider)) == source_calls and model.calls == 1
    with repo.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n'] == 1
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n'] == 1
        assert conn.execute('SELECT retry_count FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(old.job_id,)).fetchone()['retry_count'] == 3


@pytest.mark.parametrize('provider',['bankone','banktwo'])
@pytest.mark.parametrize('review_state',['awaiting','rejected','corrected','approved_then_rejected'])
def test_full_unchanged_refresh_adopts_saved_review_owner_without_redraft(fresh_database,capture_fixture,tmp_path,provider,review_state):
    import json
    from copy import deepcopy
    from autodata_ingestion.article_content_review import record_review,export_review,bindings_for
    from autodata_ingestion.article_lifecycle import run_article_job,run_article_worker_once
    from autodata_ingestion.source_job_persistence import refresh_article_job
    repo = fresh_database();old,candidate,expected = awaiting_full(repo,capture_fixture,provider=provider)
    allowlist = tmp_path / 'refresh-reviewers.json'
    allowlist.write_text(json.dumps({'version':1,'drafting_identities':['fixture'], 'reviewers':{'correcting-human':{'kind':'human'}}}))
    allowlist.chmod(0o600)
    if review_state == 'approved_then_rejected':
        approve_full(repo,expected,tmp_path)
    if review_state in ('rejected','corrected','approved_then_rejected'):
        with repo.connect() as conn:
            original = conn.execute('SELECT response FROM canonical_article_rewrite_attempts').fetchone()['response']
        correction = None
        if review_state == 'corrected':
            correction = deepcopy(original)
            correction['introduction'] = 'This article describes the pump.'
        decision = record_review(repo,expected=expected,reviewer_id='correcting-human',allowlist=allowlist,decision='REJECTED',
            rationale='Compared every complete sentence with the original source.',full_content_reviewed=True,retention_reviews={},correction=correction)
        expected = decision['bindings']
    with repo.connect() as conn:
        conn.execute('UPDATE source_fetch_jobs SET retry_count=3 WHERE source_fetch_job_id=%s',(old.job_id,))
        before_attempt = conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchone()
        before_candidate = conn.execute('SELECT * FROM canonical_article_revisions').fetchone()
        original_owner = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(old.job_id,)).fetchone()
        before_reviews = conn.execute('SELECT * FROM canonical_article_reviews ORDER BY reviewed_at').fetchall()
    inspection = refresh_article_job(repo,old.canonical_article_id,actor='fixture',reason='Explicit source freshness inspection')
    inspection_lease = claim_source_job(repo,worker_id=uuid4())
    assert inspection_lease.job_id == inspection.job_id
    class Never:
        def complete_json(self,prompt):pytest.fail('unchanged source refresh redrafted saved candidate')
    run_article_job(repo,inspection_lease,registry=capture_fixture.registry,object_store=capture_fixture.objects,model_client=Never())
    state = store.load_article_state(repo,old.canonical_article_id)
    assert state['content_origin'] == 'source' and state['processing_state'] == 'needs_review'
    with repo.connect() as conn:
        article = conn.execute('SELECT * FROM canonical_articles').fetchone()
        owner = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(old.job_id,)).fetchone()
        inspection_row = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(inspection.job_id,)).fetchone()
        assert article['current_job_id'] == old.job_id and owner['request_generation'] == article['request_generation']
        assert owner['request_generation'] > inspection_lease.generation > old.generation
        assert owner['retry_count'] == 3 and owner['lease_token'] == original_owner['lease_token']
        assert inspection_row['status'] == 'completed'
        assert owner['checkpoint']['content_review']['state'] == 'awaiting_review'
        assert 'review_id' not in owner['checkpoint']['content_review']
        assert owner['checkpoint']['review_owner_adoption'] == {'previous_generation':old.generation,'inspection_job_id':str(inspection.job_id),'inspection_generation':inspection_lease.generation}
        assert conn.execute('SELECT * FROM canonical_article_reviews ORDER BY reviewed_at').fetchall() == before_reviews
        assert conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchone() == before_attempt
        assert conn.execute('SELECT * FROM canonical_article_revisions').fetchone() == before_candidate
        new_expected = bindings_for(owner,article,before_candidate,expected['source_fingerprint'])
    assert claim_source_job(repo,worker_id=uuid4()) is None
    with pytest.raises(ValueError,match='STALE_BINDING'):
        export_review(repo,expected=expected,destination=tmp_path / 'stale-export')
    export_review(repo,expected=new_expected,destination=tmp_path / 'current-export')
    approve_full(repo,new_expected,tmp_path)
    first = claim_source_job(repo,worker_id=uuid4())
    assert first.job_id == old.job_id
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(old.job_id,))
    resumed = claim_source_job(repo,worker_id=uuid4())
    run_article_job(repo,resumed,registry={},object_store=None,model_client=Never())
    assert store.load_article_state(repo,old.canonical_article_id)['canonical_revision_id'] == candidate['canonical_article_revision_id']
    assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=Never())
    with repo.connect() as conn:
        assert conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchone() == before_attempt
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n'] == 1


@pytest.mark.parametrize('provider',['bankone','banktwo'])
def test_full_changed_source_refresh_keeps_saved_draft_generation_fenced(fresh_database,capture_fixture,tmp_path,provider):
    from autodata_ingestion.article_content_review import export_review
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.source_job_persistence import refresh_article_job
    repo = fresh_database();old,candidate,expected = awaiting_full(repo,capture_fixture,provider=provider)
    inspection = refresh_article_job(repo,old.canonical_article_id,actor='fixture',reason='Explicit changed source inspection')
    capture_fixture.body(provider,b'<p>Remove the cover.</p>')
    lease = claim_source_job(repo,worker_id=uuid4())
    assert lease.job_id == inspection.job_id
    def stop_after_capture(point):
        if point == 'after_source_commit':raise InjectedFailure()
    class Never:
        def complete_json(self,prompt):pytest.fail('source-only inspection called model')
    with pytest.raises(InjectedFailure):
        run_article_job(repo,lease,registry=capture_fixture.registry,object_store=capture_fixture.objects,model_client=Never(),hooks=stop_after_capture)
    with repo.connect() as conn:
        article = conn.execute('SELECT * FROM canonical_articles').fetchone()
        owner = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(old.job_id,)).fetchone()
        assert article['current_job_id'] == inspection.job_id and article['request_generation'] == lease.generation
        assert owner['request_generation'] == old.generation
        assert article['current_source_revision_id'] != candidate['source_revision_id']
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n'] == 1
    with pytest.raises(ValueError,match='STALE_BINDING'):
        export_review(repo,expected=expected,destination=tmp_path / 'stale-source-export')
    assert store.load_article_state(repo,old.canonical_article_id)['content_origin'] == 'source'


def automatic_validated(repo, fixture):
    from test_article_worker import prepare_automatic, AutomaticModel
    lease, source = prepare_automatic(repo, fixture)
    store.save_normalized_input(repo, lease, source.as_article())
    attempt = store.prepare_rewrite_attempt(repo, lease, source.source_document, context=source.vehicle, model="fixture-auto")
    store.mark_rewrite_dispatched(repo, lease, attempt)
    result = rewrite_ordered_document(source.source_document, client=AutomaticModel(), context=source.vehicle, profile_version=lease.rewrite_profile_version)
    revision = store.store_rewrite_result(repo, lease, result)
    validation = store.validate_saved_candidate(repo, lease, store.load_candidate(repo, lease))
    store.store_validation(repo, lease, validation)
    return lease, source, revision


def test_automatic_publication_rejects_tampered_saved_response(fresh_database, capture_fixture):
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import digest_json
    repo = fresh_database(); lease, source, revision = automatic_validated(repo, capture_fixture)
    with repo.connect() as conn:
        response = conn.execute("SELECT response FROM canonical_article_rewrite_attempts").fetchone()["response"]
        response["introduction"] = "The following instructions cover pump removal."
        conn.execute("UPDATE canonical_article_rewrite_attempts SET response=%s,response_hash=%s", (Jsonb(response), digest_json(response)))
    with pytest.raises(ValueError, match="binding"):
        store.publish_article_revision(repo, lease, revision)
    assert store.load_article_state(repo, lease.canonical_article_id)["content_origin"] == "source"


def test_automatic_saved_candidate_resumes_without_model_or_review(fresh_database, capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job
    from test_article_worker import prepare_automatic, AutomaticModel
    repo = fresh_database(); lease, source = prepare_automatic(repo, capture_fixture)
    store.save_normalized_input(repo, lease, source.as_article())
    attempt = store.prepare_rewrite_attempt(repo, lease, source.source_document, context=source.vehicle, model="fixture-auto")
    store.mark_rewrite_dispatched(repo, lease, attempt)
    result = rewrite_ordered_document(source.source_document, client=AutomaticModel(), context=source.vehicle, profile_version=lease.rewrite_profile_version)
    revision = store.store_rewrite_result(repo, lease, result)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s", (lease.job_id,))
    current = claim_source_job(repo, worker_id=uuid4())
    class Never:
        def complete_json(self, prompt): pytest.fail("saved automatic candidate redrafted")
    run_article_job(repo, current, registry={}, object_store=None, model_client=Never())
    assert store.load_article_state(repo, lease.canonical_article_id)["canonical_revision_id"] == revision
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_reviews").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1
