"""Table cells keep authored nested structures and locally authorized media."""

from base64 import b64decode
from hashlib import sha256
import json

import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import STRUCTURED_TABLE_NESTED_MEDIA_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.source_article_capture import capture_source_article, _image_nodes
from test_source_article_capture import capture_fixture


PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aYWQAAAAASUVORK5CYII="
)


def _paragraph(text):
    return {"type": "paragraph", "text": text}


@pytest.mark.parametrize(("provider", "position", "available"), [
    ("bankone", "row", True),
    ("banktwo", "row", True),
    ("bankone", "column", True),
    ("banktwo", "column", True),
    ("banktwo", "row", False),
])
def test_structured_nested_cell_keeps_figure_in_preview_and_stored_source(capture_fixture, provider, position, available):
    image = {
        "type": "image", "asset_resource_ref": "figure", "alt": "Registration diagram",
        "caption": "Registration marks on the sample",
        "url": "https://outside.invalid/figure.png", "storage_key": "unverified/figure",
    }
    inner = [_paragraph("Align the first mark."), image, _paragraph("Check the second mark.")]
    if position == "row":
        nested = {"type": "ordered_list", "start": 4, "items": [
            {"number": 9, "text": "Position the sample.", "blocks": inner},
            "Leave the setup undisturbed.",
        ]}
    else:
        nested = {"type": "table", "columns": ["Inner reference"], "rows": [[{"blocks": inner}]]}
    cell = {"blocks": [_paragraph("Inspect the tray."), nested, _paragraph("Set the sample aside.")]}
    without_media = {"blocks": [
        _paragraph("Inspect the other tray."), {"type": "unordered_list", "items": ["Set a spare aside."]},
    ]}
    direct = {"blocks": [
        _paragraph("Inspect the direct placement."), image, _paragraph("Finish the direct placement."),
    ]}
    table = {
        "type": "table",
        "columns": [cell if position == "column" else "Reference"],
        "rows": [[cell if position == "row" else "Reference"], [without_media], [direct]],
    }
    body = {"blocks": [_paragraph("Prepare the paper sample."), table, _paragraph("Record the result.")]}
    media_type = "application/json"
    if provider == "banktwo":
        body = {"_embedded": {"data": {"article": body}}}
        media_type = "application/hal+json"
    capture_fixture.body(provider, json.dumps(body).encode(), media_type, assets=["figure"])
    if available:
        capture_fixture.body(provider, PNG, "image/png", kind="asset", ref="figure")
    previews = []
    captured = capture_source_article(
        capture_fixture.context(provider), registry=capture_fixture.registry, object_store=capture_fixture.objects,
        keep_structured_table_columns=True, keep_structured_table_cell_order=True,
        keep_structured_table_column_order=True, on_body_preview=lambda _, document: previews.append(document),
    )

    assert capture_fixture.resource_calls(provider, "figure") == 1
    assert captured.resource_manifest[0]["structured_table_nested_media_layout"] == STRUCTURED_TABLE_NESTED_MEDIA_LAYOUT
    assert "structured_table_cell_order_layout" in captured.resource_manifest[0]
    assert len(previews) == 1
    assert not validate_ordered_document(captured.source_document, strict=True)
    for document in [previews[0], captured.source_document]:
        stored_table = document["blocks"][1]
        assert stored_table["rows"][1] == ["Inspect the other tray."]
        assert [node["type"] for node in stored_table["rows"][2][0]["blocks"]] == ["paragraph", "image", "paragraph"]
        stored_cell = (stored_table["rows"][0][0] if position == "row" else stored_table["columns"][0])
        lead, retained_nested, tail = stored_cell["blocks"]
        assert lead["text"] == "Inspect the tray." and tail["text"] == "Set the sample aside."
        if position == "row":
            assert retained_nested["type"] == "ordered_list" and retained_nested["start"] == 4
            item, next_item = retained_nested["items"]
            assert item["number"] == 9 and item["text"] == "Position the sample."
            assert next_item == "Leave the setup undisturbed."
            inner_blocks = item["blocks"]
        else:
            assert retained_nested["type"] == "table" and retained_nested["columns"] == ["Inner reference"]
            inner_blocks = retained_nested["rows"][0][0]["blocks"]
        assert [node["type"] for node in inner_blocks] == ["paragraph", "image", "paragraph"]
        assert inner_blocks[0]["text"] == "Align the first mark."
        assert inner_blocks[2]["text"] == "Check the second mark."
        assert inner_blocks[1]["caption"] == "Registration marks on the sample"

    pending = list(_image_nodes(previews[0]["blocks"]))
    stored = captured.source_images
    assert len(pending) == len(stored) == 2
    assert [node["block_id"] for node in pending] == [node["block_id"] for node in stored]
    assert all(node["unavailable_reason"] == "SOURCE_MEDIA_PENDING" for node in pending)
    assert all(not {"asset_id", "alt", "storage_key", "content_sha256"} & node.keys() for node in pending)
    assert "outside.invalid" not in json.dumps(captured.source_document)
    assert "unverified/figure" not in json.dumps(captured.source_document)
    if available:
        assert captured.projection_status == "readable"
        assert all(node["status"] == "available" and node["content_sha256"] == sha256(PNG).hexdigest() for node in stored)
        assert all(capture_fixture.objects.data[node["storage_key"]] == (PNG, "image/png") for node in stored)
    else:
        assert captured.projection_status == "partial"
        assert all(node["status"] == "unavailable" and node["unavailable_reason"] == "SOURCE_NOT_FOUND" for node in stored)
        assert all("storage_key" not in node for node in stored)

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document,
        "body": captured.source_body,
        "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)
    assert normalized["normalized_document"] == captured.source_document
