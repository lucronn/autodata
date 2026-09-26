import sys
import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.catalog_service import (
    CatalogRequest,
    CacheFirstCatalogService,
    _autoapitwo_car_ids,
    _engine_number,
    canonical_catalog_id,
    ensure_catalog_hydration,
)


class CatalogServiceTests(unittest.TestCase):
    def test_engine_number_prefers_displacement_in_provider_engine_label(self):
        self.assertEqual(_engine_number("L4-2.4L (K24W1)"), 2.4)
        self.assertEqual(_engine_number("V6-3.5L (J35Y2)"), 3.5)

    def test_autoapitwo_id_only_mapping_is_enriched_before_engine_filtering(self):
        class Connector:
            def search_vehicles(self, query):
                return [
                    {"id": "52597", "year": "2013", "make": "Honda", "model": "Accord Coupe", "engine": "L4-2.4L (K24W1)"},
                    {"id": "52599", "year": "2013", "make": "Honda", "model": "Accord Coupe", "engine": "V6-3.5L (J35Y2)"},
                ]

        vehicle = {"model_year": 2013, "make": "Honda", "model": "Accord Coupe", "engine": "2.4"}
        self.assertEqual(
            _autoapitwo_car_ids(
                {"vehicle_id": "vehicle-1"},
                vehicle,
                Connector(),
            ),
            ("52597",),
        )

    def test_complete_cache_is_returned_without_calling_provider(self):
        provider_calls = []
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {
                "complete": True,
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
                "provenance": [{"provider": "autoapi", "uri": "db://cached"}],
            },
            providers=[lambda _request: provider_calls.append(True)],
        )

        result = service.resolve(CatalogRequest(2024, "Toyota", "RAV4"))

        self.assertTrue(result.cache_hit)
        self.assertTrue(result.complete)
        self.assertEqual(provider_calls, [])
        self.assertEqual(result.rows[0]["catalog_id"], canonical_catalog_id(result.rows[0]))

    def test_incomplete_cache_hydrates_and_merges_provider_rows_and_provenance(self):
        provider_calls = []

        def autoapi(_request):
            provider_calls.append("autoapi")
            return {
                "complete": False,
                "missing_scopes": ["engine"],
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
                "provenance": [{"provider": "autoapi", "uri": "https://autoapi.test/a", "hash": "a"}],
            }

        def autoapitwo(_request):
            provider_calls.append("autoapitwo")
            return {
                "complete": True,
                "rows": [{
                    "year": 2024, "make": "Toyota", "model": "RAV4", "region": "US",
                    "engine": 2.5, "trim": "XLE",
                }],
                "provenance": [{"provider": "autoapitwo", "uri": "https://autoapitwo.test/b", "hash": "b"}],
            }

        written = []
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {"complete": False, "rows": [], "missing_scopes": ["model"]},
            providers=[autoapi, autoapitwo],
            cache_writer=written.append,
        )

        result = service.resolve(CatalogRequest(2024, "Toyota", "RAV4"))

        self.assertEqual(provider_calls, ["autoapi", "autoapitwo"])
        self.assertTrue(result.complete)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual({item["provider"] for item in result.provenance}, {"autoapi", "autoapitwo"})
        self.assertEqual(written[0], result)
        self.assertTrue(all("provider" not in row.get("raw", {}) for row in result.rows))

    def test_http_hydration_replays_the_same_idempotent_result(self):
        request = json.dumps({
            "scope": "models",
            "idempotency_key": "catalog-http-replay-1",
            "year": 2024,
            "make": "Toyota",
            "model": "RAV4",
        })

        first = ensure_catalog_hydration(request)
        second = ensure_catalog_hydration(request)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(first["missing_scopes"], ["models"])

    def test_http_hydration_complete_cache_is_provider_free(self):
        result = ensure_catalog_hydration(json.dumps({
            "scope": "configurations",
            "idempotency_key": "catalog-http-cache-1",
            "cache": {
                "complete": True,
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
            },
        }))

        self.assertEqual(result["status"], "cache_hit")
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["rows"]), 1)

    def test_article_scope_uses_targeted_index_loader_with_empty_query(self):
        calls = []

        def load_catalog(vehicle, target, *, query):
            calls.append((vehicle, target, query))
            return (
                [{"article": {"article_id": "a1", "title": "Oil pump replacement"}}],
                {"traversal": "vehicle_bundle", "targeted_article_fetch_count": 0},
            )

        request = json.dumps({
            "scope": "articles",
            "idempotency_key": "catalog-http-articles-index-1",
            "year": 1999,
            "make": "Toyota Truck",
            "model": "4 Runner 4wd",
            "region": "US",
            "trim": "SR5",
            "engine": "2.7",
        })
        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertTrue(result["complete"])
        self.assertEqual(result["metadata"]["targeted_article_fetch_count"], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "")

    def test_article_scope_falls_back_to_autoapitwo_when_autoapi_fails(self):
        primary_calls = []
        fallback_calls = []

        def load_catalog(vehicle, target, *, query):
            primary_calls.append(query)
            raise RuntimeError("AutoAPI vehicle lookup failed")

        def load_autoapitwo(request, vehicle):
            fallback_calls.append((request["make"], vehicle["model"]))
            return (
                [{"article": {"article_id": "autoapitwo:52597:1535667", "title": "Oil Pump"}}],
                {"mode": "autoapitwo_article_index", "targeted_article_fetch_count": 0},
            )

        request = json.dumps({
            "scope": "articles",
            "idempotency_key": "catalog-http-articles-autoapitwo-fallback-1",
            "vehicle_id": "vehicle-1",
            "year": 2013,
            "make": "Honda",
            "model": "Accord Coupe",
            "region": "US",
            "engine": "2.4",
        })
        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog), \
                patch("autodata_ingestion.catalog_service._load_autoapitwo_article_catalog", load_autoapitwo):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertTrue(result["complete"])
        self.assertEqual(result["metadata"]["mode"], "autoapitwo_article_index")
        self.assertEqual(primary_calls, [""])
        self.assertEqual(fallback_calls, [("Honda", "Accord Coupe")])

    def test_selected_article_scope_falls_back_to_autoapitwo(self):
        request = json.dumps({
            "scope": "article",
            "idempotency_key": "catalog-http-article-autoapitwo-fallback-1",
            "vehicle_id": "vehicle-1",
            "year": 2013,
            "make": "Honda",
            "model": "Accord Coupe",
            "region": "US",
            "engine": "2.4",
            "source_article_id": "autoapitwo:52597:1535667",
            "title": "Oil Pump",
        })

        def load_catalog(vehicle, target, *, query):
            raise RuntimeError("AutoAPI vehicle lookup failed")

        def load_detail(request, vehicle):
            return ([{"article": {"article_id": "autoapitwo:52597:1535667", "title": "Oil Pump"}}], {"mode": "autoapitwo_article_detail"})

        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog), \
                patch("autodata_ingestion.catalog_service._load_autoapitwo_article_detail", load_detail):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertEqual(result["metadata"]["mode"], "autoapitwo_article_detail")
        self.assertEqual(result["rows"][0]["article"]["article_id"], "autoapitwo:52597:1535667")

    def test_article_scope_does_not_fall_back_to_full_provider_snapshot(self):
        class SnapshotOnlyProvider:
            def __init__(self):
                self.calls = []

            def fetch_catalog_snapshot(self):
                self.calls.append("snapshot")
                raise AssertionError("article scope must not call a full snapshot")

            def fetch_catalog(self):
                self.calls.append("catalog")
                raise AssertionError("article scope must not call full catalog")

        provider = SnapshotOnlyProvider()
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {"complete": False, "rows": []},
            providers=[provider],
        )

        result = service.resolve(
            CatalogRequest(1999, "Toyota Truck", "4 Runner 4wd", scope="articles")
        )

        self.assertFalse(result.complete)
        self.assertEqual(provider.calls, [])
        self.assertEqual(result.missing_scopes, ("provider",))


if __name__ == "__main__":
    unittest.main()
