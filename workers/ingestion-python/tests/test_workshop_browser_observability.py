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
        (directory/'result.json').write_text(json.dumps({'passed':True,'binding':binding}))
        (directory/'child-processes.json').write_text(json.dumps({'status':'passed','binding':binding}))
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
    assert json.loads((directory/'result.json').read_text())['passed'] is True


def test_child_setup_failure_retains_failed_sidecar_without_services(producer,monkeypatch,tmp_path):
    configure_case(producer,monkeypatch,tmp_path)
    for name,value in producer._binding_env(producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest'),'child-pytest').items():monkeypatch.setenv(name,value)
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


def fake_child_dependencies(producer,monkeypatch,tmp_path,browser_code=0,stale=False,root=ROOT_NAME):
    import contextlib
    import threading
    configure_case(producer,monkeypatch,tmp_path)
    for name,value in producer._binding_env(producer._binding(root,'chromium','bankone','parent-pytest'),'child-pytest').items():monkeypatch.setenv(name,value)
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
        row={'status':'passed','browser':'chromium','scenario':root,'provider':'bankone','observations':{'binding':binding,'status':'passed','primary_failure':None,'publication':'written'}}
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


def test_worker_changed_original_inode_is_unavailable(producer,monkeypatch,tmp_path):
    logs=[];workers=[]
    for n in (1,2):
        log=(tmp_path/('worker-'+str(n)*32+'.log')).open('w');logs.append(log);workers.append(Process([-15]))
    runtime=types.SimpleNamespace(workers=workers,logs=logs,barrier=None)
    captured=producer._capture_workers(runtime,False,artifact_root=tmp_path)
    exits=[]
    for worker,log in zip(workers,logs):
        worker.wait(3);log.close();exits.append(dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
    path=Path(logs[0].name);original=path.stat();path.unlink();path.write_text('replacement')
    replacement=path.stat();real_stat=os.stat;real_fstat=os.fstat
    def reused_identity(info):
        # Deterministically model a filesystem reusing the released inode number.
        if (info.st_dev,info.st_ino)==(replacement.st_dev,replacement.st_ino):
            return types.SimpleNamespace(st_dev=original.st_dev,st_ino=original.st_ino,
                **{key:getattr(info,key) for key in ('st_mode','st_nlink','st_uid','st_size','st_mtime_ns')})
        return info
    monkeypatch.setattr(os,'stat',lambda *args,**kwargs:reused_identity(real_stat(*args,**kwargs)))
    monkeypatch.setattr(os,'fstat',lambda *args,**kwargs:reused_identity(real_fstat(*args,**kwargs)))
    records,status=producer._finalize_workers(captured,exits,True)
    assert status=='unavailable' and records[0]['log_hash'] is None


@pytest.mark.parametrize('failure',['none','exit-count','writer-open','hash-error','capture-second','dup-second'])
def test_worker_identity_is_pinned_until_finalization_without_descriptor_leaks(producer,monkeypatch,tmp_path,failure):
    logs=[];workers=[];pins=[]
    real_dup=os.dup
    def duplicate(fd):
        if failure=='dup-second' and pins:raise OSError('injected descriptor exhaustion')
        pinned=real_dup(fd);pins.append(pinned);return pinned
    monkeypatch.setattr(os,'dup',duplicate)
    for n in (1,2):
        log=(tmp_path/('worker-'+str(n)*32+'.log')).open('w')
        log.write('owned original');log.flush();logs.append(log);workers.append(Process([-15]))
    if failure=='capture-second':workers[1].returncode=9
    try:
        capture=producer._capture_workers(types.SimpleNamespace(workers=workers,logs=logs,barrier=None),False,artifact_root=tmp_path)
        if failure in ('capture-second','dup-second'):
            assert capture==([], 'unavailable') and len(pins)==1
        else:
            assert capture[1]=='observed' and len(pins)==2
            assert all(not os.get_inheritable(fd) for fd in pins)
            exits=[]
            for worker,log in zip(workers,logs):
                worker.wait(3)
                if failure!='writer-open':log.close()
                exits.append(dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
            # Original identity remains owned even after all runtime writers close.
            assert all(os.fstat(fd).st_nlink==1 for fd in pins)
            if failure=='exit-count':exits=[]
            if failure=='hash-error':monkeypatch.setattr(producer,'_hash_artifact',forbidden)
            records,status=producer._finalize_workers(capture,exits,failure!='writer-open')
            assert status==('observed' if failure=='none' else 'unavailable')
            if failure=='none':assert all(row['log_hash'] for row in records)
            else:assert all(row['log_hash'] is None for row in records)
        for fd in pins:
            with pytest.raises(OSError):os.fstat(fd)
        if failure=='none':
            # Cleanup is idempotent even when a later open reuses a released fd.
            with (tmp_path/'unrelated').open('w') as unrelated:
                assert producer._finalize_workers(capture,exits,True)[1]=='unavailable'
                unrelated.write('still owned by its caller');unrelated.flush()
    finally:
        for log in logs:log.close()
        # A failing implementation must not leak descriptors into later tests.
        for fd in pins:
            try:os.close(fd)
            except OSError:pass


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'"\xff"'])
def test_strict_json_rejects_ambiguous_bytes(producer,raw):
    with pytest.raises((ValueError,UnicodeError)):producer._strict_json(raw)


def test_publication_rejects_symlink_ancestor(producer,tmp_path):
    real=tmp_path/'real';real.mkdir(mode=0o700)
    link=tmp_path/'link';link.symlink_to(real,target_is_directory=True)
    leaf=real/'leaf';leaf.mkdir(mode=0o700)
    with pytest.raises((ValueError,OSError)):producer._publish(link/'leaf','child-processes.json',{},262144)
    assert not list(leaf.iterdir())


def test_parent_timeout_signals_only_owned_group_and_retains_reap(producer,monkeypatch,tmp_path):
    directory=configure_case(producer,monkeypatch,tmp_path);signals=[]
    process=Process([subprocess.TimeoutExpired('child',84),subprocess.TimeoutExpired('child',2),-9])
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**kw:process)
    monkeypatch.setattr(os,'killpg',lambda pid,sig:signals.append((pid,sig)))
    with pytest.raises(AssertionError,match='API21 timeout'):producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    receipt=json.loads((directory/'parent-process.json').read_text())
    assert signals==[(123,producer.signal.SIGTERM),(123,producer.signal.SIGKILL)]
    assert receipt['child']['return_code']==-9 and receipt['child']['wait_kind']=='cleanup'
    assert receipt['status']=='failed'


def test_parent_launch_failure_does_not_signal_unowned_process(producer,monkeypatch,tmp_path):
    directory=configure_case(producer,monkeypatch,tmp_path)
    def fail(*a,**kw):raise OSError('secret-launch')
    monkeypatch.setattr(subprocess,'Popen',fail)
    with pytest.raises(AssertionError,match='API21'):producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    receipt=json.loads((directory/'parent-process.json').read_text())
    assert receipt['child']['return_code'] is None and receipt['child']['launched'] is False
    assert receipt['child']['events'][-1]['kind']=='launch-failed'


def test_repeated_cleanup_does_not_signal_finalized_process(producer):
    process=Process([-15]);receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None);receipt.launched(process)
    receipt.cleanup();before=list(receipt.data['events']);receipt.cleanup()
    assert receipt.data['events']==before and process.signals==['term']


def test_signal_and_reap_failure_never_invent_return_code(producer):
    process=Process([OSError('secret-reap')])
    def signal_failure():raise OSError('secret-signal')
    process.terminate=signal_failure
    receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None);receipt.launched(process);receipt.cleanup()
    assert receipt.data['return_code'] is None and receipt.data['reaped'] is False
    assert {e['kind'] for e in receipt.data['events']} >= {'signal-failed','reap-failed'}


@pytest.mark.parametrize('kind',['symlink','hardlink','live'])
def test_worker_unfinalized_log_does_not_get_a_hash(producer,tmp_path,kind):
    workers=[];logs=[]
    for n in (1,2):
        log=(tmp_path/('worker-'+str(n)*32+'.log')).open('w');logs.append(log);workers.append(Process([-15]))
    captured=producer._capture_workers(types.SimpleNamespace(workers=workers,logs=logs,barrier=None),False,artifact_root=tmp_path)
    exits=[]
    for worker,log in zip(workers,logs):
        worker.wait(3)
        if kind!='live':log.close()
        exits.append(dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
    path=Path(logs[0].name)
    if kind=='symlink':path.unlink();path.symlink_to(Path(logs[1].name))
    if kind=='hardlink':os.link(path,tmp_path/'extra-link')
    records,status=producer._finalize_workers(captured,exits,True)
    assert status=='unavailable' and records[0]['log_hash'] is None
    for log in logs:log.close()


def test_worker_unexpected_extra_exit_is_not_discarded(producer,tmp_path):
    logs=[];workers=[]
    for n in (1,2):
        log=(tmp_path/('worker-'+str(n)*32+'.log')).open('w');logs.append(log);workers.append(Process([-15]))
    capture=producer._capture_workers(types.SimpleNamespace(workers=workers,logs=logs,barrier=None),False,artifact_root=tmp_path)
    for worker,log in zip(workers,logs):worker.wait(3);log.close()
    outcome=dict(kind='cli',exit_code=-15,terminated=True,intentional_cleanup=True,alive_before_cleanup=True)
    records,status=producer._finalize_workers(capture,[outcome]*3,True)
    assert records==[] and status=='unavailable'


def test_private_log_is_exclusive_and_0600(producer,tmp_path):
    path=tmp_path/'go-fixture.log'
    with producer._private_log(path) as log:log.write(b'original')
    assert path.stat().st_mode & 0o777==0o600
    with pytest.raises(FileExistsError):producer._private_log(path)
    assert path.read_bytes()==b'original'


def test_actual_child_worker_branch_hashes_originals_after_stop_and_close(producer,monkeypatch,tmp_path):
    root='test_browser_owned_source_canonical_and_media_real_api'
    runtime,bridge=fake_child_dependencies(producer,monkeypatch,tmp_path,root=root)
    original_browser=subprocess.run
    def browser(*args,**kwargs):
        result=original_browser(*args,**kwargs)
        for n in (1,2):
            runtime.logs.append((tmp_path/('worker-'+str(n)*32+'.log')).open('w'))
            runtime.logs[-1].write('worker original\n');runtime.workers.append(Process([-15]))
        return result
    monkeypatch.setattr(subprocess,'run',browser)
    def stop():
        records=[]
        for worker in runtime.workers:
            assert worker.poll() is None
            code=worker.wait(3)
            records.append(dict(kind='cli',exit_code=code,terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
        runtime.workers=[]
        return records
    bridge.stop=stop
    runtime.close=lambda:[log.close() for log in runtime.logs]
    # Resolve the runtime-owned root at call time rather than the default argument.
    original_capture=producer._capture_workers
    monkeypatch.setattr(producer,'_capture_workers',lambda runtime,google:original_capture(runtime,google,artifact_root=tmp_path))
    producer._child(root,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['status']=='passed' and receipt['worker_mapping_status']=='observed'
    assert [row['original_ref'] for row in receipt['workers']]==['worker-'+'1'*32+'.log','worker-'+'2'*32+'.log']
    assert all(row['log_hash']['sha256']==hashlib.sha256(b'worker original\n').hexdigest() for row in receipt['workers'])
    assert all(row['exit_code']==-15 and row['reaped'] is True for row in receipt['workers'])


def test_child_failed_sidecar_publication_cannot_leave_passed_result(producer,monkeypatch,tmp_path):
    fake_child_dependencies(producer,monkeypatch,tmp_path)
    original=producer._publish
    def publish(directory,name,value,limit):
        if name=='child-processes.json':raise OSError('secret-publication')
        return original(directory,name,value,limit)
    monkeypatch.setattr(producer,'_publish',publish)
    with pytest.raises(RuntimeError,match='API21 publication_failed'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    assert json.loads((tmp_path/'result.json').read_text())['passed'] is False


def test_event_capacity_preserves_prefix_and_rejects_next_event(producer):
    receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None)
    for _ in range(32):receipt.event('launch-requested')
    with pytest.raises(ValueError,match='over_limit'):receipt.event('launch-requested')
    assert [e['seq'] for e in receipt.data['events']]==list(range(1,33))


def test_private_publication_exact_limit_counts_final_newline(producer,tmp_path):
    tmp_path.chmod(0o700)
    producer._publish(tmp_path,'x.json',{},3)
    assert (tmp_path/'x.json').read_bytes()==b'{}\n'
    with pytest.raises(ValueError):producer._publish(tmp_path,'x.json',{},2)
    assert (tmp_path/'x.json').read_bytes()==b'{}\n'


def test_json_support_read_is_bounded_before_parse(producer,tmp_path):
    path=tmp_path/'evidence.json';path.write_bytes(b' '*4194305)
    with pytest.raises(ValueError,match='over_limit'):producer._read_json(path)


def test_parent_always_allocates_fresh_attempt(producer,monkeypatch,tmp_path):
    configure_case(producer,monkeypatch,tmp_path)
    monkeypatch.setenv('AUTODATA_API21_RUN_ID','0'*32);monkeypatch.setenv('AUTODATA_API21_ATTEMPT_ID','1'*32)
    first=producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest')
    second=producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest')
    assert first['run_id']==second['run_id'] and first['run_id']!='0'*32
    assert first['attempt_id']!=second['attempt_id'] and first['attempt_id']!='1'*32


def test_hash_rejects_symlink_ancestor(producer,tmp_path):
    real=tmp_path/'real';real.mkdir();(real/'log').write_bytes(b'original')
    link=tmp_path/'link';link.symlink_to(real,target_is_directory=True)
    with pytest.raises((ValueError,OSError)):producer._hash_artifact(link/'log','log')


def test_support_budget_counts_parent_serialization_and_fails_at_limit_plus_one(producer,monkeypatch,tmp_path):
    value={'binding':{'root':ROOT_NAME,'engine':'chromium'},'child_artifacts':[],'status':'failed'}
    length=len((json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode())
    monkeypatch.setattr(producer,'_RUN_SUPPORT_BYTES',67108864-length)
    producer._account_support(tmp_path,value)
    assert producer._RUN_SUPPORT_BYTES==67108864
    monkeypatch.setattr(producer,'_RUN_SUPPORT_BYTES',67108865-length)
    with pytest.raises(ValueError,match='over_limit'):producer._account_support(tmp_path,value)


def test_parent_rejects_stale_child_receipt_binding(producer,monkeypatch,tmp_path):
    directory=configure_case(producer,monkeypatch,tmp_path)
    def launch(*a,**kw):
        binding=json.loads(kw['env']['AUTODATA_API21_BINDING']);binding['attempt_id']='0'*32
        (directory/'result.json').write_text(json.dumps({'passed':True,'binding':binding}))
        (directory/'child-processes.json').write_text(json.dumps({'status':'passed','binding':binding}))
        for name in ('ready.json','go-fixture.log','browser.stdout.log','browser.stderr.log','browser/evidence.json'):
            path=directory/name;path.parent.mkdir(mode=0o700,exist_ok=True);path.write_text('original')
        return Process([0])
    monkeypatch.setattr(subprocess,'Popen',launch)
    with pytest.raises(AssertionError,match='API21'):producer._case(ROOT_NAME,'chromium','bankone',lambda:types.SimpleNamespace(database_name='fake'),monkeypatch)
    assert json.loads((directory/'parent-process.json').read_text())['status']=='failed'


def test_bool_is_not_an_observed_process_exit(producer):
    receipt=producer._OwnedProcess('go-test','child-pytest',['go'],'.',None,None)
    receipt.launched(Process([True]))
    with pytest.raises(ValueError):receipt.wait(3)
    assert receipt.data['return_code'] is None


def test_inherited_binding_mismatch_remains_partial(producer,monkeypatch,tmp_path):
    configure_case(producer,monkeypatch,tmp_path)
    parent=producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest')
    env=producer._binding_env(parent,'child-pytest')
    for name,value in env.items():monkeypatch.setenv(name,value)
    monkeypatch.setenv('AUTODATA_API21_ATTEMPT_ID','0'*32)
    child=producer._binding(ROOT_NAME,'chromium','bankone','child-pytest')
    assert child['binding_state']=='partial' and child['unavailable_reason']=='source_binding_failed'
    assert child['candidate_sha']=='a'*40 and len(child['source_input_sha256'])==7


def test_failure_publication_releases_preallocated_reserve_before_retry(producer,monkeypatch,tmp_path):
    tmp_path.chmod(0o700);reserve=bytearray(16384);original=producer._publish;count=0
    def publish(directory,name,value,limit):
        nonlocal count
        count+=1
        if count==1:raise MemoryError()
        assert len(reserve)==0
        return original(directory,name,value,limit)
    monkeypatch.setattr(producer,'_publish',publish)
    value={'status':'failed','primary_failure':'timeout','publication_failure':None}
    assert producer._safe_publish(tmp_path,'parent-process.json',value,65536,reserve=reserve) is False
    assert json.loads((tmp_path/'parent-process.json').read_text())['primary_failure']=='timeout'


def test_runtime_close_retry_preserves_completed_original_worker_exits(producer,monkeypatch,tmp_path):
    root='test_browser_owned_source_canonical_and_media_real_api'
    runtime,bridge=fake_child_dependencies(producer,monkeypatch,tmp_path,root=root)
    original_browser=subprocess.run;stop_calls=0;close_calls=0
    def browser(*args,**kwargs):
        result=original_browser(*args,**kwargs)
        for n in (1,2):
            runtime.logs.append((tmp_path/('worker-'+str(n)*32+'.log')).open('w'))
            runtime.logs[-1].write('original worker\n');runtime.workers.append(Process([-15]))
        return result
    monkeypatch.setattr(subprocess,'run',browser)
    def stop():
        nonlocal stop_calls
        stop_calls+=1;outcomes=[]
        for worker in runtime.workers:
            outcomes.append(dict(kind='cli',exit_code=worker.wait(3),terminated=True,intentional_cleanup=True,alive_before_cleanup=True))
        runtime.workers=[]
        return outcomes
    def close():
        nonlocal close_calls
        close_calls+=1
        if close_calls==1:raise RuntimeError('private-close-failure')
        for log in runtime.logs:log.close()
    bridge.stop=stop;runtime.close=close
    capture=producer._capture_workers
    monkeypatch.setattr(producer,'_capture_workers',lambda runtime,google:capture(runtime,google,artifact_root=tmp_path))
    with pytest.raises(RuntimeError,match='API21'):producer._child(root,'chromium','bankone',tmp_path,monkeypatch)
    result=json.loads((tmp_path/'result.json').read_text());sidecar=json.loads((tmp_path/'child-processes.json').read_text())
    assert result['passed'] is False and sidecar['status']=='failed'
    assert [row['exit_code'] for row in result['worker_exits']]==[-15,-15]
    assert sidecar['worker_mapping_status']=='observed'
    assert len(sidecar['workers'])==2 and all(row['log_finalized'] for row in sidecar['workers'])
    assert all(row['log_hash']['sha256']==hashlib.sha256(b'original worker\n').hexdigest() for row in sidecar['workers'])
    assert stop_calls==1 and close_calls==2


@pytest.mark.parametrize('owner',['parent','child'])
def test_minimal_receipt_removes_dangling_references_and_stale_availability(producer,monkeypatch,tmp_path,owner):
    configure_case(producer,monkeypatch,tmp_path)
    binding=producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest')
    process=producer._OwnedProcess('child-pytest' if owner=='parent' else 'go-test','parent-pytest' if owner=='parent' else 'child-pytest',['go'],'.',None,None)
    process.event('launch-requested');process.launched(Process([0]));process.wait(3)
    artifact={'ref':'original.log','length':1,'sha256':'a'*64}
    if owner=='parent':
        value=dict(binding=binding,status='passed',child=process.data,child_artifacts=[artifact],child_artifact_status='finalized',
            child_launch_cause=dict(stream='process-child',producer_role='parent-pytest',seq=2),primary_failure=None,
            publication_failure=None,engine_os_exit=None,outer_pytest_exit=None)
        name='parent-process.json';limit=65536
    else:
        browser=producer._OwnedProcess('browser-runner','child-pytest',['$PYTHON','$REPO/scripts/dev/workshop_browser_smoke.py'],'.',None,None)
        browser.event('launch-requested');browser.launched(Process([0]));browser.wait(3)
        worker=dict(ordinal=1,kind='cli',original_ref='worker-'+'a'*32+'.log',mapping='observed',alive_before_cleanup=True,
            intentional_cleanup=True,terminated=True,exit_code=-15,reaped=True,log_finalized=True,log_hash=artifact,reason=None)
        value=dict(binding=dict(binding,producer_role='child-pytest'),status='passed',go=process.data,browser_runner=browser.data,workers=[worker],
            worker_mapping_status='observed',finalization_events=[],primary_failure=None,publication_failure=None,
            engine_os_exit=None,outer_pytest_exit=None)
        name='child-processes.json';limit=262144
    original=producer._publish;attempt=0
    def publish(*args):
        nonlocal attempt
        attempt+=1
        if attempt==1:raise OSError('private-write-failure')
        return original(*args)
    monkeypatch.setattr(producer,'_publish',publish)
    assert producer._safe_publish(tmp_path,name,value,limit) is False
    minimal=json.loads((tmp_path/name).read_text())
    assert minimal['status']=='failed' and minimal['publication_failure']=='publication_failed'
    if owner=='parent':
        assert minimal['child']['events']==[] and minimal['child_launch_cause'] is None
        assert minimal['child_artifacts']==[] and minimal['child_artifact_status']=='unavailable'
    else:
        assert minimal['workers']==[] and minimal['worker_mapping_status']=='unavailable'


@pytest.mark.parametrize('missing',['all','AUTODATA_API21_BINDING','empty_binding','AUTODATA_API21_RUN_ID','AUTODATA_API21_ATTEMPT_ID','malformed_run','malformed_attempt'])
def test_child_never_mints_identity_when_parent_handoff_is_missing(producer,monkeypatch,tmp_path,missing):
    configure_case(producer,monkeypatch,tmp_path)
    parent=producer._binding(ROOT_NAME,'chromium','bankone','parent-pytest')
    for name,value in producer._binding_env(parent,'child-pytest').items():monkeypatch.setenv(name,value)
    if missing=='all':
        for name in ('AUTODATA_API21_BINDING','AUTODATA_API21_RUN_ID','AUTODATA_API21_ATTEMPT_ID'):monkeypatch.delenv(name)
    elif missing=='empty_binding':monkeypatch.setenv('AUTODATA_API21_BINDING','')
    elif missing=='malformed_run':monkeypatch.setenv('AUTODATA_API21_RUN_ID','invalid')
    elif missing=='malformed_attempt':monkeypatch.setenv('AUTODATA_API21_ATTEMPT_ID','invalid')
    else:monkeypatch.delenv(missing)
    child=producer._binding(ROOT_NAME,'chromium','bankone','child-pytest')
    assert child['binding_state']=='partial' and child['unavailable_reason']=='source_binding_failed'
    assert child['candidate_sha']=='a'*40 and child['source_tree']=='b'*40 and len(child['source_input_sha256'])==7
    if missing in ('all','AUTODATA_API21_RUN_ID','malformed_run'):assert child['run_id'] is None
    else:assert child['run_id']==parent['run_id']
    if missing in ('all','AUTODATA_API21_ATTEMPT_ID','malformed_attempt'):assert child['attempt_id'] is None
    else:assert child['attempt_id']==parent['attempt_id']


def test_actual_child_without_parent_handoff_fails_before_service_setup(producer,monkeypatch,tmp_path):
    configure_case(producer,monkeypatch,tmp_path)
    for name in ('AUTODATA_API21_BINDING','AUTODATA_API21_RUN_ID','AUTODATA_API21_ATTEMPT_ID'):monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('AUTODATA_WORKSHOP_BROWSER_DATABASE','fake')
    with pytest.raises(RuntimeError,match='API21'):producer._child(ROOT_NAME,'chromium','bankone',tmp_path,monkeypatch)
    receipt=json.loads((tmp_path/'child-processes.json').read_text())
    assert receipt['status']=='failed' and receipt['binding']['binding_state']=='partial'
    assert receipt['binding']['run_id'] is None and receipt['binding']['attempt_id'] is None
    assert receipt['go']['launched'] is False and receipt['browser_runner']['launched'] is False
    assert receipt['go']['events']==[] and receipt['browser_runner']['events']==[]
