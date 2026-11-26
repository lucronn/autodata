from dataclasses import replace
from hashlib import sha256

from autodata_ingestion.article_lifecycle_types import BANKONE_LIST_BOUNDARY_LAYOUT
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def test_bankone_note_and_nested_lists_keep_the_source_order_and_numbered_steps():
    html = (
        '<ol start="5"><li>Prime the unit.</li>'
        '<div class="note"><p><b>Note:</b><ul><li>Watch the level.</li></ul></p></div>'
        '<li value="8">Inspect the outlet.</li><ol><div class="note"><p>Note: Stop if empty.</p></div>'
        '<li>Restore the level.</li></ol><li>Switch the unit off.</li></ol>'
        '<ol><li>Check the connection.<ul><li>Check the seal.</li></ul></li></ol>'
    )
    parser = ArticleParser(
        preserve_legacy_list_starts=False, keep_bankone_html_flow=True, keep_bankone_list_boundaries=True,
    )
    parser.feed(html)
    parser.close()
    parser.flush()
    assert parser.bankone_list_boundaries
    assert parser.blocks == [
        {"kind": "ordered_list", "start": 5, "items": ["Prime the unit."]},
        {"kind": "text", "text": "Note:"},
        {"kind": "unordered_list", "items": ["Watch the level."]},
        {"kind": "ordered_list", "start": 6, "items": [{"number": 8, "text": "Inspect the outlet."}]},
        {"kind": "text", "text": "Note: Stop if empty."},
        {"kind": "ordered_list", "items": ["Restore the level."]},
        {"kind": "ordered_list", "start": 9, "items": ["Switch the unit off."]},
        {"kind": "ordered_list", "items": [{
            "text": "Check the connection.",
            "blocks": [{"kind": "unordered_list", "items": ["Check the seal."]}],
        }]},
    ]


def test_new_capture_preserves_list_boundaries_without_replacing_an_unchanged_publication(capture_fixture):
    payload = (
        b'<ol><li>Check the fluid level.</li><ol><p>Note: Check when cold.</p>'
        b'<li>Check the lower mark.</li></ol><li>Install the cap.</li></ol>'
    )
    capture_fixture.body("bankone", payload)
    context = capture_fixture.context("bankone")
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects, keep_bankone_html_flow=True)
    legacy = capture_source_article(context, **options)
    previews = []
    captured = capture_source_article(
        context, **options, keep_bankone_list_boundaries=True,
        on_body_preview=lambda _, document: previews.append(document),
    )
    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.resource_manifest[0]["bankone_list_boundary_layout"] == BANKONE_LIST_BOUNDARY_LAYOUT
    for document in (captured.source_document, previews[0]):
        initial, notice, substeps, following = document["blocks"]
        assert initial["items"] == ["Check the fluid level."]
        assert notice["text"] == "Note: Check when cold."
        assert substeps["items"] == ["Check the lower mark."]
        assert following["start"] == 2 and following["items"] == ["Install the cap."]
    pinned = replace(context, legacy_published_bankone_list_boundary_body=sha256(payload).hexdigest())
    unchanged = capture_source_article(pinned, **options, keep_bankone_list_boundaries=True)
    assert unchanged.source_document == legacy.source_document
    assert unchanged.source_fingerprint == legacy.source_fingerprint
