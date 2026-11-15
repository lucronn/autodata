"""Private purchase-disabled authority: no payment transport is constructed."""
import json
import os
from pathlib import Path
import sys
import threading
import socket
import subprocess
import time
import unittest
from unittest.mock import MagicMock, Mock, patch
import uuid
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from autodata_ingestion import commerce_service as commerce
from autodata_ingestion.http_service import dispatch_commerce, make_handler

ENV = {
    'AUTODATA_COMMERCE_MODE': 'read_only',
    'AUTODATA_COMMERCE_READ_ONLY_MODE': 'stripe_test',
    'AUTODATA_ENV': 'production',
    'AUTODATA_PUBLIC_ORIGIN': 'https://autodata.cars.tk',
    'AUTODATA_STRIPE_ACCOUNT_ID': 'acct_fixture',
    'AUTODATA_STRIPE_PRICE_ID': 'price_fixture',
    'AUTODATA_INGESTION_INTERNAL_TOKEN': 'fixture-internal',
}
BLOCKED = ('checkouts', 'orders/status', 'stripe/webhook', 'demo-mode', 'unknown')


class ReadOnlyCommerceTests(unittest.TestCase):
    def service(self):
        return commerce.ReadOnlyCommerceService(
            Mock(side_effect=AssertionError('database forbidden')),
            commerce.CommerceConfig('stripe_test', 'acct_fixture', 'price_fixture'))

    def test_public_startup_requires_explicit_pins_and_never_constructs_stripe(self):
        for mode, purchase_json in (('stripe_test', 'invalid'), ('stripe_live', '{"enabled":true}')):
            connection = MagicMock()
            cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [{'present': 1}, {'dataset_product_id': uuid.uuid4()}]
            env = {**ENV, 'AUTODATA_COMMERCE_READ_ONLY_MODE': mode,
                   'AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON': purchase_json}
            with self.subTest(mode=mode), patch.dict(os.environ, env, clear=True), patch('stripe.StripeClient') as stripe:
                service = commerce.configured_commerce(connection_factory=lambda: connection)
            self.assertTrue(service.read_only)
            self.assertEqual(service.config.livemode, mode == 'stripe_live')
            self.assertIsNone(service.provider)
            self.assertFalse(service.purchase_configuration()['enabled'])
            stripe.assert_not_called()
            queries = [call.args[0] for call in cursor.execute.call_args_list]
            self.assertEqual(queries[0], 'SET TRANSACTION READ ONLY')
            self.assertFalse(any(query.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for query in queries))

    def test_missing_schema_or_product_fails_closed_without_stripe(self):
        for rows in ((None,), ({'present': 1}, None)):
            connection = MagicMock()
            cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = rows
            with self.subTest(rows=rows), patch.dict(os.environ, ENV, clear=True), patch('stripe.StripeClient') as stripe:
                with self.assertRaises(commerce.CommerceError) as error:
                    commerce.configured_commerce(connection_factory=lambda: connection)
            self.assertEqual(error.exception.http_status, 503)
            stripe.assert_not_called()

    def test_invalid_read_only_configuration_fails_before_database_or_stripe(self):
        for key, values in {
            'AUTODATA_COMMERCE_READ_ONLY_MODE': ('', 'read_only', 'false'),
            'AUTODATA_STRIPE_ACCOUNT_ID': ('', 'other', 'acct_bad\n'),
            'AUTODATA_STRIPE_PRICE_ID': ('', 'other', 'price_bad\n'),
            'AUTODATA_INGESTION_INTERNAL_TOKEN': ('',),
            'AUTODATA_PUBLIC_ORIGIN': ('https://foreign.example',),
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), patch.dict(os.environ, {**ENV, key: value}, clear=True), patch('stripe.StripeClient') as stripe:
                    connect = Mock(side_effect=AssertionError('database forbidden'))
                    with self.assertRaises(commerce.CommerceError) as error:
                        commerce.configured_commerce(connection_factory=connect)
                    self.assertEqual(error.exception.http_status, 503)
                    connect.assert_not_called()
                    stripe.assert_not_called()

    def test_public_stripe_test_refusal_is_unchanged(self):
        with patch.dict(os.environ, {**ENV, 'AUTODATA_COMMERCE_MODE': 'stripe_test'}, clear=True):
            with self.assertRaises(commerce.CommerceError) as error:
                commerce.configured_commerce(connection_factory=Mock(side_effect=AssertionError('database forbidden')))
        self.assertEqual(error.exception.http_status, 503)

    def test_all_direct_payment_methods_refuse_before_arguments_or_io(self):
        service = self.service()
        for method in ('checkout', 'order_status', 'webhook', 'reconcile_event', '_reconcile_expiry', 'demo_mode_status'):
            with self.subTest(method=method), self.assertRaises(commerce.CommerceError) as error:
                getattr(service, method)()
            self.assertEqual(error.exception.http_status, 503)
        service.connect.assert_not_called()

    def test_dispatch_blocks_payment_before_handler_and_keeps_exact_allowed_dto(self):
        service = self.service()
        for suffix in BLOCKED:
            with self.subTest(suffix=suffix), self.assertRaises(commerce.CommerceError) as error:
                dispatch_commerce(service, '/internal/commerce/' + suffix, None)
            self.assertEqual(error.exception.http_status, 503)
        service.quote = Mock(return_value={'amount_minor': 2000})
        self.assertEqual(dispatch_commerce(service, '/internal/commerce/quote', {'configuration_id': 'id', 'region': 'US'}), {'amount_minor': 2000})
        with self.assertRaises(commerce.CommerceError) as error:
            dispatch_commerce(service, '/internal/commerce/quote', {'configuration_id': 'id', 'region': 'US', 'price': 1})
        self.assertEqual(error.exception.http_status, 400)
        self.assertEqual(service.quote.call_count, 1)

    def test_authenticated_http_blocks_payment_before_body_parse_and_forces_disabled_config(self):
        service = self.service()
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler('fixture-internal', commerce=service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for suffix in BLOCKED:
                for token, expected in (('', 401), ('fixture-internal', 503)):
                    with self.subTest(suffix=suffix, token=token):
                        request = Request(f'http://127.0.0.1:{server.server_port}/internal/commerce/{suffix}', data=b'invalid json', headers={'X-Autodata-Internal-Token': token})
                        with self.assertRaises(HTTPError) as error:
                            urlopen(request, timeout=3)
                        with error.exception as response:
                            self.assertEqual(response.status, expected)
                            json.load(response)
            request = Request(f'http://127.0.0.1:{server.server_port}/internal/commerce/purchase-config', data=b'{}', headers={'X-Autodata-Internal-Token': 'fixture-internal'})
            with urlopen(request, timeout=3) as response:
                self.assertFalse(json.load(response)['enabled'])
            service.connect.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


import pytest
from lifecycle_support import fresh_database, seed_configuration, seed_vehicle


def test_read_only_http_startup_uses_local_schema_without_stripe_keys(fresh_database):
    repo = fresh_database()
    configuration = str(seed_configuration(repo, seed_vehicle(repo)))
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    env = {**ENV, 'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
           'PYTHONPATH': os.environ.get('PYTHONPATH', ''), 'PYTHONDONTWRITEBYTECODE': '1',
           'AUTODATA_INGESTION_HTTP_ADDR': f'127.0.0.1:{port}',
           'AUTODATA_DB_ADDRESS': 'postgres:5432', 'AUTODATA_POSTGRES_DB': repo.database_name,
           'AUTODATA_POSTGRES_USER': 'lifecycle_test', 'AUTODATA_POSTGRES_PASSWORD': 'lifecycle_test_only'}
    process = subprocess.Popen([sys.executable, '-m', 'autodata_ingestion.http_service'], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for attempt in range(60):
            if process.poll() is not None:
                raise AssertionError('read-only HTTP startup failed: ' + process.communicate()[1].decode())
            try:
                with urlopen(f'http://127.0.0.1:{port}/healthz', timeout=0.5) as response:
                    assert response.status == 200
                break
            except OSError:
                if attempt == 59:
                    raise
                time.sleep(0.05)
        request = Request(f'http://127.0.0.1:{port}/internal/commerce/purchase-config', data=b'{}',
                          headers={'X-Autodata-Internal-Token': 'fixture-internal'})
        with urlopen(request, timeout=3) as response:
            assert response.status == 200 and json.load(response)['enabled'] is False
        request = Request(f'http://127.0.0.1:{port}/internal/commerce/quote',
                          data=json.dumps({'configuration_id': configuration, 'region': 'US'}).encode(),
                          headers={'X-Autodata-Internal-Token': 'fixture-internal'})
        with urlopen(request, timeout=3) as response:
            quote = json.load(response)
            assert response.status == 200 and quote['amount_minor'] == 2000
            assert quote['purchasable'] is False
    finally:
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)


@pytest.mark.parametrize('live', [False, True])
def test_read_only_retains_exact_paid_scope_without_writes(fresh_database, live):
    repo = fresh_database()
    configuration = str(seed_configuration(repo, seed_vehicle(repo)))
    foreign_configuration = str(seed_configuration(repo, seed_vehicle(repo)))
    order_id, request_id, entitlement_id = [str(uuid.uuid4()) for _ in range(3)]
    with repo.connect() as conn:
        account = conn.execute("INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES('fixture',%s) RETURNING customer_account_id,personal_organization_id", (uuid.uuid4().hex,)).fetchone()
        owner, organization = str(account['customer_account_id']), str(account['personal_organization_id'])
        product = conn.execute("SELECT dataset_product_id FROM dataset_products WHERE product_key='workshop-configuration-v1'").fetchone()['dataset_product_id']
        conn.execute("""INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,
          amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at)
          VALUES(%s,%s,%s,%s,'US',%s,'workshop-v1',2000,'USD','acct_fixture',%s,'price_fixture',%s,'paid',now())""",
          (order_id, owner, organization, configuration, product, live, uuid.uuid4().hex))
        conn.execute("""INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id)
          VALUES(%s,%s,%s,'US','purchased','fast',%s,%s,'workshop-v1',%s)""", (request_id, product, configuration, order_id, uuid.uuid4().hex, organization))
        conn.execute("""INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id)
          VALUES(%s,%s,%s,%s,'active',now(),%s,%s,'US',%s)""", (entitlement_id, organization, request_id, uuid.uuid4().hex, owner, configuration, order_id))
        conn.execute('UPDATE workshop_orders SET entitlement_id=%s,dataset_request_id=%s WHERE order_id=%s', (entitlement_id, request_id, order_id))

    def snapshot():
        with repo.connect() as conn:
            return {table: conn.execute('SELECT md5(string_agg(row_to_json(t)::text,\'\' ORDER BY row_to_json(t)::text)) AS digest FROM '+table+' t').fetchone()['digest']
                    for table in ('workshop_orders', 'entitlements', 'dataset_requests', 'payment_events')}

    before = snapshot()
    mode = 'stripe_live' if live else 'stripe_test'
    service = commerce.ReadOnlyCommerceService(repo.connect, commerce.CommerceConfig(mode, 'acct_fixture', 'price_fixture'))
    with service.transaction() as (_, cursor):
        cursor.execute('SHOW transaction_read_only')
        assert cursor.fetchone()['transaction_read_only'] == 'on'
    from psycopg.errors import ReadOnlySqlTransaction
    with pytest.raises(ReadOnlySqlTransaction), service.transaction() as (_, cursor):
        cursor.execute('UPDATE dataset_products SET price_minor=price_minor')
    quote = service.quote(configuration, 'US')
    assert quote['amount_minor'] == 2000 and quote['purchasable'] is False
    assert service.grant_check(owner, organization, configuration, 'US')['entitlement_id'] == entitlement_id
    assert service.library(owner, organization)['items'][0]['configuration_id'] == configuration
    for config in (commerce.CommerceConfig(mode, 'acct_foreign', 'price_fixture'),
                   commerce.CommerceConfig(mode, 'acct_fixture', 'price_foreign'),
                   commerce.CommerceConfig('stripe_test' if live else 'stripe_live', 'acct_fixture', 'price_fixture')):
        foreign = commerce.ReadOnlyCommerceService(repo.connect, config)
        with pytest.raises(commerce.CommerceError):
            foreign.grant_check(owner, organization, configuration, 'US')
        assert foreign.library(owner, organization)['items'] == []
    for account_id, organization_id, config_id, region in ((str(uuid.uuid4()), organization, configuration, 'US'),
        (owner, str(uuid.uuid4()), configuration, 'US'), (owner, organization, foreign_configuration, 'US'),
        (owner, organization, configuration, 'CA')):
        with pytest.raises(commerce.CommerceError):
            service.grant_check(account_id, organization_id, config_id, region)
    assert snapshot() == before
    with repo.connect() as conn:
        conn.execute("UPDATE entitlements SET status='revoked' WHERE entitlement_id=%s", (entitlement_id,))
    with pytest.raises(commerce.CommerceError) as error:
        service.grant_check(owner, organization, configuration, 'US')
    assert error.value.code == 'ENTITLEMENT_REVOKED'
    assert service.library(owner, organization)['items'][0]['access_state'] == 'revoked'
