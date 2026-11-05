"""Local content-review security and exact binding regressions; synthetic content only."""
import json
import os
from copy import deepcopy
from uuid import uuid4
import pytest
from autodata_ingestion import article_content_review as review
from autodata_ingestion.article_lifecycle_types import digest_json


def rows():
    article_id, job_id, source_id, candidate_id = [uuid4() for _ in range(4)]
    source = {"blocks": [{"text": "Remove the pump."}]}
    candidate = {"blocks": [{"text": "Take off the pump."}]}
    job = dict(source_fetch_job_id=job_id, canonical_article_id=article_id,
        source_revision_id=source_id, request_generation=3,
        normalization_version="ordered-article-v1", rewrite_profile_version=review.PROFILE)
    article = dict(identity_key="bankone:synthetic", canonical_article_id=article_id)
    revision = dict(canonical_article_revision_id=candidate_id, canonical_article_id=article_id,
        source_revision_id=source_id, normalized_source_document=source, canonical_document=candidate,
        normalized_source_hash=digest_json(source), rewrite_result_hash=digest_json(candidate))
    return job, article, revision


def reason_and_rows():
    job, article, candidate = rows()
    reason = dict(schema=review.REASON_SCHEMA, bindings=review.bindings_for(job, article, candidate, "a"*64),
        full_content_reviewed=True, retention_reviews={}, rationale="Compared every instruction and all source context.",
        reviewer_kind="human", correction=None)
    row = dict(decision="APPROVED", authorized_reviewer_id="qualified-human")
    return reason, job, article, candidate, row


def test_exact_review_bindings_reject_every_changed_field():
    reason, job, article, candidate, row = reason_and_rows()
    assert review.validate_review(reason, job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)==reason
    for key in reason["bindings"]:
        changed=deepcopy(reason);changed["bindings"][key]="foreign"
        with pytest.raises(ValueError):
            review.validate_review(changed,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


@pytest.mark.parametrize("field,value",[("full_content_reviewed",1),("rationale","short"),("reviewer_kind","synthetic"),("retention_reviews",[])])
def test_approval_requires_human_full_review(field,value):
    reason,job,article,candidate,row=reason_and_rows();reason[field]=value
    with pytest.raises(ValueError):
        review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


def test_json_reason_is_parsed_and_rejection_cannot_approve():
    reason,job,article,candidate,row=reason_and_rows()
    assert review.validate_review(json.dumps(reason),job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)==reason
    row["decision"]="REJECTED"
    with pytest.raises(ValueError):review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


def test_external_allowlist_requires_private_file_and_independent_human(tmp_path):
    policy=tmp_path/'reviewers.json'
    policy.write_text(json.dumps({"version":1,"drafting_identities":["drafter"],"reviewers":{"alice":{"kind":"human"},"drafter":{"kind":"human"},"synthetic:test":{"kind":"synthetic"}}}))
    policy.chmod(0o600)
    assert review.authorize_reviewer(policy,"alice",drafting_identities=["model"])=="human"
    for actor in ("drafter","synthetic:test","model","unknown"):
        with pytest.raises(ValueError):review.authorize_reviewer(policy,actor,drafting_identities=["model"])
    policy.chmod(0o644)
    with pytest.raises(ValueError):review.authorize_reviewer(policy,"alice",drafting_identities=[])


def test_private_export_is_exclusive_and_rejects_public_parent(tmp_path):
    destination=tmp_path/'export'
    review.write_private_export(destination,{"source":{"private":"source"},"candidate":{"private":"draft"},"manifest":{"hash":"a"*64}})
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in destination.iterdir())
    assert json.loads((destination/'source.json').read_text())=={"private":"source"}
    with pytest.raises(ValueError):review.write_private_export(destination,{"source":{}})
    public=tmp_path/'public';public.mkdir(mode=0o755)
    with pytest.raises(ValueError):review.write_private_export(public/'export',{"source":{}})


def test_correction_provenance_requires_exact_response_hash():
    reason,job,article,candidate,row=reason_and_rows()
    correction={"original_candidate_hash":"b"*64,"final_candidate_hash":reason['bindings']['candidate_hash'],"response":{"introduction":"source"},"response_hash":"c"*64,"actor":"alice"}
    reason['correction']=correction
    with pytest.raises(ValueError):review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)
    correction['response_hash']=digest_json(correction['response'])
    assert review.correction_response(reason)==correction['response']

# Integration fixtures seed only synthetic captures in a uniquely named database.
from lifecycle_support import fresh_database
from test_source_article_capture import capture_fixture


@pytest.fixture
def draft(fresh_database,capture_fixture,tmp_path,request):
    from dataclasses import replace
    from test_article_source_persistence import prepare
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document
    from autodata_ingestion.procedure_rewrite_full import validate_full
    from psycopg.types.json import Jsonb
    repo=fresh_database();context,lease,captured=prepare(repo,capture_fixture)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET rewrite_profile_version=%s WHERE source_fetch_job_id=%s",(review.PROFILE,lease.job_id))
        conn.execute("UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",(review.PROFILE,lease.canonical_article_id))
    source_id=store.store_captured_source(repo,replace(lease,rewrite_profile_version=review.PROFILE),captured)
    lease=replace(lease,source_revision_id=source_id,rewrite_profile_version=review.PROFILE)
    source=store.load_source_revision(repo,source_id)
    store.save_normalized_input(repo,lease,source.as_article())
    class Model:
        _model='synthetic-drafter'
        def complete_json(self,prompt):
            return {"introduction":"This article describes removing the pump.","replacements":[
                {"block_id":slot['block_id'],"path":slot['path'],"action":"retain" if getattr(request,'param',None)=='retain' else "rewrite","text":slot['text'] if getattr(request,'param',None)=='retain' else "Take the pump off.","reason":"Exact technical wording retained for independent full source review." if getattr(request,'param',None)=='retain' else ""}
                for slot in json.loads(prompt)['slots']]}
    attempt=store.prepare_rewrite_attempt(repo,lease,source.source_document,context=source.vehicle,model=Model._model)
    store.mark_rewrite_dispatched(repo,lease,attempt)
    result=rewrite_ordered_document(source.source_document,client=Model(),context=source.vehicle,profile_version=review.PROFILE)
    assert not result.error_code,result.error_code
    revision=store.store_rewrite_result(repo,lease,result)
    validation=validate_full(source.source_document,result.document,response=result.raw_response)
    assert validation.passed
    checkpoint={"version":1,"state":"awaiting_review","candidate_revision_id":str(revision),"candidate_hash":result.output_hash}
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_article_revisions SET status='validated',validation_report=%s,validation_hash=%s WHERE canonical_article_revision_id=%s",(Jsonb(validation.report),digest_json(validation.report),revision))
        conn.execute("UPDATE source_fetch_jobs SET status='needs_review',phase='publishing',retry_count=3,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,error_code='CONTENT_REVIEW_REQUIRED',retryable=false,checkpoint=checkpoint||%s WHERE source_fetch_job_id=%s",(Jsonb({'content_review':checkpoint}),lease.job_id))
        job=conn.execute('SELECT * FROM source_fetch_jobs').fetchone()
        article=conn.execute('SELECT * FROM canonical_articles').fetchone()
        candidate=conn.execute('SELECT * FROM canonical_article_revisions').fetchone()
    allowlist=tmp_path/'reviewers.json';allowlist.write_text(json.dumps({'version':1,'drafting_identities':[Model._model],
        'reviewers':{'alice':{'kind':'human'},'bob':{'kind':'human'},'synthetic:test':{'kind':'synthetic'}}}));allowlist.chmod(0o600)
    return dict(repo=repo,expected=review.bindings_for(job,article,candidate,source.source_fingerprint),
        reviewer_id='alice',allowlist=allowlist,rationale='Compared every instruction against the complete original source.',
        full_content_reviewed=True),result.raw_response


def test_postgres_approval_is_atomic_and_preserves_exhausted_budget(draft):
    args,response=draft
    result=review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        job=conn.execute('SELECT * FROM source_fetch_jobs').fetchone()
        rows=conn.execute('SELECT * FROM canonical_article_reviews').fetchall()
        attempt=conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchone()
        article=conn.execute('SELECT * FROM canonical_articles').fetchone()
    assert len(rows)==1 and rows[0]['decision']=='APPROVED'
    assert job['status']=='pending' and job['phase']=='publishing' and job['retry_count']==3
    assert job['checkpoint']['content_review']['review_id']==result['review_id']
    assert article['current_canonical_revision_id'] is None
    assert attempt['response']==response


@pytest.mark.parametrize('field',['request_generation','candidate_hash','source_hash','source_fingerprint','identity_key','source_revision_id','article_id','profile_version'])
def test_postgres_stale_command_has_no_review_or_scheduling_effect(draft,field):
    args,response=draft;args['expected']=deepcopy(args['expected'])
    args['expected'][field]=str(uuid4()) if field.endswith('_id') else 'foreign'
    with pytest.raises(ValueError):review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_reviews').fetchone()['n']==0
        assert conn.execute('SELECT status FROM source_fetch_jobs').fetchone()['status']=='needs_review'


def test_postgres_correction_preserves_original_then_requires_independent_approval(draft):
    args,response=draft;corrected=deepcopy(response);corrected['replacements'][0]['text']='The pump must be removed.'
    review.record_review(**args,decision='REJECTED',correction=corrected)
    with args['repo'].connect() as conn:
        candidate=conn.execute('SELECT * FROM canonical_article_revisions').fetchone()
        assert conn.execute('SELECT response FROM canonical_article_rewrite_attempts').fetchone()['response']==response
        assert conn.execute('SELECT status FROM source_fetch_jobs').fetchone()['status']=='needs_review'
    args['expected']['candidate_hash']=candidate['rewrite_result_hash']
    with pytest.raises(ValueError,match='INDEPENDENT'):
        review.record_review(**args,decision='APPROVED')
    args['reviewer_id']='bob'
    review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        decisions=conn.execute('SELECT * FROM canonical_article_reviews ORDER BY reviewed_at,canonical_article_review_id').fetchall()
        assert [row['decision'] for row in decisions]==['REJECTED','APPROVED']
        reason=json.loads(decisions[-1]['reason'])
        assert reason['correction']['response']==corrected
        assert reason['correction']['original_candidate_hash']!=reason['correction']['final_candidate_hash']


def test_postgres_rejection_revokes_queued_approval_and_duplicate_approve_is_noop(draft):
    args,response=draft
    first=review.record_review(**args,decision='APPROVED')
    assert review.record_review(**args,decision='APPROVED')==first
    args['reviewer_id']='bob'
    review.record_review(**args,decision='REJECTED')
    with args['repo'].connect() as conn:
        job=conn.execute('SELECT * FROM source_fetch_jobs').fetchone()
        latest=conn.execute('SELECT * FROM canonical_article_reviews ORDER BY reviewed_at DESC,canonical_article_review_id DESC LIMIT 1').fetchone()
    assert job['status']=='needs_review' and job['checkpoint']['content_review']['state']=='awaiting_review'
    assert latest['decision']=='REJECTED'


def test_postgres_rejection_revokes_live_resume_lease(draft):
    args,response=draft
    review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='processing',lease_owner=%s,lease_expires_at=clock_timestamp()+interval '1 minute',heartbeat_at=clock_timestamp()",(uuid4(),))
        token=conn.execute('SELECT lease_token FROM source_fetch_jobs').fetchone()['lease_token']
    args['reviewer_id']='bob';review.record_review(**args,decision='REJECTED')
    with args['repo'].connect() as conn:
        job=conn.execute('SELECT * FROM source_fetch_jobs').fetchone()
    assert job['status']=='needs_review' and job['lease_owner'] is None and job['lease_token']>token


def test_postgres_export_contains_real_source_and_candidate_in_private_files(draft,tmp_path):
    args,response=draft;destination=tmp_path/'comparison'
    result=review.export_review(args['repo'],expected=args['expected'],destination=destination)
    assert result['status']=='exported'
    source_export=json.loads((destination/'source.json').read_text())
    assert source_export['source_body']=='Remove the pump.'
    assert source_export['observation']['captured_context']['descriptor']['title']=='Pump'
    assert source_export['observation']['captured_context']['vehicle']['make']=='Example'
    assert 'Remove the pump.' in json.dumps(source_export)
    assert 'Take the pump off.' in json.dumps(json.loads((destination/'candidate.json').read_text()))
    assert 'Remove the pump.' not in json.dumps(result)


def test_postgres_failed_append_rolls_back_correction_and_schedule(draft):
    from test_article_source_persistence import FailingRepository,InjectedFailure
    args,response=draft;corrected=deepcopy(response);corrected['replacements'][0]['text']='The pump must be removed.'
    actual=args['repo']
    # Exercise every SQL boundary through the committed review, using a fresh
    # transaction each time; all failing calls leave original content intact.
    for boundary in range(1,18):
        args['repo']=FailingRepository(actual,boundary)
        try:review.record_review(**args,decision='REJECTED',correction=corrected)
        except InjectedFailure:
            with actual.connect() as conn:
                assert conn.execute('SELECT rewrite_result_hash FROM canonical_article_revisions').fetchone()['rewrite_result_hash']==args['expected']['candidate_hash']
                assert conn.execute('SELECT count(*) AS n FROM canonical_article_reviews').fetchone()['n']==0
                assert conn.execute('SELECT status FROM source_fetch_jobs').fetchone()['status']=='needs_review'
        else:break
    else:pytest.fail('review transaction never committed')


@pytest.mark.parametrize('draft',['retain'],indirect=True)
def test_postgres_every_retained_path_needs_human_justification(draft):
    args,response=draft
    with pytest.raises(ValueError,match='RETENTION'):
        review.record_review(**args,decision='APPROVED')
    args['retention_reviews']={row['path']:'Verified this exact technical label needs its original source wording.' for row in response['replacements']}
    review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        row=conn.execute('SELECT reason FROM canonical_article_reviews').fetchone()
    assert json.loads(row['reason'])['retention_reviews']==args['retention_reviews']


@pytest.mark.parametrize('column,value', [('canonical_body','Tampered body'),('validation_report',{})])
def test_postgres_approval_recomputes_projection_and_structural_report(draft,column,value):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    args,response=draft
    with args['repo'].connect() as conn:
        conn.execute(sql.SQL('UPDATE canonical_article_revisions SET {}=%s').format(sql.Identifier(column)),(Jsonb(value) if isinstance(value,dict) else value,))
    with pytest.raises(ValueError):review.record_review(**args,decision='APPROVED')
    with args['repo'].connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_reviews').fetchone()['n']==0


def test_postgres_synthetic_reviewer_requires_explicit_isolated_fixture_mode(draft):
    args,response=draft;args['reviewer_id']='synthetic:test'
    with pytest.raises(ValueError):review.record_review(**args,decision='APPROVED')
    review.record_review(**args,decision='APPROVED',fixture_mode=True)
    with args['repo'].connect() as conn:
        reason=json.loads(conn.execute('SELECT reason FROM canonical_article_reviews').fetchone()['reason'])
    assert reason['reviewer_kind']=='synthetic'
