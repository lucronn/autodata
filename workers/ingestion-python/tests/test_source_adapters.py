import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.source_adapters import (  # noqa: E402
    SourceResource,
    adapt_source_resource,
    classify_json_candidates,
    detect_media_type,
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
        self.assertEqual(artifact.raw_payload, resource.payload)

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

    def test_content_sniffing_takes_precedence_over_misleading_file_extensions(self):
        xml = b'\xef\xbb\xbf<?xml version="1.0"?><vehicle><make>Ford</make></vehicle>'

        self.assertEqual(detect_media_type("file://drop/payload.json", xml, None), "application/xml")
        self.assertEqual(adapt_source_resource(SourceResource.from_bytes(
            "file://drop/payload.json", "v1", xml, None,
        )).kind, "structured")

    def test_html_and_svg_sniffing_accepts_utf8_bom(self):
        html = b"\xef\xbb\xbf<!doctype html><html><body>procedure</body></html>"
        svg = b"\xef\xbb\xbf<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>"

        self.assertEqual(detect_media_type("file://drop/unknown", html, None), "text/html")
        self.assertEqual(detect_media_type("file://drop/unknown", svg, None), "image/svg+xml")

    def test_path_hint_covers_delimited_text_after_content_sniffing(self):
        csv = b"part_number,description\nA-1,Connector\n"

        self.assertEqual(detect_media_type("file://drop/parts.csv", csv, None), "text/csv")

    def test_generic_declared_media_type_uses_content_signatures(self):
        json_payload = b'{"body":"2019 Cadillac Escalade ESV"}'
        html_payload = b"<!doctype html><html><body>procedure</body></html>"
        xml_payload = b"<?xml version=\"1.0\"?><vehicle><make>Ford</make></vehicle>"

        self.assertEqual(
            detect_media_type("file://drop/payload", json_payload, "application/octet-stream"),
            "application/json",
        )
        self.assertEqual(
            detect_media_type("file://drop/payload", html_payload, "text/plain"),
            "text/html",
        )
        self.assertEqual(
            detect_media_type("file://drop/payload", xml_payload, "application/octet-stream"),
            "application/xml",
        )

    def test_extensionless_delimited_text_with_generic_media_type_is_structured(self):
        csv = b"part_number,description\nA-1,Connector\n"

        self.assertEqual(
            detect_media_type("file://drop/parts", csv, "application/octet-stream"),
            "text/csv",
        )

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
        self.assertEqual(candidates[0].key, "article:6158075:0")
        self.assertEqual(candidates[1].key, "part:22943127")
        self.assertEqual(candidates[2].key, "model:168702")

    def test_common_specification_shapes_emit_typed_candidates(self):
        payload = {
            "body": {
                "make": "Cadillac",
                "model": "Escalade ESV",
                "year": 2019,
                "specifications": {
                    "engine_displacement_l": {"value": 6.2, "unit": "L"},
                    "fuel": "gasoline",
                },
            }
        }

        candidates = classify_json_candidates(payload)

        self.assertEqual([candidate.kind for candidate in candidates], [
            "vehicle_identity", "specification", "specification"
        ])
        self.assertEqual(candidates[1].data["value"], 6.2)
        self.assertEqual(candidates[1].data["unit"], "L")
        self.assertEqual(candidates[2].data["name"], "fuel")

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

    def test_csv_records_emit_conservative_vehicle_and_part_candidates(self):
        resource = SourceResource.from_bytes(
            "file://drop/catalog.csv",
            "v1",
            (
                b"record_type,make,model,year,region,partNumber,partDescription\n"
                b"vehicle,Toyota,Corolla,2024,US,,\n"
                b"part,,,,US,A-1,Oil filter\n"
            ),
            None,
        )

        artifact = adapt_source_resource(resource)

        self.assertEqual(artifact.kind, "structured")
        self.assertEqual(artifact.metadata["record_count"], 2)
        self.assertEqual([candidate.kind for candidate in artifact.candidates], ["vehicle_identity", "part"])
        self.assertEqual(artifact.candidates[0].data["make"], "Toyota")
        self.assertEqual(artifact.candidates[1].data["partNumber"], "A-1")

    def test_xml_records_emit_conservative_vehicle_and_part_candidates(self):
        resource = SourceResource.from_bytes(
            "https://source.example/catalog.xml",
            "v1",
            (
                b"<catalog><vehicle><make>Toyota</make><model>Corolla</model>"
                b"<year>2024</year><region>US</region></vehicle>"
                b"<part><partNumber>A-1</partNumber><description>Oil filter</description></part></catalog>"
            ),
            None,
        )

        artifact = adapt_source_resource(resource)

        self.assertEqual(artifact.kind, "structured")
        self.assertEqual(artifact.metadata["record_count"], 2)
        self.assertEqual([candidate.kind for candidate in artifact.candidates], ["vehicle_identity", "part"])
        self.assertEqual(artifact.candidates[0].locator, "vehicle")
        self.assertEqual(artifact.candidates[1].data["partNumber"], "A-1")

    def test_malformed_structured_content_is_retained_for_review(self):
        resource = SourceResource.from_bytes(
            "file://drop/broken.xml",
            "v1",
            b"<catalog><vehicle>",
            "application/xml",
        )

        artifact = adapt_source_resource(resource)

        self.assertEqual(artifact.kind, "structured")
        self.assertEqual(artifact.metadata["extraction_status"], "needs_review")
        self.assertIn("extraction_error", artifact.metadata)


if __name__ == "__main__":
    unittest.main()
