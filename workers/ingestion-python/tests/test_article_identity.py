import hashlib
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts/python"))
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def _exact_hash(article):
    payload = {
        "body": article["body"],
        "source_uri": article.get("source_uri"),
        "title": article["title"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class ArticleIdentityTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("autodata_ingestion.article_identity")
        self.assertIsNotNone(spec, "article identity module must exist")
        return importlib.import_module("autodata_ingestion.article_identity")

    def test_exact_hash_is_stable_and_default_gate_marks_near_duplicate(self):
        module = self._module()

        article = {
            "source_uri": "https://example.com/articles/tsb-42",
            "title": "Brake connector service bulletin",
            "body": "Inspect the brake connector.\nReplace the terminal if needed.",
        }
        existing = [
            {
                "source_uri": "https://mirror.example.com/articles/tsb-42",
                "title": "Brake Connector Service Bulletin",
                "body": "Inspect the brake connector. Replace the terminal if needed!",
            }
        ]

        identity = module.canonicalize_article_identity(article, existing_articles=existing)

        self.assertEqual(identity.article_key, _exact_hash(article))
        self.assertEqual(identity.near_duplicate_of, _exact_hash(existing[0]))
        self.assertTrue(identity.is_near_duplicate)
        self.assertGreaterEqual(identity.near_duplicate_score, 0.95)
        self.assertEqual(
            identity.to_dict()["token_signature"],
            [
                "brake",
                "connector",
                "service",
                "bulletin",
                "inspect",
                "the",
                "brake",
                "connector",
                "replace",
                "the",
                "terminal",
                "if",
                "needed",
            ],
        )

    def test_below_gate_articles_remain_distinct(self):
        module = self._module()

        article = {
            "source_uri": "https://example.com/articles/tsb-50",
            "title": "Brake connector service bulletin",
            "body": "Inspect the brake connector and replace the terminal if needed.",
        }
        existing = [
            {
                "source_uri": "https://example.com/articles/tsb-51",
                "title": "Brake connector service bulletin",
                "body": "Inspect the seat harness and replace the buckle if needed.",
            }
        ]

        identity = module.canonicalize_article_identity(
            article,
            existing_articles=existing,
            near_duplicate_gate=0.95,
        )

        self.assertEqual(identity.article_key, _exact_hash(article))
        self.assertFalse(identity.is_near_duplicate)
        self.assertIsNone(identity.near_duplicate_of)
        self.assertLess(identity.near_duplicate_score, 0.95)


if __name__ == "__main__":
    unittest.main()
