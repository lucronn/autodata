"""Opt-in, task-only PostgreSQL proof with authored localhost connector bytes."""
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import psycopg
from psycopg import sql
import pytest
from autodata_ingestion import catalog_service as catalog, selector_job
from autodata_ingestion.http_service import make_handler
from test_source_connector_client import _envelope

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def isolated_selector(monkeypatch):
    if os.getenv('AUTODATA_SELECTOR_ISOLATED_TEST')!='1':
        pytest.skip('explicit task-only selector PostgreSQL fixture required')
    host=os.getenv('AUTODATA_SELECTOR_TEST_HOST','')
    if not re.fullmatch(r'172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}',host):
        raise RuntimeError('private task-only Docker fixture host required')
    conninfo=dict(host=host,port=5432,user='selector436',password='selector436_fixture_only',connect_timeout=2)
    name='selector436_test_'+uuid.uuid4().hex
    with psycopg.connect(**conninfo,dbname='selector436_fixture',autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn=psycopg.conninfo.make_conninfo(**conninfo,dbname=name)
    # Exact owning table DDL, without unrelated vector/identity migrations.
    definitions=[('002_platform_spine.sql','source_snapshots'),('003_canonical_vehicle.sql','vehicles'),
                 ('030_vehicle_catalog_years.sql','vehicle_catalog_years'),
                 ('033_catalog_scope_coverage.sql','vehicle_catalog_hydration_scopes')]
    with psycopg.connect(dsn,autocommit=True) as connection:
        connection.execute('CREATE TABLE schema_migrations(version text PRIMARY KEY)')
        for filename,table in definitions:
            source=(ROOT/'db/migrations'/filename).read_text()
            match=re.search(r'CREATE TABLE IF NOT EXISTS '+table+r' \(.*?\n\);',source,re.S)
            assert match, table
            connection.execute(match[0])
        connection.execute((ROOT/'db/migrations/042_catalog_selector_rows.sql').read_text())
    for key,value in {'AUTODATA_DB_ADDRESS':host+':5432','AUTODATA_POSTGRES_DB':name,
                      'AUTODATA_POSTGRES_USER':'selector436','AUTODATA_POSTGRES_PASSWORD':'selector436_fixture_only',
                      'AUTODATA_SOURCE_PERSIST':'1','BANKTWO_BASE_URL':''}.items(): monkeypatch.setenv(key,value)
    monkeypatch.setattr(selector_job,'ADMISSION',selector_job.SelectorAdmission())
    catalog._HYDRATION_RESULTS.clear()
    state={'calls':[], 'complete':True, 'status':200}
    class Connector(BaseHTTPRequestHandler):
        def do_GET(self):
            state['calls'].append(self.path)
            if state['status']!=200:
                self.send_response(state['status']); self.end_headers(); return
            body=json.dumps(_envelope(scope='years',items=[
                {'year':2024,'opaque_ref':'authored-2024','label':'2024'},
                {'year':2023,'opaque_ref':'authored-2023','label':'2023'}],
                complete=state['complete'],next_cursor=None if state['complete'] else 'next')).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    source=ThreadingHTTPServer(('127.0.0.1',0),Connector)
    worker=ThreadingHTTPServer(('127.0.0.1',0),make_handler('selector436-fixture-token'))
    threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (source,worker)]
    monkeypatch.setenv('BANKONE_BASE_URL',f'http://127.0.0.1:{source.server_port}')
    for thread in threads: thread.start()
    def request(key='cold-years'):
        body=json.dumps({'scope':'years','idempotency_key':key}).encode()
        with urlopen(Request(f'http://127.0.0.1:{worker.server_port}/v1/catalog/ensure',body,
                            headers={'X-Autodata-Internal-Token':'selector436-fixture-token','Content-Type':'application/json'}),timeout=24) as response:
            return json.load(response)
    try:
        yield dsn,state,request,f'http://127.0.0.1:{worker.server_port}',name
    finally:
        for server in (source,worker): server.shutdown(); server.server_close()
        for thread in threads: thread.join(2)
        with psycopg.connect(**conninfo,dbname='selector436_fixture',autocommit=True) as connection:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def test_http_cold_years_owned_job_durable_ordered_and_no_fake_marker(isolated_selector,monkeypatch):
    from autodata_ingestion import catalog_years
    monkeypatch.setattr(catalog_years,'ensure_catalog_years',lambda *_: pytest.fail('legacy daemon called'))
    dsn,state,request,_,_=isolated_selector
    result=request()
    assert result['complete'] is True and len(result['rows'])==2
    with psycopg.connect(dsn) as connection:
        rows=connection.execute('SELECT year,provider,source_version,source_uri,source_snapshot_id FROM vehicle_catalog_years ORDER BY year').fetchall()
        assert [r[0] for r in rows]==[2023,2024]
        assert all(r[1]=='autoapi' and r[2]=='revision-1' and r[3].endswith('/v1/catalog/years') and r[4] is None for r in rows)
        assert connection.execute('SELECT count(*) FROM vehicle_catalog_hydration_scopes').fetchone()[0]==0
        assert connection.execute('SELECT count(*) FROM source_snapshots').fetchone()[0]==0
    assert len(state['calls'])==1
    assert request()['complete'] is True and len(state['calls'])==1


def test_http_failed_provider_cannot_create_years_or_complete_marker(isolated_selector):
    dsn,state,request,_,_=isolated_selector
    state['status']=503
    result=request()
    assert result['complete'] is False
    with psycopg.connect(dsn) as connection:
        assert connection.execute('SELECT count(*) FROM vehicle_catalog_years').fetchone()[0]==0
        assert connection.execute('SELECT count(*) FROM vehicle_catalog_hydration_scopes').fetchone()[0]==0
    assert len(state['calls'])==1


def test_years_upsert_lock_timeout_rolls_back_without_marker(isolated_selector):
    dsn,state,request,_,_=isolated_selector
    with psycopg.connect(dsn) as lock:
        lock.execute('LOCK TABLE vehicle_catalog_years IN ACCESS EXCLUSIVE MODE')
        start=time.monotonic()
        with pytest.raises(HTTPError) as caught: request()
        assert caught.value.code==502 and time.monotonic()-start<3
    with psycopg.connect(dsn) as connection:
        assert connection.execute('SELECT count(*) FROM vehicle_catalog_years').fetchone()[0]==0
        assert connection.execute('SELECT count(*) FROM vehicle_catalog_hydration_scopes').fetchone()[0]==0


def test_go_cold_years_handler_through_actual_python_http_and_pg(isolated_selector):
    if os.getenv('AUTODATA_SELECTOR_GO_TEST')!='1': pytest.skip('explicit Go cross-language fixture opt-in')
    dsn,state,_,worker,name=isolated_selector
    from urllib.parse import quote
    host=os.environ['AUTODATA_SELECTOR_TEST_HOST']
    env={**os.environ,'AUTODATA_SELECTOR_GO_DSN':f'postgres://selector436:selector436_fixture_only@{host}:5432/{name}?sslmode=disable',
         'AUTODATA_SELECTOR_WORKER_URL':worker}
    result=subprocess.run(['go','test','-count=1','-run','^TestSelectorOwnedColdYearsFixture$','.'],
                          cwd=ROOT/'apps/api-go',env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    assert result.returncode==0,result.stdout[-6000:]
    assert len(state['calls'])==1


def test_partial_selector_marker_remains_partial_until_complete(isolated_selector):
    dsn,_,_,_,_=isolated_selector
    request={'scope':'makes','year':2024,'region':'US'}
    partial=catalog.CatalogResult(rows=({'year':2024,'make':'Authored','region':'US'},),
                                  complete=False,missing_scopes=('makes',))
    catalog._persist_hydration_scope(request,partial,deadline=time.monotonic()+3)
    with psycopg.connect(dsn) as connection:
        version,rows=connection.execute('SELECT completion_version,selector_rows FROM vehicle_catalog_hydration_scopes').fetchone()
        assert version==0 and len(rows)==1
    complete=catalog.CatalogResult(rows=partial.rows,complete=True)
    catalog._persist_hydration_scope(request,complete,deadline=time.monotonic()+3)
    with psycopg.connect(dsn) as connection:
        assert connection.execute('SELECT completion_version FROM vehicle_catalog_hydration_scopes').fetchone()[0]==1
