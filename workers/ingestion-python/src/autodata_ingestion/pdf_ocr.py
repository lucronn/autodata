"""Optional scanned-PDF rasterization through the existing OCR boundary."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from itertools import pairwise
from typing import Iterable

from .ocr import OCRTextBlock, OCRUnavailable, extract_image_text


class PDFRasterizationUnavailable(OCRUnavailable):
    """The optional PDF rasterizer is not available or cannot read the PDF."""


def rasterize_pdf_pages(
    payload: bytes, *, dpi: int = 200, page_range: tuple[int, int] | None = None,
) -> tuple[bytes, ...]:
    """Render PDF pages to PNG bytes with a deterministic, single-threaded boundary."""

    try:
        from pdf2image import convert_from_bytes
    except ImportError as error:
        raise PDFRasterizationUnavailable("PDF rasterizer is not installed") from error

    try:
        bounds = {"first_page": page_range[0], "last_page": page_range[1]} if page_range else {}
        rendered_pages = convert_from_bytes(
            payload,
            dpi=dpi,
            fmt="png",
            thread_count=1,
            **bounds,
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
    if page_range is not None and len(page_payloads) != page_range[1] - page_range[0] + 1:
        raise PDFRasterizationUnavailable("PDF rasterizer did not return the requested pages")
    return tuple(page_payloads)


def _rasterization_windows(
    page_range: tuple[int, int], native_pages: set[int],
) -> Iterable[tuple[int, int]]:
    first, last = page_range
    scanned = [page for page in range(first, last + 1) if page not in native_pages]
    if not scanned:
        return
    # Keep small gaps together and limit how often Poppler opens the PDF.
    gaps = [(left, right) for left, right in pairwise(scanned) if right - left > 2]
    largest = sorted(gaps, key=lambda gap: gap[1] - gap[0], reverse=True)[:3]
    splits = sorted(largest)
    starts = [scanned[0], *(right for _, right in splits)]
    ends = [*(left for left, _ in splits), scanned[-1]]
    yield from zip(starts, ends, strict=True)


def extract_scanned_pdf_text(
    content_sha256: str,
    payload: bytes,
    native_text_pages: Iterable[int] = (),
    *,
    page_range: tuple[int, int] | None = None,
) -> tuple[OCRTextBlock, ...]:
    """Extract OCR from scanned pages, retaining the original page numbers."""

    native_pages = {int(page_number) for page_number in native_text_pages}
    blocks: list[OCRTextBlock] = []
    windows = (None,) if page_range is None else _rasterization_windows(page_range, native_pages)
    for window in windows:
        first_page = window[0] if window is not None else 1
        for page_number, page_payload in enumerate(
            rasterize_pdf_pages(payload, page_range=window), start=first_page,
        ):
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
