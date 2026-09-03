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
    def test_idle_run_reports_fast_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "ingestion", "lane": "fast", "status": "idle"})

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
