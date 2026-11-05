"""Offline execution of the actual API21 integration producer; no service imports."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import types

import pytest


def forbidden(*args, **kwargs):
    raise AssertionError('forbidden external operation')


@pytest.fixture
def producer(monkeypatch):
    lifecycle=types.ModuleType('lifecycle_support')
    lifecycle.fresh_database=lifecycle.LifecycleRuntime=lifecycle.Repository=forbidden
    paid=types.ModuleType('test_paid_catalog_api_integration')
    class PaidBridge:
        def __init__(self,*args,**kwargs):forbidden()
    paid.PaidBridge=PaidBridge
    paid.configure_scoped_runtime=paid.serve=forbidden
    monkeypatch.setitem(sys.modules,'lifecycle_support',lifecycle)
    monkeypatch.setitem(sys.modules,'test_paid_catalog_api_integration',paid)
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(socket,'socket',forbidden)
    monkeypatch.setattr(os,'killpg',forbidden)
    import urllib.request
    monkeypatch.setattr(urllib.request,'urlopen',forbidden)
    spec=importlib.util.spec_from_file_location('_private_api21_integration',Path(__file__).with_name('test_workshop_browser_integration.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Process:
    pid=123
    def __init__(self,codes):self.codes=iter(codes);self.returncode=None;self.signals=[]
    def wait(self,timeout):
        code=next(self.codes)
        if isinstance(code,BaseException):raise code
        self.returncode=code;return code
    def poll(self):return self.returncode
    def terminate(self):self.signals.append('term')
    def kill(self):self.signals.append('kill')


@pytest.mark.parametrize('code',[0,7,-15])
def test_actual_wait_value_is_preserved(producer,code):
    receipt=producer._OwnedProcess('go-test','child-pytest',['go','test'], 'apps/api-go',None,None)
    process=Process([code]);receipt.launched(process)
    assert receipt.wait(3)==code
    data=receipt.data
    assert data['return_code']==code and data['return_code_source']=='wait'
    assert data['reaped'] is True and data['alive_final'] is False


def test_timeout_is_not_a_successful_exit(producer):
    receipt=producer._OwnedProcess('browser-runner','child-pytest',['$PYTHON'],'.',None,None)
    receipt.event('timeout',reason='timeout')
    assert receipt.data['return_code'] is None
    assert receipt.data['return_code_source']=='unavailable'


def test_cleanup_retains_kill_and_actual_negative_exit(producer):
    receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None)
    process=Process([subprocess.TimeoutExpired('go',2),-9]);receipt.launched(process)
    receipt.cleanup()
    assert process.signals==['term','kill']
    assert receipt.data['return_code']==-9 and receipt.data['intentional_cleanup'] is True
    assert [e['kind'] for e in receipt.data['events']][-3:]==['kill-requested','kill-sent','wait-completed']


def test_early_nonzero_poll_is_observed(producer):
    receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None)
    process=Process([]);process.returncode=8;receipt.launched(process);receipt.cleanup()
    assert receipt.data['return_code']==8 and receipt.data['return_code_source']=='poll'
    assert process.signals==[]


def test_private_atomic_publication_and_original_digest(producer,tmp_path):
    tmp_path.chmod(0o700)
    producer._publish(tmp_path,'child-processes.json',{'status':'failed'},262144)
    raw=(tmp_path/'child-processes.json').read_bytes()
    assert raw==b'{"status":"failed"}\n'
    assert (tmp_path/'child-processes.json').stat().st_mode & 0o777==0o600
    assert producer._hash_artifact(tmp_path/'child-processes.json','child-processes.json')['sha256']==hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('kind',['symlink','hardlink'])
def test_publication_rejects_unsafe_destination(producer,tmp_path,kind):
    tmp_path.chmod(0o700);other=tmp_path/'other';other.write_bytes(b'original')
    target=tmp_path/'child-processes.json'
    if kind=='symlink':target.symlink_to(other)
    else:os.link(other,target)
    with pytest.raises(ValueError):producer._publish(tmp_path,target.name,{},262144)
    assert other.read_bytes()==b'original'


def test_publication_rejects_over_limit_and_nonfinite(producer,tmp_path):
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError):producer._publish(tmp_path,'x.json',{'x':'a'*100},32)
    with pytest.raises(ValueError):producer._publish(tmp_path,'x.json',{'x':float('nan')},1000)
    assert not list(tmp_path.iterdir())


def test_worker_pair_capture_survives_cleared_runtime(producer,tmp_path):
    logs=[];workers=[]
    for n in (1,2):
        path=tmp_path/('worker-'+str(n)*32+'.log');log=path.open('w');log.write('original\n');logs.append(log);workers.append(Process([-15]))
    runtime=types.SimpleNamespace(workers=workers,logs=logs,barrier=None)
    capture=producer._capture_workers(runtime,False,artifact_root=tmp_path)
    runtime.workers=[]
    exits=[]
    for worker,log in zip(workers,logs):
        worker.wait(3);log.close();exits.append(dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
    records,status=producer._finalize_workers(capture,exits,True)
    assert status=='observed' and len(records)==2
    assert all(row['log_finalized'] and row['exit_code']==-15 for row in records)
    assert records[0]['original_ref']=='worker-'+ '1'*32 +'.log'


def test_worker_partial_launch_is_unavailable(producer,tmp_path):
    log=(tmp_path/('worker-'+'a'*32+'.log')).open('w')
    runtime=types.SimpleNamespace(workers=[],logs=[log],barrier=None)
    captured=producer._capture_workers(runtime,False,artifact_root=tmp_path);log.close()
    records,status=producer._finalize_workers(captured,[],True)
    assert status=='unavailable' and records==[]


ROOT_NAME='test_browser_google_exchange_checkout_library_real_api'


def configure_case(producer,monkeypatch,tmp_path):
    tmp_path.chmod(0o700);monkeypatch.setattr(producer,'ARTIFACT_ROOT',tmp_path)
    monkeypatch.setattr(producer,'REQUIRED',True)
    monkeypatch.setenv('AUTODATA_R3_CANDIDATE_SHA','a'*40)
    monkeypatch.setenv('AUTODATA_API21_SOURCE_TREE','b'*40)
    monkeypatch.delenv('AUTODATA_WORKSHOP_BROWSER_CHILD',raising=False)
    return tmp_path/'workshop-browser'/ROOT_NAME/'chromium-bankone'


@pytest.mark.parametrize('code',[0,7])
def test_parent_publishes_after_actual_child_wait(producer,monkeypatch,tmp_path,code):
    directory=configure_case(producer,monkeypatch,tmp_path)
    def launch(command,**kwargs):
        assert command[-1].endswith(ROOT_NAME+'[chromium]')
        binding=json.loads(kwargs['env']['AUTODATA_API21_BINDING'])
        assert binding['producer_role']=='child-pytest' and binding['case_id']==ROOT_NAME+'[chromium]'
        assert len(binding['source_input_sha256'])==7
        (directory/'result.json').write_text('{"passed":true}')
        (directory/'child-processes.json').write_text('{"status":"passed"}')
        for name in ('ready.json','go-fixture.log','browser.stdout.log','browser.stderr.log','browser/evidence.json'):
            path=directory/name;path.parent.mkdir(mode=0o700,exist_ok=True);path.write_text('original')
        return Process([code])
    monkeypatch.setattr(subprocess,'Popen',launch)
    if code:
        with pytest.raises(AssertionError,match='API21'):producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    else:producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    receipt=json.loads((directory/'parent-process.json').read_text())
    assert receipt['child']['return_code']==code
    assert receipt['status']==('passed' if code==0 else 'failed')
    assert receipt['engine_os_exit'] is None and receipt['outer_pytest_exit'] is None
    assert next(r for r in receipt['child_artifacts'] if r['ref'].endswith('child.log'))['length']==0
    assert (directory/'result.json').read_text()=='{"passed":true}'


def test_child_setup_failure_retains_failed_sidecar_without_services(producer,monkeypatch,tmp_path):
    configure_case(producer,monkeypatch,tmp_path)
    monkeypatch.setenv('AUTODATA_WORKSHOP_BROWSER_DATABASE','fake')
    monkeypatch.setattr(producer,'Repository',lambda name:types.SimpleNamespace(database_name=name))
    def fail_setup(*args):raise RuntimeError('secret-sentinel')
    monkeypatch.setattr(producer,'LifecycleRuntime',fail_setup)
    with pytest.raises(RuntimeError,match='API21'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['status']=='failed' and receipt['go']['return_code'] is None
    assert receipt['browser_runner']['return_code'] is None
    assert 'secret-sentinel' not in (tmp_path/'child-processes.json').read_text()
    assert json.loads((tmp_path/'result.json').read_text())['passed'] is False


def fake_child_dependencies(producer,monkeypatch,tmp_path,browser_code=0,stale=False):
    import contextlib
    import threading
    configure_case(producer,monkeypatch,tmp_path)
    monkeypatch.setenv('AUTODATA_WORKSHOP_BROWSER_DATABASE','fake')
    for key,value in {'GOTOOLCHAIN':'local','GOPROXY':'off','GOCACHE':str(tmp_path/'cache'),'GOTMPDIR':str(tmp_path/'gotmp')}.items():monkeypatch.setenv(key,value)
    monkeypatch.setattr(producer,'Repository',lambda name:types.SimpleNamespace(database_name=name))
    runtime=types.SimpleNamespace(env={},vehicle='vehicle',article_id='article',articles={'banktwo':'other'},bucket='bucket',workers=[],logs=[],barrier=None,close=lambda:None,stop_workers=lambda:None)
    monkeypatch.setattr(producer,'LifecycleRuntime',lambda repo,stack:runtime)
    monkeypatch.setattr(producer,'configure_scoped_runtime',lambda *a:{key:key for key in ('configuration','adjacent','other_region','unscoped')})
    bridge=types.SimpleNamespace(token='never-retain-token',model_handler=lambda:None,ensure_handler=lambda:None,control_handler=lambda:None,
        snapshot=lambda:{'proxy':{'errors':[]},'ensure':{'active':0}},stop=lambda:[],release_model=threading.Event())
    monkeypatch.setattr(producer,'BrowserBridge',lambda runtime:bridge)
    monkeypatch.setattr(producer,'serve',lambda handler:contextlib.nullcontext('https://127.0.0.1:1234'))
    def popen(command,**kwargs):
        assert command==['go','test','-count=1','-run','^TestWorkshopBrowserFixtureHTTP$','-timeout=85s','.']
        (tmp_path/'ready.json').write_text('{"kind":"api-fixture","origin":"https://127.0.0.1:1234"}')
        return Process([0])
    monkeypatch.setattr(subprocess,'Popen',popen)
    def browser(command,**kwargs):
        assert kwargs['timeout']<=70 and kwargs['timeout']>=1
        binding=json.loads(kwargs['env']['AUTODATA_API21_BINDING'])
        assert binding['producer_role']=='browser-runner' and kwargs['env']['AUTODATA_API21_RUN_ID']==binding['run_id']
        if stale:binding['attempt_id']='0'*32
        output=tmp_path/'browser';output.mkdir(mode=0o700)
        row={'status':'passed','browser':'chromium','scenario':ROOT_NAME,'provider':'bankone','observations':{'binding':binding,'status':'passed','primary_failure':None,'publication':'written'}}
        evidence={'mode':'api-fixture','candidate_sha':'a'*40,'api_observability_version':'api21-producer-v2','binding':binding,
            'input_sha256':{k:v for k,v in binding['source_input_sha256'].items() if not k.endswith('test_workshop_browser_integration.py')},'results':[row]}
        (output/'evidence.json').write_text(json.dumps(evidence))
        return types.SimpleNamespace(returncode=browser_code)
    monkeypatch.setattr(subprocess,'run',browser)
    monkeypatch.setattr(producer,'urlopen',lambda *a,**kw:contextlib.nullcontext(types.SimpleNamespace(status=204)))
    return runtime,bridge


@pytest.mark.parametrize('browser_code',[0,9])
def test_actual_child_branches_keep_owned_outcomes(producer,monkeypatch,tmp_path,browser_code):
    fake_child_dependencies(producer,monkeypatch,tmp_path,browser_code)
    if browser_code:
        with pytest.raises(RuntimeError,match='API21'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    else:producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['status']==('passed' if browser_code==0 else 'failed')
    assert receipt['browser_runner']['return_code']==browser_code
    assert receipt['go']['return_code']==0
    assert receipt['worker_mapping_status']=='not_started'
    assert len(receipt['go']['output_hashes'])==1
    assert len(receipt['browser_runner']['output_hashes'])==2
    assert 'never-retain-token' not in (tmp_path/'child-processes.json').read_text()


def test_child_rejects_stale_browser_binding(producer,monkeypatch,tmp_path):
    fake_child_dependencies(producer,monkeypatch,tmp_path,stale=True)
    with pytest.raises(RuntimeError,match='API21'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    assert json.loads((tmp_path/'child-processes.json').read_text())['status']=='failed'


def test_browser_timeout_keeps_exit_unavailable(producer,monkeypatch,tmp_path):
    fake_child_dependencies(producer,monkeypatch,tmp_path)
    def timeout(*a,**kw):raise subprocess.TimeoutExpired('browser',3)
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(RuntimeError,match='API21 timeout'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['browser_runner']['launched'] is True
    assert receipt['browser_runner']['return_code'] is None
    assert receipt['browser_runner']['return_code_source']=='unavailable'
    assert receipt['status']=='failed'


def test_primary_failure_survives_runtime_close_failure(producer,monkeypatch,tmp_path):
    runtime,_=fake_child_dependencies(producer,monkeypatch,tmp_path,browser_code=7)
    def fail():raise RuntimeError('secret-close')
    runtime.close=fail
    with pytest.raises(RuntimeError,match='API21 assertion_failed'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['primary_failure']=='assertion_failed'
    assert any(e['payload']['reason']=='close_failed' for e in receipt['finalization_events'])


def test_child_launch_failure_retains_null_exit(producer,monkeypatch,tmp_path):
    fake_child_dependencies(producer,monkeypatch,tmp_path)
    def fail(*a,**kw):raise OSError('secret-launch')
    monkeypatch.setattr(subprocess,'Popen',fail)
    with pytest.raises(RuntimeError,match='API21'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['go']['launched'] is False and receipt['go']['return_code'] is None
    assert receipt['go']['events'][-1]['kind']=='launch-failed'


def test_failed_publication_retries_closed_failure_shape(producer,monkeypatch,tmp_path):
    original=producer._publish;calls=[]
    def first_fails(directory,name,value,limit):
        calls.append(name)
        if len(calls)==1:raise OSError('secret-write')
        return original(directory,name,value,limit)
    monkeypatch.setattr(producer,'_publish',first_fails);tmp_path.chmod(0o700)
    value=dict(binding={},status='passed',child={},child_artifacts=[],child_artifact_status='unavailable',child_launch_cause=None,
        primary_failure=None,publication_failure=None,engine_os_exit=None,outer_pytest_exit=None)
    assert producer._safe_publish(tmp_path,'parent-process.json',value,65536) is False
    receipt=json.loads((tmp_path/'parent-process.json').read_text())
    assert receipt['status']=='failed' and receipt['primary_failure']=='publication_failed'
    assert receipt['publication_failure']=='publication_failed'


def test_failed_minimal_publication_reports_only_fixed_marker(producer,monkeypatch,tmp_path,capsys):
    def fail(*a,**kw):raise OSError('secret-write')
    monkeypatch.setattr(producer,'_publish',fail)
    value={'status':'failed','primary_failure':'timeout','publication_failure':None}
    assert producer._safe_publish(tmp_path,'parent-process.json',value,65536) is False
    assert capsys.readouterr().err=='API21_PUBLICATION_FAILED\n'
    assert not (tmp_path/'parent-process.json').exists()
    assert value['primary_failure']=='timeout'


def test_parent_missing_originals_cannot_pass(producer,monkeypatch,tmp_path):
    directory=configure_case(producer,monkeypatch,tmp_path)
    def launch(*a,**kw):
        (directory/'result.json').write_text('{"passed":true}');(directory/'child-processes.json').write_text('{"status":"passed"}')
        return Process([0])
    monkeypatch.setattr(subprocess,'Popen',launch)
    with pytest.raises(AssertionError,match='API21'):producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    receipt=json.loads((directory/'parent-process.json').read_text())
    assert receipt['status']=='failed' and receipt['child_artifact_status']=='partial'


def test_worker_changed_original_inode_is_unavailable(producer,tmp_path):
    logs=[];workers=[]
    for n in (1,2):
        log=(tmp_path/('worker-'+str(n)*32+'.log')).open('w');logs.append(log);workers.append(Process([-15]))
    runtime=types.SimpleNamespace(workers=workers,logs=logs,barrier=None)
    captured=producer._capture_workers(runtime,False,artifact_root=tmp_path)
    exits=[]
    for worker,log in zip(workers,logs):
        worker.wait(3);log.close();exits.append(dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
    path=Path(logs[0].name);path.unlink();path.write_text('replacement')
    records,status=producer._finalize_workers(captured,exits,True)
    assert status=='unavailable' and records[0]['log_hash'] is None


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'"\xff"'])
def test_strict_json_rejects_ambiguous_bytes(producer,raw):
    with pytest.raises((ValueError,UnicodeError)):producer._strict_json(raw)
