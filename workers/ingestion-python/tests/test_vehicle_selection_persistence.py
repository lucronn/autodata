import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.vehicle_selection_persistence import (  # noqa: E402
    persist_vehicle_selection_list,
)


class RecordingCursor:
    def __init__(self):
        self.calls = []
        self.last_query = ""

    def execute(self, query, params):
        self.last_query = query
        self.calls.append((query, params))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def fetchone(self):
        if "FROM source_snapshots" in self.last_query:
            return ("snapshot-1",)
        if "FROM vehicle_identity_bases" in self.last_query:
            return None
        return (self.calls[-1][1][0],)


class RecordingConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True


class VehicleSelectionPersistenceTests(unittest.TestCase):
    def test_persists_coarse_and_rich_rows_under_one_vehicle_family(self):
        values = [
            {
                "year": "99",
                "make": "Chevy",
                "model": "Silverado 1500",
                "region": "US",
                "drivetrain": "2wd",
            },
            {
                "year": 1999,
                "make": "Chevrolet",
                "model": "Silverado 1500",
                "region": "US",
                "drivetrain": "2WD",
                "engine_displacement_l": 5.3,
            },
        ]
        cursor = RecordingCursor()
        connection = RecordingConnection(cursor)

        with patch(
            "autodata_ingestion.vehicle_selection_persistence.store_source_artifacts"
        ) as store_artifacts:
            fake_json = types.ModuleType("psycopg.types.json")
            fake_json.Jsonb = lambda value: value
            fake_types = types.ModuleType("psycopg.types")
            fake_types.json = fake_json
            fake_psycopg = types.ModuleType("psycopg")
            fake_psycopg.connect = lambda **_kwargs: connection
            with patch.dict(
                sys.modules,
                {
                    "psycopg": fake_psycopg,
                    "psycopg.types": fake_types,
                    "psycopg.types.json": fake_json,
                },
            ):
                with patch.dict("os.environ", {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
                    result = persist_vehicle_selection_list(
                        values,
                        source_uri="file://selectors/vehicles.json",
                        source_version="selectors-v1",
                    )

        self.assertEqual(result["status"], "persisted")
        self.assertEqual(result["source_snapshot_id"], "snapshot-1")
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(
            [item["vehicle_key"] for item in result["observations"]],
            ["chevrolet-silverado-1500-1999-us"] * 2,
        )
        self.assertEqual(
            result["observations"][0]["configuration_key"],
            "chevrolet-silverado-1500-1999-us",
        )
        self.assertEqual(
            result["observations"][1]["configuration_key"],
            "chevrolet-silverado-1500-1999-us-engine-5-3l",
        )
        self.assertTrue(connection.committed)
        store_artifacts.assert_called_once()
        self.assertEqual(len(store_artifacts.call_args.args[0]), 1)
        self.assertEqual(
            sum("vehicle_identity_observations" in query for query, _ in cursor.calls),
            2,
        )
        self.assertEqual(
            sum("INSERT INTO extraction_evidence" in query for query, _ in cursor.calls),
            2,
        )


if __name__ == "__main__":
    unittest.main()
