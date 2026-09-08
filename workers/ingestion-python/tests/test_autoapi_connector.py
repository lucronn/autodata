import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.autoapi_batch import execute_autoapi_batch  # noqa: E402
from autodata_ingestion.autoapi_connector import AutoAPIConnector  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.headers = {"content-type": "application/json"}
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        payload, self._payload = self._payload, b""
        return payload

    def geturl(self):
        return "http://127.0.0.1:3000"


class AutoAPIConnectorTests(unittest.TestCase):
    def test_discovers_catalog_and_fetches_every_article_as_source_resources(self):
        responses = {
            "/v1/api/years": {"header": {}, "body": [1999]},
            "/v1/api/year/1999/makes": {
                "header": {},
                "body": [{"makeId": 46, "makeName": "Chevrolet"}],
            },
            "/v1/api/year/1999/make/46/models": {
                "header": {},
                "body": [
                    {
                        "modelId": "m1",
                        "modelName": "Silverado 1500",
                        "vehicles": [{"vehicleId": "v1"}],
                    }
                ],
            },
            "/v1/api/source/GeneralMotors/vehicles?vehicleIds=v1": {
                "header": {},
                "body": [
                    {
                        "vehicleId": "v1",
                        "vehicleName": "1999 Chevrolet Silverado 1500 - 2WD",
                    }
                ],
            },
            "/v1/api/source/GeneralMotors/v1/name": {
                "header": {},
                "body": "1999 Chevrolet Silverado 1500 - 2WD",
            },
            "/v1/api/source/GeneralMotors/v1/motorvehicles": {
                "header": {},
                "body": [
                    {
                        "model": "Silverado 1500 Base",
                        "id": "m1",
                        "engines": [{"id": "e1", "name": "5.3L V8 GAS"}],
                    }
                ],
            },
            "/v1/api/source/GeneralMotors/vehicle/v1/articles/v2": {
                "header": {},
                "body": {
                    "filterTabs": [{"name": "All", "articlesCount": 2}],
                    "articleDetails": [
                        {"id": "a1", "title": "Brake procedure"},
                        {"id": "a2", "title": "Engine procedure"},
                    ]
                },
            },
            "/v1/api/source/GeneralMotors/vehicle/v1/article/a1": {
                "header": {},
                "body": {"documentId": "a1", "html": "<p>Brake</p>"},
            },
            "/v1/api/source/GeneralMotors/vehicle/v1/article/a2": {
                "header": {},
                "body": {"documentId": "a2", "html": "<p>Engine</p>"},
            },
        }
        requests = []

        def opener(request, timeout):
            parsed = urlsplit(request.full_url)
            key = parsed.path
            if parsed.query:
                key += "?" + parsed.query
            requests.append((request.get_method(), request.full_url, timeout))
            try:
                return FakeResponse(responses[key])
            except KeyError as error:
                raise AssertionError(f"unexpected AutoAPI request: {key}") from error

        connector = AutoAPIConnector(
            "http://127.0.0.1:3000",
            content_source="GeneralMotors",
            opener=opener,
            max_concurrency=2,
        )

        catalog = connector.fetch_catalog()

        self.assertEqual(catalog.years, (1999,))
        self.assertEqual(len(catalog.vehicles), 1)
        vehicle = catalog.vehicles[0]
        self.assertEqual(vehicle.vehicle_id, "v1")
        self.assertEqual(vehicle.vehicle["vehicle_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(vehicle.article_ids), 2)
        self.assertEqual(len(vehicle.resources), 5)
        self.assertEqual(vehicle.article_errors, ())
        batches = catalog.to_batches()
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].vehicle_key, "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(batches[0].source_resources), 5)
        execution = execute_autoapi_batch(
            batches,
            source_version="autoapi-http-test-v1",
            persist=False,
            selector_rows=catalog.selection_rows,
        )
        self.assertEqual(execution["vehicle_count"], 1)
        self.assertEqual(execution["results"][0]["articles"], 2)
        self.assertEqual(execution["results"][0]["article_coverage"]["unaccounted_unique_ids"], [])
        self.assertEqual(
            sorted(url for _method, url, _timeout in requests if "/article/" in url),
            [
                "http://127.0.0.1:3000/v1/api/source/GeneralMotors/vehicle/v1/article/a1",
                "http://127.0.0.1:3000/v1/api/source/GeneralMotors/vehicle/v1/article/a2",
            ],
        )

    def test_rejects_truncated_article_index(self):
        responses = {
            "/v1/api/source/GeneralMotors/v1/name": {
                "header": {},
                "body": "1999 Chevrolet Silverado 1500 - 2WD",
            },
            "/v1/api/source/GeneralMotors/v1/motorvehicles": {
                "header": {},
                "body": [],
            },
            "/v1/api/source/GeneralMotors/vehicle/v1/articles/v2": {
                "header": {},
                "body": {
                    "filterTabs": [{"name": "All", "articlesCount": 2}],
                    "articleDetails": [{"id": "a1", "title": "Only one record returned"}],
                },
            },
        }

        def opener(request, timeout):
            del timeout
            return FakeResponse(responses[urlsplit(request.full_url).path])

        connector = AutoAPIConnector("http://127.0.0.1:3000", opener=opener)

        with self.assertRaisesRegex(ValueError, "incomplete article index"):
            connector.fetch_vehicle_bundle({"vehicle_id": "v1"})

    def test_catalog_retains_successful_years_and_reports_failed_traversal_scopes(self):
        responses = {
            "/v1/api/years": {"header": {}, "body": [1999, 2000]},
            "/v1/api/year/1999/makes": {
                "header": {},
                "body": [{"makeId": 46, "makeName": "Chevrolet"}],
            },
            "/v1/api/year/2000/makes": {
                "header": {},
                "body": [{"makeId": 52, "makeName": "Ford"}],
            },
            "/v1/api/year/1999/make/46/models": {
                "header": {},
                "body": [{"id": "v1", "modelName": "Silverado 1500"}],
            },
            "/v1/api/source/GeneralMotors/vehicles?vehicleIds=v1": {
                "header": {},
                "body": [],
            },
        }

        def opener(request, timeout):
            del timeout
            parsed = urlsplit(request.full_url)
            key = parsed.path + ("?" + parsed.query if parsed.query else "")
            if key == "/v1/api/year/2000/make/52/models":
                return FakeResponse({"header": {}, "body": "unavailable"}, status=503)
            return FakeResponse(responses[key])

        connector = AutoAPIConnector("http://127.0.0.1:3000", opener=opener)

        catalog = connector.fetch_catalog()

        self.assertEqual(catalog.years, (1999, 2000))
        self.assertEqual(catalog.vehicles, ())
        self.assertEqual(len(catalog.errors), 1)
        self.assertEqual(catalog.errors[0]["scope"], "models:2000:52")


if __name__ == "__main__":
    unittest.main()
