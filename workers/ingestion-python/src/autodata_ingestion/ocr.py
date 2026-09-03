"""Provider-neutral OCR result normalization and evidence coordinates."""

from __future__ import annotations

import io
import math
import uuid
from dataclasses import dataclass
from typing import Iterable

from .source_adapters import NormalizationCandidate


@dataclass(frozen=True)
class OCRTextBlock:
    """One OCR text region returned by a provider."""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]
    page_number: int = 1


class OCRUnavailable(RuntimeError):
    """The configured OCR runtime cannot process the source bytes."""


def extract_image_text(
    content_sha256: str,
    payload: bytes,
    media_type: str,
) -> tuple[OCRTextBlock, ...]:
    """Use Tesseract when installed and return provider-neutral text regions."""

    if not str(media_type).casefold().startswith("image/"):
        raise OCRUnavailable("OCR image extractor requires an image media type")
    try:
        from PIL import Image
        import pytesseract
    except ImportError as error:
        raise OCRUnavailable("Pillow and pytesseract are required for image OCR") from error

    try:
        with Image.open(io.BytesIO(payload)) as image:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception as error:
        raise OCRUnavailable(f"image could not be processed by OCR: {error}") from error

    try:
        texts = data["text"]
        confidences = data["conf"]
        left = data["left"]
        top = data["top"]
        widths = data["width"]
        heights = data["height"]
        blocks = []
        for index, raw_text in enumerate(texts):
            text = str(raw_text).strip()
            if not text:
                continue
            raw_confidence = float(confidences[index])
            if raw_confidence < 0:
                continue
            blocks.append(
                OCRTextBlock(
                    text=text,
                    confidence=raw_confidence / 100,
                    bbox=(
                        int(left[index]),
                        int(top[index]),
                        int(widths[index]),
                        int(heights[index]),
                    ),
                )
            )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise OCRUnavailable("OCR provider returned an invalid region response") from error
    # Validate the hash and all coordinates even when the provider returned no text.
    build_ocr_candidates(content_sha256, blocks)
    return tuple(blocks)


def build_ocr_candidates(
    content_sha256: str,
    blocks: Iterable[OCRTextBlock],
) -> tuple[NormalizationCandidate, ...]:
    """Convert OCR blocks into stable evidence candidates without domain parsing."""

    if len(str(content_sha256).strip()) != 64:
        raise ValueError("OCR content hash must be a SHA-256 value")
    candidates: list[NormalizationCandidate] = []
    for block in blocks:
        text = str(block.text).strip()
        if not text:
            continue
        if not math.isfinite(float(block.confidence)) or not 0 <= float(block.confidence) <= 1:
            raise ValueError("OCR confidence must be between 0 and 1")
        if int(block.page_number) < 1:
            raise ValueError("OCR page number must be positive")
        x, y, width, height = (int(value) for value in block.bbox)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("OCR bounding box must have non-negative origin and positive dimensions")
        bbox = [x, y, width, height]
        locator = f"page:{int(block.page_number)}:region:{x},{y},{width},{height}"
        key = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"autodata-ocr:{content_sha256}:{locator}:{text}",
            )
        )
        candidates.append(
            NormalizationCandidate(
                "image_text",
                f"image-text:{key}",
                {
                    "text": text,
                    "confidence": float(block.confidence),
                    "bbox": bbox,
                    "page_number": int(block.page_number),
                },
                locator,
            )
        )
    return tuple(candidates)
