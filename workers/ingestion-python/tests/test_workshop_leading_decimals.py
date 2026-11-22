"""Preserve decimal measurements without erasing real compact step numbers."""

from base64 import b64encode
from io import BytesIO
import json

from reportlab.pdfgen import canvas
import pytest

from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle_types import LEADING_DECIMAL_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


_INTRO = "Remove the cover."
_MEASUREMENT = "4.5 V at pin 3."
_INSTRUCTION = "Check the ground connection."


def _native_pdf(lines):
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    text = pdf.beginText(72, 720)
    for line in lines:
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()
    return stream.getvalue()


def _article(provider, article):
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


def _bind_fixture(fixture, provider, shape, lines):
    if shape == "native PDF":
        fixture.body(provider, _native_pdf(lines), "application/pdf", kind="binary")
        return
    if shape == "linked PDF":
        fixture.body(provider, _native_pdf(lines[1:]), "application/pdf", ref="measurements", kind="asset")
        html = f'<p>{lines[0]}</p><iframe src="/docs/measurements"></iframe>'
        raw, media = (html.encode(), "text/html") if provider == "bankone" else _article(provider, {"body": html})
        fixture.body(provider, raw, media, assets=["measurements"],
                     asset_bindings=[{"source_url": "/docs/measurements", "resource_ref": "measurements"}])
        return
    if shape == "wrapped PDF":
        encoded = b64encode(_native_pdf(lines)).decode("ascii")
        raw, media = _article(provider, {"body": {"pdf": "data:application/pdf;base64," + encoded}})
    elif shape == "plain text":
        raw, media = "\n".join(lines).encode(), "text/plain"
    elif shape == "structured paragraphs":
        raw, media = _article(provider, {"blocks": [{"kind": "paragraph", "text": "\n".join(lines)}]})
    else:
        html = "".join(f"<p>{line}</p>" for line in lines)
        raw, media = (html.encode(), "text/html") if provider == "bankone" else _article(provider, {"body": html})
    fixture.body(provider, raw, media)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("shape", ["HTML", "structured paragraphs", "plain text", "native PDF", "wrapped PDF", "linked PDF"])
@pytest.mark.parametrize("measurement", [_MEASUREMENT, "-" + _MEASUREMENT, None], ids=["positive", "negative", "compact-ordinal"])
def test_capture_preserves_leading_decimal_and_compact_numbered_step(capture_fixture, provider, shape, measurement):
    lines = [_INTRO] + ([measurement] if measurement else []) + ["4." + _INSTRUCTION]
    _bind_fixture(capture_fixture, provider, shape, lines)
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects,
                   keep_pdf_figure_order=True, keep_embedded_pdf=True, keep_bound_pdf_iframes=True)
    original = capture_source_article(context, **options)
    corrected = capture_source_article(context, keep_leading_decimals=True, **options)
    assert not validate_ordered_document(corrected.source_document, strict=True)
    assert corrected.body_source_snapshot_id == original.body_source_snapshot_id
    assert corrected.evidence_manifest == original.evidence_manifest
    assert corrected.resource_manifest[1:] == original.resource_manifest[1:]
    assert corrected.projection_status == "readable"
    [step] = corrected.source_steps
    assert step["number"] == 4 and step["text"] == _INSTRUCTION
    if not measurement:
        assert corrected.source_fingerprint == original.source_fingerprint
        assert corrected.resource_manifest == original.resource_manifest
        assert corrected.source_document == original.source_document
        return

    if measurement.startswith("-") and shape == "HTML":
        legacy = normalize_procedure_article({
            "normalized_document": original.source_document, "body": original.source_body, "steps": original.source_steps,
        }, resource_manifest=original.resource_manifest)["normalized_document"]
        assert legacy["blocks"][1]["text"] == "5 V at pin 3."
    else:
        assert original.source_document["blocks"][1]["type"] == "step"
        assert original.source_document["blocks"][1]["text"] == "5 V at pin 3."
    assert corrected.source_fingerprint != original.source_fingerprint
    assert corrected.resource_manifest[0]["leading_decimal_layout"] == LEADING_DECIMAL_LAYOUT
    assert corrected.source_document["blocks"][1]["type"] == "paragraph"
    assert corrected.source_body.splitlines() == [_INTRO, measurement, _INSTRUCTION]
    document = normalize_procedure_article({
        "normalized_document": corrected.source_document, "body": corrected.source_body, "steps": corrected.source_steps,
    }, resource_manifest=corrected.resource_manifest)["normalized_document"]
    assert document == corrected.source_document
    if shape == "linked PDF":
        [pdf] = [item for item in corrected.resources if item["role"] == "document_asset"]
        assert document["blocks"][1]["evidence_ids"] == [f"source:{pdf['source_snapshot_id']}"]

    slots = prose_slots(document, include_cell_blocks=True)
    paraphrases = {_INTRO: "Take off the cover.", _INSTRUCTION: "Inspect the ground connection."}
    reply = {"introduction": "This procedure covers a ground connection inspection.", "replacements": [
        {**slot, "action": "rewrite", "text": paraphrases[slot["text"]], "reason": ""}
        if slot["text"] != measurement else
        {**slot, "action": "retain", "text": measurement, "reason": "Exact voltage and pin reference"}
        for slot in slots
    ]}
    canonical = render_auto(document, reply)
    assert validate_auto(document, canonical, response=reply).passed
    assert canonical["blocks"][2]["text"] == measurement
    assert canonical["blocks"][3]["number"] == 4
