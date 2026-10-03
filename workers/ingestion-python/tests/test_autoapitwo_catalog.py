import io
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote
import hashlib


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.autoapitwo_catalog import AutoAPITwoCatalogConnector  # noqa: E402


class AutoAPITwoCatalogTests(unittest.TestCase):
    def test_catalog_adapter_uses_autodbtwo_and_preserves_upstream_response_bytes(self):
        payload = b'[{"year":"2012"}]'
        source_uri = "https://autoapitwo.test/api/v1/fleet/years"
        calls = []

        class Response(io.BytesIO):
            status = 200
            headers = {
                "Content-Type": "application/json",
                "X-Source-Uri": source_uri,
                "X-Content-Sha256": hashlib.sha256(payload).hexdigest(),
            }

            def geturl(self):
                return calls[-1]

        def opener(request, **_kwargs):
            calls.append(request.full_url)
            return Response(payload)

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test",
            connector_url="http://127.0.0.1:3001",
            opener=opener,
        )
        rows, resources = connector.fetch_rows_with_provenance()

        self.assertEqual(rows, [])
        self.assertEqual(resources[0].source_uri, source_uri)
        self.assertEqual(resources[0].payload, payload)
        self.assertIn("/v1/fleet/resource?path=", calls[0])

    def test_catalog_resources_retain_raw_response_provenance(self):
        payloads = {
            "/api/v1/fleet/years": [{"year": "1999"}],
            "/api/v1/fleet/years/1999/makes": [],
        }

        def opener(request, **_kwargs):
            path = unquote(request.full_url.split("https://autoapitwo.test", 1)[1].split("?", 1)[0])
            return io.BytesIO(json.dumps(payloads[path]).encode("utf-8"))

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )
        rows, resources = connector.fetch_rows_with_provenance()

        self.assertEqual(rows, [])
        self.assertEqual([resource.source_uri for resource in resources], [
            "https://autoapitwo.test/api/v1/fleet/years",
            "https://autoapitwo.test/api/v1/fleet/years/1999/makes",
        ])
        self.assertEqual(json.loads(resources[0].payload), payloads["/api/v1/fleet/years"])
        self.assertEqual(resources[0].metadata["provider"], "autoapitwo")

    def test_fetch_years_returns_sorted_valid_provider_years(self):
        def opener(request, **_kwargs):
            self.assertTrue(request.full_url.endswith("/api/v1/fleet/years"))
            return io.BytesIO(json.dumps([
                {"year": "2027"}, {"year": "1966"}, {"year": "2027"}, {"year": "not-a-year"}
            ]).encode("utf-8"))

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )

        self.assertEqual(connector.fetch_years(), ["1966", "2027"])

    def test_traverses_vocabulary_and_emits_engine_identity_rows_without_content_calls(self):
        payloads = {
            "/api/v1/fleet/years": [{"year": "1999"}],
            "/api/v1/fleet/years/1999/makes": [{"make": "Toyota"}],
            "/api/v1/fleet/years/1999/makes/Toyota/models": [{"model": "Avalon XL"}],
            "/api/v1/fleet/years/1999/makes/Toyota/models/Avalon%20XL/engines": [
                {
                    "engine": "V6-3.0L (1MZ-FE)",
                    "_embedded": {"carId": "33496"},
                    "_links": {"car": {"href": "/api/v1/fleet/carids/33496"}},
                }
            ],
            "/api/v1/fleet/carids/33496": {
                "id": "33496",
                "year": "1999",
                "make": "Toyota",
                "model": "Avalon XL",
                "engine": "V6-3.0L (1MZ-FE)",
                "acesVehicleNames": ["19868: 1999 Toyota Avalon XL USA"],
                "acesEngineConfigNames": ["3968: V6-3.0L 2995cc DOHC MFI (1MZ-FE)"],
            },
        }
        calls = []

        def opener(request, **_kwargs):
            path = request.full_url.split("https://autoapitwo.test", 1)[1].split("?", 1)[0]
            calls.append(path)
            if path not in payloads:
                raise AssertionError(f"unexpected upstream path: {path}")
            return io.BytesIO(json.dumps(payloads[path]).encode("utf-8"))

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )
        rows = connector.fetch_rows()

        self.assertEqual(rows, [
            {
                "year": 1999,
                "make": "Toyota",
                "model": "Avalon XL",
                "engine": 3.0,
                "engine_label": "V6-3.0L (1MZ-FE)",
                "region": "US",
                "autoapitwo_vehicle_id": "33496",
                "provider_mappings": [
                    {
                        "provider": "autoapitwo",
                        "entity_type": "aces_engine",
                        "provider_id": "3968",
                    },
                    {
                        "provider": "autoapitwo",
                        "entity_type": "aces_vehicle",
                        "provider_id": "19868",
                    },
                    {
                        "provider": "autoapitwo",
                        "entity_type": "car",
                        "provider_id": "33496",
                    },
                ],
                "source_locator": "/api/v1/fleet/carids/33496",
            }
        ])
        self.assertTrue(calls)
        self.assertTrue(all("/content/" not in path for path in calls))

    def test_repeated_catalog_reads_use_connector_cache(self):
        payloads = {
            "/api/v1/fleet/years": [{"year": "1999"}],
            "/api/v1/fleet/years/1999/makes": [],
        }
        calls = []

        def opener(request, **_kwargs):
            path = unquote(request.full_url.split("https://autoapitwo.test", 1)[1].split("?", 1)[0])
            calls.append(path)
            return io.BytesIO(json.dumps(payloads[path]).encode("utf-8"))

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )
        connector.fetch_rows()
        connector.fetch_rows()

        self.assertEqual(calls.count("/api/v1/fleet/years"), 1)
        self.assertEqual(calls.count("/api/v1/fleet/years/1999/makes"), 1)

    def test_iter_rows_yields_rows_incrementally(self):
        payloads = {
            "/api/v1/fleet/years": [{"year": "1999"}],
            "/api/v1/fleet/years/1999/makes": [{"make": "Toyota"}],
            "/api/v1/fleet/years/1999/makes/Toyota/models": [{"model": "Avalon XL"}],
            "/api/v1/fleet/years/1999/makes/Toyota/models/Avalon XL/engines": [
                {"engine": "V6-3.0L", "_embedded": {"carId": "33496"}}
            ],
            "/api/v1/fleet/carids/33496": {
                "id": "33496", "year": "1999", "make": "Toyota",
                "model": "Avalon XL", "engine": "V6-3.0L",
            },
        }

        def opener(request, **_kwargs):
            path = unquote(request.full_url.split("https://autoapitwo.test", 1)[1].split("?", 1)[0])
            return io.BytesIO(json.dumps(payloads[path]).encode("utf-8"))

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )
        self.assertEqual(len(list(connector.iter_rows())), 1)

    def test_preserves_engine_labels_that_have_no_numeric_displacement(self):
        from autodata_ingestion.autoapitwo_catalog import _row

        row = _row(
            "2024", "Tesla", "Model 3", "Electric",
            {"year": "2024", "make": "Tesla", "model": "Model 3", "engine": "Electric"},
            "/api/v1/fleet/carids/1",
        )

        self.assertIsNone(row["engine"])
        self.assertEqual(row["engine_label"], "Electric")

    def test_scoped_models_read_only_selected_year_and_make_vocabulary(self):
        payloads = {
            "/api/v1/fleet/years/1999/makes": [{"make": "Chevy Truck"}, {"make": "Toyota"}],
            "/api/v1/fleet/years/1999/makes/Chevy Truck/models": [{"model": "C 1500 Truck 2WD"}],
            "/api/v1/fleet/years/1999/makes/Toyota/models": [{"model": "Camry"}],
        }

        def opener(request, **_kwargs):
            path = unquote(request.full_url.split("https://autoapitwo.test", 1)[1].split("?", 1)[0])
            if path not in payloads:
                raise AssertionError(f"unexpected upstream path: {path}")
            return io.BytesIO(json.dumps(payloads[path]).encode("utf-8"))

        from autodata_ingestion.catalog_service import CatalogRequest

        connector = AutoAPITwoCatalogConnector(
            "https://autoapitwo.test", opener=opener, retry_delay=0
        )
        result = connector.fetch_catalog_scope(
            CatalogRequest(1999, "unknown", "unknown", scope="makes")
        )

        self.assertTrue(result["complete"])
        self.assertEqual(
            {(row["make"], row["model"]) for row in result["rows"]},
            {("Chevy Truck", "C 1500 Truck 2WD"), ("Toyota", "Camry")},
        )


if __name__ == "__main__":
    unittest.main()
