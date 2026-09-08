import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import (  # noqa: E402
    VehicleTarget,
    ingest_vehicle_article,
)
from autodata_ingestion.source_adapters import (  # noqa: E402
    NormalizationCandidate,
    SourceResource,
    adapt_source_resource,
)
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
    def test_unknown_json_article_uses_opt_in_mercury_extraction(self):
        from autodata_ingestion.mercury2 import Mercury2SourceExtractor
        from unittest.mock import patch

        resource = SourceResource.from_bytes(
            "https://source.example/unknown.json",
            "source-v1",
            b'{"providerPayload":{"headline":"Brake connector bulletin"}}',
            "application/json",
        )
        candidates = (
            NormalizationCandidate(
                "vehicle_identity",
                "mercury2:vehicle_identity:stable",
                {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500"},
                "providerPayload.vehicle",
            ),
            NormalizationCandidate(
                "article",
                "mercury2:article:stable",
                {
                    "id": "TSB-42",
                    "title": "Brake connector bulletin",
                    "body": "Inspect the brake connector.",
                },
                "providerPayload.article",
            ),
        )
        with patch.dict("os.environ", {"AUTODATA_MERCURY2_EXTRACTION_ENABLED": "1"}, clear=False):
            with patch(
                "autodata_ingestion.mercury2.Mercury2Client.from_environment",
                return_value=object(),
            ):
                with patch.object(Mercury2SourceExtractor, "extract", return_value=candidates):
                    result = ingest_vehicle_article(
                        resource.source_uri,
                        VehicleTarget("Chevy", "Silverado 1500", 1999, "US"),
                        connector=_StaticConnector([resource]),
                    )

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(result.artifacts[0].metadata["extraction_mode"], "mercury-2")

    def test_vehicle_target_canonicalizes_chevy_alias_for_stable_key(self):
        target = VehicleTarget("Chevy", "Silverado 1500", 1999, "US")

        self.assertEqual(target.make, "Chevrolet")
        self.assertEqual(target.vehicle_key, "chevrolet-silverado-1500-1999-us")

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

    def test_article_for_a_different_configuration_is_rejected_before_publication(self):
        target = VehicleTarget(
            "Chevy",
            "Silverado 1500",
            1999,
            "US",
            drivetrain="2wd",
            engine_displacement_l="5.3LT",
        )
        resource = SourceResource.from_bytes(
            "https://source.example/articles/wrong-configuration",
            "wrong-configuration-v1",
            b'{"body":{"year":1999,"make":"Chevrolet","model":"Silverado 1500",'
            b'"region":"US","drivetrain":"4WD","engine":"4.8L",'
            b'"articleDetails":[{"id":"TSB-43","title":"Brake connector bulletin"}]}}',
            "application/json",
        )

        result = ingest_vehicle_article(
            resource.source_uri,
            target,
            connector=_StaticConnector([resource]),
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.rejection_reason, "vehicle_identity_mismatch")
        self.assertIsNone(result.bundle.vehicle)
        self.assertEqual(result.bundle.articles, ())
        conflict = next(
            item for item in result.bundle.conflicts
            if item["field"] == "target_vehicle"
        )
        self.assertEqual(conflict["candidate"]["drivetrain"], "4WD")

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

    def test_vehicle_aliases_are_canonicalized_before_target_association(self):
        resource = SourceResource.from_bytes(
            "https://source.example/articles/chevy",
            "chevy-v1",
            _html("Brake connector service bulletin", vehicle="2019 Chevy Escalade ESV"),
            "text/html",
        )

        result = ingest_vehicle_article(
            resource.source_uri,
            VehicleTarget("Chevy", "Escalade ESV", 2019, "US"),
            connector=_StaticConnector([resource]),
        )

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.bundle.vehicle["make"], "Chevrolet")
        self.assertEqual(result.bundle.vehicle["vehicle_key"], "chevrolet-escalade-esv-2019-us")

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
                _html("Brake bulletin", article_id="TSB-42"),
                "text/html",
            ),
            SourceResource.from_bytes(
                "https://two.example/tsb-43",
                "v2",
                _html("Brake bulletin", article_id="TSB-43"),
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
