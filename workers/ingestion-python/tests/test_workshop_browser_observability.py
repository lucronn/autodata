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
