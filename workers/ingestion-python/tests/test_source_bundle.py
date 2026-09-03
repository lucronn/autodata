import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


class SourceBundleTests(unittest.TestCase):
    def test_normalizes_cross_resource_vehicle_bundle_with_evidence(self):
        resources = [
            SourceResource.from_bytes(
                "provider://vehicle/name",
                "source-v1",
                b'{"header":{"statusCode":200},"body":"2019 Cadillac Escalade ESV - 2WD"}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/models",
                "source-v1",
                b'{"body":[{"id":"168702","model":"Escalade ESV Base","engines":[{"id":"e1","name":"6.2L V8"}]}]}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/parts",
                "source-v1",
                b'{"body":[{"partNumber":"22943127","partDescription":"Power outlet","quantity":1,"price":"$46.99"}]}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/articles",
                "source-v1",
                b'{"body":{"articleDetails":[{"id":"6158075","bucket":"Technical Service Bulletins","title":"Example"}]}}',
                "application/json",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.vehicle["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(bundle.vehicle["trim"], "2WD")
        self.assertEqual(bundle.models[0]["provider_model_id"], "168702")
        self.assertEqual(bundle.powertrains[0]["provider_powertrain_id"], "e1")
        self.assertEqual(bundle.parts[0]["price_minor"], 4699)
        self.assertEqual(bundle.articles[0]["article_id"], "6158075")
        self.assertGreaterEqual(len(bundle.evidence), 4)
        self.assertTrue(all(item["content_sha256"] for item in bundle.evidence))

    def test_unrecognized_resource_is_retained_and_blocks_ready_status(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/new-shape",
            "source-v1",
            b'{"body":{"newProviderField":42}}',
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(bundle.status, "needs_review")
        self.assertEqual(bundle.quarantined[0]["reason"], "no_typed_candidates")
        self.assertEqual(bundle.quarantined[0]["content_sha256"], resource.content_sha256)

    def test_price_parser_rejects_ambiguous_currency_instead_of_guessing(self):
        resources = [
            SourceResource.from_bytes(
                "provider://vehicle/name",
                "source-v1",
                b'{"body":"2019 Cadillac Escalade ESV - 2WD"}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/parts",
                "source-v1",
                b'{"body":[{"partNumber":"p1","partDescription":"Part","quantity":1,"price":"100"}]}',
                "application/json",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        self.assertEqual(bundle.status, "needs_review")
        self.assertEqual(bundle.parts[0]["price_minor"], None)
        self.assertEqual(bundle.parts[0]["price_status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
