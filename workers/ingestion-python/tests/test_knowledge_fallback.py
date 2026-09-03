import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.article_intake import VehicleTarget  # noqa: E402
from autodata_ingestion.knowledge_fallback import (  # noqa: E402
    ResolvedSource,
    query_vehicle_knowledge,
)
from autodata_ingestion.source_adapters import SourceResource  # noqa: E402


TARGET = VehicleTarget("Cadillac", "Escalade ESV", 2019, "US")


class _StaticConnector:
    name = "test-source"

    def __init__(self, resources):
        self.resources = resources
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        return list(self.resources)


def _html(*, vehicle="2019 Cadillac Escalade ESV", article_id="TSB-42"):
    return f"""
    <!doctype html>
    <html>
      <head>
        <title>Brake connector service bulletin</title>
        <meta property="og:title" content="Brake connector service bulletin">
        <meta name="article:id" content="{article_id}">
        <meta name="article:section" content="Service Bulletins">
        <meta name="article:published_time" content="2024-01-02">
        <meta name="vehicle" content="{vehicle}">
      </head>
      <body><article><h1>Brake connector service bulletin</h1>
        <p>Inspect the brake connector.</p>
      </article></body>
    </html>
    """.encode()


class KnowledgeFallbackTests(unittest.TestCase):
    def test_catalog_hit_returns_normalized_article_without_calling_resolver(self):
        resolver_calls = []
        catalog = [
            {
                "vehicle_key": TARGET.vehicle_key,
                "kind": "article",
                "id": "TSB-42",
                "article": {
                    "article_id": "TSB-42",
                    "article_key": "article:TSB-42",
                    "title": "Brake connector service bulletin",
                    "body": "Inspect the brake connector.",
                },
                "evidence": [
                    {
                        "evidence_id": "evidence-42",
                        "locator": "body.articleDetails[0]",
                        "source_uri": "provider://catalog/tsb-42",
                        "source_version": "catalog-v1",
                        "confidence": 0.98,
                    }
                ],
            }
        ]

        def resolver(*args, **kwargs):
            resolver_calls.append((args, kwargs))
            raise AssertionError("a catalog hit must not resolve a source")

        result = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            keywords=["service", "connector"],
            catalog=catalog,
            source_resolver=resolver,
        )

        self.assertEqual(result.status, "cache_hit")
        self.assertEqual(resolver_calls, [])
        self.assertEqual(result.results[0]["kind"], "article")
        self.assertEqual(result.results[0]["article"]["article_id"], "TSB-42")
        self.assertEqual(result.results[0]["evidence"][0]["evidence_id"], "evidence-42")
        self.assertEqual(result.results[0]["evidence"][0]["source_uri"], "provider://catalog/tsb-42")

    def test_catalog_miss_resolves_and_fetches_a_vehicle_article(self):
        source_uri = "https://source.example/articles/tsb-42"
        connector = _StaticConnector(
            [SourceResource.from_bytes(source_uri, "etag-42", _html(), "text/html")]
        )
        resolver_calls = []

        def resolver(target, query, keywords):
            resolver_calls.append((target, query, keywords))
            return ResolvedSource(source_uri, connector)

        result = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            keywords=["service", "connector"],
            catalog=[],
            source_resolver=resolver,
        )

        self.assertEqual(result.status, "fetched")
        self.assertEqual(resolver_calls, [(TARGET, "brake connector", ("connector", "service"))])
        self.assertEqual(connector.requests, [{"source_uri": source_uri}])
        self.assertEqual(result.results[0]["article"]["article_id"], "TSB-42")
        self.assertTrue(
            any(
                evidence["source_uri"] == source_uri
                for evidence in result.results[0]["evidence"]
            )
        )

    def test_fetched_article_for_another_vehicle_is_rejected(self):
        source_uri = "https://source.example/articles/other"
        connector = _StaticConnector(
            [
                SourceResource.from_bytes(
                    source_uri,
                    "other-v1",
                    _html(vehicle="2020 Cadillac Escalade ESV"),
                    "text/html",
                )
            ]
        )

        result = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            catalog=[],
            source_resolver=lambda target, query, keywords: ResolvedSource(
                source_uri, connector
            ),
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.rejection_reason, "vehicle_identity_mismatch")
        self.assertEqual(result.results, ())
        self.assertTrue(
            any(
                evidence["source_uri"] == source_uri
                for evidence in result.evidence
            )
        )

    def test_replaying_the_same_miss_is_deterministic(self):
        source_uri = "https://source.example/articles/tsb-42"
        connector = _StaticConnector(
            [SourceResource.from_bytes(source_uri, "etag-42", _html(), "text/html")]
        )

        def resolver(target, query, keywords):
            return ResolvedSource(source_uri, connector)

        first = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            keywords=["service", "connector"],
            catalog=[],
            source_resolver=resolver,
        )
        replay = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            keywords=["connector", "service"],
            catalog=[],
            source_resolver=resolver,
        )

        self.assertEqual(first.idempotency_key, replay.idempotency_key)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True),
            json.dumps(replay.to_dict(), sort_keys=True),
        )

    def test_fetched_source_still_requires_a_query_match(self):
        source_uri = "https://source.example/articles/unrelated"
        unrelated = _html().replace(b"Brake connector", b"Oil filter")
        connector = _StaticConnector(
            [SourceResource.from_bytes(source_uri, "unrelated-v1", unrelated, "text/html")]
        )

        result = query_vehicle_knowledge(
            TARGET,
            "airbag wiring",
            catalog=[],
            source_resolver=lambda target, query, keywords: ResolvedSource(
                source_uri, connector
            ),
        )

        self.assertEqual(result.status, "fetched")
        self.assertEqual(result.results, ())

    def test_kind_filter_keeps_the_normalized_result_type_vehicle_scoped(self):
        catalog = [
            {
                "vehicle_key": TARGET.vehicle_key,
                "kind": "article",
                "article": {
                    "article_id": "TSB-42",
                    "title": "Brake connector service bulletin",
                },
                "evidence": [],
            },
            {
                "vehicle_key": TARGET.vehicle_key,
                "kind": "procedure",
                "procedure": {
                    "procedure_id": "PROC-42",
                    "section": "brakes",
                    "excerpt": "Inspect the brake connector.",
                },
                "evidence": [],
            },
        ]

        result = query_vehicle_knowledge(
            TARGET,
            "brake connector",
            catalog=catalog,
            source_resolver=lambda target, query, keywords: (_ for _ in ()).throw(
                AssertionError("the article catalog hit must not fetch")
            ),
            kind="procedure",
        )

        self.assertEqual(result.status, "cache_hit")
        self.assertEqual([item["kind"] for item in result.results], ["procedure"])


if __name__ == "__main__":
    unittest.main()
