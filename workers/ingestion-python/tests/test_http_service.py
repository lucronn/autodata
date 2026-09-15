import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.http_service import dispatch_request  # noqa: E402


class HTTPServiceTests(unittest.TestCase):
    def test_article_intake_dispatches_vehicle_scoped_url_request(self):
        calls = []

        def article_runner(source_uri, vehicle_json):
            calls.append((source_uri, json.loads(vehicle_json)))
            return {"status": "ready", "articles": [{"article_id": "TSB-42"}]}

        result = dispatch_request(
            "/v1/article-intakes",
            {
                "source_uri": "https://source.example/tsb-42",
                "vehicle": {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US"},
            },
            article_runner=article_runner,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(calls[0][0], "https://source.example/tsb-42")
        self.assertEqual(calls[0][1]["make"], "Chevy")

    def test_knowledge_dispatches_the_complete_vehicle_query_payload(self):
        calls = []

        def knowledge_runner(serialized_request):
            calls.append(json.loads(serialized_request))
            return {"status": "cache_hit", "results": []}

        result = dispatch_request(
            "/v1/knowledge-queries",
            {
                "vehicle": {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US"},
                "query": "brake caliper",
                "keywords": ["torque"],
            },
            knowledge_runner=knowledge_runner,
        )

        self.assertEqual(result["status"], "cache_hit")
        self.assertEqual(calls[0]["query"], "brake caliper")
        self.assertEqual(calls[0]["vehicle"]["model"], "Silverado 1500")

    def test_job_plan_dispatches_natural_language_vehicle_request(self):
        calls = []

        def job_runner(serialized_request):
            calls.append(json.loads(serialized_request))
            return {"status": "ready", "labor": {"total_labor_hours": 3.5}}

        result = dispatch_request(
            "/v1/job-plans",
            {
                "vehicle": {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US"},
                "query": "replace alternator and starter",
            },
            job_runner=job_runner,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(calls[0]["query"], "replace alternator and starter")

    def test_dispatch_rejects_unknown_routes_and_invalid_shapes(self):
        with self.assertRaises(ValueError):
            dispatch_request("/v1/unknown", {})
        with self.assertRaises(ValueError):
            dispatch_request("/v1/article-intakes", {"source_uri": "https://source.example/article"})
        with self.assertRaises(ValueError):
            dispatch_request("/v1/job-plans", {"vehicle": {}, "query": "starter"})


if __name__ == "__main__":
    unittest.main()
