"""Exactly 21 required browser cases over actual PG/auth/commerce/catalog/S3 HTTP."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
import ssl
import uuid

import pytest

from lifecycle_support import fresh_database, LifecycleRuntime, Repository
from test_paid_catalog_api_integration import PaidBridge, configure_scoped_runtime, serve

ROOT=Path(__file__).resolve().parents[3]
REQUIRED=os.environ.get('AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION')=='1'
ENGINES=('chromium','firefox','webkit')
BANKS=('bankone','banktwo')
if REQUIRED and os.environ.get('AUTODATA_LIFECYCLE_TEST')!='1':
    raise RuntimeError('required Workshop browser cases need isolated lifecycle runtime')
if not REQUIRED:
    pytestmark=pytest.mark.skip(reason='explicit Workshop browser fixture acceptance only; not API proof')


class BrowserBridge(PaidBridge):
    """Synthetic Stripe facts still enter the actual public signed webhook."""
    def control_handler(self):
        parent=super().control_handler();owner=self
        class Control(parent):
            def dispatch(self):
                target=urlsplit(self.path)
                if not target.path.startswith('/browser-fixture/'):
                    return super().dispatch()
                try:
                    assert self.headers.get('X-R3-Fixture-Token')==owner.token
                    assert self.headers.get('Content-Length','0')=='0'
                    if target.path=='/browser-fixture/lose-response':
                        assert self.command=='POST';owner.payment.lose_once=True;result={'ok':True}
                    elif target.path=='/browser-fixture/event':
                        assert self.command=='GET'
                        query=parse_qs(target.query);order=str(uuid.UUID(query['order_id'][0]));action=query['action'][0]
                        with owner.runtime.repo.connect() as conn:
                            row=conn.execute('SELECT checkout_session_id FROM workshop_orders WHERE order_id=%s',(order,)).fetchone()
                        assert row and row['checkout_session_id'] in owner.payment.sessions
                        sid=row['checkout_session_id']
                        if action=='settle':
                            owner.payment.paid(sid);signature,body=owner.payment.event(sid)
                        else:
                            assert action=='refund'
                            signature,body=owner.payment.event(sid,kind='charge.refunded',amount_refunded=2000,refunded=True)
                        result={'signature':signature,'body':body.decode()}
                    else: raise AssertionError('unexpected browser control route')
                    raw=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
                except Exception:
                    self.send_error(500,'owned browser fixture control failed')
            do_GET=dispatch
            do_POST=dispatch
        return Control


def _child(root_name,engine,provider,directory,monkeypatch):
    deadline=time.monotonic()+78
    candidate=os.environ['AUTODATA_R3_CANDIDATE_SHA']
    repo=Repository(os.environ['AUTODATA_WORKSHOP_BROWSER_DATABASE'])
    runtime=bridge=process=None
    result={'version':'v1','mode':'api-fixture','candidate_sha':candidate,'browser':engine,'provider':provider,'test':root_name,'fixture_database':repo.database_name,'passed':False}
    try:
        with ExitStack() as stack:
            runtime=LifecycleRuntime(repo,stack)
            scope=configure_scoped_runtime(runtime,provider)
            bridge=BrowserBridge(runtime)
            model=stack.enter_context(serve(bridge.model_handler()))
            runtime.env['INCEPTION_API_BASE_URL']=model+'/v1';runtime.env['INCEPTION_API_TIMEOUT_SECONDS']='35'
            for key,value in runtime.env.items():monkeypatch.setenv(key,value)
            ensure=stack.enter_context(serve(bridge.ensure_handler()));control=stack.enter_context(serve(bridge.control_handler()))
            allowed=('PATH','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR','PLAYWRIGHT_BROWSERS_PATH','XDG_CACHE_HOME','XDG_CONFIG_HOME','TMPDIR')
            env={key:os.environ[key] for key in allowed if key in os.environ}
            assert env.get('GOTOOLCHAIN')=='local' and env.get('GOPROXY')=='off'
            for key in ('GOCACHE','GOTMPDIR'):Path(env[key]).mkdir(parents=True,exist_ok=True)
            env.update(AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION='1',AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION='1',AUTODATA_CATALOG_INTEGRATION_REQUIRED='1',AUTODATA_LIFECYCLE_TEST='1',
                AUTODATA_WORKSHOP_BROWSER_FIXTURE='1',AUTODATA_WORKSHOP_BROWSER_READY=str(directory/'ready.json'),
                AUTODATA_CATALOG_TEST_DSN=f'postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable',
                AUTODATA_CATALOG_TEST_ENSURE_URL=ensure,AUTODATA_CATALOG_TEST_CONTROL_URL=control,AUTODATA_CATALOG_TEST_CONTROL_TOKEN=bridge.token,
                AUTODATA_CATALOG_TEST_VEHICLE_ID=str(runtime.vehicle),AUTODATA_CATALOG_TEST_ARTICLE_ID=str(runtime.article_id),
                AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID=str(runtime.articles['banktwo' if provider=='bankone' else 'bankone']),
                AUTODATA_CATALOG_TEST_PROVIDER=provider,AUTODATA_CATALOG_TEST_CANDIDATE_SHA=candidate,AUTODATA_CATALOG_TEST_CASE_DIR=str(directory),
                AUTODATA_PAID_TEST_CONFIGURATION_ID=scope['configuration'],AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID=scope['adjacent'],
                AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID=scope['other_region'],AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID=scope['unscoped'],
                AUTODATA_S3_ENDPOINT='minio:9000',AUTODATA_S3_ACCESS_KEY='fixture',AUTODATA_S3_SECRET_KEY='fixture',AUTODATA_SOURCE_BUCKET=runtime.bucket)
            with (directory/'go-fixture.log').open('wb') as log:
                process=subprocess.Popen(['go','test','-count=1','-run','^TestWorkshopBrowserFixtureHTTP$','-timeout=85s','.'],cwd=ROOT/'apps/api-go',env=env,stdout=log,stderr=subprocess.STDOUT)
                ready=directory/'ready.json'
                while not ready.exists():
                    assert process.poll() is None,(directory/'go-fixture.log').read_text()
                    assert time.monotonic()<deadline-15,'fixture readiness budget exhausted'
                    time.sleep(.05)
                metadata=json.loads(ready.read_text());assert metadata['kind']=='api-fixture'
                browser_env={key:value for key,value in env.items() if key in allowed}
                browser_env.update(CANDIDATE_SHA=candidate,AUTODATA_WORKSHOP_BROWSER_CASE=root_name)
                browser_home=(directory/'browser-home').absolute()
                browser_home.mkdir(mode=0o700,exist_ok=False)
                home_stat=browser_home.lstat()
                assert stat.S_ISDIR(home_stat.st_mode) and stat.S_IMODE(home_stat.st_mode)==0o700 and home_stat.st_uid==os.getuid(),'browser home must be an owned private directory'
                browser_env['HOME']=str(browser_home)
                command=[sys.executable,str(ROOT/'scripts/dev/workshop_browser_smoke.py'),'--base-url',metadata['origin'],'--mode','api-fixture','--browser',engine,'--candidate-sha',candidate,'--output',str(directory/'browser')]
                with (directory/'browser.stdout.log').open('wb') as stdout,(directory/'browser.stderr.log').open('wb') as stderr:
                    tested=subprocess.run(command,cwd=ROOT,env=browser_env,stdout=stdout,stderr=stderr,timeout=max(1,deadline-time.monotonic()-8))
                assert tested.returncode==0,(directory/'browser.stderr.log').read_text()+(directory/'browser.stdout.log').read_text()
                evidence=json.loads((directory/'browser/evidence.json').read_text())
                assert len(evidence['results'])==1 and evidence['results'][0]['status']=='passed' and evidence['mode']=='api-fixture'
                final=bridge.snapshot();assert not final['proxy']['errors'] and final['ensure']['active']==0
                result['final_snapshot']=final
                with urlopen(Request(metadata['origin']+'/__fixture/stop',method='POST'),context=ssl._create_unverified_context(),timeout=2) as response:assert response.status==204
                assert process.wait(timeout=3)==0,(directory/'go-fixture.log').read_text();process=None
            result['worker_exits']=bridge.stop();runtime.close();runtime=None
        result['passed']=True
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
        if bridge is not None:bridge.release_model.set()
        if runtime is not None:
            try:bridge.stop() if bridge else runtime.stop_workers()
            finally:runtime.close()
        (directory/'result.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
        for path in directory.rglob('*'):
            if path.is_file():path.chmod(0o600)


def _case(root_name,engine,provider,fresh_database,monkeypatch):
    assert REQUIRED
    if os.environ.get('AUTODATA_WORKSHOP_BROWSER_CHILD')=='1':
        _child(root_name,engine,provider,Path(os.environ['AUTODATA_WORKSHOP_BROWSER_DIRECTORY']),monkeypatch);return
    start=time.monotonic()
    directory=Path('/artifacts/workshop-browser')/root_name/(engine+'-'+provider)
    directory.mkdir(mode=0o700,parents=True,exist_ok=False)
    repo=fresh_database()
    allowed=('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_R3_CANDIDATE_SHA','AUTODATA_LIFECYCLE_TEST','AUTODATA_CATALOG_INTEGRATION_REQUIRED','AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR','PLAYWRIGHT_BROWSERS_PATH','XDG_CACHE_HOME','XDG_CONFIG_HOME','TMPDIR')
    env={key:os.environ[key] for key in allowed if key in os.environ}
    env.update(AUTODATA_WORKSHOP_BROWSER_CHILD='1',AUTODATA_WORKSHOP_BROWSER_DATABASE=repo.database_name,AUTODATA_WORKSHOP_BROWSER_DIRECTORY=str(directory))
    suffix=engine if root_name=='test_browser_google_exchange_checkout_library_real_api' else engine+'-'+provider
    node='workers/ingestion-python/tests/test_workshop_browser_integration.py::'+root_name+'['+suffix+']'
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',node]
    with (directory/'child.log').open('wb') as log:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=process.wait(timeout=max(1,84-(time.monotonic()-start)))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
            pytest.fail('owned browser case exceeded90s including cleanup')
    assert code==0,(directory/'child.log').read_text()
    assert json.loads((directory/'result.json').read_text())['passed'] is True


@pytest.mark.parametrize('engine',ENGINES)
def test_browser_google_exchange_checkout_library_real_api(engine,fresh_database,monkeypatch):
    _case('test_browser_google_exchange_checkout_library_real_api',engine,'bankone',fresh_database,monkeypatch)


@pytest.mark.parametrize('engine,provider',[(e,b) for e in ENGINES for b in BANKS])
def test_browser_owned_source_canonical_and_media_real_api(engine,provider,fresh_database,monkeypatch):
    _case('test_browser_owned_source_canonical_and_media_real_api',engine,provider,fresh_database,monkeypatch)


@pytest.mark.parametrize('engine,provider',[(e,b) for e in ENGINES for b in BANKS])
def test_browser_account_scope_and_revocation_real_api(engine,provider,fresh_database,monkeypatch):
    _case('test_browser_account_scope_and_revocation_real_api',engine,provider,fresh_database,monkeypatch)


@pytest.mark.parametrize('engine,provider',[(e,b) for e in ENGINES for b in BANKS])
def test_browser_signed_refund_blocks_old_links_real_api(engine,provider,fresh_database,monkeypatch):
    _case('test_browser_signed_refund_blocks_old_links_real_api',engine,provider,fresh_database,monkeypatch)
