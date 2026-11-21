"""Verify supplier table sequences around retained figures."""

import json
from uuid import uuid4

import pytest

from autodata_ingestion import source_article_capture
from autodata_ingestion.article_document import validate_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import STRUCTURED_TABLE_CELL_ORDER_LAYOUT
from autodata_ingestion.procedure_normalize import normalize_procedure_article
from autodata_ingestion.procedure_rewrite_auto import PROFILE, render_auto, validate_auto
from autodata_ingestion.procedure_rewrite_full import prose_slots
from autodata_ingestion.source_job_persistence import refresh_article_job

from lifecycle_support import fresh_database, runtime
from test_source_article_capture import capture_fixture
from test_workshop_linked_pdf import FixtureDraft, _INTRODUCTION, _PARAPHRASES
from test_workshop_table_column_media import _fixture_png


def _supplier_body(provider):
    figure = {"kind": "image", "asset_resource_ref": "figure", "alt": "Inner seal diagram"}
    ordered = [
        {"kind": "text", "text": "Inspect the inner seal first."}, figure,
        {"kind": "warning", "label": "Warning", "text": "Do not reuse the outer seal."},
    ]
    legacy_cell = {"blocks": [{"kind": "text", "text": "Inspect the spare seal."}, figure],
                   "_ordered_html_table_cell": True, "_preserve_cell_block_order": True}
    rows = [["Drive seal", {"blocks": ordered}], ["Spare seal", legacy_cell]]
    if provider == "banktwo":
        rows = [{"cells": row} for row in rows]
    article = {"blocks": [
        {"type": "paragraph", "text": "Remove the pump."},
        {"type": "table", "label": "Seal positions", "columns": ["Part", "Inspection"], "rows": rows},
        {"type": "paragraph", "text": "Inspect the seal."},
        {"type": "paragraph", "text": "Install the replacement."},
    ]}
    if provider == "banktwo":
        return json.dumps({"_embedded": {"data": {"article": article}}}).encode(), "application/hal+json"
    return json.dumps(article).encode(), "application/json"


@pytest.mark.parametrize("provider,available", [("bankone", True), ("banktwo", True), ("banktwo", False)])
def test_structured_table_keeps_figure_before_its_following_warning(capture_fixture, provider, available):
    raw, media = _supplier_body(provider)
    figure = _fixture_png()
    capture_fixture.body(provider, raw, media, assets=["figure"])
    if available:
        capture_fixture.body(provider, figure, "image/png", kind="asset", ref="figure")
    context = capture_fixture.context(provider)
    options = dict(registry=capture_fixture.registry, object_store=capture_fixture.objects)
    legacy = source_article_capture.capture_source_article(context, **options)
    captured = source_article_capture.capture_source_article(context, keep_structured_table_cell_order=True, **options)
    old = legacy.source_document["blocks"][1]["rows"][0][1]
    assert old["text"] == "Inspect the inner seal first. Do not reuse the outer seal."
    assert old["images"][0]["alt"] == "Inner seal diagram"
    assert legacy.body_source_snapshot_id == captured.body_source_snapshot_id
    assert legacy.source_fingerprint != captured.source_fingerprint
    assert captured.resource_manifest[0]["structured_table_cell_order_layout"] == STRUCTURED_TABLE_CELL_ORDER_LAYOUT
    assert captured.resource_manifest[1:] == legacy.resource_manifest[1:]
    assert captured.evidence_manifest == legacy.evidence_manifest
    assert captured.projection_status == ("readable" if available else "partial")
    assert not validate_ordered_document(captured.source_document, strict=True)

    table = captured.source_document["blocks"][1]
    cell = table["rows"][0][1]
    before, image, after = cell["blocks"]
    assert cell["protected_text"] is True
    assert before["type"] == "paragraph" and before["text"] == "Inspect the inner seal first."
    assert image["type"] == "image" and image["alt"] == "Inner seal diagram"
    assert after["type"] == "callout" and after["label"] == "Warning"
    assert after["text"] == "Do not reuse the outer seal."
    assert image["image_id"] == old["images"][0]["image_id"]
    assert table["rows"][1] == legacy.source_document["blocks"][1]["rows"][1]
    if available:
        assert capture_fixture.objects.data[image["storage_key"]] == (figure, "image/png")
    else:
        assert image["status"] == "unavailable" and image["unavailable_reason"] == "SOURCE_NOT_FOUND"

    normalized = normalize_procedure_article({
        "normalized_document": captured.source_document, "body": captured.source_body, "steps": captured.source_steps,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]
    slots = prose_slots(normalized, include_cell_blocks=True)
    assert [slot["text"] for slot in slots] == list(_PARAPHRASES)
    response = {"introduction": _INTRODUCTION, "replacements": [
        {**slot, "action": "rewrite", "text": _PARAPHRASES[slot["text"]], "reason": ""} for slot in slots
    ]}
    canonical = render_auto(normalized, response)
    assert validate_auto(normalized, canonical, response=response).passed
    assert canonical["blocks"][2]["rows"] == table["rows"]


def test_structured_table_publishes_ordered_cell_without_changing_original(runtime, monkeypatch):
    provider = "banktwo"
    runtime.article_id = runtime.articles[provider]
    raw, media = _supplier_body(provider)
    figure = _fixture_png()
    connector = runtime.servers[provider]
    connector.body(raw, media, assets=["figure"])
    connector.body(figure, "image/png", kind="asset", ref="figure")
    capture = source_article_capture.capture_source_article
    draft = FixtureDraft()

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_structured_table_cell_order": False})

    def refresh():
        job = refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="check table sequence",
                                  rewrite_profile_version=PROFILE)
        assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                       object_store=runtime.objects, model_client=draft, job_id=job.job_id)
        view = runtime.read_current()
        assert view["content_origin"] == "canonical", runtime.diagnostics()
        return view

    def source(revision):
        with runtime.repo.connect() as conn:
            return conn.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                (revision,)).fetchone()

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        previous = refresh()
    previous_source = source(previous["source_revision_id"])
    current = refresh()
    current_source = source(current["source_revision_id"])
    assert previous["canonical_revision_id"] != current["canonical_revision_id"]
    assert previous_source["body_source_snapshot_id"] == current_source["body_source_snapshot_id"]
    assert previous_source["resource_manifest"][1:] == current_source["resource_manifest"][1:]
    assert source(previous["source_revision_id"]) == previous_source
    cell = current["document"]["blocks"][2]["rows"][0][1]
    assert cell == current_source["source_document"]["blocks"][1]["rows"][0][1]
    assert [block["type"] for block in cell["blocks"]] == ["paragraph", "image", "callout"]
    assert runtime.objects.get_object(cell["blocks"][1]["storage_key"], max_bytes=1 << 20) == figure
    assert refresh()["canonical_revision_id"] == current["canonical_revision_id"] and len(draft.requests) == 2
