"""Preserve separate captions from one missing supplier chart."""

from collections import Counter
from hashlib import sha256
from io import BytesIO
from urllib.parse import unquote, urlsplit
import json

from PIL import Image
import pytest
from reportlab.pdfgen import canvas

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import (
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT,
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V2,
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V3,
)
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


CHART = "chart/pressure"
OTHER = "chart/other"
PRESSURE_CAPTION = "Read pressure above 2,000 rpm."
OUTLET_CAPTION = "Apply the outlet correction at altitude."
OTHER_CAPTION = "Check the supply illustration."
LAYOUT_FIELD = "missing_table_image_caption_layout"


def _image(ref, caption=None, **fields):
    return {
        "kind": "image",
        "asset_resource_ref": ref,
        **({"caption": caption} if caption is not None else {}),
        **fields,
    }


def _body(fixture, provider, figures, *, placement="table"):
    table = {"type": "table", "columns": ["Pressure"], "rows": [["500 kPa"]]}
    if placement == "row":
        table["rows"] = [{"cells": ["500 kPa"], "images": figures}]
    elif placement == "mixed":
        table["images"] = figures[:2]
        table["rows"] = [{"cells": ["500 kPa"], "images": figures[2:]}]
    else:
        table["images"] = figures
    if placement == "list":
        table = {"type": "ordered_list", "items": [{"text": "Check the gauge.", "blocks": [table]}]}
    elif placement == "metadata":
        table = {"type": "paragraph", "text": "Check the gauge.", "supplier_metadata": table}
    article = {"blocks": [
        {"type": "paragraph", "text": "Remove the pump."},
        table,
        {"type": "paragraph", "text": "Inspect the seal."},
        {"type": "paragraph", "text": "Install the replacement."},
    ]}
    if provider == "banktwo":
        payload, media = {"_embedded": {"data": {"article": article}}}, "application/hal+json"
    else:
        payload, media = article, "application/json"
    raw = json.dumps(payload).encode()
    fixture.body(provider, raw, media, assets=list(dict.fromkeys(image["asset_resource_ref"] for image in figures)))
    return raw, media


def _deny(fixture, provider, ref, monkeypatch):
    server = fixture.servers[provider]
    response = server.response

    def deny_resource(path, request=None):
        if unquote(urlsplit(path).path) == f"/v1/resources/{ref}":
            server.calls.append(path)
            return 403, {}
        return response(path, request)

    monkeypatch.setattr(server, "response", deny_resource)


def _capture(fixture, context, *, structured=True):
    return capture_source_article(
        context,
        registry=fixture.registry,
        object_store=fixture.objects,
        keep_structured_table_cell_order=structured,
    )


def _write_counts(fixture, monkeypatch):
    writes = Counter()
    put_object = fixture.objects.put_object

    def record_write(key, payload, media_type):
        writes[media_type] += 1
        put_object(key, payload, media_type)

    monkeypatch.setattr(fixture.objects, "put_object", record_write)
    return writes


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_missing_table_chart_keeps_distinct_authored_captions(capture_fixture, provider, monkeypatch):
    raw, media = _body(capture_fixture, provider, [
        _image(CHART, PRESSURE_CAPTION),
        _image(OTHER, OTHER_CAPTION),
        _image(CHART, "  Read pressure above   2,000 rpm. "),
        _image(CHART, label=OUTLET_CAPTION),
        _image(CHART, alt="Uncaptioned summary"),
    ])
    _deny(capture_fixture, provider, OTHER, monkeypatch)
    writes = _write_counts(capture_fixture, monkeypatch)
    context = capture_fixture.context(provider)
    caught = _capture(capture_fixture, context)
    table = caught.source_document["blocks"][1]
    assert [image["caption"] for image in table["images"]] == [PRESSURE_CAPTION, OTHER_CAPTION, OUTLET_CAPTION]
    pressure, other, outlet = table["images"]
    assert pressure["asset_id"] == pressure["image_id"] == outlet["asset_id"] == outlet["image_id"]
    assert pressure["image_id"] != other["image_id"]
    assert pressure["unavailable_reason"] == outlet["unavailable_reason"] == "SOURCE_NOT_FOUND"
    assert other["unavailable_reason"] == "UNAUTHORIZED"
    assert all(image["status"] == "unavailable" and "storage_key" not in image for image in table["images"])
    assert not validate_ordered_document(caught.source_document, strict=True)
    assert capture_fixture.resource_calls(provider, CHART) == capture_fixture.resource_calls(provider, OTHER) == 1
    assert writes == {media: 1}
    assert len(caught.resources) == 1 and caught.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert caught.projection_status == "partial"
    assert [entry for entry in caught.resource_manifest if entry.get("opaque_ref") == CHART] == [
        {"role": "asset", "opaque_ref": CHART, "failure_code": "SOURCE_NOT_FOUND"},
    ]
    assert caught.source_images == table["images"]
    for record in (caught.resources[0], caught.resource_provenance[0], caught.resource_manifest[0]):
        assert record[LAYOUT_FIELD] == MISSING_TABLE_IMAGE_CAPTION_LAYOUT

    previous = _capture(capture_fixture, context, structured=False)
    assert LAYOUT_FIELD not in previous.resource_manifest[0]
    assert caught.body_source_snapshot_id == previous.body_source_snapshot_id
    assert caught.source_fingerprint != previous.source_fingerprint
    assert caught.resource_manifest[1:] == previous.resource_manifest[1:]
    assert caught.resource_provenance[1:] == previous.resource_provenance[1:]
    assert caught.source_body == previous.source_body and caught.source_steps == previous.source_steps
    assert caught.evidence_manifest == previous.evidence_manifest
    assert pressure["image_id"] == previous.source_document["blocks"][1]["images"][0]["image_id"]

    normalized = normalize_procedure_article({
        "normalized_document": caught.source_document, "body": caught.source_body, "steps": caught.source_steps,
    }, resource_manifest=caught.resource_manifest)["normalized_document"]
    replacements = ["Take off the pump.", "Check the seal.", "Fit the replacement."]
    response = {
        "introduction": "This procedure covers pump service.",
        "replacements": [
            {**slot, "action": "rewrite", "text": phrase, "reason": ""}
            for slot, phrase in zip(prose_slots(normalized, include_cell_blocks=True), replacements, strict=True)
        ],
    }
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    [rewritten_table] = [block for block in canonical["blocks"] if block["type"] == "table"]
    assert rewritten_table["block_id"] == table["block_id"]
    assert rewritten_table["images"] == table["images"]


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("placement", ["list", "row", "mixed"])
def test_missing_chart_captions_in_nested_tables_and_row_images(capture_fixture, provider, placement, monkeypatch):
    _, media = _body(capture_fixture, provider, [
        _image(CHART, PRESSURE_CAPTION),
        _image(OTHER, OTHER_CAPTION),
        _image(CHART, "  Read pressure above   2,000 rpm. "),
        _image(CHART, OUTLET_CAPTION),
    ], placement=placement)
    _deny(capture_fixture, provider, OTHER, monkeypatch)
    writes = _write_counts(capture_fixture, monkeypatch)
    context = capture_fixture.context(provider)
    captured = _capture(capture_fixture, context)
    table = captured.source_document["blocks"][1]
    if placement == "list":
        table = table["items"][0]["blocks"][0]
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert [image["caption"] for image in table["images"]] == [PRESSURE_CAPTION, OTHER_CAPTION, OUTLET_CAPTION]
    pressure, other, outlet = table["images"]
    assert pressure["image_id"] == outlet["image_id"] != other["image_id"]
    assert pressure["unavailable_reason"] == outlet["unavailable_reason"] == "SOURCE_NOT_FOUND"
    assert other["unavailable_reason"] == "UNAUTHORIZED"
    assert capture_fixture.resource_calls(provider, CHART) == capture_fixture.resource_calls(provider, OTHER) == 1
    assert writes == {media: 1}
    assert captured.source_images == table["images"]
    assert captured.resource_manifest[0][LAYOUT_FIELD] == MISSING_TABLE_IMAGE_CAPTION_LAYOUT


def test_missing_captions_in_unvisited_supplier_metadata_keep_legacy_fingerprint(capture_fixture):
    _body(capture_fixture, "bankone", [
        _image(CHART, PRESSURE_CAPTION), _image(CHART, OUTLET_CAPTION),
    ], placement="metadata")
    context = capture_fixture.context("bankone")
    captured = _capture(capture_fixture, context)
    previous = _capture(capture_fixture, context, structured=False)
    assert captured.source_document == previous.source_document
    assert captured.source_fingerprint == previous.source_fingerprint
    assert LAYOUT_FIELD not in captured.resource_manifest[0]


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("order", ["interleaved", "captionless-first"])
def test_missing_table_chart_keeps_one_authored_caption(capture_fixture, provider, order, monkeypatch):
    chart = _image(CHART, PRESSURE_CAPTION)
    denied = _image(OTHER, OTHER_CAPTION)
    if order == "interleaved":
        figures = [chart, denied, _image(CHART, label="  Read pressure above   2,000 rpm. ")]
    else:
        figures = [_image(CHART, alt="Uncaptioned summary"), chart, denied]
    raw, _ = _body(capture_fixture, provider, figures)
    _deny(capture_fixture, provider, OTHER, monkeypatch)
    context = capture_fixture.context(provider)
    historical = _capture(capture_fixture, context, structured=False)
    historical_images = historical.source_document["blocks"][1]["images"]
    if order == "interleaved":
        assert [image["caption"] for image in historical_images] == [PRESSURE_CAPTION, OTHER_CAPTION, PRESSURE_CAPTION]
        assert historical_images[0]["image_id"] != historical_images[2]["image_id"]
    else:
        assert "caption" not in historical_images[0]

    repaired = _capture(capture_fixture, context)
    images = repaired.source_document["blocks"][1]["images"]
    assert [image["caption"] for image in images] == [PRESSURE_CAPTION, OTHER_CAPTION]
    assert images[0]["image_id"] == historical_images[0]["image_id"]
    assert images[0]["unavailable_reason"] == "SOURCE_NOT_FOUND"
    assert images[1]["unavailable_reason"] == "UNAUTHORIZED"
    assert not validate_ordered_document(repaired.source_document, strict=True)
    assert repaired.source_images == images
    assert repaired.source_fingerprint != historical.source_fingerprint
    for record in (repaired.resources[0], repaired.resource_provenance[0], repaired.resource_manifest[0]):
        assert record[LAYOUT_FIELD] == MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V2
    assert repaired.resources[0]["sha256"] == historical.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert repaired.resource_manifest[1:] == historical.resource_manifest[1:]
    assert repaired.evidence_manifest == historical.evidence_manifest
    assert capture_fixture.resource_calls(provider, CHART) == capture_fixture.resource_calls(provider, OTHER) == 2


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("placement", ["ordered-cell", "inline-cell", "row-summary", "column"])
def test_missing_chart_caption_keeps_cell_over_summary(capture_fixture, provider, placement, monkeypatch):
    chart = _image(CHART, PRESSURE_CAPTION)
    other = _image(OTHER, OTHER_CAPTION)
    repeat = _image(CHART, label="  Read pressure above   2,000 rpm. ")
    cell = {"text": "Check the gauge.", "images": [chart, other]}
    if placement == "ordered-cell":
        cell = {"blocks": [chart, other, {"kind": "text", "text": "Check the gauge."}]}
    table = {"type": "table", "columns": ["Pressure"], "rows": [[cell]], "images": [repeat]}
    if placement == "row-summary":
        table["rows"] = [{"cells": [cell], "images": table.pop("images")}]
    elif placement == "column":
        table["columns"] = [cell]
        table["rows"] = [["500 kPa"]]
    article = {"blocks": [{"type": "paragraph", "text": "Remove the pump."}, table]}
    payload, media = (article, "application/json") if provider == "bankone" else (
        {"_embedded": {"data": {"article": article}}}, "application/hal+json"
    )
    raw = json.dumps(payload).encode()
    capture_fixture.body(provider, raw, media, assets=[CHART, OTHER])
    context = capture_fixture.context(provider)

    def capture():
        return capture_source_article(
            context, registry=capture_fixture.registry, object_store=capture_fixture.objects,
            keep_structured_table_cell_order=True, keep_structured_table_columns=True,
        )

    captured = capture()
    clean_table = captured.source_document["blocks"][1]
    assert "images" not in clean_table
    assert [image["caption"] for image in captured.source_images] == [PRESSURE_CAPTION, OTHER_CAPTION]
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert captured.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert capture_fixture.resource_calls(provider, CHART) == capture_fixture.resource_calls(provider, OTHER) == 1
    for entry in (captured.resources[0], captured.resource_manifest[0], captured.resource_provenance[0]):
        assert entry[LAYOUT_FIELD] == MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V3

    with monkeypatch.context() as historical:
        historical.setattr(source_article_capture, "_drop_duplicate_missing_table_summaries", lambda *_: False)
        prior = capture()
    old_table = prior.source_document["blocks"][1]
    [summary] = old_table["images"]
    assert summary["caption"] == PRESSURE_CAPTION and summary["image_id"] != captured.source_images[0]["image_id"]
    assert clean_table == {key: value for key, value in old_table.items() if key != "images"}
    assert captured.source_document["blocks"][0] == prior.source_document["blocks"][0]
    assert captured.source_fingerprint != prior.source_fingerprint
    assert captured.body_source_snapshot_id == prior.body_source_snapshot_id
    assert captured.resource_manifest[1:] == prior.resource_manifest[1:]
    assert captured.evidence_manifest == prior.evidence_manifest

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    [slot] = prose_slots(normalized, include_cell_blocks=True)
    response = {
        "introduction": "This procedure covers pump service.",
        "replacements": [{**slot, "action": "rewrite", "text": "Take off the pump.", "reason": ""}],
    }
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    [rewritten_table] = [block for block in canonical["blocks"] if block["type"] == "table"]
    assert rewritten_table == {**clean_table, "source_order": clean_table["source_order"] + 1}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("control", ["same-id", "distinct-caption", "distinct-chart", "metadata", "denied"])
def test_cell_caption_summary_controls_keep_fingerprint(capture_fixture, provider, control, monkeypatch):
    chart = _image(CHART, PRESSURE_CAPTION)
    extra = [] if control == "same-id" else [_image(OTHER, OTHER_CAPTION)]
    cell = {"text": "Check the gauge.", "images": [chart, *extra]}
    if control == "metadata":
        cell["supplier_metadata"] = {"images": cell.pop("images")}
    summary = _image(OTHER if control == "distinct-chart" else CHART,
                     OUTLET_CAPTION if control == "distinct-caption" else PRESSURE_CAPTION)
    table = {"type": "table", "columns": ["Pressure"], "rows": [[cell]], "images": [summary]}
    article = {"blocks": [{"type": "paragraph", "text": "Remove the pump."}, table]}
    payload, media = (article, "application/json") if provider == "bankone" else (
        {"_embedded": {"data": {"article": article}}}, "application/hal+json"
    )
    capture_fixture.body(provider, json.dumps(payload).encode(), media, assets=[CHART, OTHER] if extra else [CHART])
    if control == "denied":
        _deny(capture_fixture, provider, CHART, monkeypatch)
    context = capture_fixture.context(provider)
    captured = _capture(capture_fixture, context)
    prior = _capture(capture_fixture, context, structured=False)
    assert captured.source_document == prior.source_document
    assert captured.source_fingerprint == prior.source_fingerprint
    assert LAYOUT_FIELD not in captured.resource_manifest[0]
    [figure] = captured.source_document["blocks"][1]["images"]
    assert figure["caption"] == summary["caption"]
    if control == "denied":
        assert figure["unavailable_reason"] == "UNAUTHORIZED"


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("control", ["available", "denied", "captionless", "matching"])
def test_unaffected_table_chart_keeps_legacy_projection(capture_fixture, provider, control, monkeypatch):
    if control == "captionless":
        figures = [_image(CHART), _image(CHART, alt="Uncaptioned repeat")]
    elif control == "matching":
        figures = [_image(CHART, PRESSURE_CAPTION), _image(CHART, label="  Read pressure above   2,000 rpm. ")]
    else:
        figures = [_image(CHART, PRESSURE_CAPTION), _image(CHART, OUTLET_CAPTION)]
    _, media = _body(capture_fixture, provider, figures)
    if control == "available":
        png = BytesIO()
        Image.new("RGB", (96, 48), "navy").save(png, format="PNG")
        capture_fixture.body(provider, png.getvalue(), "image/png", kind="asset", ref=CHART)
    if control == "denied":
        _deny(capture_fixture, provider, CHART, monkeypatch)
    writes = _write_counts(capture_fixture, monkeypatch)
    context = capture_fixture.context(provider)
    captured = _capture(capture_fixture, context)
    assert capture_fixture.resource_calls(provider, CHART) == 1
    assert writes == ({media: 1, "image/png": 1} if control == "available" else {media: 1})
    previous = _capture(capture_fixture, context, structured=False)
    assert captured.source_fingerprint == previous.source_fingerprint
    assert captured.projection_version == previous.projection_version
    assert captured.source_document == previous.source_document
    assert LAYOUT_FIELD not in captured.resource_manifest[0]
    [chart] = captured.source_document["blocks"][1]["images"]
    if control == "available":
        assert chart["status"] == "available" and chart["caption"] == PRESSURE_CAPTION
        assert capture_fixture.objects.data[chart["storage_key"]] == (png.getvalue(), "image/png")
    elif control == "denied":
        assert chart["unavailable_reason"] == "UNAUTHORIZED" and chart["caption"] == PRESSURE_CAPTION
    elif control == "matching":
        assert chart["unavailable_reason"] == "SOURCE_NOT_FOUND" and chart["caption"] == PRESSURE_CAPTION
    else:
        assert chart["unavailable_reason"] == "SOURCE_NOT_FOUND"
        assert chart["alt"] == "Article illustration" and "caption" not in chart


def test_bound_pdf_keeps_its_html_table_position(capture_fixture):
    pdf_bytes = BytesIO()
    pdf = canvas.Canvas(pdf_bytes, invariant=True)
    pdf.drawString(72, 718, "Check the drive seal.")
    pdf.save()
    markup = (
        b"<p>Inspect the housing.</p><table><tr><td>Drive reference"
        b'<iframe src="/docs/drive"></iframe>Finish the inspection.</td></tr></table>'
    )
    capture_fixture.body("bankone", markup, assets=["drive"], asset_bindings=[
        {"source_url": "/docs/drive", "resource_ref": "drive"},
    ])
    capture_fixture.body("bankone", pdf_bytes.getvalue(), "application/pdf", ref="drive", kind="asset")
    context = capture_fixture.context("bankone")
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects, keep_bound_pdf_iframes=True)
    captured = capture_source_article(context, keep_structured_table_cell_order=True, **options)
    assert capture_fixture.resource_calls("bankone", "drive") == 1
    previous = capture_source_article(context, **options)
    assert captured.source_fingerprint == previous.source_fingerprint
    assert captured.projection_version == previous.projection_version == "source-projection-v6"
    assert captured.source_document == previous.source_document
    assert LAYOUT_FIELD not in captured.resource_manifest[0]
    [cell] = captured.source_document["blocks"][1]["rows"][0]
    assert [block["text"] for block in cell["blocks"]] == [
        "Drive reference", "Check the drive seal.", "Finish the inspection.",
    ]
