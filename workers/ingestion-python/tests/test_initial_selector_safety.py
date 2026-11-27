"""Authored-only initial selector admission, budgets and owned-job regressions."""
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
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


def test_admission_retry_hint_uses_the_later_cooldown():
    clock = Clock()
    gate = job.SelectorAdmission(clock=clock)
    first = {'scope': 'models', 'year': 2024, 'make': 'Acura', 'region': 'US'}
    same = {**first, 'make': ' ACURA ', 'region': 'us'}
    second = {**first, 'make': 'Buick'}
    token = gate.acquire(first)
    assert gate.retry_after_ms(second) is None
    gate.release(token, complete=False)
    clock.now = 5.5
    assert gate.retry_after_ms(second) == 500
    assert gate.retry_after_ms(same) == 24_500
    assert gate.acquire(second) is None
    clock.now = 6.0
    assert gate.acquire(second)


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


@pytest.mark.parametrize('invalid,reason', [('complete', 'invalid_result'), ('oversize', 'output_limit')])
def test_owned_progress_never_publishes_invalid_frames(invalid, reason):
    frame = {'rows': [{'make': 'Authored'}], 'complete': invalid == 'complete',
             'provenance': [{'provider': 'autoapi'}], 'missing_scopes': ['makes']}
    script = f'import json; frame={frame!r}; '
    if invalid == 'oversize':
        script += f"frame['rows'][0]['make']='x'*{job.MAX_PROGRESS}; "
    script += 'print(json.dumps(frame))'
    with pytest.raises(job.SelectorJobStopped, match=reason):
        job.run_owned({},time.monotonic()+2,command=[sys.executable,'-c',script],
                      on_progress=lambda _: pytest.fail('invalid partial selector reached persistence'))


def test_owned_deadline_reaps_child_while_progress_writer_is_busy(tmp_path):
    pidfile = tmp_path / 'progress-child-pid'
    partial = {'rows': [{'make': 'Authored'}], 'complete': False,
               'provenance': [{'provider': 'autoapi'}], 'missing_scopes': ['makes']}
    script = ('import os, time; '
              f'open({str(pidfile)!r}, "w").write(str(os.getpid())); '
              f'print({json.dumps(partial)!r}, flush=True); time.sleep(30)')
    entered, release = threading.Event(), threading.Event()
    stopped = []

    def write_progress(value):
        assert value == partial
        entered.set()
        release.wait(4)

    def run():
        try:
            job.run_owned({}, time.monotonic() + .5,
                          command=[sys.executable, '-c', script], on_progress=write_progress)
        except job.SelectorJobStopped as error:
            stopped.append(error.reason)

    reader = threading.Thread(target=run)
    reader.start()
    try:
        assert entered.wait(2)
        pid = int(pidfile.read_text())
        until = time.monotonic() + 2
        while time.monotonic() < until:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.02)
        else:
            pytest.fail('a blocked persistence callback delayed reaping the owned child')
    finally:
        release.set()
        reader.join(3)
    assert stopped == ['elapsed']


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


@pytest.mark.parametrize('stall', ['dns', 'headers', 'trickle'])
def test_actual_connector_dns_headers_trickle_hard_deadline(tmp_path, stall, monkeypatch):
    """Exercise the connector's real opener/read1 path inside the owned child."""
    monkeypatch.delenv("PYTHONPATH",raising=False)
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    seen = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.set()
            if stall == 'headers':
                time.sleep(1)
                return
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', '100000')
                self.end_headers()
                for _ in range(50):
                    self.wfile.write(b' '); self.wfile.flush(); time.sleep(.03)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    pidfile=tmp_path/'actual-pid'
    script = ('import os,socket,time; from autodata_ingestion.source_connector_client import SourceConnectorClient; '
              f'open({str(pidfile)!r},"w").write(str(os.getpid())); '
              + ('socket.getaddrinfo=lambda *a,**k: time.sleep(30); ' if stall=='dns' else '')
              + f'SourceConnectorClient("http://127.0.0.1:{server.server_port}",provider="bankone").catalog("years",timeout=10)')
    try:
        started=time.monotonic()
        with pytest.raises(job.SelectorJobStopped,match='elapsed'):
            job.run_owned({},time.monotonic()+.4,command=[sys.executable,'-c',script])
        assert time.monotonic()-started < 2
        assert pidfile.exists()
        with pytest.raises(ProcessLookupError): os.kill(int(pidfile.read_text()),0)
        assert seen.is_set() == (stall != 'dns')
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_parallel_different_scopes_start_only_one_job(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    catalog._HYDRATION_RESULTS.clear()
    monkeypatch.setattr(job,'ADMISSION',job.SelectorAdmission())
    monkeypatch.setattr(catalog,'_configured_catalog_providers',lambda **_: (object(),))
    entered=threading.Event(); release=threading.Event(); calls=[]
    def owned(*a,**k):
        calls.append(1); entered.set(); assert release.wait(2)
        return {'rows':[], 'complete':True,'provenance':[],'missing_scopes':[]}
    monkeypatch.setattr(job,'run_owned',owned)
    monkeypatch.setattr(catalog,'_persist_hydration_scope',lambda *a,**k: {})
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(catalog.ensure_catalog_hydration,json.dumps({'scope':'makes','year':2024,'idempotency_key':'parallel-first'}))
        assert entered.wait(1)
        other=catalog.ensure_catalog_hydration(json.dumps({'scope':'years','idempotency_key':'parallel-other'}))
        assert other['complete'] is False and other['stop_reason']=='admission'
        release.set(); assert first.result()['complete']
    assert len(calls)==1


def test_complete_cache_never_admits_child_even_cold_years(monkeypatch):
    catalog._HYDRATION_RESULTS.clear()
    monkeypatch.setattr(job,'run_owned',lambda *a,**k: pytest.fail('cached selector dispatched'))
    result=catalog.ensure_catalog_hydration(json.dumps({'scope':'years','idempotency_key':'cached-years',
        'cache':{'complete':True,'rows':[{'year':2024}]}}))
    assert result['complete'] and result['status']=='cache_hit'


def test_banktwo_make_proof_and_model_read_share_one_request_budget(monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    from autodata_ingestion.source_connector_client import SourceConnectorClient
    from test_source_connector_client import _Response, _envelope
    monkeypatch.setattr(catalog, '_stored_banktwo_make_label', lambda *_: None)
    dispatched=[]
    def opener(request, **kwargs):
        dispatched.append(request.full_url)
        parsed=urlsplit(request.full_url); query=parse_qs(parsed.query)
        if parsed.path.endswith('/models') and query['make']==['authored']:
            return _Response({},url=request.full_url,status=404)
        scope='makes' if parsed.path.endswith('/makes') else 'models'
        item={'year':2024,'make':'Authored','opaque_ref':'authored-ref','label':'Authored'}
        if scope=='models': item['model']='Fiction'
        return _Response(_envelope('banktwo',scope=scope,items=[item],complete=True,next_cursor=None),url=request.full_url)
    control=job.SelectorJobControl(time.monotonic()+3, dispatch_interval=0)
    client=SourceConnectorClient('http://127.0.0.1:1',provider='banktwo',opener=opener)
    result=catalog._SourceCatalogProvider(client,deepening_control=control).resolve_catalog(
        catalog.CatalogRequest(2024,'authored','unknown',scope='models'))
    assert result['complete'] and len(result['rows'])==1
    assert len(dispatched) == control.requests == 2
    assert [urlsplit(url).path for url in dispatched] == ['/v1/catalog/makes', '/v1/catalog/models']
    assert parse_qs(urlsplit(dispatched[1]).query)['make'] == ['Authored']
    assert control.rows == 2 and control.bytes > 0


def test_page_response_and_decoded_rows_are_bounded_in_connector():
    from autodata_ingestion.source_connector_client import SourceConnectorClient
    from test_source_connector_client import _Response, _envelope
    control=job.SelectorJobControl(time.monotonic()+3,dispatch_interval=0)
    def huge(request,**kwargs):
        return _Response(b' '* (1024*1024+1),url=request.full_url)
    client=SourceConnectorClient('http://127.0.0.1:1',provider='bankone',opener=huge)
    with pytest.raises(job.SelectorJobStopped,match='response_limit'):
        catalog._SourceCatalogProvider(client,deepening_control=control).resolve_catalog(catalog.CatalogRequest(2024,'unknown','unknown',scope='years'))
    control=job.SelectorJobControl(time.monotonic()+3,dispatch_interval=0)
    control.rows=5000
    def one(request,**kwargs):
        return _Response(_envelope(scope='years',items=[{'year':2024,'opaque_ref':'y','label':'2024'}],complete=True,next_cursor=None),url=request.full_url)
    client=SourceConnectorClient('http://127.0.0.1:1',provider='bankone',opener=one)
    with pytest.raises(job.SelectorJobStopped,match='row_limit'):
        catalog._SourceCatalogProvider(client,deepening_control=control).resolve_catalog(catalog.CatalogRequest(2024,'unknown','unknown',scope='years'))


def test_rate_limit_stops_remaining_providers_and_budget_is_not_swallowed():
    from autodata_ingestion.source_connector_client import SourceConnectorClient
    from test_source_connector_client import _Response
    control=job.SelectorJobControl(time.monotonic()+3,dispatch_interval=0)
    def limited(request,**kwargs): return _Response({},url=request.full_url,status=429)
    first=catalog._SourceCatalogProvider(SourceConnectorClient('http://127.0.0.1:1',provider='bankone',opener=limited),deepening_control=control)
    def forbidden(*args): pytest.fail('dispatch after 429')
    service=catalog.CacheFirstCatalogService(cache_reader=lambda _:None, providers=(first,forbidden))
    with pytest.raises(job.SelectorJobStopped,match='rate_limited'):
        service.resolve(catalog.CatalogRequest(2024,'unknown','unknown',scope='years'))
    assert control.requests==1


def test_actual_http_years_boundary_uses_shared_job_not_legacy_manifest(monkeypatch):
    from autodata_ingestion.http_service import dispatch_request
    from autodata_ingestion import catalog_years
    calls=[]
    monkeypatch.setattr(catalog_years,'ensure_catalog_years',lambda *_: pytest.fail('legacy unbounded years thread route'))
    monkeypatch.setattr(catalog,'_ensure_initial_selector',lambda request,key: calls.append(request['scope']) or {'complete':False,'stop_reason':'admission'})
    result=dispatch_request('/v1/catalog/ensure',{'scope':'years','idempotency_key':'http-cold-years'})
    assert result['complete'] is False and calls==['years']


@pytest.mark.parametrize('scope',['years','makes','models'])
def test_real_owned_job_resolves_only_authored_local_connector(monkeypatch,scope):
    monkeypatch.delenv('PYTHONPATH',raising=False)
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from test_source_connector_client import _envelope
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            item={'year':2024,'opaque_ref':'authored','label':'Authored'}
            if scope != 'years': item['make']='Authored'
            if scope == 'models': item['model']='Fiction'
            body=json.dumps(_envelope(scope=scope,items=[item],complete=True,next_cursor=None)).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    monkeypatch.setenv('BANKONE_BASE_URL',f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setenv('BANKTWO_BASE_URL','')
    try:
        result=job.run_owned({'scope':scope,'year':2024,'make':'Authored'},time.monotonic()+3)
        assert result['complete'] is True and len(result['rows'])==1
        assert len(calls)==1 and calls[0].startswith('/v1/catalog/'+scope)
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_years_bounded_persistence_is_one_transaction_and_never_false_complete(monkeypatch):
    import psycopg
    from autodata_ingestion import catalog_sync
    statements=[]; events=[]; connections=[]
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql,params): statements.append((sql,params))
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): events.append('rollback' if args[0] else 'exit')
        def cursor(self): return Cursor()
        def commit(self): events.append('commit')
    def connect(**kwargs): connections.append(kwargs); return Connection()
    monkeypatch.setattr(catalog_sync,'_conninfo',lambda: {'host':'127.0.0.1'})
    monkeypatch.setattr(psycopg,'connect',connect)
    monkeypatch.setenv('AUTODATA_SOURCE_PERSIST','1')
    request={'scope':'years'}
    partial=catalog.CatalogResult(rows=({'year':2024},),complete=False,missing_scopes=('years',))
    assert catalog._persist_hydration_scope(request,partial,deadline=time.monotonic()+3)['status']=='not_complete'
    assert not connections and not statements
    mapping={'provider':'autoapi','source_uri':'http://127.0.0.1:1/v1/catalog/years','source_version':'authored-v1'}
    resolved=catalog.CatalogResult(rows=tuple({'year':year,'provider_mappings':[mapping]} for year in (2024,2024,2023)),complete=True)
    assert catalog._persist_hydration_scope(request,resolved,deadline=time.monotonic()+3)['status']=='persisted'
    assert len(connections)==1 and connections[0]['connect_timeout']==1
    assert connections[0]['options']=='-c statement_timeout=1000 -c lock_timeout=250'
    assert len(statements)==1 and 'INSERT INTO vehicle_catalog_years' in statements[0][0]
    assert sorted(row['year'] for row in statements[0][1][1].obj)==[2023,2024]
    assert all(row['source_version']=='authored-v1' for row in statements[0][1][1].obj)
    assert all('INSERT INTO vehicle_catalog_hydration_scopes' not in sql for sql,_ in statements)
    assert events==['commit','exit']
    statements.clear(); connections.clear()
    with pytest.raises(job.SelectorJobStopped,match='elapsed'):
        catalog._persist_hydration_scope(request,resolved,deadline=time.monotonic()+.5)
    assert not connections and not statements


def test_direct_initial_read_hook_charges_first_dispatch_and_body_without_timeout():
    from autodata_ingestion.source_connector_client import SourceConnectorClient
    from test_source_connector_client import _Response, _envelope
    control=job.SelectorJobControl(time.monotonic()+3,dispatch_interval=0)
    def one(request,**kwargs):
        assert 0<kwargs['timeout']<=3
        return _Response(_envelope(scope='years',items=[{'year':2024,'opaque_ref':'y','label':'2024'}],complete=True,next_cursor=None),url=request.full_url)
    client=SourceConnectorClient('http://127.0.0.1:1',provider='bankone',opener=one)
    assert client.catalog('years',read_control=control).complete
    assert control.requests==1 and control.rows==1 and control.bytes>0


def test_unfiltered_years_scope_cannot_bypass_cooldown_with_region():
    clock=Clock(); admission=job.SelectorAdmission(clock=clock)
    token=admission.acquire({'scope':'years','region':'US'})
    admission.release(token,complete=False); clock.now=7
    assert admission.acquire({'scope':'years','year':2024,'make':'ignored','region':'CA'}) is None


@pytest.mark.parametrize("delivery", ["final", "progress", "expired"])
def test_initial_models_persist_evidence_from_the_last_provider_dispatch(monkeypatch, delivery):
    import psycopg
    from autodata_ingestion import catalog_sync

    clock = Clock()
    monkeypatch.setattr(catalog.time, "monotonic", clock)
    monkeypatch.setattr(job, "ADMISSION", job.SelectorAdmission(clock=clock))
    monkeypatch.setattr(catalog, "_HYDRATION_RESULTS", {})
    monkeypatch.setattr(catalog, "_configured_catalog_providers", lambda: [object()])
    monkeypatch.setattr(catalog_sync, "_conninfo", lambda: {"host": "127.0.0.1"})
    monkeypatch.setenv("AUTODATA_SOURCE_PERSIST", "1")
    payload = {
        "rows": [{"year": 2024, "make": "Authored", "model": "Fiction"}],
        "complete": False,
        "missing_scopes": ["models", "provider"],
        "provenance": [{"provider": "autoapitwo"}],
    }

    def owned(request, deadline, *, on_progress):
        assert deadline == 20
        clock.now = 18.4
        if delivery == "final":
            return payload
        if delivery == "progress":
            on_progress(payload)
        clock.now = 20
        raise job.SelectorJobStopped("elapsed")

    writes = []
    commits = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return self

        def execute(self, sql, params):
            assert "INSERT INTO vehicle_catalog_hydration_scopes" in sql
            writes.append(params)

        def commit(self):
            commits.append(True)

    def connect(**options):
        assert options["connect_timeout"] == 1
        assert options["options"] == "-c statement_timeout=1000 -c lock_timeout=250"
        return Connection()

    monkeypatch.setattr(job, "run_owned", owned)
    monkeypatch.setattr(psycopg, "connect", connect)
    request = {"scope": "models", "year": 2024, "make": "authored", "region": "US"}
    result = catalog._ensure_initial_selector(request, "fixture")
    assert not result["complete"]
    if delivery == "expired":
        assert result["stop_reason"] == "elapsed" and not writes and not commits
        return
    [row] = writes
    assert len(commits) == 1
    assert row[6].obj == payload["provenance"]
    assert row[7].obj == [{"year": 2024, "make": "Authored", "model": "Fiction"}]
    assert row[8] == 0
    assert row[-1] == (delivery == "progress")
    if delivery == "final":
        assert result["coverage"]["status"] == "persisted"


@pytest.mark.parametrize('shared_locator', [False, True])
def test_paginated_years_retains_exact_page_provenance(shared_locator):
    from autodata_ingestion.source_connector_client import SourceConnectorClient
    from test_source_connector_client import _Response, _envelope
    control=job.SelectorJobControl(time.monotonic()+3,dispatch_interval=0)
    calls=[]
    def pages(request,**kwargs):
        calls.append(request.full_url); last=len(calls)==2
        locator = {'source_locator': 'http://127.0.0.1:1/authored'} if shared_locator else {}
        return _Response(_envelope(scope='years',items=[{'year':2023 if last else 2024,'opaque_ref':'y','label':'year'}],
                                   complete=last,next_cursor=None if last else 'authored/cursor',**locator),url=request.full_url)
    provider=catalog._SourceCatalogProvider(SourceConnectorClient('http://127.0.0.1:1',provider='bankone',opener=pages),deepening_control=control)
    result=catalog.CacheFirstCatalogService(cache_reader=lambda _:None, providers=(provider,)).resolve(
        catalog.CatalogRequest(2024,'unknown','unknown',scope='years'))
    expected = ['http://127.0.0.1:1/authored'] * 2 if shared_locator else calls
    assert [record['source_uri'] for record in result.provenance] == expected
    assert [record['metadata']['page_number'] for record in result.provenance] == [1, 2]
    records = catalog._owned_year_records(result.rows)
    assert [(row['source_uri'], row['page_number']) for row in records] == list(zip(expected, (1, 2)))


@pytest.mark.parametrize('items, complete', [([], True), ([{'label': 'Missing year'}], False)])
def test_year_source_distinguishes_true_empty_from_invalid_nonempty_page(items, complete):
    from autodata_ingestion.source_connector_client import SourceEnvelopeV1

    page = SourceEnvelopeV1('request', 'bankone', 'authored-v1', '2026-11-22T00:00:00Z', None,
                            {'items': items, 'complete': True})
    client = SimpleNamespace(base_url='http://fixture.invalid', catalog=lambda *_: page)
    service = catalog.CacheFirstCatalogService(cache_reader=lambda _: None, providers=(catalog._SourceCatalogProvider(client),))
    result = service.resolve(catalog.CatalogRequest(2024, 'unknown', 'unknown', scope='years'))
    assert result.complete is complete and not result.rows
    if complete:
        assert [(source['provider'], source['source_version']) for source in result.provenance] == [('autoapi', 'authored-v1')]
    else:
        assert not result.provenance and result.missing_scopes == ('provider',)


@pytest.mark.parametrize('failure',['incomplete','error'])
def test_two_source_partial_years_stage_verified_choices_and_retry_after_cooldown(monkeypatch,failure):
    catalog._HYDRATION_RESULTS.clear()
    clock=Clock(); healthy=[False]; calls=[]; durable=[]; staged=[]
    monkeypatch.setattr(job,'ADMISSION',job.SelectorAdmission(clock=clock))
    monkeypatch.setattr(catalog,'_HYDRATION_INCOMPLETE_TTL_SECONDS',0)
    class Provider:
        deepening_control=SimpleNamespace(initial_selector_budget=True)
        def __init__(self,name): self.name=name
        def resolve_catalog(self,request):
            calls.append(self.name)
            if self.name=='second' and not healthy[0] and failure=='error': raise TimeoutError('authored outage')
            return {'rows':[{'year':2024 if self.name=='first' else 2023}],
                    'complete':self.name=='first' or healthy[0],
                    'provenance':[{'provider':self.name}]}
    providers=(Provider('first'),Provider('second'))
    monkeypatch.setattr(catalog,'_configured_catalog_providers',lambda **_:providers)
    def owned(request,deadline,on_progress):
        resolved=catalog.CacheFirstCatalogService(cache_reader=lambda _:None,providers=providers).resolve(
            catalog.CatalogRequest(2000,'unknown','unknown',scope='years'),
            on_progress=lambda result: on_progress({'rows':list(result.rows),'provenance':list(result.provenance)}))
        return {'rows':list(resolved.rows),'complete':resolved.complete,
                'missing_scopes':list(resolved.missing_scopes),'provenance':[]}
    monkeypatch.setattr(job,'run_owned',owned)
    def persist(request,result,**kwargs):
        target = staged if kwargs.get('progress') else durable
        assert result.complete == (target is durable)
        target.extend(row['year'] for row in result.rows)
        return {'status':'persisted'}
    monkeypatch.setattr(catalog,'_persist_hydration_scope',persist)
    request=json.dumps({'scope':'years','idempotency_key':'two-source-'+failure})
    partial=catalog.ensure_catalog_hydration(request)
    assert not partial['complete'] and partial['rows'] and not durable
    assert staged == [2024]
    assert partial['coverage']=={'status':'skipped_incomplete_years','row_count':0}
    assert partial['persistence']=={'status':'skipped_incomplete_years','row_count':0}
    clock.now=7
    assert catalog.ensure_catalog_hydration(request)['stop_reason']=='admission'
    assert len(calls)==2 and not durable
    healthy[0]=True; clock.now=31
    complete=catalog.ensure_catalog_hydration(request)
    assert complete['complete'] and sorted(durable)==[2023,2024] and len(calls)==4
