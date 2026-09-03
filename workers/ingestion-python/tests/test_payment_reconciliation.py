import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.payment_reconciliation import (  # noqa: E402
    PaymentIntent,
    canonical_payment_payload,
)


class PaymentReconciliationTests(unittest.TestCase):
    def test_verified_event_accepts_delayed_dataset_request_reference(self):
        intent = PaymentIntent.from_event(
            {
                "provider_name": "fake",
                "provider_event_id": "fake-event-1",
                "event_type": "checkout.completed",
                "product_id": "vehicle-core-fixture",
                "purchaser_id": "41000000-0000-0000-0000-000000000001",
                "dataset_request_id": "30000000-0000-0000-0000-000000000001",
            }
        )

        self.assertEqual(intent.dataset_request_id, "30000000-0000-0000-0000-000000000001")
        self.assertEqual(intent.product_id, "vehicle-core-fixture")
        self.assertEqual(intent.event_type, "checkout.completed")

    def test_canonical_payload_is_stable_for_replayed_webhooks(self):
        first = {"product_id": "vehicle-core-fixture", "purchaser_id": "org-1", "metadata": {"b": 2, "a": 1}}
        second = {"metadata": {"a": 1, "b": 2}, "purchaser_id": "org-1", "product_id": "vehicle-core-fixture"}

        self.assertEqual(canonical_payment_payload(first), canonical_payment_payload(second))

    def test_verified_event_rejects_unknown_event_types_and_missing_identity(self):
        with self.assertRaises(ValueError):
            PaymentIntent.from_event({"provider_event_id": "event-1", "event_type": "charge.refunded"})
        with self.assertRaises(ValueError):
            PaymentIntent.from_event({"event_type": "checkout.completed", "product_id": "p", "purchaser_id": "o"})


if __name__ == "__main__":
    unittest.main()
