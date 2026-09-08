import json
import tempfile
import unittest
from pathlib import Path


from autodata_ingestion.autoapi_batch import (
    AutoAPIBatch,
    build_autoapi_batch_plan,
    collect_autoapi_selection_rows,
    derive_autoapi_vehicle_rows,
    execute_autoapi_batch,
)


class AutoAPIBatchTests(unittest.TestCase):
    def test_derives_vehicle_configurations_from_split_autoapi_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "name.json").write_text(
                json.dumps({"header": {"status": "OK"}, "body": "2019 Cadillac Escalade ESV - 2WD"})
            )
            (root / "motorvehicles.json").write_text(
                json.dumps(
                    {
                        "header": {"status": "OK"},
                        "body": [
                            {
                                "model": "Escalade ESV Base",
                                "id": "168702",
                                "engines": [
                                    {"id": "168702:7864", "name": "6.2L V8 (J) L86 FLEX Electronic"}
                                ],
                            }
                        ],
                    }
                )
            )

            rows = derive_autoapi_vehicle_rows(root, default_region="US")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(rows[0]["trim"], "Base")
        self.assertEqual(rows[0]["engine"], "6.2L")
        self.assertEqual(rows[0]["drivetrain"], "2WD")

    def test_plan_groups_one_source_bundle_with_all_configurations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "name.json").write_text(
                json.dumps({"header": {"status": "OK"}, "body": "2019 Cadillac Escalade ESV - 2WD"})
            )
            (root / "motorvehicles.json").write_text(
                json.dumps(
                    {
                        "header": {"status": "OK"},
                        "body": [
                            {
                                "model": "Escalade ESV Base",
                                "id": "168702",
                                "engines": [
                                    {"id": "1", "name": "6.2L V8 GAS"},
                                    {"id": "2", "name": "5.3L V8 FLEX"},
                                ],
                            }
                        ],
                    }
                )
            )

            plan = build_autoapi_batch_plan(root, default_region="US")

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].vehicle_key, "cadillac-escalade-esv-2019-us")
        self.assertEqual(plan[0].source_directory, root)
        self.assertEqual(
            sorted(item["engine_displacement_l"] for item in plan[0].configurations),
            [5.3, 6.2],
        )

    def test_collects_selector_rows_for_every_discovered_source_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "cadillac"
            bundle.mkdir()
            (bundle / "name.json").write_text(
                json.dumps({"header": {"status": "OK"}, "body": "2019 Cadillac Escalade ESV - 2WD"})
            )
            (bundle / "motorvehicles.json").write_text(
                json.dumps(
                    {
                        "header": {"status": "OK"},
                        "body": [
                            {
                                "model": "Escalade ESV Base",
                                "id": "168702",
                                "engines": [{"id": "1", "name": "6.2L V8 GAS"}],
                            }
                        ],
                    }
                )
            )

            rows = collect_autoapi_selection_rows(root, default_region="US")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(rows[0]["engine"], "6.2L")

    def test_plan_surfaces_selector_vehicles_without_a_source_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "name.json").write_text(
                json.dumps({"header": {"status": "OK"}, "body": "2019 Cadillac Escalade ESV - 2WD"})
            )
            (root / "motorvehicles.json").write_text(
                json.dumps({"header": {"status": "OK"}, "body": []})
            )

            plan = build_autoapi_batch_plan(
                root,
                selector_rows=[
                    {"year": 2019, "make": "Cadillac", "model": "Escalade ESV", "region": "US"},
                    {"year": 2020, "make": "Ford", "model": "F-150", "region": "US"},
                ],
                default_region="US",
            )

        self.assertEqual(
            [item.vehicle_key for item in plan],
            ["cadillac-escalade-esv-2019-us", "ford-f-150-2020-us"],
        )
        self.assertIsNone(plan[1].source_directory)

    def test_execution_reports_missing_source_without_stringifying_null_path(self):
        result = execute_autoapi_batch(
            [
                AutoAPIBatch(
                    vehicle_key="ford-f-150-2020-us",
                    vehicle={
                        "year": 2020,
                        "make": "Ford",
                        "model": "F-150",
                        "region": "US",
                    },
                    source_directory=None,
                    configurations=(),
                )
            ],
            source_version="autoapi-batch-test-v1",
        )

        self.assertEqual(result["status"], "pending_source")
        self.assertIsNone(result["results"][0]["source_directory"])


if __name__ == "__main__":
    unittest.main()
