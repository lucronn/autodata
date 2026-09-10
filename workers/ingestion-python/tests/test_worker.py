import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.worker import run_once  # noqa: E402
from autodata_ingestion.source_adapters import SourceResource  # noqa: E402


class IngestionWorkerTests(unittest.TestCase):
    def test_autoapi_query_fallback_hydrates_only_selected_articles_and_labor(self):
        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle
        from autodata_ingestion.worker import _load_autoapi_job_catalog

        def resource(uri, payload):
            return SourceResource.from_bytes(uri, "autoapi-test-v1", json.dumps(payload).encode(), "application/json")

        vehicle = {
            "vehicle_id": "v1",
            "autoapi_vehicle_id": "v1",
            "vehicle_key": "chevrolet-silverado-1500-1999-us",
            "year": 1999,
            "make": "Chevrolet",
            "model": "Silverado 1500",
            "region": "US",
        }
        bundle = AutoAPIVehicleBundle(
            vehicle_id="v1",
            content_source="GeneralMotors",
            vehicle=vehicle,
            configurations=(),
            resources=(
                resource("http://source/name", {"body": "1999 Chevrolet Silverado 1500"}),
                resource("http://source/motorvehicles", {"body": [{"id": "m1", "model": "Silverado 1500", "engines": []}]}),
                resource(
                    "http://source/articles/v2",
                    {"body": {"articleDetails": [
                        {"id": "alt-1", "title": "Alternator replacement"},
                        {"id": "starter-1", "title": "Starter replacement"},
                        {"id": "brake-1", "title": "Brake replacement"},
                    ]}},
                ),
            ),
            article_ids=("alt-1", "starter-1", "brake-1"),
        )
        details = {
            "alt-1": (
                resource("http://source/article/alt-1", {"body": {"documentId": "alt-1", "html": "Replace the alternator."}}),
                resource("http://source/labor/alt-1", {"body": {"operations": [{"operationId": "shared-belt", "name": "Remove belt", "hours": 0.25}, {"operationId": "alternator", "name": "Replace alternator", "hours": 1.5}]}}),
            ),
            "starter-1": (
                resource("http://source/article/starter-1", {"body": {"documentId": "starter-1", "html": "Replace the starter."}}),
                resource("http://source/labor/starter-1", {"body": {"operations": [{"operationId": "shared-belt", "name": "Remove belt", "hours": 0.25}, {"operationId": "starter", "name": "Replace starter", "hours": 2.0}]}}),
            ),
        }
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.fetch_vehicle_bundle.return_value = bundle
            connector.fetch_article_resources.side_effect = lambda _vehicle_id, article_id: details[article_id]
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_AUTOAPI_BASE_URL": "http://127.0.0.1:3000",
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                records, source_info = _load_autoapi_job_catalog(
                    vehicle, object(), query="replace alternator and starter"
                )

        self.assertEqual(source_info["targeted_article_fetch_count"], 2)
        self.assertEqual(connector.fetch_article_resources.call_count, 2)
        by_id = {record["article"]["article_id"]: record["article"] for record in records}
        self.assertEqual(by_id["alt-1"]["operations"][1]["duration_hours"], 1.5)
        self.assertEqual(by_id["starter-1"]["operations"][0]["operation_id"], "shared-belt")
        self.assertNotIn("brake-1", [call.args[1] for call in connector.fetch_article_resources.call_args_list])

    def test_unknown_structured_source_can_use_opt_in_mercury_extractor(self):
        from autodata_ingestion.source_adapters import NormalizationCandidate
        from autodata_ingestion.worker import _collect_connector

        resource = SourceResource.from_bytes(
            "provider://vehicle/unknown.json",
            "source-v1",
            b'{"providerPayload":{"headline":"Brake connector bulletin"}}',
            "application/json",
        )

        class FakeConnector:
            def fetch(self, request):
                self.request = request
                return [resource]

        candidate = NormalizationCandidate(
            "article",
            "mercury2:article:stable",
            {
                "id": "TSB-42",
                "title": "Brake connector bulletin",
                "body": "Inspect the brake connector.",
            },
            "providerPayload.article",
        )
        identity = NormalizationCandidate(
            "vehicle_identity",
            "mercury2:vehicle_identity:stable",
            {"year": 2019, "make": "Cadillac", "model": "Escalade ESV"},
            "providerPayload.vehicle",
        )
        with patch.dict(
            "os.environ",
            {"AUTODATA_MERCURY2_EXTRACTION_ENABLED": "1"},
            clear=False,
        ):
            with patch(
                "autodata_ingestion.mercury2.Mercury2Client.from_environment",
                return_value=object(),
            ) as client_factory:
                with patch(
                    "autodata_ingestion.mercury2.Mercury2SourceExtractor.extract",
                    return_value=(identity, candidate),
                ) as extract:
                    artifacts, bundle, quality = _collect_connector(FakeConnector())

        self.assertEqual(artifacts[0].metadata["extraction_mode"], "mercury-2")
        self.assertEqual(artifacts[0].metadata["candidate_count"], 2)
        self.assertEqual(bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(quality.status, "needs_review")
        client_factory.assert_called_once_with()
        extract.assert_called_once()

    def test_idle_run_reports_fast_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "ingestion", "lane": "fast", "status": "idle"})

    def test_configured_vehicle_list_returns_deterministic_structured_selection(self):
        with patch.dict(
            "os.environ",
            {
                "AUTODATA_SOURCE_DIRECTORY": "",
                "AUTODATA_SOURCE_URI": "",
                "AUTODATA_FAST_EVENT_JSON": "",
                "AUTODATA_VEHICLE_LIST_JSON": json.dumps([
                    {"model_year": "99", "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2wd"},
                    {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine_displacement_l": 5.3},
                ]),
            },
            clear=False,
        ):
            result = run_once()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["vehicle_count"], 1)
        self.assertEqual(result["vehicles"][0]["vehicle_id_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(result["vehicles"][0]["configurations"]), 2)

    def test_configured_vehicle_list_surfaces_conflicting_dimensions_as_review(self):
        from autodata_ingestion.worker import run_vehicle_selection

        result = run_vehicle_selection(
            json.dumps(
                [
                    {
                        "year": 1999,
                        "make": "Chevrolet",
                        "model": "Silverado 1500",
                        "region": "US",
                        "drivetrain": "2WD",
                    },
                    {
                        "year": 1999,
                        "make": "Chevrolet",
                        "model": "Silverado 1500",
                        "region": "US",
                        "drivetrain": "4WD",
                    },
                ]
            )
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(
            result["vehicles"][0]["configurations"][-1]["status"],
            "needs_review",
        )

    def test_configured_vehicle_list_can_persist_identity_observations(self):
        from autodata_ingestion import vehicle_selection_persistence

        values = [
            {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2wd"},
            {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine_displacement_l": 5.3},
        ]
        with patch(
            "autodata_ingestion.vehicle_selection_persistence.persist_vehicle_selection_list",
            return_value={
                "status": "persisted",
                "observation_count": 2,
                "observations": [
                    {
                        "vehicle_id": "vehicle-1",
                        "vehicle_key": "chevrolet-silverado-1500-1999-us",
                        "vehicle_configuration_id": "configuration-1",
                        "configuration_key": "chevrolet-silverado-1500-1999-us",
                        "observation_id": "observation-1",
                        "resolution_status": "matched",
                    },
                    {
                        "vehicle_id": "vehicle-1",
                        "vehicle_key": "chevrolet-silverado-1500-1999-us",
                        "vehicle_configuration_id": "configuration-2",
                        "configuration_key": "chevrolet-silverado-1500-1999-us-engine-5-3l",
                        "observation_id": "observation-2",
                        "resolution_status": "matched",
                    },
                ],
            },
        ) as persist:
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "",
                    "AUTODATA_FAST_EVENT_JSON": "",
                    "AUTODATA_VEHICLE_LIST_JSON": json.dumps(values),
                    "AUTODATA_SOURCE_PERSIST": "1",
                    "AUTODATA_SOURCE_REGION": "US",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["persistence"]["status"], "persisted")
        self.assertEqual(result["vehicles"][0]["vehicle_id"], "vehicle-1")
        self.assertEqual(
            result["vehicles"][0]["configurations"][1]["vehicle_configuration_id"],
            "configuration-2",
        )
        persist.assert_called_once()
        self.assertEqual(persist.call_args.args[0], values)

    def test_configured_article_url_returns_normalized_article_and_evidence_json(self):
        from autodata_ingestion.worker import run_article_url

        resource = SourceResource.from_bytes(
            "https://source.example/tsb-42",
            "v1",
            b'<html><head><meta name="vehicle" content="2019 Cadillac Escalade ESV"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch.dict("os.environ", {"AUTODATA_SOURCE_VERSION": "v1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": "", "AUTODATA_SOURCE_PERSIST": "0"}, clear=False):
                result = run_article_url(
                    resource.source_uri,
                    json.dumps({"year": 2019, "make": "Cadillac", "model": "Escalade ESV", "region": "US"}),
                )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["vehicle"]["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["articles"][0]["article_id"], "TSB-42")
        self.assertTrue(result["evidence"])

    def test_configured_article_url_persists_ready_intake_when_enabled(self):
        from autodata_ingestion.worker import run_article_url

        resource = SourceResource.from_bytes(
            "https://source.example/tsb-42",
            "v1",
            b'<html><head><meta name="vehicle" content="2019 Cadillac Escalade ESV"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.name = "http"
            connector_class.return_value.fetch.return_value = [resource]
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "ready", "vehicle_id": "vehicle-1"},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {"AUTODATA_SOURCE_PERSIST": "1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": ""},
                    clear=False,
                ):
                    result = run_article_url(
                        resource.source_uri,
                        json.dumps({"year": 2019, "make": "Cadillac", "model": "Escalade ESV", "region": "US"}),
                    )

        self.assertEqual(result["persistence"]["vehicle_id"], "vehicle-1")
        persist.assert_called_once()
        self.assertEqual(persist.call_args.kwargs["adapter_name"], "http")

    def test_configured_knowledge_request_returns_catalog_hit_without_http_fetch(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        request = {
            "vehicle": {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US"},
            "query": "brake connector",
            "catalog": [
                {
                    "vehicle_key": "chevrolet-silverado-1500-1999-us",
                    "kind": "article",
                    "article": {"article_id": "TSB-42", "title": "Brake connector bulletin"},
                    "evidence": [],
                }
            ],
        }

        with patch.dict(
            "os.environ",
            {
                "AUTODATA_SOURCE_DIRECTORY": "",
                "AUTODATA_SOURCE_URI": "",
                "AUTODATA_FAST_EVENT_JSON": "",
                "AUTODATA_ARTICLE_URI": "",
                "AUTODATA_KNOWLEDGE_REQUEST_JSON": json.dumps(request),
            },
            clear=False,
        ):
            result = run_once()

        self.assertEqual(result["status"], "cache_hit")
        self.assertEqual(result["vehicle"]["make"], "Chevrolet")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")

    def test_configured_knowledge_request_fetches_on_catalog_miss(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        source_uri = "https://source.example/{vehicle_key}/{drivetrain}/{engine_displacement_l}?q={query}"
        resource = SourceResource.from_bytes(
            "https://source.example/chevrolet-silverado-1500-1999-us/2WD/5.3?q=brake%20connector",
            "source-v1",
            b'<html><head><meta name="vehicle" content="1999 Chevrolet Silverado 1500"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect the brake connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "ready", "vehicle_id": "vehicle-1"},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {"AUTODATA_SOURCE_PERSIST": "1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": ""},
                    clear=False,
                ):
                    result = run_vehicle_knowledge(
                        json.dumps(
                            {
                                "vehicle": {
                                    "year": 1999,
                                    "make": "Chevy",
                                    "model": "Silverado 1500",
                                    "region": "US",
                                    "drivetrain": "2wd",
                                    "engine_displacement_l": 5.3,
                                },
                                "query": "brake connector",
                                "source_uri_template": source_uri,
                            }
                        )
                    )

        self.assertEqual(result["status"], "fetched")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")
        connector_class.assert_called_once()
        self.assertEqual(
            connector_class.call_args.args[0],
            "https://source.example/chevrolet-silverado-1500-1999-us/2WD/5.3?q=brake%20connector",
        )
        persist.assert_called_once()
        self.assertEqual(persist.call_args.kwargs["adapter_name"], "knowledge-fallback")

    def test_configured_knowledge_request_reads_database_catalog_when_not_supplied(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=[
                {
                    "vehicle_key": "chevrolet-silverado-1500-1999-us",
                    "kind": "article",
                    "article": {
                        "article_id": "TSB-42",
                        "title": "Brake connector bulletin",
                    },
                    "evidence": [],
                }
            ],
        ) as load_catalog:
            result = run_vehicle_knowledge(
                json.dumps(
                    {
                        "vehicle": {
                            "year": 1999,
                            "make": "Chevy",
                            "model": "Silverado 1500",
                            "region": "US",
                        },
                        "query": "brake connector",
                    }
                )
            )

        self.assertEqual(result["status"], "cache_hit")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")
        load_catalog.assert_called_once()

    def test_configured_source_directory_runs_the_normalization_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "name.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV - 2WD"}')
            (root / "procedure").write_bytes(b"<html><body>Connector procedure</body></html>")

            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": directory,
                    "AUTODATA_SOURCE_VERSION": "drop-v1",
                    "AUTODATA_SOURCE_REGION": "US",
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["worker"], "ingestion")
        self.assertEqual(result["lane"], "fast")
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["source_artifacts"], 2)
        self.assertEqual(result["quarantined"], 0)

    def test_configured_http_source_runs_through_the_same_pipeline(self):
        resource = SourceResource.from_bytes(
            "https://source.example/vehicle",
            "http-drop-v1",
            b'{"body":"2019 Cadillac Escalade ESV"}',
            "application/json",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "https://source.example/vehicle",
                    "AUTODATA_SOURCE_VERSION": "http-drop-v1",
                    "AUTODATA_SOURCE_REGION": "US",
                    "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": '{"X-Source-Token":"local-test"}',
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        connector_class.assert_called_once()
        self.assertEqual(connector_class.call_args.args[:2], ("https://source.example/vehicle", "http-drop-v1"))
        self.assertEqual(connector_class.call_args.kwargs["request_headers"], {"X-Source-Token": "local-test"})
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["source_artifacts"], 1)

    def test_module_entrypoint_does_not_preload_itself(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        environment["AUTODATA_WORKER_ONCE"] = "1"
        for variable in ("AUTODATA_SOURCE_DIRECTORY", "AUTODATA_SOURCE_URI"):
            environment.pop(variable, None)

        completed = subprocess.run(
            [sys.executable, "-m", "autodata_ingestion.worker"],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertNotIn("RuntimeWarning", completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"worker": "ingestion", "lane": "fast", "status": "idle"})

    def test_fast_event_json_dispatches_a_source_descriptor_through_the_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "vehicle.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV"}')
            fast_event = {
                "event_id": "event-1",
                "event_type": "dataset.fast.requested",
                "event_version": 1,
                "occurred_at": "2026-09-03T12:00:00+00:00",
                "producer": "payment-reconciler",
                "request_id": "request-1",
                "projection_id": "projection-1",
                "revision_id": None,
                "correlation_id": "correlation-1",
                "idempotency_key": "fast-request-1",
                "payload": {
                    "vehicle_key": "cadillac-escalade-esv-2019-us",
                    "region": "US",
                    "source": {"kind": "directory", "location": directory, "version": "drop-v1"},
                },
            }
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "",
                    "AUTODATA_FAST_EVENT_JSON": json.dumps(fast_event),
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["request_id"], "request-1")
        self.assertEqual(result["projection_id"], "projection-1")
        self.assertEqual(result["idempotency_key"], "fast-request-1")
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")

    def test_persistent_fast_event_passes_projection_identity_to_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "vehicle.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV"}')
            fast_event = {
                "event_id": "event-2",
                "event_type": "dataset.fast.requested",
                "event_version": 1,
                "occurred_at": "2026-09-03T12:00:00+00:00",
                "producer": "payment-reconciler",
                "request_id": "request-2",
                "projection_id": "projection-2",
                "correlation_id": "correlation-2",
                "idempotency_key": "fast-request-2",
                "payload": {
                    "vehicle_key": "cadillac-escalade-esv-2019-us",
                    "region": "US",
                    "source": {"kind": "directory", "location": directory, "version": "drop-v2"},
                },
            }
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "viewable", "publication": {"published": True}},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {
                        "AUTODATA_SOURCE_DIRECTORY": "",
                        "AUTODATA_SOURCE_URI": "",
                        "AUTODATA_FAST_EVENT_JSON": json.dumps(fast_event),
                        "AUTODATA_SOURCE_PERSIST": "1",
                    },
                    clear=False,
                ):
                    result = run_once()

        self.assertEqual(result["persistence_status"], "viewable")
        publication = persist.call_args.kwargs["publication"]
        self.assertEqual(publication.request_id, "request-2")
        self.assertEqual(publication.projection_id, "projection-2")
        self.assertEqual(publication.idempotency_key, "fast-request-2")

    def test_nats_once_delegates_to_the_durable_consumer(self):
        with patch("autodata_ingestion.consumer.consume_once", new_callable=AsyncMock) as consume:
            consume.return_value = {"status": "idle", "received": 0}

            from autodata_ingestion.worker import run_nats_once

            result = run_nats_once()

        self.assertEqual(result, {"status": "idle", "received": 0})
        consume.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
