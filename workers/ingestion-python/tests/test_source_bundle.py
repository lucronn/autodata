import base64
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.ocr import OCRTextBlock  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


class SourceBundleTests(unittest.TestCase):
    def test_exact_article_id_replay_merges_later_content_after_other_articles(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/articles.json",
            "source-v1",
            (
                b'{"body":{"articleDetails":['
                b'{"id":"TSB-1","title":"Alpha bulletin"},'
                b'{"id":"TSB-2","title":"Beta bulletin","body":"Inspect the battery."},'
                b'{"id":"TSB-1","title":"Zeta bulletin",'
                b'"body":"Inspect the connector before service."}'
                b']}}'
            ),
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(len(bundle.articles), 2)
        first = next(article for article in bundle.articles if article["article_id"] == "TSB-1")
        self.assertEqual(first["body"], "Inspect the connector before service.")
        self.assertEqual(first["duplicate_count"], 2)

    def test_near_duplicate_article_bodies_are_quarantined_even_when_titles_differ(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/articles.json",
            "source-v1",
            (
                b'{"body":{"articleDetails":['
                b'{"id":"TSB-1","title":"Brake connector service bulletin",'
                b'"body":"Inspect the brake connector before service. Remove the retaining clip and replace the terminal if damaged."},'
                b'{"id":"TSB-2","title":"Brake connector replacement bulletin",'
                b'"body":"Inspect the brake connector before service. Remove the retaining clip and replace the terminal if damaged."}'
                b']}}'
            ),
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(len(bundle.articles), 1)
        self.assertIn(bundle.articles[0]["article_id"], {"TSB-1", "TSB-2"})
        self.assertTrue(
            any(item.get("reason") == "similar_article_requires_review" for item in bundle.quarantined)
        )

    def test_generic_json_article_record_preserves_body_and_steps(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/article.json",
            "source-v1",
            (
                b'{"body":{"type":"article","article_id":"TSB-99",'
                b'"title":"Brake connector procedure",'
                b'"body":"Inspect the connector before service.",'
                b'"steps":["Inspect connector","Replace terminal"]}}'
            ),
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(len(bundle.articles), 1)
        self.assertEqual(bundle.articles[0]["article_id"], "TSB-99")
        self.assertEqual(
            bundle.articles[0]["body"],
            "Inspect the connector before service.",
        )
        self.assertEqual(
            bundle.articles[0]["steps"],
            ["Inspect connector", "Replace terminal"],
        )

    def test_normalized_article_preserves_source_images_for_downstream_persistence(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/article-with-images.json",
            "source-v1",
            (
                b'{"body":{"type":"article","article_id":"TSB-IMAGE-1",'
                b'"title":"Alternator replacement",'
                b'"body":"Disconnect the battery before service.",'
                b'"images":[{"url":"https://source.test/alternator.png",'
                b'"alt":"Alternator connector diagram"}]}}'
            ),
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(
            bundle.articles[0]["images"],
            [{
                "url": "https://source.test/alternator.png",
                "alt": "Alternator connector diagram",
            }],
        )

    def test_html_article_images_are_normalized_with_resolved_source_urls(self):
        resource = SourceResource.from_bytes(
            "https://source.test/guides/alternator.html",
            "source-v1",
            (
                b"<html><head><meta property='og:title' content='Alternator replacement'></head>"
                b"<body><article><p>Disconnect the battery.</p>"
                b"<img src='../media/alternator.png' alt='Connector diagram'></article></body></html>"
            ),
            "text/html",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(
            bundle.articles[0]["images"],
            [{
                "url": "https://source.test/media/alternator.png",
                "alt": "Connector diagram",
            }],
        )

    def test_coarse_identity_is_enriched_by_a_later_structured_identity_record(self):
        resources = [
            SourceResource.from_bytes(
                "provider://vehicle/name",
                "source-v1",
                b'{"body":"99 Chevy Silverado 1500"}',
                "application/json",
            ),
            SourceResource.from_bytes(
                "provider://vehicle/fitment",
                "source-v1",
                b'{"year":1999,"make":"Chevrolet","model":"Silverado 1500",'
                b'"region":"US","drivetrain":"2wd","engine":"5.3LT"}',
                "application/json",
            ),
        ]

        bundle = normalize_source_bundle([adapt_source_resource(resource) for resource in resources], "US")

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.vehicle["vehicle_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(bundle.vehicle["drivetrain"], "2WD")
        self.assertEqual(bundle.vehicle["engine_displacement_l"], 5.3)

    def test_structured_vehicle_dimensions_survive_normalization_and_aliasing(self):
        resource = SourceResource.from_bytes(
            "provider://vehicle/identity.json",
            "source-v1",
            (
                b'{"vehicle":{"year":"99","manufacturer":"Chevy",'
                b'"model":"Silverado-1500","market":"US",'
                b'"bodyStyle":"Pickup","driveType":"4x2",'
                b'"engineDisplacementL":"5.3LT"}}'
            ),
            "application/json",
        )

        bundle = normalize_source_bundle([adapt_source_resource(resource)], "US")

        self.assertEqual(bundle.status, "ready")
        self.assertIsNotNone(bundle.vehicle)
        self.assertEqual(bundle.vehicle["vehicle_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(bundle.vehicle["make"], "Chevrolet")
        self.assertEqual(bundle.vehicle["model"], "Silverado 1500")
        self.assertEqual(bundle.vehicle["model_year"], 1999)
        self.assertEqual(bundle.vehicle["body_style"], "Pickup")
        self.assertEqual(bundle.vehicle["drivetrain"], "2WD")
        self.assertEqual(bundle.vehicle["engine_displacement_l"], 5.3)
        self.assertTrue(bundle.vehicle["evidence_id"])

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

    def test_autoapi_document_body_is_linked_to_the_matching_article_index_record(self):
        index_resource = SourceResource.from_bytes(
            "file://v2.json",
            "autoapi-v1",
            b'{"header":{"status":"OK"},"body":{"articleDetails":[{"id":"3950424:12924016","bucket":"Other Diagnostics","title":"A/C System Performance Test"}]}}',
            "application/json",
        )
        document_resource = SourceResource.from_bytes(
            "file://3950424_12924016.json",
            "autoapi-v1",
            b'{"header":{"status":"OK"},"body":{"documentId":"3950424","html":"<html><body><p>Check compressor operation.</p></body></html>"}}',
            "application/json",
        )

        bundle = normalize_source_bundle(
            [adapt_source_resource(index_resource), adapt_source_resource(document_resource)],
            "US",
        )

        self.assertEqual(len(bundle.articles), 1)
        article = bundle.articles[0]
        self.assertEqual(article["article_id"], "3950424:12924016")
        self.assertIn("Check compressor operation.", article["body"])
        self.assertEqual(article["content_locator"], "body.html:3950424")
        self.assertIn(article["content_evidence_id"], {item["evidence_id"] for item in bundle.evidence})
        self.assertNotEqual(article["content_evidence_id"], article["evidence_id"])

    def test_autoapi_pdf_pages_are_joined_with_aggregate_content_evidence(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _stream):
                self.pages = [FakePage("Page one"), FakePage("Page two")]

        index_resource = SourceResource.from_bytes(
            "file://v2.json",
            "autoapi-v1",
            b'{"body":{"articleDetails":[{"id":"8:pdf-1","title":"PDF procedure"}]}}',
            "application/json",
        )
        encoded_pdf = base64.b64encode(b"%PDF-1.7 test").decode()
        document_resource = SourceResource.from_bytes(
            "file://P_8.json",
            "autoapi-v1",
            (
                '{"body":{"documentId":"8","pdf":"'
                + encoded_pdf
                + '"}}'
            ).encode(),
            "application/json",
        )

        with patch.dict(sys.modules, {"pypdf": types.SimpleNamespace(PdfReader=FakeReader)}):
            bundle = normalize_source_bundle(
                [adapt_source_resource(index_resource), adapt_source_resource(document_resource)],
                "US",
            )

        article = bundle.articles[0]
        self.assertEqual(article["article_id"], "8:pdf-1")
        self.assertEqual(article["body"], "Page one\n\nPage two")
        self.assertEqual(
            article["content_locator"],
            "body.pdf:8:page:1..body.pdf:8:page:2",
        )
        aggregate = next(
            item
            for item in bundle.evidence
            if item["evidence_id"] == article["content_evidence_id"]
        )
        self.assertEqual(aggregate["extracted_text"], "Page one\n\nPage two")

    def test_embedded_guide_links_mtr_image_to_the_original_diagram_artifact(self):
        index_resource = SourceResource.from_bytes(
            "file://v2.json",
            "autoapi-v1",
            b'{"body":{"articleDetails":[{"id":"4942414:guide-1",'
            b'"bucket":"Wiring Diagrams","title":"Adaptive Cruise Module"}]}}',
            "application/json",
        )
        guide_resource = SourceResource.from_bytes(
            "file://4942414.json",
            "autoapi-v1",
            b'{"body":{"documentId":"4942414","html":"<h2>Adaptive Cruise Module</h2>'
            b'<mtr-image id=\'4937423\' alt=\'Module diagram\'></mtr-image>"}}',
            "application/json",
        )
        diagram_resource = SourceResource.from_bytes(
            "file://4937423.svg",
            "autoapi-v1",
            b"<svg xmlns='http://www.w3.org/2000/svg'><title>Module diagram</title></svg>",
            "image/svg+xml",
        )

        diagram_artifact = adapt_source_resource(diagram_resource)
        bundle = normalize_source_bundle(
            [
                adapt_source_resource(index_resource),
                adapt_source_resource(guide_resource),
                diagram_artifact,
            ],
            "US",
        )

        article = next(item for item in bundle.articles if item["article_id"] == "4942414:guide-1")
        assert article["images"][0]["url"] == "file://4937423.svg"
        assert article["images"][0]["alt"] == "Module diagram"
        assert article["images"][0]["artifact_key"] == diagram_artifact.object_key
        assert article["images"][0]["evidence_id"] in {
            item["evidence_id"] for item in bundle.evidence
        }

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
