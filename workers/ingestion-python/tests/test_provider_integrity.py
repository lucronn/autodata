import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.catalog_service import (  # noqa: E402
    CacheFirstCatalogService,
    CatalogRequest,
    _configured_catalog_providers,
    _load_autoapitwo_article_detail,
    ensure_catalog_hydration,
)
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402
from autodata_ingestion.worker import _load_autoapi_job_catalog  # noqa: E402


class ProviderIntegrityTests(unittest.TestCase):
    def test_autoapi_protection_bypass_is_loaded_as_a_worker_header(self):
        from autodata_ingestion.autoapi_connector import configured_source_request_headers

        with patch.dict(
            os.environ,
            {
                "AUTODATA_AUTOAPI_VERCEL_PROTECTION_BYPASS": "synthetic-vercel-bypass",
                "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": "{}",
            },
            clear=False,
        ):
            headers = configured_source_request_headers("https://autodbone-curtt.vercel.app")

        self.assertEqual(
            headers,
            {"x-vercel-protection-bypass": "synthetic-vercel-bypass"},
        )

        with patch.dict(
            os.environ,
            {"AUTODATA_AUTOAPI_VERCEL_PROTECTION_BYPASS": "synthetic-vercel-bypass"},
            clear=False,
        ):
            self.assertNotIn(
                "x-vercel-protection-bypass",
                configured_source_request_headers("https://untrusted.example"),
            )

    def test_same_raw_article_id_from_two_providers_keeps_two_qualified_articles(self):
        payloads = (
            ("autodbone", "AutoDBone procedure", "Remove the alternator."),
            ("autodbtwo", "AutoDBtwo procedure", "Install the alternator."),
        )
        artifacts = []
        for provider, title, body in payloads:
            resource = SourceResource.from_bytes(
                f"https://{provider}.example/article/42",
                "provider-v1",
                json.dumps(
                    {
                        "body": {
                            "articleDetails": [
                                {"id": "42", "title": title, "body": body}
                            ]
                        }
                    }
                ).encode(),
                "application/json",
                metadata={"provider": provider},
            )
            artifacts.append(adapt_source_resource(resource))

        bundle = normalize_source_bundle(artifacts, "US")

        self.assertEqual(
            {article["article_id"] for article in bundle.articles},
            {"autodbone:42", "autodbtwo:42"},
        )
        self.assertEqual(
            {article["provider_article_id"] for article in bundle.articles},
            {"42"},
        )
        self.assertEqual({article["provider"] for article in bundle.articles}, {"autodbone", "autodbtwo"})
        self.assertEqual(
            {evidence["content_sha256"] for evidence in bundle.evidence},
            {artifact.content_sha256 for artifact in artifacts},
        )
        self.assertTrue(all(evidence["source_version"] == "provider-v1" for evidence in bundle.evidence))
        self.assertTrue(all(evidence["artifact_key"].startswith("sources/") for evidence in bundle.evidence))

    def test_provider_failure_cannot_be_reported_as_complete_catalog(self):
        class AutoDBone:
            name = "autodbone"

            def fetch_catalog(self, _request):
                return {
                    "complete": True,
                    "rows": [{"year": 2024, "make": "Honda", "model": "Pilot", "region": "US"}],
                    "provenance": [{"provider": "autodbone", "content_sha256": "a" * 64}],
                }

        class AutoDBtwo:
            name = "autodbtwo"

            def fetch_catalog(self, _request):
                raise RuntimeError("403 bearer=should-not-escape")

        result = CacheFirstCatalogService(
            cache_reader=lambda _request: {"complete": False, "rows": []},
            providers=[AutoDBone(), AutoDBtwo()],
        ).resolve(CatalogRequest(2024, "Honda", "Pilot"))

        self.assertFalse(result.complete)
        self.assertIn("provider", result.missing_scopes)
        self.assertEqual(result.provider_failures[0]["provider"], "autodbtwo")
        self.assertEqual(result.provider_failures[0]["reason"], "source access denied")
        self.assertNotIn("bearer", json.dumps(result.provider_failures))

    def test_catalog_autodbone_factory_receives_approved_headers_without_logging_them(self):
        with patch.dict(
            os.environ,
            {
                "AUTODATA_AUTOAPI_BASE_URL": "https://autodbone.example",
                "AUTODATA_AUTOAPITWO_BASE_URL": "",
                "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": '{"X-Approved-Source":"opaque-test-value"}',
            },
            clear=False,
        ), patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            providers = _configured_catalog_providers()

        self.assertEqual(len(providers), 1)
        self.assertEqual(
            connector_class.call_args.kwargs["request_headers"],
            {"X-Approved-Source": "opaque-test-value"},
        )

    def test_worker_autodbone_factory_receives_approved_headers(self):
        vehicle = {
            "year": 2013,
            "make": "Honda",
            "model": "Pilot",
            "region": "US",
        }
        with patch.dict(
            os.environ,
            {
                "AUTODATA_AUTOAPI_BASE_URL": "https://autodbone.example",
                "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": '{"X-Approved-Source":"opaque-test-value"}',
            },
            clear=False,
        ), patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector_class.return_value.find_vehicle_targets.return_value = []
            _load_autoapi_job_catalog(vehicle, object(), query="alternator")

        self.assertEqual(
            connector_class.call_args.kwargs["request_headers"],
            {"X-Approved-Source": "opaque-test-value"},
        )

    def test_worker_does_not_send_autodbtwo_article_id_to_autodbone(self):
        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle

        vehicle = {
            "year": 2013,
            "make": "Honda",
            "model": "Crosstour 2wd",
            "region": "US",
            "requested_article_id": "autoapitwo:52992:water-pump-1",
        }
        resource = SourceResource.from_bytes(
            "https://autodbone.example/article/autodbone-water-pump-index",
            "provider-v1",
            json.dumps(
                {
                    "body": {
                        "vehicle": {"year": 2013, "make": "Honda", "model": "Crosstour 2wd"},
                        "articleDetails": [
                            {
                                "id": "autodbone-water-pump-index",
                                "title": "Water Pump Replacement",
                                "body": "Remove the pump.",
                            }
                        ]
                    }
                }
            ).encode(),
            "application/json",
            metadata={"provider": "autodbone"},
        )
        bundle = AutoAPIVehicleBundle(
            vehicle_id="autodbone-vehicle-1",
            content_source="Motor",
            vehicle={**vehicle, "vehicle_key": "honda-crosstour-2013"},
            configurations=(),
            resources=(resource,),
            article_ids=("autodbone-water-pump-index",),
        )

        with patch.dict(
            os.environ,
            {"AUTODATA_AUTOAPI_BASE_URL": "https://autodbone.example"},
            clear=False,
        ), patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector_class.return_value.find_vehicle_targets.return_value = [
                {"vehicle_id": "autodbone-vehicle-1"}
            ]
            connector_class.return_value.fetch_vehicle_bundle.return_value = bundle
            _records, source_info = _load_autoapi_job_catalog(vehicle, object(), query="water pump")

        requested_ids = [
            call.args[1]
            for call in connector_class.return_value.fetch_article_resources.call_args_list
        ]
        self.assertNotIn("autoapitwo:52992:water-pump-1", requested_ids)
        self.assertEqual(
            source_info["provider_id_rejections"],
            [
                {
                    "article_id": "autoapitwo:52992:water-pump-1",
                    "provider": "autoapitwo",
                    "reason": "article belongs to AutoDBtwo",
                }
            ],
        )

    def test_autodbtwo_detail_loader_rejects_an_autodbone_article_id(self):
        with patch("autodata_ingestion.autoapitwo_connector.AutoAPITwoConnector") as connector_class:
            with self.assertRaisesRegex(ValueError, "belongs to AutoDBone"):
                _load_autoapitwo_article_detail(
                    {"source_article_id": "autodbone:42", "title": "Alternator"},
                    {"make": "Honda", "model": "Pilot", "year": 2024, "region": "US"},
                )

        connector_class.assert_not_called()

    def test_selected_article_with_empty_instructions_is_not_complete(self):
        request = json.dumps(
            {
                "scope": "article",
                "idempotency_key": "provider-integrity-empty-instructions-1",
                "vehicle_id": "vehicle-ram-1",
                "year": 2012,
                "make": "Ram",
                "model": "Ram 1500 DS",
                "region": "US",
                "source_article_id": "autodbone:water-pump-1",
                "title": "Water Pump Replacement",
            }
        )
        empty_article = {
            "article_id": "autodbone:water-pump-1",
            "title": "Water Pump Replacement",
            "content_status": "content_complete",
            "steps": [{"action": "REMOVAL", "instructions": []}],
        }
        with patch(
            "autodata_ingestion.catalog_service._load_stored_article_for_repair",
            return_value=None,
        ), patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            return_value=([{"article": empty_article}], {"mode": "autoapi_fallback"}),
        ), patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            side_effect=RuntimeError("no readable source instructions"),
        ):
            result = ensure_catalog_hydration(request)

        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_scopes"], ["article"])
        self.assertEqual(result["status"], "source_unavailable")
        self.assertEqual(
            [failure["provider"] for failure in result["metadata"]["provider_failures"]],
            ["autodbone", "autodbtwo"],
        )


if __name__ == "__main__":
    unittest.main()
