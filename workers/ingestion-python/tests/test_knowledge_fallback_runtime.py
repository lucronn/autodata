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


if __name__ == "__main__":
    unittest.main()
