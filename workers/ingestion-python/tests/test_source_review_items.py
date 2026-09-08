import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.bundle_persistence import persist_source_review_items  # noqa: E402


class RecordingCursor:
    def __init__(self):
        self.calls = []
        self._returned_id = None

    def execute(self, query, params):
        self.calls.append((query, params))
        self._returned_id = params[0]


class SourceReviewItemTests(unittest.TestCase):
    def test_review_items_are_durable_and_provenance_linked(self):
        cursor = RecordingCursor()
        bundle = type(
            "Bundle",
            (),
            {
                "quarantined": (
                    {
                        "reason": "unsupported_artifact",
                        "content_sha256": "a" * 64,
                        "source_uri": "https://source.example/file.bin",
                    },
                ),
                "conflicts": (
                    {
                        "kind": "article_similarity",
                        "resolution": "needs_review",
                        "article_keys": ["article-a", "article-b"],
                        "evidence_ids": ["evidence-a", "evidence-b"],
                        "similarity": 0.987,
                    },
                ),
            },
        )()
        evidence = {
            "evidence-a": {"content_sha256": "b" * 64},
            "evidence-b": {"content_sha256": "c" * 64},
        }

        count = persist_source_review_items(
            cursor,
            bundle,
            {"a" * 64: "snapshot-a", "b" * 64: "snapshot-b", "c" * 64: "snapshot-c"},
            evidence,
            lambda value: value,
        )

        self.assertEqual(count, 2)
        self.assertEqual(len(cursor.calls), 2)
        for query, params in cursor.calls:
            compact = " ".join(query.split())
            self.assertIn("INSERT INTO source_review_items", compact)
            self.assertIn("ON CONFLICT (item_key)", compact)
            self.assertIn(params[3], {"unsupported_artifact", "article_similarity"})
            self.assertEqual(params[4], "pending")
            self.assertIsInstance(params[5], list)
            self.assertIsInstance(params[6], list)
            self.assertIsInstance(params[7], dict)

        conflict_params = next(
            params for _query, params in cursor.calls if params[2] == "conflict"
        )
        self.assertEqual(conflict_params[2], "conflict")
        self.assertEqual(conflict_params[4], "pending")
        self.assertEqual(conflict_params[5], ["snapshot-b", "snapshot-c"])
        self.assertEqual(json.loads(json.dumps(conflict_params[7]))["similarity"], 0.987)

    def test_similarity_quarantine_is_not_duplicated_when_conflict_is_recorded(self):
        cursor = RecordingCursor()
        bundle = type(
            "Bundle",
            (),
            {
                "quarantined": (
                    {
                        "reason": "similar_article_requires_review",
                        "article_id": "TSB-42",
                        "content_sha256": "a" * 64,
                    },
                ),
                "conflicts": (
                    {
                        "kind": "article_similarity",
                        "article_keys": ["article-a", "article-b"],
                        "evidence_ids": [],
                    },
                ),
            },
        )()

        count = persist_source_review_items(
            cursor,
            bundle,
            {"a" * 64: "snapshot-a"},
            {},
            lambda value: value,
        )

        self.assertEqual(count, 1)
        self.assertEqual(cursor.calls[0][1][2], "conflict")

    def test_migration_defines_review_state_and_indexes(self):
        migration = (ROOT / "db/migrations/018_source_review_items.sql").read_text()

        self.assertIn("CREATE TABLE IF NOT EXISTS source_review_items", migration)
        self.assertIn("item_key text NOT NULL UNIQUE", migration)
        self.assertIn("source_snapshot_ids jsonb NOT NULL", migration)
        self.assertIn("extraction_evidence_ids jsonb NOT NULL", migration)
        self.assertIn("status text NOT NULL DEFAULT", migration)
        self.assertIn("source_review_items_status_idx", migration)
        self.assertIn("INSERT INTO schema_migrations (version)", migration)


if __name__ == "__main__":
    unittest.main()
