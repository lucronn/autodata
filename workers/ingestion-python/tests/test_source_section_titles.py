from dataclasses import replace
from hashlib import sha256
import json

import pytest

from autodata_ingestion.article_lifecycle_types import HTML_SECTION_TITLE_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("media_type", ["text/html", "application/hal+json"])
def test_standalone_section_titles_keep_their_source_role(capture_fixture, provider, media_type):
    html = (
        '<p><b>Removal</b></p><ol><li>Remove the cover.</li></ol>'
        '<img data-resource-ref="figure" alt="Fastener layout">'
        '<p><strong>All&nbsp;Vehicles</strong></p>'
        '<p><b>Installation</b></p><p><b>Align the seal.</b></p>'
        '<p><b>Removal</b> requires checking the seal.</p>'
    )
    payload = html.encode() if media_type == "text/html" else json.dumps({
        "_embedded": {"data": {"article": {"body": html}}},
    }).encode()
    capture_fixture.body(provider, payload, media_type)
    context = capture_fixture.context(provider, asset_ref="figure")
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    previews = []
    before = capture_source_article(context, **options)
    after = capture_source_article(
        context, keep_html_section_titles=True,
        on_body_preview=lambda _, document: previews.append(document), **options,
    )
    assert before.source_fingerprint != after.source_fingerprint
    assert before.source_images == after.source_images
    assert len(after.source_images) == 1
    assert after.resource_manifest[0]["sha256"] == sha256(payload).hexdigest()
    assert after.resource_manifest[0]["html_section_title_layout"] == HTML_SECTION_TITLE_LAYOUT
    assert [block["type"] for block in after.source_document["blocks"]] == [
        "heading", "ordered_list", "image", "heading", "heading", "paragraph", "paragraph",
    ]
    headings = [
        (block["text"], block["level"]) for block in after.source_document["blocks"] if block["type"] == "heading"
    ]
    assert headings == [("Removal", 2), ("All Vehicles", 3), ("Installation", 2)]
    assert [slot["text"] for slot in prose_slots(after.source_document)] == [
        "Remove the cover.", "Align the seal.", "Removal requires checking the seal.",
    ]
    assert [block["type"] for block in previews[0]["blocks"]] == [
        block["type"] for block in after.source_document["blocks"]
    ]
    normalized = normalize_procedure_article(
        {"normalized_document": after.source_document, "body": after.source_body, "steps": after.source_steps},
        resource_manifest=after.resource_manifest,
    )
    assert normalized["normalized_document"] == after.source_document

    legacy = replace(context, legacy_published_html_section_title_body=sha256(payload).hexdigest())
    retained = capture_source_article(legacy, keep_html_section_titles=True, **options)
    assert retained.source_document == before.source_document
    assert retained.source_fingerprint == before.source_fingerprint
