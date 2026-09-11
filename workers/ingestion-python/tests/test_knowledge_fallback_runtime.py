import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from autodata_ingestion.article_intake import VehicleTarget
from autodata_ingestion.knowledge_fallback_runtime import (
    ConfiguredKnowledgeSourceResolver,
    _source_configuration,
)


class KnowledgeFallbackRuntimeTests(unittest.TestCase):
    target = VehicleTarget("Toyota", "Corolla", 2024, "US")

    def test_explicit_source_hint_wins_over_template(self):
        with patch.dict(
            os.environ,
            {"AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE": "https://template.test/{vehicle_key}"},
            clear=False,
        ):
            uri, version = _source_configuration(
                self.target, "brake caliper", ("brake", "caliper"),
                {"source_uri": "https://source.test/article", "source_version": "v7"},
            )
        self.assertEqual(uri, "https://source.test/article")
        self.assertEqual(version, "v7")

    def test_template_receives_canonical_vehicle_and_query_values(self):
        with patch.dict(
            os.environ,
            {
                "AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE": (
                    "https://source.test/{region}/{vehicle_key}?q={query}&k={keywords}"
                ),
                "AUTODATA_KNOWLEDGE_SOURCE_VERSION": "catalog-v2",
            },
            clear=False,
        ):
            resolver = ConfiguredKnowledgeSourceResolver()
            source = resolver(self.target, "brake caliper", ("brake", "caliper"))
        self.assertEqual(
            source.source_uri,
            "https://source.test/US/toyota-corolla-2024-us?q=brake caliper&k=brake,caliper",
        )
        self.assertEqual(source.source_version, "catalog-v2")
        self.assertEqual(source.connector.name, "http")

    def test_missing_source_configuration_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LookupError, "source_hint"):
                _source_configuration(self.target, "brake", ("brake",), None)

    def test_credentials_in_source_hint_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            _source_configuration(
                self.target, "brake", ("brake",), "https://user:password@source.test/article"
            )

    def test_resolver_persists_source_resources_before_returning_them(self):
        from autodata_ingestion.source_adapters import SourceResource

        captured = []
        resolver = ConfiguredKnowledgeSourceResolver(
            source_persister=lambda resources: captured.extend(resources)
        )
        source = resolver(self.target, "brake", ("brake",), "https://source.test/article")
        resource = SourceResource.from_bytes(
            "https://source.test/article",
            "source-v1",
            b'{"body": {"documentId": "a1"}}',
            "application/json",
        )
        from autodata_ingestion import knowledge_fallback_runtime as runtime

        with patch.object(runtime.HttpSourceConnector, "fetch", return_value=[resource]) as fetch:
            returned = source.connector.fetch({"source_uri": source.source_uri})
            self.assertEqual(returned, [resource])
            fetch.assert_called_once()
        # The configured persister is attached to the connector boundary and
        # receives the exact immutable resources that will be normalized.
        self.assertEqual(captured, [resource])

    def test_fulfillment_exposes_source_unnormalized_when_normalization_is_pending(self):
        from autodata_ingestion import knowledge_fallback_runtime as runtime

        envelope = {
            "event_type": "dataset.knowledge.fallback.requested",
            "event_version": 1,
            "event_id": "event-1",
            "occurred_at": "2026-09-11T12:00:00Z",
            "producer": "test",
            "request_id": "request-1",
            "projection_id": "projection-1",
            "revision_id": "revision-1",
            "correlation_id": "correlation-1",
            "idempotency_key": "fallback-1",
            "payload": {
                "vehicle_key": "toyota-corolla-2024-us",
                "region": "US",
                "query": "brake",
                "keywords": ["brake"],
                "kind": "article",
                "dataset_id": "dataset-1",
                "revision_id": "revision-1",
            },
        }
        fulfillment = {
            "status": "completed",
            "result": {
                "status": "rejected",
                "idempotency_key": "fallback-1",
                "vehicle": self.target.as_dict(),
                "query": "brake",
                "keywords": ("brake",),
                "results": (),
                "evidence": ({"evidence_id": "evidence-1"},),
                "source_uri": "https://source.test/article",
                "rejection_reason": "article_not_ready",
            },
        }
        fake_handler = type("FakeHandler", (), {"handle": lambda self, _envelope: fulfillment})()
        with patch.object(runtime, "load_revision_catalog", return_value={}), patch.object(
            runtime, "KnowledgeFallbackFulfillmentHandler", return_value=fake_handler
        ):
            result = runtime.fulfill_once(envelope)

        self.assertEqual(result["result"]["status"], "source_unnormalized")
        self.assertEqual(result["result"]["data_state"], "source_unnormalized")
        self.assertEqual(result["result"]["source_uri"], "https://source.test/article")


if __name__ == "__main__":
    unittest.main()
