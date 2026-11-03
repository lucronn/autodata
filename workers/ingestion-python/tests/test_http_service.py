import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.http_service import dispatch_request  # noqa: E402


class HTTPServiceTests(unittest.TestCase):
    def test_dispatch_rejects_retired_chat_paths(self):
        with self.assertRaisesRegex(ValueError, "unknown ingestion service route"):
            dispatch_request("/v1/chat/queries", {"message": "legacy request"})

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

    def test_catalog_ensure_dispatches_years_to_year_manifest(self):
        calls = []

        def catalog_years_runner(serialized_request):
            calls.append(json.loads(serialized_request))
            return {"status": "scheduled", "scope": "years"}

        result = dispatch_request(
            "/v1/catalog/ensure",
            {"scope": "years", "idempotency_key": "catalog-hydration:years"},
            catalog_years_runner=catalog_years_runner,
        )

        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(calls[0]["scope"], "years")

    def test_catalog_ensure_dispatches_scoped_hydration(self):
        calls = []

        def catalog_runner(serialized_request):
            calls.append(json.loads(serialized_request))
            return {"status": "hydrated", "scope": "makes"}

        result = dispatch_request(
            "/v1/catalog/ensure",
            {"scope": "makes", "year": 2020, "idempotency_key": "catalog-hydration:makes"},
            catalog_runner=catalog_runner,
        )

        self.assertEqual(result["status"], "hydrated")
        self.assertEqual(calls[0]["year"], 2020)

    def test_catalog_ensure_requires_key_and_known_scope(self):
        with self.assertRaises(ValueError):
            dispatch_request("/v1/catalog/ensure", {"scope": "years"})
        with self.assertRaises(ValueError):
            dispatch_request(
                "/v1/catalog/ensure",
                {"scope": "unknown", "idempotency_key": "catalog-hydration:x"},
            )

    def test_dispatch_rejects_unknown_routes_and_invalid_shapes(self):
        with self.assertRaises(ValueError):
            dispatch_request("/v1/unknown", {})
        with self.assertRaises(ValueError):
            dispatch_request("/v1/article-intakes", {"source_uri": "https://source.example/article"})
        with self.assertRaises(ValueError):
            dispatch_request("/v1/job-plans", {"vehicle": {}, "query": "starter"})


if __name__ == "__main__":
    unittest.main()


from lifecycle_support import runtime,fresh_database


def test_actual_http_article_ensure_only_commits_job_within_two_seconds(runtime,monkeypatch):
    from autodata_ingestion.http_service import make_handler
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request,urlopen
    import time
    monkeypatch.setattr("autodata_ingestion.worker.ArticleRepository",lambda:runtime.repo)
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler("fixture-internal"))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f"http://127.0.0.1:{server.server_port}/v1/catalog/ensure",data=json.dumps({"scope":"article","vehicle_id":str(runtime.vehicle),"canonical_article_id":str(runtime.article_id),"idempotency_key":"fixture"}).encode(),headers={"Content-Type":"application/json","X-Autodata-Internal-Token":"fixture-internal"},method="POST")
        started=time.monotonic()
        with urlopen(request,timeout=2) as response:
            assert response.status==202
            body=json.load(response)
        assert time.monotonic()-started<2
        assert body["state"]=="queued" and body["job_id"]==str(runtime.current_job_id())
        assert runtime.counters()=={"source":0,"asset":0,"model":0,"schedule":1}
        runtime.start_workers(2);revision=runtime.await_publication();runtime.stop_workers();runtime.reset_counters()
        with urlopen(request,timeout=2) as response:
            assert response.status==200 and json.load(response)["state"]=="completed"
        assert runtime.counters()=={"source":0,"asset":0,"model":0,"schedule":0}
        assert runtime.read_current()["canonical_revision_id"]==revision
    finally:server.shutdown();server.server_close();thread.join()


def test_actual_http_scheduling_dependency_failure_is_503(runtime,monkeypatch):
    from autodata_ingestion.http_service import make_handler
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    import pytest
    class Unavailable:
        def connect(self):raise OSError("fixture database unavailable")
    monkeypatch.setattr("autodata_ingestion.worker.ArticleRepository",Unavailable)
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler("fixture-internal"));thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f"http://127.0.0.1:{server.server_port}/v1/catalog/ensure",data=json.dumps({"scope":"article","vehicle_id":str(runtime.vehicle),"canonical_article_id":str(runtime.article_id),"idempotency_key":"fixture"}).encode(),headers={"X-Autodata-Internal-Token":"fixture-internal"},method="POST")
        with pytest.raises(HTTPError) as error:urlopen(request,timeout=2)
        assert error.value.code==503
        assert runtime.counters()["schedule"]==0
    finally:server.shutdown();server.server_close();thread.join()
