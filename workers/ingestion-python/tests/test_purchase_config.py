"""Pure strict configuration and pre-transaction purchase authority regressions."""
import json
import sys
import unittest
from pathlib import Path
from dataclasses import FrozenInstanceError
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from autodata_ingestion.purchase_config import PurchaseConfig, parse_purchase_config
from autodata_ingestion.commerce_service import CommerceService, CommerceConfig, CommerceError

DISABLED = {"enabled":False,"terms_version":"workshop-v1","terms_url":None,"privacy_url":None,"refund_url":None,"contact_url":None,"tax_notice":None}
def enabled_public():
    return dict(DISABLED, enabled=True, terms_url="https://legal.example.test/terms", privacy_url="https://legal.example.test/privacy", refund_url="https://legal.example.test/refund", contact_url="https://legal.example.test/contact", tax_notice="Synthetic fixture notice")
def enabled_config():
    return PurchaseConfig.from_public(enabled_public())
URL_VECTORS = [{'id': 'plain_https', 'url': 'https://legal.example.test/terms', 'valid': True}, {'id': 'explicit_443', 'url': 'https://legal.example.test:443/terms', 'valid': True}, {'id': 'mixed_ascii', 'url': 'https://Legal.Example.TEST/terms', 'valid': True}, {'id': 'punycode', 'url': 'https://xn--bcher-kva.example/terms', 'valid': True}, {'id': 'encoded_space', 'url': 'https://legal.example.test/terms%20v1', 'valid': True}, {'id': 'encoded_octets', 'url': 'https://legal.example.test/a%2Fb%FF', 'valid': True}, {'id': 'wrong_scheme', 'url': 'http://legal.example.test/terms', 'valid': False}, {'id': 'upper_scheme', 'url': 'HTTPS://legal.example.test/terms', 'valid': False}, {'id': 'credentials', 'url': 'https://user:pass@legal.example.test/terms', 'valid': False}, {'id': 'empty_query', 'url': 'https://legal.example.test/terms?', 'valid': False}, {'id': 'query', 'url': 'https://legal.example.test/terms?v=1', 'valid': False}, {'id': 'empty_fragment', 'url': 'https://legal.example.test/terms#', 'valid': False}, {'id': 'fragment', 'url': 'https://legal.example.test/terms#v1', 'valid': False}, {'id': 'wrong_port', 'url': 'https://legal.example.test:444/terms', 'valid': False}, {'id': 'padded_port', 'url': 'https://legal.example.test:0443/terms', 'valid': False}, {'id': 'empty_port', 'url': 'https://legal.example.test:/terms', 'valid': False}, {'id': 'ipv4', 'url': 'https://127.0.0.1/terms', 'valid': False}, {'id': 'ipv6', 'url': 'https://[::1]/terms', 'valid': False}, {'id': 'localhost', 'url': 'https://localhost/terms', 'valid': False}, {'id': 'trailing_dot', 'url': 'https://legal.example.test./terms', 'valid': False}, {'id': 'empty_label', 'url': 'https://legal..test/terms', 'valid': False}, {'id': 'leading_hyphen', 'url': 'https://-legal.example.test/terms', 'valid': False}, {'id': 'trailing_hyphen', 'url': 'https://legal-.example.test/terms', 'valid': False}, {'id': 'underscore', 'url': 'https://legal_site.example.test/terms', 'valid': False}, {'id': 'numeric_tld', 'url': 'https://legal.example.123/terms', 'valid': False}, {'id': 'unicode_host', 'url': 'https://bücher.example/terms', 'valid': False}, {'id': 'host_escape', 'url': 'https://legal%2Eexample.test/terms', 'valid': False}, {'id': 'incomplete_escape', 'url': 'https://legal.example.test/a%2', 'valid': False}, {'id': 'bad_escape', 'url': 'https://legal.example.test/a%G0', 'valid': False}, {'id': 'bare_percent', 'url': 'https://legal.example.test/a%', 'valid': False}, {'id': 'space', 'url': 'https://legal.example.test/terms v1', 'valid': False}, {'id': 'tab', 'url': 'https://legal.example.test/terms\tv1', 'valid': False}, {'id': 'nbsp', 'url': 'https://legal.example.test/terms\xa0v1', 'valid': False}, {'id': 'line_separator', 'url': 'https://legal.example.test/terms\u2028v1', 'valid': False}, {'id': 'feff', 'url': 'https://legal.example.test/terms\ufeffv1', 'valid': False}, {'id': 'c0', 'url': 'https://legal.example.test/terms\x01v1', 'valid': False}, {'id': 'del', 'url': 'https://legal.example.test/terms\x7fv1', 'valid': False}, {'id': 'c1', 'url': 'https://legal.example.test/terms\x9fv1', 'valid': False}]
FORBIDDEN = list(range(33)) + list(range(127,161)) + [0x1680] + list(range(0x2000,0x200b)) + [0x2028,0x2029,0x202f,0x205f,0x3000,0xfeff]

class PurchaseConfigTests(unittest.TestCase):
    def test_defaults_and_complete_disabled_precedence(self):
        for raw in (None, "", json.dumps(DISABLED)):
            config, invalid = parse_purchase_config(raw)
            self.assertFalse(invalid); self.assertEqual(config.public(), DISABLED)
        for value in ({"enabled":False}, dict(DISABLED, terms_url="https://private.invalid"), dict(DISABLED, other=1)):
            self.assertEqual(parse_purchase_config(json.dumps(value))[1], True)
        for raw in (" ", "null", "[]", "true", "NaN", '{"enabled":false,"enabled":false}', '\ud800', '"\\ud800"'):
            self.assertEqual(parse_purchase_config(raw)[0].public(), DISABLED)
            self.assertTrue(parse_purchase_config(raw)[1])

    def test_frozen_validating_construction_and_fresh_projection(self):
        value=enabled_public(); config=PurchaseConfig.from_public(value)
        value['enabled']=False; projection=config.public();projection['enabled']=False
        self.assertTrue(config.enabled)
        with self.assertRaises((FrozenInstanceError, AttributeError)):config.enabled=False
        with self.assertRaises((ValueError, TypeError)):PurchaseConfig(True)
        with self.assertRaises((ValueError, TypeError)):PurchaseConfig(enabled=True,terms_version='workshop-v1')
        for field,bad in [('enabled',1),('terms_version','v2'),('tax_notice',None),('tax_notice',' '),('tax_notice','a\nb'),('tax_notice','a\u2028b'),('tax_notice','a\x7fb'),('tax_notice','a\ud800b')]:
            with self.subTest(field=field,bad=repr(bad)):
                self.assertTrue(parse_purchase_config(json.dumps(dict(enabled_public(),**{field:bad})))[1])
        raw=json.dumps(enabled_public())
        self.assertFalse(parse_purchase_config(raw)[1])
        for bad in (raw[:-1]+',"enabled":true}',raw+' {}'):
            self.assertTrue(parse_purchase_config(bad)[1])

    def test_literal_url_inventory_and_forbidden_codepoints(self):
        for vector in URL_VECTORS:
            with self.subTest(id=vector['id']):
                config,invalid=parse_purchase_config(json.dumps(dict(enabled_public(),terms_url=vector['url'])))
                self.assertEqual(not invalid,vector['valid'])
                if not invalid:self.assertEqual(config.public()['terms_url'],vector['url'])
        for code in FORBIDDEN:
            for value in (chr(code)+'https://legal.example.test/a','https://legal.example.test/a'+chr(code)+'b','https://legal.example.test/a'+chr(code)):
                self.assertTrue(parse_purchase_config(json.dumps(dict(enabled_public(),terms_url=value)))[1],repr(value))

    def test_utf8_raw_notice_url_and_dns_boundaries(self):
        for n,valid in ((1024,True),(1025,False)):
            self.assertEqual(not parse_purchase_config(json.dumps(dict(enabled_public(),tax_notice='x'*n)))[1],valid)
        prefix='https://legal.example.test/'
        for n,valid in ((2048,True),(2049,False)):
            self.assertEqual(not parse_purchase_config(json.dumps(dict(enabled_public(),terms_url=prefix+'x'*(n-len(prefix)))))[1],valid)
        for host,valid in [('a.co',True),('a.c',False),('a.'+'x'*63,True),('a.'+'x'*64,False),('x'*63+'.test',True),('x'*64+'.test',False),('.'.join(['x'*63]*3+['x'*61]),True),('.'.join(['x'*63]*3+['x'*62]),False)]:
            self.assertEqual(not parse_purchase_config(json.dumps(dict(enabled_public(),terms_url='https://'+host+'/')))[1],valid,host)
        raw=json.dumps(DISABLED)
        self.assertFalse(parse_purchase_config(raw+' '*(16384-len(raw)))[1])
        self.assertTrue(parse_purchase_config(raw+' '*(16385-len(raw)))[1])

    def test_direct_default_and_malformed_deny_before_database_or_provider(self):
        def forbidden():raise AssertionError('database touched while paused')
        for config in (None,PurchaseConfig.disabled(),parse_purchase_config('{"enabled":false}')[0]):
            service=CommerceService(forbidden,CommerceConfig('stripe_test','acct_fixture','price_fixture'),object(),purchase_config=config)
            for key in ('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222'):
                with self.assertRaises(CommerceError) as error:
                    service.checkout('account','org',key,dict(configuration_id=key,region='US',terms_version='workshop-v1'))
                self.assertEqual((error.exception.code,error.exception.http_status),('COMMERCE_UNAVAILABLE',503))
            self.assertEqual(service.purchase_configuration(),DISABLED)
        with self.assertRaises((ValueError,TypeError)):
            CommerceService(forbidden,CommerceConfig('stripe_test','acct_fixture','price_fixture'),object(),purchase_config=enabled_public())
        service=CommerceService(forbidden,CommerceConfig('stripe_test','acct_fixture','price_fixture'),object(),purchase_config=enabled_config())
        with self.assertRaisesRegex(AssertionError,'database touched'):
            service.checkout('account','org','11111111-1111-4111-8111-111111111111',dict(configuration_id='11111111-1111-4111-8111-111111111111',region='US',terms_version='workshop-v1'))

    def test_malformed_composition_logs_once_without_bypassing_existing_checks(self):
        from autodata_ingestion.commerce_service import configured_commerce
        raw='private notice https://secret.invalid'
        with patch.dict('os.environ',{'AUTODATA_COMMERCE_MODE':'stripe_test','AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON':raw},clear=True):
            with self.assertLogs('autodata_ingestion.commerce_service',level='WARNING') as logs:
                with self.assertRaises(CommerceError):configured_commerce()
        self.assertEqual(len(logs.output),1)
        self.assertEqual(logs.records[0].getMessage(),'Workshop purchase configuration invalid; new checkout disabled')
        self.assertNotIn(raw,str(logs.output))
        for raw in ('',json.dumps(DISABLED)):
            with patch.dict('os.environ',{'AUTODATA_COMMERCE_MODE':'stripe_test','AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON':raw},clear=True):
                with self.assertNoLogs('autodata_ingestion.commerce_service'):
                    with self.assertRaises(CommerceError):configured_commerce()

    def test_valid_financial_startup_survives_malformed_notices_and_preserves_checks(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from autodata_ingestion.commerce_service import configured_commerce
        calls=[]
        class Provider:
            def __init__(self,**kwargs):pass
            def verify_merchant(self,account):calls.append(('merchant',account))
            def verify_price(self,price,mode):calls.append(('price',price,mode))
        class Cursor:
            def execute(self,sql,args=None):self.sql=sql;calls.append(('sql',sql))
            def fetchone(self):
                if 'schema_migrations' in self.sql:return {'present':1}
                if 'stripe_account_id<>' in self.sql:return None
                if 'dataset_products' in self.sql:return {'dataset_product_id':'fixture'}
                raise AssertionError(self.sql)
        @contextmanager
        def transaction(_):yield None,Cursor()
        stripe=SimpleNamespace(StripeClient=lambda *a,**k:object(),RequestsClient=lambda **k:object())
        env=dict(AUTODATA_COMMERCE_MODE='stripe_test',AUTODATA_ENV='test',AUTODATA_PUBLIC_ORIGIN='http://127.0.0.1:3000',
            AUTODATA_STRIPE_SECRET_KEY='sk_test_fixture',AUTODATA_STRIPE_WEBHOOK_SECRET='whsec_fixture',
            AUTODATA_STRIPE_ACCOUNT_ID='acct_fixture',AUTODATA_STRIPE_PRICE_ID='price_fixture',AUTODATA_INGESTION_INTERNAL_TOKEN='fixture-token')
        for raw,enabled,diagnostic in (('{"enabled":false}',False,True),(json.dumps(DISABLED),False,False),(json.dumps(enabled_public()),True,False)):
            calls.clear()
            with patch.dict('os.environ',dict(env,AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON=raw),clear=True),patch.dict('sys.modules',{'stripe':stripe}),patch('autodata_ingestion.stripe_adapter.StripePaymentProvider',Provider),patch.object(CommerceService,'transaction',transaction):
                with (self.assertLogs('autodata_ingestion.commerce_service') if diagnostic else self.assertNoLogs('autodata_ingestion.commerce_service')) as logs:
                    service=configured_commerce(connection_factory=lambda:None)
                self.assertEqual(service.purchase_configuration()['enabled'],enabled)
                self.assertIn(('merchant','acct_fixture'),calls)
                self.assertIn(('price','price_fixture',False),calls)
                self.assertEqual(sum('schema_migrations' in str(call) for call in calls),1)
                self.assertEqual(sum('stripe_account_id<>' in str(call) for call in calls),1)
                self.assertEqual(sum('dataset_products' in str(call) for call in calls),1)
                if diagnostic:self.assertEqual(len(logs.output),1)

    def test_notice_cannot_be_only_ecmascript_whitespace(self):
        for notice in ('\ufeff',' \ufeff '):
            self.assertTrue(parse_purchase_config(json.dumps(dict(enabled_public(),tax_notice=notice)))[1])
