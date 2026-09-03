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
    def construct_event(cls, body, signature, secret):
        if (body, signature, secret) != ('{"signed":true}', "sig-123", "whsec-test"):
            raise ValueError("invalid signature")
        return cls.event


class FakeStripeModule:
    Webhook = FakeStripeWebhook


class FakeCheckoutSessions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "cs_test_123", "url": "https://checkout.stripe.test/cs_test_123"}


class FakeStripeClient:
    def __init__(self, sessions):
        self.checkout = type("Checkout", (), {"sessions": sessions})()


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


if __name__ == "__main__":
    unittest.main()
