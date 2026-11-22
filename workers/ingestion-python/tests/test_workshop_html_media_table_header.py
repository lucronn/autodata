"""Keep a supplier chart and linked PDF in their authored column header."""

from hashlib import sha256
from io import BytesIO
import json

from PIL import Image
from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import HTML_MEDIA_TABLE_HEADER_LAYOUT
from autodata_ingestion.banktwo_connector import ArticleParser
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


_HEADER = (
    '<thead><tr><th scope="col">Check the pressure scale.'
    '<figure><img src="/fixture/chart.png" alt="Pressure chart">'
    '<figcaption>Pressure at 2,000 rpm</figcaption></figure>'
    'Read the upper line.{pdf}<p>Record the result.</p></th><th>Limit</th></tr></thead>'
)
_ROWS = '<tbody><tr><td>Supply</td><td>500 kPa</td></tr></tbody>'
_PDF = '<iframe src="/fixture/drive.pdf">Hidden fallback.</iframe>'


def _capture_pair(fixture, provider, *, linked=True):
    chart = BytesIO()
    Image.new("RGB", (96, 48), "navy").save(chart, format="PNG")
    fixture.body(provider, chart.getvalue(), "image/png", ref="chart", kind="asset")
    assets = ["chart"]
    bindings = [{"source_url": "/fixture/chart.png", "resource_ref": "chart"}]
    document = BytesIO()
    if linked:
        pdf = canvas.Canvas(document, invariant=1)
        pdf.drawString(72, 720, "Confirm the drive witness mark.")
        pdf.save()
        fixture.body(provider, document.getvalue(), "application/pdf", ref="drive", kind="asset")
        assets.append("drive")
        bindings.append({"source_url": "/fixture/drive.pdf", "resource_ref": "drive"})
    header = _HEADER.format(pdf=_PDF if linked else "")
    html = (
        '<p>Remove the cover.</p><table><caption>Pressure data</caption>'
        f'{header}{_ROWS}</table><p>Install the cover.</p>'
    )
    payload, media = html.encode(), "text/html"
    if provider == "banktwo":
        payload = json.dumps({"_embedded": {"data": {"article": {"body": html}}}}).encode()
        media = "application/hal+json"
    fixture.body(provider, payload, media, assets=assets, asset_bindings=bindings)
    context = fixture.context(provider)
    options = dict(
        registry=fixture.registry, object_store=fixture.objects, keep_html_table_image_order=True,
        keep_html_figure_captions=True, keep_html_table_captions=True, keep_html_table_spans=True,
        keep_html_nested_tables=True, keep_bound_pdf_iframes=True, keep_pdf_figure_order=True,
        keep_structured_table_columns=True, keep_structured_table_column_order=True,
    )
    legacy = capture_source_article(context, **options)
    corrected = capture_source_article(context, keep_html_media_table_headers=True, **options)
    return legacy, corrected, chart.getvalue(), document.getvalue()


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("linked", [False, True])
def test_html_chart_and_pdf_keep_their_column_header(capture_fixture, provider, linked):
    legacy, capture, png, pdf = _capture_pair(capture_fixture, provider, linked=linked)
    assert capture.projection_status == "readable"
    assert capture.projection_version == legacy.projection_version
    assert capture.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert capture.source_fingerprint != legacy.source_fingerprint
    assert capture.resource_manifest[0]["html_media_table_header_layout"] == HTML_MEDIA_TABLE_HEADER_LAYOUT
    assert capture.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert capture.evidence_manifest == legacy.evidence_manifest
    assert capture.source_body == legacy.source_body
    assert "Pressure at 2,000 rpm\nRead the upper line." in capture.source_body
    assert "Hidden fallback" not in capture.source_body and "/fixture/" not in repr(capture.source_document)
    assert not validate_ordered_document(capture.source_document, strict=True)

    old_table = legacy.source_document["blocks"][1]
    assert not old_table.get("columns") and old_table["rows"][0][1] == "Limit"
    _, table, _ = capture.source_document["blocks"]
    header, limit = table["columns"]
    assert table["label"] == "Pressure data"
    assert limit == "Limit" and table["rows"] == [["Supply", "500 kPa"]]
    assert [child.get("text") or child.get("alt") for child in header["blocks"]] == [
        "Check the pressure scale.", "Pressure chart", "Read the upper line.",
        *(["Confirm the drive witness mark."] if linked else []), "Record the result.",
    ]
    [image] = capture.source_images
    assert header["blocks"][1] == image
    assert image["block_id"] == table["block_id"] + ":column:0001:block:0002"
    assert image["caption"] == "Pressure at 2,000 rpm"
    assert image["image_id"] == legacy.source_images[0]["image_id"]
    assert image["content_sha256"] == sha256(png).hexdigest()
    assert capture_fixture.objects.data[image["storage_key"]] == (png, "image/png")
    if linked:
        [reference] = [resource for resource in capture.resources if resource["role"] == "document_asset"]
        assert header["blocks"][3]["evidence_ids"] == [f"source:{reference['source_snapshot_id']}"]
        assert capture_fixture.objects.data[reference["object_key"]] == (pdf, "application/pdf")

    normalized = normalize_procedure_article({
        "normalized_document": capture.source_document, "body": capture.source_body, "steps": capture.source_steps,
    }, resource_manifest=capture.resource_manifest)["normalized_document"]
    slots = prose_slots(normalized, include_cell_blocks=True)
    assert [slot["text"] for slot in slots] == ["Remove the cover.", "Install the cover."]
    reply = {"introduction": "This procedure covers cover removal and installation.", "replacements": [
        {**slot, "action": "rewrite", "text": text, "reason": ""}
        for slot, text in zip(slots, ("Take off the cover.", "Fit the cover."), strict=True)
    ]}
    canonical = render_auto(normalized, reply)
    assert validate_auto(normalized, canonical, response=reply).passed
    assert canonical["blocks"][2]["columns"] == table["columns"]
    assert canonical["blocks"][2]["rows"] == table["rows"]


@pytest.mark.parametrize("head", [
    '<thead><tr><th>Pressure</th><th>Limit</th></tr></thead>',
    '<thead><tr><th><img data-resource-ref="chart"></th><td>Limit</td></tr></thead>',
    '<thead><tr><th scope="row"><img data-resource-ref="chart"></th><th>Limit</th></tr></thead>',
    '<thead><tr><th colspan="2"><img data-resource-ref="chart"></th></tr></thead>',
    '<thead><tr><th><img data-resource-ref="chart"></th></tr><tr><th>Pressure</th></tr></thead>',
    '<tr><th><img data-resource-ref="chart"></th><th>Limit</th></tr>',
])
def test_html_media_header_leaves_other_table_shapes_compatible(head):
    html = f"<table>{head}{_ROWS}</table>"
    expected = ArticleParser(keep_html_table_spans=True)
    actual = ArticleParser(keep_html_table_spans=True, keep_html_media_table_headers=True)
    for parser in (expected, actual):
        parser.feed(html)
        parser.close()
    assert not actual.html_media_table_headers
    assert actual.blocks == expected.blocks
