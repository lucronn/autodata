import sys
import types
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.ocr import OCRTextBlock  # noqa: E402
from autodata_ingestion.pdf_ocr import extract_scanned_pdf_text, rasterize_pdf_pages  # noqa: E402


class PDFOCRTests(unittest.TestCase):
    def test_rasterizer_serializes_pages_as_deterministic_png_bytes(self):
        class FakeRenderedPage:
            def save(self, stream, format):
                self.format = format
                stream.write(b"rendered-png")

        def convert_from_bytes(payload, dpi, fmt, thread_count):
            self.assertEqual(payload, b"pdf")
            self.assertEqual(dpi, 200)
            self.assertEqual(fmt, "png")
            self.assertEqual(thread_count, 1)
            return [FakeRenderedPage()]

        with patch.dict(
            sys.modules,
            {"pdf2image": types.SimpleNamespace(convert_from_bytes=convert_from_bytes)},
        ):
            self.assertEqual(rasterize_pdf_pages(b"pdf"), (b"rendered-png",))

    def test_scanned_pdf_ocr_numbers_regions_by_rendered_page(self):
        with (
            patch("autodata_ingestion.pdf_ocr.rasterize_pdf_pages", return_value=(b"page1", b"page2")),
            patch(
                "autodata_ingestion.pdf_ocr.extract_image_text",
                side_effect=(
                    (OCRTextBlock("first", 0.81, (1, 2, 3, 4)),),
                    (OCRTextBlock("second", 0.82, (5, 6, 7, 8)),),
                ),
            ) as extract_image,
        ):
            blocks = tuple(extract_scanned_pdf_text("a" * 64, b"pdf", set()))

        self.assertEqual([block.page_number for block in blocks], [1, 2])
        self.assertEqual([block.text for block in blocks], ["first", "second"])
        self.assertEqual(extract_image.call_args_list[0].args, ("a" * 64, b"page1", "image/png"))
        self.assertEqual(extract_image.call_args_list[1].args, ("a" * 64, b"page2", "image/png"))

    def test_scanned_pdf_ocr_skips_pages_with_native_text(self):
        with (
            patch("autodata_ingestion.pdf_ocr.rasterize_pdf_pages", return_value=(b"page1", b"page2")),
            patch(
                "autodata_ingestion.pdf_ocr.extract_image_text",
                return_value=(OCRTextBlock("first", 0.81, (1, 2, 3, 4)),),
            ) as extract_image,
        ):
            blocks = tuple(extract_scanned_pdf_text("b" * 64, b"pdf", {2}))

        self.assertEqual([block.page_number for block in blocks], [1])
        extract_image.assert_called_once_with("b" * 64, b"page1", "image/png")


if __name__ == "__main__":
    unittest.main()
