"""Exactly 21 required browser cases over actual PG/auth/commerce/catalog/S3 HTTP."""
from contextlib import ExitStack
import json
import hashlib
import re
import secrets
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


API21_VERSION='api21-producer-v2'
ARTIFACT_ROOT=Path('/artifacts')
_RUN_ID=secrets.token_hex(16)
_INPUTS=('scripts/dev/workshop_browser_smoke.py','scripts/dev/fixtures/workshop_customer/scenarios.json',
    'scripts/dev/fixtures/workshop_customer/firebase_transport.js','scripts/dev/fixtures/workshop_customer/hostile_source.json',
    'scripts/dev/fixtures/workshop_customer/stripe_checkout.html','apps/api-go/workshop_browser_fixture_test.go',
    'workers/ingestion-python/tests/test_workshop_browser_integration.py')


def _canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')


def _strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('invalid_json')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_json')))


def _regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid():raise ValueError('unsafe artifact')


def _hash_artifact(path,ref,expected=None):
    before=path.lstat();_regular(before)
    if expected is not None and (before.st_dev,before.st_ino)!=expected:raise ValueError('replaced artifact')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        actual=os.fstat(stream.fileno());_regular(actual)
        if (actual.st_dev,actual.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('replaced artifact')
        raw=stream.read(8388609)
        after=os.fstat(stream.fileno())
    if len(raw)>8388608 or (after.st_size,after.st_mtime_ns)!=(actual.st_size,actual.st_mtime_ns):raise ValueError('unfinalized artifact')
    final=path.lstat()
    if (final.st_dev,final.st_ino)!=(actual.st_dev,actual.st_ino):raise ValueError('replaced artifact')
    return {'ref':ref,'length':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _publish(directory,name,value,limit):
    if Path(name).name!=name or name in ('.','..'):raise ValueError('unsafe destination')
    raw=_canonical(value)
    if len(raw)>limit:raise ValueError('over_limit')
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    fd=os.open(directory,flags);temporary='.'+name+'.'+secrets.token_hex(8)
    try:
        info=os.fstat(fd)
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('unsafe directory')
        try:previous=os.stat(name,dir_fd=fd,follow_symlinks=False);_regular(previous)
        except FileNotFoundError:previous=None
        output=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        with os.fdopen(output,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        try:current=os.stat(name,dir_fd=fd,follow_symlinks=False);_regular(current)
        except FileNotFoundError:current=None
        identity=lambda item:None if item is None else (item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns)
        if identity(previous)!=identity(current):raise ValueError('replaced destination')
        os.replace(temporary,name,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
    finally:
        try:os.unlink(temporary,dir_fd=fd)
        except FileNotFoundError:pass
        os.close(fd)


def _failure(exc):
    if isinstance(exc,subprocess.TimeoutExpired):return 'timeout'
    if isinstance(exc,AssertionError):return 'assertion_failed'
    if isinstance(exc,(KeyboardInterrupt,SystemExit)):return 'cancelled'
    return 'internal_error'


class _OwnedProcess:
    def __init__(self,role,owner,argv,cwd,stdout,stderr):
        self.start=time.monotonic();self.process=None
        self.data=dict(role=role,observer_role=owner,argv=argv,cwd=cwd,launched=False,events=[],return_code=None,
            return_code_source='unavailable',wait_kind='unavailable',intentional_cleanup=False,reaped=None,
            alive_final=None,started_us=None,finished_us=None,stdout_ref=stdout,stderr_ref=stderr,output_hashes=[])
    def elapsed(self):return max(0,int((time.monotonic()-self.start)*1000000))
    def event(self,kind,code=None,reason=None):
        if len(self.data['events'])>=32:raise ValueError('over_limit')
        self.data['events'].append(dict(seq=len(self.data['events'])+1,kind=kind,elapsed_us=self.elapsed(),return_code=code,reason=reason))
    def launched(self,process):
        self.process=process;self.data.update(launched=True,started_us=self.elapsed());self.event('launch-succeeded')
    def observed(self,code,source,kind):
        if type(code) is not int:raise ValueError('unavailable exit')
        self.data.update(return_code=code,return_code_source=source,wait_kind=kind,reaped=True,alive_final=False,finished_us=self.elapsed())
        self.event('wait-completed',code)
        return code
    def wait(self,timeout,kind='normal'):
        try:return self.observed(self.process.wait(timeout=timeout),'wait',kind)
        except subprocess.TimeoutExpired:self.event('timeout',reason='timeout');raise
        except BaseException:self.event('reap-failed',reason='reap_failed');raise
    def cleanup(self,group=False):
        if self.process is None or self.data['reaped'] is True:return
        code=self.process.poll()
        if code is not None:self.observed(code,'poll','cleanup');return
        self.data.update(intentional_cleanup=True,alive_final=True,wait_kind='cleanup')
        for name,sig in (('term',signal.SIGTERM),('kill',signal.SIGKILL)):
            self.event(name+'-requested')
            try:
                if group:os.killpg(self.process.pid,sig)
                else:getattr(self.process,'terminate' if name=='term' else 'kill')()
                self.event(name+'-sent')
            except BaseException:self.event('signal-failed',reason='signal_failed')
            try:self.wait(2,'cleanup');return
            except subprocess.TimeoutExpired:continue
            except BaseException:break
        self.data['reaped']=False


def _capture_workers(runtime,google,artifact_root=ARTIFACT_ROOT):
    workers=list(runtime.workers);logs=list(runtime.logs)
    if google and not workers and not logs:return ([], 'not_started')
    if google or runtime.barrier or len(workers)!=2 or len(logs)!=2 or len({id(w) for w in workers})!=2 or len({id(l) for l in logs})!=2:return ([], 'unavailable')
    captured=[]
    try:
        for worker,log in zip(workers,logs):
            path=Path(log.name)
            if path.parent!=artifact_root or not re.fullmatch(r'worker-[a-f0-9]{32}\.log',path.name):raise ValueError('mapping_unavailable')
            info=os.fstat(log.fileno());_regular(info)
            if worker.poll() is not None:raise ValueError('mapping_unavailable')
            captured.append((worker,log,path,(info.st_dev,info.st_ino)))
        if len({item[3] for item in captured})!=2:raise ValueError('mapping_unavailable')
    except BaseException:return ([], 'unavailable')
    return (captured,'observed')


def _finalize_workers(capture,exits,closed):
    pairs,status=capture
    if status!='observed':return [],status
    records=[]
    for index,(worker,log,path,identity) in enumerate(pairs):
        row=dict(ordinal=index+1,kind='cli',original_ref=path.name,mapping='observed',alive_before_cleanup=True,
            intentional_cleanup=None,terminated=None,exit_code=None,reaped=None,log_finalized=False,log_hash=None,reason=None)
        try:
            outcome=exits[index]
            if set(outcome)!={'kind','exit_code','terminated','intentional_cleanup','alive_before_cleanup'} or outcome['kind']!='cli' or type(outcome['exit_code']) is not int:raise ValueError('mapping_unavailable')
            if not all(outcome[key] is True for key in ('terminated','intentional_cleanup','alive_before_cleanup')):raise ValueError('mapping_unavailable')
            if worker.poll()!=outcome['exit_code']:raise ValueError('mapping_unavailable')
            row.update({key:outcome[key] for key in ('alive_before_cleanup','intentional_cleanup','terminated','exit_code')});row['reaped']=True
            if not closed or not log.closed:raise ValueError('log_not_finalized')
            row['log_hash']=_hash_artifact(path,path.name,identity);row['log_finalized']=True
        except BaseException:row['reason']='log_not_finalized' if not closed or not log.closed else 'mapping_unavailable';status='unavailable'
        records.append(row)
    return records,status


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
