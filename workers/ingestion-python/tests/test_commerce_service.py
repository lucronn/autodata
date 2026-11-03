"""Authority checks independent of external services; PG transitions live separately."""
import copy
from datetime import UTC, datetime
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from autodata_ingestion.commerce_service import (CommerceError, validate_uuid, exact_fields,
    validate_settlement, validate_checkout_url, canonical_checkout_hash, checkout_return_origin)


class CommerceAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.order = {'order_id':'6f0a2166-0df4-4d2b-916d-99b4d0bd52de','amount_minor':2000,
                      'currency':'USD','livemode':False,'expected_price_id':'price_fixture'}
        self.session = {'id':'cs_test_fixture','metadata':{'order_id':self.order['order_id']},
            'mode':'payment','livemode':False,'amount_total':2000,'currency':'usd',
            'payment_status':'paid','status':'complete',
            'line_items':{'data':[{'price':{'id':'price_fixture'},'quantity':1}]},
            'payment_intent':{'id':'pi_fixture','metadata':{'order_id':self.order['order_id']},
                'livemode':False,'amount':2000,'amount_received':2000,'currency':'usd',
                'capture_method':'automatic','status':'succeeded'}}

    def test_settlement_requires_all_server_financial_bindings(self):
        self.assertEqual(validate_settlement(self.order,self.session), 'pi_fixture')
        for key,bad in [('mode','subscription'),('livemode',True),('amount_total',1999),
                        ('currency','eur'),('payment_status','unpaid'),('status','open')]:
            session=copy.deepcopy(self.session);session[key]=bad
            with self.assertRaises(CommerceError,msg=key):validate_settlement(self.order,session)
        for mutation in (lambda s:s['metadata'].update(order_id='foreign'),
                         lambda s:s['line_items']['data'][0].update(quantity=2),
                         lambda s:s['line_items']['data'][0]['price'].update(id='foreign'),
                         lambda s:s['payment_intent'].update(capture_method='manual'),
                         lambda s:s['payment_intent'].update(status='processing'),
                         lambda s:s['payment_intent']['metadata'].update(order_id='foreign')):
            session=copy.deepcopy(self.session);mutation(session)
            with self.assertRaises(CommerceError):validate_settlement(self.order,session)

    def test_client_cannot_supply_price_owner_or_return_url(self):
        with self.assertRaises(CommerceError):exact_fields({'configuration_id':'id','amount_minor':1},{'configuration_id'})
        for value in ('no',self.order['order_id'].upper(),None):
            with self.assertRaises(CommerceError):validate_uuid(value)
        for value in ('http://checkout.stripe.com/c/pay/a','https://evil.test/c/pay/a',
                      'https://user@checkout.stripe.com/c/pay/a','https://checkout.stripe.com:443/c/pay/a',
                      'https://checkout.stripe.com/c/pay/','https://checkout.stripe.com/c/pay/a\n'):
            with self.assertRaises(CommerceError):validate_checkout_url(value)
        self.assertEqual(validate_checkout_url('https://checkout.stripe.com/c/pay/a'),'https://checkout.stripe.com/c/pay/a')
        hosted='https://checkout.stripe.com/c/pay/cs_test_fixture#fidkdFixtureFragment'
        self.assertEqual(validate_checkout_url(hosted),hosted)
        self.assertEqual(canonical_checkout_hash('id','US','v1'),canonical_checkout_hash('id','US','v1'))
        self.assertNotEqual(canonical_checkout_hash('id','US','v1'),canonical_checkout_hash('id','CA','v1'))

    def test_return_origin_is_server_configured_and_environment_bound(self):
        self.assertEqual(checkout_return_origin('production','https://cars.tk'),'https://cars.tk')
        self.assertEqual(checkout_return_origin('staging','https://stage.example:8443'),'https://stage.example:8443')
        self.assertEqual(checkout_return_origin('test','http://127.0.0.1:8080'),'http://127.0.0.1:8080')
        for environment,value in [('production','https://other.test'),('staging','http://localhost'),
            ('unknown','https://cars.tk'),('','https://cars.tk'),('test','http://evil.test'),
            ('test','https://user@localhost'),('test','https://localhost:bad'),
            ('test','https://localhost/'),('test','https://localhost?q=x'),('test','https://localhost#x')]:
            with self.assertRaises(CommerceError,msg=(environment,value)):checkout_return_origin(environment,value)
