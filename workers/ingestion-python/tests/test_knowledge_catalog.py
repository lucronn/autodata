import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import VehicleTarget  # noqa: E402
from autodata_ingestion.knowledge_catalog import (  # noqa: E402
    _derived_rows_to_catalog,
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
                    [{"url": "https://source.example/connector.png", "alt": "Connector diagram"}],
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
        self.assertEqual(
            result[0]["article"]["images"],
            [{"url": "https://source.example/connector.png", "alt": "Connector diagram"}],
        )
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

    def test_query_aware_read_selects_requested_articles_outside_default_window(self):
        cursor = Cursor([])
        connection = Connection(cursor)
        fake_psycopg = types.ModuleType("psycopg")
        fake_psycopg.connect = lambda **_kwargs: connection
        target = VehicleTarget("Toyota", "Rav4", 1997, "US")

        with patch.dict(
            sys.modules,
            {"psycopg": fake_psycopg},
        ):
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_POSTGRES_PASSWORD": "test-only",
                    "AUTODATA_DERIVED_ARTICLE_CACHE_ENABLED": "0",
                },
            ):
                load_vehicle_knowledge_catalog(target, query="oil pump, water pump replacement procedure")

        self.assertEqual(
            cursor.params,
            (target.vehicle_key, "%oil pump%", "%water pump%", 200),
        )
        self.assertIn("DISTINCT ON (ca.article_id)", cursor.query)
        self.assertNotIn("NOT EXISTS", cursor.query)
        self.assertIn("ca.title ILIKE %s", cursor.query)

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

    def test_derived_catalog_read_preserves_components_labor_and_procedure(self):
        result = _derived_rows_to_catalog(
            [(
                "combined:vehicle:alternator+starter:v1",
                "Alternator and starter service",
                "Disconnect battery. Replace both components.",
                [{"sequence": 1, "action": "Disconnect battery"}],
                "source-v1",
                "ready",
                "revision-2",
                {"article_ids": ["alt-1", "start-1"], "evidence_ids": ["ev-1"], "requested_components": ["alternator", "starter"]},
                [{"url": "https://source.test/combined.png"}],
                {"total_labor_hours": 4.25, "overlap_hours": 0.25},
                "a" * 64,
            )],
            VehicleTarget("Chevrolet", "Silverado 1500", 1999, "US"),
        )

        article = result[0]["article"]
        self.assertEqual(article["derived_components"], ["alternator", "starter"])
        self.assertEqual(article["source_article_ids"], ["alt-1", "start-1"])
        self.assertEqual(article["labor"]["total_labor_hours"], 4.25)
        self.assertEqual(article["procedure"]["steps"][0]["action"], "Disconnect battery")

    def test_derived_catalog_read_preserves_review_warnings_and_exclusions(self):
        result = _derived_rows_to_catalog(
            [(
                "combined:vehicle:brake-line:v2",
                "Brake line service",
                "Replace the line and bleed the system.",
                [{"sequence": 1, "action": "Replace brake line"}],
                "source-v9",
                "needs_review",
                "revision-3",
                {
                    "article_ids": ["brake-line"],
                    "evidence_ids": ["ev-1"],
                    "requested_components": ["brake_line"],
                    "procedure": {
                        "title": "Brake line service",
                        "steps": [{"sequence": 1, "action": "Replace brake line"}],
                        "warnings": [{"warning_id": "warn-1", "message": "Depressurize first."}],
                        "review_state": "UNREVIEWED",
                        "review_label": "UNREVIEWED / human review pending",
                        "requires_review": True,
                        "excluded_operation_ids": ["bleed-brakes"],
                        "excluded_operation_reasons": {"bleed-brakes": "missing source evidence"},
                    },
                    "review_state": "pending",
                    "review_label": "pending human review",
                    "requires_review": True,
                    "review_reasons": ["procedure_requires_review"],
                    "excluded_operation_ids": ["bleed-brakes"],
                    "excluded_operation_reasons": {"bleed-brakes": "missing source evidence"},
                },
                [],
                {"total_labor_hours": 1.5},
                "b" * 64,
                "mercury-2",
            )],
            VehicleTarget("Toyota", "RAV4", 1997, "US"),
        )

        article = result[0]["article"]
        assert article["procedure"]["warnings"][0]["warning_id"] == "warn-1"
        assert article["procedure"]["review_state"] == "UNREVIEWED"
        assert article["review_label"] == "pending human review"
        assert article["requires_review"] is True
        assert article["review_reasons"] == ["procedure_requires_review"]
        assert article["excluded_operation_ids"] == ["bleed-brakes"]
        assert article["excluded_operation_reasons"]["bleed-brakes"] == "missing source evidence"


if __name__ == "__main__":
    unittest.main()
