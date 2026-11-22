"""An authored figure can sit between two protected table-header instructions."""

from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import STRUCTURED_TABLE_COLUMN_ORDER_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite import build_rewrite_prompt, rewrite_ordered_document
from autodata_ingestion.source_article_capture import capture_source_article
from test_procedure_rewrite_full import Draft
from test_source_article_capture import capture_fixture


def _supplier_table(provider, *, row_only=False):
    ordered = {"blocks": [
        {"kind": "text", "text": "Check the pressure scale."},
        {"kind": "image", "asset_resource_ref": "chart", "alt": "Pressure chart", "caption": "Pressure at 2,000 rpm",
         "url": "https://outside.invalid/chart.png", "storage_key": "unverified/chart"},
        {"kind": "text", "text": "Read the upper line."},
    ]}
    article = {"blocks": [
        {"type": "paragraph", "text": "Remove the pump."},
        {"type": "table", "label": "Pressure data", "columns": [{"text": "Pressure scale"} if row_only else ordered, "Limit"],
         "rows": [[ordered if row_only else "Supply", "500 kPa"]]},
        {"type": "paragraph", "text": "Inspect the seal."},
        {"type": "paragraph", "text": "Install the replacement."},
    ]}
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


def _capture_pair(fixture, provider, *, available=True, row_only=False):
    raw, media = _supplier_table(provider, row_only=row_only)
    fixture.body(provider, raw, media, assets=["chart"])
    buffer = BytesIO()
    Image.new("RGB", (96, 48), "navy").save(buffer, format="PNG")
    png = buffer.getvalue()
    if available:
        fixture.body(provider, png, "image/png", kind="asset", ref="chart")
    context = fixture.context(provider)
    options = dict(registry=fixture.registry, object_store=fixture.objects,
                   keep_structured_table_columns=True, keep_structured_table_cell_order=True)
    legacy = capture_source_article(context, **options)
    corrected = capture_source_article(context, keep_structured_table_column_order=True, **options)
    return legacy, corrected, png


@pytest.mark.parametrize("provider,available", [("bankone", True), ("banktwo", True), ("banktwo", False)])
def test_structured_table_header_preserves_chart_between_instructions(capture_fixture, provider, available):
    legacy, capture, png = _capture_pair(capture_fixture, provider, available=available)
    before = legacy.source_document["blocks"][1]["columns"][0]
    assert before["text"] == "Check the pressure scale. Read the upper line."
    [old_image] = before["images"]
    assert capture.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert capture.source_fingerprint != legacy.source_fingerprint
    assert capture.resource_manifest[0]["structured_table_column_order_layout"] == STRUCTURED_TABLE_COLUMN_ORDER_LAYOUT
    assert capture.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert capture.evidence_manifest == legacy.evidence_manifest
    assert capture.source_body.split() == legacy.source_body.split()
    assert capture.projection_version == legacy.projection_version == "source-projection-v5"
    assert capture.projection_status == ("readable" if available else "partial")
    assert not validate_ordered_document(capture.source_document, strict=True)
    table = capture.source_document["blocks"][1]
    header, limit = table["columns"]
    assert limit == "Limit" and table["rows"] == [["Supply", "500 kPa"]]
    assert header["protected_text"] is True
    assert [block["type"] for block in header["blocks"]] == ["paragraph", "image", "paragraph"]
    lead, image, tail = header["blocks"]
    assert lead["text"] == "Check the pressure scale." and tail["text"] == "Read the upper line."
    assert image["block_id"] == table["block_id"] + ":column:0001:block:0002"
    assert image["image_id"] == old_image["image_id"]
    assert capture.source_images == [image]
    assert image["alt"] == "Pressure chart" and image["caption"] == "Pressure at 2,000 rpm"
    assert "outside.invalid" not in json.dumps(table) and "unverified/chart" not in json.dumps(table)
    if available:
        assert image["content_sha256"] == sha256(png).hexdigest()
        assert capture_fixture.objects.data[image["storage_key"]] == (png, "image/png")
    else:
        assert image["status"] == "unavailable" and image["unavailable_reason"] == "SOURCE_NOT_FOUND"
        assert "storage_key" not in image

    normalized = normalize_procedure_article({
        "normalized_document": capture.source_document, "body": capture.source_body, "steps": capture.source_steps,
    }, resource_manifest=capture.resource_manifest)["normalized_document"]
    profile = "full-prose-auto-v1"
    slots = json.loads(build_rewrite_prompt(normalized, context={}, profile_version=profile))["slots"]
    assert [slot["text"] for slot in slots] == ["Remove the pump.", "Inspect the seal.", "Install the replacement."]
    response = {"introduction": "This procedure describes pump service.", "replacements": [
        {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "text": text, "reason": ""}
        for slot, text in zip(slots, ("Take off the pump.", "Check the seal.", "Fit the replacement."), strict=True)
    ]}
    rewritten = rewrite_ordered_document(normalized, client=Draft(response), context={}, profile_version=profile)
    assert rewritten.error_code is None
    assert rewritten.document["blocks"][2]["columns"] == table["columns"]
    assert rewritten.document["blocks"][2]["rows"] == table["rows"]


def test_row_only_media_keeps_original_fingerprint(capture_fixture):
    legacy, capture, _ = _capture_pair(capture_fixture, "bankone", row_only=True)
    assert capture.source_fingerprint == legacy.source_fingerprint
    assert capture.source_document == legacy.source_document
    assert capture.resource_manifest == legacy.resource_manifest
    assert "structured_table_column_order_layout" not in capture.resource_manifest[0]
