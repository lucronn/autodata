"""Verify simulated checkout and merchant separation against disposable storage."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import uuid

import pytest
from psycopg import OperationalError, sql

from autodata_ingestion import catalog_index_worker
from autodata_ingestion import commerce_service as commerce
from autodata_ingestion.article_lifecycle_types import ArticleKey, scope_key
from autodata_ingestion.http_service import dispatch_commerce
from autodata_ingestion.payment_reconciliation import revoke_entitlement
from autodata_ingestion.stripe_adapter import StripePaymentProvider
from lifecycle_support import fresh_database, insert_descriptor, seed_configuration, seed_snapshot, seed_vehicle


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


def test_catalog_worker_prepares_simulated_purchase_without_stripe(fresh_database, monkeypatch):
    repo = fresh_database()
    setup_env(monkeypatch)
    monkeypatch.setenv('AUTODATA_DB_ADDRESS', 'postgres:5432')
    monkeypatch.setenv('AUTODATA_POSTGRES_DB', repo.database_name)
    monkeypatch.setenv('AUTODATA_POSTGRES_USER', 'lifecycle_test')
    monkeypatch.setenv('AUTODATA_POSTGRES_PASSWORD', 'lifecycle_test_only')
    owner = account(repo)
    configuration = seed_configuration(repo, seed_vehicle(repo), engine_displacement_l=2.0)
    scope = {'configuration_id': str(configuration), 'region': 'US'}
    simulation = commerce.configured_commerce(connection_factory=repo.connect)
    receipt = call(simulation, 'checkouts', dict(scope, **owner, expected_mode='simulation',
        terms_version=commerce.TERMS, idempotency_key=str(uuid.uuid4())))
    assert receipt['state'] == 'owned'
    called = []

    def dispatch(actual_repo, **kwargs):
        assert actual_repo is repo and kwargs['model_client'] is None
        with repo.connect() as conn:
            order = conn.execute('''SELECT status,preparation_state,preparation_index_job_ids
                FROM workshop_orders WHERE order_id=%s''', (receipt['order_id'],)).fetchone()
            assert order['status'] == 'paid' and order['preparation_state'] == 'index_queued'
            jobs = conn.execute('''SELECT j.job_kind,j.provider_slug,s.vehicle_configuration_id
                FROM source_fetch_jobs j JOIN catalog_article_provider_scopes s USING(catalog_provider_scope_id)
                WHERE j.source_fetch_job_id=ANY(%s)''',
                (order['preparation_index_job_ids'],)).fetchall()
            assert {(job['job_kind'], job['provider_slug'], str(job['vehicle_configuration_id']))
                    for job in jobs} == {('catalog_index', provider, scope['configuration_id'])
                                         for provider in ('bankone', 'banktwo')}
            assert kwargs['job_id'] in order['preparation_index_job_ids']
        called.append(kwargs['job_id'])
        return True

    monkeypatch.setattr(catalog_index_worker, 'run_article_worker_once', dispatch)
    assert catalog_index_worker.run_catalog_worker(repo, registry={}, object_store=None, once=True) == 0
    assert not called
    assert catalog_index_worker.run_catalog_worker(repo, registry={}, object_store=None, once=True,
                                                   prepare_orders=True) == 0
    assert len(called) == 1
    assert call(simulation, 'grants/check', {**scope, **owner})['order_id'] == receipt['order_id']


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
    configuration = seed_configuration(repo, seed_vehicle(repo), engine_displacement_l=2.0)
    scope = {'configuration_id': str(configuration), 'region': 'US'}
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
    with repo.connect() as listener:
        listener.autocommit = True
        listener.execute(sql.SQL('LISTEN {}').format(sql.Identifier(commerce.WORKSHOP_PREPARATION_CHANNEL)))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(lambda attempt_key: call(service, 'checkouts',
                dict(request, **tester, idempotency_key=attempt_key)), [key, str(uuid.uuid4())])
        signals = list(listener.notifies(timeout=.2))
        assert [signal.payload for signal in signals] == ['']
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


def test_failed_notification_leaves_simulated_purchase_owned(fresh_database, monkeypatch):
    repo = fresh_database()
    setup_env(monkeypatch)
    owner = account(repo)
    configuration = seed_configuration(repo, seed_vehicle(repo), engine_displacement_l=2.0)
    scope = {'configuration_id': str(configuration), 'region': 'US'}
    service = commerce.configured_commerce(connection_factory=repo.connect)

    with monkeypatch.context() as offline:
        offline.setattr(service, 'connect', Mock(side_effect=[
            repo.connect(), OperationalError('notification connection unavailable'),
        ]))
        receipt = call(service, 'checkouts', {
            **scope, **owner, 'expected_mode': 'simulation',
            'terms_version': commerce.TERMS, 'idempotency_key': str(uuid.uuid4()),
        })

    assert receipt['state'] == 'owned'
    assert call(service, 'grants/check', {**scope, **owner})['order_id'] == receipt['order_id']


def test_empty_configuration_requires_its_own_evidence_for_new_offer(fresh_database, monkeypatch):
    repo = fresh_database()
    setup_env(monkeypatch)
    service = commerce.configured_commerce(connection_factory=repo.connect)
    buyer, other = account(repo), account(repo)
    vehicle, other_vehicle = seed_vehicle(repo), seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle)
    sibling = seed_configuration(repo, vehicle, engine_displacement_l=2.0)
    scope = {'configuration_id': str(configuration), 'region': 'US'}
    request = dict(scope, expected_mode='simulation', terms_version=commerce.TERMS)

    def checkout(owner, key=None):
        return call(service, 'checkouts', dict(request, **owner, idempotency_key=key or str(uuid.uuid4())))

    def quote():
        return call(service, 'quote', dict(scope, **buyer))

    def assert_unresolved():
        offer = quote()
        assert offer['amount_minor'] == 2000
        assert offer['purchasable'] is False and offer['configuration_unresolved'] is True
        assert 'engine_variant_market_unverified' not in offer

    insert_descriptor(repo, ArticleKey('banktwo', vehicle, None, 'model-ref', 'model-article'))
    insert_descriptor(repo, ArticleKey('bankone', vehicle, sibling, 'sibling-ref', 'sibling-article'))
    with repo.connect() as conn:
        base = conn.execute("""UPDATE vehicle_configurations SET trim=%s WHERE vehicle_configuration_id=%s
            RETURNING vehicle_identity_base_id""", ('\t ', configuration)).fetchone()['vehicle_identity_base_id']
        conn.execute("UPDATE vehicle_identity_bases SET body_style='SUV',drivetrain=%s WHERE vehicle_identity_base_id=%s",
                     (' \n', base))
        for mapping_key, config, owner, provider, ref, status in (
            ('model', None, vehicle, 'bankone', 'model-ref', 'verified'),
            ('sibling', sibling, vehicle, 'banktwo', 'sibling-ref', 'verified'),
            ('other_vehicle', configuration, other_vehicle, 'banktwo', 'foreign-ref', 'verified'),
            ('alias', configuration, vehicle, 'autoapi', 'unpromoted-ref', 'verified'),
            ('pending', configuration, vehicle, 'banktwo', 'pending-ref', 'pending'),
            ('blank', configuration, vehicle, 'banktwo', '\t ', 'verified'),
            ('mapped', configuration, vehicle, 'bankone', 'ref-1', 'verified'),
            ('mapped_duplicate', configuration, vehicle, 'bankone', 'ref-1', 'verified'),
            ('ambiguous', configuration, vehicle, 'bankone', 'ref-2', 'verified'),
        ):
            conn.execute("""INSERT INTO vehicle_provider_mappings(mapping_key,vehicle_id,vehicle_configuration_id,
                provider,entity_type,provider_id,source_snapshot_id,extraction_evidence_id,source_locator,
                evidence_locator,evidence_confidence,mapping_status)
                SELECT %s,%s,%s,%s,'car',%s,source_snapshot_id,extraction_evidence_id,'fixture','fixture',1,%s
                FROM vehicle_configurations WHERE vehicle_configuration_id=%s""",
                (mapping_key, owner, config, provider, ref, status, configuration))
        conn.execute("""INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,
            scope_key,provider_slug,source_vehicle_ref) VALUES (%s,%s,%s,'bankone','model-ref')""",
            (uuid.uuid4(), vehicle, scope_key(vehicle)))

    assert_unresolved()
    with pytest.raises(commerce.CommerceError) as refused:
        checkout(buyer)
    assert (refused.value.code, refused.value.http_status) == ('CONFIGURATION_UNRESOLVED', 409)
    with repo.connect() as conn:
        for table in ('workshop_orders', 'workshop_checkout_requests', 'payment_events', 'entitlements'):
            assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] == 0
        conn.execute("UPDATE vehicle_provider_mappings SET mapping_status='rejected' WHERE mapping_key='ambiguous'")

    assert quote()['purchasable'] is True
    with repo.connect() as conn:
        conn.execute("UPDATE vehicle_provider_mappings SET mapping_status='pending' WHERE mapping_key LIKE 'mapped%'")
        exact_scope = scope_key(vehicle, configuration)
        conn.execute("""INSERT INTO catalog_article_provider_scopes(catalog_provider_scope_id,vehicle_id,
            vehicle_configuration_id,scope_key,provider_slug,source_vehicle_ref)
            VALUES (%s,%s,%s,%s,'banktwo','exact-ref')""", (uuid.uuid4(), vehicle, configuration, exact_scope))

    assert quote()['purchasable'] is True
    with repo.connect() as conn:
        conn.execute('UPDATE catalog_article_provider_scopes SET source_vehicle_ref=NULL WHERE scope_key=%s', (exact_scope,))
    assert_unresolved()
    article = insert_descriptor(repo, ArticleKey('banktwo', vehicle, configuration, 'exact-ref', 'exact-article'))
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET takedown_status='takedown' WHERE canonical_article_id=%s", (article,))
    assert_unresolved()
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET takedown_status='active' WHERE canonical_article_id=%s", (article,))

    offer = quote()
    assert offer['purchasable'] is True and 'configuration_unresolved' not in offer
    order_key = str(uuid.uuid4())
    receipt = checkout(buyer, order_key)
    assert receipt['state'] == 'owned'
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=%s", (article,))

    assert_unresolved()
    assert checkout(buyer, order_key) == receipt
    assert checkout(buyer) == receipt
    assert call(service, 'grants/check', dict(scope, **buyer))['order_id'] == receipt['order_id']
    assert call(service, 'library', dict(buyer, cursor='', limit=20))['items'][0]['library_item_id'] == receipt['order_id']
    with pytest.raises(commerce.CommerceError, match='CONFIGURATION_UNRESOLVED'):
        checkout(other)


def test_empty_configuration_uses_visible_exact_legacy_articles(fresh_database, monkeypatch):
    repo = fresh_database()
    setup_env(monkeypatch)
    service = commerce.configured_commerce(connection_factory=repo.connect)
    buyer = account(repo)
    vehicle = seed_vehicle(repo)
    configuration, sibling = seed_configuration(repo, vehicle), seed_configuration(repo, vehicle)
    scope = dict(buyer, configuration_id=str(configuration), region='US')
    request = dict(scope, expected_mode='simulation', terms_version=commerce.TERMS,
                   idempotency_key=str(uuid.uuid4()))
    public_source = seed_snapshot(repo, b'legacy visible source')
    quarantine = seed_snapshot(repo, b'legacy quarantined source')
    withdrawn = seed_snapshot(repo, b'legacy withdrawn source')
    retired = insert_descriptor(repo, ArticleKey('bankone', vehicle, configuration, 'legacy-ref', 'aliased'))
    with repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=%s", (retired,))
        conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s", (withdrawn,))
        conn.execute("""INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids)
            VALUES (gen_random_uuid(),'legacy-commerce-source','quarantine','FIXTURE',jsonb_build_array(%s::text))""", (quarantine,))
        for config, article, snapshot in (
            (None, 'model-wide', public_source),
            (sibling, 'sibling', public_source),
            (configuration, 'L:link-only', public_source),
            (configuration, 'quarantined', quarantine),
            (configuration, 'withdrawn', withdrawn),
            (configuration, 'aliased', public_source),
        ):
            conn.execute("""INSERT INTO catalog_articles(vehicle_id,vehicle_configuration_id,article_id,source_snapshot_id,
                evidence_locator,evidence_confidence) VALUES (%s,%s,%s,%s,'fixture',1)""", (vehicle, config, article, snapshot))
        conn.execute("""INSERT INTO canonical_article_aliases(catalog_article_id,canonical_article_id,proof)
            SELECT catalog_article_id,%s,'{"fixture": true}' FROM catalog_articles
            WHERE vehicle_configuration_id=%s AND article_id='aliased'""", (retired, configuration))

    offer = call(service, 'quote', scope)
    assert offer['purchasable'] is False and offer['configuration_unresolved'] is True
    with pytest.raises(commerce.CommerceError, match='CONFIGURATION_UNRESOLVED'):
        call(service, 'checkouts', request)

    with repo.connect() as conn:
        conn.execute("UPDATE source_review_items SET status='approved' WHERE item_key='legacy-commerce-source'")

    offer = call(service, 'quote', scope)
    assert offer['purchasable'] is True and 'configuration_unresolved' not in offer
    receipt = call(service, 'checkouts', request)
    assert receipt['state'] == 'owned'
    assert call(service, 'grants/check', scope)['order_id'] == receipt['order_id']
