"""Verify simulated checkout and merchant separation against disposable storage."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import uuid

import pytest

from autodata_ingestion import commerce_service as commerce
from autodata_ingestion.http_service import dispatch_commerce
from autodata_ingestion.payment_reconciliation import revoke_entitlement
from autodata_ingestion.stripe_adapter import StripePaymentProvider
from lifecycle_support import fresh_database, seed_configuration, seed_vehicle


ORIGIN = 'https://autodata.cars.tk'


def setup_env(monkeypatch):
    env = {
        'AUTODATA_COMMERCE_MODE': 'simulation',
        'AUTODATA_COMMERCE_READ_ONLY_MODE': 'stripe_test',
        'AUTODATA_ENV': 'production',
        'AUTODATA_PUBLIC_ORIGIN': ORIGIN,
        'AUTODATA_STRIPE_ACCOUNT_ID': 'acct_fixture',
        'AUTODATA_STRIPE_PRICE_ID': 'price_fixture',
        'AUTODATA_INGESTION_INTERNAL_TOKEN': 'fixture-internal',
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('AUTODATA_STRIPE_SECRET_KEY', raising=False)
    monkeypatch.delenv('AUTODATA_STRIPE_WEBHOOK_SECRET', raising=False)


def call(service, operation, payload):
    return dispatch_commerce(service, '/internal/commerce/' + operation, payload)


def reject(service, operation, payload, code):
    with pytest.raises(commerce.CommerceError) as error:
        call(service, operation, payload)
    assert error.value.code == code


def test_simulation_expected_mode_denies_stale_or_unmarked_intent(monkeypatch):
    setup_env(monkeypatch)
    purchase = commerce._simulation_configuration(ORIGIN)
    connect = Mock(side_effect=AssertionError('database access'))
    pins = commerce.CommerceConfig('stripe_test', 'acct_fixture', 'price_fixture')
    simulation = commerce.SimulationCommerceService(connect, pins, purchase)
    payload = {
        'customer_account_id': str(uuid.uuid4()), 'organization_id': str(uuid.uuid4()),
        'idempotency_key': str(uuid.uuid4()), 'configuration_id': str(uuid.uuid4()),
        'region': 'US', 'terms_version': commerce.TERMS,
    }
    reject(simulation, 'checkouts', payload, 'COMMERCE_UNAVAILABLE')
    reject(simulation, 'checkouts', dict(payload, expected_mode='stripe_test'), 'COMMERCE_UNAVAILABLE')
    reject(simulation, 'checkouts', dict(payload, expected_mode=[]), 'COMMERCE_UNAVAILABLE')
    reject(simulation, 'stripe/webhook', {}, 'COMMERCE_UNAVAILABLE')
    for service in (commerce.CommerceService(connect, pins, None),
                    commerce.ReadOnlyCommerceService(connect, pins),
                    commerce.CommerceService(connect, commerce.CommerceConfig(
                        'stripe_live', pins.account_id, pins.price_id), None)):
        reject(service, 'checkouts', dict(payload, expected_mode='simulation'), 'COMMERCE_UNAVAILABLE')
    connect.assert_not_called()


def account(repo):
    with repo.connect() as conn:
        row = conn.execute("""INSERT INTO customer_accounts(firebase_project_id,firebase_uid)
            VALUES('fixture',%s) RETURNING customer_account_id,personal_organization_id""",
            (uuid.uuid4().hex,)).fetchone()
    return {'customer_account_id': str(row['customer_account_id']),
            'organization_id': str(row['personal_organization_id'])}

def seed_existing_paid_order(repo, owner, scope):
    pins = commerce.CommerceConfig('stripe_live', 'acct_fixture', 'price_fixture')
    prior = commerce.CommerceService(repo.connect, pins, None)
    with prior.transaction() as (_, cursor):
        order, created = prior._reserve_checkout(
            cursor, owner['customer_account_id'], owner['organization_id'],
            scope['configuration_id'], scope['region'], str(uuid.uuid4()))
        assert created
        event_id, provider_ref = str(uuid.uuid4()), 'evt_prior_fixture'
        cursor.execute("""INSERT INTO payment_events(payment_event_id,provider_name,provider_event_id,
            event_type,verified,payload,occurred_at,fulfillment_status,fulfilled_at)
            VALUES(%s,'stripe',%s,'checkout.session.completed',true,'{}',now(),'fulfilled',now())""",
            (event_id, provider_ref))
        prior._settle_order(cursor, order, event_id, provider_ref,
                            checkout_session_id='cs_live_prior_fixture', payment_intent_id='pi_prior_fixture')
    return str(order['order_id'])


def test_simulated_order_is_atomic_owned_and_separate_from_stripe(fresh_database, monkeypatch):
    repo = fresh_database()
    scope = {'configuration_id': str(seed_configuration(repo, seed_vehicle(repo))), 'region': 'US'}
    tester, other = account(repo), account(repo)
    existing_order = seed_existing_paid_order(repo, other, scope)
    outsider = account(repo)
    setup_env(monkeypatch)
    monkeypatch.setenv('AUTODATA_COMMERCE_READ_ONLY_MODE', 'stripe_live')
    provider_factory = Mock(side_effect=AssertionError('Stripe provider constructed'))
    with monkeypatch.context() as no_stripe:
        no_stripe.setattr('autodata_ingestion.stripe_adapter.StripePaymentProvider', provider_factory)
        service = commerce.configured_commerce(connection_factory=repo.connect)
    provider_factory.assert_not_called()
    assert service.provider is None

    notices = call(service, 'purchase-config', tester)
    assert notices['checkout_mode'] == 'simulation' and notices['enabled']
    assert notices['terms_version'] == commerce.TERMS
    for name in ('terms', 'privacy', 'refund', 'contact'):
        assert notices[name + '_url'] == f'{ORIGIN}/workshop/test-notices/{name}'
    assert not call(service, 'purchase-config', {})['enabled']
    assert call(service, 'purchase-config', other)['enabled']
    assert not call(service, 'quote', scope)['purchasable']
    assert call(service, 'quote', {**scope, **other})['purchasable']
    assert call(service, 'quote', {**scope, **tester})['purchasable']
    wrong_owner = dict(tester, organization_id=other['organization_id'])
    reject(service, 'purchase-config', wrong_owner, 'CUSTOMER_ACCESS_REQUIRED')
    reject(service, 'quote', {**scope, **wrong_owner}, 'CUSTOMER_ACCESS_REQUIRED')

    request = dict(scope, terms_version=commerce.TERMS, expected_mode='simulation')
    key = str(uuid.uuid4())
    assert call(service, 'checkouts', dict(request, **other, idempotency_key=key))['order_id'] == existing_order
    reject(service, 'checkouts', dict(request, **wrong_owner, idempotency_key=key), 'CUSTOMER_ACCESS_REQUIRED')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(lambda attempt_key: call(service, 'checkouts',
            dict(request, **tester, idempotency_key=attempt_key)), [key, str(uuid.uuid4())])
    assert first == second and first.http_status == 200 and first['state'] == 'owned'
    order_id = first['order_id']
    assert first['library_item_id'] == order_id and 'checkout_url' not in first
    assert call(service, 'checkouts', dict(request, **tester, idempotency_key=key)) == first
    reject(service, 'checkouts', dict(request, **tester, idempotency_key=key, region='CA'), 'IDEMPOTENCY_CONFLICT')
    assert call(service, 'orders/status', dict(tester, order_id=order_id))['state'] == 'paid'
    reject(service, 'orders/status', dict(other, order_id=order_id), 'ORDER_NOT_FOUND')
    grant = call(service, 'grants/check', {**scope, **tester})
    assert grant['order_id'] == order_id and grant['configuration_id'] == scope['configuration_id']
    library_query = dict(cursor='', limit=20)
    assert call(service, 'library', {**tester, **library_query})['items'][0]['library_item_id'] == order_id
    assert call(service, 'library', {**other, **library_query})['items'][0]['library_item_id'] == existing_order
    assert call(service, 'grants/check', {**scope, **other})['order_id'] == existing_order
    assert call(service, 'library', {**outsider, **library_query})['items'] == []
    reject(service, 'grants/check', {**scope, **outsider}, 'ENTITLEMENT_REQUIRED')
    outsider_result = call(service, 'checkouts', dict(request, **outsider, idempotency_key=str(uuid.uuid4())))
    assert outsider_result['state'] == 'owned' and outsider_result['order_id'] not in {order_id, existing_order}
    assert call(service, 'library', {**outsider, **library_query})['items'][0]['library_item_id'] == outsider_result['order_id']

    with repo.connect() as conn:
        persisted = conn.execute("""SELECT o.stripe_account_id,o.expected_price_id,o.livemode,o.checkout_session_id,
            o.payment_intent_id,o.preparation_state,p.provider_name,p.verified,p.fulfillment_status,
            p.payload,e.status AS entitlement_status
            FROM workshop_orders o JOIN entitlements e ON e.entitlement_id=o.entitlement_id
            JOIN payment_events p USING(payment_event_id) WHERE o.order_id=%s""", (order_id,)).fetchone()
        assert persisted == {
            'stripe_account_id': commerce.SIMULATION_MERCHANT, 'expected_price_id': commerce.SIMULATION_PRICE,
            'livemode': False, 'checkout_session_id': None, 'payment_intent_id': None, 'preparation_state': 'pending',
            'provider_name': commerce.SIMULATION_PROVIDER, 'verified': False, 'fulfillment_status': 'fulfilled',
            'payload': {'order_id': order_id, 'amount_charged_minor': 0}, 'entitlement_status': 'active',
        }
        assert conn.execute('SELECT count(*) AS n FROM workshop_orders').fetchone()['n'] == 3
        assert conn.execute('SELECT count(*) AS n FROM dataset_projections').fetchone()['n'] == 3
        assert conn.execute('SELECT count(*) AS n FROM workshop_checkout_requests').fetchone()['n'] == 5

    monkeypatch.setenv('AUTODATA_COMMERCE_MODE', 'read_only')
    rollback = commerce.configured_commerce(connection_factory=repo.connect)
    reject(rollback, 'grants/check', {**scope, **tester}, 'ENTITLEMENT_REQUIRED')
    assert call(rollback, 'library', {**tester, **library_query})['items'] == []
    assert call(rollback, 'grants/check', {**scope, **other})['order_id'] == existing_order
    reject(rollback, 'checkouts', dict(request, **tester, idempotency_key=key), 'COMMERCE_UNAVAILABLE')

    with repo.connect() as conn:
        revoke_entitlement(conn, grant['entitlement_id'], 'administrative fixture cleanup')
        conn.execute("""UPDATE workshop_orders SET status='revoked',revoked_at=now(),
            revocation_reason_code='administrative' WHERE order_id=%s""", (order_id,))
    reject(service, 'grants/check', {**scope, **tester}, 'ENTITLEMENT_REVOKED')

    monkeypatch.setenv('AUTODATA_COMMERCE_MODE', 'stripe_live')
    monkeypatch.setenv('AUTODATA_STRIPE_SECRET_KEY', 'sk_live_fixture')
    monkeypatch.setenv('AUTODATA_STRIPE_WEBHOOK_SECRET', 'whsec_fixture')
    monkeypatch.setattr(StripePaymentProvider, 'verify_merchant', Mock())
    monkeypatch.setattr(StripePaymentProvider, 'verify_price', Mock())
    assert commerce.configured_commerce(connection_factory=repo.connect).config.livemode
    with repo.connect() as conn:
        conn.execute("UPDATE workshop_orders SET expected_price_id='foreign_price' WHERE order_id=%s", (order_id,))
    with pytest.raises(commerce.CommerceError, match='COMMERCE_CONFIGURATION_INVALID'):
        commerce.configured_commerce(connection_factory=repo.connect)
