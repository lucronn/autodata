import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import VehicleTarget  # noqa: E402
from autodata_ingestion.knowledge_catalog import (  # noqa: E402
    load_vehicle_knowledge_catalog,
)


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_value


class KnowledgeCatalogTests(unittest.TestCase):
    def test_loads_active_article_and_procedure_with_vehicle_configuration(self):
        cursor = Cursor(
            [
                (
                    "catalog-1",
                    "TSB-42",
                    "Repair Procedure",
                    "Brake connector replacement",
                    None,
                    None,
                    1,
                    "Inspect and replace the brake connector.",
                    ["Inspect connector", "Replace connector"],
                    "snapshot-1",
                    "body.articleDetails[0]",
                    "body.articleDetails[0]",
                    0.98,
                    "https://source.example/tsb-42",
                    "source-v1",
                    "evidence-1",
                    "sources/tsb-42.html",
                    "Inspect and replace the brake connector.",
                    "pending",
                    "Chevrolet",
                    "Silverado 1500",
                    1999,
                    "US",
                    "Pickup",
                    "2WD",
                    None,
                    5.3,
                )
            ]
        )
        connection = Connection(cursor)
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: connection
        target = VehicleTarget("Chevy", "Silverado 1500", 1999, "US", drivetrain="2wd", engine_displacement_l=5.3)

        with patch.dict(
            sys.modules,
            {"psycopg": fake_psycopg},
        ):
            with patch.dict("os.environ", {"AUTODATA_POSTGRES_PASSWORD": "test-only"}):
                result = load_vehicle_knowledge_catalog(target)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["vehicle_key"], target.vehicle_key)
        self.assertEqual(result[0]["article"]["article_id"], "TSB-42")
        self.assertEqual(result[0]["vehicle_identity"]["engine_displacement_l"], 5.3)
        self.assertEqual(result[0]["evidence"][0]["evidence_id"], "evidence-1")
        self.assertEqual(result[0]["evidence"][0]["artifact_key"], "sources/tsb-42.html")
        self.assertEqual(result[0]["evidence"][0]["reviewer_state"], "pending")
        self.assertEqual(result[1]["procedure"]["procedure_id"], "procedure:TSB-42")
        self.assertEqual(cursor.params, (target.vehicle_key,))
        self.assertIn("JOIN extraction_evidence", cursor.query)
        self.assertIn("NOT EXISTS", cursor.query)
        self.assertIn("takedown_status = 'active'", cursor.query)


if __name__ == "__main__":
    unittest.main()
