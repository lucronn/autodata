import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import (  # noqa: E402
    VehicleTarget,
    ingest_vehicle_article,
)
from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import (  # noqa: E402
    ARTICLE_SIMILARITY_THRESHOLD,
    normalize_source_bundle,
)


class _StaticConnector:
    name = "test-http"

    def __init__(self, resources):
        self.resources = resources
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        return list(self.resources)


TARGET = VehicleTarget("Cadillac", "Escalade ESV", 2019, "US")


def _html(title, *, article_id="TSB-42", vehicle="2019 Cadillac Escalade ESV"):
    return f"""
    <!doctype html>
    <html>
      <head>
        <title>{title}</title>
        <meta property="og:title" content="{title}">
        <meta name="article:id" content="{article_id}">
        <meta name="article:section" content="Service Bulletins">
        <meta name="article:published_time" content="2024-01-02">
        <meta name="vehicle" content="{vehicle}">
      </head>
      <body><article><h1>{title}</h1><p>Inspect the brake connector.</p></article></body>
    </html>
    """.encode()


class VehicleArticleIntakeTests(unittest.TestCase):
    def test_http_article_extracts_facts_with_source_provenance_and_vehicle_association(self):
        resource = SourceResource.from_bytes(
            "https://source.example/articles/tsb-42",
            "etag-42",
            _html("Brake connector service bulletin"),
            "text/html",
        )
        connector = _StaticConnector([resource])

        result = ingest_vehicle_article(
            "https://source.example/articles/tsb-42",
            TARGET,
            connector=connector,
        )

        self.assertEqual(connector.requests, [{"source_uri": "https://source.example/articles/tsb-42"}])
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.bundle.vehicle["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(len(result.bundle.articles), 1)
        article = result.bundle.articles[0]
        self.assertEqual(article["article_id"], "TSB-42")
        self.assertEqual(article["title"], "Brake connector service bulletin")
        self.assertEqual(article["bucket"], "Service Bulletins")
        self.assertEqual(article["release_date"], "2024-01-02")
        self.assertIn("Inspect the brake connector.", article["body"])
        self.assertEqual(article["content_locator"], "html:article")
        evidence = result.bundle.evidence
        self.assertTrue(any(item["source_uri"] == resource.source_uri for item in evidence))
        self.assertTrue(any(item["content_sha256"] == resource.content_sha256 for item in evidence))

    def test_article_for_a_different_vehicle_is_rejected_before_publication(self):
        resource = SourceResource.from_bytes(
            "https://source.example/articles/other",
            "other-v1",
            _html(
                "Brake connector service bulletin",
                vehicle="2020 Cadillac Escalade ESV",
            ),
            "text/html",
        )

        result = ingest_vehicle_article(
            resource.source_uri,
            TARGET,
            connector=_StaticConnector([resource]),
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.rejection_reason, "vehicle_identity_mismatch")
        self.assertIsNone(result.bundle.vehicle)
        self.assertEqual(result.bundle.articles, ())
        self.assertTrue(any(item["reason"] == "vehicle_identity_mismatch" for item in result.bundle.quarantined))

    def test_json_ld_article_and_vehicle_facts_are_recognized_without_provider_specific_api_fields(self):
        payload = b"""
        <html><head><script type="application/ld+json">
        {"@type":"TechArticle","headline":"Brake connector service bulletin",
         "identifier":"TSB-42","articleSection":"Service Bulletins",
         "datePublished":"2024-01-02",
         "steps":["Verify connector","Replace terminal"],
         "about":{"@type":"Vehicle","name":"2019 Cadillac Escalade ESV"}}
        </script></head><body><article><p>Inspect the connector.</p></article></body></html>
        """
        resource = SourceResource.from_bytes(
            "https://source.example/articles/json-ld",
            "json-ld-v1",
            payload,
            "text/html",
        )

        result = ingest_vehicle_article(
            resource.source_uri,
            TARGET,
            connector=_StaticConnector([resource]),
        )

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(result.bundle.articles[0]["release_date"], "2024-01-02")
        self.assertEqual(
            result.bundle.articles[0]["steps"],
            ["Verify connector", "Replace terminal"],
        )
        self.assertEqual(result.bundle.vehicle["vehicle_key"], TARGET.vehicle_key)

    def test_same_article_id_is_merged_deterministically_without_duplicate_records(self):
        resources = [
            SourceResource.from_bytes(
                "https://one.example/tsb-42",
                "v1",
                _html("Brake connector service bulletin", article_id="TSB-42"),
                "text/html",
            ),
            SourceResource.from_bytes(
                "https://two.example/tsb-42",
                "v2",
                _html("Brake connector service bulletin", article_id="TSB-42"),
                "text/html",
            ),
        ]

        bundle = normalize_source_bundle(
            [adapt_source_resource(resource) for resource in resources],
            "US",
            expected_vehicle=TARGET.as_dict(),
        )

        self.assertEqual(len(bundle.articles), 1)
        self.assertEqual(bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(bundle.articles[0]["duplicate_count"], 2)
        self.assertEqual(len(bundle.articles[0]["evidence_ids"]), 2)
        self.assertEqual(bundle.quarantined, ())

    def test_same_title_different_ids_at_or_above_095_are_quarantined_for_review(self):
        resources = [
            SourceResource.from_bytes(
                "https://one.example/tsb-42",
                "v1",
                _html("Brake connector service bulletin", article_id="TSB-42"),
                "text/html",
            ),
            SourceResource.from_bytes(
                "https://two.example/tsb-43",
                "v2",
                _html("Brake connector service bulletin", article_id="TSB-43"),
                "text/html",
            ),
        ]

        bundle = normalize_source_bundle(
            [adapt_source_resource(resource) for resource in resources],
            "US",
            expected_vehicle=TARGET.as_dict(),
        )

        self.assertEqual(len(bundle.articles), 1)
        self.assertEqual(bundle.articles[0]["article_id"], "TSB-42")
        self.assertTrue(any(item["reason"] == "similar_article_requires_review" for item in bundle.quarantined))
        similarity_conflicts = [item for item in bundle.conflicts if item["kind"] == "article_similarity"]
        self.assertEqual(len(similarity_conflicts), 1)
        self.assertGreaterEqual(similarity_conflicts[0]["similarity"], ARTICLE_SIMILARITY_THRESHOLD)
        self.assertEqual(ARTICLE_SIMILARITY_THRESHOLD, 0.95)


if __name__ == "__main__":
    unittest.main()
