from dataclasses import replace
from hashlib import sha256
from io import BytesIO

from PIL import Image

from autodata_ingestion.article_lifecycle_types import BANKONE_DEFINITION_HEADING_LAYOUT
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def test_bankone_definition_headings_leave_unmatched_and_nested_markup_alone():
    html = (
        '<dl><dt>Term</dt><dd><span class="satitle">Definition</span></dd></dl>'
        '<p>Inspect the seal.</p>'
        '<table><tr><td><dt class="document-subheader">Term</dt>'
        '<dd><span class="satitle">Definition</span></dd></td></tr></table>'
    )
    records = []
    for flag in (False, True):
        parser = ArticleParser(keep_bankone_definition_headings=flag)
        parser.feed(html)
        parser.close()
        parser.flush()
        assert not parser.bankone_definition_headings
        records.append(parser.blocks)
    assert records[0] == records[1]


def test_bankone_definition_headings_survive_preview_and_normalization(capture_fixture):
    payload = (
        b'<p>Inspect the seal.</p><dl><dt class="document-subheader">Correction</dt>'
        b'<dd><span class="satitle">Seals &amp; gaskets</span><ol start="3">'
        b'<li>Align the seal.<img src="/media/figure" alt="Alignment marks"></li>'
        b'</ol></dd></dl>'
    )
    image = BytesIO()
    Image.new("RGB", (24, 24), "green").save(image, format="PNG")
    capture_fixture.body("bankone", payload, assets=["figure"], asset_bindings=[
        {"source_url": "/media/figure", "resource_ref": "figure"},
    ])
    capture_fixture.body("bankone", image.getvalue(), "image/png", ref="figure", kind="asset")
    context = capture_fixture.context("bankone", asset_ref="figure")
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    legacy = capture_source_article(context, **options)
    previews = []
    captured = capture_source_article(
        context, **options, keep_bankone_definition_headings=True,
        on_body_preview=lambda _, document: previews.append(document),
    )
    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.resource_manifest[0]["sha256"] == sha256(payload).hexdigest()
    assert captured.resource_manifest[0]["bankone_definition_heading_layout"] == BANKONE_DEFINITION_HEADING_LAYOUT
    assert captured.resource_provenance[0]["bankone_definition_heading_layout"] == BANKONE_DEFINITION_HEADING_LAYOUT
    assert captured.source_images[0]["content_sha256"] == legacy.source_images[0]["content_sha256"]
    for document in (captured.source_document, previews[0]):
        assert [block["type"] for block in document["blocks"]] == ["paragraph", "heading", "heading", "ordered_list"]
        _, term, title, steps = document["blocks"]
        assert (term["level"], term["text"]) == (2, "Correction")
        assert (title["level"], title["text"]) == (3, "Seals & gaskets")
        assert steps["start"] == 3
        assert steps["items"][0]["text"] == "Align the seal."
        assert steps["items"][0]["blocks"][0]["type"] == "image"
    normalized = normalize_procedure_article(
        {"normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps},
        resource_manifest=captured.resource_manifest,
    )
    assert normalized["normalized_document"] == captured.source_document
    pinned = replace(context, legacy_published_bankone_definition_heading_body=sha256(payload).hexdigest())
    unchanged = capture_source_article(pinned, **options, keep_bankone_definition_headings=True)
    assert unchanged.source_document == legacy.source_document
    assert unchanged.source_fingerprint == legacy.source_fingerprint
