import sys
import types
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch


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

    def test_scanned_pdf_ocr_keeps_original_page_numbers_in_shorter_window(self):
        class RenderedPage:
            def save(self, stream, format):
                stream.write(b"page7")

        converter = types.SimpleNamespace(convert_from_bytes=Mock(return_value=[RenderedPage()]))
        with (
            patch.dict(sys.modules, {"pdf2image": converter}),
            patch(
                "autodata_ingestion.pdf_ocr.extract_image_text",
                return_value=(OCRTextBlock("Check the connector.", 0.9, (1, 2, 3, 4)),),
            ) as extract_image,
        ):
            blocks = extract_scanned_pdf_text("b" * 64, b"pdf", range(1, 7), page_range=(7, 7))

        converter.convert_from_bytes.assert_called_once_with(
            b"pdf", dpi=200, fmt="png", thread_count=1, first_page=7, last_page=7,
        )
        extract_image.assert_called_once_with("b" * 64, b"page7", "image/png")
        self.assertEqual(blocks, (OCRTextBlock("Check the connector.", 0.9, (1, 2, 3, 4), page_number=7),))


if __name__ == "__main__":
    unittest.main()
