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
_RUN_SUPPORT_BYTES=0
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


def _read_original(path,limit,expected=None):
    directory=_open_directory(path.parent)
    try:
        before=os.stat(path.name,dir_fd=directory,follow_symlinks=False);_regular(before)
        if expected is not None and (before.st_dev,before.st_ino)!=expected:raise ValueError('replaced artifact')
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        with os.fdopen(fd,'rb') as stream:
            actual=os.fstat(stream.fileno());_regular(actual)
            if (actual.st_dev,actual.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('replaced artifact')
            raw=stream.read(limit+1);after=os.fstat(stream.fileno());_regular(after)
        if len(raw)>limit:raise ValueError('over_limit')
        if (after.st_size,after.st_mtime_ns)!=(actual.st_size,actual.st_mtime_ns):raise ValueError('unfinalized artifact')
        final=os.stat(path.name,dir_fd=directory,follow_symlinks=False);_regular(final)
        if (final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns)!=(actual.st_dev,actual.st_ino,actual.st_size,actual.st_mtime_ns):raise ValueError('replaced artifact')
        return raw
    finally:os.close(directory)


def _hash_artifact(path,ref,expected=None):
    raw=_read_original(path,8388608,expected)
    return {'ref':ref,'length':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def _read_json(path):return _strict_json(_read_original(path,4194304))


def _private_log(path):
    return os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')


def _open_directory(directory):
    path=Path(directory).absolute()
    if '..' in path.parts:raise ValueError('unsafe directory')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        return fd
    except BaseException:os.close(fd);raise


def _publish(directory,name,value,limit):
    if Path(name).name!=name or name in ('.','..'):raise ValueError('unsafe destination')
    raw=_canonical(value)
    if len(raw)>limit:raise ValueError('over_limit')
    fd=_open_directory(directory);temporary='.'+name+'.'+secrets.token_hex(8)
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
            os.fchmod(log.fileno(),0o600)
            if worker.poll() is not None:raise ValueError('mapping_unavailable')
            captured.append((worker,log,path,(info.st_dev,info.st_ino)))
        if len({item[3] for item in captured})!=2:raise ValueError('mapping_unavailable')
    except BaseException:return ([], 'unavailable')
    return (captured,'observed')


def _finalize_workers(capture,exits,closed):
    pairs,status=capture
    if status!='observed':return [],status
    if len(exits)!=len(pairs):return [],'unavailable'
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
        except BaseException:row.update(mapping='unavailable',reason='log_not_finalized' if not closed or not log.closed else 'mapping_unavailable');status='unavailable'
        records.append(row)
    return records,status


def _binding(root,engine,bank,role):
    suffix=engine if root=='test_browser_google_exchange_checkout_library_real_api' else engine+'-'+bank
    binding=dict(binding_state='partial',unavailable_reason='source_binding_failed',api_observability_version=API21_VERSION,
        run_id=_RUN_ID if role=='parent-pytest' else os.environ.get('AUTODATA_API21_RUN_ID'),attempt_id=secrets.token_hex(16) if role=='parent-pytest' else os.environ.get('AUTODATA_API21_ATTEMPT_ID'),
        case_id=root+'['+suffix+']',root=root,engine=engine,bank=bank,candidate_sha=None,source_tree=None,source_input_sha256={},producer_role=role)
    for key in ('run_id','attempt_id'):
        if not isinstance(binding[key],str) or not re.fullmatch('[a-f0-9]{32}',binding[key]):binding[key]=None
    try:
        candidate=os.environ['AUTODATA_R3_CANDIDATE_SHA'];tree=os.environ['AUTODATA_API21_SOURCE_TREE']
        if not re.fullmatch('[a-f0-9]{40}',candidate) or not re.fullmatch('[a-f0-9]{40}',tree):raise ValueError('source_binding_failed')
        binding.update(candidate_sha=candidate,source_tree=tree)
        for name in _INPUTS:binding['source_input_sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        inherited=os.environ.get('AUTODATA_API21_BINDING') if role!='parent-pytest' else None
        if role!='parent-pytest':
            if not inherited or binding['run_id'] is None or binding['attempt_id'] is None:raise ValueError('source_binding_failed')
            expected=_strict_json(inherited);expected['producer_role']=role
            binding.update(binding_state='complete',unavailable_reason=None)
            if binding!=expected:raise ValueError('source_binding_failed')
        if any(binding[key] is None for key in ('run_id','attempt_id')):raise ValueError('source_binding_failed')
        binding.update(binding_state='complete',unavailable_reason=None)
    except BaseException:binding.update(binding_state='partial',unavailable_reason='source_binding_failed')
    return binding


def _binding_env(binding,role):
    value=dict(binding,producer_role=role)
    return dict(AUTODATA_API21_BINDING=_canonical(value).decode().strip(),AUTODATA_API21_RUN_ID=value['run_id'],
        AUTODATA_API21_ATTEMPT_ID=value['attempt_id'],AUTODATA_API21_SOURCE_TREE=value['source_tree'] or '')


def _safe_publish(directory,name,receipt,limit,reserve=None):
    try:_publish(directory,name,receipt,limit);return True
    except BaseException:
        if reserve is not None:reserve.clear()
        receipt['status']='failed';receipt['publication_failure']='publication_failed'
        if receipt.get('primary_failure') is None:receipt['primary_failure']='publication_failed'
        # Keep the same closed schema, with bounded unavailable collections.
        minimal=dict(receipt)
        for key in ('workers','finalization_events','child_artifacts'):
            if key in minimal:minimal[key]=[]
        for key in ('go','browser_runner','child'):
            if key in minimal:
                minimal[key]=dict(minimal[key],events=[],output_hashes=[])
        if 'child_launch_cause' in minimal:minimal['child_launch_cause']=None
        if 'child_artifact_status' in minimal:minimal['child_artifact_status']='unavailable'
        if minimal.get('worker_mapping_status')=='observed':minimal['worker_mapping_status']='unavailable'
        try:_publish(directory,name,minimal,min(limit,16384))
        except BaseException:print('API21_PUBLICATION_FAILED',file=sys.stderr)
        return False


def _normalized(command,directory,origin=None):
    result=[]
    for value in command:
        value=str(value)
        if value==sys.executable:value='$PYTHON'
        elif origin is not None and value==origin:value='$ORIGIN'
        elif value==str(directory) or value.startswith(str(directory)+'/'):value='$CASE'+value[len(str(directory)):]
        elif value.startswith(str(ROOT)+'/'):value='$REPO'+value[len(str(ROOT)):]
        result.append(value)
    if len(result)>32 or any(len(v.encode())>512 for v in result):raise ValueError('over_limit')
    return result


def _account_support(directory,receipt):
    # Only bytes actually visible to this owner count here. The later outer JUnit
    # is unavailable to this process and still requires full transport admission.
    global _RUN_SUPPORT_BYTES
    cost=len(_canonical(receipt))
    for artifact in receipt['child_artifacts']:
        if type(artifact['length']) is not int or not 0<=artifact['length']<=8388608:raise ValueError('over_limit')
        cost+=artifact['length']
    child_path=directory/'child-processes.json'
    if child_path.exists():
        child=_read_json(child_path)
        for worker in child.get('workers',[]):
            name=worker['original_ref']
            if not re.fullmatch(r'worker-[a-f0-9]{32}\.log',name):raise ValueError('mapping_unavailable')
            actual=_hash_artifact(ARTIFACT_ROOT/name,name)
            if worker['log_hash']!=actual:raise ValueError('log_not_finalized')
            cost+=actual['length']
    binding=receipt['binding']
    screenshot=directory/'browser'/binding['engine']/(binding['root']+'-failure.png')
    if screenshot.exists():cost+=_hash_artifact(screenshot,str(screenshot.relative_to(ARTIFACT_ROOT)))['length']
    _RUN_SUPPORT_BYTES+=cost
    if _RUN_SUPPORT_BYTES>67108864:raise ValueError('over_limit')


def _lifecycle(receipt,operation,state,reason=None,elapsed_us=0):
    events=receipt['finalization_events']
    if len(events)>=64:raise ValueError('over_limit')
    events.append(dict(seq=len(events)+1,phase=operation,caused_by=[],elapsed_us=elapsed_us,
        payload=dict(kind='lifecycle',operation=operation,state=state,reason=reason)))


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
    result_reserve=bytearray(16384);sidecar_reserve=bytearray(16384)
    binding=_binding(root_name,engine,provider,'child-pytest')
    runtime=bridge=process=None;capture=([],'unavailable');closed=False;workers_stopped=False;failure=None
    google=root_name=='test_browser_google_exchange_checkout_library_real_api'
    prefix=str(directory.relative_to(ARTIFACT_ROOT))+'/'
    go=_OwnedProcess('go-test','child-pytest',['go','test','-count=1','-run','^TestWorkshopBrowserFixtureHTTP$','-timeout=85s','.'],'apps/api-go',prefix+'go-fixture.log',prefix+'go-fixture.log')
    browser=_OwnedProcess('browser-runner','child-pytest',[],'.',prefix+'browser.stdout.log',prefix+'browser.stderr.log')
    sidecar=dict(binding=binding,status='failed',go=go.data,browser_runner=browser.data,workers=[],worker_mapping_status='unavailable',
        finalization_events=[],primary_failure=None,publication_failure=None,engine_os_exit=None,outer_pytest_exit=None)
    candidate=binding['candidate_sha']
    result=dict(version='v1',mode='api-fixture',candidate_sha=candidate,browser=engine,provider=provider,test=root_name,
        fixture_database=None,passed=False,api_observability_version=API21_VERSION,binding=binding)
    try:
        assert binding['binding_state']=='complete','API21 source binding unavailable'
        with ExitStack() as stack:
            repo=Repository(os.environ['AUTODATA_WORKSHOP_BROWSER_DATABASE']);result['fixture_database']=repo.database_name
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
            with _private_log(directory/'go-fixture.log') as log:
                go.event('launch-requested')
                process=subprocess.Popen(['go','test','-count=1','-run','^TestWorkshopBrowserFixtureHTTP$','-timeout=85s','.'],cwd=ROOT/'apps/api-go',env=env,stdout=log,stderr=subprocess.STDOUT)
                go.launched(process)
                ready=directory/'ready.json'
                while not ready.exists():
                    code=process.poll()
                    if code is not None:go.observed(code,'poll','normal')
                    assert code is None,'API21 fixture exited before readiness'
                    assert time.monotonic()<deadline-15,'fixture readiness budget exhausted'
                    time.sleep(.05)
                metadata=_read_json(ready);assert metadata['kind']=='api-fixture'
                browser_env={key:value for key,value in env.items() if key in allowed}
                browser_env.update(_binding_env(binding,'browser-runner'))
                browser_env.update(CANDIDATE_SHA=candidate,AUTODATA_WORKSHOP_BROWSER_CASE=root_name)
                browser_home=(directory/'browser-home').absolute()
                browser_home.mkdir(mode=0o700,exist_ok=False)
                home_stat=browser_home.lstat()
                assert stat.S_ISDIR(home_stat.st_mode) and stat.S_IMODE(home_stat.st_mode)==0o700 and home_stat.st_uid==os.getuid(),'browser home must be an owned private directory'
                browser_env['HOME']=str(browser_home)
                command=[sys.executable,str(ROOT/'scripts/dev/workshop_browser_smoke.py'),'--base-url',metadata['origin'],'--mode','api-fixture','--browser',engine,'--candidate-sha',candidate,'--output',str(directory/'browser')]
                browser.data['argv']=_normalized(command,directory,metadata['origin'])
                browser.event('launch-requested');browser.data['started_us']=browser.elapsed()
                with _private_log(directory/'browser.stdout.log') as stdout,_private_log(directory/'browser.stderr.log') as stderr:
                    try:tested=subprocess.run(command,cwd=ROOT,env=browser_env,stdout=stdout,stderr=stderr,timeout=max(1,deadline-time.monotonic()-8))
                    except subprocess.TimeoutExpired:browser.data['launched']=True;browser.event('timeout',reason='timeout');raise
                    browser.data.update(launched=True);browser.event('launch-succeeded')
                    browser.observed(tested.returncode,'wait','normal')
                assert tested.returncode==0,'API21 browser runner failed'
                evidence=_read_json(directory/'browser/evidence.json')
                assert len(evidence['results'])==1 and evidence['results'][0]['status']=='passed' and evidence['mode']=='api-fixture'
                expected_binding=dict(binding,producer_role='browser-runner')
                assert evidence['api_observability_version']==API21_VERSION and evidence['candidate_sha']==candidate
                assert evidence['binding']==expected_binding
                assert evidence['input_sha256']=={name:digest for name,digest in binding['source_input_sha256'].items() if name!=_INPUTS[-1]}
                row=evidence['results'][0]
                assert (row['browser'],row['scenario'],row['provider'])==(engine,root_name,provider)
                observed=row['observations']
                assert observed['binding']==expected_binding and observed['status']=='passed' and observed['primary_failure'] is None and observed['publication']=='written'
                final=bridge.snapshot();assert not final['proxy']['errors'] and final['ensure']['active']==0
                result['final_snapshot']=final
                with urlopen(Request(metadata['origin']+'/__fixture/stop',method='POST'),context=ssl._create_unverified_context(),timeout=2) as response:assert response.status==204
                _lifecycle(sidecar,'fixture-stop','completed',elapsed_us=go.elapsed())
                assert go.wait(3)==0,'API21 fixture stop failed';process=None
            capture=_capture_workers(runtime,google)
            _lifecycle(sidecar,'worker-stop','requested',elapsed_us=go.elapsed())
            result['worker_exits']=bridge.stop();workers_stopped=True;_lifecycle(sidecar,'worker-stop','completed',elapsed_us=go.elapsed())
            _lifecycle(sidecar,'runtime-close','requested',elapsed_us=go.elapsed())
            runtime.close();closed=True;runtime=None;_lifecycle(sidecar,'runtime-close','completed',elapsed_us=go.elapsed())
        result['passed']=True
    except BaseException as exc:
        failure=_failure(exc);sidecar['primary_failure']=failure
        if not go.data['launched'] and go.data['events']:go.event('launch-failed',reason='launch_failed')
        if not browser.data['launched'] and browser.data['events']:browser.event('launch-failed',reason='launch_failed')
    finally:
        try:go.cleanup()
        except BaseException:
            failure=failure or 'reap_failed';sidecar['primary_failure']=failure
        if runtime is not None:
            if capture[1]=='unavailable':capture=_capture_workers(runtime,google)
            try:
                if bridge is not None:bridge.release_model.set()
                if not workers_stopped:
                    if bridge is not None:result['worker_exits']=bridge.stop()
                    else:runtime.stop_workers()
                    workers_stopped=True
                    _lifecycle(sidecar,'worker-stop','completed',elapsed_us=go.elapsed())
            except BaseException:
                failure=failure or 'close_failed';_lifecycle(sidecar,'worker-stop','failed','close_failed',elapsed_us=go.elapsed())
            try:runtime.close();closed=True;_lifecycle(sidecar,'runtime-close','completed',elapsed_us=go.elapsed())
            except BaseException:
                failure=failure or 'close_failed';_lifecycle(sidecar,'runtime-close','failed','close_failed',elapsed_us=go.elapsed())
        sidecar['workers'],sidecar['worker_mapping_status']=_finalize_workers(capture,result.get('worker_exits',[]),closed)
        if sidecar['worker_mapping_status']=='unavailable':failure=failure or 'mapping_unavailable'
        for owned in (go,browser):
            if owned.data['reaped'] is True:
                try:
                    owned.data['output_hashes']=[_hash_artifact(ARTIFACT_ROOT/name,name) for name in dict.fromkeys((owned.data['stdout_ref'],owned.data['stderr_ref'])) if name]
                except BaseException:failure=failure or 'log_not_finalized'
        if not (go.data['return_code']==0 and browser.data['return_code']==0):failure=failure or 'not_observed'
        result['passed']=result['passed'] and failure is None
        sidecar.update(status='passed' if result['passed'] else 'failed',primary_failure=failure)
        try:_publish(directory,'result.json',result,4194304)
        except BaseException:
            result_reserve.clear()
            failure=failure or 'publication_failed';result['passed']=False;sidecar.update(status='failed',primary_failure=failure,publication_failure='publication_failed')
            try:_publish(directory,'result.json',{k:v for k,v in result.items() if k not in ('final_snapshot','worker_exits')},16384)
            except BaseException:print('API21_PUBLICATION_FAILED',file=sys.stderr)
        if not _safe_publish(directory,'child-processes.json',sidecar,262144,reserve=sidecar_reserve):
            failure=failure or 'publication_failed';result['passed']=False
            try:_publish(directory,'result.json',{k:v for k,v in result.items() if k not in ('final_snapshot','worker_exits')},16384)
            except BaseException:print('API21_PUBLICATION_FAILED',file=sys.stderr)
    if failure:raise RuntimeError('API21 '+failure) from None


def _case(root_name,engine,provider,fresh_database,monkeypatch):
    assert REQUIRED
    if os.environ.get('AUTODATA_WORKSHOP_BROWSER_CHILD')=='1':
        _child(root_name,engine,provider,Path(os.environ['AUTODATA_WORKSHOP_BROWSER_DIRECTORY']),monkeypatch);return
    start=time.monotonic()
    directory=ARTIFACT_ROOT/'workshop-browser'/root_name/(engine+'-'+provider)
    for parent in (ARTIFACT_ROOT/'workshop-browser',ARTIFACT_ROOT/'workshop-browser'/root_name):
        parent.mkdir(mode=0o700,exist_ok=True)
        info=parent.lstat()
        assert stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700,'API21 private directory required'
    directory.mkdir(mode=0o700,exist_ok=False)
    publication_reserve=bytearray(16384)
    binding=_binding(root_name,engine,provider,'parent-pytest')
    suffix=engine if root_name=='test_browser_google_exchange_checkout_library_real_api' else engine+'-'+provider
    node='workers/ingestion-python/tests/test_workshop_browser_integration.py::'+root_name+'['+suffix+']'
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',node]
    child=_OwnedProcess('child-pytest','parent-pytest',_normalized(command,directory),'.',str((directory/'child.log').relative_to(ARTIFACT_ROOT)),str((directory/'child.log').relative_to(ARTIFACT_ROOT)))
    receipt=dict(binding=binding,status='failed',child=child.data,child_artifacts=[],child_artifact_status='unavailable',child_launch_cause=None,
        primary_failure=None,publication_failure=None,engine_os_exit=None,outer_pytest_exit=None)
    failure=None
    try:
        assert binding['binding_state']=='complete','API21 source binding unavailable'
        repo=fresh_database()
        allowed=('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_R3_CANDIDATE_SHA','AUTODATA_LIFECYCLE_TEST','AUTODATA_CATALOG_INTEGRATION_REQUIRED','AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR','PLAYWRIGHT_BROWSERS_PATH','XDG_CACHE_HOME','XDG_CONFIG_HOME','TMPDIR')
        env={key:os.environ[key] for key in allowed if key in os.environ}
        env.update(_binding_env(binding,'child-pytest'))
        env.update(AUTODATA_WORKSHOP_BROWSER_CHILD='1',AUTODATA_WORKSHOP_BROWSER_DATABASE=repo.database_name,AUTODATA_WORKSHOP_BROWSER_DIRECTORY=str(directory))
        with _private_log(directory/'child.log') as log:
            child.event('launch-requested')
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            child.launched(process)
            receipt['child_launch_cause']=dict(stream='process-child',producer_role='parent-pytest',seq=child.data['events'][-1]['seq'])
            try:code=child.wait(max(1,84-(time.monotonic()-start)))
            except subprocess.TimeoutExpired:
                child.cleanup(group=True);raise
        assert code==0,'API21 child failed'
        child_result=_read_json(directory/'result.json');child_sidecar=_read_json(directory/'child-processes.json')
        expected_binding=dict(binding,producer_role='child-pytest')
        assert child_result['passed'] is True and child_result['binding']==expected_binding,'API21 child result failed'
        assert child_sidecar['status']=='passed' and child_sidecar['binding']==expected_binding,'API21 child receipts failed'
        receipt['status']='passed'
    except BaseException as exc:
        failure=_failure(exc)
        if not child.data['launched'] and child.data['events']:child.event('launch-failed',reason='launch_failed')
    finally:
        try:child.cleanup(group=True)
        except BaseException:failure=failure or 'reap_failed'
        if child.data['reaped'] is True:
            names=('child.log','result.json','ready.json','go-fixture.log','browser.stdout.log','browser.stderr.log','browser/evidence.json','child-processes.json')
            for name in names:
                try:
                    ref=str((directory/name).relative_to(ARTIFACT_ROOT))
                    receipt['child_artifacts'].append(_hash_artifact(directory/name,ref))
                except BaseException:pass
            receipt['child_artifact_status']='finalized' if len(receipt['child_artifacts'])==8 else 'partial'
            if receipt['child_artifact_status']!='finalized':failure=failure or 'log_not_finalized'
            child.data['output_hashes']=[row for row in receipt['child_artifacts'] if row['ref'].endswith('/child.log')]
        receipt.update(status='passed' if failure is None and receipt['status']=='passed' else 'failed',primary_failure=failure)
        try:_account_support(directory,receipt)
        except BaseException as exc:
            failure=failure or ('over_limit' if isinstance(exc,ValueError) and exc.args==('over_limit',) else 'read_failed')
            receipt.update(status='failed',primary_failure=failure)
        if not _safe_publish(directory,'parent-process.json',receipt,65536,reserve=publication_reserve):failure=failure or 'publication_failed'
    if failure:raise AssertionError('API21 '+failure) from None


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
