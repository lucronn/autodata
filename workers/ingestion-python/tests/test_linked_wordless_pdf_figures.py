"""Keep provider-bound, wordless diagram pages in the linked PDF's order."""

from hashlib import sha256
from io import BytesIO
import json

from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion import source_adapters
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import PDF_WORDLESS_FIGURE_LAYOUT
from autodata_ingestion.ocr import OCRTextBlock, OCRUnavailable
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def _linked_pdf(variant):
    image = Image.new("RGB", (196, 146), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 44, 76, 94), outline="black", width=3)
    draw.rectangle((118, 44, 176, 94), outline="black", width=3)
    draw.line(((76, 61), (118, 61)), fill="darkblue", width=3)
    draw.line(((76, 77), (118, 77)), fill="brown", width=3)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    if variant == "middle":
        pdf.drawString(72, 710, "Inspect the harness connector.")
        pdf.showPage()
    if variant != "blank":
        pdf.drawImage(ImageReader(image), -10 if variant == "clipped" else 72, 480, 196, 146)
    if variant == "ambiguous":
        pdf.line(72, 650, 100, 650)
    if variant == "middle":
        pdf.showPage()
        pdf.drawString(72, 710, "Seat the terminal in the connector.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue(), image


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("variant", ["standalone", "middle", "blank", "ambiguous", "clipped", "ocr_text", "ocr_failure"])
def test_linked_pdf_keeps_proven_compact_diagram(capture_fixture, monkeypatch, provider, variant):
    pdf, figure = _linked_pdf(variant)
    if variant != "blank":
        page = PdfReader(BytesIO(pdf)).pages[int(variant == "middle")]
        [native_image] = page.images
        assert len(native_image.data) < 2_048

    ocr_calls = []

    def ocr(digest, payload, native_pages, *, page_range):
        assert payload == pdf and digest == sha256(pdf).hexdigest()
        assert native_pages == ({1, 3} if variant == "middle" else set())
        assert page_range == ((2, 2) if variant == "middle" else None)
        ocr_calls.append(variant)
        if variant == "ocr_failure":
            raise OCRUnavailable("Synthetic OCR failure")
        if variant == "ocr_text":
            return (OCRTextBlock("Check the connector seal.", 0.95, (4, 5, 100, 20)),)
        return ()

    monkeypatch.setattr(source_adapters, "extract_scanned_pdf_text", ocr)
    html = '<p>Remove the cover.</p><iframe src="/docs/drive"></iframe><p>Install the cover.</p>'
    if provider == "banktwo":
        raw = json.dumps({"_embedded": {"data": {"article": {"body": html}}}}).encode()
        media = "application/hal+json"
    else:
        raw, media = html.encode(), "text/html"
    capture_fixture.body(provider, raw, media, assets=["drive"],
                         asset_bindings=[{"source_url": "/docs/drive", "resource_ref": "drive"}])
    capture_fixture.body(provider, pdf, "application/pdf", kind="asset", ref="drive")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_bound_pdf_iframes=True, keep_pdf_figure_order=True, keep_compact_pdf_figures=True,
                   skip_blank_linked_pdf_pages=True)
    legacy = capture_source_article(context, **options)
    captured = capture_source_article(context, keep_wordless_linked_pdf_figures=True, **options)
    assert ocr_calls == ([] if variant == "blank" else [variant, variant])
    assert capture_fixture.resource_calls(provider, "drive") == 2
    other = "banktwo" if provider == "bankone" else "bankone"
    assert capture_fixture.calls(other) == []
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert "/docs/" not in repr(captured.source_document)
    assert legacy.body_source_snapshot_id == captured.body_source_snapshot_id
    assert legacy.projection_version == captured.projection_version == "source-projection-v6"
    [old_pdf] = [r for r in legacy.resources if r["role"] == "document_asset"]
    [new_pdf] = [r for r in captured.resources if r["role"] == "document_asset"]
    assert old_pdf["source_snapshot_id"] == new_pdf["source_snapshot_id"]

    if variant not in {"middle", "standalone"}:
        assert captured.source_document == legacy.source_document
        assert captured.resource_manifest == legacy.resource_manifest
        assert captured.source_fingerprint == legacy.source_fingerprint
        assert captured.source_images == []
        assert captured.projection_status == ("readable" if variant == "ocr_text" else "partial")
        return

    assert legacy.source_images == []
    assert captured.projection_status == "readable"
    assert captured.source_fingerprint != legacy.source_fingerprint
    [manifest_pdf] = [r for r in captured.resource_manifest if r["role"] == "document_asset"]
    assert manifest_pdf["pdf_wordless_figure_layout"] == PDF_WORDLESS_FIGURE_LAYOUT
    [image] = captured.source_images
    [retained] = [r for r in captured.resources if r["role"] == "embedded_asset"]
    assert retained["opaque_ref"] == f"embedded:{new_pdf['sha256']}:{image['content_sha256']}"
    assert image["status"] == "available" and image["evidence_ids"] == [f"source:{new_pdf['source_snapshot_id']}"]
    png, image_mime = capture_fixture.objects.data[image["storage_key"]]
    assert image_mime == "image/png" and sha256(png).hexdigest() == retained["sha256"]
    with Image.open(BytesIO(png)) as restored:
        assert restored.size == figure.size and restored.convert("RGB").tobytes() == figure.tobytes()
    blocks = [(block["type"], block.get("text") or block.get("alt")) for block in captured.source_document["blocks"]]
    embed = [("image", "Figure from page 1")]
    if variant == "middle":
        embed = [("paragraph", "Inspect the harness connector."), ("image", "Figure from page 2"),
                 ("paragraph", "Seat the terminal in the connector.")]
    assert blocks == [("paragraph", "Remove the cover."), *embed, ("paragraph", "Install the cover.")]
