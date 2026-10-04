import json
import sys
import unittest
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.http_service import dispatch_request, make_handler  # noqa: E402


class HTTPServiceTests(unittest.TestCase):
    def test_dispatch_rejects_retired_chat_paths(self):
        with self.assertRaisesRegex(ValueError, "unknown ingestion service route"):
            dispatch_request("/v1/chat/queries", {"message": "legacy request"})

    def test_catalog_ensure_dispatches_once_to_catalog_hydration_service(self):
        calls = []

        def catalog_runner(serialized_request):
            calls.append(json.loads(serialized_request))
            return {"status": "hydrated", "complete": True, "rows": [{"id": "article-1"}]}

        result = dispatch_request(
            "/v1/catalog/ensure",
            {"scope": "article", "idempotency_key": "catalog-key-1", "article_id": "article-1"},
            catalog_runner=catalog_runner,
        )

        self.assertEqual(result["status"], "hydrated")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["idempotency_key"], "catalog-key-1")
        self.assertEqual(calls[0]["article_id"], "article-1")

    def test_catalog_ensure_requires_idempotency_key(self):
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            dispatch_request("/v1/catalog/ensure", {"scope": "years"})

    def test_catalog_ensure_http_route_reaches_hydration_service(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        calls = []
        try:
            payload = {"scope": "years", "idempotency_key": "http-catalog-key"}
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/v1/catalog/ensure",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with patch(
                "autodata_ingestion.catalog_service.ensure_catalog_hydration",
                side_effect=lambda body: calls.append(json.loads(body))
                or {"status": "hydrated", "complete": True, "rows": []},
            ):
                with urllib.request.urlopen(request, timeout=2) as response:
                    result = json.loads(response.read())
            self.assertEqual(result["status"], "hydrated")
            self.assertEqual(calls, [payload])
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

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
