"""Synthetic PDF fixtures for the optional Workshop figure placement pass."""

import base64
from io import BytesIO
import json
from random import Random

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion.ocr import OCRTextBlock
from autodata_ingestion.source_adapters import SourceResource, adapt_bound_article
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def _image(seed):
    return ImageReader(Image.frombytes("RGB", (96, 96), Random(seed).randbytes(96 * 96 * 3)))


def _pdf(layout="clear", *, mixed=False):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, invariant=True, pagesize=(612, 792))
    figure = _image(7)
    if layout == "rotated":
        pdf.setPageRotation(90)
    swapped = layout == "reverse-text"
    pdf.drawString(72, 520 if swapped else 720, "Open the pump cover.")
    if layout == "form":
        pdf.beginForm("diagram")
        pdf.drawImage(figure, 0, 0, width=96, height=120)
        pdf.endForm()
        pdf.saveState()
        pdf.translate(72, 560)
        pdf.doForm("diagram")
        pdf.restoreState()
    elif layout != "late-draw":
        pdf.drawImage(figure, 72, 560, width=96, height=120)
    if layout == "repeat":
        pdf.drawImage(figure, 72, 700, width=40, height=40)
    pdf.drawString(
        260 if layout == "columns" else 72,
        720 if swapped else 570 if layout == "overlap" else 520,
        "Install the seal.",
    )
    if layout == "late-draw":
        pdf.drawImage(figure, 72, 560, width=96, height=120)
    pdf.showPage()
    if layout == "repeat-across-pages":
        pdf.drawImage(figure, 72, 560, width=96, height=120)
        pdf.drawString(72, 520, "Check the fitting.")
        pdf.showPage()
    if mixed:
        pdf.drawImage(_image(8), 72, 560, width=96, height=120)
        pdf.showPage()
        pdf.drawString(72, 720, "Check the fitting.")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _layout(blocks):
    return [(block.get("type", block.get("kind")), block.get("text") or block.get("alt")) for block in blocks]


@pytest.mark.parametrize("container", ["pdf", "wrapper", "linked"])
def test_capture_places_pdf_figure_without_changing_text_or_retained_bytes(capture_fixture, container):
    provider = "banktwo" if container == "linked" else "bankone"
    payload = _pdf()
    context = capture_fixture.context(provider)
    options = {"keep_embedded_pdf": True, "keep_bound_pdf_iframes": True}
    if container == "pdf":
        capture_fixture.body(provider, payload, "application/pdf", kind="binary")
    elif container == "wrapper":
        body = json.dumps({"body": {"pdf": base64.b64encode(payload).decode()}}).encode()
        capture_fixture.body(provider, body, "application/json")
    else:
        capture_fixture.body(
            provider, b'<p>Read the addendum.</p><iframe src="/fixture/diagram"></iframe><p>Close the job.</p>',
            assets=["addendum"], asset_bindings=[{"source_url": "/fixture/diagram", "resource_ref": "addendum"}],
        )
        capture_fixture.body(provider, payload, "application/pdf", kind="binary", ref="addendum")
    legacy = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects, **options,
    )
    retained_bytes = capture_fixture.objects.data.copy()
    positioned = capture_source_article(
        context, registry=capture_fixture.registry, object_store=capture_fixture.objects,
        keep_pdf_figure_order=True, **options,
    )
    prefix = [("paragraph", "Read the addendum.")] if container == "linked" else []
    suffix = [("paragraph", "Close the job.")] if container == "linked" else []
    first = ("paragraph", "Open the pump cover.")
    second = ("paragraph", "Install the seal.")
    figure = ("image", "Figure from page 1")
    assert _layout(legacy.source_document["blocks"]) == prefix + [first, second, figure] + suffix
    assert _layout(positioned.source_document["blocks"]) == prefix + [first, figure, second] + suffix
    assert positioned.source_body == legacy.source_body
    assert positioned.source_steps == legacy.source_steps
    assert positioned.source_fingerprint == legacy.source_fingerprint
    assert positioned.resource_manifest == legacy.resource_manifest
    assert positioned.evidence_manifest == legacy.evidence_manifest
    assert positioned.projection_version == legacy.projection_version
    assert capture_fixture.objects.data == retained_bytes
    [before], [after] = legacy.source_images, positioned.source_images
    assert {key: value for key, value in before.items() if key not in ("source_order", "block_id")} == {
        key: value for key, value in after.items() if key not in ("source_order", "block_id")
    }


@pytest.mark.parametrize("layout", [
    "reverse-text", "columns", "overlap", "repeat", "repeat-across-pages", "form", "rotated",
])
def test_ambiguous_native_page_retains_exact_legacy_blocks(layout):
    resource = SourceResource.from_bytes("fixture:placement", "fixture", _pdf(layout), "application/pdf")
    legacy = adapt_bound_article(resource, None)
    assert any(block["kind"] == "image" for block in legacy["blocks"])
    assert adapt_bound_article(resource, None, keep_pdf_figure_order=True) == legacy


def test_places_figure_by_visible_gap_even_when_it_is_drawn_last():
    resource = SourceResource.from_bytes("fixture:placement", "fixture", _pdf("late-draw"), "application/pdf")
    result = adapt_bound_article(resource, None, keep_pdf_figure_order=True)
    assert result["positioned_pdf_figures"] is True
    assert _layout(result["blocks"]) == [
        ("text", "Open the pump cover."), ("image", "Figure from page 1"), ("text", "Install the seal."),
    ]


def test_only_repositions_native_page_on_a_mixed_pdf(monkeypatch):
    def scanned_text(_digest, _payload, native):
        assert native == {1, 3}
        return (
            OCRTextBlock("Read the warning.", 0.98, (72, 140, 180, 30), page_number=2),
            OCRTextBlock("Check the bracket.", 0.98, (72, 740, 180, 30), page_number=2),
        )

    monkeypatch.setattr("autodata_ingestion.source_adapters.extract_scanned_pdf_text", scanned_text)
    resource = SourceResource.from_bytes("fixture:mixed", "fixture", _pdf(mixed=True), "application/pdf")
    legacy = adapt_bound_article(resource, None)
    positioned = adapt_bound_article(resource, None, keep_pdf_figure_order=True)
    assert "positioned_pdf_figures" not in legacy
    assert positioned["positioned_pdf_figures"] is True
    assert _layout(positioned["blocks"]) == [
        ("text", "Open the pump cover."),
        ("image", "Figure from page 1"),
        ("text", "Install the seal."),
        ("text", "Read the warning."),
        ("text", "Check the bracket."),
        ("image", "Figure from page 2"),
        ("text", "Check the fitting."),
    ]
    assert positioned["blocks"][3:] == legacy["blocks"][3:]
