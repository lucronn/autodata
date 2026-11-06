"""Required acceptance uses real worker processes and isolated fixture services."""
from concurrent.futures import ProcessPoolExecutor
from uuid import uuid4
import asyncio
import pytest
from lifecycle_support import runtime,Repository,fresh_database


def ensure_child(args):
    from autodata_ingestion.source_job_persistence import ensure_article_job
    repo,article=args
    return ensure_article_job(repo,article,normalization_version="ordered-article-v1",rewrite_profile_version="technical-prose-v1")


def test_twenty_ensures_two_processes_one_source_model_revision_event(runtime):
    with ProcessPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(ensure_child,[(runtime.repo,runtime.article_id)]*20))
    assert len({r.job_id for r in results})==1
    runtime.start_workers(2);runtime.await_publication();runtime.stop_workers()
    assert runtime.counters()=={"source":1,"asset":0,"model":1,"schedule":1}
    with runtime.repo.connect() as conn:
        for table in ("canonical_article_source_revisions","canonical_article_revisions","publication_events"):
            assert conn.execute("SELECT count(*) AS n FROM "+table).fetchone()["n"]==1


def test_warm_restart_is_provider_and_model_free(runtime):
    first=runtime.ingest_to_publication("bankone")
    runtime.restart_workers();runtime.reset_counters()
    for _ in range(100):
        assert runtime.read_current()["canonical_revision_id"]==first
        assert runtime.ensure().job_id==runtime.current_job_id()
    assert runtime.counters()=={"source":0,"asset":0,"model":0,"schedule":0}


@pytest.mark.parametrize("provider",["bankone","banktwo"])
def test_provider_bound_real_s3_capture_and_publication(runtime,provider):
    revision=runtime.ingest_to_publication(provider)
    assert runtime.read_current()["review_status"]=="UNREVIEWED"
    assert runtime.servers["banktwo" if provider=="bankone" else "bankone"].calls==[]
    with runtime.repo.connect() as conn:
        key=conn.execute("SELECT snap.object_key FROM canonical_article_source_revisions s JOIN source_snapshots snap ON snap.source_snapshot_id=s.body_source_snapshot_id WHERE s.canonical_article_id=%s",(runtime.article_id,)).fetchone()["object_key"]
    response=runtime.objects.client.get_object(runtime.bucket,key)
    try:assert response.read()==b"<ol><li>Remove the pump.</li></ol>"
    finally:response.close();response.release_conn()


@pytest.mark.parametrize("point,expected_calls",[("before_source_commit",2),("after_source_commit",1),("after_model_dispatch",1),("after_model_result_commit",1),("before_publication",1),("inside_publication",1)])
def test_process_death_resumes_durable_stage(runtime,point,expected_calls):
    runtime.ensure();runtime.pause(point);runtime.start_workers(1);runtime.await_barrier()
    job=runtime.current_job_id();runtime.kill_worker();runtime.expire_lease(job)
    runtime.barrier=None;runtime.start_workers(2);runtime.await_publication();runtime.stop_workers()
    assert runtime.counters()["source"]==(2 if point=="before_source_commit" else 1)
    assert runtime.counters()["model"]==1
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==1
        attempts=conn.execute("SELECT status FROM canonical_article_rewrite_attempts ORDER BY created_at").fetchall()
        assert [a["status"] for a in attempts]==(["ambiguous","succeeded"] if point=="after_model_dispatch" else ["succeeded"])


def test_changed_source_keeps_identity_and_old_revision_immutable(runtime):
    old=runtime.ingest_to_publication("banktwo");runtime.stop_workers()
    with runtime.repo.connect() as conn:original=conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",(old,)).fetchone()
    runtime.change_fixture_body(b"<ol><li>Remove the cover.</li></ol>")
    runtime.refresh();runtime.pause("after_source_commit");runtime.start_workers(1);runtime.await_barrier()
    assert runtime.read_current()["content_origin"]=="source"
    assert runtime.read_current()["canonical_revision_id"] is None
    runtime.release("after_source_commit");new=runtime.await_publication()
    assert new!=old
    with runtime.repo.connect() as conn:assert conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",(old,)).fetchone()==original


def test_revision_only_refresh_reuses_publication_with_new_observation(runtime):
    old=runtime.ingest_to_publication("bankone");runtime.stop_workers();runtime.reset_counters()
    runtime.servers["bankone"].source_revision="revision-2"
    runtime.refresh();runtime.start_workers(2)
    runtime.wait_for(lambda:runtime.read_current()["processing_state"]=="completed")
    assert runtime.read_current()["canonical_revision_id"]==old
    assert runtime.read_current()["source_version"]=="revision-2"
    assert runtime.counters()=={"source":1,"asset":0,"model":0,"schedule":1}
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"]==2
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==1


@pytest.mark.parametrize("mode,code",[("unchanged","REWRITE_UNCHANGED"),("unsafe","REWRITE_PROTECTED_MUTATION")])
def test_invalid_or_unchanged_model_retains_readable_source(runtime,mode,code):
    runtime.model.mode=mode;runtime.ensure();runtime.start_workers(2);runtime.await_phase("needs_review")
    state=runtime.read_current()
    assert state["content_origin"]=="source" and state["processing_error_code"]==code
    assert "Remove the pump." in state["body"]
    with runtime.repo.connect() as conn:assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==0


def test_unchanged_refresh_reuses_exhausted_transform_without_reset(runtime):
    runtime.model.mode="transport";runtime.ensure();runtime.start_workers(2)
    for claim in range(1,4):
        def reached_attempt():
            with runtime.repo.connect() as conn:
                row=conn.execute("SELECT retry_count,status FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(runtime.current_job_id(),)).fetchone()
            return row["retry_count"]==claim and row["status"] in {"failed","dead_letter"}
        runtime.wait_for(reached_attempt)
        if claim<3:
            with runtime.repo.connect() as conn:assert conn.execute("SELECT retry_count FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(runtime.current_job_id(),)).fetchone()["retry_count"]==claim
            runtime.make_due()
    runtime.stop_workers()
    with runtime.repo.connect() as conn:owner=conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(runtime.current_job_id(),)).fetchone()
    assert owner["status"]=="dead_letter" and owner["retry_count"]==3
    runtime.reset_counters();runtime.refresh();runtime.start_workers(2)
    runtime.wait_for(lambda:runtime.read_current()["job_id"]==owner["source_fetch_job_id"])
    runtime.stop_workers()
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(owner["source_fetch_job_id"],)).fetchone()==owner
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"]==2
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_revisions").fetchone()["n"]==0
    assert runtime.counters()=={"source":1,"asset":0,"model":0,"schedule":1}
    runtime.reset_counters()
    for _ in range(100):assert runtime.ensure().job_id==owner["source_fetch_job_id"]
    assert runtime.counters()=={"source":0,"asset":0,"model":0,"schedule":0}


def test_real_nats_ack_before_mark_replay_is_one_logical_event_and_fenced(runtime,monkeypatch):
    import json
    import nats
    from autodata_enrichment import outbox
    runtime.ingest_to_publication("bankone");runtime.stop_workers()
    for name,value in runtime.env.items():monkeypatch.setenv(name,value)
    first=outbox._claim_next_event(3)
    assert first is not None
    async def send_twice():
        connection=await nats.connect("nats://nats:4222",connect_timeout=1)
        try:
            js=connection.jetstream();await outbox._ensure_stream(js)
            subscription=await js.pull_subscribe("catalog.article.published",durable="fixture-"+uuid4().hex,stream="AUTODATA_CATALOG")
            ack=await outbox.publish_event(first,js)
            with runtime.repo.connect() as conn:
                conn.execute("UPDATE publication_events SET delivery_lease_expires_at=clock_timestamp()-interval '1 second' WHERE publication_event_id=%s",(first.publication_event_id,))
            second=outbox._claim_next_event(3)
            assert second.publication_event_id==first.publication_event_id and second.delivery_lease_token==first.delivery_lease_token+1
            replay=await outbox.publish_event(second,js)
            assert replay.seq==ack.seq and replay.duplicate
            with pytest.raises(outbox.DeliveryLeaseLost):outbox._mark_delivered(first)
            outbox._mark_delivered(second)
            # Consumers independently deduplicate the immutable logical key.
            with runtime.repo.connect() as conn:conn.execute("CREATE TABLE fixture_event_keys (idempotency_key text PRIMARY KEY)")
            received=[]
            deadline=__import__('time').monotonic()+10
            while __import__('time').monotonic()<deadline:
                messages=await subscription.fetch(1,timeout=1)
                message=messages[0];value=json.loads(message.data)
                await message.ack()
                if value["event_id"]!=first.publication_event_id:continue
                for _ in range(2):
                    with runtime.repo.connect() as conn:conn.execute("INSERT INTO fixture_event_keys VALUES (%s) ON CONFLICT DO NOTHING",(value["idempotency_key"],))
                received.append(value);break
            assert len(received)==1
            await js.delete_consumer("AUTODATA_CATALOG",subscription._consumer)
        finally:await connection.close()
    asyncio.run(send_twice())
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM fixture_event_keys").fetchone()["n"]==1
        row=conn.execute("SELECT delivery_status,delivery_attempts FROM publication_events").fetchone()
        assert row=={"delivery_status":"published","delivery_attempts":2}


def test_broker_outage_keeps_canonical_publication_and_pending_event(runtime,monkeypatch):
    from autodata_enrichment.outbox import relay_pending_events
    revision=runtime.ingest_to_publication("banktwo");runtime.stop_workers()
    for name,value in runtime.env.items():monkeypatch.setenv(name,value)
    result=asyncio.run(relay_pending_events(nats_url="nats://127.0.0.1:1"))
    assert result["claimed"]==0
    assert runtime.read_current()["canonical_revision_id"]==revision
    with runtime.repo.connect() as conn:assert conn.execute("SELECT delivery_status FROM publication_events").fetchone()["delivery_status"]=="pending"


def test_expired_final_outbox_claim_is_dead_lettered(runtime,monkeypatch):
    from autodata_enrichment import outbox
    runtime.ingest_to_publication("bankone");runtime.stop_workers()
    for name,value in runtime.env.items():monkeypatch.setenv(name,value)
    first=outbox._claim_next_event(3)
    with runtime.repo.connect() as conn:conn.execute("UPDATE publication_events SET delivery_attempts=3,delivery_lease_expires_at=clock_timestamp()-interval '1 second'")
    assert outbox._claim_next_event(3) is None
    with runtime.repo.connect() as conn:assert conn.execute("SELECT delivery_status,delivery_attempts FROM publication_events").fetchone()=={"delivery_status":"dead_letter","delivery_attempts":3}


def test_crash_after_actual_model_request_records_ambiguous_and_bounded_replay(runtime):
    runtime.model.delay=1;runtime.ensure();runtime.start_workers(1)
    runtime.wait_for(lambda:runtime.model.calls==1)
    job=runtime.current_job_id();runtime.kill_worker();runtime.expire_lease(job)
    runtime.model.delay=0;runtime.start_workers(2)
    runtime.await_publication();runtime.stop_workers()
    assert runtime.counters()["source"]==1 and runtime.counters()["model"]==2
    with runtime.repo.connect() as conn:
        assert [r["status"] for r in conn.execute("SELECT status FROM canonical_article_rewrite_attempts ORDER BY created_at").fetchall()]==["ambiguous","succeeded"]
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==1


def test_stale_worker_after_source_io_cannot_commit_or_publish(runtime):
    runtime.ensure();runtime.pause("before_source_commit");runtime.start_workers(1);runtime.await_barrier()
    job=runtime.current_job_id();runtime.expire_lease(job)
    # The second process is the new lease owner. The paused old process has
    # already uploaded bytes, but its subsequent SQL write is fenced.
    old_barrier=runtime.barrier;runtime.barrier=None;runtime.start_workers(1)
    revision=runtime.await_publication();old_barrier[2].set()
    runtime.stop_workers()
    assert runtime.read_current()["canonical_revision_id"]==revision
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"]==1
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==1


def test_real_s3_required_upload_failure_keeps_previous_publication(runtime):
    old=runtime.ingest_to_publication("bankone");runtime.stop_workers()
    runtime.change_fixture_body(b"<p>Remove the cover.</p>")
    runtime.env["AUTODATA_SOURCE_BUCKET"]="fixture-missing-"+uuid4().hex
    runtime.refresh();runtime.start_workers(2);runtime.await_phase("failed");runtime.stop_workers()
    state=runtime.read_current()
    assert state["canonical_revision_id"]==old and state["content_origin"]=="canonical"
    assert state["processing_error_code"]=="ASSET_STORAGE_UNAVAILABLE"
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_revisions").fetchone()["n"]==1
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==1


def test_real_s3_optional_asset_failure_retains_readable_source_and_position(runtime):
    from autodata_ingestion.worker import ArticleObjectStore
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.source_job_persistence import claim_source_job
    from psycopg.types.json import Jsonb
    from autodata_ingestion.mercury2 import Mercury2Client
    provider=runtime.servers["bankone"]
    provider.body(b'<p>Remove the pump.</p><img data-resource-ref="figure" src="https://provider.invalid/image">',assets=["figure"])
    provider.body(b"fixture-image","image/png",ref="figure",kind="asset")
    with runtime.repo.connect() as conn:
        descriptor=conn.execute("SELECT descriptor FROM canonical_articles WHERE canonical_article_id=%s",(runtime.article_id,)).fetchone()["descriptor"]
        descriptor["asset_resource_refs"]=["figure"]
        conn.execute("UPDATE canonical_articles SET descriptor=%s WHERE canonical_article_id=%s",(Jsonb(descriptor),runtime.article_id))
    missing=ArticleObjectStore(endpoint="minio:9000",access_key="fixture",secret_key="fixture",bucket="fixture-missing-"+uuid4().hex)
    class SelectiveStore:
        def put_object(self,key,payload,media_type):
            (missing if media_type=="image/png" else runtime.objects).put_object(key,payload,media_type)
    runtime.ensure();lease=claim_source_job(runtime.repo,worker_id=uuid4())
    model=Mercury2Client(api_key="fixture-model",base_url=runtime.model.url)
    run_article_job(runtime.repo,lease,registry=runtime.registry,object_store=SelectiveStore(),model_client=model)
    state=runtime.read_current()
    assert state["availability"]=="available"
    assert state["document"]["blocks"][1]["type"]=="image" and state["document"]["blocks"][1]["status"]=="unavailable"
    with runtime.repo.connect() as conn:
        source=conn.execute("SELECT resource_manifest,projection_status FROM canonical_article_source_revisions").fetchone()
        assert source["projection_status"]=="partial"
        asset=next(item for item in source["resource_manifest"] if item["role"]=="asset")
        assert asset["failure_code"]=="ASSET_STORAGE_UNAVAILABLE" and "sha256" not in asset


def relay_paused_after_ack(env, arrived, release):
    import os
    from autodata_enrichment.outbox import relay_pending_events
    os.environ.clear();os.environ.update(env)
    def pause(point,event):
        if point=="after_broker_ack":
            arrived.set()
            if not release.wait(15):raise AssertionError("relay barrier timed out")
    asyncio.run(relay_pending_events(limit=1,hooks=pause,nats_url="nats://nats:4222"))


def test_relay_process_death_after_real_broker_ack_replays_same_event(runtime,monkeypatch):
    import multiprocessing
    from autodata_enrichment import outbox
    runtime.ingest_to_publication("banktwo");runtime.stop_workers()
    for name,value in runtime.env.items():monkeypatch.setenv(name,value)
    ctx=multiprocessing.get_context("spawn");arrived=ctx.Event();release=ctx.Event()
    relay=ctx.Process(target=relay_paused_after_ack,args=(runtime.env,arrived,release))
    relay.start()
    try:
        assert arrived.wait(10)
        with runtime.repo.connect() as conn:
            before=conn.execute("SELECT publication_event_id,idempotency_key,delivery_status FROM publication_events").fetchone()
        assert before["delivery_status"]=="processing"
        relay.kill();relay.join(3)
        with runtime.repo.connect() as conn:conn.execute("UPDATE publication_events SET delivery_lease_expires_at=clock_timestamp()-interval '1 second'")
        result=asyncio.run(outbox.relay_pending_events(limit=1,nats_url="nats://nats:4222"))
        assert result["published"]==1
        with runtime.repo.connect() as conn:
            after=conn.execute("SELECT publication_event_id,idempotency_key,delivery_status,delivery_attempts FROM publication_events").fetchone()
        assert after=={**before,"delivery_status":"published","delivery_attempts":2}
    finally:
        if relay.is_alive():relay.kill();relay.join(3)


def scoped_runtime_article(runtime):
    from lifecycle_support import seed_configuration
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    configuration=seed_configuration(runtime.repo,runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring',engine_displacement_l=2.0 WHERE vehicle_configuration_id=%s",(configuration,))
        conn.execute("UPDATE vehicle_identity_bases SET body_style='Sedan',drivetrain='AWD' WHERE vehicle_id=%s",(runtime.vehicle,))
    ensure_article_catalog_jobs(runtime.repo,vehicle_id=runtime.vehicle,vehicle_configuration_id=configuration)
    for _ in range(2):
        assert run_article_worker_once(runtime.repo,worker_id=uuid4(),registry=runtime.registry,object_store=runtime.objects,model_client=None)
    with runtime.repo.connect() as conn:
        runtime.article_id=conn.execute("SELECT canonical_article_id FROM canonical_articles WHERE vehicle_configuration_id=%s AND provider_slug='bankone'",(configuration,)).fetchone()["canonical_article_id"]
    return configuration


@pytest.mark.parametrize("field,value,scoped",[("year",1999,False),("model_year",1999,False),("trim","Different",True),("engine_displacement_l",5.0,True),("drivetrain","RWD",True),("body_style","Coupe",True),("configuration","Different 5.0L RWD",True)])
def test_actual_worker_rejects_wrong_year_aliases_and_configuration(runtime,field,value,scoped):
    import json
    if scoped:scoped_runtime_article(runtime)
    runtime.servers["bankone"].body(json.dumps({"vehicle":{field:value},"body":"Remove the pump."}).encode(),"application/json")
    runtime.ensure();runtime.start_workers(2)
    runtime.wait_for(lambda:runtime.read_current()["processing_state"] in {"needs_review","completed"})
    runtime.stop_workers()
    state=runtime.read_current()
    assert state["processing_state"]=="needs_review"
    assert state["processing_error_code"]=="WRONG_APPLICABILITY" and state["canonical_revision_id"] is None
    assert runtime.counters()["model"]==0
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"]==0
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"]==0


def test_matching_scoped_applicability_persists_actual_context_for_replay(runtime):
    import json
    from autodata_ingestion.article_lifecycle_store import load_source_revision
    configuration=scoped_runtime_article(runtime)
    facts={"year":2024,"model_year":2024,"trim":"Touring","engine_displacement_l":2.0,"body_style":"Sedan","drivetrain":"AWD","configuration":"Touring 2.0L AWD"}
    runtime.servers["bankone"].body(json.dumps({"vehicle":facts,"body":"Remove the pump."}).encode(),"application/json")
    runtime.ensure();runtime.start_workers(2);runtime.await_publication();runtime.stop_workers()
    source_id=runtime.read_current()["source_revision_id"]
    source=load_source_revision(runtime.repo,source_id)
    assert {name:source.vehicle[name] for name in facts}==facts
    assert source.context.key.vehicle_configuration_id==configuration
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Changed later' WHERE vehicle_configuration_id=%s",(configuration,))
    assert load_source_revision(runtime.repo,source_id).vehicle==source.vehicle


# Kept local because the immutable v1 fixture server is deliberately unchanged.
# This real HTTP stub exercises Mercury transport and records both profile prompts.
from contextlib import contextmanager


@contextmanager
def operation_model():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from types import SimpleNamespace
    import json
    import time
    model = SimpleNamespace(calls=0, prompts=[], mode="valid", delay=0)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            if self.headers.get("Authorization") != "Bearer fixture-model":
                self.send_error(401); return
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = json.loads(payload["messages"][-1]["content"])
            model.calls += 1; model.prompts.append(prompt)
            time.sleep(model.delay)
            if model.mode == "transport":
                self.send_error(503); return
            response = {"operations": [{key: op[key] for key in ("block_id", "path", "operation_id")}
                                       for op in prompt["plan"]["operations"]]}
            if model.mode == "unsafe": response["operations"][0]["text"] = "invented"
            raw = json.dumps({"choices": [{"message": {"content": json.dumps(response)}}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers()
            try: self.wfile.write(raw)
            except BrokenPipeError: pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    model.url = f"http://127.0.0.1:{server.server_port}/v1"
    try: yield model
    finally: server.shutdown(); server.server_close(); thread.join()


def target_v2(runtime, body=None):
    from autodata_ingestion.source_job_persistence import refresh_article_job
    model = runtime.stack.enter_context(operation_model())
    runtime.model = model
    runtime.env["INCEPTION_API_BASE_URL"] = model.url
    if body is not None: runtime.change_fixture_body(body)
    return refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="explicit v2 target",
                               rewrite_profile_version="technical-prose-v2")


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_v2_explicit_refresh_preserves_v1_and_warm_restart_has_zero_calls(runtime, provider):
    from autodata_ingestion.source_job_persistence import ensure_article_job, refresh_article_job
    old = runtime.ingest_to_publication(provider); runtime.stop_workers()
    with runtime.repo.connect() as conn:
        original = conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s", (old,)).fetchone()
    runtime.reset_counters(); target_v2(runtime)
    assert runtime.read_current()["content_origin"] == "source"
    runtime.start_workers(2); new = runtime.await_publication(); runtime.stop_workers()
    assert new != old and runtime.read_current()["body"] == "The pump is to be removed."
    assert runtime.read_current()["review_status"] == "UNREVIEWED"
    assert runtime.counters() == {"source": 1, "asset": 0, "model": 1, "schedule": 1}
    other = "banktwo" if provider == "bankone" else "bankone"
    assert runtime.servers[other].calls == []
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s", (old,)).fetchone() == original
        revisions = conn.execute("SELECT transformation_key,rewrite_profile_version FROM canonical_article_revisions").fetchall()
        assert len({r["transformation_key"] for r in revisions}) == 2
        assert {r["rewrite_profile_version"] for r in revisions} == {"technical-prose-v1", "technical-prose-v2"}
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 2
    owner = runtime.current_job_id()
    with runtime.repo.connect() as conn:
        owner_before = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (owner,)).fetchone()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="same source and v2", rewrite_profile_version="technical-prose-v2")
    runtime.start_workers(2); runtime.await_phase("completed"); runtime.stop_workers()
    assert runtime.read_current()["canonical_revision_id"] == new and runtime.model.calls == 1
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (owner,)).fetchone() == owner_before
        inspection = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (runtime.current_job_id(),)).fetchone()
        assert inspection["checkpoint"]["reused_transformation_job_id"] == str(owner)
        assert inspection["checkpoint"]["reused_published_revision_id"] == str(new)
        assert inspection["transformation_key"] is None
    owner = runtime.current_job_id()  # Reader tracks the completed observation job.
    runtime.restart_workers(); runtime.reset_counters()
    for _ in range(100):
        assert runtime.read_current()["canonical_revision_id"] == new
        assert ensure_article_job(runtime.repo, runtime.article_id, normalization_version="ordered-article-v1",
                                  rewrite_profile_version="technical-prose-v2").job_id == owner
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_v2_v1_ineligible_prose_renders_full_document_and_preserves_media(runtime, provider):
    runtime.article_id = runtime.articles[provider]
    body = b'<p>Inspect the pump.</p><p>Tighten the bolts to 25 Nm.</p><p>Do not start the engine.</p><table><tr><td>25 Nm</td></tr></table><img src="https://provider.invalid/unavailable">'
    target_v2(runtime, body); runtime.start_workers(2); revision = runtime.await_publication(); runtime.stop_workers()
    state = runtime.read_current()
    assert state["canonical_revision_id"] == revision and "The pump is to be inspected." in state["body"]
    assert "The bolts are to be tightened to 25 Nm." in state["body"]
    with runtime.repo.connect() as conn:
        row = conn.execute("SELECT * FROM canonical_article_revisions").fetchone()
        source, candidate = row["normalized_source_document"], row["canonical_document"]
        assert candidate["blocks"][2:] == source["blocks"][2:]
        assert row["validation_report"]["changed_clauses"] == 2
        assert row["validation_report"]["complete_rewrite"]
        assert row["validation_report"]["grammar_version"] == "complete-directive-v2"
        attempt = conn.execute("SELECT * FROM canonical_article_rewrite_attempts").fetchone()
        assert attempt["profile_version"] == "technical-prose-v2" and set(attempt["response"]) == {"operations"}
    assert runtime.counters() == {"source": 1, "asset": 0, "model": 1, "schedule": 1}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_v2_unsupported_article_never_dispatches_and_retains_readable_source(runtime, provider):
    runtime.article_id = runtime.articles[provider]
    target_v2(runtime, b"<p>Inspect the pump.</p><p>The cover provides access.</p>")
    runtime.start_workers(2); runtime.await_phase("needs_review"); runtime.stop_workers()
    state = runtime.read_current()
    assert state["content_origin"] == "source" and "The cover provides access." in state["body"]
    assert state["processing_error_code"] == "REWRITE_UNSUPPORTED_PROSE" and not state["retryable"]
    assert runtime.model.calls == 0
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_rewrite_attempts").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 0


@pytest.mark.parametrize("point", ["after_source_commit", "after_model_dispatch", "after_model_result_commit", "inside_publication"])
def test_v2_process_death_recovers_saved_stage_with_one_publication(runtime, point):
    target_v2(runtime, b"<p>Inspect the pump.</p>")
    runtime.pause(point); runtime.start_workers(1); runtime.await_barrier()
    job = runtime.current_job_id(); runtime.kill_worker(); runtime.expire_lease(job)
    runtime.barrier = None; runtime.start_workers(2); runtime.await_publication(); runtime.stop_workers()
    assert runtime.counters()["source"] == 1 and runtime.counters()["model"] == 1
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1
        attempts = conn.execute("SELECT status FROM canonical_article_rewrite_attempts ORDER BY created_at").fetchall()
        assert [a["status"] for a in attempts] == (["ambiguous", "succeeded"] if point == "after_model_dispatch" else ["succeeded"])


def test_v2_exhausted_same_source_refresh_does_not_reset_budget(runtime):
    from autodata_ingestion.source_job_persistence import refresh_article_job
    target_v2(runtime, b"<p>Inspect the pump.</p>"); runtime.model.mode = "transport"
    runtime.start_workers(2)
    for claim in range(1, 4):
        def reached():
            with runtime.repo.connect() as conn:
                row = conn.execute("SELECT retry_count,status FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (runtime.current_job_id(),)).fetchone()
            return row["retry_count"] == claim and row["status"] in {"failed", "dead_letter"}
        runtime.wait_for(reached)
        if claim < 3: runtime.make_due()
    runtime.stop_workers()
    with runtime.repo.connect() as conn:
        owner = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (runtime.current_job_id(),)).fetchone()
    runtime.reset_counters()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="same exhausted v2", rewrite_profile_version="technical-prose-v2")
    runtime.start_workers(2); runtime.wait_for(lambda: runtime.current_job_id() == owner["source_fetch_job_id"]); runtime.stop_workers()
    assert runtime.counters() == {"source": 1, "asset": 0, "model": 0, "schedule": 1}
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (owner["source_fetch_job_id"],)).fetchone() == owner


def test_v2_invalid_selector_stays_source_readable_with_failed_bound_attempt(runtime):
    target_v2(runtime, b"<p>Inspect the pump.</p>"); runtime.model.mode = "unsafe"
    runtime.start_workers(2); runtime.await_phase("needs_review"); runtime.stop_workers()
    state = runtime.read_current()
    assert state["body"] == "Inspect the pump." and state["content_origin"] == "source"
    assert state["processing_error_code"] == "REWRITE_OPERATION_MISMATCH"
    with runtime.repo.connect() as conn:
        attempt = conn.execute("SELECT status,error_code FROM canonical_article_rewrite_attempts").fetchone()
        assert attempt == {"status": "failed", "error_code": "REWRITE_OPERATION_MISMATCH"}
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 0


def test_v2_actual_request_ambiguity_uses_bounded_replay(runtime):
    target_v2(runtime, b"<p>Inspect the pump.</p>"); runtime.model.delay = 1
    runtime.start_workers(1); runtime.wait_for(lambda: runtime.model.calls == 1)
    job = runtime.current_job_id(); runtime.kill_worker(); runtime.expire_lease(job)
    runtime.model.delay = 0; runtime.start_workers(2); runtime.await_publication(); runtime.stop_workers()
    assert runtime.counters()["source"] == 1 and runtime.counters()["model"] == 2
    with runtime.repo.connect() as conn:
        assert [r["status"] for r in conn.execute("SELECT status FROM canonical_article_rewrite_attempts ORDER BY created_at").fetchall()] == ["ambiguous", "succeeded"]
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1


def test_v2_changed_source_refresh_rejects_stale_publisher_and_keeps_old_revision(runtime):
    from autodata_ingestion.source_job_persistence import claim_source_job, refresh_article_job, LeaseLost
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.procedure_rewrite import validate_article_rewrite
    target_v2(runtime, b"<p>Inspect the pump.</p>")
    runtime.pause("after_model_result_commit"); runtime.start_workers(1); runtime.await_barrier()
    job = runtime.current_job_id(); runtime.kill_worker(); runtime.expire_lease(job)
    lease = claim_source_job(runtime.repo, worker_id=uuid4())
    candidate = store.load_candidate(runtime.repo, lease)
    validation = validate_article_rewrite(candidate["normalized_source_document"], candidate["canonical_document"], profile_version="technical-prose-v2")
    store.store_validation(runtime.repo, lease, validation)
    store.publish_article_revision(runtime.repo, lease, candidate["canonical_article_revision_id"])
    runtime.change_fixture_body(b"<p>Clean the cover.</p>")
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="changed v2 source", rewrite_profile_version="technical-prose-v2")
    with pytest.raises(LeaseLost):
        store.publish_article_revision(runtime.repo, lease, candidate["canonical_article_revision_id"])
    with runtime.repo.connect() as conn:
        before = conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s", (candidate["canonical_article_revision_id"],)).fetchone()
    runtime.pause("after_source_commit"); runtime.start_workers(1); runtime.await_barrier()
    assert runtime.read_current()["content_origin"] == "source"
    assert runtime.read_current()["canonical_revision_id"] is None
    runtime.release("after_source_commit"); new = runtime.await_publication(); runtime.stop_workers()
    assert new != candidate["canonical_article_revision_id"]
    assert runtime.read_current()["body"] == "The cover is to be cleaned."
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s", (candidate["canonical_article_revision_id"],)).fetchone() == before
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 2


def projection_capture(runtime, lease):
    from autodata_ingestion.article_lifecycle import _capture_context
    from autodata_ingestion.source_article_capture import capture_source_article
    return capture_source_article(_capture_context(runtime.repo, lease),
                                  registry=runtime.registry, object_store=runtime.objects)


@pytest.mark.parametrize("terminal", [False, True])
def test_projection_v2_append_isolates_historical_results(runtime, monkeypatch, terminal):
    from dataclasses import replace
    from autodata_ingestion import source_article_capture as capture_module
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    from autodata_ingestion.article_lifecycle_store import load_source_revision, store_captured_source
    from autodata_ingestion.source_job_persistence import claim_source_job, fail_source_job, LeaseLost
    from autodata_ingestion.mercury2 import Mercury2Client
    original_capture = capture_module.capture_source_article
    monkeypatch.setattr(capture_module, "capture_source_article", lambda *a, **kw:
                        replace(original_capture(*a, **kw), projection_version="source-projection-v1"))
    model = None if terminal else Mercury2Client(api_key="fixture-model", base_url=runtime.model.url,
                                                 model="fixture-mercury")
    runtime.ensure()
    assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                   object_store=runtime.objects, model_client=model)
    old_state = runtime.read_current()
    old_id, old_job = old_state["source_revision_id"], runtime.current_job_id()
    old = load_source_revision(runtime.repo, old_id)
    assert old.projection_version == "source-projection-v1"
    assert (old_state["canonical_revision_id"] is None) == terminal
    with runtime.repo.connect() as conn:
        preserved = {table: conn.execute("SELECT * FROM " + table).fetchall() for table in (
            "canonical_article_source_revisions", "canonical_article_source_observations",
            "canonical_article_revisions", "publication_events")}
        owner = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (old_job,)).fetchone()
    monkeypatch.setattr(capture_module, "capture_source_article", original_capture)
    runtime.refresh()
    lease = claim_source_job(runtime.repo, worker_id=uuid4())
    captured = projection_capture(runtime, lease)
    new_id = store_captured_source(runtime.repo, lease, captured)
    new = load_source_revision(runtime.repo, new_id)
    assert new_id != old_id and new.projection_version == "source-projection-v2"
    assert new.source_fingerprint == old.source_fingerprint
    assert new.body_source_snapshot_id == old.body_source_snapshot_id
    assert new.resource_manifest == old.resource_manifest
    assert runtime.read_current()["content_origin"] == "source"
    assert runtime.read_current()["canonical_revision_id"] is None
    with runtime.repo.connect() as conn:
        new_job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (lease.job_id,)).fetchone()
        assert new_job["transformation_key"] != owner["transformation_key"]
        assert conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (old_job,)).fetchone() == owner
        for table, before in preserved.items():
            after = conn.execute("SELECT * FROM " + table).fetchall()
            assert all(row in after for row in before)
    fail_source_job(runtime.repo, lease, code="FIXTURE_TERMINAL", retryable=False)
    runtime.refresh(); repeat = claim_source_job(runtime.repo, worker_id=uuid4())
    assert store_captured_source(runtime.repo, repeat, projection_capture(runtime, repeat)) == new_id
    with pytest.raises(LeaseLost):
        store_captured_source(runtime.repo, lease, captured)
    runtime.refresh(); downgrade = claim_source_job(runtime.repo, worker_id=uuid4())
    with runtime.repo.connect() as conn:
        before = conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"]
    with pytest.raises(ValueError, match="downgrade"):
        store_captured_source(runtime.repo, downgrade, replace(captured, projection_version="source-projection-v1"))
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"] == before
        assert conn.execute("SELECT transformation_key FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (downgrade.job_id,)).fetchone()["transformation_key"] is None


def test_unknown_projection_rejected_before_any_persistence(runtime):
    from dataclasses import replace
    from autodata_ingestion.article_lifecycle_store import store_captured_source
    from autodata_ingestion.source_job_persistence import claim_source_job
    runtime.ensure(); lease = claim_source_job(runtime.repo, worker_id=uuid4())
    captured = projection_capture(runtime, lease)
    with runtime.repo.connect() as conn:
        before = {t: conn.execute("SELECT count(*) AS n FROM " + t).fetchone()["n"] for t in
                  ("canonical_article_source_revisions", "canonical_article_source_observations", "source_snapshots")}
    with pytest.raises(ValueError, match="unsupported source projection"):
        store_captured_source(runtime.repo, lease, replace(captured, projection_version="future"))
    with runtime.repo.connect() as conn:
        assert {t: conn.execute("SELECT count(*) AS n FROM " + t).fetchone()["n"] for t in before} == before


# Reuse the synthetic nine-leaf captured-source failed-attempt fixture.
# Worker subprocesses prepend scripts/dev, which contains another module with
# this basename. Bind these fixture functions to their exact file instead.
import importlib.util
from pathlib import Path
_recovery_spec = importlib.util.spec_from_file_location(
    'article_recovery_fixtures', Path(__file__).with_name('test_article_content_review.py'))
_recovery_fixtures = importlib.util.module_from_spec(_recovery_spec)
_recovery_spec.loader.exec_module(_recovery_fixtures)
failed_draft = _recovery_fixtures.failed_draft
recovery_snapshot = _recovery_fixtures.recovery_snapshot
from test_source_article_capture import capture_fixture


@pytest.mark.parametrize('failed_draft',['current','legacy'],indirect=True)
def test_failed_intro_correction_publishes_same_revision_without_model_calls(failed_draft):
    from autodata_ingestion import article_content_review as review
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.source_job_persistence import claim_source_job
    args = failed_draft
    repo = args['repo']
    before = recovery_snapshot(repo)
    revision = before['canonical_article_revisions'][0]['canonical_article_revision_id']
    receipt = review.record_failed_correction(**args)
    # Before independent full review the worker cannot claim the saved draft.
    assert claim_source_job(repo,worker_id=uuid4()) is None
    assert store.load_article_state(repo,before['canonical_articles'][0]['canonical_article_id'])['content_origin'] == 'source'
    normal = {key:args[key] for key in ('repo','allowlist','rationale')}
    review.record_review(**normal,expected=receipt['bindings'],reviewer_id='bob',decision='APPROVED',full_content_reviewed=True)
    class ForbiddenModel:
        def complete_json(self,prompt):
            raise AssertionError('saved-candidate resume called model')
    class ForbiddenRegistry(dict):
        def __getitem__(self,key):
            raise AssertionError('saved-candidate resume fetched source')
    lease = claim_source_job(repo,worker_id=uuid4())
    assert lease is not None
    def fail_publication(point):
        if point == 'inside_publication': raise RuntimeError('fixture publication rollback')
    with pytest.raises(RuntimeError,match='fixture publication rollback'):
        store.publish_article_revision(repo,lease,revision,hooks=fail_publication)
    assert store.load_article_state(repo,before['canonical_articles'][0]['canonical_article_id'])['content_origin'] == 'source'
    with repo.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM publication_events').fetchone()['n']==0
    run_article_job(repo,lease,registry=ForbiddenRegistry(),object_store=None,model_client=ForbiddenModel())
    after = recovery_snapshot(repo)
    assert after['source_fetch_jobs'][0]['status'] == 'completed'
    assert after['canonical_article_rewrite_attempts'] == before['canonical_article_rewrite_attempts']
    assert after['source_fetch_jobs'][0]['retry_count'] == 2
    assert after['source_fetch_jobs'][0]['max_attempts'] == before['source_fetch_jobs'][0]['max_attempts']
    assert 'rewrite_error_code' not in after['source_fetch_jobs'][0]['checkpoint']
    assert len(after['canonical_article_revisions']) == len(after['publication_events']) == 1
    assert after['canonical_article_revisions'][0]['canonical_article_revision_id'] == revision
    assert after['canonical_articles'][0]['current_canonical_revision_id'] == revision
    for _ in range(5):
        assert store.load_article_state(repo,before['canonical_articles'][0]['canonical_article_id'])['canonical_revision_id'] == revision
        assert claim_source_job(repo,worker_id=uuid4()) is None
    assert recovery_snapshot(repo) == after


def test_uncorrected_failed_intro_still_stops_at_active_worker_error(failed_draft):
    from autodata_ingestion.article_lifecycle import run_article_job
    from autodata_ingestion.source_job_persistence import claim_source_job
    args=failed_draft;repo=args['repo']
    before=recovery_snapshot(repo)
    # A fenced fixture resume proves the existing worker guard still rejects it.
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='pending'")
    lease=claim_source_job(repo,worker_id=uuid4())
    class ForbiddenModel:
        def complete_json(self,prompt): raise AssertionError('unexpected model call')
    run_article_job(repo,lease,registry={},object_store=None,model_client=ForbiddenModel())
    after=recovery_snapshot(repo)
    assert after['source_fetch_jobs'][0]['checkpoint']['rewrite_error_code']=='REWRITE_TECHNICAL_MUTATION'
    assert after['source_fetch_jobs'][0]['status']=='needs_review'
    assert after['canonical_article_rewrite_attempts']==before['canonical_article_rewrite_attempts']
    assert after['canonical_article_revisions']==before['canonical_article_revisions']
    assert after['canonical_article_reviews']==after['publication_events']==[]
    assert after['canonical_articles'][0]['current_canonical_revision_id'] is None
