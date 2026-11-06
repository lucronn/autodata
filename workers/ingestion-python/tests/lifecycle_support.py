"""Isolated PostgreSQL fixture: never connects to an application database."""

from dataclasses import dataclass
from pathlib import Path
import os
import uuid
import hashlib
import tempfile
import shutil
import subprocess
import pytest
import psycopg
from psycopg.rows import dict_row
from psycopg import sql

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Repository:
    database_name: str

    def connect(self):
        if os.environ.get(
            "AUTODATA_LIFECYCLE_TEST"
        ) != "1" or not self.database_name.startswith("lifecycle_test_"):
            raise RuntimeError("isolated lifecycle fixture required")
        return psycopg.connect(
            host="postgres",
            dbname=self.database_name,
            user="lifecycle_test",
            password="lifecycle_test_only",
            row_factory=dict_row,
        )


def apply_migration(repo, number):
    """Raw original SQL for intentional upgrade/failure tests, not an operational path."""
    (path,) = (ROOT / "db/migrations").glob(f"{number:03d}_*.sql")
    with repo.connect() as conn:
        conn.autocommit = True
        conn.execute(path.read_text())


@pytest.fixture
def fresh_database():
    if os.environ.get("AUTODATA_LIFECYCLE_TEST") != "1":
        pytest.skip("requires isolated lifecycle Compose runner")
    names = []

    def fresh(through=None):
        name = "lifecycle_test_" + uuid.uuid4().hex
        with psycopg.connect(
            host="postgres",
            dbname="lifecycle_fixture",
            user="lifecycle_test",
            password="lifecycle_test_only",
            autocommit=True,
        ) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        names.append(name)
        repo = Repository(name)
        if through != 0:
            with tempfile.TemporaryDirectory(prefix="lifecycle-migrations-") as temporary:
                prefix = Path(temporary)
                for path in sorted((ROOT / "db/migrations").glob("*.sql")):
                    if through is None or int(path.name[:3]) <= through:
                        shutil.copyfile(path, prefix / path.name)
                result = subprocess.run(
                    ["sh", str(ROOT / "scripts/dev/migrate_sql.sh"), "--migrations-dir", str(prefix)],
                    env={**os.environ, "PGHOST": "postgres", "PGDATABASE": name,
                         "PGUSER": "lifecycle_test", "PGPASSWORD": "lifecycle_test_only"},
                    check=False, capture_output=True, text=True,
                )
                assert result.returncode == 0, result.stdout + result.stderr
        return repo

    yield fresh
    for name in names:
        with psycopg.connect(
            host="postgres",
            dbname="lifecycle_fixture",
            user="lifecycle_test",
            password="lifecycle_test_only",
            autocommit=True,
        ) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def seed_snapshot(repo, payload=b"fixture"):
    digest = hashlib.sha256(payload).hexdigest()
    with repo.connect() as conn:
        return conn.execute(
            """INSERT INTO source_snapshots(adapter_name, source_uri, source_version, content_sha256, object_key, license_metadata, retrieved_at)
        VALUES ('fixture','fixture://source','v1',%s,%s,'{}',now()) ON CONFLICT(content_sha256) DO UPDATE SET content_sha256=EXCLUDED.content_sha256 RETURNING source_snapshot_id""",
            (digest, "sources/" + digest),
        ).fetchone()["source_snapshot_id"]


def seed_vehicle(repo):
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        return conn.execute(
            "INSERT INTO vehicles(vehicle_key,make,model,model_year,region,source_snapshot_id,source_watermark) VALUES (%s,'Example','Car',2024,'US',%s,'v1') RETURNING vehicle_id",
            (uuid.uuid4().hex, snapshot),
        ).fetchone()["vehicle_id"]


def insert_descriptor(repo, key, **kwargs):
    from autodata_ingestion.article_lifecycle_store import upsert_article_descriptor

    return upsert_article_descriptor(
        repo,
        key,
        kwargs.get("descriptor", {"title": "Pump", "body_resource_ref": "body"}),
        seed_snapshot(repo),
        kwargs.get("generation", 0),
        rewrite_profile_version=kwargs.get("rewrite_profile_version", "technical-prose-v1"),
    )


def seed_legacy_jobs_and_read_invariants(repo):
    vehicle = seed_vehicle(repo)
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        for status in (
            "pending",
            "processing",
            "completed",
            "needs_review",
            "failed",
            "dead_letter",
        ):
            conn.execute(
                """INSERT INTO autoapi_article_fetch_jobs(vehicle_id,vehicle_key,source_location,selector_source_snapshot_id,source_snapshot_id,source_version,adapter_name,idempotency_key,status,attempt_count)
            VALUES (%s,'opaque:vehicle','fixture://legacy',%s,%s,'v1','autoapi',%s,%s,2)""",
                (vehicle, snapshot, snapshot, "legacy:" + status, status),
            )
        return conn.execute(
            "SELECT autoapi_article_fetch_job_id AS id,idempotency_key,vehicle_id,attempt_count AS retries,status,selector_source_snapshot_id,source_snapshot_id,source_location FROM autoapi_article_fetch_jobs ORDER BY idempotency_key"
        ).fetchall()


def read_imported_job_invariants(repo):
    with repo.connect() as conn:
        return conn.execute(
            "SELECT source_fetch_job_id AS id,idempotency_key,canonical_vehicle_id AS vehicle_id,retry_count AS retries,status,selector_source_snapshot_id,source_snapshot_id,source_locator AS source_location FROM source_fetch_jobs WHERE job_kind='legacy_batch' ORDER BY idempotency_key"
        ).fetchall()


def seed_configuration(repo, vehicle):
    snapshot = seed_snapshot(repo)
    with repo.connect() as conn:
        evidence = conn.execute(
            "INSERT INTO extraction_evidence(source_snapshot_id,locator,artifact_key,extracted_text,confidence,reviewer_state) VALUES (%s,'fixture','fixture','fixture',1,'approved') RETURNING extraction_evidence_id",
            (snapshot,),
        ).fetchone()["extraction_evidence_id"]
        base = conn.execute(
            "INSERT INTO vehicle_identity_bases(canonical_base_key,vehicle_id,make,model,model_year,region,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES (%s,%s,'Example','Car',2024,'US',%s,%s,'fixture','fixture',1,'approved') RETURNING vehicle_identity_base_id",
            (uuid.uuid4().hex, vehicle, snapshot, evidence),
        ).fetchone()["vehicle_identity_base_id"]
        return conn.execute(
            "INSERT INTO vehicle_configurations(configuration_key,vehicle_identity_base_id,vehicle_id,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) VALUES (%s,%s,%s,%s,%s,'fixture','fixture',1,'approved') RETURNING vehicle_configuration_id",
            (uuid.uuid4().hex, base, vehicle, snapshot, evidence),
        ).fetchone()["vehicle_configuration_id"]


# Runtime acceptance uses the production CLI, real loopback HTTP, PostgreSQL,
# fixture S3 and JetStream. Injected barriers use spawned Python worker processes.
def _hooked_worker(repo,env,point,arrived,released):
    os.environ.clear();os.environ.update(env)
    from autodata_ingestion.worker import ArticleObjectStore
    from autodata_ingestion.source_connector_client import source_connector_registry
    from autodata_ingestion.mercury2 import Mercury2Client
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    objects=ArticleObjectStore(endpoint="minio:9000",access_key="fixture",secret_key="fixture",bucket=env["AUTODATA_SOURCE_BUCKET"])
    def hook(name):
        if name==point:
            arrived.set()
            if not released.wait(10):raise RuntimeError("fixture barrier timeout: "+point)
    run_article_worker_once(repo,worker_id=uuid.uuid4(),registry=source_connector_registry(),object_store=objects,model_client=Mercury2Client.from_environment(),hooks=hook)


class LifecycleRuntime:
    def __init__(self,repo,stack):
        import sys
        sys.path.insert(0,str(ROOT/"scripts/dev"))
        from source_connector_fixture_server import serve_connector,serve_model
        from autodata_ingestion.worker import ArticleObjectStore
        from autodata_ingestion.source_connector_client import SourceConnectorClient
        from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
        from autodata_ingestion.article_lifecycle import run_article_worker_once
        self.repo=repo;self.stack=stack;self.workers=[];self.logs=[];self.barrier=None
        self.servers={p:stack.enter_context(serve_connector(p)) for p in ("bankone","banktwo")}
        self.model=stack.enter_context(serve_model())
        self.registry={p:SourceConnectorClient(s.url,token=s.token,provider=p) for p,s in self.servers.items()}
        self.bucket="lifecycle-"+uuid.uuid4().hex
        self.objects=ArticleObjectStore(endpoint="minio:9000",access_key="fixture",secret_key="fixture",bucket=self.bucket)
        self.objects.client.make_bucket(self.bucket)
        self.vehicle=seed_vehicle(repo)
        for provider,server in self.servers.items():
            server.pages=[{"complete":True,"articles":[{"opaque_ref":"same/article","title":"Pump","resource_ref":"body","asset_resource_refs":[]}]}]
            server.body(b"<ol><li>Remove the pump.</li></ol>")
        ensure_article_catalog_jobs(repo,vehicle_id=self.vehicle,vehicle_configuration_id=None)
        for _ in range(2):
            assert run_article_worker_once(repo,worker_id=uuid.uuid4(),registry=self.registry,object_store=self.objects,model_client=None)
        with repo.connect() as conn:
            # This fixture exercises the historical v1 transport/runtime lane.
            # New production registration is automatic; explicit auto tests opt in.
            conn.execute("UPDATE canonical_articles SET target_rewrite_profile_version='technical-prose-v1'")
            self.articles={r["provider_slug"]:r["canonical_article_id"] for r in conn.execute("SELECT * FROM canonical_articles").fetchall()}
        self.article_id=self.articles["bankone"]
        self.env={"PATH":os.environ.get("PATH","/usr/local/bin:/usr/bin:/bin"),"PYTHONDONTWRITEBYTECODE":"1",
            "PYTHONPATH":":".join(str(ROOT/p) for p in ("workers/ingestion-python/src","workers/enrichment-python/src","packages/contracts/python","workers/ingestion-python/tests")),
            "AUTODATA_LIFECYCLE_TEST":"1","AUTODATA_DB_ADDRESS":"postgres:5432","AUTODATA_POSTGRES_DB":repo.database_name,
            "AUTODATA_POSTGRES_USER":"lifecycle_test","AUTODATA_POSTGRES_PASSWORD":"lifecycle_test_only",
            "AUTODATA_S3_ENDPOINT":"http://minio:9000","AUTODATA_S3_ACCESS_KEY":"fixture","AUTODATA_S3_SECRET_KEY":"fixture","AUTODATA_SOURCE_BUCKET":self.bucket,
            "INCEPTION_API_KEY":"fixture-model","INCEPTION_API_BASE_URL":self.model.url,"INCEPTION_MODEL":"fixture-mercury","INCEPTION_API_TIMEOUT_SECONDS":"2"}
        for provider,server in self.servers.items():
            self.env[provider.upper()+"_BASE_URL"]=server.url;self.env[provider.upper()+"_API_TOKEN"]=server.token
        self.reset_counters()

    def start_workers(self,count=2):
        import subprocess,sys,multiprocessing
        for _ in range(count):
            if self.barrier:
                point,arrived,released=self.barrier
                worker=multiprocessing.get_context("spawn").Process(target=_hooked_worker,args=(self.repo,self.env,point,arrived,released))
                worker.start()
            else:
                log=open("/artifacts/worker-"+uuid.uuid4().hex+".log","w");self.logs.append(log)
                worker=subprocess.Popen([sys.executable,str(ROOT/"scripts/dev/article_worker.py"),"--poll-seconds","0.05"],cwd=ROOT,env=self.env,stdout=log,stderr=log)
            self.workers.append(worker)

    def stop_workers(self):
        for worker in self.workers:
            if hasattr(worker,"poll"):
                if worker.poll() is None:worker.terminate()
                try:worker.wait(timeout=3)
                except Exception:worker.kill();worker.wait(timeout=3)
            else:
                if worker.is_alive():worker.terminate()
                worker.join(timeout=3)
        self.workers=[]

    def restart_workers(self):self.stop_workers();self.barrier=None;self.start_workers(2)
    def kill_worker(self,index=0):
        worker=self.workers.pop(index)
        worker.kill()
        if hasattr(worker,"wait"):worker.wait(timeout=3)
        else:worker.join(timeout=3)
    def pause(self,point):
        import multiprocessing
        ctx=multiprocessing.get_context("spawn")
        self.barrier=(point,ctx.Event(),ctx.Event())
    def release(self,point):
        assert self.barrier[0]==point
        self.barrier[2].set()
    def await_barrier(self):
        assert self.barrier[1].wait(10),self.diagnostics()
    def wait_for(self,predicate):
        import time
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            result=predicate()
            if result:return result
            for worker in self.workers:
                if hasattr(worker,"poll") and worker.poll() is not None:
                    raise AssertionError("CLI worker exited: "+self.diagnostics())
            time.sleep(.02)
        raise AssertionError("fixture deadline: "+self.diagnostics())
    def diagnostics(self):
        with self.repo.connect() as conn:
            jobs=conn.execute("SELECT source_fetch_job_id,status,phase,retry_count,error_code FROM source_fetch_jobs").fetchall()
        return repr({"jobs":jobs,"counters":self.counters()})
    def ensure(self):
        from autodata_ingestion.source_job_persistence import ensure_article_job
        return ensure_article_job(self.repo,self.article_id,normalization_version="ordered-article-v1",rewrite_profile_version="technical-prose-v1")
    def current_job_id(self):return self.read_current()["job_id"]
    def read_current(self):
        from autodata_ingestion.article_lifecycle_store import load_article_state
        return load_article_state(self.repo,self.article_id)
    def await_phase(self,phase):return self.wait_for(lambda:self.read_current()["processing_state"]==phase)
    def await_publication(self):return self.wait_for(lambda:self.read_current()["canonical_revision_id"])
    def ingest_to_publication(self,provider):
        self.article_id=self.articles[provider];self.ensure()
        if not self.workers:self.start_workers(2)
        return self.await_publication()
    def refresh(self,actor="fixture",reason="inspection"):
        from autodata_ingestion.source_job_persistence import refresh_article_job
        return refresh_article_job(self.repo,self.article_id,actor=actor,reason=reason)
    def expire_lease(self,job_id):
        with self.repo.connect() as conn:
            conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s AND status='processing'",(job_id,))
    def make_due(self):
        with self.repo.connect() as conn:conn.execute("UPDATE source_fetch_jobs SET next_attempt_at=clock_timestamp()-interval '1 second' WHERE status='failed'")
    def change_fixture_body(self,payload):self.servers[self.provider].body(payload)
    @property
    def provider(self):return next(p for p,a in self.articles.items() if a==self.article_id)
    def reset_counters(self):
        for server in self.servers.values():server.calls.clear()
        self.model.calls=0
        with self.repo.connect() as conn:self.initial_jobs=conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]
    def counters(self):
        from urllib.parse import unquote
        source=asset=0
        for server in self.servers.values():
            for path in server.calls:
                if "/resources/" in path:
                    ref=unquote(path.split("/resources/",1)[1])
                    if ref=="body":source+=1
                    else:asset+=1
        with self.repo.connect() as conn:schedule=conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]-self.initial_jobs
        return {"source":source,"asset":asset,"model":self.model.calls,"schedule":schedule}
    def record_evidence(self, test_id):
        import json
        from datetime import datetime, timezone
        from urllib.parse import urlsplit
        origins=[server.url for server in self.servers.values()]+[self.model.url]
        assert all(urlsplit(origin).hostname in ("127.0.0.1","localhost","::1") for origin in origins)
        with self.repo.connect() as conn:
            jobs=conn.execute("SELECT source_fetch_job_id,canonical_article_id,job_kind,status,phase,retry_count,max_attempts,lease_token,transformation_key,error_code FROM source_fetch_jobs ORDER BY created_at").fetchall()
            attempts=conn.execute("SELECT rewrite_attempt_id,source_fetch_job_id,lease_token,attempt_number,status,error_code FROM canonical_article_rewrite_attempts ORDER BY created_at").fetchall()
            events=conn.execute("SELECT publication_event_id,idempotency_key,canonical_article_id,canonical_article_revision_id,delivery_status,delivery_attempts FROM publication_events ORDER BY created_at").fetchall()
            revisions=conn.execute("SELECT canonical_article_revision_id,canonical_article_id,source_revision_id,status,transformation_key FROM canonical_article_revisions ORDER BY created_at").fetchall()
            counts={table:conn.execute("SELECT count(*) AS n FROM "+table).fetchone()["n"] for table in ("canonical_article_source_revisions","canonical_article_source_observations","canonical_article_revisions","publication_events")}
            duplicates=conn.execute("SELECT count(*) AS n FROM (SELECT idempotency_key FROM publication_events GROUP BY idempotency_key HAVING count(*)>1) d").fetchone()["n"]
            unvalidated=conn.execute("SELECT count(*) AS n FROM canonical_article_revisions r WHERE r.status='published' AND COALESCE(r.validation_report->>'passed','false')<>'true'").fetchone()["n"]
        payload={"test_id":test_id,"fixture_id":self.repo.database_name,"recorded_at":datetime.now(timezone.utc).isoformat(),"origins":origins,"counter_scope":"since latest explicit reset","measured_calls":self.counters(),"counts":counts,"expected_invariants":{"duplicate_event_keys":0,"unvalidated_publications":0},"measured_invariants":{"duplicate_event_keys":duplicates,"unvalidated_publications":unvalidated},"jobs":jobs,"attempts":attempts,"revisions":revisions,"events":events}
        Path("/artifacts/runtime-"+uuid.uuid4().hex+".json").write_text(json.dumps(payload,default=str,indent=2)+"\n")

    def close(self):
        self.stop_workers()
        for log in self.logs:log.close()
        for item in self.objects.client.list_objects(self.bucket,recursive=True):self.objects.client.remove_object(self.bucket,item.object_name)
        self.objects.client.remove_bucket(self.bucket)


@pytest.fixture
def runtime(fresh_database, request):
    from contextlib import ExitStack
    with ExitStack() as stack:
        instance=LifecycleRuntime(fresh_database(),stack)
        try:yield instance
        finally:
            instance.stop_workers()
            try:instance.record_evidence(request.node.nodeid)
            finally:instance.close()
