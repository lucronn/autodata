import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.worker import run_once  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
