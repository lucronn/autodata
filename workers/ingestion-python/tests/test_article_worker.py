"""Worker dispatch/recovery uses persisted phases and no warm IO."""
import pytest
from uuid import uuid4
from lifecycle_support import fresh_database
from test_source_article_capture import capture_fixture
from test_article_transform import prepare_transform, Model
from autodata_ingestion import article_lifecycle_store as store


def test_worker_publishes_persisted_source_and_warm_ensure_never_calls_model(fresh_database,capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job, run_article_worker_once
    from autodata_ingestion.source_job_persistence import ensure_article_job
    repo=fresh_database();lease,source=prepare_transform(repo,capture_fixture)
    class Counting(Model):
        calls=0
        def complete_json(self,prompt):self.calls+=1;return super().complete_json(prompt)
    model=Counting()
    run_article_job(repo,lease,registry={},object_store=None,model_client=model)
    assert model.calls==1
    state=store.load_article_state(repo,lease.canonical_article_id)
    assert state["content_origin"]=="canonical"
    for _ in range(100):
        result=ensure_article_job(repo,lease.canonical_article_id,normalization_version=lease.normalization_version,rewrite_profile_version=lease.rewrite_profile_version)
        assert result.job_id==lease.job_id and not result.created
        assert store.load_article_state(repo,lease.canonical_article_id)["canonical_revision_id"]==state["canonical_revision_id"]
    assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=model)
    assert model.calls==1


def test_worker_missing_model_retains_source_with_explicit_review(fresh_database,capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job
    repo=fresh_database();lease,source=prepare_transform(repo,capture_fixture)
    run_article_job(repo,lease,registry={},object_store=None,model_client=None)
    state=store.load_article_state(repo,lease.canonical_article_id)
    assert state["content_origin"]=="source" and state["processing_state"]=="needs_review"
    assert state["processing_error_code"]=="MODEL_NOT_CONFIGURED"


def test_worker_resume_after_saved_result_does_not_call_model(fresh_database,capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document
    repo=fresh_database();lease,source=prepare_transform(repo,capture_fixture)
    store.save_normalized_input(repo,lease,source.as_article())
    attempt=store.prepare_rewrite_attempt(repo,lease,source.source_document,context=source.vehicle,model="fixture")
    store.mark_rewrite_dispatched(repo,lease,attempt)
    store.store_rewrite_result(repo,lease,rewrite_ordered_document(source.source_document,client=Model(),context=source.vehicle))
    class Never:
        def complete_json(self,prompt):pytest.fail("durable result recomputed")
    run_article_job(repo,lease,registry={},object_store=None,model_client=Never())
    assert store.load_article_state(repo,lease.canonical_article_id)["content_origin"]=="canonical"


def test_real_s3_sdk_has_bounded_socket_timeouts_and_zero_retries():
    from autodata_ingestion.worker import ArticleObjectStore
    store=ArticleObjectStore(endpoint="127.0.0.1:1",access_key="fixture",secret_key="fixture",bucket="fixture")
    settings=store.client._http.connection_pool_kw
    assert settings["timeout"].connect_timeout==2 and settings["timeout"].read_timeout==5
    assert settings["retries"].total==0 and settings["retries"].read==0


@pytest.mark.parametrize("mode",["failure","delay"])
def test_actual_s3_sdk_failure_and_delayed_response_do_not_retry(mode):
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    from threading import Thread
    from hashlib import sha256
    import time
    from autodata_ingestion.worker import ArticleObjectStore
    from urllib3.exceptions import MaxRetryError
    from minio.error import S3Error
    class Handler(BaseHTTPRequestHandler):
        calls=0
        def log_message(self,*args):pass
        def do_GET(self):
            raw=b'<LocationConstraint xmlns="http://s3.amazonaws.com/doc/2006-03-01/">us-east-1</LocationConstraint>'
            self.send_response(200);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_PUT(self):
            Handler.calls+=1
            self.rfile.read(int(self.headers.get("Content-Length",0)))
            if mode=="delay":time.sleep(5.5)
            raw=b'<Error><Code>AccessDenied</Code><Message>fixture failure</Message><Resource>/fixture</Resource><RequestId>fixture</RequestId><HostId>fixture</HostId></Error>'
            self.send_response(403);self.send_header("Content-Type","application/xml");self.send_header("Content-Length",str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except BrokenPipeError:pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        store=ArticleObjectStore(endpoint=f"127.0.0.1:{server.server_port}",access_key="fixture",secret_key="fixture",bucket="fixture")
        payload=b"fixture";digest=sha256(payload).hexdigest();started=time.monotonic()
        with pytest.raises((MaxRetryError,S3Error)):
            store.put_object("sources/"+digest[:16]+"/"+digest,payload,"text/plain")
        elapsed=time.monotonic()-started
        assert Handler.calls==1 and elapsed<7
        if mode=="delay":assert elapsed>=4.5
    finally:server.shutdown();server.server_close();thread.join()


def test_stale_error_recording_does_not_stop_worker_polling(monkeypatch):
    from types import SimpleNamespace
    from autodata_ingestion import article_lifecycle as lifecycle
    from autodata_ingestion.source_job_persistence import LeaseLost
    monkeypatch.setattr(lifecycle,"claim_source_job",lambda *args,**kwargs:SimpleNamespace(kind="article"))
    def expired(*args,**kwargs):raise LeaseLost("lease expired while recording transport error")
    monkeypatch.setattr(lifecycle,"run_article_job",expired)
    assert lifecycle.run_article_worker_once(None,worker_id=uuid4(),registry={},object_store=None,model_client=None)


class FullModel:
    _model = 'fixture'
    calls = 0
    def complete_json(self, prompt):
        import json
        self.calls += 1
        slots = json.loads(prompt)['slots']
        return {'introduction':'This article describes removing the pump.', 'replacements':[
            {**slot,'action':'rewrite','text':slot['text'].replace('Remove','Take off'), 'reason':''} for slot in slots]}


def prepare_full(repo, fixture, *, provider="bankone", body=None):
    from test_article_source_persistence import prepare
    from dataclasses import replace
    context,lease,captured = prepare(repo,fixture,provider=provider)
    if body is not None:
        from autodata_ingestion.source_article_capture import capture_source_article
        fixture.body(provider,body)
        captured = capture_source_article(context,registry=fixture.registry,object_store=fixture.objects)
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET target_rewrite_profile_version='full-prose-review-v1' WHERE canonical_article_id=%s", (lease.canonical_article_id,))
        conn.execute("UPDATE source_fetch_jobs SET rewrite_profile_version='full-prose-review-v1' WHERE source_fetch_job_id=%s", (lease.job_id,))
    lease = replace(lease,rewrite_profile_version='full-prose-review-v1')
    revision = store.store_captured_source(repo,lease,captured)
    return replace(lease,source_revision_id=revision),store.load_source_revision(repo,revision)


def test_full_draft_parks_source_and_100_ensures_never_redraft(fresh_database,capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job,run_article_worker_once
    from autodata_ingestion.source_job_persistence import ensure_article_job
    repo = fresh_database(); lease,_ = prepare_full(repo,capture_fixture)
    model = FullModel()
    run_article_job(repo,lease,registry={},object_store=None,model_client=model)
    state = store.load_article_state(repo,lease.canonical_article_id)
    assert state['content_origin'] == 'source'
    assert state['processing_state'] == 'needs_review'
    assert state['processing_error_code'] == 'CONTENT_REVIEW_REQUIRED'
    assert model.calls == 1
    for _ in range(100):
        assert not ensure_article_job(repo,lease.canonical_article_id,normalization_version=lease.normalization_version,rewrite_profile_version=lease.rewrite_profile_version).created
        assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=model)
    with repo.connect() as conn:
        job = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(lease.job_id,)).fetchone()
        assert job['lease_owner'] is None and job['lease_expires_at'] is None
        assert job['checkpoint']['content_review']['state'] == 'awaiting_review'
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_revisions').fetchone()['n'] == 1
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n'] == 1
    assert model.calls == 1


def test_full_table_only_draft_still_requires_complete_human_review(fresh_database,capture_fixture):
    from autodata_ingestion.article_lifecycle import run_article_job
    repo = fresh_database()
    lease,_ = prepare_full(repo,capture_fixture,body=b'<table><tr><td>Pump</td><td>10 Nm</td></tr></table>')
    model = FullModel()
    run_article_job(repo,lease,registry={},object_store=None,model_client=model)
    state = store.load_article_state(repo,lease.canonical_article_id)
    assert model.calls == 1
    assert state['content_origin'] == 'source' and state['processing_error_code'] == 'CONTENT_REVIEW_REQUIRED'


def test_full_saved_result_atomically_parks_at_exhausted_delivery_budget(fresh_database,capture_fixture):
    from autodata_ingestion.procedure_rewrite import rewrite_ordered_document
    from autodata_ingestion.source_job_persistence import claim_source_job
    repo = fresh_database();lease,source = prepare_full(repo,capture_fixture)
    store.save_normalized_input(repo,lease,source.as_article())
    attempt = store.prepare_rewrite_attempt(repo,lease,source.source_document,context=source.vehicle,model='fixture')
    store.mark_rewrite_dispatched(repo,lease,attempt)
    with repo.connect() as conn:
        conn.execute('UPDATE source_fetch_jobs SET retry_count=3 WHERE source_fetch_job_id=%s',(lease.job_id,))
    result = rewrite_ordered_document(source.source_document,client=FullModel(),context=source.vehicle,profile_version=lease.rewrite_profile_version)
    revision = store.store_rewrite_result(repo,lease,result)
    # Simulate immediate process loss after the durable model-result commit.
    assert claim_source_job(repo,worker_id=uuid4()) is None
    with repo.connect() as conn:
        job = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s',(lease.job_id,)).fetchone()
        candidate = conn.execute('SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s',(revision,)).fetchone()
        assert job['status'] == 'needs_review' and job['retry_count'] == 3
        assert job['error_code'] == 'CONTENT_REVIEW_REQUIRED' and job['lease_owner'] is None
        assert candidate['status'] == 'validated'


@pytest.mark.parametrize('crash_after_save',[False,True])
def test_full_failed_response_preserves_specific_error_and_original_response(fresh_database,capture_fixture,crash_after_save):
    from autodata_ingestion.article_lifecycle import run_article_job,run_article_worker_once
    from autodata_ingestion.source_job_persistence import claim_source_job
    from test_article_source_persistence import InjectedFailure
    class InvalidModel(FullModel):
        def complete_json(self,prompt):
            self.response = super().complete_json(prompt)
            self.response['replacements'][0]['text'] += ' Use 10 Nm.'
            return self.response
    repo = fresh_database();lease,_ = prepare_full(repo,capture_fixture)
    model = InvalidModel()
    def crash(point):
        if point == 'after_model_result_commit':raise InjectedFailure()
    if crash_after_save:
        with pytest.raises(InjectedFailure):
            run_article_job(repo,lease,registry={},object_store=None,model_client=model,hooks=crash)
        with repo.connect() as conn:
            conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(lease.job_id,))
        current = claim_source_job(repo,worker_id=uuid4())
        run_article_job(repo,current,registry={},object_store=None,model_client=model)
    else:
        run_article_job(repo,lease,registry={},object_store=None,model_client=model)
    state = store.load_article_state(repo,lease.canonical_article_id)
    assert state['content_origin'] == 'source' and state['processing_state'] == 'needs_review'
    assert state['processing_error_code'] == 'REWRITE_TECHNICAL_MUTATION'
    with repo.connect() as conn:
        attempt = conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchone()
        assert attempt['status'] == 'failed' and attempt['error_code'] == state['processing_error_code']
        assert attempt['response'] == model.response
        assert conn.execute('SELECT count(*) AS n FROM canonical_article_rewrite_attempts').fetchone()['n'] == 1
    assert model.calls == 1
    assert not run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=model)
