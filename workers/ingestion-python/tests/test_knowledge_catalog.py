import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import VehicleTarget  # noqa: E402
from autodata_ingestion.knowledge_catalog import (  # noqa: E402
    _rows_to_catalog,
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
        self.assertEqual(cursor.params, (target.vehicle_key, 200))
        self.assertIn("JOIN extraction_evidence", cursor.query)
        self.assertIn("NOT EXISTS", cursor.query)
        self.assertIn("takedown_status = 'active'", cursor.query)
        self.assertIn("LIMIT %s", cursor.query)

    def test_cache_limit_is_configurable_but_bounded(self):
        from autodata_ingestion.knowledge_catalog import _knowledge_cache_limit

        with patch.dict("os.environ", {"AUTODATA_KNOWLEDGE_CACHE_MAX_RECORDS": "37"}):
            self.assertEqual(_knowledge_cache_limit(), 37)
        with patch.dict("os.environ", {"AUTODATA_KNOWLEDGE_CACHE_MAX_RECORDS": "not-a-number"}):
            self.assertEqual(_knowledge_cache_limit(), 200)
        with patch.dict("os.environ", {"AUTODATA_KNOWLEDGE_CACHE_MAX_RECORDS": "50000"}):
            self.assertEqual(_knowledge_cache_limit(), 1000)

    def test_catalog_read_exposes_separate_document_content_evidence(self):
        row = (
            "catalog-1",
            "3950424:12924016",
            "Other Diagnostics",
            "A/C System Performance Test",
            None,
            None,
            1,
            "Check compressor operation.",
            None,
            "index-snapshot",
            "body.articleDetails[4848]",
            "body.articleDetails[4848]",
            1.0,
            "file://v2.json",
            "autoapi-v1",
            "index-evidence",
            "sources/v2.json",
            "{metadata}",
            "pending",
            "Cadillac",
            "Escalade ESV",
            2019,
            "US",
            None,
            "2WD",
            "BASE",
            6.2,
            "document-snapshot",
            "body.html:3950424",
            "document-evidence",
            "file://3950424_12924016.json",
            "autoapi-v1",
            "sources/document.json",
            "Check compressor operation.",
            0.91,
            "pending",
        )

        result = _rows_to_catalog([row], VehicleTarget("Cadillac", "Escalade ESV", 2019, "US"))

        self.assertEqual(result[0]["article"]["body"], "Check compressor operation.")
        self.assertEqual(result[0]["article"]["content_locator"], "body.html:3950424")
        self.assertEqual(
            {item["evidence_id"] for item in result[0]["evidence"]},
            {"index-evidence", "document-evidence"},
        )


if __name__ == "__main__":
    unittest.main()
