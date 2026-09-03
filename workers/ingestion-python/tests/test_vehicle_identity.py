import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


class VehicleIdentityTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("autodata_ingestion.vehicle_identity")
        self.assertIsNotNone(spec, "vehicle identity module must exist")
        return importlib.import_module("autodata_ingestion.vehicle_identity")

    def test_mapping_input_normalizes_aliases_and_emits_json_ready_identity(self):
        module = self._module()

        observation = module.canonicalize_vehicle_observation(
            {
                "year": "24",
                "make": " Chevy ",
                "model": " Silverado-1500 ",
                "trim": " ltz ",
                "drivetrain": "4x2",
                "engine": "5.3LT",
            }
        )
        base_identity = module.build_base_identity(observation)
        configuration = module.build_vehicle_configuration(observation)
        aliases = module.build_vehicle_aliases(observation)

        self.assertEqual(
            base_identity.to_dict(),
            {
                "vehicle_key": "chevrolet-silverado-1500-2024",
                "year": 2024,
                "make": "Chevrolet",
                "model": "Silverado 1500",
            },
        )
        self.assertEqual(
            configuration.to_dict(),
            {
                "configuration_key": "chevrolet-silverado-1500-2024-ltz-2wd-5-3l",
                "vehicle_key": "chevrolet-silverado-1500-2024",
                "trim": "LTZ",
                "drivetrain": "2WD",
                "engine_displacement_l": 5.3,
            },
        )
        self.assertEqual(
            [alias.to_dict() for alias in aliases],
            [
                {"kind": "make", "raw": "Chevy", "canonical": "Chevrolet"},
                {"kind": "drivetrain", "raw": "4x2", "canonical": "2WD"},
                {"kind": "engine_displacement", "raw": "5.3LT", "canonical": "5.3L"},
            ],
        )

    def test_text_input_supports_common_vehicle_form(self):
        module = self._module()

        observation = module.canonicalize_vehicle_observation(
            "24 chevy silverado 1500 ltz 4x2 5.3lt"
        )

        self.assertEqual(observation.year, 2024)
        self.assertEqual(observation.make, "Chevrolet")
        self.assertEqual(observation.model, "Silverado 1500")
        self.assertEqual(observation.trim, "LTZ")
        self.assertEqual(observation.drivetrain, "2WD")
        self.assertEqual(observation.engine_displacement_l, 5.3)

    def test_text_input_normalizes_spaced_engine_displacement(self):
        module = self._module()

        observation = module.canonicalize_vehicle_observation(
            "2024 Chevy, Silverado-1500 LTZ 4x2 5.3 LT"
        )

        self.assertEqual(observation.model, "Silverado 1500")
        self.assertEqual(observation.engine_displacement_l, 5.3)

    def test_candidate_review_prefers_more_complete_exact_match(self):
        module = self._module()

        observation = module.canonicalize_vehicle_observation(
            {
                "year": 2024,
                "make": "Chevrolet",
                "model": "Silverado 1500",
                "trim": "LTZ",
                "drivetrain": "2WD",
                "engine": "5.3L",
            }
        )

        review = module.review_vehicle_candidates(
            observation,
            [
                {
                    "year": 2024,
                    "make": "Chevrolet",
                    "model": "Silverado 1500",
                    "trim": "LT",
                    "drivetrain": "2WD",
                    "engine": "5.3L",
                },
                {
                    "year": 2024,
                    "make": "Chevrolet",
                    "model": "Silverado 1500",
                    "trim": "LTZ",
                    "drivetrain": "4x2",
                    "engine": "5.3LT",
                },
            ],
        )

        self.assertEqual(review.status, "matched")
        self.assertFalse(review.ambiguous)
        self.assertEqual(
            review.selected_candidate_key,
            "chevrolet-silverado-1500-2024-ltz-2wd-5-3l",
        )
        self.assertEqual(
            [candidate.candidate_key for candidate in review.candidates],
            [
                "chevrolet-silverado-1500-2024-ltz-2wd-5-3l",
                "chevrolet-silverado-1500-2024-lt-2wd-5-3l",
            ],
        )
        self.assertGreater(review.candidates[0].score, review.candidates[1].score)

    def test_candidate_review_marks_equal_top_scores_as_ambiguous(self):
        module = self._module()

        observation = module.canonicalize_vehicle_observation(
            {
                "year": 2024,
                "make": "Chevrolet",
                "model": "Silverado 1500",
            }
        )

        review = module.review_vehicle_candidates(
            observation,
            [
                {"year": 2024, "make": "Chevrolet", "model": "Silverado 1500", "trim": "LT"},
                {"year": 2024, "make": "Chevrolet", "model": "Silverado 1500", "trim": "LTZ"},
            ],
        )

        self.assertEqual(review.status, "ambiguous")
        self.assertTrue(review.ambiguous)
        self.assertIsNone(review.selected_candidate_key)
        self.assertEqual(review.reason, "multiple_top_candidates")
        self.assertEqual(review.candidates[0].score, review.candidates[1].score)


if __name__ == "__main__":
    unittest.main()
