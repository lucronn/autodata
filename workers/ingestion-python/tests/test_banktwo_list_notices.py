from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion.article_lifecycle_types import BANKTWO_LIST_NOTICE_LAYOUT
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def test_notices_keep_their_position_and_the_authored_list_counter():
    parser = ArticleParser(keep_banktwo_list_notices=True, preserve_legacy_list_starts=False)
    parser.feed(
        '<ol start="3"><li>Inspect the cover.</li>'
        '<div><b>Note:</b> Check the ring (2).<br>Keep it in place.<br></div>'
        '<div><strong>Caution:</strong> Avoid touching the seal.</div>'
        '<li value="8">Align the cover.</li>'
        '<div><b>Warning:</b> Keep fingers clear.</div><li>Install the cover.</li></ol>'
        '<ol><li>Verify the cover.</li></ol>'
    )
    parser.close()
    parser.flush()
    assert parser.banktwo_list_notices
    assert parser.blocks == [
        {"kind": "ordered_list", "start": 3, "items": ["Inspect the cover."]},
        {"kind": "callout", "label": "Note", "text": "Check the ring (2). Keep it in place."},
        {"kind": "callout", "label": "Caution", "text": "Avoid touching the seal."},
        {"kind": "ordered_list", "start": 4, "items": [{"number": 8, "text": "Align the cover."}]},
        {"kind": "callout", "label": "Warning", "text": "Keep fingers clear."},
        {"kind": "ordered_list", "start": 9, "items": ["Install the cover."]},
        {"kind": "ordered_list", "items": ["Verify the cover."]},
    ]


@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"])
def test_capture_keeps_a_notice_with_its_procedure_in_preview_and_source(capture_fixture, media_type):
    html = (
        '<ol><li>Remove the cap.<img src="/media/figure" alt="Cap placement"></li>'
        '<div><b>Note:</b> Inspect the cap (1) and seal (2), replace only if damaged.<br></div>'
        '<li>Install the cap.</li></ol>'
    )
    payload = html.encode() if media_type == "text/html" else json.dumps({
        "_embedded": {"data": {"article": {"content": html}}},
    }).encode()
    capture_fixture.body("banktwo", payload, media_type, assets=["figure"], asset_bindings=[
        {"source_url": "/media/figure", "resource_ref": "figure"},
    ])
    figure = BytesIO()
    Image.new("RGB", (24, 24), "green").save(figure, format="PNG")
    capture_fixture.body("banktwo", figure.getvalue(), "image/png", ref="figure", kind="asset")
    context = capture_fixture.context("banktwo", asset_ref="figure")
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    before = capture_source_article(context, **options)
    previews = []
    captured = capture_source_article(
        context, keep_banktwo_list_notices=True, **options,
        on_body_preview=lambda _, document: previews.append(document),
    )
    assert captured.source_fingerprint != before.source_fingerprint
    assert captured.resource_manifest[0]["sha256"] == sha256(payload).hexdigest()
    assert captured.resource_manifest[0]["banktwo_list_notice_layout"] == BANKTWO_LIST_NOTICE_LAYOUT
    assert captured.resource_provenance[0]["banktwo_list_notice_layout"] == BANKTWO_LIST_NOTICE_LAYOUT
    assert len(captured.source_images) == len(before.source_images) == 1
    assert captured.source_images[0]["content_sha256"] == before.source_images[0]["content_sha256"]
    expected_notice = "Inspect the cap (1) and seal (2), replace only if damaged."
    for document in (captured.source_document, previews[0]):
        assert [block["type"] for block in document["blocks"]] == ["ordered_list", "callout", "ordered_list"]
        first, notice, last = document["blocks"]
        assert first["items"][0]["text"] == "Remove the cap."
        assert first["items"][0]["blocks"][0]["type"] == "image"
        assert notice["label"] == "Note" and notice["text"] == expected_notice
        assert last["start"] == 2 and last["items"] == ["Install the cap."]
    normalized = normalize_procedure_article(
        {"normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps},
        resource_manifest=captured.resource_manifest,
    )
    assert normalized["normalized_document"] == captured.source_document

    legacy = replace(context, legacy_published_banktwo_list_notice_body=sha256(payload).hexdigest())
    recaptured = capture_source_article(legacy, keep_banktwo_list_notices=True, **options)
    assert recaptured.source_document == before.source_document
    assert recaptured.source_fingerprint == before.source_fingerprint
