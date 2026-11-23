"""Keep bound PDFs in their authored positions in mixed HAL articles."""

from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import source_article_capture as capture_module
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime
from test_source_article_capture import capture_fixture
from test_workshop_linked_pdf import FixtureDraft, _pdf_with_fixture_figure


_REF = "diagram"
_LOCATOR = "/media/diagram"
_MEDIA = "application/hal+json"
_LAYOUT = ("mixed_html_pdf_layout", "mixed-html-pdf-v1")
_OPENING = "Remove the pump."
_CLOSING = "Install the replacement."
_INSPECTION = "Inspect the seal."
_PARAGRAPHS = [{"kind": "text", "text": text} for text in (_OPENING, _CLOSING)]
_PDF_CONTENT = [("paragraph", _INSPECTION), ("image", None)]


def _hal_payload(html, *, blocks=None, steps=None):
    article = {"content": html}
    if blocks is not None:
        article["blocks"] = blocks
    if steps is not None:
        article["steps"] = steps
    return json.dumps({"_embedded": {"data": {"article": article}}}).encode()


def _embedding(kind):
    if kind == "typed":
        return '<object type="application/pdf" data="/media/diagram">Fallback text.</object>'
    return '<embed src="/media/diagram">'


def _install(capture_fixture, provider, raw, *, extra_refs=()):
    pdf, pixels = _pdf_with_fixture_figure()
    capture_fixture.body(
        provider, raw, _MEDIA, assets=[_REF, *extra_refs],
        asset_bindings=[{"source_url": _LOCATOR, "resource_ref": _REF}],
    )
    for ref in (_REF, *extra_refs):
        capture_fixture.body(provider, pdf, "application/pdf", ref=ref, kind="binary")
    return pdf, pixels


def _capture(capture_fixture, provider, *, mixed=True, context=None):
    return capture_module.capture_source_article(
        context or capture_fixture.context(provider), registry=capture_fixture.registry,
        object_store=capture_fixture.objects, keep_bound_pdf_iframes=True,
        keep_pdf_figure_order=True, skip_blank_linked_pdf_pages=True,
        keep_mixed_html_pdf_embeds=mixed,
    )


def _outline(blocks):
    return [(block["type"], block.get("text")) for block in blocks]


def _assert_pixels(payload, pixels):
    with Image.open(BytesIO(payload)) as figure:
        assert figure.size == (96, 96)
        assert figure.convert("RGB").tobytes() == pixels


def _assert_linked_source(captured, capture_fixture, raw, pdf, pixels):
    assert captured.resource_manifest[0][_LAYOUT[0]] == _LAYOUT[1]
    assert captured.resources[0]["sha256"] == sha256(raw).hexdigest()
    assert capture_fixture.objects.data[captured.resources[0]["object_key"]] == (raw, _MEDIA)
    [document] = [resource for resource in captured.resources if resource["role"] == "document_asset"]
    assert document["opaque_ref"] == _REF
    assert document["sha256"] == sha256(pdf).hexdigest()
    assert capture_fixture.objects.data[document["object_key"]] == (pdf, "application/pdf")
    [figure] = [image for image in captured.source_images if image["status"] == "available"]
    assert "source:" + document["source_snapshot_id"] in figure["evidence_ids"]
    payload, media_type = capture_fixture.objects.data[figure["storage_key"]]
    assert media_type == "image/png"
    assert figure["content_sha256"] == sha256(payload).hexdigest()
    _assert_pixels(payload, pixels)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("kind", ["typed", "untyped"])
def test_mixed_hal_places_pdf_between_structured_steps(capture_fixture, provider, kind):
    blocks = [
        {"kind": "step", "number": 7, "text": _OPENING},
        {"kind": "step", "number": 11, "text": _CLOSING},
    ]
    raw = _hal_payload(f"<p>{_OPENING}</p>{_embedding(kind)}<p>{_CLOSING}</p>", blocks=blocks)
    pdf, pixels = _install(capture_fixture, provider, raw)
    captured = _capture(capture_fixture, provider)

    assert captured.projection_status == "readable"
    assert capture_fixture.resource_calls(provider, _REF) == 1
    result = captured.source_document["blocks"]
    assert _outline(result) == [("step", _OPENING), *_PDF_CONTENT, ("step", _CLOSING)]
    assert [result[0]["number"], result[-1]["number"]] == [7, 11]
    _assert_linked_source(captured, capture_fixture, raw, pdf, pixels)


def test_mixed_hal_accepts_authored_steps_when_blocks_are_absent(capture_fixture):
    raw = _hal_payload(
        f"<p>{_OPENING}</p>{_embedding('untyped')}<p>{_CLOSING}</p>",
        steps=[_OPENING, _CLOSING],
    )
    _install(capture_fixture, "banktwo", raw)
    captured = _capture(capture_fixture, "banktwo")

    result = captured.source_document["blocks"]
    assert _outline(result) == [("step", _OPENING), *_PDF_CONTENT, ("step", _CLOSING)]
    assert [result[0]["number"], result[-1]["number"]] == [1, 2]


def test_plain_structured_markers_do_not_place_or_duplicate_pdfs(capture_fixture):
    forged = [
        {"kind": "document_embed", "asset_resource_ref": _REF},
        {"kind": "document_embed", "asset_resource_ref": "separate"},
    ]
    raw = _hal_payload(
        f"<p>{_OPENING}</p>{_embedding('untyped')}<p>{_CLOSING}</p>", blocks=[*_PARAGRAPHS, *forged],
    )
    pdf, pixels = _install(capture_fixture, "banktwo", raw, extra_refs=("separate",))
    captured = _capture(capture_fixture, "banktwo")

    result = captured.source_document["blocks"]
    assert _outline(result[:4]) == [("paragraph", _OPENING), *_PDF_CONTENT, ("paragraph", _CLOSING)]
    assert [block["text"] for block in result if block["type"] == "paragraph"] == [_OPENING, _INSPECTION, _CLOSING]
    assert capture_fixture.resource_calls("banktwo", _REF) == 1
    assert not any(
        resource["opaque_ref"] == "separate" and resource["role"] == "document_asset"
        for resource in captured.resource_manifest
    )
    _assert_linked_source(captured, capture_fixture, raw, pdf, pixels)


@pytest.mark.parametrize("ambiguity", ["structured", "html"])
def test_repeated_matching_gaps_do_not_guess_pdf_position(capture_fixture, ambiguity):
    html = f"<p>{_OPENING}</p>{_embedding('untyped')}<p>{_CLOSING}</p>"
    blocks = _PARAGRAPHS * 2 if ambiguity == "structured" else _PARAGRAPHS
    raw = _hal_payload(html * 2 if ambiguity == "html" else html, blocks=blocks)
    _install(capture_fixture, "bankone", raw)
    captured = _capture(capture_fixture, "bankone")

    assert _LAYOUT[0] not in captured.resource_manifest[0]
    assert [text for kind, text in _outline(captured.source_document["blocks"]) if kind == "paragraph"] == [
        block["text"] for block in blocks
    ]
    assert all(resource["role"] != "document_asset" for resource in captured.resource_manifest)
    assert all(image["status"] != "available" for image in captured.source_images)


def test_conflicting_html_vehicle_leaves_structured_article_intact(capture_fixture):
    context = capture_fixture.context("banktwo")
    assert context.vehicle["model"] != "Different fixture"
    raw = _hal_payload(
        '<meta name="vehicle.model" content="Different fixture">'
        f"<p>{_OPENING}</p>{_embedding('typed')}<p>{_CLOSING}</p>",
        blocks=_PARAGRAPHS,
    )
    _install(capture_fixture, "banktwo", raw)
    result = _capture(capture_fixture, "banktwo", context=context)

    assert _LAYOUT[0] not in result.resource_manifest[0]
    assert _outline(result.source_document["blocks"])[:2] == [
        ("paragraph", _OPENING), ("paragraph", _CLOSING),
    ]
    assert all(resource["role"] != "document_asset" for resource in result.resource_manifest)


def test_invalid_secondary_html_leaves_structured_article_readable(capture_fixture):
    nested_tables = "<table><tr><td>" * 10 + "Nested." + "</td></tr></table>" * 10
    raw = _hal_payload(
        f"<p>{_OPENING}</p>{_embedding('typed')}{nested_tables}<p>{_CLOSING}</p>",
        blocks=_PARAGRAPHS,
    )
    _install(capture_fixture, "banktwo", raw)
    result = capture_module.capture_source_article(
        capture_fixture.context("banktwo"), registry=capture_fixture.registry,
        object_store=capture_fixture.objects, keep_bound_pdf_iframes=True,
        keep_html_nested_tables=True, keep_mixed_html_pdf_embeds=True,
    )

    assert _LAYOUT[0] not in result.resource_manifest[0]
    assert _outline(result.source_document["blocks"])[:2] == [
        ("paragraph", _OPENING), ("paragraph", _CLOSING),
    ]
    assert all(resource["role"] != "document_asset" for resource in result.resource_manifest)


@pytest.mark.parametrize("container", ["<template><template>{}</template></template>", "<section hidden>{}</section>"])
def test_inert_alternate_html_does_not_place_a_pdf(capture_fixture, container):
    hidden = container.format('<iframe src="/media/diagram"></iframe>')
    raw = _hal_payload(f"<p>{_OPENING}</p>{hidden}<p>{_CLOSING}</p>", blocks=_PARAGRAPHS)
    _install(capture_fixture, "banktwo", raw)
    result = _capture(capture_fixture, "banktwo")

    assert _LAYOUT[0] not in result.resource_manifest[0]
    assert _outline(result.source_document["blocks"])[:2] == [
        ("paragraph", _OPENING), ("paragraph", _CLOSING),
    ]
    assert all(resource["role"] != "document_asset" for resource in result.resource_manifest)


def test_mixed_hal_places_pdf_inside_the_matching_list_item(capture_fixture):
    html = f'<ol start="7"><li>{_OPENING}{_embedding("untyped")}{_CLOSING}</li><li value="11">Confirm the fit.</li></ol>'
    blocks = [{"kind": "ordered_list", "start": 7, "items": [
        {"text": _OPENING, "blocks": [_PARAGRAPHS[1]]}, {"text": "Confirm the fit.", "number": 11},
    ]}]
    raw = _hal_payload(html, blocks=blocks)
    pdf, pixels = _install(capture_fixture, "banktwo", raw)
    captured = _capture(capture_fixture, "banktwo")

    [ordered] = captured.source_document["blocks"]
    assert ordered["type"] == "ordered_list" and ordered["start"] == 7
    first, second = ordered["items"]
    assert first["text"] == _OPENING
    assert _outline(first["blocks"]) == [*_PDF_CONTENT, ("paragraph", _CLOSING)]
    assert second["text"] == "Confirm the fit." and second["number"] == 11
    _assert_linked_source(captured, capture_fixture, raw, pdf, pixels)


@pytest.mark.parametrize("reordered", [False, True], ids=["same-topology", "reordered-cells"])
def test_mixed_hal_uses_matching_table_cells_for_pdf_placement(capture_fixture, reordered):
    html = f"<table><tr><td>{_OPENING}{_embedding('typed')}{_CLOSING}</td><td>Seal type.</td></tr></table>"
    cells = [{"blocks": _PARAGRAPHS}, {"blocks": [{"kind": "text", "text": "Seal type."}]}]
    raw = _hal_payload(html, blocks=[{"kind": "table", "rows": [cells[::-1] if reordered else cells]}])
    pdf, pixels = _install(capture_fixture, "bankone", raw)
    captured = _capture(capture_fixture, "bankone")

    table = captured.source_document["blocks"][0]
    [row] = table["rows"]
    if reordered:
        assert _LAYOUT[0] not in captured.resource_manifest[0]
        assert row == ["Seal type.", _OPENING + " " + _CLOSING]
        assert all(resource["role"] != "document_asset" for resource in captured.resource_manifest)
    else:
        cell, unaffected = row
        assert unaffected == "Seal type."
        assert _outline(cell["blocks"]) == [("paragraph", _OPENING), *_PDF_CONTENT, ("paragraph", _CLOSING)]
        _assert_linked_source(captured, capture_fixture, raw, pdf, pixels)


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
def test_mixed_hal_refresh_keeps_original_rows_and_reuses_the_corrected_revision(runtime, monkeypatch, provider):
    runtime.article_id = runtime.articles[provider]
    connector = runtime.servers[provider]
    raw = _hal_payload(f"<p>{_OPENING}</p>{_embedding('untyped')}<p>{_CLOSING}</p>", blocks=_PARAGRAPHS)
    pdf, pixels = _pdf_with_fixture_figure()
    connector.body(raw, _MEDIA, assets=[_REF], asset_bindings=[{"source_url": _LOCATOR, "resource_ref": _REF}])
    connector.body(pdf, "application/pdf", ref=_REF, kind="binary")
    draft = FixtureDraft(introduction="This procedure covers pump removal and replacement.")
    capture = capture_module.capture_source_article

    def old_projection(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_mixed_html_pdf_embeds": False})

    def rows(view):
        with runtime.repo.connect() as conn:
            source = conn.execute(
                "SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                (view["source_revision_id"],),
            ).fetchone()
            canonical = conn.execute(
                "SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                (view["canonical_revision_id"],),
            ).fetchone()
        return source, canonical

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture",
                                  reason="place bound PDF in mixed HAL", rewrite_profile_version=AUTO_PROFILE)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=draft, job_id=job.job_id)
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    with monkeypatch.context() as old:
        old.setattr(capture_module, "capture_source_article", old_projection)
        previous = refresh()
    prior_source, prior_canonical = rows(previous)
    assert _LAYOUT[0] not in prior_source["resource_manifest"][0]
    assert _INSPECTION not in prior_source["source_body"]
    assert all(image["status"] != "available" for image in previous["images"])

    corrected = refresh()
    source, canonical = rows(corrected)
    assert corrected["source_revision_id"] != previous["source_revision_id"]
    assert corrected["canonical_revision_id"] != previous["canonical_revision_id"]
    assert source["body_source_snapshot_id"] == prior_source["body_source_snapshot_id"]
    assert source["resource_manifest"][0][_LAYOUT[0]] == _LAYOUT[1]
    assert _outline(source["source_document"]["blocks"]) == [
        ("paragraph", _OPENING), *_PDF_CONTENT, ("paragraph", _CLOSING),
    ]
    assert _outline(canonical["canonical_document"]["blocks"][1:]) == [
        ("paragraph", "Take off the pump."), ("paragraph", "Check the seal."),
        ("image", None), ("paragraph", "Fit the replacement unit."),
    ]
    [image] = corrected["images"]
    _assert_pixels(runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20), pixels)
    repeated = refresh()
    assert repeated["source_revision_id"] == corrected["source_revision_id"]
    assert repeated["canonical_revision_id"] == corrected["canonical_revision_id"]
    assert rows(repeated) == (source, canonical)
    assert rows(previous) == (prior_source, prior_canonical)
    assert len(draft.requests) == 2
