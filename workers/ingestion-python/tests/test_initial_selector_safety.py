"""Authored-only initial selector admission, budgets and owned-job regressions."""
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from autodata_ingestion import catalog_service as catalog
try:
    from autodata_ingestion import selector_job as job
except ImportError:  # red-first checkpoint before the owned job exists
    job = None


class Clock:
    def __init__(self): self.now = 0.0
    def sleep(self, seconds): self.now += seconds
    def __call__(self): return self.now


def test_shared_control_counts_requests_repairs_bytes_rows_and_time():
    clock = Clock(); control = job.SelectorJobControl(20, clock=clock, sleep=clock.sleep)
    assert control.before_request() == 20
    assert control.before_request() == 14
    assert control.before_request() == 8
    assert control.before_request() == 2
    with pytest.raises(job.SelectorJobStopped, match='elapsed'): control.before_request()
    control = job.SelectorJobControl(100, clock=lambda: 0, sleep=lambda _: None, dispatch_interval=0)
    for _ in range(12): control.before_request()
    with pytest.raises(job.SelectorJobStopped, match='request_limit'): control.before_request()
    control = job.SelectorJobControl(100, clock=lambda: 0)
    control.consume_bytes(4 * 1024 * 1024)
    with pytest.raises(job.SelectorJobStopped, match='byte_limit'): control.consume_bytes(1)
    control.consume_rows(5000)
    with pytest.raises(job.SelectorJobStopped, match='row_limit'): control.consume_rows(1)


def test_global_admission_cooldown_and_normalized_scope():
    clock = Clock(); gate = job.SelectorAdmission(clock=clock)
    first = {'scope':'models','year':2024,'make':'Acura','region':'us'}
    same = {**first,'make':' acura ','region':'US'}
    other = {**first,'year':2023}
    token = gate.acquire(first); assert token
    assert gate.acquire(same) is None and gate.acquire(other) is None
    gate.release(token, complete=False)
    clock.now = 7
    assert gate.acquire(same) is None
    other_token = gate.acquire(other); assert other_token
    gate.release(other_token, complete=True)
    clock.now = 31
    assert gate.acquire(same)


@pytest.mark.parametrize('stall', ['dns', 'headers', 'trickle'])
def test_owned_stall_is_hard_stopped_and_reaped(tmp_path, stall):
    # Synthetic process stalls before output, before headers, or after a partial
    # response byte. No supplier or serving endpoint is contacted.
    pidfile = tmp_path/'pid'
    script = ('import os,time,sys; open(sys.argv[1],"w").write(str(os.getpid())); '
              + ('sys.stdout.write("{"); sys.stdout.flush(); ' if stall=='trickle' else '')
              + 'time.sleep(30)')
    started=time.monotonic()
    with pytest.raises(job.SelectorJobStopped, match='elapsed'):
        job.run_owned({}, time.monotonic()+.25,
                      command=[sys.executable,'-c',script,str(pidfile)])
    assert time.monotonic()-started < 2.5
    if pidfile.exists():
        with pytest.raises(ProcessLookupError): os.kill(int(pidfile.read_text()),0)


def test_owned_output_limit_and_secret_stderr_are_not_forwarded():
    with pytest.raises(job.SelectorJobStopped, match='output_limit'):
        job.run_owned({},time.monotonic()+2,command=[sys.executable,'-c','import sys;sys.stdout.write("x"*5000000)'])
    with pytest.raises(job.SelectorJobStopped) as caught:
        job.run_owned({},time.monotonic()+2,command=[sys.executable,'-c','import sys;sys.stderr.write("SECRET_PROVIDER_URL");sys.exit(1)'])
    assert 'SECRET_PROVIDER' not in str(caught.value)


@pytest.mark.parametrize('scope',['years','makes','models'])
def test_public_initial_selector_never_schedules_descendants(monkeypatch,scope):
    catalog._HYDRATION_RESULTS.clear()
    monkeypatch.setattr(job,'ADMISSION',job.SelectorAdmission())
    monkeypatch.setattr(catalog,'_configured_catalog_providers',lambda **_: (object(),))
    monkeypatch.setattr(job,'run_owned',lambda *a,**k: {'rows':[], 'complete':True,'provenance':[],'missing_scopes':[]})
    monkeypatch.setattr(catalog,'_persist_resolved_catalog_rows',lambda *a,**k: {'status':'persisted'})
    monkeypatch.setattr(catalog,'_persist_hydration_scope',lambda *a,**k: {'status':'persisted'})
    monkeypatch.setattr(catalog,'_schedule_selector_deepening',lambda *a,**k: pytest.fail('uncharged descendant job'))
    result=catalog.ensure_catalog_hydration(json.dumps({'scope':scope,'year':2024,'make':'Acura','idempotency_key':'public-'+scope}))
    assert result['complete'] is True


def test_expired_child_never_persists_false_completion(monkeypatch):
    catalog._HYDRATION_RESULTS.clear(); monkeypatch.setattr(job,'ADMISSION',job.SelectorAdmission())
    monkeypatch.setattr(catalog,'_configured_catalog_providers',lambda **_: (object(),))
    def expired(*a,**k): raise job.SelectorJobStopped('elapsed')
    monkeypatch.setattr(job,'run_owned',expired)
    monkeypatch.setattr(catalog,'_persist_resolved_catalog_rows',lambda *a,**k: pytest.fail('late row write'))
    monkeypatch.setattr(catalog,'_persist_hydration_scope',lambda *a,**k: pytest.fail('false coverage'))
    result=catalog.ensure_catalog_hydration(json.dumps({'scope':'years','idempotency_key':'expired'}))
    assert result['complete'] is False and result['rows']==[]


def test_existing_public_selector_must_not_start_detached_deepening(monkeypatch):
    catalog._HYDRATION_RESULTS.clear()
    monkeypatch.setattr(catalog,'_configured_catalog_providers',lambda **_: (object(),))
    monkeypatch.setattr(catalog.CacheFirstCatalogService,'resolve',lambda *a: catalog.CatalogResult(
        rows=({'year':2024,'make':'Authored','region':'US'},), complete=True))
    if job is not None:
        monkeypatch.setattr(job,'ADMISSION',job.SelectorAdmission())
        monkeypatch.setattr(job,'run_owned',lambda *a,**k: {'rows':[{'year':2024,'make':'Authored','region':'US'}], 'complete':True,'provenance':[],'missing_scopes':[]})
    monkeypatch.setattr(catalog,'_persist_resolved_catalog_rows',lambda *a,**k: {})
    monkeypatch.setattr(catalog,'_persist_hydration_scope',lambda *a,**k: {})
    monkeypatch.setattr(catalog,'_schedule_selector_deepening',lambda *a,**k: pytest.fail('public initial selector started uncharged descendants'))
    assert catalog.ensure_catalog_hydration(json.dumps({'scope':'makes','year':2024,'idempotency_key':'red-descendants'}))['complete']
