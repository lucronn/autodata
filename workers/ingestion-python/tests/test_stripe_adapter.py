import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.stripe_adapter import StripePaymentProvider  # noqa: E402


class FakeStripeWebhook:
    event = {
        "id": "evt_checkout_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "product_id": "vehicle-core-fixture",
                    "purchaser_id": "org-123",
                    "dataset_request_id": "request-123",
                }
            }
        },
    }

    @classmethod
    def construct_event(cls, body, signature, secret, tolerance=300):
        if (body, signature, secret) != ('{"signed":true}', "sig-123", "whsec-test"):
            raise ValueError("invalid signature")
        return cls.event


class FakeStripeModule:
    Webhook = FakeStripeWebhook


class FakeCheckoutSessions:
    def __init__(self):
        self.calls = []

    def create(self, params=None, options=None):
        self.calls.append(params)
        self.options = options
        return {"id": "cs_test_123", "url": "https://checkout.stripe.test/cs_test_123"}


class FakeStripeClient:
    def __init__(self, sessions):
        self.v1 = type("V1", (), {"checkout": type("Checkout", (), {"sessions": sessions})()})()


class StripePaymentProviderTests(unittest.TestCase):
    def setUp(self):
        self.sessions = FakeCheckoutSessions()
        self.client = FakeStripeClient(self.sessions)
        self.provider = StripePaymentProvider(
            stripe_module=FakeStripeModule,
            client=self.client,
            webhook_secret="whsec-test",
            success_url="https://app.test/success",
            cancel_url="https://app.test/cancel",
        )

    def test_checkout_session_sends_only_provider_neutral_metadata(self):
        session = self.provider.create_checkout_session(
            "vehicle-core-fixture", "org-123", "request-123"
        )

        self.assertEqual(session, {
            "provider_name": "stripe",
            "session_id": "cs_test_123",
            "checkout_url": "https://checkout.stripe.test/cs_test_123",
        })
        self.assertEqual(
            self.sessions.calls,
            [{
                "mode": "payment",
                "line_items": [{"price": "vehicle-core-fixture", "quantity": 1}],
                "success_url": "https://app.test/success",
                "cancel_url": "https://app.test/cancel",
                "metadata": {
                    "product_id": "vehicle-core-fixture",
                    "purchaser_id": "org-123",
                    "dataset_request_id": "request-123",
                },
            }],
        )

    def test_order_checkout_uses_durable_key_and_exact_financial_parameters(self):
        order = {'order_id': '6f0a2166-0df4-4d2b-916d-99b4d0bd52de',
                 'expected_price_id': 'price_fixture', 'provider_idempotency_key': 'workshop:durable:v1',
                 'first_create_attempt_at': 1700000000}
        self.provider.create_order_checkout(order)
        params = self.sessions.calls[0]
        self.assertEqual(self.sessions.options, {'idempotency_key': 'workshop:durable:v1'})
        self.assertEqual(params['line_items'], [{'price': 'price_fixture', 'quantity': 1}])
        self.assertEqual(params['payment_method_types'], ['card'])
        self.assertEqual(params['payment_intent_data'], {'capture_method': 'automatic', 'metadata': {'order_id': order['order_id']}})
        self.assertEqual(params['metadata'], {'order_id': order['order_id']})
        self.assertEqual(params['expires_at'], 1700003600)
        self.assertNotIn('purchaser_id', str(params))

    def test_commerce_webhook_freezes_only_safe_signed_facts(self):
        original = FakeStripeWebhook.event
        try:
            FakeStripeWebhook.event = {'id': 'evt_safe', 'type': 'charge.refunded', 'created': 123,
                'livemode': False, 'data': {'object': {'id': 'ch_safe', 'payment_intent': 'pi_safe',
                'metadata': {'order_id': '6f0a2166-0df4-4d2b-916d-99b4d0bd52de'},
                'amount': 2000, 'amount_refunded': 2000, 'currency': 'usd', 'refunded': True,
                'customer': {'email': 'must-not-persist'}, 'receipt_url': 'private'}}}
            event = self.provider.verify_commerce_webhook({'Stripe-Signature': 'sig-123'}, '{"signed":true}')
            self.assertEqual(event['payment_intent_id'], 'pi_safe')
            self.assertEqual(event['amount_refunded'], 2000)
            self.assertNotIn('must-not-persist', str(event))
            self.assertNotIn('receipt_url', event)
        finally:
            FakeStripeWebhook.event = original

    def test_webhook_is_signature_verified_and_normalized(self):
        event = self.provider.verify_webhook(
            {"Stripe-Signature": "sig-123"}, '{"signed":true}'
        )

        self.assertEqual(event, {
            "provider_name": "stripe",
            "provider_event_id": "evt_checkout_123",
            "event_type": "checkout.completed",
            "product_id": "vehicle-core-fixture",
            "purchaser_id": "org-123",
            "dataset_request_id": "request-123",
        })

    def test_webhook_rejects_unsupported_event_and_missing_metadata(self):
        class UnsupportedWebhook(FakeStripeWebhook):
            event = {"id": "evt_other", "type": "payment_intent.succeeded", "data": {"object": {}}}

        provider = StripePaymentProvider(
            stripe_module=type("Stripe", (), {"Webhook": UnsupportedWebhook}),
            client=self.client,
            webhook_secret="whsec-test",
            success_url="https://app.test/success",
            cancel_url="https://app.test/cancel",
        )
        with self.assertRaises(ValueError):
            provider.verify_webhook({"Stripe-Signature": "sig-123"}, '{"signed":true}')


class OfficialStripeSDKTests(unittest.TestCase):
    def test_actual_sdk_price_must_match_immutable_product_before_checkout(self):
        import stripe,json
        class Transport(stripe.HTTPClient):
            name='price-fixture'
            def __init__(self):super().__init__();self.price={'id':'price_fixture','active':True,'type':'one_time','currency':'usd','unit_amount':2000,'livemode':False}
            def request(self,method,url,headers,post_data=None,**kwargs):
                if method!='get' or url!='https://api.stripe.com/v1/prices/price_fixture':raise AssertionError('unexpected destination')
                return json.dumps(self.price),200,{}
        transport=Transport()
        provider=StripePaymentProvider(stripe_module=stripe,client=stripe.StripeClient('sk_test_fixture',max_network_retries=0,http_client=transport),webhook_secret='whsec_fixture',success_url='https://cars.tk/workshop/',cancel_url='https://cars.tk/workshop/')
        provider.verify_price('price_fixture',False)
        for key,bad in [('active',False),('type','recurring'),('currency','eur'),('unit_amount',1999),('livemode',True)]:
            original=transport.price[key];transport.price[key]=bad
            with self.assertRaises(ValueError,msg=key):provider.verify_price('price_fixture',False)
            transport.price[key]=original

    def test_actual_sdk_params_options_merchant_and_signature_transport(self):
        import hashlib
        import hmac
        import json
        import time
        import stripe
        from urllib.parse import parse_qs
        self.assertEqual(stripe.VERSION, '16.1.0')

        class LocalTransport(stripe.HTTPClient):
            name = 'fixture'
            def __init__(self):
                super().__init__()
                self.calls = []
            def request(self, method, url, headers, post_data=None, **kwargs):
                self.calls.append((method, url, headers, post_data))
                if method == 'get' and url == 'https://api.stripe.com/v1/account':
                    payload = {'id': 'acct_fixture', 'object': 'account'}
                elif method == 'post' and url == 'https://api.stripe.com/v1/checkout/sessions':
                    payload = {'id': 'cs_test_fixture', 'object': 'checkout.session', 'url': 'https://checkout.stripe.com/c/pay/cs_test_fixture'}
                else:
                    raise AssertionError('unexpected SDK destination')
                return json.dumps(payload), 200, {}
        transport = LocalTransport()
        client = stripe.StripeClient('sk_test_fixture', max_network_retries=0, http_client=transport)
        provider = StripePaymentProvider(stripe_module=stripe, client=client,
            webhook_secret='whsec_fixture', success_url='https://cars.tk/workshop/', cancel_url='https://cars.tk/workshop/')
        provider.verify_merchant('acct_fixture')
        order = {'order_id': '6f0a2166-0df4-4d2b-916d-99b4d0bd52de', 'expected_price_id':'price_fixture',
                 'provider_idempotency_key':'workshop:fixture:v1', 'first_create_attempt_at': int(time.time())}
        self.assertEqual(provider.create_order_checkout(order)['id'], 'cs_test_fixture')
        method,url,headers,body = transport.calls[-1]
        self.assertEqual(headers['Idempotency-Key'], order['provider_idempotency_key'])
        self.assertEqual(parse_qs(body)['payment_intent_data[metadata][order_id]'], [order['order_id']])
        event = {'id':'evt_fixture','object':'event','created':int(time.time()),'livemode':False,
                 'type':'checkout.session.completed','data':{'object':{'id':'cs_test_fixture','metadata':{'order_id':order['order_id']}}}}
        raw = json.dumps(event).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(b'whsec_fixture', stamp.encode()+b'.'+raw, hashlib.sha256).hexdigest()
        self.assertEqual(provider.verify_commerce_webhook({'Stripe-Signature':f't={stamp},v1={signature}'},raw)['order_id'],order['order_id'])
        with self.assertRaises(ValueError):
            provider.verify_commerce_webhook({'Stripe-Signature':f't={stamp},v1={signature}'},raw+b' ')
        self.assertEqual(len(transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
