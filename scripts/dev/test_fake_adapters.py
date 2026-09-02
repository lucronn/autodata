import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))

from autodata_contracts.fakes import (  # noqa: E402
    FakePaymentProvider,
    FakePrimarySource,
)


class FakeAdapterTests(unittest.TestCase):
    def test_source_retrieval_is_stable_and_has_attribution(self):
        source = FakePrimarySource()

        first = source.fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")
        second = source.fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")

        self.assertEqual(first, second)
        self.assertEqual(len(first.content_sha256), 64)
        self.assertEqual(first.attribution["adapter"], "fake-primary-source")
        self.assertEqual(first.takedown_status, "active")

    def test_takedown_fixture_is_explicit(self):
        source = FakePrimarySource()

        snapshot = source.fetch("Toyota", "Corolla", 2024, "US", "takedown-v1")

        self.assertEqual(snapshot.takedown_status, "takedown")
        self.assertTrue(snapshot.attribution["takedown_fixture"])

    def test_replayed_webhook_creates_one_event_and_one_entitlement(self):
        provider = FakePaymentProvider(signing_secret="local-test-signing-secret")
        session = provider.create_checkout_session(
            "vehicle-core-fixture", "41000000-0000-0000-0000-000000000001"
        )

        verified_first = provider.verify_webhook(session["headers"], session["body"])
        verified_second = provider.verify_webhook(session["headers"], session["body"])
        event_first = provider.record_payment_event(verified_first)
        event_second = provider.record_payment_event(verified_second)
        entitlement_first = provider.create_entitlement(event_first)
        entitlement_second = provider.create_entitlement(event_second)

        self.assertEqual(event_first, event_second)
        self.assertEqual(entitlement_first, entitlement_second)
        self.assertEqual(len(provider.payment_events), 1)
        self.assertEqual(len(provider.entitlements), 1)

    def test_entitlement_can_be_revoked_without_mutating_payment_event(self):
        provider = FakePaymentProvider(signing_secret="local-test-signing-secret")
        session = provider.create_checkout_session("vehicle-core-fixture", "org-1")
        payment_event = provider.record_payment_event(
            provider.verify_webhook(session["headers"], session["body"])
        )
        entitlement = provider.create_entitlement(payment_event)

        revoked = provider.revoke_entitlement(entitlement.entitlement_id, "source_takedown")

        self.assertEqual(revoked.status, "revoked")
        self.assertEqual(provider.payment_events[payment_event.provider_event_id], payment_event)


if __name__ == "__main__":
    unittest.main()
