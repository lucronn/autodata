import sys
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.worker import run_once  # noqa: E402


class EnrichmentWorkerTests(unittest.TestCase):
    def test_idle_run_reports_deep_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "enrichment", "lane": "deep", "status": "idle"})

    def test_viewable_consumer_fans_out_to_the_scheduler(self):
        handled = {}

        async def consume(handler, **_kwargs):
            event = {
                "event_id": "event-1",
                "producer": "ingestion-worker",
                "event_type": "dataset.viewable",
                "event_version": 1,
                "request_id": "request-1",
                "projection_id": "projection-1",
                "correlation_id": "correlation-1",
                "idempotency_key": "viewable-1",
                "payload": {"deep_sections": ["diagnostics", "procedures"]},
            }
            handled["result"] = handler(event)
            return {"status": "completed", "received": 1}

        with patch.dict("os.environ", {"AUTODATA_VIEWABLE_CONSUMER_ENABLED": "1"}, clear=False):
            with patch("autodata_enrichment.viewable_consumer.consume_once", side_effect=consume):
                with patch(
                    "autodata_enrichment.publisher.schedule_deep_sections",
                    return_value={"status": "scheduled", "jobs": ["job-1"]},
                ) as schedule:
                    result = run_once()

        schedule.assert_called_once_with("projection-1", ("diagnostics", "procedures"), "deep-v1")
        self.assertEqual(handled["result"]["status"], "scheduled")
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
