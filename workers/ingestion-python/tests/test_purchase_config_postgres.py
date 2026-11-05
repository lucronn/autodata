"""Separate opt-in Task59 regressions; no frozen acceptance inventory credit."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
_REQUIRED = os.getenv('AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION') == '1'


@pytest.fixture(autouse=True)
def task59_required():
    if not _REQUIRED:
        pytest.skip('requires separate Task59 isolated lifecycle runner')
    assert os.getenv('AUTODATA_LIFECYCLE_TEST') == '1', 'Task59 requires isolated lifecycle fixture'
    artifact = Path(os.environ['AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR'])
    assert artifact.is_absolute() and artifact.is_dir(), 'dedicated artifacts missing'
    assert not artifact.is_relative_to(Path(__file__).resolve().parents[3]), 'artifacts must be outside source'


@pytest.fixture
def purchase_fixture(task59_required):
    # Import only after required-mode guard: unavailable dependencies must fail,
    # and ordinary source discovery does not require PostgreSQL/Stripe packages.
    from lifecycle_support import fresh_database as database_fixture, seed_vehicle, seed_configuration
    from test_commerce_postgres import StripeFixture
    from autodata_ingestion.commerce_service import CommerceService, CommerceConfig
    from autodata_ingestion.purchase_config import PurchaseConfig
    databases = database_fixture.__wrapped__()
    fresh = next(databases)
    try:
        repo = fresh()
        config = str(seed_configuration(repo, seed_vehicle(repo)))
        stripe = StripeFixture()
        now = [datetime.now(UTC)]
        enabled = PurchaseConfig.from_public(dict(enabled=True, terms_version='workshop-v1',
            terms_url='https://legal.example.test/terms', privacy_url='https://legal.example.test/privacy',
            refund_url='https://legal.example.test/refund', contact_url='https://legal.example.test/contact',
            tax_notice='Synthetic fixture notice'))
        def service(config_value):
            return CommerceService(repo.connect, CommerceConfig('stripe_test','acct_fixture','price_fixture'),
                stripe.provider, clock=lambda: now[0], purchase_config=config_value)
        with repo.connect() as conn:
            account = conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture',%s) RETURNING customer_account_id,personal_organization_id", (uuid.uuid4().hex,)).fetchone()
        owner = (str(account['customer_account_id']), str(account['personal_organization_id']))
        yield dict(repo=repo, stripe=stripe, now=now, enabled=enabled, service=service,
            current=service(enabled), owner=owner, configuration=config)
    finally:
        try:
            next(databases)
        except StopIteration:
            pass


def checkout(f, key=None, configuration=None):
    return f['current'].checkout(*f['owner'],key or str(uuid.uuid4()),dict(
        configuration_id=configuration or f['configuration'],region='US',terms_version='workshop-v1'))


def row(f, order_id):
    with f['repo'].connect() as conn:
        return conn.execute('SELECT * FROM workshop_orders WHERE order_id=%s',(order_id,)).fetchone()


def snapshot(f):
    # Actual full rows, including expiry/status, corroborate no mapping/order/grant writes.
    with f['repo'].connect() as conn:
        return {table: [r['value'] for r in conn.execute(
            'SELECT to_jsonb(t)::text AS value FROM '+table+' t ORDER BY to_jsonb(t)::text').fetchall()]
            for table in ('workshop_orders','workshop_checkout_requests','entitlements','dataset_requests','dataset_projections')}


def write_artifact(name, value):
    target = Path(os.environ['AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR']) / name
    target.write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')


def pause(f):
    from autodata_ingestion.purchase_config import PurchaseConfig
    f['current'] = f['service'](PurchaseConfig.disabled())


def settle(f, result):
    sid = row(f,result['order_id'])['checkout_session_id']
    f['stripe'].paid(sid)
    event = f['stripe'].event(sid)
    assert f['current'].webhook(*event)['status']=='accepted'
    assert f['current'].webhook(*event)['status']=='accepted'
    return sid


def test_pause_preserves_paid_access_and_no_new_charge(purchase_fixture):
    from autodata_ingestion.commerce_service import CommerceError
    f=purchase_fixture;key=str(uuid.uuid4());first=checkout(f,key);settle(f,first)
    assert row(f,first['order_id'])['amount_minor']==2000
    assert row(f,first['order_id'])['currency']=='USD'
    pause(f);before=snapshot(f);calls=len(f['stripe'].create_attempts)
    for candidate in (key,str(uuid.uuid4())):
        with pytest.raises(CommerceError) as error:checkout(f,candidate)
        assert (error.value.code,error.value.http_status)==('COMMERCE_UNAVAILABLE',503)
    assert snapshot(f)==before and len(f['stripe'].create_attempts)==calls
    assert f['current'].grant_check(*f['owner'],f['configuration'],'US')['order_id']==first['order_id']
    assert f['current'].library(*f['owner'])['items'][0]['library_item_id']==first['order_id']
    assert f['current'].order_status(*f['owner'],first['order_id'])['state']=='paid'
    assert len(before['entitlements'])==1
    f['current']=f['service'](f['enabled'])
    assert checkout(f,key)['state']=='owned'
    assert snapshot(f)==before and len(f['stripe'].create_attempts)==calls
    write_artifact('paid-pause.json',dict(before=before,after=snapshot(f),provider_create_count=calls))


def test_late_settlement_refund_and_reconciliation_while_paused(purchase_fixture):
    from lifecycle_support import seed_configuration, seed_vehicle
    from autodata_ingestion.commerce_service import reconcile_workshop_preparation
    from autodata_ingestion.payment_reconciliation import reconcile_pending_payments
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog
    f=purchase_fixture;first=checkout(f)
    other=str(seed_configuration(f['repo'],seed_vehicle(f['repo'])))
    second=checkout(f,configuration=other)
    pause(f);calls=len(f['stripe'].create_attempts);sid=settle(f,first)
    sid2=settle(f,second)
    assert len(snapshot(f)['entitlements'])==2
    # Exercise genuine recorded pending-event reconciliation against paused authority.
    with f['repo'].connect() as conn:
        conn.execute("UPDATE payment_events SET fulfillment_status='pending',fulfilled_at=NULL WHERE verified=true")
    with f['repo'].connect() as conn:
        from psycopg.rows import tuple_row
        conn.row_factory=tuple_row
        assert all(r['status']=='accepted' for r in reconcile_pending_payments(conn,commerce=f['current']))
    def real(payload):return _ensure_lifecycle_catalog(json.loads(payload),repo=f['repo'])
    with f['repo'].connect() as conn:
        assert len(reconcile_workshop_preparation(conn,scheduler=real))==2
    assert f['current'].webhook(*f['stripe'].event(sid,kind='charge.refunded',refunded=True,amount_refunded=2000))['status']=='accepted'
    assert f['current'].webhook(*f['stripe'].event(sid2,kind='charge.dispute.closed',status='lost',amount=2000))['status']=='accepted'
    f['current'].webhook(*f['stripe'].event(sid))
    f['current'].webhook(*f['stripe'].event(sid2))
    assert row(f,first['order_id'])['status']==row(f,second['order_id'])['status']=='revoked'
    assert all(json.loads(r)['status']=='revoked' for r in snapshot(f)['entitlements'])
    assert len(f['stripe'].create_attempts)==calls
    write_artifact('late-recovery.json',dict(rows=snapshot(f),provider_create_count=calls))


def test_stale_public_config_rejected_through_go_authority_bridge(purchase_fixture):
    from lifecycle_support import ROOT, seed_configuration, seed_vehicle
    from autodata_ingestion.http_service import make_handler
    f=purchase_fixture;artifact=Path(os.environ['AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR'])
    go=shutil.which('go');assert go,'pinned Go binary missing'
    open_key=str(uuid.uuid4());opened=checkout(f,open_key)
    other=str(seed_configuration(f['repo'],seed_vehicle(f['repo'])))
    creating_key=str(uuid.uuid4());f['stripe'].lose_once=True;creating=checkout(f,creating_key,other)
    assert row(f,opened['order_id'])['status']=='open' and row(f,creating['order_id'])['status']=='creating'
    token='task59-fixture-'+uuid.uuid4().hex
    session=base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('=')
    with f['repo'].connect() as conn:
        conn.execute('INSERT INTO auth_sessions(session_token_hash,customer_account_id,firebase_auth_time,created_at,expires_at) VALUES(%s,%s,%s,%s,%s)',
            (hashlib.sha256(session.encode()).digest(),f['owner'][0],int(f['now'][0].timestamp()),f['now'][0],f['now'][0]+timedelta(hours=1)))
    cases=[dict(key=str(uuid.uuid4()),configuration_id=f['configuration']),dict(key=open_key,configuration_id=f['configuration']),dict(key=creating_key,configuration_id=other)]
    class CurrentAuthority:
        def __getattr__(self,name):return getattr(f['current'],name)
    base=make_handler(token,commerce=CurrentAuthority())
    class Handler(base):
        def do_POST(self):
            if self.path not in ('/task59/bootstrap','/task59/pause'):
                return super().do_POST()
            if self.headers.get('X-Autodata-Internal-Token')!=token:
                self._write_json(401,{});return
            length=int(self.headers.get('Content-Length','0'))
            if length>1024 or self.rfile.read(length)!=b'{}':
                self._write_json(400,{});return
            if self.path=='/task59/bootstrap':
                self._write_json(200,dict(database=f['repo'].database_name,session=session,cases=cases));return
            pause(f);f['before']=snapshot(f);f['create_before']=len(f['stripe'].create_attempts)
            write_artifact('authority-before.json',f['before'])
            self._write_json(200,{'paused':True})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    environment={k:os.environ[k] for k in ('PATH','GOCACHE','GOMODCACHE','GOPATH','GOTOOLCHAIN','GOROOT','GOTMPDIR') if k in os.environ}
    environment.setdefault('GOCACHE',str(artifact/'go-cache'))
    environment.update(GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=readonly',CGO_ENABLED='0')
    environment.update(AUTODATA_PURCHASE_CONFIG_GO_BRIDGE='1',AUTODATA_REQUIRE_PURCHASE_CONFIG_INTEGRATION='1',
        AUTODATA_PURCHASE_CONFIG_FIXTURE_URL=f'http://127.0.0.1:{server.server_port}',
        AUTODATA_PURCHASE_CONFIG_FIXTURE_TOKEN=token,AUTODATA_PURCHASE_CONFIG_ARTIFACT_DIR=str(artifact))
    process=None;timed_out=False
    try:
        with (artifact/'go-events.jsonl').open('w') as stdout,(artifact/'go-stderr.log').open('w') as stderr:
            process=subprocess.Popen([go,'test','-json','-count=1','-timeout=120s','-run','^TestWorkshopPurchaseConfigAuthorityIntegration$','.'],
                cwd=ROOT/'apps/api-go',env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
            try:process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        assert not timed_out and process.returncode==0,'Go authority bridge failed; raw output retained'
        events=[json.loads(line) for line in (artifact/'go-events.jsonl').read_text().splitlines()]
        named=[e for e in events if e.get('Test')=='TestWorkshopPurchaseConfigAuthorityIntegration']
        assert sum(e['Action']=='run' for e in named)==1 and sum(e['Action']=='pass' for e in named)==1
        assert not any(e['Action'] in ('skip','fail') for e in events)
        assert any(e['Action']=='pass' and 'Test' not in e for e in events),'package pass missing'
        assert 'before' in f,'Go did not exercise pause'
        assert snapshot(f)==f['before'] and len(f['stripe'].create_attempts)==f['create_before']
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        after=snapshot(f);write_artifact('authority-after.json',after)
        write_artifact('provider-trace.json',dict(create_attempts=f['stripe'].create_attempts,calls=f['stripe'].calls,
            create_before=f.get('create_before'),create_after=len(f['stripe'].create_attempts),timed_out=timed_out))
