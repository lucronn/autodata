"""Actual-image behavior payload; import-inert, synthetic ownership mandatory.

Host use: wrap_transport(sealed_disabled_transport_class) composes independently
verified Docker contract evidence with these behavior checks. Container use:
sealed transport prepends FIXTURE and executes this file on stdin.
"""
import json
import os
import re
import uuid

HOST_CHECKS = frozenset({'actual_image','source_readonly','rootfs_readonly','environment_names',
    'entrypoint_user_workdir','synthetic_network_only','synthetic_credentials_only'})
BEHAVIOR_CHECKS = frozenset({'child_import','two_bank_years_makes_models','partial_provenance',
    'cooldown','stall_kill_reap','configuration_budget_unchanged','purchase_false','quote_false',
    'grants_library_merchant','payment_denied','provider_none','svg_png','no_article_recapture',
    'no_supplier_or_payment_or_model_request'})
IMAGE='sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7'
SOURCE='a82b31dc8850aa3956972928b8c720969765a972'
POLICY={'source_mount_readonly':True,'rootfs_readonly':True,'no_host_ports':True,
    'private_fixture_network':True,'synthetic_endpoints_only':True,'credentials_substituted':True,
    'environment_names_verified':True,'entrypoint_user_workdir_verified':True,
    'memory_limit':805306368,'pids_limit':128,'tmpfs_limit':67108864}


def ownership(fixture, env):
    database=env.get('AUTODATA_POSTGRES_DB','')
    if not (re.fullmatch(r'lifecycle_test_[a-f0-9]{32}',database)
            and fixture.get('database')==database
            and fixture.get('bucket')=='autodata-selector-fixture-'+database.removeprefix('lifecycle_test_')
            and env.get('AUTODATA_DB_ADDRESS')=='postgres:5432'
            and env.get('AUTODATA_POSTGRES_USER')=='lifecycle_test'
            and env.get('AUTODATA_POSTGRES_PASSWORD')=='lifecycle_test_only'
            and env.get('AUTODATA_S3_ENDPOINT')=='minio:9000'
            and env.get('BANKONE_BASE_URL')=='http://127.0.0.1:18311'
            and env.get('BANKTWO_BASE_URL')=='http://127.0.0.1:18312'
            and env.get('AUTODATA_COMMERCE_MODE')=='read_only'):
        raise ValueError('synthetic_fixture_required')
    for key in ('configuration','foreign_configuration','owner','organization','entitlement'):
        if str(uuid.UUID(fixture.get(key,''))) != fixture[key]: raise ValueError('synthetic_uuid')
    return database


def compose_checks(proof, behavior):
    if not (isinstance(proof,dict) and proof.get('role')=='worker'
            and proof.get('image')==IMAGE and proof.get('source')==SOURCE
            and proof.get('owned_synthetic') is True and proof.get('policy')==POLICY
            and set(behavior)==BEHAVIOR_CHECKS and all(v is True for v in behavior.values())):
        raise ValueError('fixture_proof_incomplete')
    return {**dict.fromkeys(HOST_CHECKS,True),**behavior}


def wrap_transport(base):
    """Loaded only from the externally sealed fixture_client artifact by launcher."""
    class ProofTransport(base):
        def exercise_fixture(self,identifier,manifest):
            before=self.fixture_identity(identifier)
            behavior=super().exercise_fixture(identifier,manifest)
            after=self.fixture_identity(identifier)
            if before!=after: raise ValueError('fixture_contract_changed')
            return compose_checks(after,behavior)
    return ProofTransport


def connector_response(provider,path,*,partial=False):
    """Only authored selector routes; article/model/payment paths fail closed."""
    from urllib.parse import parse_qs,urlsplit
    if provider not in ('bankone','banktwo'): raise ValueError('fixture_provider_forbidden')
    parsed=urlsplit(path); query=parse_qs(parsed.query)
    scope=parsed.path.removeprefix('/v1/catalog/')
    if parsed.path!='/v1/catalog/'+scope or scope not in ('years','makes','models'):
        raise ValueError('fixture_route_forbidden')
    if set(query)-{'year','make','cursor'} or 'cursor' in query: raise ValueError('fixture_query_forbidden')
    if partial and provider=='banktwo': return 503,{'error':'synthetic_unavailable'}
    year=int(query.get('year',['2024'])[0])
    row={'year':2024} if scope=='years' else {'year':year,'make':'Authored'}
    if scope=='models': row['model']='Fixture'
    row.update(opaque_ref='fixture-'+scope,label='2024' if scope=='years' else row.get('model',row.get('make')))
    return 200,{'request_id':'00000000-0000-4000-8000-000000000001','provider':provider,
        'source_revision':'fixture-v1','fetched_at':'2026-11-15T00:00:00Z','scope':scope,
        'items':[row],'complete':True,'next_cursor':None}


def main(fixture):
    database=ownership(fixture,os.environ)  # Refuse before importing transport clients.
    import hashlib,subprocess,sys,tempfile,threading,time
    from contextlib import ExitStack
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from io import BytesIO
    from pathlib import Path
    from unittest.mock import patch
    from urllib.error import HTTPError
    from urllib.request import ProxyHandler,Request,build_opener
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from minio import Minio
    from minio.deleteobjects import DeleteObject
    from PIL import Image
    from autodata_ingestion import commerce_service as commerce,catalog_service as catalog,selector_job as job
    from autodata_ingestion.svg_rasterization import rasterize_svg,SVGUnavailable
    opener=build_opener(ProxyHandler({}))
    checks={}; servers=[];threads=[];state={'calls':[],'forbidden':0,'partial':False,'stall':None}
    objects=None; bucket_created=False; cleanup={'database_removed':False,'bucket_removed':False}
    def connect():
        return psycopg.connect(host='postgres',dbname=database,user='lifecycle_test',
            password='lifecycle_test_only',connect_timeout=2,row_factory=dict_row,options='-c statement_timeout=5000 -c lock_timeout=1000')
    def snapshot():
        names=('customer_accounts','workshop_orders','entitlements','dataset_requests','payment_events',
               'canonical_articles','source_snapshots','source_fetch_jobs')
        with connect() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            return {t:dict(conn.execute("SELECT count(*) AS count,md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) AS digest FROM "+t+' t').fetchone()) for t in names}
    def http(path,payload=None,*,token=True,raw=None):
        data=None if payload is None and raw is None else raw if raw is not None else json.dumps(payload).encode()
        headers={'X-Autodata-Internal-Token':os.environ['AUTODATA_INGESTION_INTERNAL_TOKEN']} if token else {}
        try: response=opener.open(Request('http://127.0.0.1:3031'+path,data=data,headers=headers),timeout=24)
        except HTTPError as error: response=error
        with response: return response.status,json.loads(response.read(262145))
    def make_handler(bank):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                state['calls'].append((bank,self.path))
                try: status,body=connector_response(bank,self.path,partial=state['partial'])
                except ValueError:
                    state['forbidden']+=1;self.send_response(404);self.end_headers();return
                if state['stall']=='headers': time.sleep(5);return
                encoded=json.dumps(body).encode()
                try:
                    self.send_response(status);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(encoded) if not state['stall'] else 100000));self.end_headers()
                    if state['stall']=='trickle':
                        for _ in range(100):self.wfile.write(b' ');self.wfile.flush();time.sleep(.05)
                    else:self.wfile.write(encoded)
                except (BrokenPipeError,ConnectionResetError):pass
            def log_message(self,*_):pass
        return Handler
    try:
        before=snapshot()
        for bank,port in (('bankone',18311),('banktwo',18312)):
            server=ThreadingHTTPServer(('127.0.0.1',port),make_handler(bank));server.daemon_threads=True
            servers.append(server);thread=threading.Thread(target=server.serve_forever,daemon=True);threads.append(thread);thread.start()
        for attempt in range(80):
            try:
                assert http('/healthz')[0]==200;break
            except OSError:
                if attempt==79:raise
                time.sleep(.05)
        assert http('/internal/commerce/purchase-config',{})[1]['enabled'] is False;checks['purchase_false']=True
        status,quote=http('/internal/commerce/quote',{'configuration_id':fixture['configuration'],'region':'US'})
        assert status==200 and quote['purchasable'] is False and quote['amount_minor']==2000;checks['quote_false']=True
        owner={'customer_account_id':fixture['owner'],'organization_id':fixture['organization']}
        status,grant=http('/internal/commerce/grants/check',{**owner,'configuration_id':fixture['configuration'],'region':'US'})
        assert status==200 and grant['entitlement_id']==fixture['entitlement']
        assert http('/internal/commerce/library',{**owner,'cursor':'','limit':20})[1]['items'][0]['configuration_id']==fixture['configuration']
        for configuration,region in ((fixture['foreign_configuration'],'US'),(fixture['configuration'],'CA')):
            assert http('/internal/commerce/grants/check',{**owner,'configuration_id':configuration,'region':region})[0] in (403,404)
        service=commerce.configured_commerce();assert service.read_only and service.provider is None;checks['provider_none']=True
        for account,price,mode in [('acct_foreign','price_fixture','stripe_test'),('acct_fixture','price_foreign','stripe_test'),('acct_fixture','price_fixture','stripe_live')]:
            foreign=commerce.ReadOnlyCommerceService(commerce.database_connection,commerce.CommerceConfig(mode,account,price))
            try:foreign.grant_check(fixture['owner'],fixture['organization'],fixture['configuration'],'US')
            except commerce.CommerceError:pass
            else:raise AssertionError('foreign_scope')
            assert foreign.library(fixture['owner'],fixture['organization'])['items']==[]
        checks['grants_library_merchant']=True
        for suffix in ('checkouts','orders/status','stripe/webhook'):
            assert http('/internal/commerce/'+suffix,raw=b'invalid',token=False)[0]==401
            assert http('/internal/commerce/'+suffix,raw=b'invalid')[0]==503
        checks['payment_denied']=True
        requests=[{'scope':'years'},{'scope':'makes','year':2024,'region':'US'},
                  {'scope':'models','year':2024,'make':'Authored','region':'US'}]
        for index,request in enumerate(requests):
            if index:time.sleep(6.1)
            start=len(state['calls']);status,value=http('/v1/catalog/ensure',{**request,'idempotency_key':uuid.uuid4().hex})
            assert status==200 and value['complete'] is True and len(value['rows'])==1
            assert {x['provider'] for x in value['provenance']}=={'autoapi','autoapitwo'}
            assert len(state['calls'])-start==2
        checks['child_import']=True;checks['two_bank_years_makes_models']=True
        time.sleep(6.1);state['partial']=True
        partial={'scope':'makes','year':2023,'region':'US','idempotency_key':uuid.uuid4().hex}
        status,value=http('/v1/catalog/ensure',partial);assert status==200 and value['complete'] is False
        with connect() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            rows=conn.execute('SELECT scope_key,completion_version,selector_rows,provenance FROM vehicle_catalog_hydration_scopes ORDER BY scope_key').fetchall()
            assert len(rows)==3 and {r['scope_key'] for r in rows}=={'makes|2024|||US','models|2024|authored||US','makes|2023|||US'}
            for row in rows:
                expected=0 if row['scope_key']=='makes|2023|||US' else 1
                assert row['completion_version']==expected and len(row['selector_rows'])==1
                assert {p['provider'] for p in row['provenance']}==({'autoapi'} if expected==0 else {'autoapi','autoapitwo'})
            assert conn.execute('SELECT count(*) AS n FROM vehicle_catalog_years').fetchone()['n']==2
        checks['partial_provenance']=True
        calls=len(state['calls']);partial['idempotency_key']=uuid.uuid4().hex
        status,value=http('/v1/catalog/ensure',partial)
        assert status==200 and value['stop_reason']=='admission' and len(state['calls'])==calls;checks['cooldown']=True
        state['partial']=False
        # Exact product owned-child implementation, no PYTHONPATH inherited.
        with tempfile.TemporaryDirectory(dir='/tmp') as temp:
            for stall in ('dns','headers','trickle'):
                state['stall']=stall;pidfile=Path(temp)/('pid-'+stall)
                script='import os,socket,time;from autodata_ingestion.source_connector_client import SourceConnectorClient;'+f'open({str(pidfile)!r},"w").write(str(os.getpid()));'+('socket.getaddrinfo=lambda *a,**k:time.sleep(30);' if stall=='dns' else '')+'SourceConnectorClient("http://127.0.0.1:18311",provider="bankone").catalog("years",timeout=10)'
                with patch.dict(os.environ):
                    os.environ.pop('PYTHONPATH',None)
                    try:job.run_owned({},time.monotonic()+1.5,command=[sys.executable,'-c',script])
                    except job.SelectorJobStopped as error:assert error.reason=='elapsed'
                    else:raise AssertionError('stall_not_stopped')
                assert pidfile.exists()
                try:os.kill(int(pidfile.read_text()),0)
                except ProcessLookupError:pass
                else:raise AssertionError('child_not_reaped')
        state['stall']=None;checks['stall_kill_reap']=True
        control=catalog._ConfigurationHydrationControl()
        for _ in range(12):control.before_request()
        try:control.before_request()
        except catalog._ConfigurationHydrationStopped as error:assert error.reason=='request_limit'
        else:raise AssertionError('configuration_cap_changed')
        checks['configuration_budget_unchanged']=True
        png=rasterize_svg(b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="red"/></svg>')
        with Image.open(BytesIO(png)) as image:assert image.format=='PNG' and image.size==(40,20) and image.convert('RGB').getpixel((10,10))==(255,0,0)
        try:rasterize_svg(b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><image href="https://invalid.example/sentinel"/></svg>')
        except SVGUnavailable:pass
        else:raise AssertionError('external_svg_allowed')
        from urllib3 import PoolManager,Timeout
        objects=Minio('minio:9000',access_key='fixture',secret_key='fixture',secure=False,http_client=PoolManager(timeout=Timeout(connect=2,read=2),retries=False))
        objects.make_bucket(fixture['bucket']);bucket_created=True
        objects.put_object(fixture['bucket'],'synthetic.png',BytesIO(png),len(png),content_type='image/png')
        response=objects.get_object(fixture['bucket'],'synthetic.png')
        try:assert response.read()==png
        finally:response.close();response.release_conn()
        checks['svg_png']=True
        assert snapshot()==before;checks['no_article_recapture']=True
        assert state['forbidden']==0
        assert all(path.startswith('/v1/catalog/') for _,path in state['calls'])
        checks['no_supplier_or_payment_or_model_request']=True
        assert set(checks)==BEHAVIOR_CHECKS and all(checks.values())
    finally:
        for server in servers:server.shutdown();server.server_close()
        for thread in threads:thread.join(2)
        try:
            if objects is not None and bucket_created:
                errors=list(objects.remove_objects(fixture['bucket'],[DeleteObject(x.object_name,version_id=x.version_id) for x in objects.list_objects(fixture['bucket'],recursive=True,include_version=True)]))
                if errors:raise ValueError('fixture_bucket_cleanup_unknown')
                objects.remove_bucket(fixture['bucket'])
            cleanup['bucket_removed']=True
        finally:
            # A bucket cleanup failure cannot skip exact owned DB cleanup.
            with psycopg.connect(host='postgres',dbname='lifecycle_fixture',user='lifecycle_test',password='lifecycle_test_only',connect_timeout=2,autocommit=True,options='-c statement_timeout=5000 -c lock_timeout=1000') as conn:
                conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
                assert conn.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(database,)).fetchone()[0]==0
            cleanup['database_removed']=True
    print(json.dumps({'checks':checks,'cleanup':cleanup},sort_keys=True))


if __name__=='__main__': main(FIXTURE)
