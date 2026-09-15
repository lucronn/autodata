import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.bundle_persistence import (  # noqa: E402
    _persist_catalog_articles,
    normalized_article_fingerprint,
)


class RecordingCursor:
    def __init__(self, select_rows=()):
        self.calls = []
        self._returned_id = None
        self._select_rows = list(select_rows)
        self._last_was_select = False

    def execute(self, query, params):
        self.calls.append((query, params))
        self._last_was_select = " ".join(query.split()).lower().startswith("select ")
        if not self._last_was_select:
            self._returned_id = params[0]

    def fetchone(self):
        if self._last_was_select:
            return None
        return (self._returned_id,)

    def fetchall(self):
        if not self._last_was_select:
            raise AssertionError("fetchall is only valid after a SELECT")
        return list(self._select_rows)


ARTICLE = {
    "article_key": "article:TSB-42:json:article[0]",
    "article_id": "TSB-42",
    "bucket": "Service Bulletins",
    "title": "Brake caliper replacement",
    "bulletin_number": "42",
    "release_date": "2026-09-02",
    "sort": 1,
    "body": "Remove the wheel. Replace the caliper.",
    "steps": [
        "Remove the wheel",
        {"text": "Torque the guide pins", "sequence": 2},
    ],
    "evidence_id": "evidence-1",
}

EVIDENCE = {
    "evidence-1": {
        "content_sha256": "a" * 64,
        "locator": "json:article[0]",
        "confidence": 0.97,
    }
}

CONTENT_EVIDENCE = {
    "content-evidence-1": {
        "evidence_id": "content-evidence-1",
        "content_sha256": "b" * 64,
        "locator": "body.html:3950424",
        "confidence": 0.91,
    }
}


class BundlePersistenceTests(unittest.TestCase):
    def test_fingerprint_is_canonical_for_normalized_article_content(self):
        equivalent = {
            **ARTICLE,
            "body": "  Remove   the wheel.\nReplace the caliper. ",
            "steps": [
                "Remove the wheel",
                {"sequence": 2, "text": "Torque   the guide pins"},
            ],
        }

        first = normalized_article_fingerprint(ARTICLE)
        second = normalized_article_fingerprint(equivalent)

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            "f669e7c0f487942b90d5d7fffb33af3b94edc0754333817f2c8973fabc60b4cd",
        )
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        self.assertNotEqual(
            first,
            normalized_article_fingerprint({**ARTICLE, "steps": ["Remove the wheel"]}),
        )

    def test_article_upsert_persists_content_fingerprint_and_provenance(self):
        cursor = RecordingCursor()

        _persist_catalog_articles(
            cursor,
            (ARTICLE,),
            EVIDENCE,
            {"a" * 64: "snapshot-1"},
            "vehicle-1",
            lambda value: value,
            vehicle_configuration_id="configuration-1",
        )

        query, params = next(
            (query, params)
            for query, params in cursor.calls
            if "INSERT INTO catalog_articles" in query
        )
        compact_query = " ".join(query.split())
        for column in (
            "body",
            "steps",
            "images",
            "operations",
            "normalized_fingerprint",
            "source_snapshot_id",
            "source_locator",
            "evidence_locator",
            "vehicle_configuration_id",
        ):
            self.assertIn(column, compact_query)
        self.assertIn("ON CONFLICT (vehicle_id, article_id, source_snapshot_id, source_locator)", compact_query)
        self.assertIn("body = EXCLUDED.body", compact_query)
        self.assertIn("steps = EXCLUDED.steps", compact_query)
        self.assertIn("normalized_fingerprint = EXCLUDED.normalized_fingerprint", compact_query)
        self.assertIn(
            "vehicle_configuration_id = COALESCE( EXCLUDED.vehicle_configuration_id, catalog_articles.vehicle_configuration_id )",
            compact_query,
        )
        self.assertEqual(params[8], ARTICLE["body"])
        self.assertEqual(params[9], ARTICLE["steps"])
        self.assertEqual(params[10], [])
        self.assertEqual(params[11], normalized_article_fingerprint(ARTICLE))
        self.assertEqual(params[12], "snapshot-1")
        self.assertEqual(params[13], "json:article[0]")
        self.assertEqual(params[14], "json:article[0]")
        self.assertEqual(params[15], 0.97)
        self.assertEqual(params[16], "configuration-1")
        self.assertEqual(params[20], [])

    def test_article_upsert_persists_separate_document_content_provenance(self):
        article = {
            **ARTICLE,
            "content_evidence_id": "content-evidence-1",
            "content_locator": "body.html:3950424",
        }
        cursor = RecordingCursor()

        _persist_catalog_articles(
            cursor,
            (article,),
            {**EVIDENCE, **CONTENT_EVIDENCE},
            {"a" * 64: "snapshot-index", "b" * 64: "snapshot-document"},
            "vehicle-1",
            lambda value: value,
        )

        query, params = next(
            (query, params)
            for query, params in cursor.calls
            if "INSERT INTO catalog_articles" in query
        )
        compact_query = " ".join(query.split())
        for column in (
            "content_source_snapshot_id",
            "content_source_locator",
            "content_extraction_evidence_id",
        ):
            self.assertIn(column, compact_query)
        self.assertEqual(params[17], "snapshot-document")
        self.assertEqual(params[18], "body.html:3950424")
        self.assertEqual(params[19], "content-evidence-1")

    def test_replaying_the_same_article_has_the_same_row_identity_and_values(self):
        first_cursor = RecordingCursor()
        second_cursor = RecordingCursor()

        arguments = (
            (ARTICLE,),
            EVIDENCE,
            {"a" * 64: "snapshot-1"},
            "vehicle-1",
            lambda value: value,
        )
        _persist_catalog_articles(first_cursor, *arguments)
        _persist_catalog_articles(second_cursor, *arguments)

        self.assertEqual(first_cursor.calls[0][1], second_cursor.calls[0][1])
        self.assertEqual(first_cursor.fetchone(), second_cursor.fetchone())
        insert_query = next(
            query for query, _params in first_cursor.calls
            if "INSERT INTO catalog_articles" in query
        )
        self.assertIn(
            "ON CONFLICT (vehicle_id, article_id, source_snapshot_id, source_locator)",
            " ".join(insert_query.split()),
        )

    def test_later_source_snapshot_links_a_near_duplicate_to_existing_canonical_row(self):
        existing = (
            "canonical-article",
            ARTICLE["title"],
            ARTICLE["body"],
            "https://source.example/original",
        )
        incoming = {
            **ARTICLE,
            "article_id": "TSB-42-NEW-SOURCE",
            "article_key": "article:TSB-42-NEW-SOURCE:html",
            "title": "Brake caliper replacement",
            "body": "Remove the wheel; Replace the caliper.",
            "evidence_id": "evidence-2",
        }
        evidence = {
            "evidence-2": {
                "evidence_id": "evidence-2",
                "content_sha256": "b" * 64,
                "locator": "html:article",
                "confidence": 0.96,
                "reviewer_state": "pending",
            }
        }
        cursor = RecordingCursor(select_rows=[existing])

        links = _persist_catalog_articles(
            cursor,
            (incoming,),
            evidence,
            {"b" * 64: "snapshot-2"},
            "vehicle-1",
            lambda value: value,
        )

        self.assertEqual(links, 1)
        link_query, link_params = cursor.calls[-1]
        self.assertIn("INSERT INTO catalog_article_vehicle_links", " ".join(link_query.split()))
        self.assertEqual(link_params[1], "vehicle-1")
        self.assertEqual(link_params[2], "canonical-article")
        self.assertNotEqual(link_params[2], link_params[3])
        self.assertEqual(link_params[4:7], ("snapshot-2", "evidence-2", "html:article"))

    def test_migration_adds_compatible_exact_fingerprint_columns_without_similarity_index(self):
        migration_path = ROOT / "db/migrations/014_normalized_article_content.sql"
        migration = migration_path.read_text()

        self.assertIn("ALTER TABLE catalog_articles", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS body text", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS steps jsonb", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS normalized_fingerprint text", migration)
        self.assertRegex(
            migration,
            r"normalized_fingerprint\s+IS NULL\s+OR\s+normalized_fingerprint\s+~",
        )
        self.assertIn("catalog_articles_normalized_fingerprint_idx", migration)
        self.assertIn("ON catalog_articles (vehicle_id, normalized_fingerprint)", migration)
        self.assertNotRegex(
            migration,
            r"CREATE\s+UNIQUE\s+INDEX[^;]*normalized_fingerprint",
            re.IGNORECASE,
        )
        self.assertIn("no schema-level similarity index", migration)
        self.assertIn("semantic near-duplicate quarantine", migration)
        self.assertNotIn("pg_trgm", migration)
        self.assertNotRegex(migration, r"USING\s+(gist|gin).*similar", re.IGNORECASE)
        self.assertIn("INSERT INTO schema_migrations (version)", migration)
        self.assertIn("014_normalized_article_content", migration)


if __name__ == "__main__":
    unittest.main()
