import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_contracts.fakes import FakePrimarySource  # noqa: E402
from autodata_ingestion.normalization import normalize_source_snapshot  # noqa: E402


class NormalizationTests(unittest.TestCase):
    def test_source_snapshot_becomes_normalized_vehicle_output(self):
        snapshot = FakePrimarySource().fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")

        normalized = normalize_source_snapshot(snapshot)

        self.assertEqual(normalized.vehicle_key, "toyota-corolla-2024-us")
        self.assertEqual(normalized.model_year, 2024)
        self.assertEqual(normalized.region, "US")
        self.assertEqual(normalized.source_snapshot_id, snapshot.source_snapshot_id)
        self.assertEqual(normalized.specifications[0].name, "engine_displacement_l")
        self.assertEqual(normalized.specifications[0].value, 2.0)

    def test_normalization_rejects_missing_vehicle_identity(self):
        snapshot = FakePrimarySource().fetch("Toyota", "Corolla", 2024, "US", "fixture-v1")
        snapshot.content["vehicle"].pop("model")

        with self.assertRaisesRegex(ValueError, "model"):
            normalize_source_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
