import unittest

from autodata_ingestion.vehicle_selection import normalize_vehicle_list_json


class VehicleSelectionTests(unittest.TestCase):
    def test_coarse_and_richer_rows_share_one_family_and_add_engine_configuration(self):
        result = normalize_vehicle_list_json(
            [
                {"model_year": "99", "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2wd"},
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine_displacement_l": 5.3},
            ]
        )

        self.assertEqual(len(result), 1)
        family = result[0]
        self.assertEqual(family["vehicle_id_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(family["drivetrain"], "2WD")
        self.assertEqual(
            [item["configuration_key"] for item in family["configurations"]],
            ["chevrolet-silverado-1500-1999-us", "chevrolet-silverado-1500-1999-us-engine-5-3l"],
        )

    def test_duplicate_rows_are_idempotent_and_conflicts_are_reviewable(self):
        result = normalize_vehicle_list_json(
            [
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine": "5.3L"},
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "4WD", "engine": "5.3L"},
            ]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["drivetrain"], "2WD")
        self.assertEqual(result[0]["configurations"][-1]["status"], "needs_review")
        self.assertEqual(result[0]["configurations"][-1]["conflicts"][0]["field"], "drivetrain")


if __name__ == "__main__":
    unittest.main()
