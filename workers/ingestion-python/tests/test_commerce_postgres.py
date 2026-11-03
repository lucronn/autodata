"""Fourteen mandatory isolated PostgreSQL commerce acceptance cases.

The official Stripe SDK uses only the deterministic in-process HTTP transport.
There are no Firebase, Stripe, bank, model, payment-card or cloud credentials.
"""
from __future__ import annotations
import copy
import hashlib
import hmac
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from lifecycle_support import ROOT, fresh_database, seed_vehicle, seed_configuration, seed_snapshot
from autodata_ingestion.commerce_service import (CommerceService, CommerceConfig, CommerceError,
    TERMS, reconcile_workshop_preparation)
from autodata_ingestion.stripe_adapter import StripePaymentProvider


@pytest.fixture(autouse=True)
def mandatory_fixture():
    if os.getenv('AUTODATA_REQUIRE_COMMERCE_INTEGRATION') == '1':
        assert os.getenv('AUTODATA_LIFECYCLE_TEST') == '1', 'required isolated PG fixture missing'


class StripeFixture:
    def __init__(self):
        import stripe
        self.sessions, self.intents, self.keys, self.calls = {}, {}, {}, []
        self.lock = threading.Lock()
        self.create_attempts = []
        self.lose_once = False
        self.barrier = None
        outer = self
        class Transport(stripe.HTTPClient):
            name = 'commerce-fixture'
            def request(self, method, url, headers, post_data=None, **kwargs):
                if outer.barrier is not None and method.lower() == 'post' and urlsplit(url).path.endswith('/checkout/sessions'):
                    outer.barrier.wait(timeout=5)
                with outer.lock:
                    value = outer.request(method.lower(), url, headers, post_data)
                return json.dumps(value), 200, {}
        client = stripe.StripeClient('sk_test_fixture', http_client=Transport(), max_network_retries=0)
        self.provider = StripePaymentProvider(stripe_module=stripe, client=client, webhook_secret='whsec_fixture',
            success_url='https://fixture.invalid/workshop/', cancel_url='https://fixture.invalid/workshop/')

    def request(self, method, url, headers, data):
        p = urlsplit(url)
        assert p.scheme == 'https' and p.hostname == 'api.stripe.com', 'external transport forbidden'
        args = parse_qs(data.decode() if isinstance(data, bytes) else (data or ''))
        def one(key): return args[key][0]
        self.calls.append((method, p.path))
        if p.path == '/v1/account': return {'id':'acct_fixture'}
        if p.path == '/v1/checkout/sessions' and method == 'post':
            key = next(v for k,v in headers.items() if k.lower() == 'idempotency-key')
            if key not in self.keys:
                sid = 'cs_test_' + uuid.uuid4().hex
                pid = 'pi_' + uuid.uuid4().hex
                order = one('metadata[order_id]')
                intent = dict(id=pid,metadata={'order_id':order},livemode=False,amount=2000,amount_received=0,
                    currency='usd',capture_method='automatic',status='requires_payment_method')
                self.intents[pid] = intent
                self.sessions[sid] = dict(id=sid,url='https://checkout.stripe.com/c/pay/' + sid + '#fidkdFixtureFragment',metadata={'order_id':order},
                    mode='payment',livemode=False,amount_total=2000,currency='usd',payment_status='unpaid',status='open',
                    expires_at=int(one('expires_at')),line_items={'data':[{'price':{'id':one('line_items[0][price]')},'quantity':1}]},payment_intent=pid)
                self.keys[key] = sid
            sid = self.keys[key]
            self.create_attempts.append(dict(provider_idempotency_key_sha256=hashlib.sha256(key.encode()).hexdigest(),order_id=self.sessions[sid]['metadata']['order_id'],session_id=sid))
            result = copy.deepcopy(self.sessions[sid])
            if self.lose_once:
                self.lose_once = False
                raise RuntimeError('fixture response lost after remote commit')
            return result
        if p.path.startswith('/v1/checkout/sessions/'):
            sid = p.path.split('/')[4]
            value = self.sessions[sid]
            if p.path.endswith('/expire') and method == 'post':
                if value['status'] == 'open': value['status'] = 'expired'
            result = copy.deepcopy(value)
            if isinstance(result.get('payment_intent'), str):
                result['payment_intent'] = copy.deepcopy(self.intents[result['payment_intent']])
            return result
        if p.path.startswith('/v1/payment_intents/'):
            pid = p.path.split('/')[3]
            if p.path.endswith('/cancel'):
                if self.intents[pid]['status'] != 'succeeded': self.intents[pid]['status'] = 'canceled'
            return copy.deepcopy(self.intents[pid])
        raise AssertionError((method,p.path))

    def paid(self, sid):
        with self.lock:
            session = self.sessions[sid]
            session.update(status='complete',payment_status='paid')
            self.intents[session['payment_intent']].update(status='succeeded',amount_received=2000)

    def event(self, sid, *, kind='checkout.session.completed', event_id=None, **changes):
        session = self.sessions[sid]
        if kind.startswith('checkout.'):
            obj = copy.deepcopy(session)
        elif kind.startswith('payment_intent.'):
            obj = copy.deepcopy(self.intents[session['payment_intent']])
        else:
            obj = dict(id='ch_fixture',payment_intent=session['payment_intent'],amount=2000,currency='usd',metadata={})
        obj.update(changes)
        event = dict(id=event_id or 'evt_' + uuid.uuid4().hex,type=kind,livemode=False,created=int(time.time()),data={'object':obj})
        body = json.dumps(event,separators=(',',':')).encode()
        stamp = str(int(time.time()))
        sig = hmac.new(b'whsec_fixture',stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        return 't='+stamp+',v1='+sig,body


@pytest.fixture
def commerce(fresh_database, request):
    repo = fresh_database()
    config = str(seed_configuration(repo, seed_vehicle(repo)))
    stripe = StripeFixture()
    now = [datetime.now(UTC)]
    service = CommerceService(repo.connect, CommerceConfig('stripe_test','acct_fixture','price_fixture'), stripe.provider,clock=lambda:now[0])
    with repo.connect() as conn:
        account = conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture',%s) RETURNING customer_account_id,personal_organization_id",(uuid.uuid4().hex,)).fetchone()
    owner = (str(account['customer_account_id']),str(account['personal_organization_id']))
    value = repo,service,stripe,owner,config,now
    yield value
    if os.getenv('AUTODATA_REQUIRE_COMMERCE_INTEGRATION') == '1':
        export_case_rows(value, request.node.name)


def checkout(c, key=None, config=None):
    repo, service, stripe, owner, configuration, now = c
    return service.checkout(*owner,key or str(uuid.uuid4()),dict(configuration_id=config or configuration,region='US',terms_version=TERMS))


def order(c, oid):
    with c[0].connect() as conn:
        return conn.execute('SELECT * FROM workshop_orders WHERE order_id=%s',(oid,)).fetchone()


def settle(c, result, **changes):
    sid = order(c,result['order_id'])['checkout_session_id']
    c[2].paid(sid)
    signature,body = c[2].event(sid,**changes)
    return c[1].webhook(signature,body)


def counts(c):
    with c[0].connect() as conn:
        return {table:conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in ('workshop_orders','workshop_checkout_requests','entitlements','dataset_requests','dataset_projections')}


def test_orders_create_and_owner_scope(commerce):
    c=commerce
    from autodata_ingestion.http_service import make_handler
    from http.server import ThreadingHTTPServer
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler('fixture-internal',commerce=c[1]))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def post(path,payload,token='fixture-internal'):
        request=Request(f'http://127.0.0.1:{server.server_port}/internal/commerce/'+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Autodata-Internal-Token':token},method='POST')
        with urlopen(request,timeout=5) as response:return response.status,json.load(response)
    try:
        with pytest.raises(HTTPError) as error:post('quote',dict(configuration_id=c[4],region='US'),token='')
        assert error.value.code==401
        status,quote=post('quote',dict(configuration_id=c[4],region='US'))
        assert status==200 and quote['amount_minor']==2000 and quote['currency']=='USD'
        status,result=post('checkouts',dict(customer_account_id=c[3][0],organization_id=c[3][1],idempotency_key=str(uuid.uuid4()),configuration_id=c[4],region='US',terms_version=TERMS))
        assert status==201 and result['state']=='checkout' and result['checkout_url'].endswith('#fidkdFixtureFragment')
    finally:server.shutdown();server.server_close();thread.join()

    assert c[1].order_status(*c[3],result['order_id'])['state']=='open'
    with pytest.raises(CommerceError) as error:c[1].order_status(str(uuid.uuid4()),str(uuid.uuid4()),result['order_id'])
    assert error.value.http_status==403
    with c[0].connect() as conn:
        foreign=conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture','other') RETURNING customer_account_id,personal_organization_id").fetchone()
    with pytest.raises(CommerceError) as error:c[1].order_status(str(foreign['customer_account_id']),str(foreign['personal_organization_id']),result['order_id'])
    assert error.value.http_status==404
    assert len(c[2].sessions)==1


def test_same_key_replay_and_conflict(commerce):
    c=commerce;key=str(uuid.uuid4());a=checkout(c,key);b=checkout(c,key)
    assert a['order_id']==b['order_id'] and b.http_status==200 and len(c[2].sessions)==1
    other=str(seed_configuration(c[0],seed_vehicle(c[0])))
    with pytest.raises(CommerceError) as error:checkout(c,key,other)
    assert error.value.code=='IDEMPOTENCY_CONFLICT'
    assert counts(c)['workshop_checkout_requests']==1


def test_concurrent_keys_share_one_checkout(commerce):
    c=commerce;c[2].barrier=threading.Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:checkout(c),range(2)))
    assert results[0]['order_id']==results[1]['order_id']
    assert len(c[2].sessions)==1 and counts(c)['workshop_orders']==1 and counts(c)['workshop_checkout_requests']==2


def test_scope_races_single_active_grant(commerce):
    c=commerce;result=checkout(c);sid=order(c,result['order_id'])['checkout_session_id'];c[2].paid(sid)
    events=[c[2].event(sid) for _ in range(2)];barrier=threading.Barrier(2)
    def run(event):barrier.wait(5);return c[1].webhook(*event)
    with ThreadPoolExecutor(2) as pool: assert all(r['status']=='accepted' for r in pool.map(run,events))
    assert counts(c)['entitlements']==1 and counts(c)['dataset_projections']==1
    calls=len(c[2].calls);assert checkout(c)['state']=='owned';assert len(c[2].calls)==calls


def test_lost_create_response_and_retention_boundary(commerce):
    c=commerce;key=str(uuid.uuid4());c[2].lose_once=True
    first=checkout(c,key);assert first['state']=='processing'
    retry=checkout(c,key);assert retry['state']=='checkout' and retry['order_id']==first['order_id'] and len(c[2].sessions)==1
    c[2].lose_once=True;other=str(seed_configuration(c[0],seed_vehicle(c[0])))
    pending=checkout(c,config=other);c[5][0]+=timedelta(hours=23)
    calls=len(c[2].calls);again=checkout(c,config=other)
    assert again['order_id']==pending['order_id'] and again['state']=='processing' and len(c[2].calls)==calls
    assert order(c,pending['order_id'])['status']=='reconciliation_required'


def test_expiry_requires_remote_nonchargeable_proof(commerce):
    c=commerce;key=str(uuid.uuid4());first=checkout(c,key);c[5][0]+=timedelta(hours=2)
    assert checkout(c)['order_id']==first['order_id']
    # First request expires session; next request cancels its pending intent.
    assert checkout(c)['order_id']==first['order_id']
    assert order(c,first['order_id'])['status']=='expired'
    second=checkout(c);assert second['order_id']!=first['order_id']
    assert checkout(c,key)['order_id']==first['order_id'] and len(c[2].sessions)==2


def test_completion_races_expiry_without_recharge(commerce):
    c=commerce;first=checkout(c);sid=order(c,first['order_id'])['checkout_session_id'];c[2].paid(sid);c[5][0]+=timedelta(hours=2)
    assert checkout(c)['order_id']==first['order_id'] and len(c[2].sessions)==1
    signature,body=c[2].event(sid);assert c[1].webhook(signature,body)['status']=='accepted'
    assert checkout(c)['state']=='owned' and counts(c)['entitlements']==1


def test_webhook_before_create_response(commerce):
    c=commerce;c[2].lose_once=True;first=checkout(c);assert first['state']=='processing'
    sid=next(iter(c[2].sessions));c[2].paid(sid)
    assert c[1].webhook(*c[2].event(sid))['status']=='accepted'
    assert checkout(c)['state']=='owned' and counts(c)['entitlements']==1


def test_settlement_binds_financial_owner_scope(commerce):
    c=commerce;first=checkout(c);sid=order(c,first['order_id'])['checkout_session_id'];c[2].paid(sid)
    c[2].sessions[sid]['amount_total']=1
    assert c[1].webhook(*c[2].event(sid))['status']=='quarantined'
    assert counts(c)['entitlements']==0
    c[2].sessions[sid]['amount_total']=2000
    c[2].sessions[sid]['line_items']['data'][0]['price']['id']='price_foreign'
    assert c[1].webhook(*c[2].event(sid))['status']=='quarantined'
    assert counts(c)['entitlements']==0


def test_duplicate_and_distinct_events_grant_once(commerce):
    c=commerce;first=checkout(c);sid=order(c,first['order_id'])['checkout_session_id'];c[2].paid(sid)
    event=c[2].event(sid);assert c[1].webhook(*event)['status']=='accepted';assert c[1].webhook(*event)['status']=='accepted'
    assert c[1].webhook(*c[2].event(sid,kind='payment_intent.succeeded'))['status']=='accepted'
    assert counts(c)['entitlements']==counts(c)['dataset_requests']==counts(c)['dataset_projections']==1
    with c[0].connect() as conn:
        rows=conn.execute("SELECT payload FROM payment_events WHERE payload->>'kind'='workshop'").fetchall()
    assert len(rows)==2 and all('line_items' not in row['payload'] for row in rows)


def test_refund_chargeback_ordering_and_monotonic_revocation(commerce):
    c=commerce;first=checkout(c);sid=order(c,first['order_id'])['checkout_session_id'];c[2].paid(sid)
    assert c[1].webhook(*c[2].event(sid,kind='charge.refunded',refunded=True,amount_refunded=2000))['status']=='accepted'
    assert order(c,first['order_id'])['status']=='revoked'
    tombstone=c[1].library(*c[3])['items'][0]
    assert tombstone['access_state']=='revoked' and tombstone['granted_at'] is None
    assert c[1].webhook(*c[2].event(sid))['status']=='accepted' and counts(c)['entitlements']==0
    with pytest.raises(CommerceError) as error:checkout(c)
    assert error.value.code=='ENTITLEMENT_REVOKED'
    other=str(seed_configuration(c[0],seed_vehicle(c[0])));second=checkout(c,config=other);settle(c,second)
    sid=order(c,second['order_id'])['checkout_session_id']
    c[1].webhook(*c[2].event(sid,kind='charge.refunded',refunded=False,amount_refunded=100))
    assert order(c,second['order_id'])['status']=='paid'
    c[1].webhook(*c[2].event(sid,kind='charge.dispute.closed',status='won',amount=2000))
    c[1].webhook(*c[2].event(sid,kind='charge.dispute.closed',status='lost',amount=100))
    assert order(c,second['order_id'])['status']=='paid'
    c[1].webhook(*c[2].event(sid,kind='charge.dispute.closed',status='lost',amount=2000))
    assert order(c,second['order_id'])['status']=='revoked'
    c[1].webhook(*c[2].event(sid));assert order(c,second['order_id'])['status']=='revoked'
    with c[0].connect() as conn:assert conn.execute('SELECT status FROM entitlements').fetchone()['status']=='revoked'


def test_payment_survives_source_unavailable_and_restart(commerce):
    c=commerce;first=checkout(c);settle(c,first)
    with c[0].connect() as conn:
        request=conn.execute('SELECT source_snapshot_id,status FROM dataset_requests').fetchone()
        assert request['source_snapshot_id'] is None and request['status']=='purchased'
        assert not conn.execute("SELECT 1 FROM publication_events WHERE event_type='dataset.fast.requested'").fetchone()
    # Controlled repository outage in actual catalog scheduling, then real recovery.
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog
    class Unavailable:
        def connect(self):raise RuntimeError('controlled fixture database unavailable')
    def unavailable(serialized):return _ensure_lifecycle_catalog(json.loads(serialized),repo=Unavailable())
    with c[0].connect() as conn:assert reconcile_workshop_preparation(conn,scheduler=unavailable)[0]['preparation_state']=='retry'
    def real(serialized):return _ensure_lifecycle_catalog(json.loads(serialized),repo=c[0])
    with c[0].connect() as conn:
        conn.execute('UPDATE workshop_orders SET preparation_next_attempt_at=now()')
    def crash_after_ensure(serialized):
        real(serialized)
        raise RuntimeError('controlled crash after durable scheduling, before acknowledgement')
    with c[0].connect() as conn:assert reconcile_workshop_preparation(conn,scheduler=crash_after_ensure)[0]['preparation_state']=='retry'
    with c[0].connect() as conn:
        durable=conn.execute("SELECT source_fetch_job_id FROM source_fetch_jobs WHERE job_kind='catalog_index' ORDER BY source_fetch_job_id").fetchall()
        assert len(durable)==2
        conn.execute('UPDATE workshop_orders SET preparation_next_attempt_at=now()')
    with c[0].connect() as conn:assert reconcile_workshop_preparation(conn,scheduler=real)[0]['preparation_state']=='index_queued'
    before=order(c,first['order_id'])['preparation_index_job_ids'];assert len(set(before))==2
    with c[0].connect() as conn:
        conn.execute('UPDATE workshop_orders SET preparation_next_attempt_at=now(),preparation_lease_expires_at=now()-interval \'1 second\'')
    with c[0].connect() as conn:reconcile_workshop_preparation(conn,scheduler=real)
    assert order(c,first['order_id'])['preparation_index_job_ids']==before
    with c[0].connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='completed',phase='completed' WHERE source_fetch_job_id=ANY(%s)",(before,))
        conn.execute('UPDATE workshop_orders SET preparation_next_attempt_at=now()')
    with c[0].connect() as conn:reconcile_workshop_preparation(conn,scheduler=real)
    assert order(c,first['order_id'])['preparation_state']=='index_ready'
    assert c[1].library(*c[3])['items'][0]['access_state']=='paid'
    assert counts(c)['entitlements']==1
    with c[0].connect() as conn:
        account=conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture','second-owner') RETURNING customer_account_id,personal_organization_id").fetchone()
    owner=(str(account['customer_account_id']),str(account['personal_organization_id']))
    second_context=(c[0],c[1],c[2],owner,c[4],c[5])
    second=checkout(second_context);settle(second_context,second)
    with c[0].connect() as conn:reconcile_workshop_preparation(conn,scheduler=real)
    assert order(c,second['order_id'])['preparation_index_job_ids']==before
    assert c[1].library(*owner)['items'][0]['access_state']=='paid'
    with c[0].connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs WHERE job_kind='catalog_index'").fetchone()['n']==2
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs WHERE job_kind='article'").fetchone()['n']==0


def test_library_is_owner_only_and_paginated(commerce):
    c=commerce;first=checkout(c);settle(c,first)
    second=checkout(c,config=str(seed_configuration(c[0],seed_vehicle(c[0]))));settle(c,second)
    page=c[1].library(*c[3],limit=1);assert len(page['items'])==1 and page['next_cursor']
    last=c[1].library(*c[3],cursor_value=page['next_cursor'],limit=1)
    assert len(last['items'])==1 and not last['next_cursor'] and page['items'][0]['library_item_id']!=last['items'][0]['library_item_id']
    with pytest.raises(CommerceError):c[1].library(str(uuid.uuid4()),str(uuid.uuid4()),cursor_value=page['next_cursor'])
    text=json.dumps(page);assert 'cs_' not in text and 'pi_' not in text and 'acct_' not in text
    descriptor,body=seed_readable_source(c)
    assert next(i for i in c[1].library(*c[3])['items'] if i['configuration_id']==c[4])['access_state']=='viewable'
    with c[0].connect() as conn:conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s",(descriptor,))
    assert next(i for i in c[1].library(*c[3])['items'] if i['configuration_id']==c[4])['access_state']!='viewable'
    with c[0].connect() as conn:
        conn.execute("UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=%s",(descriptor,))
        conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s",(body,))
    assert next(i for i in c[1].library(*c[3])['items'] if i['configuration_id']==c[4])['access_state']!='viewable'



def test_grant_check_exact_scope_legacy_and_revoked(commerce):
    c=commerce;first=checkout(c);settle(c,first)
    assert c[1].grant_check(*c[3],c[4],'US')['order_id']==first['order_id']
    legacy_configuration=str(uuid.uuid4())
    with c[0].connect() as conn:
        product=order(c,first['order_id'])['dataset_product_id']
        request=conn.execute("""INSERT INTO dataset_requests(dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id)
            VALUES(%s,%s,'US','purchased','fast',%s,%s,'legacy-fixture',%s) RETURNING dataset_request_id""",
            (product,legacy_configuration,uuid.uuid4(),uuid.uuid4().hex,c[3][1])).fetchone()['dataset_request_id']
        conn.execute("INSERT INTO entitlements(organization_id,dataset_request_id,provider_event_id,status,granted_at) VALUES(%s,%s,'legacy-unscoped','active',now())",(c[3][1],request))
    for config,region in ((legacy_configuration,'US'),(c[4],'CA')):
        with pytest.raises(CommerceError) as error:c[1].grant_check(*c[3],config,region)
        assert error.value.code=='ENTITLEMENT_REQUIRED'
    sid=order(c,first['order_id'])['checkout_session_id'];c[1].webhook(*c[2].event(sid,kind='charge.refunded',refunded=True,amount_refunded=2000))
    with pytest.raises(CommerceError) as error:c[1].grant_check(*c[3],c[4],'US')
    assert error.value.code=='ENTITLEMENT_REVOKED'


SAFE_COLUMNS = {
    'workshop_orders': ('order_id','customer_account_id','organization_id','configuration_id','region','dataset_product_id','terms_version','amount_minor','currency','stripe_account_id','livemode','expected_price_id','status','checkout_session_id','payment_intent_id','first_create_attempt_at','provider_expires_at','dataset_request_id','entitlement_id','created_at','paid_at','revoked_at','revocation_reason_code','preparation_state','preparation_attempts','preparation_index_job_ids','preparation_last_error_code'),
    'workshop_checkout_requests': ('customer_account_id','client_idempotency_key','canonical_request_sha256','order_id','created_at'),
    'entitlements': ('entitlement_id','organization_id','dataset_request_id','payment_event_id','provider_event_id','status','granted_at','revoked_at','revoke_reason','customer_account_id','configuration_id','region','commerce_order_id'),
    'dataset_requests': ('dataset_request_id','dataset_product_id','vehicle_key','region','status','lane','source_snapshot_id','correlation_id','idempotency_key','processing_version','organization_id'),
    'dataset_projections': ('dataset_projection_id','dataset_product_id','dataset_request_id','entitlement_id'),
    'source_fetch_jobs': ('source_fetch_job_id','job_kind','catalog_provider_scope_id','canonical_article_id','status','phase','request_generation'),
    'catalog_article_provider_scopes': ('catalog_provider_scope_id','vehicle_id','vehicle_configuration_id','provider_slug','scope_key','status'),
    'payment_events': ('payment_event_id','provider_name','provider_event_id','event_type','verified','fulfillment_status','fulfillment_attempts','last_fulfillment_error','fulfilled_at'),
}


def export_case_rows(c, name):
    import stripe
    from autodata_ingestion.payment_reconciliation import canonical_payment_payload
    artifact=Path('/artifacts/workshop-commerce-migration-rows.json')
    candidate=os.environ['AUTODATA_R3_CANDIDATE_SHA']
    output=json.loads(artifact.read_text()) if artifact.exists() else dict(schema_version=1,candidate_sha=candidate,cases={})
    assert output['candidate_sha']==candidate
    with c[0].connect() as conn:
        measured=dict(fixture_database=c[0].database_name,
            server_version_num=int(conn.execute('SHOW server_version_num').fetchone()['server_version_num']),
            schema_migrations=conn.execute('SELECT version,applied_at FROM schema_migrations ORDER BY version').fetchall(),
            stripe_sdk_version=stripe.VERSION,stripe_transport_calls=list(c[2].calls),stripe_create_attempts=list(c[2].create_attempts),
            stripe_remote_sessions=[dict(session_id=s['id'],order_id=s['metadata']['order_id'],status=s['status'],payment_status=s['payment_status'],amount_total=s['amount_total'],currency=s['currency'],price_id=s['line_items']['data'][0]['price']['id'],quantity=s['line_items']['data'][0]['quantity'],payment_intent_id=s['payment_intent']) for s in c[2].sessions.values()])
        for table,columns in SAFE_COLUMNS.items():
            rows=conn.execute('SELECT '+','.join(columns)+' FROM '+table+' ORDER BY 1').fetchall()
            if table=='workshop_checkout_requests':
                for row in rows:row['canonical_request_sha256']=bytes(row['canonical_request_sha256']).hex()
            if table=='payment_events':
                for row in rows:
                    payload=conn.execute('SELECT payload FROM payment_events WHERE payment_event_id=%s',(row['payment_event_id'],)).fetchone()['payload']
                    row['payload_sha256']=hashlib.sha256(canonical_payment_payload(payload).encode()).hexdigest()
            measured[table]=rows
    output['cases'][name]=measured
    artifact.write_text(json.dumps(output,default=str,sort_keys=True,indent=2)+'\n');artifact.chmod(0o644)


def seed_readable_source(c):
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    from autodata_ingestion.article_lifecycle_store import upsert_article_descriptor
    descriptor=seed_snapshot(c[0],b'commerce-descriptor-rights')
    body=seed_snapshot(c[0],b'commerce-readable-body')
    with c[0].connect() as conn:
        vehicle=conn.execute('SELECT vehicle_id FROM vehicle_configurations WHERE vehicle_configuration_id=%s',(c[4],)).fetchone()['vehicle_id']
    aid=upsert_article_descriptor(c[0],ArticleKey('bankone',vehicle,uuid.UUID(c[4]),'fixture-vehicle','fixture-article'),{'title':'Fixture'},descriptor,0)
    rid=uuid.uuid4()
    with c[0].connect() as conn:
        conn.execute("""INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at)
            VALUES(%s,%s,%s,%s,'[]',%s,'[]','Fixture readable source','[]','readable','["fixture-evidence"]',now())""",
            (rid,aid,hashlib.sha256(b'commerce-source').hexdigest(),body,Jsonb({'blocks':[{'type':'paragraph','text':'Fixture readable source','evidence_ids':['fixture-evidence']}]})))
        conn.execute('UPDATE canonical_articles SET current_source_revision_id=%s WHERE canonical_article_id=%s',(rid,aid))
    return descriptor,body
