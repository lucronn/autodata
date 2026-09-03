import sys
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.ocr import OCRTextBlock  # noqa: E402
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
            SourceResource.from_bytes(
                "provider://vehicle/specifications",
                "source-v1",
                b'{"body":{"specifications":{"engine_displacement_l":{"value":6.2,"unit":"L"}}}}',
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
        self.assertEqual(bundle.specifications[0]["name"], "engine_displacement_l")
        self.assertEqual(bundle.specifications[0]["value"], 6.2)
        self.assertEqual(bundle.specifications[0]["unit"], "L")
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

    def test_literal_document_text_is_retained_as_searchable_evidence(self):
        resources = [
            SourceResource.from_bytes(
                "provider://vehicle/name",
                "source-v1",
                b'{"body":"2019 Cadillac Escalade ESV"}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/procedure.html",
                "source-v1",
                b"<html><body>Inspect the brake connector before service.</body></html>",
                "text/html",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        html_hash = resources[1].content_sha256
        document_evidence = [item for item in bundle.evidence if item["content_sha256"] == html_hash]
        self.assertEqual(len(document_evidence), 1)
        self.assertEqual(
            document_evidence[0]["extracted_text"],
            "Inspect the brake connector before service.",
        )
        self.assertEqual(document_evidence[0]["reviewer_state"], "pending")

    def test_ocr_evidence_preserves_provider_confidence(self):
        image = SourceResource.from_bytes(
            "provider://vehicle/wiring.png",
            "source-v1",
            b"image bytes",
            "image/png",
        )
        identity = SourceResource.from_bytes(
            "provider://vehicle/name",
            "source-v1",
            b'{"body":"2019 Cadillac Escalade ESV"}',
            "application/json",
        )

        with patch(
            "autodata_ingestion.source_adapters.extract_image_text",
            return_value=(OCRTextBlock("C101", 0.88, (1, 2, 30, 10)),),
        ):
            bundle = normalize_source_bundle(
                [adapt_source_resource(identity), adapt_source_resource(image)], "US"
            )

        image_evidence = [item for item in bundle.evidence if item["content_sha256"] == image.content_sha256]
        self.assertEqual(len(image_evidence), 1)
        self.assertEqual(image_evidence[0]["confidence"], 0.88)
        self.assertEqual(image_evidence[0]["extracted_text"], "C101")

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

    def test_price_parser_accepts_grouped_currency_amounts(self):
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
                b'{"body":[{"partNumber":"p1","partDescription":"Part","quantity":1,"price":"$1,021.96"}]}',
                "application/json",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.parts[0]["price_minor"], 102196)
        self.assertEqual(bundle.parts[0]["currency"], "USD")
        self.assertEqual(bundle.parts[0]["price_status"], "normalized")
        self.assertEqual(bundle.quarantined, ())

    def test_conflicting_vehicle_identities_are_explicit_and_evidence_linked(self):
        resources = [
            SourceResource.from_bytes(
                "provider-a://vehicle/name",
                "source-a-v1",
                b'{"body":"2019 Cadillac Escalade ESV"}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider-b://vehicle/name",
                "source-b-v1",
                b'{"body":"2020 Cadillac Escalade ESV"}',
                "application/json",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        self.assertEqual(bundle.status, "needs_review")
        self.assertIsNone(bundle.vehicle)
        self.assertEqual(len(bundle.conflicts), 1)
        conflict = bundle.conflicts[0]
        self.assertEqual(conflict["kind"], "vehicle_identity")
        self.assertEqual(conflict["field"], "year/make/model")
        self.assertEqual(len(conflict["candidates"]), 2)
        self.assertEqual(len(conflict["evidence_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
