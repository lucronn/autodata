"""Supplier headings containing only a protected figure keep their source position."""

from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import STRUCTURED_HEADING_IMAGE_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite import build_rewrite_prompt, rewrite_ordered_document
from autodata_ingestion.source_article_capture import capture_source_article
from test_procedure_rewrite_full import Draft
from test_source_article_capture import capture_fixture


def _supplier_heading(provider, title=""):
    heading = {"type": "heading", "text": title, "level": 3, "images": [{
        "asset_resource_ref": "figure", "alt": "Seal position", "caption": "Seal alignment witness marks",
        "storage_key": "unverified/connector/path", "url": "https://outside.invalid/not-authorized.png",
    }]}
    article = {"blocks": [
        {"type": "paragraph", "text": "Remove the pump."},
        heading,
        {"type": "paragraph", "text": "Inspect the seal."},
        {"type": "paragraph", "text": "Install the replacement."},
    ]}
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


def _capture_pair(fixture, provider, *, available=True, title=""):
    raw, media = _supplier_heading(provider, title)
    fixture.body(provider, raw, media, assets=["figure"])
    parts = BytesIO()
    Image.new("RGB", (11, 9), "#357895").save(parts, format="PNG")
    png = parts.getvalue()
    if available:
        fixture.body(provider, png, "image/png", ref="figure", kind="asset")
    context = fixture.context(provider)
    options = {"registry": fixture.registry, "object_store": fixture.objects}
    legacy = capture_source_article(context, **options)
    corrected = capture_source_article(context, keep_image_only_headings=True, **options)
    return legacy, corrected, png


@pytest.mark.parametrize("provider,available", [("bankone", True), ("banktwo", True), ("banktwo", False)])
def test_image_only_heading_retains_authorized_figure_at_source_position(capture_fixture, provider, available):
    legacy, captured, png = _capture_pair(capture_fixture, provider, available=available)
    assert not legacy.source_images
    assert captured.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.resource_manifest[0]["structured_heading_image_layout"] == STRUCTURED_HEADING_IMAGE_LAYOUT
    assert captured.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.source_body == legacy.source_body
    assert captured.projection_version == "source-projection-v5"
    assert captured.projection_status == ("readable" if available else "partial")

    blocks = captured.source_document["blocks"]
    assert [block["type"] for block in blocks] == ["paragraph", "image", "paragraph", "paragraph"]
    assert blocks[0]["text"] == "Remove the pump." and blocks[2]["text"] == "Inspect the seal."
    figure = blocks[1]
    assert figure["alt"] == "Seal position" and figure["caption"] == "Seal alignment witness marks"
    [image] = captured.source_images
    assert image["asset_id"] == figure["asset_id"]
    assert "outside.invalid" not in json.dumps(blocks) and "unverified/connector/path" not in json.dumps(blocks)
    if available:
        assert image["content_sha256"] == sha256(png).hexdigest()
        assert capture_fixture.objects.data[image["storage_key"]] == (png, "image/png")
    else:
        assert figure["status"] == "unavailable" and figure["unavailable_reason"] == "SOURCE_NOT_FOUND"
        assert "storage_key" not in image
    assert not validate_ordered_document(captured.source_document, strict=True)

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    profile = "full-prose-auto-v1"
    slots = json.loads(build_rewrite_prompt(normalized, context={}, profile_version=profile))["slots"]
    assert [slot["text"] for slot in slots] == ["Remove the pump.", "Inspect the seal.", "Install the replacement."]
    response = {
        "introduction": "This procedure describes pump service.",
        "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite", "text": text, "reason": ""}
            for slot, text in zip(slots, ("Take off the pump.", "Check the seal.", "Fit the replacement."), strict=True)
        ],
    }
    rewritten = rewrite_ordered_document(normalized, client=Draft(response), context={}, profile_version=profile)
    assert rewritten.error_code is None
    assert rewritten.document["blocks"][1]["text"] == "Take off the pump."
    assert rewritten.document["blocks"][2] == {**normalized["blocks"][1], "source_order": 3}
    assert rewritten.document["blocks"][3]["text"] == "Check the seal."


def test_text_bearing_heading_keeps_its_existing_projection(capture_fixture):
    legacy, captured, _ = _capture_pair(capture_fixture, "bankone", title="Seal alignment")
    assert captured.source_fingerprint == legacy.source_fingerprint
    assert captured.source_document == legacy.source_document
    assert captured.projection_version == legacy.projection_version
    assert captured.source_document["blocks"][1]["type"] == "heading"
