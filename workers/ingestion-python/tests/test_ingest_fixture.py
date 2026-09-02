import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_contracts.fakes import FakePrimarySource  # noqa: E402
from autodata_ingestion.ingest_fixture import build_viewable_content  # noqa: E402
from autodata_ingestion.normalization import normalize_source_snapshot  # noqa: E402


class IngestFixtureTests(unittest.TestCase):
    def test_viewable_content_is_structured_and_provenance_backed(self):
        snapshot = FakePrimarySource().fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")
        normalized = normalize_source_snapshot(snapshot)

        content = build_viewable_content(normalized)

        self.assertEqual(content["vehicle_identity"]["vehicle_key"], "toyota-corolla-2024-us")
        self.assertEqual(content["source_metadata"]["source_snapshot_id"], snapshot.source_snapshot_id)
        self.assertEqual(content["specifications"][0]["name"], "engine_displacement_l")
        self.assertEqual(content["specifications"][0]["unit"], "L")


if __name__ == "__main__":
    unittest.main()
