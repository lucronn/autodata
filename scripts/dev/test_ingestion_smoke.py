import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))

from ingestion_smoke import summarize_source_object, summarize_viewable_event  # noqa: E402


class IngestionSmokeContractTests(unittest.TestCase):
    def test_source_object_summary_checks_content_hash_and_identity(self):
        payload = b'{"vehicle":{"make":"Toyota","model":"Corolla","year":2024,"region":"US"}}'

        summary = summarize_source_object(payload, "Toyota Corolla 2024", "toyota-corolla-2024-us")

        self.assertEqual(summary["object_bytes"], len(payload))
        self.assertEqual(summary["object_vehicle"], "Toyota Corolla 2024")

    def test_viewable_event_summary_requires_versioned_event_and_revision(self):
        event = {
            "event_type": "dataset.viewable",
            "event_version": 1,
            "revision_id": "revision-1",
            "idempotency_key": "viewable:request-1:1",
        }

        summary = summarize_viewable_event(event, "revision-1")

        self.assertEqual(summary["subject"], "dataset.viewable")
        self.assertEqual(summary["revision_id"], "revision-1")

    def test_viewable_event_summary_fails_actionably_for_wrong_event(self):
        with self.assertRaisesRegex(ValueError, "dataset.viewable"):
            summarize_viewable_event({"event_type": "dataset.deep.requested"}, "revision-1")


if __name__ == "__main__":
    unittest.main()
