import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
