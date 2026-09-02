import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_enrichment.worker import run_once  # noqa: E402


class EnrichmentWorkerTests(unittest.TestCase):
    def test_idle_run_reports_deep_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "enrichment", "lane": "deep", "status": "idle"})


if __name__ == "__main__":
    unittest.main()
