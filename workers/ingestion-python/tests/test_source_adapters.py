import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_adapters import (  # noqa: E402
    SourceResource,
    adapt_source_resource,
    classify_json_candidates,
)


class SourceAdapterTests(unittest.TestCase):
    def test_resource_detects_media_type_and_preserves_content_address(self):
        resource = SourceResource.from_bytes(
            source_uri="https://source.example/vehicle.json",
            source_version="2026-09-03T12:00:00Z",
            payload=b'{"vehicle":{"make":"Cadillac"}}',
            media_type=None,
        )

        self.assertEqual(resource.media_type, "application/json")
        self.assertEqual(len(resource.content_sha256), 64)
        self.assertEqual(resource.content_sha256, SourceResource.from_bytes(
            source_uri="other://same-content",
            source_version="different",
            payload=resource.payload,
            media_type="application/json",
        ).content_sha256)

    def test_json_api_envelope_is_unwrapped_without_losing_header_provenance(self):
        resource = SourceResource.from_bytes(
            source_uri="https://source.example/name.json",
            source_version="v1",
            payload=b'{"header":{"status":"OK","statusCode":200},"body":"2019 Cadillac Escalade ESV - 2WD"}',
            media_type="application/json",
        )

        artifact = adapt_source_resource(resource)

        self.assertEqual(artifact.kind, "structured")
        self.assertEqual(artifact.metadata["response_status_code"], 200)
        self.assertEqual(artifact.payload["body"], "2019 Cadillac Escalade ESV - 2WD")

        candidates = classify_json_candidates(artifact.payload)
        self.assertEqual(candidates[0].kind, "vehicle_identity")
        self.assertEqual(candidates[0].data["year"], 2019)
        self.assertEqual(candidates[0].data["make"], "Cadillac")
        self.assertEqual(candidates[0].data["model"], "Escalade ESV")
        self.assertEqual(candidates[0].data["trim"], "2WD")

    def test_media_types_are_classified_and_unknown_content_is_quarantined(self):
        expected = {
            "text/html": "document",
            "application/pdf": "document",
            "image/svg+xml": "diagram",
            "application/xml": "structured",
            "text/csv": "structured",
            "application/octet-stream": "quarantine",
        }
        for media_type, kind in expected.items():
            with self.subTest(media_type=media_type):
                resource = SourceResource.from_bytes(
                    source_uri=f"https://source.example/resource?type={media_type}",
                    source_version="v1",
                    payload=b"<svg/>" if media_type == "image/svg+xml" else b"payload",
                    media_type=media_type,
                )
                self.assertEqual(adapt_source_resource(resource).kind, kind)

    def test_media_type_sniffing_handles_html_and_pdf_without_headers(self):
        html = SourceResource.from_bytes(
            "https://source.example/document",
            "v1",
            b"<!doctype html><html><body>procedure</body></html>",
            None,
        )
        pdf = SourceResource.from_bytes("https://source.example/document", "v1", b"%PDF-1.7", None)

        self.assertEqual(html.media_type, "text/html")
        self.assertEqual(pdf.media_type, "application/pdf")

    def test_sample_shaped_json_yields_typed_candidates(self):
        payload = {
            "body": {
                "articleDetails": [{"id": "6158075", "bucket": "Technical Service Bulletins", "title": "Example"}],
                "parts": [{"partNumber": "22943127", "partDescription": "Outlet", "quantity": 1, "price": "$46.99"}],
                "models": [{"id": "168702", "model": "Escalade ESV Base", "engines": [{"id": "e1", "name": "6.2L V8"}]}],
            }
        }

        candidates = classify_json_candidates(payload)

        self.assertEqual([candidate.kind for candidate in candidates], ["article", "part", "model"])
        self.assertEqual(candidates[0].key, "article:6158075")
        self.assertEqual(candidates[1].key, "part:22943127")
        self.assertEqual(candidates[2].key, "model:168702")

    def test_valid_but_unrecognized_json_is_retained_for_review(self):
        resource = SourceResource.from_bytes(
            "https://source.example/new-shape",
            "v1",
            b'{"newProviderField":{"value":42}}',
            "application/json",
        )

        artifact = adapt_source_resource(resource)

        self.assertEqual(artifact.kind, "structured")
        self.assertEqual(artifact.metadata["extraction_status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
