import unittest
from base64 import b64decode

from autodata_ingestion.guide_pdf import render_guide_pdf

try:
    import reportlab  # noqa: F401
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


class GuidePdfTests(unittest.TestCase):
    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is installed by the ingestion image")
    def test_pdf_contains_installation_content_and_embedded_figure(self):
        guide = {
            "title": "Water Pump Replacement Guide",
            "applicability": "1997 Toyota RAV4",
            "content_status": "complete",
            "pdf_ready": True,
            "steps": [{"sequence": 1, "action": "Install the pump and gasket.", "instructions": ["Tighten the bolts to 8.8 Nm."], "images": [{"url": "https://example.test/figure.png", "alt": "Pump figure", "image_bytes": b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")}]}],
            "warnings": [],
            "images": [],
        }
        pdf = render_guide_pdf(guide)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        from io import BytesIO
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
        self.assertIn("Install the pump and gasket.", text)
        self.assertTrue(any(image for page in PdfReader(BytesIO(pdf)).pages for image in page.images))

    def test_partial_guide_cannot_be_rendered_as_final_pdf(self):
        with self.assertRaises(ValueError):
            render_guide_pdf({"content_status": "partial", "pdf_ready": False})
