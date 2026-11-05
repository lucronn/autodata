"""Twelve isolated real HTTP/PG/worker/S3 paid-access cases, no live services."""
from __future__ import annotations
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/dev'))
from workshop_paid_access_smoke import GO_NAMES,CASE_IDS,CASE_ASSERTIONS,MIGRATION_ASSERTIONS,go_valid
from test_catalog_api_integration import (Bridge,GO_NAMES as R3_NAMES,serve,install_source_asset_fixture,
    migration_env,migration_snapshot,run_migrations,probes,digest,now,write_json)
from lifecycle_support import fresh_database,LifecycleRuntime,seed_configuration

ARTIFACTS=Path('/artifacts')
REQUIRED=os.getenv('AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION')=='1'
if REQUIRED and (os.getenv('AUTODATA_LIFECYCLE_TEST')!='1' or os.getenv('AUTODATA_CATALOG_INTEGRATION_REQUIRED')!='1'):
    raise RuntimeError('required paid acceptance needs explicit isolated lifecycle/catalog flags')
if not REQUIRED:pytestmark=pytest.mark.skip(reason='explicit paid catalog fixture acceptance only')


class PaidBridge(Bridge):
    def __init__(self,runtime):
        super().__init__(runtime,R3_NAMES[1])
        from autodata_ingestion.purchase_config import PurchaseConfig
        from autodata_ingestion.commerce_service import CommerceService,CommerceConfig
        from test_commerce_postgres import StripeFixture
        self.payment=StripeFixture()
        self.commerce=CommerceService(runtime.repo.connect,CommerceConfig('stripe_test','acct_fixture','price_fixture'),self.payment.provider,purchase_config=PurchaseConfig.from_public(dict(enabled=True,terms_version='workshop-v1',terms_url='https://legal.example.test/terms',privacy_url='https://legal.example.test/privacy',refund_url='https://legal.example.test/refund',contact_url='https://legal.example.test/contact',tax_notice='Synthetic fixture notice')))
        self.grant_calls=[]
        self.grant_unavailable=False
        self.selector_ensure=dict(entered=0,completed=0,active=0)
        self.selector_ensure_requests=[]

    def ensure_handler(self):
        from autodata_ingestion.http_service import make_handler
        parent=make_handler(internal_token='fixture-r3-internal',commerce=self.commerce)
        owner=self
        class Handler(parent):
            def log_message(self,*args):pass
            def send_response(self,status,message=None):
                if hasattr(self,'paid_ensure_receipt'):
                    with owner.lock:self.paid_ensure_receipt['status']=status
                return super().send_response(status,message)
            def do_POST(self):
                ensure=self.path=='/v1/catalog/ensure'
                grant=self.path=='/internal/commerce/grants/check'
                if ensure:
                    length=int(self.headers.get('Content-Length','-1'))
                    assert 0<=length<=1048576
                    self.connection.settimeout(5)
                    raw=self.rfile.read(length)
                    self.rfile=io.BytesIO(raw)
                    try:payload=json.loads(raw)
                    except (ValueError,UnicodeDecodeError):payload={}
                    scope=payload.get('scope') if isinstance(payload,dict) else None
                    selector=scope in ('years','makes','models','configurations')
                    counters=owner.selector_ensure if selector else owner.ensure
                    requests=owner.selector_ensure_requests if selector else owner.ensure_requests
                    started=time.monotonic()
                    self.paid_ensure_receipt=dict(scope=scope,payload=payload,request_id=self.headers.get('X-Request-ID',''),started_at=now(),completed=False,status=None,duration_seconds=None)
                    with owner.lock:
                        counters['entered']+=1;counters['active']+=1
                        requests.append(self.paid_ensure_receipt)
                if grant:
                    with owner.lock:owner.grant_calls.append({'started_at':now()})
                    if owner.grant_unavailable:
                        self.send_response(503);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":{"code":"COMMERCE_UNAVAILABLE"}}');return
                try:super().do_POST()
                finally:
                    if ensure:
                        with owner.lock:
                            counters['completed']+=1;counters['active']-=1
                            self.paid_ensure_receipt.update(completed=True,finished_at=now(),duration_seconds=time.monotonic()-started)
        return Handler

    def snapshot(self):
        result=super().snapshot()
        with self.lock:
            result['grant_calls']=len(self.grant_calls)
            result['selector_ensure']=dict(self.selector_ensure)
            result['selector_ensure_requests']=json.loads(json.dumps(self.selector_ensure_requests))
        with self.runtime.repo.connect() as conn:
            result['paid_rows']={table:[r['record'] for r in conn.execute('SELECT to_jsonb(t) AS record FROM '+table+' t ORDER BY to_jsonb(t)::text')]
                for table in ('customer_accounts','auth_sessions','entitlements','workshop_orders','dataset_requests','dataset_projections')}
        result['payment_calls']=len(self.payment.calls)
        return result

    def control_handler(self):
        parent=super().control_handler();owner=self
        class Control(parent):
            def dispatch(self):
                if self.path.startswith('/paid-fixture/'):
                    try:
                        assert self.headers.get('X-R3-Fixture-Token')==owner.token
                        assert self.command=='POST' and self.headers.get('Content-Length','0')=='0'
                        if self.path=='/paid-fixture/grant-unavailable':owner.grant_unavailable=True
                        elif self.path=='/paid-fixture/grant-available':owner.grant_unavailable=False
                        elif self.path=='/paid-fixture/refresh-source':
                            owner.runtime.servers[owner.runtime.provider].body(json.dumps({'blocks':[{'kind':'step','number':1,'text':'Remove the refreshed pump.','images':[{'asset_resource_ref':'figure','alt':'Pump figure'}]}]}).encode(),'application/json',assets=['figure'])
                            owner.runtime.refresh()
                        else:raise AssertionError('unexpected paid control')
                        body=b'{"ok":true}';self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                    except Exception:self.send_error(500,'fixture control failed')
                else:super().dispatch()
            do_GET=dispatch
            do_POST=dispatch
        return Control


def configure_scoped_runtime(runtime,provider):
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs,read_catalog_coverage
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    unscoped=dict(runtime.articles)
    configuration=seed_configuration(runtime.repo,runtime.vehicle)
    adjacent=seed_configuration(runtime.repo,runtime.vehicle)
    other_region=seed_configuration(runtime.repo,runtime.vehicle)
    configurations=((configuration,'Paid selected'),(adjacent,'Paid adjacent'),(other_region,'Paid other region'))
    with runtime.repo.connect() as conn:
        # Scoped enumeration must resolve an explicit human configuration selector;
        # the generic seed deliberately has none and is rejected by the real worker.
        for config,label in configurations:
            conn.execute('UPDATE vehicle_configurations SET trim=%s WHERE vehicle_configuration_id=%s',(label,config))
        conn.execute("UPDATE vehicle_identity_bases SET region='CA' WHERE vehicle_identity_base_id=(SELECT vehicle_identity_base_id FROM vehicle_configurations WHERE vehicle_configuration_id=%s)",(other_region,))
    for config,_ in configurations:
        ensure_article_catalog_jobs(runtime.repo,vehicle_id=runtime.vehicle,vehicle_configuration_id=config)
        for _ in range(2):assert run_article_worker_once(runtime.repo,worker_id=uuid.uuid4(),registry=runtime.registry,object_store=runtime.objects,model_client=None)
        # A claimed job may fail: require completed, exact-scope two-bank work.
        coverage=read_catalog_coverage(runtime.repo,vehicle_id=runtime.vehicle,vehicle_configuration_id=config)
        assert coverage['complete'] is True,coverage['coverage']
        assert set(coverage['coverage'])=={'bankone','banktwo'}
        assert {item['provider_slug'] for item in coverage['items']}=={'bankone','banktwo'}
        assert all(item['vehicle_configuration_id']==config for item in coverage['items'])
        assert all(scope['vehicle_configuration_id']==config for scope in coverage['coverage'].values())
    for server in runtime.servers.values():
        assert [request.get('configuration') for request in server.resolution_requests[-3:]]==[label for _,label in configurations]
    with runtime.repo.connect() as conn:
        runtime.articles={r['provider_slug']:r['canonical_article_id'] for r in conn.execute('SELECT canonical_article_id,provider_slug FROM canonical_articles WHERE vehicle_configuration_id=%s',(configuration,))}
    assert set(runtime.articles)=={'bankone','banktwo'}
    runtime.article_id=runtime.articles[provider]
    install_source_asset_fixture(runtime)
    for server in runtime.servers.values():server.body(json.dumps({'blocks':[{'kind':'step','number':1,'text':'Remove the pump.','images':[{'asset_resource_ref':'figure','alt':'Pump figure'}]}]}).encode(),'application/json',assets=['figure'])
    runtime.reset_counters()
    return dict(configuration=str(configuration),adjacent=str(adjacent),other_region=str(other_region),unscoped=str(unscoped[provider]))


def child_case(go_name,provider,fresh_database,monkeypatch,directory):
    deadline=time.monotonic()+110
    candidate=os.environ['AUTODATA_R3_CANDIDATE_SHA']
    result=dict(schema_version=1,provider=provider,go_test_name=go_name,candidate_sha=candidate,
        candidate_origin='coordinator-host-plain-clone',host_before_sha256=digest((ARTIFACTS/'host-before.json').read_bytes()),
        input_manifest_sha256=digest((ARTIFACTS/'inputs.sha256.json').read_bytes()),started_at=now(),go_exit_code=-1,timed_out=False,
        phase_snapshots={},assertion_results={},passed=False,failures=[])
    runtime=bridge=None
    try:
        repo=fresh_database(through=0);result['fixture_database']=repo.database_name
        manifest=[p.name for p in sorted((ROOT/'db/migrations').glob('*.sql'))]
        assert len(manifest)==40 and manifest[-1]=='040_workshop_commerce.sql'
        emitted=subprocess.run(['sh',str(ROOT/'scripts/dev/migrate_sql.sh'),'--emit'],cwd=ROOT,capture_output=True,timeout=10,check=False)
        (directory/'migration-driver.sql').write_bytes(emitted.stdout);(directory/'migration-driver.stderr').write_bytes(emitted.stderr);assert emitted.returncode==0
        migrations=dict(manifest=manifest,driver_sha256=digest(emitted.stdout),driver_exit_code=0,runner_sha256=digest((ROOT/'scripts/dev/migrate_sql.sh').read_bytes()))
        migrations['fresh'],empty=run_migrations(repo,directory,'fresh',manifest)
        migrations['empty_replay'],_=run_migrations(repo,directory,'replay-empty',manifest,empty)
        with ExitStack() as stack:
            runtime=LifecycleRuntime(repo,stack)
            scope=configure_scoped_runtime(runtime,provider)
            bridge=PaidBridge(runtime)
            model_url=stack.enter_context(serve(bridge.model_handler()));runtime.env['INCEPTION_API_BASE_URL']=model_url+'/v1';runtime.env['INCEPTION_API_TIMEOUT_SECONDS']='60'
            for key,value in runtime.env.items():monkeypatch.setenv(key,value)
            ensure_url=stack.enter_context(serve(bridge.ensure_handler()));control_url=stack.enter_context(serve(bridge.control_handler()))
            service_probes=probes(runtime)
            allowed=('PATH','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')
            env={key:os.environ[key] for key in allowed if key in os.environ}
            assert env['GOTOOLCHAIN']=='local' and env['GOPROXY']=='off'
            for key in ('GOCACHE','GOTMPDIR'):Path(env[key]).mkdir(parents=True,exist_ok=True)
            env.update(AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION='1',AUTODATA_CATALOG_INTEGRATION_REQUIRED='1',AUTODATA_LIFECYCLE_TEST='1',
                AUTODATA_CATALOG_TEST_DSN=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable',
                AUTODATA_CATALOG_TEST_ENSURE_URL=ensure_url,AUTODATA_CATALOG_TEST_CONTROL_URL=control_url,AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
                AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
                AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles['banktwo' if provider=='bankone' else 'bankone']),
                AUTODATA_CATALOG_TEST_PROVIDER=provider,AUTODATA_CATALOG_TEST_CANDIDATE_SHA=candidate,AUTODATA_CATALOG_TEST_CASE_DIR=str(directory),
                AUTODATA_PAID_TEST_CONFIGURATION_ID=scope['configuration'],AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID=scope['adjacent'],
                AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID=scope['other_region'],AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID=scope['unscoped'],
                AUTODATA_S3_ENDPOINT='minio:9000',AUTODATA_S3_ACCESS_KEY='fixture',AUTODATA_S3_SECRET_KEY='fixture',AUTODATA_SOURCE_BUCKET=runtime.bucket)
            argv=['go','test','-json','-count=1','-timeout=90s','-run','^'+go_name+'$','.']
            write_json(directory/'go-command.json',dict(argv=argv,cwd=str(ROOT/'apps/api-go')))
            with (directory/'go-events.jsonl').open('wb') as stdout,(directory/'go-stderr.log').open('wb') as stderr:
                # Outer case owns the process group and the whole120s boundary.
                process=subprocess.Popen(argv,cwd=ROOT/'apps/api-go',env=env,stdout=stdout,stderr=stderr)
                try:result['go_exit_code']=process.wait(timeout=max(1,min(90,deadline-time.monotonic()-12)))
                except subprocess.TimeoutExpired:
                    result['timed_out']=True;process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
                    result['go_exit_code']=process.returncode;raise
            measurement=json.loads((directory/'go-measurement.json').read_text())
            result['phase_snapshots']=measurement['phase_snapshots'];result['assertion_results']=measurement['assertion_results']
            assert result['go_exit_code']==0,(directory/'go-events.jsonl').read_text()+(directory/'go-stderr.log').read_text()
            events=[json.loads(line) for line in (directory/'go-events.jsonl').read_text().splitlines()];assert go_valid(events,go_name)
            assert set(result['assertion_results'])==set(CASE_ASSERTIONS[go_name]) and all(v is True for v in result['assertion_results'].values())
            final=bridge.snapshot();assert not final['proxy']['errors'] and final['ensure']['active']==0
            exits=bridge.stop()
            before,schema=migration_snapshot(repo,migration_env(repo));(directory/'populated-before.schema.sql').write_bytes(schema);write_json(directory/'populated-before.rows.json',before['rows'])
            migrations['populated_replay'],_=run_migrations(repo,directory,'replay-populated',manifest,before)
            result['assertion_results'].update({key:True for key in MIGRATION_ASSERTIONS})
            write_json(directory/'measured-runtime.json',dict(schema_version=1,candidate_sha=candidate,provider=provider,go_test_name=go_name,fixture_database=repo.database_name,
                snapshots=result['phase_snapshots'],migrations=migrations,service_probes=service_probes,worker_exits=exits,final_snapshot=final,
                **{key:value for key,value in measurement.items() if key not in ('phase_snapshots','assertion_results')}))
            runtime.close();runtime=None
        result['passed']=True
    except Exception as error:
        result['failures'].append(type(error).__name__+': '+str(error));raise
    finally:
        if bridge is not None:bridge.release_model.set()
        if runtime is not None:
            try:bridge.stop() if bridge else runtime.stop_workers()
            finally:runtime.close()
        result['finished_at']=now()
        for path in directory.iterdir():
            if path.is_file():path.chmod(0o644)
        result['artifact_sha256']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name not in ('result.json','case-tests.xml','case-pytest.stdout.log','case-pytest.stderr.log')}
        write_json(directory/'result.json',result);(directory/'result.json').chmod(0o644)


@pytest.mark.parametrize('go_name,provider',[(name,provider) for name in GO_NAMES for provider in ('bankone','banktwo')],ids=CASE_IDS)
def test_required_paid_catalog_access(go_name,provider,fresh_database,monkeypatch):
    assert REQUIRED
    directory=ARTIFACTS/'paid-access'/provider/go_name
    if os.getenv('AUTODATA_PAID_CASE_CHILD')=='1':
        child_case(go_name,provider,fresh_database,monkeypatch,directory);return
    directory.mkdir(parents=True,exist_ok=False)
    env={key:value for key,value in os.environ.items() if key in ('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_R3_CANDIDATE_SHA','AUTODATA_LIFECYCLE_TEST','AUTODATA_CATALOG_INTEGRATION_REQUIRED','AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')}
    env['AUTODATA_PAID_CASE_CHILD']='1'
    node='workers/ingestion-python/tests/test_paid_catalog_api_integration.py::test_required_paid_catalog_access['+go_name+'-'+provider+']'
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--junitxml='+str(directory/'case-tests.xml'),node]
    with (directory/'case-pytest.stdout.log').open('wb') as stdout,(directory/'case-pytest.stderr.log').open('wb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=process.wait(timeout=114)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
            pytest.fail('whole paid case exceeded120s; retained owned process-group evidence')
    cases=ET.parse(directory/'case-tests.xml').getroot().findall('.//testcase')
    assert code==0 and len(cases)==1 and cases[0].get('name')=='test_required_paid_catalog_access['+go_name+'-'+provider+']' and cases[0].get('classname')=='tests.test_paid_catalog_api_integration' and not any(cases[0].find(tag) is not None for tag in ('skipped','failure','error')),(directory/'case-pytest.stdout.log').read_text()
    result=json.loads((directory/'result.json').read_text())
    for path in directory.iterdir():
        if path.is_file():path.chmod(0o644)
    result['artifact_sha256']={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name!='result.json'}
    write_json(directory/'result.json',result)
    assert result['passed'] is True and result['failures']==[]
