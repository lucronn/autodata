import sys
import unittest
import json
import os
import hashlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.catalog_service import (
    _ArticleCatalogProgress,
    CatalogRequest,
    CacheFirstCatalogService,
    _engine_number,
    _source_failure_detail,
    _find_source_article,
    _load_autoapitwo_article_catalog,
    _load_autoapitwo_article_detail,
    _configured_catalog_providers,
    canonical_catalog_id,
    ensure_catalog_hydration,
)


class CatalogServiceTests(unittest.TestCase):
    def test_catalog_provider_configuration_ignores_legacy_base_urls(self):
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={}), \
                patch.dict(os.environ, {
                    "AUTODATA_AUTOAPI_BASE_URL": "https://old-bankone.test",
                    "AUTODATA_AUTOAPITWO_BASE_URL": "https://old-banktwo.test",
                }, clear=True):
            self.assertEqual(_configured_catalog_providers(), ())

    def test_article_catalog_progress_throttles_durable_writes_by_count_and_time(self):
        request = {"vehicle_id": "vehicle-1", "year": 2012, "make": "Ram", "model": "Ram 1500 Ds"}
        payload = {
            "phase": "normalizing",
            "total_units": 1000,
            "current_article_id": "article",
            "current_title": "Article",
        }
        with patch("autodata_ingestion.catalog_service._update_article_catalog_progress") as update, \
                patch("autodata_ingestion.catalog_service.time.monotonic", side_effect=[0.0, 0.1, 0.1, 0.6]):
            progress = _ArticleCatalogProgress(request)
            progress.publish({**payload, "processed_units": 0}, force=True)
            progress.publish({**payload, "processed_units": 1})
            progress.publish({**payload, "processed_units": 100})
            progress.publish({**payload, "processed_units": 101})

        self.assertEqual(update.call_count, 3)
        self.assertEqual(
            [call.kwargs["processed_units"] for call in update.call_args_list],
            [0, 100, 101],
        )

    def test_source_failure_detail_names_source_and_outcome(self):
        self.assertEqual(
            _source_failure_detail('AutoAPI', RuntimeError('expired authentication token')),
            'AutoAPI failed — authentication expired or unauthorized.',
        )
        self.assertEqual(
            _source_failure_detail('AutoAPItwo', RuntimeError('server timed out')),
            'AutoAPItwo failed — server timed out.',
        )
        self.assertEqual(
            _source_failure_detail('AutoAPItwo', RuntimeError('AutoAPItwo did not resolve a matching vehicle')),
            'AutoAPItwo failed — returned no matching vehicle.',
        )
        self.assertIn("more than one", _source_failure_detail("AutoAPItwo", RuntimeError("source connector ambiguous")))

    def test_generic_banktwo_article_index_preserves_page_order_and_lineage(self):
        from autodata_ingestion.source_connector_client import SourceEnvelopeV1

        page_one = SourceEnvelopeV1(
            "request-1", "banktwo", "revision-7", "2026-10-08T12:00:00Z", "https://banktwo.test/catalog",
            {"complete": False, "next_cursor": "cursor-2", "articles": [
                {"opaque_ref": "article-2", "title": "Second", "resource_ref": "resource-2"},
            ]},
        )
        page_two = SourceEnvelopeV1(
            "request-2", "banktwo", "revision-7", "2026-10-08T12:00:01Z", "https://banktwo.test/catalog?page=2",
            {"complete": True, "articles": [
                {"opaque_ref": "article-1", "title": "First", "resource_ref": "resource-1"},
            ]},
        )

        class Connector:
            provider = "banktwo"
            base_url = "https://banktwo.test"

            def __init__(self):
                self.cursors = []

            def resolve_vehicle(self, selector):
                self.selector = selector
                return SourceEnvelopeV1(
                    "resolve-1", "banktwo", "revision-7", "2026-10-08T12:00:00Z", None,
                    {"candidates": [{"opaque_ref": "vehicle/ref-1", "label": "2.0L Sport", "confidence": 1.0}]},
                )

            def list_articles(self, source_vehicle_ref, cursor=None):
                self.cursors.append((source_vehicle_ref, cursor))
                return page_one if cursor is None else page_two

        connector = Connector()
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={"banktwo": connector}), \
                patch.dict(os.environ, {"AUTODATA_SOURCE_PERSIST": "0"}):
            records, metadata = _load_autoapitwo_article_catalog(
                {"year": 2020},
                {"model_year": 2020, "year": 2020, "make": "Example", "model": "Sedan", "region": "US", "engine": "2.0L"},
            )

        self.assertEqual(connector.selector["configuration"], "2.0L")
        self.assertEqual(connector.cursors, [("vehicle/ref-1", None), ("vehicle/ref-1", "cursor-2")])
        self.assertEqual([row["article"]["article_id"] for row in records], [
            "autoapitwo:vehicle/ref-1:article-2", "autoapitwo:vehicle/ref-1:article-1",
        ])
        self.assertEqual(metadata["index_read_count"], 2)

    def test_generic_banktwo_selected_article_reads_original_resources_and_keeps_id(self):
        from autodata_ingestion.source_bundle import SourceBundle
        from autodata_ingestion.source_connector_client import SourceEnvelopeV1
        from autodata_ingestion.source_adapters import SourceResource

        raw_article = b'{"kind":"article","article_id":"new-id","title":"Oil pump"}'
        raw_labor = b'{"operations":[{"name":"Replace oil pump"}]}'

        def resource(ref, kind, body):
            raw = raw_article if ref == "article-resource" else raw_labor
            return SourceEnvelopeV1(
                f"request-{ref}", "banktwo", "revision-9", "2026-10-08T12:00:00Z",
                f"https://banktwo.test/source/{ref}",
                {"kind": kind, "media_type": "application/json", "sha256": hashlib.sha256(raw).hexdigest()},
                resource_uri=ref, raw_resource=raw,
            )

        class Connector:
            provider = "banktwo"
            base_url = "https://banktwo.test"

            def __init__(self):
                self.reads = []

            def resolve_vehicle(self, _selector):
                return SourceEnvelopeV1(
                    "resolve-1", "banktwo", "revision-9", "2026-10-08T12:00:00Z", None,
                    {"candidates": [{"opaque_ref": "vehicle/ref-1", "label": "Exact", "confidence": 1.0}]},
                )

            def list_articles(self, _source_vehicle_ref, cursor=None):
                return SourceEnvelopeV1(
                    "list-1", "banktwo", "revision-9", "2026-10-08T12:00:00Z", None,
                    {"complete": True, "articles": [{
                        "opaque_ref": "article-1", "title": "Oil pump", "resource_ref": "article-resource",
                        "labor_resource_ref": "labor-resource",
                    }]},
                )

            def read_resource(self, ref):
                self.reads.append(ref)
                return resource(ref, "article" if ref == "article-resource" else "labor", {})

        connector = Connector()
        observed = []
        bundle = SourceBundle(
            status="complete", vehicle={"vehicle_key": "vehicle:1"}, specifications=(), models=(),
            powertrains=(), parts=(), articles=({"article_id": "new-id", "title": "Oil pump", "evidence_id": "e1"},),
            documents=(), diagrams=(), evidence=({"evidence_id": "e1"},), quarantined=(), conflicts=(),
        )
        request = {
            "year": 2013, "make": "Honda", "model": "Accord", "region": "US",
            "source_article_id": "autoapitwo:old-vehicle-ref:article-1", "title": "Oil pump",
        }
        vehicle = {"model_year": 2013, "year": 2013, "make": "Honda", "model": "Accord", "region": "US"}
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={"banktwo": connector}), \
                patch("autodata_ingestion.source_adapters.adapt_source_resource", side_effect=lambda item: observed.append(item) or item), \
                patch("autodata_ingestion.source_bundle.normalize_source_bundle", return_value=bundle), \
                patch("autodata_ingestion.procedure_normalize.normalize_procedure_article", side_effect=lambda item: dict(item)), \
                patch("autodata_ingestion.procedure_images.localize_procedure_images", side_effect=lambda item, vehicle: item), \
                patch.dict(os.environ, {"AUTODATA_SOURCE_PERSIST": "0"}):
            rows, metadata = _load_autoapitwo_article_detail(request, vehicle)

        self.assertEqual(connector.reads, ["article-resource", "labor-resource"])
        self.assertEqual([item.payload for item in observed], [raw_article, raw_labor])
        self.assertEqual([item.content_sha256 for item in observed], [hashlib.sha256(raw_article).hexdigest(), hashlib.sha256(raw_labor).hexdigest()])
        self.assertEqual([item.locator for item in observed], ["https://banktwo.test/source/article-resource", "https://banktwo.test/source/labor-resource"])
        self.assertEqual(rows[0]["article"]["article_id"], request["source_article_id"])
        self.assertEqual(metadata["content_source"], "autoapitwo")

    def test_legacy_banktwo_article_suffix_must_match_one_descriptor(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1

        class Connector:
            def list_articles(self, _vehicle_ref, _cursor=None):
                return SourceEnvelopeV1(
                    "list-1", "banktwo", "revision-1", "2026-10-08T12:00:00Z", "https://banktwo.test/articles",
                    {"complete": True, "articles": [
                        {"opaque_ref": "article:1535667", "title": "Oil pump", "resource_ref": "r1"},
                        {"opaque_ref": "other:1535667", "title": "Oil pump alternate", "resource_ref": "r2"},
                    ]},
                )

        with self.assertRaises(SourceConnectorError) as caught:
            _find_source_article(
                Connector(), "vehicle/opaque",
                {"source_article_id": "autoapitwo:52597:1535667"},
            )
        self.assertEqual(caught.exception.code, "AMBIGUOUS")

    def test_generic_vehicle_resolution_rejects_ambiguous_source_candidates(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1

        class Connector:
            def resolve_vehicle(self, _selector):
                return SourceEnvelopeV1(
                    "resolve-ambiguous", "banktwo", "revision-1", "2026-10-08T12:00:00Z", None,
                    {"candidates": [
                        {"opaque_ref": "candidate-1", "label": "Base", "confidence": 0.8},
                        {"opaque_ref": "candidate-2", "label": "Sport", "confidence": 0.8},
                    ]},
                )

        with self.assertRaises(SourceConnectorError) as caught:
            from autodata_ingestion.catalog_service import _resolve_source_vehicle_ref
            _resolve_source_vehicle_ref(Connector(), {}, {"year": 2020, "make": "Example", "model": "Sedan"})
        self.assertEqual(caught.exception.code, "AMBIGUOUS")

    def test_generic_article_search_rejects_duplicate_exact_titles(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
        from autodata_ingestion.catalog_service import _find_source_article

        class Connector:
            def search_articles(self, source_vehicle_ref, query, cursor=None):
                self.asserted = (source_vehicle_ref, query, cursor)
                return SourceEnvelopeV1(
                    "search-1", "banktwo", "revision-1", "2026-10-08T12:00:00Z", None,
                    {"complete": True, "articles": [
                        {"opaque_ref": "article-1", "title": "Oil pump"},
                        {"opaque_ref": "article-2", "title": "Oil pump"},
                    ]},
                )

        connector = Connector()
        with self.assertRaises(SourceConnectorError) as caught:
            _find_source_article(connector, "vehicle-ref", {"title": "Oil pump"})
        self.assertEqual(caught.exception.code, "AMBIGUOUS")
        self.assertEqual(connector.asserted, ("vehicle-ref", "Oil pump", None))

    def test_engine_number_prefers_displacement_in_provider_engine_label(self):
        self.assertEqual(_engine_number("L4-2.4L (K24W1)"), 2.4)
        self.assertEqual(_engine_number("V6-3.5L (J35Y2)"), 3.5)

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
