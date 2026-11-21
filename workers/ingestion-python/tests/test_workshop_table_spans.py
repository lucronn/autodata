"""Keep authored table spans alongside protected values and cell figures."""

from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import HTML_TABLE_SPAN_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


_HEADING = "<thead><tr><th>Assembly</th><th>Fastener</th><th>Torque</th></tr></thead>"
_NESTED_FIGURE = '<img data-resource-ref="reference" alt="Housing diagram">Check the housing label.'


def _grid(shape):
    header = _HEADING
    assembly = "Pump housing"
    first_span = ""
    second_assembly = f"<td>{assembly}</td>"
    tail = ""
    if shape in ("rowspan", "rowgroup"):
        first_span = ' rowspan="2"' if shape == "rowspan" else ' rowspan="0"'
        assembly += _NESTED_FIGURE
        second_assembly = ""
        if shape == "rowgroup":
            tail = "<tbody><tr><td>Drain plate</td><td>Drain bolt</td><td>10 Nm</td></tr></tbody>"
    elif shape == "colspan":
        header = '<thead><tr><th colspan="2">Connection</th><th>Torque</th></tr></thead>'
    elif shape == "limited":
        # A positive rowspan cannot continue into the separate body group.
        header = _HEADING.replace("<th>", '<th rowspan="9">', 1)
    return (
        header + f"<tbody><tr><th{first_span}>{assembly}</th><td>Upper bolt</td><td>25 Nm</td></tr>"
        f"<tr>{second_assembly}<td>Lower bolt</td><td>12 Nm</td></tr></tbody>" + tail
    )


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("shape", ["rowspan", "colspan", "rowgroup", "flat", "limited"])
def test_html_table_spans_survive_capture_and_canonical_rewrite(capture_fixture, provider, shape):
    source_html = "<p>Remove the cover.</p><table>" + _grid(shape) + "</table><p>Install the cover.</p>"
    body, media_type = source_html.encode(), "text/html"
    if provider == "banktwo":
        body = json.dumps({"_embedded": {"data": {"article": {"body": source_html}}}}).encode()
        media_type = "application/hal+json"
    has_image = shape in ("rowspan", "rowgroup")
    capture_fixture.body(provider, body, media_type, assets=["reference"] if has_image else [])
    png = BytesIO()
    Image.new("RGB", (96, 48), "blue").save(png, format="PNG")
    if has_image:
        capture_fixture.body(provider, png.getvalue(), "image/png", kind="asset", ref="reference")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_html_table_image_order=True)
    legacy = capture_source_article(context, **options)
    captured = capture_source_article(context, keep_html_table_spans=True, **options)
    assert captured.body_source_snapshot_id == legacy.body_source_snapshot_id
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert not validate_ordered_document(captured.source_document, strict=True)
    assert captured.projection_status == "readable"
    table = captured.source_document["blocks"][1]
    rows = table["rows"]
    assert rows[2][-2:] == ["Lower bolt", "12 Nm"]

    if shape in ("flat", "limited"):
        assert captured.source_document == legacy.source_document
        assert captured.source_fingerprint == legacy.source_fingerprint
        assert captured.resource_manifest == legacy.resource_manifest
        return

    assert captured.source_fingerprint != legacy.source_fingerprint
    assert captured.resource_manifest[0]["html_table_span_layout"] == HTML_TABLE_SPAN_LAYOUT
    if shape == "colspan":
        assert rows[0] == [{"text": "Connection", "colspan": 2}, "Torque"]
    if has_image:
        cell = rows[1][0]
        assert cell["rowspan"] == 2
        assert len(rows[2]) == 2
        [image] = captured.source_images
        assert cell["blocks"][1] == image
        assert cell["blocks"][2]["text"] == "Check the housing label."
        assert capture_fixture.objects.data[image["storage_key"]] == (png.getvalue(), "image/png")
        if shape == "rowgroup":
            assert rows[3] == ["Drain plate", "Drain bolt", "10 Nm"]

    document = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    slots = prose_slots(document, include_cell_blocks=True)
    paraphrases = {"Remove the cover.": "Take off the cover.", "Install the cover.": "Fit the cover."}
    assert [slot["text"] for slot in slots] == list(paraphrases)
    reply = {"introduction": "This procedure covers cover removal and installation.", "replacements": [
        {**slot, "action": "rewrite", "text": paraphrases[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(document, reply)
    assert validate_auto(document, canonical, response=reply).passed
    assert canonical["blocks"][2]["rows"] == rows
