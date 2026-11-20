"""Synthetic PDF fixtures for the optional Workshop figure placement pass."""

import base64
from dataclasses import replace
from io import BytesIO
from hashlib import sha256
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


def _multi_figure_pdf(*, same_gap=False, overlap=False):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, invariant=True, pagesize=(612, 792))
    pdf.drawString(72, 750, "Open the pump cover.")
    # Resource and paint order are deliberately different from visual order.
    pdf.drawImage(_image(14), 72, 638 if overlap else 628 if same_gap else 450, width=96, height=18 if same_gap or overlap else 100)
    pdf.drawString(72, 600, "Check the seal.")
    pdf.drawImage(_image(7), 72, 650, width=96, height=70)
    pdf.drawString(72, 400, "Install the seal.")
    pdf.save()
    return buffer.getvalue()


def _repeated_pdf(*, margin=False, changed=False):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, invariant=True, pagesize=(612, 792))
    repeated, unique = _image(7), _image(8)
    for index, figure in enumerate((repeated, repeated, unique)):
        pdf.drawString(72, 720, ["Remove the pump.", "Inspect the seal.", "Tighten the bracket."][index])
        pdf.drawImage(figure, 72, 749 if margin and index < 2 else 550, width=96, height=32 if margin and index < 2 else 96)
        pdf.drawString(72, 450, [
            "Check the cover.", "Clean the flange." if not changed else "Check the flange.", "Install the replacement.",
        ][index])
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _layout(blocks):
    return [(block.get("type", block.get("kind")), block.get("text") or block.get("alt")) for block in blocks]


@pytest.mark.parametrize("container", ["pdf", "wrapper", "linked", "linked-hal", "linked-only-hal"])
def test_capture_places_pdf_figure_without_changing_text_or_retained_bytes(
    capture_fixture, container,
):
    provider = "banktwo" if container.startswith("linked") else "bankone"
    payload = _pdf()
    context = capture_fixture.context(provider)
    options = {"keep_embedded_pdf": True, "keep_bound_pdf_iframes": True}
    if container == "pdf":
        capture_fixture.body(provider, payload, "application/pdf", kind="binary")
    elif container == "wrapper":
        body = json.dumps({"body": {"pdf": base64.b64encode(payload).decode()}}).encode()
        capture_fixture.body(provider, body, "application/json")
    else:
        embedded = '<iframe src="/fixture/diagram"></iframe>'
        markup = embedded if container == "linked-only-hal" else (
            f"<p>Read the addendum.</p>{embedded}<p>Close the job.</p>"
        )
        if container.endswith("-hal"):
            body = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
            media = "application/hal+json"
        else:
            body, media = markup.encode(), "text/html"
        capture_fixture.body(
            provider, body, media,
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
    has_surrounding_prose = container in {"linked", "linked-hal"}
    prefix = [("paragraph", "Read the addendum.")] if has_surrounding_prose else []
    suffix = [("paragraph", "Close the job.")] if has_surrounding_prose else []
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
    assert legacy.projection_version == {
        "pdf": "source-projection-v2",
        "wrapper": "source-projection-v5",
        "linked": "source-projection-v6",
        "linked-hal": "source-projection-v6",
        "linked-only-hal": "source-projection-v6",
    }[container]
    assert positioned.projection_version == "source-projection-v7"
    assert capture_fixture.objects.data == retained_bytes
    [before], [after] = legacy.source_images, positioned.source_images
    assert {key: value for key, value in before.items() if key not in ("source_order", "block_id")} == {
        key: value for key, value in after.items() if key not in ("source_order", "block_id")
    }


@pytest.mark.parametrize("markup", [
    '<iframe src="/fixture/diagram" srcdoc="Hidden content."></iframe>',
    '<iframe src="/fixture/unbound">Hidden content.</iframe>',
])
def test_hal_embed_only_requires_connector_binding_without_srcdoc(capture_fixture, markup):
    body = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
    adapted = adapt_bound_article(
        SourceResource.from_bytes(
            "fixture:hal", "fixture", body, "application/hal+json",
            metadata={"asset_bindings": [{"source_url": "/fixture/diagram", "resource_ref": "addendum"}]},
        ),
        capture_fixture.context("banktwo"), keep_bound_pdf_iframes=True, keep_pdf_figure_order=True,
    )
    assert adapted["blocks"] == []
    assert adapted["handled_pdf_embeds"] is True


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


@pytest.mark.parametrize("embedded_count", [0, 1, 2])
@pytest.mark.parametrize("same_gap", [False, True])
def test_multi_figure_capture_preserves_original_and_manifest_order(capture_fixture, embedded_count, same_gap):
    provider = "banktwo"
    payload = _multi_figure_pdf(same_gap=same_gap)
    context = capture_fixture.context(provider)
    if embedded_count:
        capture_fixture.body(
            provider, b'<iframe src="/fixture/diagrams"></iframe>' * embedded_count,
            assets=["addendum"], asset_bindings=[{"source_url": "/fixture/diagrams", "resource_ref": "addendum"}],
        )
        capture_fixture.body(provider, payload, "application/pdf", kind="binary", ref="addendum")
    else:
        capture_fixture.body(provider, payload, "application/pdf", kind="binary")
    opts = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                keep_bound_pdf_iframes=True, keep_pdf_figure_order=True)
    before = capture_source_article(context, **opts)
    after = capture_source_article(context, **opts, keep_multiple_pdf_figures=True)
    assert before.projection_version == ("source-projection-v6" if embedded_count else "source-projection-v2")
    assert after.projection_version == "source-projection-v8"
    assert before.source_fingerprint == after.source_fingerprint
    assert before.resource_manifest == after.resource_manifest
    assert before.evidence_manifest == after.evidence_manifest
    for key in ("resources", "resource_provenance"):
        def identity(records):
            return [{k: v for k, v in row.items() if k not in ("request_id", "fetched_at")}
                    for row in records]

        assert identity(getattr(before, key)) == identity(getattr(after, key))
    assert before.source_body == after.source_body and before.source_steps == after.source_steps
    assert after.source_document != before.source_document
    digest = sha256(payload).hexdigest()
    assert capture_fixture.objects.data[f"sources/{digest[:16]}/{digest}"] == (payload, "application/pdf")
    first = ("paragraph", "Open the pump cover.")
    second = ("paragraph", "Check the seal.")
    third = ("paragraph", "Install the seal.")
    figure = ("image", "Figure from page 1")
    expected = [first, figure, figure, second, third] if same_gap else [first, figure, second, figure, third]
    assert _layout(after.source_document["blocks"]) == expected * max(embedded_count, 1)
    pixels = []
    for image in after.source_images:
        data, media = capture_fixture.objects.data[image["storage_key"]]
        assert media == "image/png"
        with Image.open(BytesIO(data)) as raster:
            pixels.append(raster.tobytes())
    assert pixels == [Random(seed).randbytes(96 * 96 * 3) for seed in [7, 14] * max(embedded_count, 1)]


def test_overlapping_multiple_figures_keep_legacy_order():
    resource = SourceResource.from_bytes("fixture:placement", "fixture", _multi_figure_pdf(overlap=True), "application/pdf")
    legacy = adapt_bound_article(resource, None)
    assert sum(block["kind"] == "image" for block in legacy["blocks"]) == 2
    assert adapt_bound_article(resource, None, keep_pdf_figure_order=True, keep_multiple_pdf_figures=True) == legacy


@pytest.mark.parametrize("container", ["pdf", "wrapper", "linked"])
def test_repeated_pdf_retains_each_proven_occurrence_with_one_png_upload(capture_fixture, monkeypatch, container):
    provider = "banktwo" if container == "linked" else "bankone"
    payload = _repeated_pdf()
    context = capture_fixture.context(provider)
    if container == "linked":
        body = b'<p>Check the service instructions.</p><iframe src="/fixture/diagrams"></iframe>'
        capture_fixture.body(
            provider, body, assets=["addendum"],
            asset_bindings=[{"source_url": "/fixture/diagrams", "resource_ref": "addendum"}],
        )
        capture_fixture.body(provider, payload, "application/pdf", kind="binary", ref="addendum")
        protected_root = sha256(payload).hexdigest()
    elif container == "wrapper":
        body = json.dumps({"body": {"pdf": base64.b64encode(payload).decode()}}).encode()
        capture_fixture.body(provider, body, "application/json")
        protected_root = sha256(body).hexdigest()
    else:
        capture_fixture.body(provider, payload, "application/pdf", kind="binary")
        protected_root = sha256(payload).hexdigest()
    uploads = []
    store = capture_fixture.objects
    put = store.put_object

    def record_upload(key, data, mime):
        uploads.append((key, mime))
        put(key, data, mime)

    monkeypatch.setattr(store, "put_object", record_upload)
    options = dict(
        registry=capture_fixture.registry, object_store=store,
        keep_bound_pdf_iframes=True, keep_embedded_pdf=True, keep_pdf_figure_order=True,
        keep_multiple_pdf_figures=True,
    )
    legacy = capture_source_article(context, **options)
    guarded = capture_source_article(
        replace(context, legacy_published_pdf_roots=frozenset({protected_root})),
        keep_repeated_pdf_figures=True, **options,
    )
    assert guarded.source_document == legacy.source_document
    assert guarded.source_fingerprint == legacy.source_fingerprint
    assert guarded.resource_manifest == legacy.resource_manifest
    assert guarded.evidence_manifest == legacy.evidence_manifest
    assert [image["alt"] for image in guarded.source_images] == ["Figure from page 3"]
    uploads.clear()

    captured = capture_source_article(context, keep_repeated_pdf_figures=True, **options)
    assert captured.projection_version == "source-projection-v10"
    assert captured.source_body == legacy.source_body
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.projection_status == "readable"
    layout = _layout(captured.source_document["blocks"])
    assert layout[-9:] == [
        ("paragraph", "Remove the pump."), ("image", "Figure from page 1"), ("paragraph", "Check the cover."),
        ("paragraph", "Inspect the seal."), ("image", "Figure from page 2"), ("paragraph", "Clean the flange."),
        ("paragraph", "Tighten the bracket."), ("image", "Figure from page 3"), ("paragraph", "Install the replacement."),
    ]
    first, second, third = captured.source_images
    assert first["storage_key"] == second["storage_key"] != third["storage_key"]
    assert first["block_id"] != second["block_id"]
    assert first["evidence_ids"] == second["evidence_ids"] == third["evidence_ids"]
    assert uploads.count((first["storage_key"], "image/png")) == 1
    assert sum(entry.get("role") == "embedded_asset" for entry in captured.resource_manifest) == 2
    assert "_retained_repeated_pdf_figure" not in repr(captured.source_document)


def test_repeated_pdf_margin_art_does_not_change_published_projection():
    resource = SourceResource.from_bytes("fixture:margin-figures", "fixture", _repeated_pdf(margin=True), "application/pdf")
    options = dict(keep_pdf_figure_order=True, keep_multiple_pdf_figures=True)
    legacy = adapt_bound_article(resource, None, **options)
    assert [block["alt"] for block in legacy["blocks"] if block["kind"] == "image"] == ["Figure from page 3"]
    assert adapt_bound_article(resource, None, keep_repeated_pdf_figures=True, **options) == legacy
