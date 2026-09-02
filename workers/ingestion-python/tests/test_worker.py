import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.worker import run_once  # noqa: E402


class IngestionWorkerTests(unittest.TestCase):
    def test_idle_run_reports_fast_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "ingestion", "lane": "fast", "status": "idle"})


if __name__ == "__main__":
    unittest.main()
