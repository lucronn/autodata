import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.autoapi_batch import execute_autoapi_batch  # noqa: E402
from autodata_ingestion.autoapi_connector import (  # noqa: E402
    AutoAPIConnector,
    _selector_rows,
    fetch_required_source_resources,
)


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
    def test_read_through_fetches_only_requested_resources_after_article_list(self):
        responses = {
            "/v1/api/source/Motor/vehicle/v1/articles/v2": {
                "header": {},
                "body": {
                    "articleDetails": [
                        {"id": "a1", "title": "Brake line replacement"},
                        {"id": "a2", "title": "Engine replacement"},
                    ]
                },
            },
            "/v1/api/source/Motor/vehicle/v1/article/a1": {
                "header": {},
                "body": {"documentId": "a1", "html": "<p>Brake line</p>"},
            },
            "/v1/api/source/Motor/vehicle/v1/labor/a1": {
                "header": {},
                "body": {"operations": [{"operationId": "line", "hours": 1.5}]},
            },
            "/v1/api/source/Motor/vehicle/v1/parts": {
                "header": {},
                "body": [
                    {"partNumber": "P1", "partDescription": "Brake fluid", "price": "$18.99"},
                    {"partNumber": "P2", "partDescription": "Engine oil", "price": "$9.50"},
                ],
            },
        }
        requests = []

        def opener(request, timeout):
            del timeout
            path = urlsplit(request.full_url).path
            requests.append(path)
            return FakeResponse(responses[path])

        connector = AutoAPIConnector(
            "http://127.0.0.1:3000",
            content_source="Motor",
            opener=opener,
        )
        vehicle = {"vehicle_id": "v1", "vehicle_key": "toyota-rav4-2024-us"}
        operations = [{"article_id": "a1", "part_numbers": ["P1"]}]

        result = fetch_required_source_resources(vehicle, operations, connector)

        self.assertEqual(
            requests,
            [
                "/v1/api/source/Motor/vehicle/v1/articles/v2",
                "/v1/api/source/Motor/vehicle/v1/article/a1",
                "/v1/api/source/Motor/vehicle/v1/labor/a1",
                "/v1/api/source/Motor/vehicle/v1/parts",
            ],
        )
        self.assertEqual(result["requested_article_ids"], ("a1",))
        self.assertEqual([part["partNumber"] for part in result["parts"]], ["P1"])
        self.assertEqual(result["data_state"], "source_unnormalized")
        self.assertEqual(len(result["source_resources"]), 4)

        fetch_required_source_resources(vehicle, operations, connector)
        self.assertEqual(len(requests), 4)

    def test_selector_identity_uses_requested_base_model_not_provider_engine_name(self):
        rows = _selector_rows(
            {"header": {}, "body": "1997 Toyota RAV4 Base 2.0L L4 (P) 3S-FE GAS Electronic"},
            {"header": {}, "body": [{"model": "RAV4 Base", "id": "17075", "engines": [{"id": "17075:996", "name": "2.0L L4 3S-FE"}]}]},
            {"year": 1997, "make": "Toyota", "model": "RAV4", "requested_model": "RAV4"},
            default_region="US",
        )

        self.assertEqual(rows[0]["model"], "RAV4")

    def test_resolves_one_year_make_model_family_without_full_catalog_traversal(self):
        responses = {
            "/v1/api/year/1997/makes": {
                "header": {},
                "body": [{"makeId": "toyota", "makeName": "Toyota"}],
            },
            "/v1/api/year/1997/make/Toyota/models": {
                "header": {},
                "body": [
                    {
                        "modelId": "rav4",
                        "modelName": "RAV4",
                        "vehicles": [{"vehicleId": "rav4-4wd"}, {"vehicleId": "rav4-2wd"}],
                    },
                    {"modelId": "camry", "modelName": "Camry", "vehicles": [{"vehicleId": "camry-1"}]},
                ],
            },
            "/v1/api/source/Toyota/vehicles?vehicleIds=rav4-4wd%2Crav4-2wd": {
                "header": {},
                "body": [
                    {"vehicleId": "rav4-4wd", "vehicleName": "1997 Toyota RAV4 4WD"},
                    {"vehicleId": "rav4-2wd", "vehicleName": "1997 Toyota RAV4 2WD"},
                ],
            },
        }
        requests = []

        def opener(request, timeout):
            del timeout
            parsed = urlsplit(request.full_url)
            key = parsed.path
            if parsed.query:
                key += "?" + parsed.query
            requests.append(key)
            return FakeResponse(responses[key])

        connector = AutoAPIConnector(
            "http://127.0.0.1:3000",
            content_source="Toyota",
            opener=opener,
        )

        targets = connector.find_vehicle_targets(1997, "Toyota", "RAV4")

        self.assertEqual(
            [target["vehicle_id"] for target in targets],
            ["rav4-2wd", "rav4-4wd"],
        )
        self.assertNotIn("/v1/api/years", requests)

    def test_fetches_only_one_requested_article_body_and_labor_resource(self):
        responses = {
            "/v1/api/source/GeneralMotors/vehicle/v1/article/a1": {
                "header": {}, "body": {"documentId": "a1", "html": "<h2>Alternator</h2>"}
            },
            "/v1/api/source/GeneralMotors/vehicle/v1/labor/a1": {
                "header": {}, "body": {"operations": [{"operationId": "remove", "hours": 1.5}]}
            },
        }
        requests = []

        def opener(request, timeout):
            del timeout
            path = urlsplit(request.full_url).path
            requests.append(path)
            return FakeResponse(responses[path])

        connector = AutoAPIConnector("http://127.0.0.1:3000", opener=opener)

        resources = connector.fetch_article_resources("v1", "a1")

        self.assertEqual(len(resources), 2)
        self.assertEqual(requests, [
            "/v1/api/source/GeneralMotors/vehicle/v1/article/a1",
            "/v1/api/source/GeneralMotors/vehicle/v1/labor/a1",
        ])

    def test_fetches_labor_by_separate_provider_id_and_targets_procedure(self):
        responses = {
            "/v1/api/source/Motor/vehicle/v1/article/P%3A1": {
                "header": {}, "body": {"documentId": "P:1", "html": "<h2>Water pump</h2>"}
            },
            "/v1/api/source/Motor/vehicle/v1/labor/L%3A2": {
                "header": {}, "body": {"operations": [{"operationId": "pump", "hours": 2.0}]}
            },
        }
        requests = []

        def opener(request, timeout):
            del timeout
            path = urlsplit(request.full_url).path
            requests.append(path)
            return FakeResponse(responses[path])

        connector = AutoAPIConnector("http://127.0.0.1:3000", content_source="Motor", opener=opener)

        resources = connector.fetch_article_resources("v1", "P:1", labor_article_id="L:2")

        self.assertEqual(requests, [
            "/v1/api/source/Motor/vehicle/v1/article/P%3A1",
            "/v1/api/source/Motor/vehicle/v1/labor/L%3A2",
        ])
        self.assertEqual(resources[1].metadata["target_article_id"], "P:1")

    def test_discovers_catalog_and_fetches_every_article_as_source_resources(self):
        responses = {
            "/v1/api/years": {"header": {}, "body": [1999]},
            "/v1/api/year/1999/makes": {
                "header": {},
                "body": [{"makeId": 46, "makeName": "Chevrolet"}],
            },
            "/v1/api/year/1999/make/Chevrolet/models": {
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
            vehicle_max_concurrency=2,
        )

        catalog = connector.fetch_catalog()

        self.assertEqual(catalog.years, (1999,))
        self.assertEqual(len(catalog.vehicles), 1)
        vehicle = catalog.vehicles[0]
        self.assertEqual(vehicle.vehicle_id, "v1")
        self.assertEqual(vehicle.vehicle["vehicle_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(vehicle.article_ids), 2)
        self.assertEqual(len(vehicle.resources), 3)
        batches = catalog.to_batches()
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].vehicle_key, "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(batches[0].source_resources), 3)
        execution = execute_autoapi_batch(
            batches,
            source_version="autoapi-http-test-v1",
            persist=False,
            selector_rows=catalog.selection_rows,
        )
        self.assertEqual(execution["vehicle_count"], 1)
        self.assertEqual(execution["results"][0]["articles"], 2)
        self.assertEqual(execution["results"][0]["article_coverage"]["unaccounted_unique_ids"], [])
        self.assertFalse(any("/article/" in url for _method, url, _timeout in requests))

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

    def test_retries_transient_http_status_without_sleeping_in_test_mode(self):
        attempts = []

        def opener(request, timeout):
            del request, timeout
            attempts.append(True)
            if len(attempts) == 1:
                return FakeResponse({"header": {}, "body": "temporarily unavailable"}, status=502)
            return FakeResponse({"header": {}, "body": [1999]})

        connector = AutoAPIConnector(
            "http://127.0.0.1:3000",
            opener=opener,
            retry_attempts=2,
            retry_backoff_seconds=0,
        )

        payload, _resource = connector._get_json("/v1/api/years")

        self.assertEqual(payload["body"], [1999])
        self.assertEqual(len(attempts), 2)

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
            "/v1/api/year/1999/make/Chevrolet/models": {
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
        self.assertEqual(catalog.errors[0]["scope"], "models:2000:Ford")


if __name__ == "__main__":
    unittest.main()
