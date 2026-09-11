import os
import sys
import unittest
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from autodata_ingestion.pricing import (  # noqa: E402
    price_freshness,
    read_cached_price_or_queue_refresh,
)


class PricingTests(unittest.TestCase):
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

    def test_price_younger_than_thirty_days_is_fresh(self):
        self.assertEqual(
            price_freshness(self.now - timedelta(days=29), self.now),
            "fresh",
        )

    def test_price_at_exactly_thirty_days_is_stale(self):
        self.assertEqual(
            price_freshness(self.now - timedelta(days=30), self.now),
            "stale",
        )

    def test_stale_price_is_returned_with_original_date_and_queued_refresh(self):
        priced_at = "2026-08-12T12:00:00Z"
        part = {
            "canonical_part_id": "brake-fluid",
            "source_part_number": "BF-1",
            "amount": 18.99,
            "currency": "USD",
            "priced_at": priced_at,
            "source_snapshot_id": "snapshot-1",
            "parts_price_snapshot_id": "price-snapshot-1",
            "source_uri": "https://source.test/parts",
        }
        refresh_calls = []

        def queue_refresh(request):
            refresh_calls.append(request)
            return {"refresh_idempotency_key": "price-refresh:snapshot-1"}

        result = read_cached_price_or_queue_refresh(
            part,
            now=self.now,
            refresh=queue_refresh,
        )

        self.assertEqual(result["priced_at"], priced_at)
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(result["refresh_status"], "queued")
        self.assertEqual(result["refresh_idempotency_key"], "price-refresh:snapshot-1")
        self.assertEqual(result["parts_price_snapshot_id"], "price-snapshot-1")
        self.assertFalse(result["markup_applied"])
        self.assertEqual(refresh_calls, [part])
        self.assertNotIn("refresh_status", part)

    def test_fresh_price_does_not_call_refresh(self):
        part = {
            "canonical_part_id": "oil-filter",
            "source_part_number": "OF-1",
            "amount": 9.50,
            "currency": "USD",
            "priced_at": (self.now - timedelta(days=29)).isoformat(),
            "source_snapshot_id": "snapshot-2",
        }
        refresh_calls = []

        result = read_cached_price_or_queue_refresh(
            part,
            now=self.now,
            refresh=lambda request: refresh_calls.append(request),
        )

        self.assertEqual(result["freshness"], "fresh")
        self.assertEqual(result["refresh_status"], "current")
        self.assertEqual(refresh_calls, [])
        self.assertFalse(result["markup_applied"])

    def test_failed_refresh_retains_stale_snapshot_and_retry_metadata(self):
        part = {
            "canonical_part_id": "air-filter",
            "source_part_number": "AF-1",
            "amount": 12.00,
            "currency": "USD",
            "priced_at": (self.now - timedelta(days=30)).isoformat(),
            "source_snapshot_id": "snapshot-3",
        }

        def failed_refresh(_request):
            raise TimeoutError("source unavailable")

        result = read_cached_price_or_queue_refresh(
            part,
            now=self.now,
            refresh=failed_refresh,
        )

        self.assertEqual(result["amount"], 12.00)
        self.assertEqual(result["priced_at"], part["priced_at"])
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(result["refresh_status"], "failed")
        self.assertEqual(result["refresh_attempt_number"], 1)
        self.assertTrue(result["retryable"])
        self.assertIn("source unavailable", result["refresh_failure"]["message"])

    def test_future_dated_price_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "future"):
            price_freshness(self.now + timedelta(seconds=1), self.now)


if __name__ == "__main__":
    unittest.main()
