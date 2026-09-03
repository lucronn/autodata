"""Optional scanned-PDF rasterization through the existing OCR boundary."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from typing import Iterable

from .ocr import OCRTextBlock, OCRUnavailable, extract_image_text


class PDFRasterizationUnavailable(OCRUnavailable):
    """The optional PDF rasterizer is not available or cannot read the PDF."""


def rasterize_pdf_pages(payload: bytes, *, dpi: int = 200) -> tuple[bytes, ...]:
    """Render PDF pages to PNG bytes with a deterministic, single-threaded boundary."""

    try:
        from pdf2image import convert_from_bytes
    except ImportError as error:
        raise PDFRasterizationUnavailable("PDF rasterizer is not installed") from error

    try:
        rendered_pages = convert_from_bytes(
            payload,
            dpi=dpi,
            fmt="png",
            thread_count=1,
        )
        page_payloads: list[bytes] = []
        for page in rendered_pages:
            stream = BytesIO()
            page.save(stream, format="PNG")
            page_payloads.append(stream.getvalue())
    except Exception as error:
        raise PDFRasterizationUnavailable(f"PDF could not be rasterized: {error}") from error

    if not page_payloads:
        raise PDFRasterizationUnavailable("PDF rasterizer returned no pages")
    return tuple(page_payloads)


def extract_scanned_pdf_text(
    content_sha256: str,
    payload: bytes,
    native_text_pages: Iterable[int] = (),
) -> tuple[OCRTextBlock, ...]:
    """Rasterize only pages without native text and return page-numbered OCR blocks."""

    native_pages = {int(page_number) for page_number in native_text_pages}
    blocks: list[OCRTextBlock] = []
    for page_number, page_payload in enumerate(rasterize_pdf_pages(payload), start=1):
        if page_number in native_pages:
            continue
        try:
            page_blocks = extract_image_text(content_sha256, page_payload, "image/png")
        except OCRUnavailable:
            raise
        except Exception as error:
            raise OCRUnavailable(f"OCR failed for rasterized PDF page {page_number}: {error}") from error
        blocks.extend(replace(block, page_number=page_number) for block in page_blocks)
    return tuple(blocks)
