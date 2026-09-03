import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.ocr import (  # noqa: E402
    OCRTextBlock,
    build_ocr_candidates,
    extract_image_text,
)


class OCRTests(unittest.TestCase):
    def test_ocr_blocks_become_stable_page_region_evidence(self):
        candidates = build_ocr_candidates(
            "a" * 64,
            [
                OCRTextBlock("  C101  ", 0.91, (10, 20, 30, 40), page_number=1),
                OCRTextBlock("", 0.4, (0, 0, 1, 1), page_number=1),
            ],
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.kind, "image_text")
        self.assertEqual(candidate.locator, "page:1:region:10,20,30,40")
        self.assertEqual(candidate.data["text"], "C101")
        self.assertEqual(candidate.data["confidence"], 0.91)
        self.assertEqual(candidate.data["bbox"], [10, 20, 30, 40])
        self.assertTrue(candidate.key.startswith("image-text:"))

    def test_ocr_blocks_reject_invalid_confidence_or_region(self):
        for block in (
            OCRTextBlock("label", -0.1, (0, 0, 1, 1)),
            OCRTextBlock("label", 1.1, (0, 0, 1, 1)),
            OCRTextBlock("label", 0.8, (0, 0, 0, 1)),
        ):
            with self.subTest(block=block), self.assertRaisesRegex(ValueError, "OCR"):
                build_ocr_candidates("b" * 64, [block])

    def test_image_provider_converts_tesseract_regions_to_ocr_blocks(self):
        class FakeImage:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class FakeImageModule:
            @staticmethod
            def open(stream):
                self.assertGreater(stream.getbuffer().nbytes, 0)
                return FakeImage()

        fake_tesseract = types.SimpleNamespace(
            Output=types.SimpleNamespace(DICT="dict"),
            image_to_data=lambda _image, output_type: {
                "text": ["C101", ""],
                "conf": ["88", "-1"],
                "left": ["1", "0"],
                "top": ["2", "0"],
                "width": ["30", "1"],
                "height": ["10", "1"],
            },
        )

        with patch.dict(
            sys.modules,
            {
                "PIL": types.SimpleNamespace(Image=FakeImageModule),
                "pytesseract": fake_tesseract,
            },
        ):
            blocks = extract_image_text("c" * 64, b"image", "image/png")

        self.assertEqual(blocks, (OCRTextBlock("C101", 0.88, (1, 2, 30, 10)),))


if __name__ == "__main__":
    unittest.main()
