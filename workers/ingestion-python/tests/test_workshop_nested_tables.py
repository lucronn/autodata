"""Keep authentic nested supplier tables, figures and document placement."""

from io import BytesIO
import json

from PIL import Image
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import HTML_NESTED_TABLE_LAYOUT
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def _nested_html(*, nest, link_pdf):
    pdf = '<iframe src="/docs/pin-reference"></iframe>' if link_pdf else ""
    inner = (
        '<table><caption>Pin voltage limits</caption><tr><th>Pin</th><th>Voltage</th></tr>'
        f'<tr><td>Contact 3</td><td>4.5 V{pdf}</td></tr></table>'
    )
    outer = (
        '<table><caption>Connector test positions</caption><tr><th>Terminal</th><th>Limits and notes</th></tr>'
        '<tr><td>Ground circuit</td><td><p>Confirm the connector is locked.</p>'
        '<img alt="Ground connector diagram" data-resource-ref="diagram">'
        f'{inner if nest else ""}<p>Record the measurement.</p></td></tr>'
        '<tr><td>Ignition feed</td><td>12 V</td></tr></table>'
    )
    return f'<p>Remove the cover.</p>{outer}{"" if nest else inner}<p>Install the cover.</p>'


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("nest,link_pdf", [(True, False), (True, True), (False, False)])
def test_nested_table_keeps_authored_cells_through_rewrite(capture_fixture, provider, nest, link_pdf):
    html = _nested_html(nest=nest, link_pdf=link_pdf)
    raw, media = html.encode(), "text/html"
    if provider == "banktwo":
        raw = json.dumps({"_embedded": {"data": {"article": {"body": html}}}}).encode()
        media = "application/hal+json"
    png = BytesIO()
    Image.new("RGB", (96, 48), "blue").save(png, format="PNG")
    capture_fixture.body(provider, png.getvalue(), "image/png", ref="diagram", kind="asset")
    assets = ["diagram"]
    bindings = []
    if link_pdf:
        stream = BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(72, 720, "Check the voltage at the contact.")
        pdf.save()
        capture_fixture.body(provider, stream.getvalue(), "application/pdf", ref="pin-doc", kind="asset")
        assets.append("pin-doc")
        bindings.append({"source_url": "/docs/pin-reference", "resource_ref": "pin-doc"})
    capture_fixture.body(provider, raw, media, assets=assets, asset_bindings=bindings)
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_html_table_image_order=True, keep_html_table_captions=True,
                   keep_bound_pdf_iframes=True)
    legacy = capture_source_article(context, **options)
    captured = capture_source_article(context, keep_html_nested_tables=True, **options)
    assert captured.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert captured.projection_status == "readable"
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert "/docs/" not in repr(captured.source_document)
    [image] = captured.source_images
    assert image["alt"] == "Ground connector diagram" and image["status"] == "available"
    assert capture_fixture.objects.data[image["storage_key"]] == (png.getvalue(), "image/png")
    if not nest:
        assert captured.source_document == legacy.source_document
        assert captured.source_fingerprint == legacy.source_fingerprint
        assert captured.resource_manifest == legacy.resource_manifest
        return

    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.resource_manifest[0]["html_nested_table_layout"] == HTML_NESTED_TABLE_LAYOUT
    assert "Ground circuit" not in legacy.source_body
    before, outer, after = captured.source_document["blocks"]
    assert before["text"] == "Remove the cover." and after["text"] == "Install the cover."
    assert outer["label"] == "Connector test positions"
    assert "4.5 V" in captured.source_body
    heading, ground, ignition = outer["rows"]
    assert heading == ["Terminal", "Limits and notes"]
    assert ground[0] == "Ground circuit" and ignition == ["Ignition feed", "12 V"]
    lead, figure, inner, tail = ground[1]["blocks"]
    assert lead["text"] == "Confirm the connector is locked." and tail["text"] == "Record the measurement."
    assert figure == image and inner["label"] == "Pin voltage limits"
    assert inner["rows"][0] == ["Pin", "Voltage"] and inner["rows"][1][0] == "Contact 3"
    value = inner["rows"][1][1]
    if link_pdf:
        [document] = [resource for resource in captured.resources if resource["role"] == "document_asset"]
        measurement, reference = value["blocks"]
        assert measurement["text"] == "4.5 V"
        assert reference["text"] == "Check the voltage at the contact."
        assert reference["evidence_ids"] == [f"source:{document['source_snapshot_id']}"]
    else:
        assert value == "4.5 V"

    document = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    slots = prose_slots(document, include_cell_blocks=True)
    paraphrases = {"Remove the cover.": "Take off the cover.", "Install the cover.": "Fit the cover."}
    assert [slot["text"] for slot in slots] == list(paraphrases)
    response = {"introduction": "This procedure covers cover removal and installation.", "replacements": [
        {**slot, "action": "rewrite", "text": paraphrases[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(document, response)
    assert validate_auto(document, canonical, response=response).passed
    assert canonical["blocks"][2]["rows"] == outer["rows"]


def test_nested_table_depth_is_bounded():
    with pytest.raises(ValueError, match="HTML table nesting exceeds its limit"):
        ArticleParser(keep_html_nested_tables=True).feed("<table><tr><td>" * 9)


def test_nested_table_restores_parent_span_and_row_group():
    parser = ArticleParser(keep_html_nested_tables=True, keep_html_table_spans=True)
    parser.feed(
        '<table><tbody><tr><td rowspan="0"><table><tr><td colspan="2">Pins</td>'
        '</tr></table></td><td>First</td></tr><tr><td>Second</td></tr></tbody>'
        '<tbody><tr><td>Third</td><td>Last</td></tr></tbody></table>'
    )
    parser.close()
    [outer] = parser.blocks
    parent = outer["rows"][0][0]
    assert parent["_html_table_cell_spans"] == {"rowspan": 2}
    [inner] = parent["blocks"]
    assert inner["rows"][0][0]["_html_table_cell_spans"] == {"colspan": 2}
    assert len(outer["rows"][2]) == 2
